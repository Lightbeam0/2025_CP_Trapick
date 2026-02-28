# ml/enhanced_tracker.py
"""
EnhancedByteTrackWrapper — v3.0
────────────────────────────────────────────────────────────────────────────
New vs v2:

  Ghost-track recovery
    When a vehicle disappears (occlusion, detector dropout) for ≤ ghost_frames
    frames, the next detection with sufficient IoU overlap is re-linked to the
    original track_id instead of being assigned a new one.  This eliminates
    the most common source of double-counting: a parked vehicle partially
    visible → invisible → reappears and gets a fresh ID that crosses the line.

  Cross-frame NMS deduplication
    If two active tracks in the same frame share IoU > nms_iou_threshold and
    are the same class, the lower-confidence one is suppressed.  Prevents the
    tracker from reporting the same physical vehicle as two IDs.

  Savitzky-Golay speed smoothing
    Per-track raw pixel-distance samples are collected in a rolling window.
    A polynomial SG filter (window=5, poly=2) smooths the result instead of
    plain EMA.  Benefits: better shape preservation through accelerations /
    decelerations; far less sensitive to single-frame jitter; no scipy needed.

  Eviction callback
    _evict_one() calls an optional callable(track_id) when it removes a stale
    track, letting BaseDirectionalDetector clean up its vehicle_status dict
    (fixes the unbounded memory growth identified in the code review).

All v2 features retained (Kalman filter, adaptive confidence EMA, heading,
area-continuity validation, fleet stats).
"""

import numpy as np
from collections import deque, defaultdict
import math
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Kalman filter  (unchanged from v2)
# ─────────────────────────────────────────────────────────────────────────────

class KalmanFilter:
    """Constant-velocity 2-D position Kalman filter (state: x, y, vx, vy)."""

    def __init__(self, dt=1.0):
        self.dt = dt
        self.A = np.array([[1, 0, dt, 0],
                           [0, 1, 0, dt],
                           [0, 0, 1,  0],
                           [0, 0, 0,  1]], dtype=float)
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]], dtype=float)
        self.Q = np.eye(4) * 0.05
        self.R = np.eye(2) * 0.5
        self.P = np.eye(4) * 100.0
        self.x = np.zeros((4, 1))
        self.initialized = False

    def init(self, x, y):
        self.x = np.array([[x], [y], [0.0], [0.0]])
        self.P = np.eye(4) * 100.0
        self.initialized = True

    def predict(self):
        if not self.initialized:
            return None, None
        self.x = self.A @ self.x
        self.P = self.A @ self.P @ self.A.T + self.Q
        return float(self.x[0, 0]), float(self.x[1, 0])

    def update(self, x, y):
        if not self.initialized:
            self.init(x, y)
            return
        z = np.array([[x], [y]])
        y_v = z - self.H @ self.x
        S   = self.H @ self.P @ self.H.T + self.R
        K   = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y_v
        self.P = (np.eye(4) - K @ self.H) @ self.P


# ─────────────────────────────────────────────────────────────────────────────
# Savitzky-Golay smoother  (scipy-free)
# ─────────────────────────────────────────────────────────────────────────────

# Pre-computed SG coefficients for window=5, polynomial degree=2, derivative=0.
# Source: standard SG coefficient table.
_SG5 = np.array([-3.0, 12.0, 17.0, 12.0, -3.0]) / 35.0


def _smooth_speed(raw_speeds):
    """
    Smooth a list of raw speed samples.

    Uses Savitzky-Golay (window 5) when ≥5 samples are available,
    falls back to the mean otherwise.  Returns a single float or None.
    """
    n = len(raw_speeds)
    if n == 0:
        return None
    arr = np.array(raw_speeds, dtype=float)
    if n < 5:
        return float(np.mean(arr))
    return float(np.dot(_SG5, arr[-5:]))


# ─────────────────────────────────────────────────────────────────────────────
# IoU helper
# ─────────────────────────────────────────────────────────────────────────────

def _box_iou(b1, b2):
    """IoU between two [x, y, w, h] boxes.  Returns 0.0–1.0."""
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    ax1, ay1, ax2, ay2 = x1, y1, x1 + w1, y1 + h1
    bx1, by1, bx2, by2 = x2, y2, x2 + w2, y2 + h2
    iw = max(0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Main tracker wrapper
# ─────────────────────────────────────────────────────────────────────────────

class EnhancedByteTrackWrapper:

    MIN_TRACK_FRAMES_BEFORE_COUNT = 6
    MAX_RAW_SPEED_KMH             = 180.0

    def __init__(self,
                 config_path="bytetrack.yaml",
                 ghost_frames=8,
                 iou_ghost_threshold=0.40,
                 nms_iou_threshold=0.60,
                 eviction_callback=None):
        """
        Parameters
        ----------
        ghost_frames : int
            A lost track is kept as a "ghost" for this many frames so a
            re-appearing vehicle can be linked back to its original ID.
        iou_ghost_threshold : float
            Minimum IoU between a new detection and a ghost's last box
            to trigger re-linking.
        nms_iou_threshold : float
            IoU above which two same-frame, same-class detections are
            treated as duplicates; only the higher-confidence one is kept.
        eviction_callback : callable(track_id) | None
            Called whenever a stale track is fully removed.  Pass a lambda
            that cleans up BaseDirectionalDetector.vehicle_status to fix
            the memory leak identified in the code review.
        """
        self.config_path         = config_path
        self.ghost_frames        = ghost_frames
        self.iou_ghost_threshold = iou_ghost_threshold
        self.nms_iou_threshold   = nms_iou_threshold
        self.eviction_callback   = eviction_callback

        # Per-track history (x, y, w, h)
        self.track_history       = defaultdict(lambda: deque(maxlen=90))
        self.track_confidences   = defaultdict(lambda: deque(maxlen=20))
        self.track_last_frame    = {}

        # Speed: raw samples → SG smoothed
        self.track_speed_raw     = defaultdict(lambda: deque(maxlen=15))
        self.track_speed_smooth  = {}       # latest smoothed value
        self.speed_ema_alpha     = 0.25     # adjusted by night-mode in base_directional

        # Acceleration EMA
        self.track_accel_ema     = {}
        self.accel_ema_alpha     = 0.20

        # Heading
        self.track_heading       = {}

        # Bounding-box area EMA for continuity check
        self.track_area_ema      = {}
        self.area_ema_alpha      = 0.30

        # Kalman filters
        self.kalman_filters      = {}

        # Confidence EMA
        self.track_conf_ema      = defaultdict(float)

        # Ghost registry: track_id → {box, center, last_frame, cid}
        self.ghost_registry      = {}

        # Appearance features (aspect ratio, conf) for Re-ID
        self.appearance_features = defaultdict(lambda: deque(maxlen=5))

        self.class_names = {1: 'car', 2: 'jeep', 3: 'motorcycle',
                            5: 'tricycle', 6: 'truck'}

        self.class_tracking_params = {
            'car':        {'min_size': 350,  'stability_threshold': 0.40},
            'jeep':       {'min_size': 450,  'stability_threshold': 0.40},
            'motorcycle': {'min_size': 100,  'stability_threshold': 0.30},
            'tricycle':   {'min_size': 200,  'stability_threshold': 0.35},
            'truck':      {'min_size': 600,  'stability_threshold': 0.45},
        }

        logger.info("🚀 EnhancedByteTrackWrapper v3.0 "
                    "(ghost_recovery + cross_nms + SG_speed + eviction_cb)")

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_eviction_callback(self, cb):
        self.eviction_callback = cb

    def postprocess_tracks(self, yolo_results, frame_number, fps):
        """
        Full post-processing pipeline:
          1. Extract boxes / IDs / classes from YOLO output.
          2. Ghost-track recovery (re-link returning vehicles).
          3. Cross-frame NMS (deduplicate overlapping detections).
          4. Per-track Kalman, confidence-EMA, SG speed, heading, validation.
          5. Evict stale tracks, fire eviction callbacks.
        Returns a list of enriched track dicts.
        """
        processed = []

        if not yolo_results or not len(yolo_results):
            self._evict_stale(frame_number)
            return processed

        result = yolo_results[0]
        if result.boxes is None or result.boxes.id is None:
            self._evict_stale(frame_number)
            return processed

        boxes  = result.boxes.xyxy.cpu().numpy()
        tids   = result.boxes.id.int().cpu().numpy()
        cids   = result.boxes.cls.int().cpu().numpy()
        confs  = result.boxes.conf.float().cpu().numpy()

        # Step 1: build raw detection list
        raw = []
        for box, tid, cid, conf in zip(boxes, tids, cids, confs):
            if int(cid) not in self.class_names:
                continue
            x1, y1, x2, y2 = box
            w, h = x2 - x1, y2 - y1
            raw.append({
                'tid':      int(tid),
                'cid':      int(cid),
                'conf':     float(conf),
                'box':      [int(x1), int(y1), int(w), int(h)],
                'center':   ((x1 + x2) / 2, (y1 + y2) / 2),
            })

        # Step 2: ghost recovery
        raw = self._ghost_recovery(raw, frame_number)

        # Step 3: cross-frame NMS
        raw = self._cross_nms(raw)

        # Step 4: per-track processing
        for det in raw:
            tid        = det['tid']
            cid        = det['cid']
            conf       = det['conf']
            x, y, w, h = det['box']
            cx, cy     = det['center']
            area       = w * h
            class_name = self.class_names[cid]

            area_valid = self._check_area_continuity(tid, area)
            self.track_history[tid].append((cx, cy, w, h))
            self.track_confidences[tid].append(conf)
            self.track_last_frame[tid] = frame_number
            self._update_area_ema(tid, area)
            self.appearance_features[tid].append([w / max(h, 1), conf])

            # Kalman
            kalman_center  = (int(cx), int(cy))
            position_error = 0.0
            if tid not in self.kalman_filters:
                kf = KalmanFilter(dt=1.0 / fps if fps > 0 else 1.0 / 30)
                kf.init(cx, cy)
                self.kalman_filters[tid] = kf
            else:
                kf = self.kalman_filters[tid]
                px, py = kf.predict()
                if px is not None:
                    position_error = math.hypot(px - cx, py - cy)
                    kalman_center  = (int(px), int(py))
                kf.update(cx, cy)

            # Adaptive confidence EMA
            prev_ema = self.track_conf_ema.get(tid, conf)
            conf_ema = 0.3 * conf + 0.7 * prev_ema
            self.track_conf_ema[tid] = conf_ema

            track_len  = len(self.track_history[tid])
            stability  = self._stability(tid)
            is_valid   = self._validate(tid, class_name, area, stability) and area_valid

            speed  = self._sg_speed(tid, fps)
            accel  = self._accel(tid, fps, speed)
            heading = self._heading(tid)

            counting_eligible = (
                track_len >= 3 if conf_ema > 0.7
                else track_len >= self.MIN_TRACK_FRAMES_BEFORE_COUNT
            )

            processed.append({
                'track_id':         tid,
                'box':              [int(x), int(y), int(w), int(h)],
                'center':           kalman_center,
                'raw_center':       (int(cx), int(cy)),
                'class_id':         cid,
                'class_name':       class_name,
                'confidence':       conf,
                'confidence_ema':   float(conf_ema),
                'stability':        float(stability),
                'is_valid':         bool(is_valid),
                'area':             float(area),
                'area_valid':       bool(area_valid),
                'frame_number':     frame_number,
                'track_length':     track_len,
                'counting_eligible': counting_eligible,
                'speed':            speed,
                'acceleration':     accel,
                'heading':          heading,
                'is_stationary':    (speed is not None and speed < 3.0),
                'position_error':   round(position_error, 2),
                'kalman_center':    kalman_center,
            })

            # Refresh ghost entry with current position
            self.ghost_registry[tid] = {
                'box':        det['box'],
                'center':     (cx, cy),
                'last_frame': frame_number,
                'cid':        cid,
            }

        self._evict_stale(frame_number)
        return processed

    # ─────────────────────────────────────────────────────────────────────────
    # Ghost-track recovery
    # ─────────────────────────────────────────────────────────────────────────

    def _ghost_recovery(self, raw_dets, frame_number):
        """
        For each detection whose ID has never been seen before (brand-new to
        our track_last_frame dict), check whether it overlaps a recently-lost
        ghost.  If IoU ≥ iou_ghost_threshold AND the classes match, reassign
        the detection to the ghost's track_id.

        This prevents occlusion-caused detector dropout from spawning a fresh
        ID and producing a duplicate crossing.
        """
        current_ids = {d['tid'] for d in raw_dets}

        # Ghosts: lost tracks still within the grace window
        active_ghosts = {
            tid: g for tid, g in self.ghost_registry.items()
            if tid not in current_ids
            and frame_number - g['last_frame'] <= self.ghost_frames
        }

        if not active_ghosts:
            return raw_dets

        remapped   = []
        used_ghost = set()

        for det in raw_dets:
            # Only try to re-link truly new IDs
            if det['tid'] in self.track_last_frame:
                remapped.append(det)
                continue

            best_iou, best_gid = self.iou_ghost_threshold - 1e-6, None

            for gid, ghost in active_ghosts.items():
                if gid in used_ghost or ghost['cid'] != det['cid']:
                    continue
                iou = _box_iou(det['box'], ghost['box'])
                if iou > best_iou:
                    best_iou, best_gid = iou, gid

            if best_gid is not None:
                logger.debug(f"👻 Ghost-link: new {det['tid']} → old {best_gid} "
                             f"(IoU={best_iou:.2f})")
                det = dict(det)
                det['tid'] = best_gid
                used_ghost.add(best_gid)

            remapped.append(det)

        return remapped

    # ─────────────────────────────────────────────────────────────────────────
    # Cross-frame NMS
    # ─────────────────────────────────────────────────────────────────────────

    def _cross_nms(self, raw_dets):
        """
        Suppress duplicate detections of the same physical vehicle that
        receive two track IDs in a single frame.

        Sort by confidence (descending).  For each pair of same-class
        detections with IoU ≥ nms_iou_threshold, discard the one with lower
        confidence.
        """
        if len(raw_dets) < 2:
            return raw_dets

        dets       = sorted(raw_dets, key=lambda d: d['conf'], reverse=True)
        suppressed = set()
        keep       = []

        for i, di in enumerate(dets):
            if i in suppressed:
                continue
            keep.append(di)
            for j in range(i + 1, len(dets)):
                if j in suppressed or dets[j]['cid'] != di['cid']:
                    continue
                if _box_iou(di['box'], dets[j]['box']) >= self.nms_iou_threshold:
                    logger.debug(f"🔁 NMS: drop {dets[j]['tid']} "
                                 f"(overlaps {di['tid']})")
                    suppressed.add(j)

        return keep

    # ─────────────────────────────────────────────────────────────────────────
    # Speed: Savitzky-Golay smoothed
    # ─────────────────────────────────────────────────────────────────────────

    def _sg_speed(self, tid, fps, px_per_m=10):
        """
        Compute the instantaneous pixel displacement between the two most-
        recent positions, convert to km/h, accumulate in a rolling buffer,
        and apply SG smoothing.

        Compared to pure EMA:
          - Preserves acceleration / deceleration events better.
          - Significantly less sensitive to single-frame jitter.
          - No scipy dependency (coefficients are hard-coded above).
        """
        hist = self._xy_history(tid)
        if len(hist) < 2:
            return None

        dist_px = math.hypot(hist[-1][0] - hist[-2][0],
                             hist[-1][1] - hist[-2][1])

        if fps <= 0 or px_per_m <= 0:
            return None

        raw_kmh = (dist_px / px_per_m) * fps * 3.6

        if not math.isfinite(raw_kmh) or raw_kmh > self.MAX_RAW_SPEED_KMH:
            raw_kmh = self.track_speed_smooth.get(tid) or 0.0

        self.track_speed_raw[tid].append(raw_kmh)
        smoothed = _smooth_speed(list(self.track_speed_raw[tid]))

        if smoothed is None or not math.isfinite(smoothed):
            return None

        smoothed = max(0.0, smoothed)
        self.track_speed_smooth[tid] = smoothed
        return round(smoothed, 1)

    # Public alias kept for callers that use the v2 name
    def get_smoothed_speed(self, track_id, fps, pixels_per_meter=10, window=12):
        return self._sg_speed(track_id, fps, pixels_per_meter)

    # ─────────────────────────────────────────────────────────────────────────
    # Eviction
    # ─────────────────────────────────────────────────────────────────────────

    def _evict_stale(self, current_frame, max_missing=90):
        stale = [tid for tid, lf in self.track_last_frame.items()
                 if current_frame - lf > max_missing]
        for tid in stale:
            self._evict_one(tid)

        expired = [tid for tid, g in self.ghost_registry.items()
                   if current_frame - g['last_frame']
                   > max(self.ghost_frames, max_missing)]
        for tid in expired:
            self.ghost_registry.pop(tid, None)

    def _evict_one(self, tid):
        for store in (self.track_history, self.track_confidences,
                      self.track_last_frame, self.track_speed_raw,
                      self.track_speed_smooth, self.track_accel_ema,
                      self.track_heading, self.track_area_ema,
                      self.kalman_filters, self.track_conf_ema,
                      self.appearance_features, self.ghost_registry):
            store.pop(tid, None)

        if self.eviction_callback is not None:
            try:
                self.eviction_callback(tid)
            except Exception as e:
                logger.debug(f"Eviction callback error for {tid}: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _xy_history(self, tid):
        return [(x, y) for x, y, _, _ in self.track_history[tid]]

    # Alias used by base_directional
    def get_track_history(self, tid):
        return self._xy_history(tid)

    def _accel(self, tid, fps, current_speed):
        if current_speed is None:
            return None
        prev = self.track_speed_smooth.get(tid)
        if prev is None:
            return None
        raw = (current_speed - prev) * fps
        pa  = self.track_accel_ema.get(tid)
        ema = (self.accel_ema_alpha * raw + (1 - self.accel_ema_alpha) * pa
               if pa is not None else raw)
        self.track_accel_ema[tid] = ema
        return round(ema, 2)

    def _heading(self, tid):
        hist = self._xy_history(tid)
        if len(hist) < 4:
            return None
        pts = hist[-4:]
        dx, dy = pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]
        if math.hypot(dx, dy) < 2:
            return None
        angle   = math.degrees(math.atan2(dx, -dy)) % 360
        idx     = int((angle + 22.5) / 45) % 8
        heading = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][idx]
        self.track_heading[tid] = heading
        return heading

    def _update_area_ema(self, tid, area):
        prev = self.track_area_ema.get(tid)
        self.track_area_ema[tid] = (
            self.area_ema_alpha * area + (1 - self.area_ema_alpha) * prev
            if prev is not None else area
        )

    def _check_area_continuity(self, tid, area):
        prev = self.track_area_ema.get(tid)
        if prev is None or prev < 1:
            return True
        return 0.25 <= area / prev <= 4.0

    def _stability(self, tid):
        hist = list(self.track_history[tid])
        if len(hist) < 4:
            return 0.0
        vecs = []
        for i in range(1, len(hist)):
            px, py, _, _ = hist[i - 1]
            cx, cy, _, _ = hist[i]
            m = math.hypot(cx - px, cy - py)
            if m > 0.5:
                vecs.append(((cx - px) / m, (cy - py) / m))
        if len(vecs) < 2:
            return 0.5
        dots = [vecs[i][0] * vecs[i+1][0] + vecs[i][1] * vecs[i+1][1]
                for i in range(len(vecs) - 1)]
        return float(max(0.0, min(1.0, (float(np.mean(dots)) + 1.0) / 2.0)))

    def _validate(self, tid, class_name, area, stability):
        params = self.class_tracking_params.get(class_name)
        if params is None:
            return True
        if area < params['min_size']:
            return False
        if (len(self.track_history[tid]) >= self.MIN_TRACK_FRAMES_BEFORE_COUNT
                and stability < params['stability_threshold']):
            return False
        return True

    def get_fleet_stats(self):
        speeds = [s for s in self.track_speed_smooth.values() if s is not None]
        return {
            'active_tracks':    len(self.track_last_frame),
            'mean_speed_kmh':   round(float(np.mean(speeds)),   1) if speeds else None,
            'median_speed_kmh': round(float(np.median(speeds)), 1) if speeds else None,
            'max_speed_kmh':    round(float(np.max(speeds)),    1) if speeds else None,
            'pct_stationary':   round(
                sum(1 for s in speeds if s < 3.0) / len(speeds) * 100, 1
            ) if speeds else 0.0,
        }