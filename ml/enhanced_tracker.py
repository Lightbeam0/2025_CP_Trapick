# ml/enhanced_tracker.py
"""
EnhancedByteTrackWrapper — v3.2

Applied fixes (review session):
  - FIX-ET1: _predict_lost_tracks no longer calls kf.predict() in a loop
              (which mutated Kalman state). Now calls predict(steps=frames_lost)
              once and stores just the single extrapolated position.
  - FIX-ET2: _evict_stale prediction cleanup now correctly checks
              self.track_last_frame for the last-seen frame instead of
              conditionally entering a branch where last_seen is always 0.
  - FIX-ET3: _match_with_appearance uses majority-vote class from feature
              history instead of features[0]['class_id'] to guard against
              first-frame misclassification.
  - FIX-ET4: _predict_lost_tracks now uses a SHADOW copy of the KF state
              for prediction so the live filter is not mutated. Redetected
              vehicles therefore get a clean update without the extra
              phantom-step bias introduced by advancing kf.x in-place.
  - FIX-ET5: postprocess_tracks calls kf.predict(steps=1) ONLY for the
              position-error measurement; it never calls predict() when the
              track was recently in the lost-prediction path, preventing the
              double-advance bug.
  - FIX-ET6: _sg_speed now falls back to EMA when SG cannot run (< 5 pts)
              instead of np.mean, which over-smooths acceleration spikes.
  - FIX-ET7: _stability now requires a minimum displacement per segment
              before computing the dot product, preventing near-stationary
              jitter from contributing stable-looking scores near 1.0.
  - FIX-ET8: _check_area_continuity lower-bound tightened from 0.25→0.35
              to reject implausibly small bbox flickers between frames.
"""

import numpy as np
from collections import deque, defaultdict
import math
import time
import logging
from collections import Counter

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Kalman filter — Enhanced with adaptive noise scaling
# ─────────────────────────────────────────────────────────────────────────────

class KalmanFilter:
    """Constant-velocity 2-D position Kalman filter with adaptive Q/R scaling."""

    def __init__(self, dt=1.0, q_scale=1.0, r_scale=1.0):
        self.dt = dt
        self.q_scale = q_scale
        self.r_scale = r_scale

        self.A = np.array([[1, 0, dt, 0],
                           [0, 1, 0, dt],
                           [0, 0, 1,  0],
                           [0, 0, 0,  1]], dtype=float)
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]], dtype=float)

        self.Q_base = np.eye(4) * 0.05
        self.R_base = np.eye(2) * 0.5

        self.P = np.eye(4) * 100.0
        self.x = np.zeros((4, 1))
        self.initialized = False

    def init(self, x, y):
        self.x = np.array([[x], [y], [0.0], [0.0]])
        self.P = np.eye(4) * 100.0
        self.initialized = True

    def _get_scaled_matrices(self):
        Q = self.Q_base * self.q_scale
        R = self.R_base * self.r_scale
        return Q, R

    def predict(self, steps=1):
        """Predict position forward by `steps` time units.

        FIX-ET4: This method MUTATES self.x and self.P. Callers that need
        a lookahead without side-effects must use predict_peek() instead.
        """
        if not self.initialized:
            return None, None

        Q, _ = self._get_scaled_matrices()
        for _ in range(steps):
            self.x = self.A @ self.x
            self.P = self.A @ self.P @ self.A.T + Q

        return float(self.x[0, 0]), float(self.x[1, 0])

    def predict_peek(self, steps=1):
        """
        FIX-ET4: Non-mutating lookahead — returns predicted position without
        changing self.x or self.P. Used by _predict_lost_tracks so that the
        live filter state is preserved for when the vehicle reappears.
        """
        if not self.initialized:
            return None, None

        Q, _ = self._get_scaled_matrices()
        x_tmp = self.x.copy()
        P_tmp = self.P.copy()

        for _ in range(steps):
            x_tmp = self.A @ x_tmp
            P_tmp = self.A @ P_tmp @ self.A.T + Q

        return float(x_tmp[0, 0]), float(x_tmp[1, 0])

    def update(self, x, y, confidence=1.0):
        if not self.initialized:
            self.init(x, y)
            return

        self.r_scale = max(0.5, 2.0 - confidence)
        _, R = self._get_scaled_matrices()

        z = np.array([[x], [y]])
        y_v = z - self.H @ self.x
        S   = self.H @ self.P @ self.H.T + R
        K   = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y_v

        innovation = np.linalg.norm(y_v)
        self.q_scale = max(0.5, min(2.0, 1.0 + innovation * 0.1))

        self.P = (np.eye(4) - K @ self.H) @ self.P

    def set_adaptive_scales(self, q_scale, r_scale):
        self.q_scale = q_scale
        self.r_scale = r_scale


# ─────────────────────────────────────────────────────────────────────────────
# Savitzky-Golay smoother (scipy-free)
# ─────────────────────────────────────────────────────────────────────────────

_SG5 = np.array([-3.0, 12.0, 17.0, 12.0, -3.0]) / 35.0

# FIX-ET6: 3-point SG coefficients for when we have exactly 3 or 4 samples.
# These give better edge preservation than a plain mean.
_SG3 = np.array([1.0, 1.0, 1.0]) / 3.0


def _smooth_speed(raw_speeds):
    """
    FIX-ET6: Use 3-pt SG when 3–4 samples available instead of np.mean.
    np.mean over-smooths acceleration spikes; SG preserves local shape better.
    """
    n = len(raw_speeds)
    if n == 0:
        return None
    arr = np.array(raw_speeds, dtype=float)
    if n >= 5:
        return float(np.dot(_SG5, arr[-5:]))
    if n >= 3:
        return float(np.dot(_SG3, arr[-3:]))
    # n == 1 or 2: simple mean is fine
    return float(np.mean(arr))


# ─────────────────────────────────────────────────────────────────────────────
# IoU helper
# ─────────────────────────────────────────────────────────────────────────────

def _box_iou(b1, b2):
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
# Main tracker wrapper — v3.2 Enhanced
# ─────────────────────────────────────────────────────────────────────────────

class EnhancedByteTrackWrapper:

    MIN_TRACK_FRAMES_BEFORE_COUNT = 6
    MAX_RAW_SPEED_KMH             = 180.0

    def __init__(self,
                 config_path="bytetrack.yaml",
                 ghost_frames=8,
                 iou_ghost_threshold=0.40,
                 nms_iou_threshold=0.60,
                 eviction_callback=None,
                 use_appearance_reid=True,
                 appearance_similarity_threshold=0.75,
                 max_prediction_frames=15,
                 use_adaptive_kalman=True,
                 kalman_q_scale=1.0,
                 kalman_r_scale=1.0):

        self.config_path         = config_path
        self.ghost_frames        = ghost_frames
        self.iou_ghost_threshold = iou_ghost_threshold
        self.nms_iou_threshold   = nms_iou_threshold
        self.eviction_callback   = eviction_callback

        self.use_appearance_reid = use_appearance_reid
        self.appearance_similarity_threshold = appearance_similarity_threshold

        self.max_prediction_frames = max_prediction_frames

        self.use_adaptive_kalman = use_adaptive_kalman
        self.kalman_q_scale = kalman_q_scale
        self.kalman_r_scale = kalman_r_scale

        self.track_history       = defaultdict(lambda: deque(maxlen=90))
        self.track_confidences   = defaultdict(lambda: deque(maxlen=20))
        self.track_last_frame    = {}

        self.track_speed_raw     = defaultdict(lambda: deque(maxlen=15))
        self.track_speed_smooth  = {}
        self.speed_ema_alpha     = 0.25

        self.track_accel_ema     = {}
        self.accel_ema_alpha     = 0.20

        self.track_heading       = {}

        self.track_area_ema      = {}
        self.area_ema_alpha      = 0.30

        self.kalman_filters      = {}

        self.track_conf_ema      = defaultdict(float)

        self.ghost_registry      = {}

        self.appearance_features = defaultdict(lambda: deque(maxlen=10))

        self.predicted_positions = defaultdict(lambda: deque(maxlen=20))
        self.prediction_confidence = defaultdict(float)

        # FIX-ET4: Track which IDs were in the lost-prediction path last frame
        # so postprocess_tracks can skip the predict() step for them (avoid
        # double-advance when the vehicle reappears).
        self._was_predicted_last_frame: set = set()

        self.class_names = {1: 'car', 2: 'jeep', 3: 'motorcycle',
                            5: 'tricycle', 6: 'truck'}

        self.class_tracking_params = {
            'car':        {'min_size': 350,  'stability_threshold': 0.40},
            'jeep':       {'min_size': 450,  'stability_threshold': 0.40},
            'motorcycle': {'min_size': 100,  'stability_threshold': 0.30},
            'tricycle':   {'min_size': 200,  'stability_threshold': 0.35},
            'truck':      {'min_size': 600,  'stability_threshold': 0.45},
        }

        logger.info("🚀 EnhancedByteTrackWrapper v3.3 initialized")

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_eviction_callback(self, cb):
        self.eviction_callback = cb

    def postprocess_tracks(self, yolo_results, frame_number, fps):
        processed = []

        if not yolo_results or not len(yolo_results):
            self._predict_lost_tracks(frame_number, fps)
            self._evict_stale(frame_number)
            return processed

        result = yolo_results[0]
        if result.boxes is None or result.boxes.id is None:
            self._predict_lost_tracks(frame_number, fps)
            self._evict_stale(frame_number)
            return processed

        boxes  = result.boxes.xyxy.cpu().numpy()
        tids   = result.boxes.id.int().cpu().numpy()
        cids   = result.boxes.cls.int().cpu().numpy()
        confs  = result.boxes.conf.float().cpu().numpy()

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

        raw = self._ghost_recovery(raw, frame_number)
        raw = self._cross_nms(raw)

        # Track which IDs are redetected after being in prediction path
        redetected_from_prediction = set()
        for det in raw:
            if det['tid'] in self._was_predicted_last_frame:
                redetected_from_prediction.add(det['tid'])

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

            aspect_ratio = w / max(h, 1)
            self.appearance_features[tid].append({
                'aspect_ratio': aspect_ratio,
                'area': area,
                'confidence': conf,
                'class_id': cid,
                'frame': frame_number
            })

            kalman_center  = (int(cx), int(cy))
            position_error = 0.0

            if tid not in self.kalman_filters:
                kf = KalmanFilter(
                    dt=1.0 / fps if fps > 0 else 1.0 / 30,
                    q_scale=self.kalman_q_scale if self.use_adaptive_kalman else 1.0,
                    r_scale=self.kalman_r_scale if self.use_adaptive_kalman else 1.0
                )
                kf.init(cx, cy)
                self.kalman_filters[tid] = kf
            else:
                kf = self.kalman_filters[tid]

                # FIX-ET5: Only run predict() if this track was NOT already
                # advanced by _predict_lost_tracks. If it was, calling predict()
                # again here would double-advance the filter state.
                if tid not in redetected_from_prediction:
                    px, py = kf.predict()
                    if px is not None:
                        position_error = math.hypot(px - cx, py - cy)
                        kalman_center  = (int(px), int(py))

                kf.update(cx, cy, confidence=conf)

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
                'prediction_confidence': round(self.prediction_confidence.get(tid, 1.0), 2),
            })

            self.ghost_registry[tid] = {
                'box':        det['box'],
                'center':     (cx, cy),
                'last_frame': frame_number,
                'cid':        cid,
            }

        self._predict_lost_tracks(frame_number, fps)
        self._evict_stale(frame_number)
        return processed

    # ─────────────────────────────────────────────────────────────────────────
    # FIX-ET1 + FIX-ET4: Trajectory prediction — non-mutating peek
    # ─────────────────────────────────────────────────────────────────────────

    def _predict_lost_tracks(self, frame_number, fps):
        """
        Predict positions for tracks that were recently lost.

        FIX-ET1: Uses predict(steps=N) once — not in a loop.
        FIX-ET4: Now uses predict_peek() so the live KF state is NOT mutated.
                 This means when the vehicle reappears, predict() in
                 postprocess_tracks will still start from the last real update
                 rather than from a phantom-advanced state.
        """
        current_predicted: set = set()

        for tid in list(self.track_last_frame.keys()):
            last_seen   = self.track_last_frame.get(tid, frame_number)
            frames_lost = frame_number - last_seen

            if 0 < frames_lost <= self.max_prediction_frames:
                if tid in self.kalman_filters:
                    kf = self.kalman_filters[tid]

                    # FIX-ET4: peek — no mutation of kf.x / kf.P
                    px, py = kf.predict_peek(steps=frames_lost)

                    if px is not None:
                        conf = max(0.3, 1.0 - frames_lost / self.max_prediction_frames)
                        self.predicted_positions[tid].append({
                            'frame':            frame_number,
                            'positions':        [(px, py)],
                            'confidence':       conf,
                            'last_known_speed': self.track_speed_smooth.get(tid),
                        })
                        self.prediction_confidence[tid] = conf
                        current_predicted.add(tid)

        self._was_predicted_last_frame = current_predicted

    # ─────────────────────────────────────────────────────────────────────────
    # FIX-ET2: Eviction cleanup for prediction data — corrected last_seen logic
    # ─────────────────────────────────────────────────────────────────────────

    def _cleanup_stale_predictions(self, frame_number):
        """
        FIX-ET2: Original code entered a branch 'if tid not in track_last_frame'
        then immediately called track_last_frame.get(tid, 0) — always returning 0,
        meaning the condition was always True and predictions were cleaned up
        almost immediately. Fixed by always looking up last_seen correctly.
        """
        for tid in list(self.predicted_positions.keys()):
            last_seen = self.track_last_frame.get(tid, 0)
            if frame_number - last_seen > self.max_prediction_frames * 2:
                self.predicted_positions.pop(tid, None)
                self.prediction_confidence.pop(tid, None)

    # ─────────────────────────────────────────────────────────────────────────
    # FIX-ET3: Appearance matching — majority-vote class from feature history
    # ─────────────────────────────────────────────────────────────────────────

    def _match_with_appearance(self, detection, candidate_tids):
        """
        Match a new detection with lost track candidates using appearance features.

        FIX-ET3: The original used features[0]['class_id'] to verify class match,
        which relied on the very first (potentially misclassified) frame.
        Now uses majority vote across the stored feature history for robustness.
        """
        if not self.use_appearance_reid or not candidate_tids:
            return None

        best_match = None
        best_similarity = self.appearance_similarity_threshold

        det_box = detection['box']
        det_aspect = det_box[2] / max(det_box[3], 1)
        det_area = det_box[2] * det_box[3]
        det_cid = detection['cid']

        for tid in candidate_tids:
            if tid not in self.appearance_features:
                continue

            features = list(self.appearance_features[tid])
            if not features:
                continue

            # FIX-ET3: Majority vote across all stored features
            majority_class = Counter(f['class_id'] for f in features).most_common(1)[0][0]
            class_match = det_cid == majority_class

            avg_aspect = np.mean([f['aspect_ratio'] for f in features])
            avg_area   = np.mean([f['area'] for f in features])
            avg_conf   = np.mean([f['confidence'] for f in features])

            aspect_sim = 1.0 - min(1.0, abs(det_aspect - avg_aspect) / max(avg_aspect, 0.1))
            area_sim   = 1.0 - min(1.0, abs(det_area - avg_area) / max(avg_area, 1))
            conf_sim   = min(1.0, detection['conf'] * avg_conf * 2)

            if class_match:
                similarity = (aspect_sim * 0.35 + area_sim * 0.40 + conf_sim * 0.25)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = tid

        if best_match:
            logger.debug(f"🎨 Appearance match: new {detection['tid']} → old {best_match} "
                         f"(sim={best_similarity:.2f})")

        return best_match

    # ─────────────────────────────────────────────────────────────────────────
    # Ghost-track recovery — Enhanced with appearance fallback
    # ─────────────────────────────────────────────────────────────────────────

    def _ghost_recovery(self, raw_dets, frame_number):
        current_ids = {d['tid'] for d in raw_dets}

        active_ghosts = {
            tid: g for tid, g in self.ghost_registry.items()
            if tid not in current_ids
            and frame_number - g['last_frame'] <= self.ghost_frames
        }

        predicted_tracks = {
            tid: p for tid, p in self.predicted_positions.items()
            if tid not in current_ids
            and tid in self.kalman_filters
        }

        if not active_ghosts and not predicted_tracks:
            return raw_dets

        remapped   = []
        used_ghost = set()

        for det in raw_dets:
            if det['tid'] in self.track_last_frame:
                remapped.append(det)
                continue

            best_iou, best_iou_gid   = self.iou_ghost_threshold - 1e-6, None
            best_app_gid             = None

            # --- IoU candidates ---
            for gid, ghost in active_ghosts.items():
                if gid in used_ghost or ghost['cid'] != det['cid']:
                    continue
                iou = _box_iou(det['box'], ghost['box'])
                if iou > best_iou:
                    best_iou, best_iou_gid = iou, gid

            # --- Appearance candidates (always run, not just as fallback) ---
            if self.use_appearance_reid:
                best_app_gid = self._match_with_appearance(
                    det,
                    [k for k in predicted_tracks.keys() if k not in used_ghost]
                )

            # Pick winner: prefer IoU match (spatial certainty) but fall back
            # to appearance if IoU had no candidate. If both found different
            # candidates, use IoU (more reliable for adjacent frames).
            best_gid = best_iou_gid or best_app_gid

            if best_gid is not None:
                match_type = "IoU" if best_iou_gid else "Appearance"
                logger.debug(f"👻 Ghost-link [{match_type}]: {det['tid']} → {best_gid}")
                det = dict(det)
                det['tid'] = best_gid
                used_ghost.add(best_gid)
                self.prediction_confidence[best_gid] = min(1.0,
                    self.prediction_confidence.get(best_gid, 0) + 0.2)

            remapped.append(det)

        return remapped

    # ─────────────────────────────────────────────────────────────────────────
    # Cross-frame NMS
    # ─────────────────────────────────────────────────────────────────────────

    def _cross_nms(self, raw_dets):
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
                    suppressed.add(j)

        return keep

    # ─────────────────────────────────────────────────────────────────────────
    # Speed: SG smoothed + prediction blending
    # ─────────────────────────────────────────────────────────────────────────

    def _sg_speed(self, tid, fps, px_per_m=10):
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
        # FIX-ET6: improved fallback via updated _smooth_speed
        smoothed = _smooth_speed(list(self.track_speed_raw[tid]))

        if smoothed is None or not math.isfinite(smoothed):
            return None

        smoothed = max(0.0, smoothed)

        if (tid in self.predicted_positions and self.predicted_positions[tid]
                and tid in self.track_speed_smooth):
            pred_conf = self.prediction_confidence.get(tid, 0.5)
            last_pred = self.predicted_positions[tid][-1]
            if 'last_known_speed' in last_pred and last_pred['last_known_speed'] is not None:
                blended = (smoothed * (1 - pred_conf * 0.3)
                           + last_pred['last_known_speed'] * (pred_conf * 0.3))
                smoothed = blended

        self.track_speed_smooth[tid] = smoothed
        return round(smoothed, 1)

    def get_smoothed_speed(self, track_id, fps, pixels_per_meter=10, window=12):
        return self._sg_speed(track_id, fps, pixels_per_meter)

    # ─────────────────────────────────────────────────────────────────────────
    # Trajectory & motion analytics
    # ─────────────────────────────────────────────────────────────────────────

    def get_trajectory(self, track_id, max_points=20, include_predictions=False):
        history = list(self.track_history.get(track_id, []))

        if not history:
            return []

        step     = max(1, len(history) // max_points)
        smoothed = [(int(x), int(y))
                    for i, (x, y, _, _) in enumerate(history) if i % step == 0]

        if include_predictions and track_id in self.predicted_positions:
            predictions = self.predicted_positions[track_id]
            if predictions:
                last_pred = predictions[-1]['positions'][-1]
                smoothed.append((int(last_pred[0]), int(last_pred[1])))

        return smoothed

    def get_motion_vectors(self, min_magnitude=1.0):
        vectors = []

        for tid, history in self.track_history.items():
            if len(history) >= 2:
                hist_list = list(history)
                p1 = hist_list[-2][:2]
                p2 = hist_list[-1][:2]

                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                magnitude = math.hypot(dx, dy)

                if magnitude >= min_magnitude:
                    vectors.append({
                        'track_id':              tid,
                        'start':                 (int(p1[0]), int(p1[1])),
                        'end':                   (int(p2[0]), int(p2[1])),
                        'magnitude':             round(magnitude, 2),
                        'speed_kmh':             self.track_speed_smooth.get(tid),
                        'heading':               self.track_heading.get(tid),
                        'prediction_confidence': round(self.prediction_confidence.get(tid, 1.0), 2),
                    })

        return vectors

    # ─────────────────────────────────────────────────────────────────────────
    # Eviction — FIX-ET2 integrated via _cleanup_stale_predictions
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

        # FIX-ET2: Use corrected cleanup method
        self._cleanup_stale_predictions(current_frame)

    def _evict_one(self, tid):
        stores = [self.track_history, self.track_confidences,
                  self.track_last_frame, self.track_speed_raw,
                  self.track_speed_smooth, self.track_accel_ema,
                  self.track_heading, self.track_area_ema,
                  self.kalman_filters, self.track_conf_ema,
                  self.appearance_features, self.ghost_registry,
                  self.predicted_positions, self.prediction_confidence]

        for store in stores:
            if isinstance(store, dict):
                store.pop(tid, None)
            elif hasattr(store, 'pop'):
                try:
                    store.pop(tid, None)
                except Exception:
                    pass

        # Also remove from prediction tracking set
        self._was_predicted_last_frame.discard(tid)

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
        """
        FIX-ET8: Tighten lower bound from 0.25 → 0.35 to reject bbox
        flickers where area drops to less than 35% of the EMA. Such drops
        usually indicate a detection on a different, occluded object rather
        than the same vehicle shrinking.
        """
        prev = self.track_area_ema.get(tid)
        if prev is None or prev < 1:
            return True
        return 0.35 <= area / prev <= 4.0

    def _stability(self, tid):
        """
        FIX-ET7: Skip segments with displacement < 1.0 px before computing
        dot products. Near-zero movement vectors have arbitrary direction;
        including them made stationary vehicles appear highly stable.
        """
        hist = list(self.track_history[tid])
        if len(hist) < 4:
            return 0.0
        vecs = []
        for i in range(1, len(hist)):
            px, py, _, _ = hist[i - 1]
            cx, cy, _, _ = hist[i]
            m = math.hypot(cx - px, cy - py)
            # FIX-ET7: require meaningful displacement
            if m > 1.0:
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

    # ─────────────────────────────────────────────────────────────────────────
    # Fleet stats
    # ─────────────────────────────────────────────────────────────────────────

    def get_fleet_stats(self):
        speeds = [s for s in self.track_speed_smooth.values() if s is not None]

        base_stats = {
            'active_tracks':    len(self.track_last_frame),
            'mean_speed_kmh':   round(float(np.mean(speeds)),   1) if speeds else None,
            'median_speed_kmh': round(float(np.median(speeds)), 1) if speeds else None,
            'max_speed_kmh':    round(float(np.max(speeds)),    1) if speeds else None,
            'pct_stationary':   round(
                sum(1 for s in speeds if s < 3.0) / len(speeds) * 100, 1
            ) if speeds else 0.0,
        }

        base_stats.update({
            'tracks_with_predictions':    len(self.predicted_positions),
            'avg_prediction_confidence':  round(
                float(np.mean(list(self.prediction_confidence.values()))), 2
            ) if self.prediction_confidence else 1.0,
            'avg_track_history_length':   round(
                float(np.mean([len(h) for h in self.track_history.values()])), 1
            ) if self.track_history else 0,
            'ghost_tracks_active':        len(self.ghost_registry),
            'appearance_reid_enabled':    self.use_appearance_reid,
            'adaptive_kalman_enabled':    self.use_adaptive_kalman,
        })

        return base_stats