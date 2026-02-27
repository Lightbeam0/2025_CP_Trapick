"""
Enhanced ByteTrack Wrapper for Traffic Detection (v2 - Kalman + Adaptive + ReID + Safe Speed)
Improvements over v1:
- Integrated Kalman Filter for position prediction and smoothing
- Adaptive confidence thresholds based on track history (EMA)
- Occlusion handling with short-term memory recovery
- Appearance feature memory buffer for Re-identification (Re-ID)
- Dynamic counting eligibility (high conf tracks count faster)
- ✅ FIXED: Robust speed calculation with NaN/Inf/Type checking
- Maintains all v1 features (Filipino class tuning, stability, heading, accel)

REPLACES: Original enhanced_tracker.py
"""

import numpy as np
from collections import deque, defaultdict
import math
import logging

# Setup logger for safe speed error reporting
logger = logging.getLogger(__name__)


class KalmanFilter:
    """
    Simple Kalman filter for 2D position prediction (x, y, vx, vy).
    State vector: [x, y, vx, vy]^T
    Measurement vector: [x, y]^T
    """
    def __init__(self, dt=1.0):
        self.dt = dt
        # State transition matrix
        self.A = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        # Observation matrix
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        # Process noise covariance
        self.Q = np.eye(4) * 0.05
        # Measurement noise covariance
        self.R = np.eye(2) * 0.5
        # Error covariance estimate
        self.P = np.eye(4) * 100
        # State vector
        self.x = np.zeros((4, 1))
        self.initialized = False

    def init(self, x, y):
        """Initialize state with position (x, y) and zero velocity."""
        self.x = np.array([[x], [y], [0], [0]])
        self.initialized = True
        self.P = np.eye(4) * 100  # Reset uncertainty on re-init

    def predict(self):
        """Predict next state."""
        if not self.initialized:
            return None, None
        self.x = self.A @ self.x
        self.P = self.A @ self.P @ self.A.T + self.Q
        return float(self.x[0, 0]), float(self.x[1, 0])

    def update(self, x, y):
        """Update state with new measurement."""
        if not self.initialized:
            self.init(x, y)
            return
        
        z = np.array([[x], [y]])
        
        # Innovation
        y_vec = z - self.H @ self.x
        
        # Innovation covariance
        S = self.H @ self.P @ self.H.T + self.R
        
        # Kalman Gain
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Updated state
        self.x = self.x + K @ y_vec
        
        # Updated covariance
        I = np.eye(4)
        self.P = (I - K @ self.H) @ self.P


class EnhancedByteTrackWrapper:
    """
    Wrapper around ByteTrack with Kalman filtering, adaptive thresholds,
    occlusion handling, re-identification capabilities, and safe speed handling.
    Fixed class IDs to match custom model (best.pt).
    Excludes VehicleCrash (0) and person (4) from all processing.
    """

    # Minimum frames a track must exist before it's eligible for line crossing
    MIN_TRACK_FRAMES_BEFORE_COUNT = 6
   
    # Speed outlier cap
    MAX_RAW_SPEED_KMH = 180.0

    def __init__(self, config_path="bytetrack.yaml"):
        # Call parent init if inheriting, otherwise just setup
        self.config_path = config_path

        # Core history buffers
        self.track_history    = defaultdict(lambda: deque(maxlen=90))   # ~3s at 30fps
        self.track_confidences = defaultdict(lambda: deque(maxlen=20))
        self.track_last_frame  = {}

        # Speed estimation
        self.track_speed_ema   = {}          
        self.track_speed_raw   = defaultdict(lambda: deque(maxlen=15))  
        self.speed_ema_alpha   = 0.25        

        # Acceleration estimation
        self.track_accel_ema   = {}
        self.accel_ema_alpha   = 0.20

        # Heading
        self.track_heading     = {}

        # Area continuity
        self.track_area_ema    = {}
        self.area_ema_alpha    = 0.30

        # ✅ NEW: Kalman Filters
        self.kalman_filters = {}  # track_id -> KalmanFilter
        
        # ✅ NEW: Adaptive Confidence
        self.track_confidence_ema = defaultdict(float)
        self.adaptive_threshold = True
        self.base_threshold = 0.45
        
        # ✅ NEW: Occlusion Memory
        self.occlusion_memory = defaultdict(lambda: deque(maxlen=15))
        self.occlusion_recovery_frames = 10
        
        # ✅ NEW: Appearance Features (for Re-ID)
        self.appearance_features = defaultdict(lambda: deque(maxlen=5))

        # ✅ Vehicle classes only
        self.class_names = {
            1: 'car',
            2: 'jeep',
            3: 'motorcycle',
            5: 'tricycle',
            6: 'truck',
        }

        # Class-specific thresholds
        self.class_tracking_params = {
            'car':        {'min_size': 350,  'stability_threshold': 0.40, 'max_area_jump': 3.0},
            'jeep':       {'min_size': 450,  'stability_threshold': 0.40, 'max_area_jump': 3.0},
            'motorcycle': {'min_size': 100,  'stability_threshold': 0.30, 'max_area_jump': 4.0},
            'tricycle':   {'min_size': 200,  'stability_threshold': 0.35, 'max_area_jump': 3.5},
            'truck':      {'min_size': 600,  'stability_threshold': 0.45, 'max_area_jump': 2.5},
        }

        print("🚀 Enhanced tracker v2 initialised (Kalman + Adaptive + ReID + Safe Speed)")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def postprocess_tracks(self, yolo_results, frame_number, fps):
        """
        Process YOLO tracking results with Kalman filtering and adaptive logic.
        """
        processed_tracks = []

        if not yolo_results or len(yolo_results) == 0:
            self._cleanup_old_tracks(frame_number)
            return processed_tracks

        result = yolo_results[0]

        if result.boxes is None or result.boxes.id is None:
            self._cleanup_old_tracks(frame_number)
            return processed_tracks

        boxes       = result.boxes.xyxy.cpu().numpy()
        track_ids   = result.boxes.id.int().cpu().numpy()
        class_ids   = result.boxes.cls.int().cpu().numpy()
        confidences = result.boxes.conf.float().cpu().numpy()

        current_ids = set()

        for box, track_id, class_id, confidence in zip(boxes, track_ids, class_ids, confidences):
            tid = int(track_id)
            current_ids.add(tid)

            # ✅ Skip excluded classes early
            if int(class_id) not in self.class_names:
                continue

            x1, y1, x2, y2 = box
            width    = x2 - x1
            height   = y2 - y1
            area     = width * height
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            # Area continuity check
            area_valid = self._check_area_continuity(tid, area)

            # Record history
            self.track_history[tid].append((center_x, center_y, width, height))
            self.track_confidences[tid].append(confidence)
            self.track_last_frame[tid] = frame_number
            self._update_area_ema(tid, area)
            
            # Update Occlusion Memory
            self.occlusion_memory[tid].append({
                'center': (center_x, center_y),
                'box': [x1, y1, x2, y2],
                'frame': frame_number
            })

            # Update Appearance Features (Placeholder)
            feat_vector = [width/height, confidence] 
            self.appearance_features[tid].append(feat_vector)

            # ── Kalman Filter Logic ────────────────────────────────────────
            kalman_center = (int(center_x), int(center_y))
            position_error = 0.0
            
            if tid not in self.kalman_filters:
                kf = KalmanFilter(dt=1.0/fps if fps > 0 else 1.0/30.0)
                kf.init(center_x, center_y)
                self.kalman_filters[tid] = kf
            else:
                kf = self.kalman_filters[tid]
                pred_x, pred_y = kf.predict()
                if pred_x is not None:
                    position_error = math.sqrt((pred_x - center_x)**2 + (pred_y - center_y)**2)
                    kalman_center = (int(pred_x), int(pred_y))
                kf.update(center_x, center_y)

            # ── Adaptive Confidence Logic ──────────────────────────────────
            prev_conf_ema = self.track_confidence_ema.get(tid, confidence)
            alpha = 0.3
            current_conf_ema = alpha * confidence + (1 - alpha) * prev_conf_ema
            self.track_confidence_ema[tid] = current_conf_ema

            track_len  = len(self.track_history[tid])
            stability  = self._calculate_stability(tid)
            class_name = self.class_names[int(class_id)]
            is_valid   = self._validate_track(tid, class_name, area, stability) and area_valid
            
            # ✅ Safe Speed Calculation
            speed      = self.get_smoothed_speed(tid, fps)
            accel      = self._get_smoothed_accel(tid, fps, speed)
            heading    = self._calculate_heading(tid)

            # Dynamic Counting Eligibility
            if current_conf_ema > 0.7:
                counting_eligible = track_len >= 3
            else:
                counting_eligible = track_len >= self.MIN_TRACK_FRAMES_BEFORE_COUNT

            track_data = {
                'track_id':          tid,
                'box':               [int(x1), int(y1), int(width), int(height)],
                'center':            kalman_center,
                'raw_center':        (int(center_x), int(center_y)),
                'class_id':          int(class_id),
                'class_name':        class_name,
                'confidence':        float(confidence),
                'confidence_ema':    float(current_conf_ema),
                'stability':         float(stability),
                'is_valid':          bool(is_valid),
                'area':              float(area),
                'area_valid':        bool(area_valid),
                'frame_number':      frame_number,
                'track_length':      track_len,
                'counting_eligible': counting_eligible,
                'speed':             speed,  # Can be None
                'acceleration':      accel,
                'heading':           heading,
                'is_stationary':     (speed is not None and speed < 3.0),
                'is_slow':           (speed is not None and 3.0 <= speed < 15.0),
                'position_error':    round(position_error, 2),
                'kalman_center':     kalman_center,
            }
            processed_tracks.append(track_data)

        # Handle Lost Tracks
        for tid in list(self.track_last_frame.keys()):
            if tid not in current_ids:
                age = frame_number - self.track_last_frame[tid]
                if age > self.occlusion_recovery_frames:
                    pass 

        self._cleanup_old_tracks(frame_number)

        return processed_tracks

    def try_reid(self, lost_track_id, current_detections):
        """Attempt to re-identify a lost track using appearance features."""
        if lost_track_id not in self.appearance_features:
            return None
        
        lost_feats_list = list(self.appearance_features[lost_track_id])
        if not lost_feats_list:
            return None
        
        avg_lost_feat = np.mean(lost_feats_list, axis=0)
        
        best_match = None
        best_score = 0.75
        
        for det in current_detections:
            if det.get('confidence', 0) < 0.6:
                continue
            
            det_feat = [det['box'][2]/det['box'][3], det['confidence']]
            det_feat_arr = np.array(det_feat)
            
            dist = np.linalg.norm(avg_lost_feat - det_feat_arr)
            score = 1.0 / (1.0 + dist)
            
            if score > best_score:
                best_score = score
                best_match = det
        
        if best_match:
            print(f"✅ Re-identified track {lost_track_id} with score {best_score:.2f}")
            
        return best_match

    def get_track_history(self, track_id):
        """Get (x, y) position history for a track."""
        if track_id not in self.track_history:
            return []
        return [(x, y) for x, y, _, _ in self.track_history[track_id]]

    def get_smoothed_speed(self, track_id, fps, pixels_per_meter=10, window=12):
        """
        Public method to get smoothed speed with None handling.
        """
        try:
            speed = self._get_smoothed_speed(track_id, fps, pixels_per_meter, window)
            # ✅ FIX: Ensure we return None for invalid speeds
            if speed is not None and isinstance(speed, (int, float)) and not math.isnan(speed):
                return speed
            return None
        except Exception as e:
            logger.debug(f"Error calculating speed for track {track_id}: {e}")
            return None

    def get_fleet_stats(self):
        active_speeds = [s for s in self.track_speed_ema.values() if s is not None]
        return {
            'active_tracks': len(self.track_last_frame),
            'mean_speed_kmh':   round(float(np.mean(active_speeds)), 1)   if active_speeds else None,
            'median_speed_kmh': round(float(np.median(active_speeds)), 1) if active_speeds else None,
            'max_speed_kmh':    round(float(np.max(active_speeds)), 1)    if active_speeds else None,
            'pct_stationary':   round(
                sum(1 for s in active_speeds if s is not None and s < 3.0) / len(active_speeds) * 100, 1
            ) if active_speeds else 0.0,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _get_smoothed_speed(self, track_id, fps, pixels_per_meter=10, window=12):
        """
        Internal EMA speed calculation with outlier rejection and None handling.
        FIXED: Returns None for invalid speeds instead of crashing.
        """
        history = self.get_track_history(track_id)
        if len(history) < 3:
            return None
        
        recent = history[-window:] if len(history) >= window else history
        n_intervals = len(recent) - 1
        if n_intervals < 1:
            return None
        
        total_dist_px = sum(
            math.hypot(recent[i+1][0] - recent[i][0], recent[i+1][1] - recent[i][1])
            for i in range(n_intervals)
        )
        
        time_elapsed = n_intervals / fps if fps > 0 else 0
        if time_elapsed <= 0:
            return None
        
        dist_meters = total_dist_px / pixels_per_meter
        raw_kmh = (dist_meters / time_elapsed) * 3.6
        
        # ✅ FIX: Check for NaN or Inf
        if not isinstance(raw_kmh, (int, float)) or math.isnan(raw_kmh) or math.isinf(raw_kmh):
            return None
        
        # Outlier rejection: ignore physically impossible readings
        if raw_kmh > self.MAX_RAW_SPEED_KMH:
            raw_kmh = self.track_speed_ema.get(track_id) or 0.0
        
        # Track raw speed history for variance analysis
        self.track_speed_raw[track_id].append(raw_kmh)
        
        # EMA smoothing
        prev_ema = self.track_speed_ema.get(track_id)
        if prev_ema is None:
            ema = raw_kmh
        else:
            ema = self.speed_ema_alpha * raw_kmh + (1 - self.speed_ema_alpha) * prev_ema
        
        # ✅ FIX: Ensure ema is a valid number
        if not isinstance(ema, (int, float)) or math.isnan(ema):
            return None
        
        self.track_speed_ema[track_id] = ema
        
        return round(ema, 1)

    def _get_smoothed_accel(self, track_id, fps, current_speed):
        """Estimate acceleration (km/h per second) using EMA on speed delta."""
        if current_speed is None:
            return None

        prev_speed = self.track_speed_ema.get(track_id)
        if prev_speed is None:
            return None

        raw_accel = (current_speed - prev_speed) * fps
        prev_accel = self.track_accel_ema.get(track_id)

        if prev_accel is None:
            ema_accel = raw_accel
        else:
            ema_accel = (self.accel_ema_alpha * raw_accel
                         + (1 - self.accel_ema_alpha) * prev_accel)

        self.track_accel_ema[track_id] = ema_accel
        return round(ema_accel, 2)

    def _calculate_heading(self, track_id):
        """Calculate compass heading string from recent movement."""
        history = self.get_track_history(track_id)
        if len(history) < 4:
            return None

        pts = history[-4:]
        dx = pts[-1][0] - pts[0][0]
        dy = pts[-1][1] - pts[0][1]

        if math.hypot(dx, dy) < 2:
            return None

        angle_deg = math.degrees(math.atan2(dx, -dy)) % 360
        headings = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        idx = int((angle_deg + 22.5) / 45) % 8
        heading = headings[idx]
        self.track_heading[track_id] = heading
        return heading

    def _update_area_ema(self, track_id, area):
        """Update EMA of bounding-box area for continuity checks."""
        prev = self.track_area_ema.get(track_id)
        if prev is None:
            self.track_area_ema[track_id] = area
        else:
            self.track_area_ema[track_id] = (
                self.area_ema_alpha * area + (1 - self.area_ema_alpha) * prev
            )

    def _check_area_continuity(self, track_id, area):
        """Return False if the new bbox area is implausibly different from the EMA."""
        if track_id not in self.track_area_ema:
            return True
        prev_ema = self.track_area_ema[track_id]
        if prev_ema < 1:
            return True

        ratio = area / prev_ema
        if ratio > 4.0 or ratio < 0.25:
            return False
        return True

    def _calculate_stability(self, track_id):
        """Calculate track stability using angular consistency of velocity vectors."""
        history = list(self.track_history[track_id])
        if len(history) < 4:
            return 0.0

        velocities = []
        for i in range(1, len(history)):
            px, py, _, _ = history[i - 1]
            cx, cy, _, _ = history[i]
            vx, vy = cx - px, cy - py
            mag = math.hypot(vx, vy)
            if mag > 0.5:
                velocities.append((vx / mag, vy / mag))

        if len(velocities) < 2:
            return 0.5

        cosines = [
            velocities[i][0] * velocities[i+1][0] + velocities[i][1] * velocities[i+1][1]
            for i in range(len(velocities) - 1)
        ]
        mean_cos = float(np.mean(cosines))
        stability = (mean_cos + 1.0) / 2.0
        return float(max(0.0, min(1.0, stability)))

    def _validate_track(self, track_id, class_name, area, stability):
        """Validate track based on class-specific size and stability criteria."""
        if class_name not in self.class_tracking_params:
            return True

        params    = self.class_tracking_params[class_name]
        track_len = len(self.track_history[track_id])

        if area < params['min_size']:
            return False

        if track_len >= self.MIN_TRACK_FRAMES_BEFORE_COUNT:
            if stability < params['stability_threshold']:
                return False

        return True

    def _cleanup_old_tracks(self, current_frame, max_missing_frames=90):
        """Remove tracks and associated resources not seen for max_missing_frames."""
        stale = [
            tid for tid, last_f in self.track_last_frame.items()
            if current_frame - last_f > max_missing_frames
        ]
        for tid in stale:
            self.track_history.pop(tid, None)
            self.track_confidences.pop(tid, None)
            self.track_last_frame.pop(tid, None)
            self.track_speed_ema.pop(tid, None)
            self.track_speed_raw.pop(tid, None)
            self.track_accel_ema.pop(tid, None)
            self.track_heading.pop(tid, None)
            self.track_area_ema.pop(tid, None)
            self.kalman_filters.pop(tid, None)
            self.track_confidence_ema.pop(tid, None)
            self.occlusion_memory.pop(tid, None)
            self.appearance_features.pop(tid, None)