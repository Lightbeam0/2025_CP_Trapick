# ml/directional_detectors/base_directional.py
"""
BaseDirectionalDetector — v4.0
────────────────────────────────────────────────────────────────────────────
DETECTION improvements
  D1. Warm-up zone guard — a vehicle must travel at least WARMUP_PX pixels
      from its first-seen position before counting is armed.  Prevents
      vehicles that spawn at or near the line (parked, partly visible)
      from triggering an immediate false count.

  D2. Per-class minimum track length — motorcycles and tricycles need
      fewer confirmed frames than cars/trucks before counting is enabled,
      matching their real-world size and transit speed.

  D3. Direction re-evaluation — valid_direction is re-checked every
      DIRECTION_RECHECK_INTERVAL frames instead of only once on entry.
      A vehicle that enters at a bad angle and then corrects course can
      still be counted once its trajectory aligns.

  D4. Kalman-smoothed centers used everywhere — history in vehicle_status
      is now built from track['center'] (the Kalman output from the
      tracker), not the raw YOLO bounding-box midpoint.  Direction checks
      and crossing checks therefore operate on noise-free positions.

  D5. Track eviction callback — EnhancedByteTrackWrapper calls back into
      this class when a stale track is removed, evicting the matching
      entry from vehicle_status.  Fixes the unbounded memory growth
      identified in the code review.

COUNTING improvements
  C1. Re-arm after crossing — status['crossed'] is reset to False after
      RE_ARM_FRAMES frames so a reversing vehicle (truck backing up,
      motorcycle doing a U-turn) can be counted again on its return pass.

  C2. Multi-point path crossing — the line-cross check now scans every
      consecutive pair in the last LINE_CHECK_WINDOW positions rather
      than only the most-recent two.  This catches fast vehicles whose
      per-frame displacement is large enough to skip over the line
      between two consecutive raw positions.

  C3. Side-of-line guard — on first detection the signed side of the
      counting line is recorded as the vehicle's approach side.  A count
      only fires when the vehicle transitions from that approach side to
      the far side, ruling out vehicles that first appear on the wrong
      side of the line.

SMOOTHING improvements
  S1. Recent-window direction check — the dot-product direction check
      uses only the RECENT_WINDOW most-recent positions, so old
      approach-angle history from when the vehicle entered the frame
      does not bias the result.

  S2. Unified history — the same Kalman-smoothed centers used for
      direction checks are used for crossing checks, so both subsystems
      agree on the vehicle's trajectory.

  S3. Throttled scene detection — cv2.cvtColor + np.mean is called at
      most once every SCENE_CHECK_INTERVAL frames and the result is
      cached, instead of the previous every-300-frame integer-modulo
      check that still ran the computation on the modulo frame.

All v3.1 fixes are retained (batch flush, valid_direction source-of-truth,
dot-product direction check, ring-buffer frame_data).
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
import time
import os
from pathlib import Path
from ultralytics import YOLO
import torch
import math

from ..enhanced_tracker import EnhancedByteTrackWrapper
from ..base_detector import BaseDetector
from ..congestion_module import CongestionModule

_BYTETRACK_PATH = str(Path(__file__).parent.parent / 'bytetrack.yaml')
_DEFAULT_MODEL  = str(
    Path(__file__).parent.parent.parent
    / 'runs' / 'detect' / 'custom_model' / 'weights' / 'best.pt'
)


# ─── Signed side-of-line ─────────────────────────────────────────────────────

def _side_of_line(px, py, lx1, ly1, lx2, ly2):
    """
    Return the sign of the 2-D cross product (line_vec × point_offset).
    Positive = left side, negative = right side, 0 = on the line.
    Used for the C3 approach-side guard.
    """
    return (lx2 - lx1) * (py - ly1) - (ly2 - ly1) * (px - lx1)


# ─────────────────────────────────────────────────────────────────────────────

class BaseDirectionalDetector(BaseDetector):

    EXCLUDED_CLASS_IDS = {0, 4}     # VehicleCrash(0), person(4)

    # ── D2: per-class minimum confirmed track frames before counting ──────────
    MIN_FRAMES_BY_CLASS = {
        'car':        6,
        'jeep':       6,
        'truck':      7,
        'motorcycle': 4,
        'tricycle':   4,
    }
    MIN_FRAMES_DEFAULT  = 5

    WRITE_EVERY_N_FRAMES  = 3
    CROSS_COOLDOWN_FRAMES = 18

    # C2: consecutive-pair window for the line-crossing path scan
    LINE_CHECK_WINDOW     = 4

    # C1: frames after a crossing before the track can count again
    RE_ARM_FRAMES         = 45      # ~1.5 s at 30 fps

    # D1: min pixel displacement from spawn before counting is armed
    WARMUP_PX             = 20

    # S1: tail length used for the direction dot-product
    RECENT_WINDOW         = 12

    # D3: how often to re-run the direction check (frames)
    DIRECTION_RECHECK_INTERVAL = 8

    # S3: minimum frames between scene-brightness checks
    SCENE_CHECK_INTERVAL  = 300

    # Batch size for GPU inference inside analyze_video
    BATCH_SIZE = 4

    # ─────────────────────────────────────────────────────────────────────────
    # Init
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self, direction_name, model_path=None):
        resolved = model_path or _DEFAULT_MODEL
        print(f"\n{'='*70}\n🚦 {direction_name.upper()} (v4.0)\n{'='*70}")
        print(f"   Model  : {resolved}")
        print(f"   Tracker: {_BYTETRACK_PATH}")

        self.model  = YOLO(resolved)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        print(f"✅ Device: {self.device.upper()}")

        # D5: wire eviction callback so vehicle_status stays bounded
        self.tracker = EnhancedByteTrackWrapper(
            eviction_callback=self._on_track_evicted
        )

        self.class_names       = {1: 'car', 2: 'jeep', 3: 'motorcycle',
                                   5: 'tricycle', 6: 'truck'}
        self.counted_classes   = list(self.class_names.values())
        self.vehicle_class_ids = list(self.class_names.keys())

        self.class_confidence_thresholds = {
            'car':        0.28,
            'jeep':       0.28,
            'motorcycle': 0.22,
            'tricycle':   0.22,
            'truck':      0.28,
        }
        self._min_conf_base = min(self.class_confidence_thresholds.values())
        self._min_conf      = self._min_conf_base

        self.colors = {
            'car':        (100, 100, 255),
            'jeep':       (255, 165,   0),
            'motorcycle': (255, 255,   0),
            'tricycle':   (  0, 255, 255),
            'truck':      (  0,   0, 255),
        }

        self.direction_name      = direction_name
        self.line_start          = None
        self.line_end            = None
        self.valid_direction     = None     # set ONLY by setup_counting_line()
        self.counting_line_setup = False

        self.use_multi_line = True
        self.counting_lines = []

        self.time_based_adaptation = True
        self.peak_hours            = [(7, 9), (17, 19)]
        self.peak_hour_multiplier  = {'confidence': 0.9, 'min_frames': 0.8}

        # S3: cached scene context
        self.scene_context = {
            'is_night':         False,
            'last_check_frame': -self.SCENE_CHECK_INTERVAL,
        }

        self.batch_size = self.BATCH_SIZE

        self.roi_enabled    = False
        self.roi_normalized = None
        self.roi_pixels     = None
        self.roi_polygon    = None
        self.roi_area       = None

        self.congestion_module = CongestionModule()
        self.reset_tracking_state()

        print(f"🎯 classes={self.vehicle_class_ids}  base_conf={self._min_conf_base}")
        print(f"📊 Multi-line: {'on' if self.use_multi_line else 'off'}")
        print(f"⚡ Batch: {self.batch_size}")
        print(f"{'='*70}\n")

    # ─────────────────────────────────────────────────────────────────────────
    # D5: eviction callback
    # ─────────────────────────────────────────────────────────────────────────

    def _on_track_evicted(self, track_id):
        """Called by EnhancedByteTrackWrapper when a stale track expires."""
        self.vehicle_status.pop(track_id, None)

    # ─────────────────────────────────────────────────────────────────────────
    # State reset
    # ─────────────────────────────────────────────────────────────────────────

    def reset_tracking_state(self):
        self.vehicle_status   = {}
        self.vehicle_counts   = defaultdict(int)
        self.counted_vehicles = set()
        self.total_count      = 0
        self.frame_count      = 0
        self.congestion_module.reset_state()
        self.count_timestamps = defaultdict(list)
        self.frame_data       = deque(maxlen=1000)

        self.results = {
            'vehicle_counts':    defaultdict(int),
            'congestion_events': [],
            'frame_data':        [],
            'roi_config': {
                'enabled':    self.roi_enabled,
                'normalized': self.roi_normalized,
                'pixels':     self.roi_pixels,
            },
        }

        self._dbg_warmup = 0

    # ─────────────────────────────────────────────────────────────────────────
    # ROI
    # ─────────────────────────────────────────────────────────────────────────

    def set_roi(self, roi_normalized):
        if not roi_normalized:
            self.roi_enabled = False
            self.roi_normalized = self.roi_pixels = self.roi_polygon = self.roi_area = None
            print("🔲 ROI disabled")
            return
        if len(roi_normalized) < 3:
            raise ValueError("ROI needs ≥3 points")
        self.roi_normalized = [
            [max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y)))]
            for x, y in roi_normalized
        ]
        self.roi_enabled = True
        self.roi_pixels  = self.roi_polygon = None
        print(f"✅ ROI: {self.roi_normalized}")

    def _setup_roi_pixels(self, w, h):
        self.roi_area = w * h
        if not self.roi_enabled or not self.roi_normalized or self.roi_pixels is not None:
            return
        self.roi_pixels  = [[int(x * w), int(y * h)] for x, y in self.roi_normalized]
        self.roi_polygon = np.array(self.roi_pixels, dtype=np.int32)
        pts, n = self.roi_pixels, len(self.roi_pixels)
        self.roi_area = abs(sum(
            pts[i][0] * pts[(i+1) % n][1] - pts[(i+1) % n][0] * pts[i][1]
            for i in range(n)
        )) * 0.5
        print(f"📐 ROI area={self.roi_area:.0f}px²")

    def _in_roi(self, x, y):
        if not self.roi_enabled or self.roi_polygon is None:
            return True
        return cv2.pointPolygonTest(self.roi_polygon, (float(x), float(y)), False) >= 0

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract interface
    # ─────────────────────────────────────────────────────────────────────────

    def setup_counting_line(self, frame_width, frame_height):
        """Return (line_start, line_end, valid_direction). Implemented by subclasses."""
        raise NotImplementedError

    def is_valid_direction(self, history, valid_direction_vector):
        return self.enhanced_is_valid_direction(history, valid_direction_vector)

    # ─────────────────────────────────────────────────────────────────────────
    # S1: Direction check over recent window only
    # ─────────────────────────────────────────────────────────────────────────

    def enhanced_is_valid_direction(self, history, valid_direction_vector,
                                    threshold=0.45, min_displacement=8):
        """
        Net-displacement dot-product direction check, applied only to the
        RECENT_WINDOW tail of the history (S1).

        Using the tail prevents old approach-angle positions (when the
        vehicle first entered the frame at a skewed angle) from biasing
        the result against legitimately-directed vehicles.
        """
        pts = list(history)
        if len(pts) < 5:
            return False

        # S1: only the recent tail
        pts = pts[-self.RECENT_WINDOW:]

        net_dx = pts[-1][0] - pts[0][0]
        net_dy = pts[-1][1] - pts[0][1]
        mag    = math.hypot(net_dx, net_dy)
        if mag < min_displacement:
            return False

        vx, vy = valid_direction_vector
        v_mag  = math.hypot(vx, vy)
        if v_mag < 1e-9:
            return False

        dot = (net_dx / mag) * (vx / v_mag) + (net_dy / mag) * (vy / v_mag)
        return dot >= threshold

    # ─────────────────────────────────────────────────────────────────────────
    # C2: Multi-point line crossing
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _segments_intersect(p1, p2, p3, p4):
        x1, y1 = p1;  x2, y2 = p2
        x3, y3 = p3;  x4, y4 = p4
        d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(d) < 1e-9:
            return False
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / d
        return 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0

    def _crossed_line(self, history_list):
        """
        C2: Test every consecutive pair in the last LINE_CHECK_WINDOW
        positions.  Returns True if any pair straddles the counting line.
        """
        window = history_list[-self.LINE_CHECK_WINDOW:]
        for i in range(len(window) - 1):
            if self._segments_intersect(
                window[i], window[i + 1],
                self.line_start, self.line_end
            ):
                return True
        return False

    def enhanced_check_line_crossing(self, prev, cur, min_displacement=1):
        """Single-pair wrapper kept for API compatibility."""
        if prev is None or cur is None:
            return False
        if math.hypot(cur[0] - prev[0], cur[1] - prev[1]) < min_displacement:
            return False
        return self._segments_intersect(prev, cur, self.line_start, self.line_end)

    # ─────────────────────────────────────────────────────────────────────────
    # Multi-line setup
    # ─────────────────────────────────────────────────────────────────────────

    def setup_multi_counting_lines(self, w, h):
        if not self.use_multi_line or not self.line_start or not self.line_end:
            return
        lines  = [(self.line_start, self.line_end)]
        dx, dy = self.line_end[0] - self.line_start[0], self.line_end[1] - self.line_start[1]
        length = math.hypot(dx, dy)
        if length > 0:
            px, py = -dy / length * 30, dx / length * 30
            for sign in (1, -1):
                s = (int(self.line_start[0] + sign * px), int(self.line_start[1] + sign * py))
                e = (int(self.line_end[0]   + sign * px), int(self.line_end[1]   + sign * py))
                lines.append((s, e))
        self.counting_lines = lines
        print(f"📏 Multi-line: {len(lines)} lines")

    # ─────────────────────────────────────────────────────────────────────────
    # S3: Throttled scene detection
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_scene_context(self, frame, frame_number):
        """Run brightness check only if SCENE_CHECK_INTERVAL has elapsed (S3)."""
        if frame_number - self.scene_context['last_check_frame'] < self.SCENE_CHECK_INTERVAL:
            return
        self.scene_context['last_check_frame'] = frame_number
        mean_brightness = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
        is_night        = mean_brightness < 80
        if is_night != self.scene_context['is_night']:
            self.scene_context['is_night'] = is_night
            self.tracker.speed_ema_alpha   = 0.35 if is_night else 0.25
            print(f"🌙 Scene: night={is_night}  brightness={mean_brightness:.0f}")

    def _get_adaptive_confidence(self):
        m = 1.0
        if self.time_based_adaptation and self._is_peak_hour():
            m *= self.peak_hour_multiplier['confidence']
        if self.scene_context['is_night']:
            m *= 0.85
        return self._min_conf_base * m

    def _is_peak_hour(self):
        h = datetime.now().hour
        return any(s <= h < e for s, e in self.peak_hours)

    # ─────────────────────────────────────────────────────────────────────────
    # D2: per-class minimum frames
    # ─────────────────────────────────────────────────────────────────────────

    def _min_frames_for(self, class_name):
        base = self.MIN_FRAMES_BY_CLASS.get(class_name, self.MIN_FRAMES_DEFAULT)
        if self.time_based_adaptation and self._is_peak_hour():
            base = max(3, int(base * self.peak_hour_multiplier['min_frames']))
        return base

    # ─────────────────────────────────────────────────────────────────────────
    # Core per-frame processing
    # ─────────────────────────────────────────────────────────────────────────

    def process_frame(self, frame, frame_number, fps, yolo_results=None):
        """
        Process one frame. Returns (current_counts, detections, congestion_info).

        yolo_results: pre-computed from the batched inference loop in
                      analyze_video, or None to trigger a fresh single-frame
                      inference call here.
        """
        # ── One-time line setup ───────────────────────────────────────────────
        if not self.counting_line_setup:
            h, w = frame.shape[:2]
            self.line_start, self.line_end, self.valid_direction = \
                self.setup_counting_line(w, h)
            self._setup_roi_pixels(w, h)
            if self.use_multi_line:
                self.setup_multi_counting_lines(w, h)
            self.counting_line_setup = True
            print(f"🔍 Line : {self.line_start} → {self.line_end}")
            print(f"🔍 Dir  : {self.valid_direction}")

        # ── S3: throttled scene check ─────────────────────────────────────────
        self._detect_scene_context(frame, frame_number)
        self._min_conf = self._get_adaptive_confidence()

        # ── YOLO inference ────────────────────────────────────────────────────
        if yolo_results is None:
            yolo_results = self.model.track(
                frame,
                persist=True,
                conf=self._min_conf,
                iou=0.38,
                agnostic_nms=True,
                classes=self.vehicle_class_ids,
                tracker=_BYTETRACK_PATH,
                verbose=False,
                device=self.device,
            )

        tracks         = self.tracker.postprocess_tracks(yolo_results, frame_number, fps)
        detections     = []
        current_counts = defaultdict(int)

        # Line endpoints used by C3 (side-of-line guard)
        lx1, ly1 = self.line_start if self.line_start else (0, 0)
        lx2, ly2 = self.line_end   if self.line_end   else (0, 0)

        for track in tracks:
            track_id   = track['track_id']
            class_id   = track.get('class_id')
            class_name = track.get('class_name')

            if class_id in self.EXCLUDED_CLASS_IDS or class_name is None:
                continue

            conf      = track.get('confidence', 0.0)
            threshold = self.class_confidence_thresholds.get(class_name, 0.28)
            if conf < threshold:
                continue

            # D4/S2: use Kalman-smoothed center for all geometry checks
            cx, cy  = track['center']
            in_roi  = self._in_roi(cx, cy)
            speed   = track.get('speed')
            heading = track.get('heading')
            t_len   = track.get('track_length', 0)

            # ── Initialise per-track status on first sight ────────────────────
            if track_id not in self.vehicle_status:
                self.vehicle_status[track_id] = {
                    'name':             class_name,
                    'crossed':          False,
                    'cross_count':      0,
                    'last_cross_frame': -self.CROSS_COOLDOWN_FRAMES,
                    'valid_direction':  False,
                    'dir_check_frame':  0,
                    # D1: spawn position for warm-up guard
                    'spawn_x':          cx,
                    'spawn_y':          cy,
                    'warmed_up':        False,
                    # C3: side of line at first detection
                    'approach_side':    _side_of_line(cx, cy, lx1, ly1, lx2, ly2),
                    # S2: smoothed-center history
                    'history':          deque(maxlen=30),
                }

            status = self.vehicle_status[track_id]

            # S2: append Kalman-smoothed center
            status['history'].append((cx, cy))

            # ── D1: warm-up guard ─────────────────────────────────────────────
            if not status['warmed_up']:
                if math.hypot(cx - status['spawn_x'],
                              cy - status['spawn_y']) >= self.WARMUP_PX:
                    status['warmed_up'] = True
                else:
                    self._dbg_warmup += 1

            # ── D3: direction re-check every N frames ─────────────────────────
            if (len(status['history']) >= 5
                    and (not status['valid_direction']
                         or frame_number - status['dir_check_frame']
                         >= self.DIRECTION_RECHECK_INTERVAL)):
                status['valid_direction'] = self.enhanced_is_valid_direction(
                    status['history'], self.valid_direction
                )
                status['dir_check_frame'] = frame_number

            # ── C1: re-arm after RE_ARM_FRAMES ───────────────────────────────
            if (status['crossed']
                    and frame_number - status['last_cross_frame'] >= self.RE_ARM_FRAMES):
                status['crossed'] = False

            # ── Crossing check ────────────────────────────────────────────────
            cooldown_ok  = frame_number - status['last_cross_frame'] >= self.CROSS_COOLDOWN_FRAMES
            min_frames   = self._min_frames_for(class_name)
            history_list = list(status['history'])

            if (status['valid_direction']
                    and not status['crossed']
                    and cooldown_ok
                    and status['warmed_up']
                    and t_len >= min_frames
                    and len(history_list) >= 2):

                # C2: multi-point path test
                if self._crossed_line(history_list):
                    # C3: side-of-line guard
                    curr_side   = _side_of_line(cx, cy, lx1, ly1, lx2, ly2)
                    approach    = status['approach_side']
                    crossed_ok  = (
                        approach == 0               # started on the line
                        or curr_side == 0           # landed exactly on the line
                        or (approach > 0) != (curr_side > 0)  # genuine cross
                    )

                    if crossed_ok:
                        status['crossed']          = True
                        status['cross_count']      += 1
                        status['last_cross_frame'] = frame_number
                        self.total_count           += 1
                        self.vehicle_counts[class_name] += 1
                        self.counted_vehicles.add(track_id)
                        self.count_timestamps[class_name].append(frame_number / fps)
                        print(f"  ✓ #{self.total_count:03d} {class_name} "
                              f"id={track_id} t={frame_number/fps:.1f}s "
                              f"spd={speed}")

            det = {
                'track_id':        track_id,
                'class_name':      class_name,
                'center':          (cx, cy),
                'bbox':            track['box'],
                'confidence':      conf,
                'color':           self.colors[class_name],
                'counted':         status['crossed'],
                'valid_direction': status['valid_direction'],
                'warmed_up':       status['warmed_up'],
                'in_roi':          in_roi,
                'speed':           speed,
                'heading':         heading,
            }
            detections.append(det)
            current_counts[class_name] += 1

        # ── Congestion ────────────────────────────────────────────────────────
        cong_src = ([d for d in detections if d['in_roi']]
                    if self.roi_enabled else detections)
        cong = self.congestion_module.detect_congestion(cong_src, fps)
        cong['total_vehicles_full_frame'] = len(detections)
        cong['total_vehicles_in_roi']     = sum(1 for d in detections if d.get('in_roi'))
        cong['roi_enabled']               = self.roi_enabled

        visible_speeds = [d['speed'] for d in detections if d['speed'] is not None]
        speed_p50 = round(float(np.median(visible_speeds)), 1) if visible_speeds else None
        speed_p85 = (round(float(np.percentile(visible_speeds, 85)), 1)
                     if len(visible_speeds) >= 4 else None)

        self.frame_data.append({
            'frame_number':             frame_number,
            'timestamp':                round(frame_number / fps, 3) if fps > 0 else 0,
            'vehicle_count_full_frame': sum(current_counts.values()),
            'vehicle_count_in_roi':     sum(1 for d in detections if d.get('in_roi')),
            'vehicle_breakdown':        dict(current_counts),
            'total_counted':            self.total_count,
            'congestion_level':         cong.get('level', 'none'),
            'congestion_score':         cong.get('congestion_score', 0),
            'onset_rate':               cong.get('onset_rate', 0.0),
            'stationary_vehicles':      cong.get('stationary_vehicles', 0),
            'speed_p50_kmh':            speed_p50,
            'speed_p85_kmh':            speed_p85,
            'roi_enabled':              self.roi_enabled,
        })
        self.frame_count = frame_number

        return current_counts, detections, cong

    # ─────────────────────────────────────────────────────────────────────────
    # Visualisation
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _speed_color(speed):
        if speed is None: return (180, 180, 180)
        if speed >= 30:   return (0, 220, 0)
        if speed >= 15:   return (0, 200, 200)
        if speed >= 5:    return (0, 140, 255)
        return (0, 0, 220)

    def draw_detections(self, frame, detections, congestion_info, fps):
        h, w = frame.shape[:2]

        # ROI tint
        if self.roi_enabled and self.roi_polygon is not None:
            ov = frame.copy()
            cv2.fillPoly(ov, [self.roi_polygon], (0, 255, 255))
            cv2.addWeighted(ov, 0.10, frame, 0.90, 0, frame)
            cv2.polylines(frame, [self.roi_polygon], True, (0, 255, 255), 2)

        # Counting lines
        if self.use_multi_line and self.counting_lines:
            for i, (s, e) in enumerate(self.counting_lines):
                cv2.line(frame, s, e, (0, 200, 200) if i == 0 else (80, 80, 80),
                         2 if i == 0 else 1)
        elif self.line_start and self.line_end:
            cv2.line(frame, self.line_start, self.line_end, (0, 200, 200), 2)

        # Title / count
        cv2.putText(frame, f"{self.direction_name.upper()} v4",
                    (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0, 255, 255), 2)
        cv2.putText(frame, f"TOTAL: {self.total_count}",
                    (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 1.10, (0, 255, 0), 3)
        if self.scene_context['is_night']:
            cv2.putText(frame, "NIGHT", (w - 120, 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

        # Congestion-coloured primary line
        lvl      = congestion_info.get('level', 'none')
        line_col = {'none': (0,220,0), 'light': (0,255,220),
                    'moderate': (0,165,255), 'heavy': (0,0,255),
                    'severe': (180,0,180)}.get(lvl, (0,200,0))
        if self.line_start and self.line_end:
            cv2.line(frame, self.line_start, self.line_end, line_col, 3)

        # HUD panel
        scr   = congestion_info.get('congestion_score', 0)
        onset = congestion_info.get('onset_rate', 0.0)
        trend = "▲" if onset > 1 else ("▼" if onset < -1 else "─")
        hx    = w - 290
        cv2.rectangle(frame, (hx, 15), (w - 10, 220), (0, 0, 0), -1)
        cv2.rectangle(frame, (hx, 15), (w - 10, 220), line_col, 2)
        yo = [40]

        def ht(txt, col=(240, 240, 240), sc=0.52):
            cv2.putText(frame, txt, (hx + 8, yo[0]),
                        cv2.FONT_HERSHEY_SIMPLEX, sc, col, 1)
            yo[0] += 24

        ht(f"CONG: {lvl.upper()} {trend}", line_col, 0.58)
        ht(f"Score: {scr}/100  rate:{onset:+.1f}")
        ht(f"Vehicles: {congestion_info.get('total_vehicles_full_frame', 0)}")
        if self.roi_enabled:
            ht(f"In ROI: {congestion_info.get('total_vehicles_in_roi', 0)}", (0,255,255))
        ht(f"Static: {congestion_info.get('stationary_vehicles', 0)}")
        ht(f"Conf: {self._min_conf:.2f} (adaptive)", (200, 200, 100))

        # Per-vehicle bounding boxes
        for det in detections:
            x, y, wb, hb = det['bbox']
            speed = det.get('speed')
            if det['counted']:
                bc, th = (0, 255, 0), 3
            elif det['valid_direction'] and det.get('warmed_up', True):
                bc, th = self._speed_color(speed), 2
            elif not det.get('warmed_up', True):
                bc, th = (255, 200, 0), 1     # warming up → amber
            else:
                bc, th = (80, 80, 80), 1

            cv2.rectangle(frame, (x, y), (x + wb, y + hb), bc, th)
            lbl = det['class_name'][:3].upper()
            if det['counted']:                   lbl += "✓"
            elif not det['valid_direction']:     lbl += "?"
            elif not det.get('warmed_up', True): lbl += "~"
            if speed is not None:                lbl += f" {speed:.0f}k"
            if det.get('heading'):               lbl += f" {det['heading']}"

            (tw, th2), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            cv2.rectangle(frame, (x, y - th2 - 5), (x + tw + 4, y), bc, -1)
            cv2.putText(frame, lbl, (x + 2, y - 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1)

        return frame

    # ─────────────────────────────────────────────────────────────────────────
    # Main pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def analyze_video(self, video_path, progress_callback=None, save_output=True,
                      roi_normalized=None, **kwargs):
        print(f"\n{'='*70}\n🎬 {self.direction_name.upper()} v4\n{'='*70}")
        print(f"📹 {video_path}")

        if roi_normalized is not None:
            self.set_roi(roi_normalized)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"Cannot open: {video_path}")

        fps          = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"📊 {width}×{height}  {fps:.1f}fps  {total_frames}f")

        output_path = out = None
        writer_fps  = max(1.0, fps / self.WRITE_EVERY_N_FRAMES)

        if save_output:
            os.makedirs('media/processed_videos', exist_ok=True)
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            sfx  = "_roi" if self.roi_enabled else ""
            safe = self.direction_name.replace('→', '_').replace(' ', '_')
            output_path = os.path.join(
                'media/processed_videos', f"{safe}_{ts}{sfx}.mp4")
            out = cv2.VideoWriter(output_path,
                                  cv2.VideoWriter_fourcc(*'mp4v'),
                                  writer_fps, (width, height))
            print(f"💾 Output: {output_path}")

        self.reset_tracking_state()
        frame_number = 0
        start_time   = time.time()

        batch_frames  = []
        batch_indices = []

        def _flush_batch():
            if not batch_frames:
                return
            batch_results = self.model.track(
                batch_frames,
                persist=True,
                conf=self._min_conf,
                iou=0.38,
                agnostic_nms=True,
                classes=self.vehicle_class_ids,
                tracker=_BYTETRACK_PATH,
                verbose=False,
                device=self.device,
            )
            for frm, f_num, result in zip(batch_frames, batch_indices, batch_results):
                counts, dets, cong = self.process_frame(
                    frm, f_num, fps, yolo_results=[result])
                if out is not None and f_num % self.WRITE_EVERY_N_FRAMES == 0:
                    out.write(self.draw_detections(frm.copy(), dets, cong, fps))
                if progress_callback and f_num % 30 == 0:
                    pct = f_num / max(total_frames, 1)
                    progress_callback(
                        min(88, 15 + int(pct * 73)),
                        total_frames,
                        f"Processing {f_num}/{total_frames}")
            batch_frames.clear()
            batch_indices.clear()

        while True:
            ret, frame = cap.read()
            if not ret:
                _flush_batch()
                break
            batch_frames.append(frame)
            batch_indices.append(frame_number)
            frame_number += 1
            if len(batch_frames) >= self.batch_size:
                _flush_batch()

        cap.release()
        if out:
            out.release()

        pt = time.time() - start_time
        print(f"\n✅ Done {pt:.1f}s  "
              f"{frame_number / max(pt, 1):.1f}fps  "
              f"counted={self.total_count}  "
              f"warmup_skips={self._dbg_warmup}")

        report = self.generate_report(frame_number, pt, fps)
        if output_path:
            report['output_video_path'] = output_path
        return report

    # ─────────────────────────────────────────────────────────────────────────
    # Report
    # ─────────────────────────────────────────────────────────────────────────

    def generate_report(self, total_frames, proc_time, fps):
        duration     = total_frames / fps if fps > 0 else 0
        vpm          = (self.total_count / duration) * 60 if duration > 0 else 0
        cong_summary = self.congestion_module.get_congestion_summary()

        frame_data_list = list(self.frame_data)
        all_p50         = [f['speed_p50_kmh'] for f in frame_data_list
                           if f.get('speed_p50_kmh')]
        avg_speed_p50   = round(float(np.mean(all_p50)), 1) if all_p50 else None

        return {
            'metadata': {
                'direction':               self.direction_name,
                'version':                 'v4.0',
                'duration_seconds':        round(duration, 1),
                'processing_time_seconds': round(proc_time, 1),
                'frames_processed':        total_frames,
                'fps':                     round(fps, 2),
                'model':                   'Custom Trained YOLOv8',
                'congestion_module':       'v4.0',
                'features': [
                    'D1_warmup_zone_guard',
                    'D2_per_class_min_frames',
                    'D3_direction_recheck',
                    'D4_kalman_smoothed_history',
                    'D5_eviction_callback',
                    'C1_rearm_after_crossing',
                    'C2_multi_point_crossing',
                    'C3_side_of_line_guard',
                    'S1_recent_window_direction',
                    'S2_unified_history',
                    'S3_throttled_scene_detect',
                    'ghost_recovery',
                    'cross_frame_nms',
                    'savitzky_golay_speed',
                    'multi_line',
                    'adaptive_conf',
                    'batch_inference',
                ],
            },
            'counting_results': {
                'total_vehicles':      self.total_count,
                'vehicle_breakdown':   dict(self.vehicle_counts),
                'vehicles_per_minute': round(vpm, 1),
            },
            'speed_results': {
                'avg_speed_p50_kmh': avg_speed_p50,
            },
            'congestion_results': {
                'total_events':           cong_summary['total_events'],
                'final_congestion_level': cong_summary['current_level'],
            },
            'raw_data': {
                'frame_data':       frame_data_list,
                'count_timestamps': {k: v[-2000:]
                                     for k, v in self.count_timestamps.items()},
            },
        }