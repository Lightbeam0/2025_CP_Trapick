# ml/directional_detectors/base_directional.py
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
import logging

logger = logging.getLogger(__name__)

from ..enhanced_tracker import EnhancedByteTrackWrapper
from ..base_detector import BaseDetector
from ..congestion_module import CongestionModule

_BYTETRACK_PATH = str(Path(__file__).parent.parent / 'bytetrack.yaml')
_DEFAULT_MODEL  = str(
    Path(__file__).parent.parent.parent
    / 'runs' / 'detect' / 'custom_model' / 'weights' / 'best.pt'
)


def _side_of_line(px, py, lx1, ly1, lx2, ly2):
    """Cross-product sign of point vs directed line (positive = left side)."""
    return (lx2 - lx1) * (py - ly1) - (ly2 - ly1) * (px - lx1)


def _sign(v):
    if v > 0:  return  1
    if v < 0:  return -1
    return 0


def _distance_to_segment(px, py, lx1, ly1, lx2, ly2):
    """Perpendicular distance from (px,py) to segment (lx1,ly1)-(lx2,ly2)."""
    dx, dy   = lx2 - lx1, ly2 - ly1
    seg_len2 = dx * dx + dy * dy
    if seg_len2 < 1e-9:
        return math.hypot(px - lx1, py - ly1)
    t = max(0.0, min(1.0, ((px - lx1) * dx + (py - ly1) * dy) / seg_len2))
    return math.hypot(px - (lx1 + t * dx), py - (ly1 + t * dy))


class BaseDirectionalDetector(BaseDetector):

    EXCLUDED_CLASS_IDS = {0, 4}  # VehicleCrash, person

    # ── Counting parameters ────────────────────────────────────────────────

    MIN_FRAMES_BY_CLASS = {
        'car': 3, 'jeep': 3, 'truck': 3,
        'motorcycle': 2, 'tricycle': 2,
    }
    MIN_FRAMES_DEFAULT = 3

    MIN_APPROACH_FRAMES_BY_CLASS = {
        'car': 4, 'jeep': 4, 'truck': 4,
        'motorcycle': 2, 'tricycle': 2,
    }
    MIN_APPROACH_FRAMES_DEFAULT = 4

    # Direction memory ring size.
    DIRECTION_MEMORY_FRAMES = 10

    # Minimum pixel displacement from spawn before counting is possible.
    WARMUP_PX = 2

    # Frames to lock out re-counting after a successful count.
    POST_COUNT_LOCKOUT_FRAMES = 45

    # Direction dot-product threshold (cosine similarity).
    DIRECTION_THRESHOLD = 0.15

    # Dead-zone half-width around the counting line for hysteretic side
    # assignment. Prevents false counts from slow vehicles on the line.
    LINE_HYSTERESIS_PX = 8

    SCENE_CHECK_INTERVAL  = 30
    WRITE_EVERY_N_FRAMES  = 3

    FEATURE_FLAGS_DEFAULT = {
        'lane_detection':            False,
        'turning_movement':          False,
        'stopped_vehicle_detection': False,
        'night_enhancement':         False,
        'enhanced_congestion':       False,
        'trajectory_prediction':     False,
        'class_confidence_tracking': False,
    }

    # ──────────────────────────────────────────────────────────────────────────
    # Constructor
    # ──────────────────────────────────────────────────────────────────────────

    def __init__(self, direction_name, model_path=None):
        resolved = model_path or _DEFAULT_MODEL
        print(f"\n{'='*70}")
        print(f"🚦 {direction_name.upper()} (v5.3 - Count All Crossings, Any Color)")
        print(f"{'='*70}")
        print(f"   Model  : {resolved}")
        print(f"   Device : {'CUDA' if torch.cuda.is_available() else 'CPU'}")

        self.model  = YOLO(resolved)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)

        self.tracker = EnhancedByteTrackWrapper(
            eviction_callback=self._on_track_evicted
        )

        self.class_names = {
            1: 'car', 2: 'motorcycle', 3: 'tricycle',
            5: 'jeep', 6: 'truck',
        }
        self.counted_classes   = list(self.class_names.values())
        self.vehicle_class_ids = list(self.class_names.keys())

        self.class_confidence_thresholds = {
            'car': 0.20, 'motorcycle': 0.18, 'tricycle': 0.18,
            'jeep': 0.20, 'truck': 0.20,
        }
        self._min_conf_base = min(self.class_confidence_thresholds.values())
        self._min_conf      = self._min_conf_base

        self.colors = {
            'car':        (100, 100, 255),
            'motorcycle': (255, 255,   0),
            'tricycle':   (  0, 255, 255),
            'jeep':       (255, 165,   0),
            'truck':      (  0,   0, 255),
        }

        self.direction_name      = direction_name
        self.line_start          = None
        self.line_end            = None
        self.valid_direction     = None
        self.counting_line_setup = False

        self.time_based_adaptation = True
        self.peak_hours            = [(7, 9), (17, 19)]
        self.peak_hour_multiplier  = {'confidence': 0.9, 'min_frames': 0.8}

        self.scene_context = {
            'is_night':         False,
            'brightness':       100,
            'last_check_frame': -self.SCENE_CHECK_INTERVAL,
        }

        self.roi_enabled    = False
        self.roi_normalized = None
        self.roi_pixels     = None
        self.roi_polygon    = None
        self.roi_area       = None

        self.congestion_module = CongestionModule()
        self.feature_flags     = dict(self.FEATURE_FLAGS_DEFAULT)

        # BaseDetector-compatible attributes
        self.current_congestion   = None
        self.congestion_events    = []
        self.track_history        = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status       = {}
        self.vehicle_counts       = defaultdict(int)
        self.counted_vehicles     = set()
        self.total_count          = 0
        self.frame_count          = 0
        self.processing_time      = 0
        self.fps                  = 30
        self.frame_data           = deque(maxlen=1000)
        self.pass_stats           = {
            'avg_density': 0.0, 'peak_density': 0.0,
            'total_frames_sampled': 0,
        }
        self.stabilizer_enabled   = False
        self.multi_pass_enabled   = False
        self.prev_gray            = None
        self.feature_detector     = cv2.ORB_create(nfeatures=1000)
        self.bf_matcher           = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.speed_data           = defaultdict(list)
        self.trajectory_data      = defaultdict(list)
        self.detection_confidence = defaultdict(list)
        self.count_timestamps     = defaultdict(list)

        self.results = {
            'metadata': {}, 'counting_results': {},
            'congestion_results': {}, 'raw_data': {},
        }

        print(f"🎯 Classes       : {self.vehicle_class_ids}")
        print(f"📏 Warmup        : {self.WARMUP_PX}px")
        print(f"📏 Lockout       : {self.POST_COUNT_LOCKOUT_FRAMES} frames")
        print(f"⚠️  MODE          : COUNT ALL CROSSINGS (Any Bounding Box Color)")
        print(f"{'='*70}\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Feature flags
    # ──────────────────────────────────────────────────────────────────────────

    def configure_features(self, **kwargs):
        for feature, enabled in kwargs.items():
            if feature in self.feature_flags:
                self.feature_flags[feature] = bool(enabled)
        return dict(self.feature_flags)

    def is_feature_enabled(self, feature_name):
        return self.feature_flags.get(feature_name, False)

    # ──────────────────────────────────────────────────────────────────────────
    # Track eviction / state reset
    # ──────────────────────────────────────────────────────────────────────────

    def _on_track_evicted(self, track_id):
        """Called by the tracker when a track ID is permanently retired."""
        self.vehicle_status.pop(track_id, None)
        # FIX: Do NOT remove from counted_vehicles on eviction.
        # The set is intentionally kept to prevent the same physical vehicle
        # from being double-counted if the tracker briefly re-assigns the same ID.
        # It is cleared only on reset_tracking_state().

    def reset_tracking_state(self):
        self.vehicle_status      = {}
        self.vehicle_counts      = defaultdict(int)
        self.counted_vehicles    = set()
        self.total_count         = 0
        self.frame_count         = 0
        self.current_congestion  = None
        self.congestion_events   = []
        self.congestion_module.reset_state()
        self.count_timestamps    = defaultdict(list)
        self.frame_data          = deque(maxlen=1000)
        self.counting_line_setup = False

    # ──────────────────────────────────────────────────────────────────────────
    # ROI
    # ──────────────────────────────────────────────────────────────────────────

    def set_roi(self, roi_normalized):
        if not roi_normalized:
            self.roi_enabled    = False
            self.roi_normalized = self.roi_pixels = self.roi_polygon = self.roi_area = None
            return
        if len(roi_normalized) < 3:
            raise ValueError("ROI needs >=3 points")
        self.roi_normalized = [
            [max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y)))]
            for x, y in roi_normalized
        ]
        self.roi_enabled = True
        self.roi_pixels  = self.roi_polygon = None

    def _setup_roi_pixels(self, w, h):
        if not self.roi_enabled or not self.roi_normalized or self.roi_pixels is not None:
            return
        self.roi_pixels  = [[int(x * w), int(y * h)] for x, y in self.roi_normalized]
        self.roi_polygon = np.array(self.roi_pixels, dtype=np.int32)
        pts, n = self.roi_pixels, len(self.roi_pixels)
        self.roi_area = abs(sum(
            pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
            for i in range(n)
        )) * 0.5

    def _in_roi(self, x, y):
        if not self.roi_enabled or self.roi_polygon is None:
            return True
        return cv2.pointPolygonTest(self.roi_polygon, (float(x), float(y)), False) >= 0

    # ──────────────────────────────────────────────────────────────────────────
    # Direction validation
    # ──────────────────────────────────────────────────────────────────────────

    def enhanced_is_valid_direction(self, raw_history, valid_direction_vector, threshold=None):
        """Check direction using RAW position history."""
        if threshold is None:
            threshold = self.DIRECTION_THRESHOLD

        pts = list(raw_history)
        if len(pts) < 3:
            return False
        pts = pts[-6:]
        if len(pts) < 2:
            return False

        net_dx = pts[-1][0] - pts[0][0]
        net_dy = pts[-1][1] - pts[0][1]
        mag    = math.hypot(net_dx, net_dy)
        if mag < 3:
            return False

        vx, vy = valid_direction_vector
        v_mag  = math.hypot(vx, vy)
        if v_mag < 1e-9:
            return False

        dot = (net_dx / mag) * (vx / v_mag) + (net_dy / mag) * (vy / v_mag)
        return dot >= threshold

    # ──────────────────────────────────────────────────────────────────────────
    # Side-state machine helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _raw_side(self, rx, ry):
        """Side of the counting line for a raw (unsmoothed) position."""
        if not self.line_start or not self.line_end:
            return 0
        lx1, ly1 = self.line_start
        lx2, ly2 = self.line_end
        return _sign(_side_of_line(rx, ry, lx1, ly1, lx2, ly2))

    def _raw_side_with_hysteresis(self, rx, ry, last_side):
        """
        Hysteretic side assignment. Within LINE_HYSTERESIS_PX of the line
        the last confirmed side is kept to prevent rapid flip-flop false counts.
        """
        if not self.line_start or not self.line_end:
            return 0
        dist = _distance_to_segment(
            rx, ry,
            self.line_start[0], self.line_start[1],
            self.line_end[0],   self.line_end[1],
        )
        if dist < self.LINE_HYSTERESIS_PX:
            return last_side
        return self._raw_side(rx, ry)

    # ──────────────────────────────────────────────────────────────────────────
    # Scene adaptation
    # ──────────────────────────────────────────────────────────────────────────

    def _detect_scene_context(self, frame, frame_number):
        mean_brightness = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
        if frame_number - self.scene_context['last_check_frame'] >= self.SCENE_CHECK_INTERVAL:
            self.scene_context['last_check_frame'] = frame_number
            self.scene_context['is_night']         = mean_brightness < 100
            self.scene_context['brightness']       = mean_brightness
        self._min_conf = self._get_adaptive_confidence()

    def _get_adaptive_confidence(self):
        conf       = self._min_conf_base
        brightness = self.scene_context.get('brightness', 100)
        if brightness < 80:
            conf *= 0.85
        elif brightness > 150:
            conf *= 1.1
        if self.time_based_adaptation and self._is_peak_hour():
            conf *= self.peak_hour_multiplier['confidence']
        min_per_class = min(self.class_confidence_thresholds.values())
        return max(min_per_class, min(0.45, conf))

    def _is_peak_hour(self):
        h = datetime.now().hour
        return any(s <= h < e for s, e in self.peak_hours)

    def _min_frames_for(self, class_name):
        base = self.MIN_FRAMES_BY_CLASS.get(class_name, self.MIN_FRAMES_DEFAULT)
        if self.time_based_adaptation and self._is_peak_hour():
            base = max(2, int(base * self.peak_hour_multiplier['min_frames']))
        return base

    # ──────────────────────────────────────────────────────────────────────────
    # Speed helper (legacy — kept for backward compatibility)
    # ──────────────────────────────────────────────────────────────────────────

    def _calculate_speed_kmh(self, track_id, current_pos, fps):
        if track_id not in self.vehicle_status:
            return None
        history = list(self.vehicle_status[track_id].get('raw_history', []))
        if len(history) < 3:
            return None
        recent = history[-3:]
        total_dist_px = sum(
            math.hypot(recent[i + 1][0] - recent[i][0], recent[i + 1][1] - recent[i][1])
            for i in range(len(recent) - 1)
        )
        time_elapsed_hours = (len(recent) - 1) / fps / 3600
        if time_elapsed_hours <= 0:
            return None
        speed_kmh = (total_dist_px / 12) / 1000 / time_elapsed_hours
        return min(max(speed_kmh, 0), 120)

    # ──────────────────────────────────────────────────────────────────────────
    # Main processing loop
    # ──────────────────────────────────────────────────────────────────────────

    def process_frame(self, frame, frame_number, fps, yolo_results=None):
        """Process a single frame: detection -> tracking -> counting -> congestion."""

        # One-time counting line and ROI pixel setup
        if not self.counting_line_setup:
            h, w = frame.shape[:2]
            self.line_start, self.line_end, self.valid_direction = self.setup_counting_line(w, h)
            self._setup_roi_pixels(w, h)
            self.counting_line_setup = True

        # Adaptive confidence based on scene brightness
        self._detect_scene_context(frame, frame_number)

        # ── YOLO inference ─────────────────────────────────────────────────
        if yolo_results is None:
            yolo_results = self.model.track(
                frame,
                persist=True,
                conf=self._min_conf,
                iou=0.45,
                agnostic_nms=True,
                classes=self.vehicle_class_ids,
                tracker=_BYTETRACK_PATH,
                verbose=False,
                device=self.device,
            )

        # ── Tracker post-processing ────────────────────────────────────────
        tracks         = self.tracker.postprocess_tracks(yolo_results, frame_number, fps)
        detections     = []
        current_counts = defaultdict(int)

        for track in tracks:
            track_id   = track['track_id']
            class_id   = track.get('class_id')
            class_name = track.get('class_name')

            if class_id in self.EXCLUDED_CLASS_IDS or class_name is None:
                continue
            if class_id not in self.class_names:
                continue

            conf = track.get('confidence', 0.0)
            if conf < self.class_confidence_thresholds.get(class_name, 0.20):
                continue

            # Kalman center — for display and congestion
            cx, cy = track['center']
            # Raw center — for counting geometry (no smoothing bias)
            rx, ry = track.get('raw_center', (cx, cy))

            in_roi  = self._in_roi(cx, cy)
            speed   = track.get('speed')
            heading = track.get('heading')
            t_len   = track.get('track_length', 0)

            # ── Initialise per-vehicle state ──────────────────────────────
            if track_id not in self.vehicle_status:
                initial_side = self._raw_side(rx, ry)
                min_approach = self.MIN_APPROACH_FRAMES_BY_CLASS.get(
                    class_name, self.MIN_APPROACH_FRAMES_DEFAULT
                )
                self.vehicle_status[track_id] = {
                    'class_name':       class_name,
                    'current_side':     initial_side,
                    'approach_side':    initial_side,
                    'approach_frames':  0,
                    'min_approach':     min_approach,
                    'has_crossed':      False,
                    'last_count_frame': -self.POST_COUNT_LOCKOUT_FRAMES,
                    'dir_memory':       deque(maxlen=self.DIRECTION_MEMORY_FRAMES),
                    'raw_history':      deque(maxlen=30),
                    'spawn_rx':         rx,
                    'spawn_ry':         ry,
                    'warmed_up':        False,
                }

            status = self.vehicle_status[track_id]
            status['raw_history'].append((rx, ry))

            # ── Warmup ────────────────────────────────────────────────────
            if not status['warmed_up']:
                if math.hypot(rx - status['spawn_rx'], ry - status['spawn_ry']) >= self.WARMUP_PX:
                    status['warmed_up'] = True

            # ── Direction check stored in memory ring (visualization only) ─
            # NOTE: Direction is computed for box coloring purposes only.
            # It does NOT gate counting — all crossings are counted regardless
            # of direction.
            is_valid_dir = (
                self.enhanced_is_valid_direction(status['raw_history'], self.valid_direction)
                if len(status['raw_history']) >= 3 else False
            )
            status['dir_memory'].append(is_valid_dir)

            # ── Side-state machine ────────────────────────────────────────
            new_side      = self._raw_side_with_hysteresis(rx, ry, status['current_side'])
            approach_side = status['approach_side']

            # Accumulate approach-side frames (capped to avoid integer overflow)
            if new_side == approach_side and new_side != 0:
                status['approach_frames'] = min(
                    status['approach_frames'] + 1,
                    status['min_approach'] + 10
                )

            # A crossing is detected when the vehicle flips to the opposite side
            side_flipped = (
                new_side != 0
                and approach_side != 0
                and new_side != approach_side
            )

            # ── COUNTING GATE ─────────────────────────────────────────────
            # COUNT ALL CROSSINGS regardless of bounding box color or direction.
            # Only requirements:
            #   1. side_flipped   — the vehicle actually crossed the line
            #   2. warmed_up      — must have moved at least WARMUP_PX pixels
            #                       (prevents counting vehicles spawned on the line)
            #   3. lockout_passed — prevents double-counting a single crossing
            #                       within POST_COUNT_LOCKOUT_FRAMES frames
            #
            # Removed gates (intentional):
            #   - track_id not in self.counted_vehicles  (was blocking re-crossings)
            #   - had_valid_direction                    (was skipping wrong-way vehicles)
            #   - min_approach_met                       (was blocking slow starters)
            #   - min_frames_ok                          (was blocking short tracks)
            lockout_passed = (
                frame_number - status['last_count_frame']
            ) >= self.POST_COUNT_LOCKOUT_FRAMES

            if side_flipped and status['warmed_up'] and lockout_passed:
                self.total_count                += 1
                self.vehicle_counts[class_name] += 1
                self.counted_vehicles.add(track_id)
                self.count_timestamps[class_name].append(frame_number / fps)
                status['has_crossed']      = True
                status['last_count_frame'] = frame_number
                status['approach_frames']  = 0
                # Reset approach_side to current side so a return crossing
                # can also be counted after the lockout expires.
                status['approach_side']    = new_side

                logger.debug(
                    f"COUNT: tid={track_id} class={class_name} "
                    f"frame={frame_number} total={self.total_count}"
                )

            # Update side AFTER the counting check
            status['current_side'] = new_side

            # ── Box colour (visual only, does not affect counting) ─────────
            # Green  = crossed in the expected direction
            # Orange = crossed in the wrong / erratic direction
            # Yellow = moving, valid direction, not yet crossed, speed unknown
            # Red    = slow vehicle in valid direction
            # Cyan   = medium-speed vehicle
            # Bright green = fast vehicle
            # Gray   = not yet warmed up
            # Blue   = warmed up but no valid direction yet
            color_valid_dir = any(status['dir_memory'])

            if status['has_crossed']:
                box_color = (0, 255, 0) if color_valid_dir else (0, 140, 255)
            elif color_valid_dir and status['warmed_up']:
                if speed is None:    box_color = (255, 255,   0)
                elif speed < 10:     box_color = (  0,   0, 255)
                elif speed < 30:     box_color = (  0, 165, 255)
                else:                box_color = (  0, 255,   0)
            elif not status['warmed_up']:
                box_color = (128, 128, 128)
            else:
                box_color = (100, 100, 255)

            detections.append({
                'track_id':        track_id,
                'class_name':      class_name,
                'center':          (cx, cy),
                'bbox':            track['box'],
                'confidence':      conf,
                'color':           box_color,
                'counted':         status['has_crossed'],
                'valid_direction': color_valid_dir,
                'warmed_up':       status['warmed_up'],
                'in_roi':          in_roi,
                'speed':           speed,
                'heading':         heading,
            })
            current_counts[class_name] += 1

        # ── Congestion detection ───────────────────────────────────────────
        cong_src  = (
            [d for d in detections if d['in_roi']] if self.roi_enabled else detections
        )
        cong_area = self.roi_area if (self.roi_enabled and self.roi_area) else None
        cong      = self.congestion_module.detect_congestion(
            cong_src, fps, roi_area=cong_area
        )
        cong['total_vehicles_full_frame'] = len(detections)
        cong['total_vehicles_in_roi']     = sum(1 for d in detections if d.get('in_roi'))

        # ── Speed statistics ───────────────────────────────────────────────
        visible_speeds = [d['speed'] for d in detections if d['speed'] is not None]
        speed_p50 = round(float(np.median(visible_speeds)), 1) if visible_speeds else None
        speed_p85 = (
            round(float(np.percentile(visible_speeds, 85)), 1)
            if len(visible_speeds) >= 4 else None
        )

        # ── Frame data record ──────────────────────────────────────────────
        self.frame_data.append({
            'frame_number':             frame_number,
            'timestamp':                round(frame_number / fps, 3) if fps > 0 else 0,
            'vehicle_count_full_frame': sum(current_counts.values()),
            'vehicle_count_in_roi':     sum(1 for d in detections if d.get('in_roi')),
            'vehicle_breakdown':        dict(current_counts),
            'total_counted':            self.total_count,
            'congestion_level':         cong.get('level', 'none'),
            'congestion_score':         cong.get('congestion_score', 0),
            'stationary_vehicles':      cong.get('stationary_vehicles', 0),
            'speed_p50_kmh':            speed_p50,
            'speed_p85_kmh':            speed_p85,
        })

        self.frame_count = frame_number
        return current_counts, detections, cong

    # ──────────────────────────────────────────────────────────────────────────
    # Visualization
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _speed_color(speed):
        if speed is None: return (180, 180, 180)
        if speed >= 30:   return (0, 255,   0)
        if speed >= 15:   return (0, 200, 200)
        if speed >= 5:    return (0, 140, 255)
        return (0, 0, 255)

    def draw_detections(self, frame, detections, congestion_info, fps):
        h, w = frame.shape[:2]

        # ROI overlay
        if self.roi_enabled and self.roi_polygon is not None:
            ov = frame.copy()
            cv2.fillPoly(ov, [self.roi_polygon], (0, 255, 255))
            cv2.addWeighted(ov, 0.10, frame, 0.90, 0, frame)
            cv2.polylines(frame, [self.roi_polygon], True, (0, 255, 255), 2)

        # Counting line
        if self.line_start and self.line_end:
            lvl = congestion_info.get('level', 'none')
            line_col = {
                'none':     (  0, 255,   0),
                'light':    (  0, 255, 255),
                'moderate': (  0, 165, 255),
                'heavy':    (  0,   0, 255),
                'severe':   (180,   0, 180),
            }.get(lvl, (0, 255, 0))
            cv2.line(frame, self.line_start, self.line_end, line_col, 4)

            mid = (
                (self.line_start[0] + self.line_end[0]) // 2,
                (self.line_start[1] + self.line_end[1]) // 2,
            )
            if self.valid_direction:
                dx, dy    = self.valid_direction
                arrow_end = (int(mid[0] + dx * 30), int(mid[1] + dy * 30))
                cv2.arrowedLine(frame, mid, arrow_end, (255, 255, 255), 2)

        # Title and total count
        cv2.putText(frame, f"{self.direction_name}", (20, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0, 255, 255), 2)
        cv2.putText(frame, f"TOTAL: {self.total_count}", (20, 72),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.10, (0, 255, 0), 3)

        # HUD panel
        lvl   = congestion_info.get('level', 'none')
        scr   = congestion_info.get('congestion_score', 0)
        onset = congestion_info.get('onset_rate', 0.0)
        trend = "▲" if onset > 1 else ("▼" if onset < -1 else "─")

        hx = w - 300
        cv2.rectangle(frame, (hx, 15), (w - 10, 200), (0, 0, 0), -1)
        line_col = {
            'none':     (  0, 255,   0),
            'light':    (  0, 255, 255),
            'moderate': (  0, 165, 255),
            'heavy':    (  0,   0, 255),
            'severe':   (180,   0, 180),
        }.get(lvl, (0, 255, 0))
        cv2.rectangle(frame, (hx, 15), (w - 10, 200), line_col, 2)

        y = 40
        cv2.putText(frame, f"CONG: {lvl.upper()} {trend}", (hx + 8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, line_col, 1)
        y += 20
        cv2.putText(frame, f"Score: {scr}/100", (hx + 8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1)
        y += 20
        cv2.putText(frame, f"Vehicles: {congestion_info.get('total_vehicles_full_frame', 0)}",
                    (hx + 8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1)
        y += 20
        cv2.putText(frame, f"Static: {congestion_info.get('stationary_vehicles', 0)}",
                    (hx + 8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1)

        # Centroid trails
        for det in detections:
            tid       = det['track_id']
            box_color = det['color']

            trajectory = self.tracker.get_trajectory(tid, max_points=20)
            n_pts      = len(trajectory)

            if n_pts >= 2:
                for i in range(1, n_pts):
                    alpha     = i / n_pts
                    seg_color = tuple(int(c * alpha) for c in box_color)
                    thickness = 1 if alpha < 0.5 else 2
                    cv2.line(frame, trajectory[i - 1], trajectory[i], seg_color, thickness)

            cx, cy = det['center']
            cv2.circle(frame, (cx, cy), 4, box_color, -1)
            cv2.circle(frame, (cx, cy), 4, (255, 255, 255), 1)

        # Bounding boxes
        for det in detections:
            x, y_b, wb, hb = det['bbox']
            speed     = det.get('speed')
            box_color = det['color']

            cv2.rectangle(frame, (x, y_b), (x + wb, y_b + hb), box_color, 2)

            lbl = det['class_name'][:3].upper()
            if det['counted']:
                lbl += "✓"
            if speed is not None:
                lbl += f" {speed:.0f}k"
            if det.get('heading'):
                lbl += f" {det['heading']}"

            (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            cv2.rectangle(frame, (x, y_b - th - 5), (x + tw + 4, y_b), box_color, -1)
            cv2.putText(frame, lbl, (x + 2, y_b - 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1)

        return frame

    # ──────────────────────────────────────────────────────────────────────────
    # Report generation
    # ──────────────────────────────────────────────────────────────────────────

    def generate_report(self, total_frames, proc_time, fps):
        duration     = total_frames / fps if fps > 0 else 0
        vpm          = (self.total_count / duration) * 60 if duration > 0 else 0
        cong_summary = self.congestion_module.get_congestion_summary()

        speeds    = [f['speed_p50_kmh'] for f in self.frame_data if f.get('speed_p50_kmh')]
        avg_speed = round(float(np.mean(speeds)), 1) if speeds else None

        return {
            'metadata': {
                'direction':               self.direction_name,
                'version':                 'v5.3',
                'duration_seconds':        round(duration, 1),
                'processing_time_seconds': round(proc_time, 1),
                'frames_processed':        total_frames,
                'fps':                     round(fps, 2),
            },
            'counting_results': {
                'total_vehicles':      self.total_count,
                'vehicle_breakdown':   dict(self.vehicle_counts),
                'vehicles_per_minute': round(vpm, 1),
            },
            'speed_results': {'avg_speed_kmh': avg_speed},
            'congestion_results': {
                'total_events':           cong_summary['total_events'],
                'final_congestion_level': cong_summary['current_level'],
            },
            'raw_data': {
                'frame_data':       list(self.frame_data),
                'count_timestamps': {k: v[-2000:] for k, v in self.count_timestamps.items()},
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Abstract methods — subclasses must implement
    # ──────────────────────────────────────────────────────────────────────────

    def setup_counting_line(self, frame_width, frame_height):
        """Return (line_start, line_end, valid_direction_vector)."""
        raise NotImplementedError

    def is_valid_direction(self, history, valid_direction_vector):
        """Default delegates to enhanced_is_valid_direction."""
        return self.enhanced_is_valid_direction(history, valid_direction_vector)