"""
ENHANCED Congestion Detection Module — v2.1
FIXES: NoneType comparison bug, integrates with Django models
"""

import numpy as np
from collections import defaultdict, deque
import time
import math
import logging

logger = logging.getLogger(__name__)

try:
    from sklearn.cluster import DBSCAN
    CLUSTERING_AVAILABLE = True
except ImportError:
    CLUSTERING_AVAILABLE = False


class CongestionModule:
    """
    Enhanced multi-factor congestion detection with temporal smoothing.
    FIXED: Handles None speeds safely, integrates with Django models
    """

    def __init__(self, config=None):
        self.config = {**self._default_config(), **(config or {})}
        self.reset_state()

        # Score history for smoothing and trend detection
        self.congestion_score_history = deque(maxlen=self.config['smoothing_window'])
        self.level_history = deque(maxlen=self.config['smoothing_window'])

        logger.info("🚦 Enhanced Congestion Module v2.1 initialised")
        logger.info(f"   Clustering: {'DBSCAN' if CLUSTERING_AVAILABLE else 'simple greedy'}")
        logger.info(f"   Smoothing window: {self.config['smoothing_window']} frames")

    # ──────────────────────────────────────────────────────────────────────────
    # Config
    # ──────────────────────────────────────────────────────────────────────────

    def _default_config(self):
        return {
            # Stationary detection
            'stationary_speed_threshold': 4.0,   # km/h — below this = stationary
            'stationary_pixel_threshold': 4,     # px movement — backup for no-speed case
            'stationary_duration_seconds': 8.0,   # seconds to classify as "long stationary"

            # Spatial clustering
            'proximity_threshold': 75,   # px — vehicle centres within this = same cluster
            'min_cluster_size': 3,

            # Smoothing / hysteresis
            'smoothing_window': 20,          # frames for EMA window
            'upgrade_threshold': 3,          # consecutive frames needed to go UP a level
            'downgrade_threshold': 10,       # consecutive frames needed to go DOWN a level

            # Multi-factor weights (must sum to 1.0)
            'weights': {
                'vehicle_count': 0.25,
                'density': 0.20,
                'stationary': 0.25,
                'clustering': 0.20,
                'speed_variance': 0.10,
            },

            # Score → level thresholds (score 0–100)
            'level_thresholds': {
                'none': (0, 20),
                'light': (20, 40),
                'moderate': (40, 60),
                'heavy': (60, 80),
                'severe': (80, 100),
            },

            # Event recording
            'min_congestion_duration': 20,  # seconds — shorter events ignored
            
            # ✅ NEW: Incident detection thresholds
            'incident_speed_threshold': 2.0,           # km/h
            'incident_duration_threshold': 30,         # seconds
            'incident_cluster_size': 5,                 # vehicles
        }

    # ──────────────────────────────────────────────────────────────────────────
    # State management
    # ──────────────────────────────────────────────────────────────────────────

    def reset_state(self):
        self.vehicle_positions = {}
        self.vehicle_stationary_sec = defaultdict(float)  # seconds stationary
        self.vehicle_speeds = {}
        self.vehicle_last_frame = {}

        self.congestion_events = []
        self.current_congestion = self._empty_congestion()

        self.frame_count = 0
        self.last_congestion_level = 'none'

        # Hysteresis counters (separate up/down)
        self._upgrade_counter = 0
        self._downgrade_counter = 0
        self._pending_level = 'none'

        # Trend tracking
        self._score_prev = 0.0
        self._onset_rate = 0.0  # EMA of score delta

        self.stats = {
            'total_vehicles_processed': 0,
            'max_simultaneous_vehicles': 0,
            'total_frames': 0,
        }

    def _empty_congestion(self):
        return {
            'level': 'none', 'start_time': None,
            'vehicles_count': 0, 'stationary_count': 0, 'peak_score': 0.0,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # ✅ FIX: Safe speed comparison helper
    # ──────────────────────────────────────────────────────────────────────────

    def _safe_speed_compare(self, speed, threshold, operator='le'):
        """
        Safely compare speed with threshold, handling None values
        
        Args:
            speed: Speed value (could be None)
            threshold: Threshold to compare against
            operator: 'le' (<=), 'lt' (<), 'ge' (>=), 'gt' (>)
        
        Returns:
            Boolean result, False if speed is None
        """
        if speed is None:
            return False
        
        if not isinstance(speed, (int, float)):
            return False
        
        if operator == 'le':
            return speed <= threshold
        elif operator == 'lt':
            return speed < threshold
        elif operator == 'ge':
            return speed >= threshold
        elif operator == 'gt':
            return speed > threshold
        else:
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # ✅ FIX: Validate detections before processing
    # ──────────────────────────────────────────────────────────────────────────

    def _validate_detections(self, detections):
        """
        Validate and clean detection data before processing
        Ensures compatibility with Django model fields
        """
        valid_detections = []
        
        for det in detections:
            # Ensure required fields exist
            if not isinstance(det, dict):
                continue
            
            # Ensure track_id exists
            if 'track_id' not in det:
                continue
            
            # Ensure center exists and is valid
            if 'center' not in det or not isinstance(det['center'], (tuple, list)) or len(det['center']) != 2:
                continue
            
            # Clean speed field - CRITICAL FIX
            if 'speed' in det:
                speed = det['speed']
                # Convert None or invalid to None for safe handling
                if speed is None or not isinstance(speed, (int, float)) or math.isnan(speed):
                    det['speed'] = None
            
            # Ensure class_name exists for Django integration
            if 'class_name' not in det:
                # Map class_id to class_name if possible
                class_id = det.get('class_id')
                if class_id == 1:
                    det['class_name'] = 'car'
                elif class_id == 2:
                    det['class_name'] = 'jeep'
                elif class_id == 3:
                    det['class_name'] = 'motorcycle'
                elif class_id == 5:
                    det['class_name'] = 'tricycle'
                elif class_id == 6:
                    det['class_name'] = 'truck'
                else:
                    det['class_name'] = 'unknown'
            
            valid_detections.append(det)
        
        return valid_detections

    # ──────────────────────────────────────────────────────────────────────────
    # Factor calculations (with None handling)
    # ──────────────────────────────────────────────────────────────────────────

    def _score_vehicle_count(self, n):
        """Non-linear count score — diminishing returns above ~20 vehicles."""
        return min(100.0, (1 - math.exp(-n / 10.0)) * 110)

    def calculate_density(self, detections, roi_area=None):
        """Vehicles per unit area, normalised to 0–100."""
        n = len(detections)
        if n < 2:
            return 0.0
        positions = np.array([d['center'] for d in detections], dtype=float)
        if roi_area and roi_area > 0:
            area = roi_area
        else:
            span = positions.max(axis=0) - positions.min(axis=0)
            area = max(span[0] * span[1], 1.0)

        # Normalise against a reference density of 1 vehicle per 5000 px²
        raw_density = n / area
        return min(100.0, raw_density / (1.0 / 5000.0) * 100.0)

    def _update_stationary_timers(self, detections, fps):
        """Update per-vehicle stationary duration (seconds) with None handling"""
        dt = 1.0 / fps if fps > 0 else 1.0 / 30.0
        seen_ids = set()
        
        for det in detections:
            tid = det['track_id']
            cx, cy = det['center']
            # ✅ FIX: Safely get speed
            speed = det.get('speed')
            seen_ids.add(tid)
            
            is_stationary = False
            if speed is not None:
                # ✅ FIX: Safe comparison
                is_stationary = speed < self.config['stationary_speed_threshold']
            elif tid in self.vehicle_positions:
                prev = self.vehicle_positions[tid]
                is_stationary = math.hypot(cx - prev[0], cy - prev[1]) < self.config['stationary_pixel_threshold']
            
            if is_stationary:
                self.vehicle_stationary_sec[tid] += dt
            else:
                self.vehicle_stationary_sec[tid] = 0.0
            
            self.vehicle_positions[tid] = (cx, cy)
            self.vehicle_last_frame[tid] = self.frame_count
        
        # Count stationary vehicles safely
        stationary_count = 0
        for det in detections:
            tid = det.get('track_id')
            if tid and tid in self.vehicle_stationary_sec:
                if self.vehicle_stationary_sec[tid] > 0:
                    stationary_count += 1
        
        # Decay stale tracks
        for tid in list(self.vehicle_last_frame):
            if tid not in seen_ids:
                age = self.frame_count - self.vehicle_last_frame[tid]
                if age > fps * 5:  # 5-second grace period
                    self.vehicle_positions.pop(tid, None)
                    self.vehicle_stationary_sec.pop(tid, None)
                    self.vehicle_last_frame.pop(tid, None)
        
        return stationary_count

    def _score_stationary(self, detections, fps):
        """
        Stationary score with None handling
        """
        if not detections:
            return 0.0
        
        n = len(detections)
        
        # ✅ FIX: Count long stationary safely
        long_stationary = 0
        short_stationary = 0
        
        for d in detections:
            tid = d.get('track_id')
            if tid and tid in self.vehicle_stationary_sec:
                duration = self.vehicle_stationary_sec[tid]
                if duration >= self.config['stationary_duration_seconds']:
                    long_stationary += 1
                elif duration > 0:
                    short_stationary += 1
        
        frac_long = long_stationary / n if n > 0 else 0
        frac_short = short_stationary / n if n > 0 else 0
        
        return min(100.0, frac_long * 100.0 + frac_short * 40.0)

    def detect_clusters(self, detections):
        """Cluster vehicles spatially; return score and metadata."""
        n = len(detections)
        if n < self.config['min_cluster_size']:
            return {'num_clusters': 0, 'cluster_sizes': [], 'clustered_vehicles': 0, 'clustering_score': 0.0}

        positions = np.array([d['center'] for d in detections], dtype=float)

        if CLUSTERING_AVAILABLE:
            labels = DBSCAN(
                eps=self.config['proximity_threshold'],
                min_samples=self.config['min_cluster_size'],
            ).fit_predict(positions)
        else:
            labels = self._simple_cluster_labels(positions)

        unique_labels = [l for l in set(labels) if l != -1]
        cluster_sizes = [int(np.sum(labels == l)) for l in unique_labels]
        clustered = sum(cluster_sizes)

        if n > 0:
            # Bonus for large clusters
            avg_size = np.mean(cluster_sizes) if cluster_sizes else 0
            score = min(100.0, (clustered / n) * 70.0 + avg_size * 3.0)
        else:
            score = 0.0

        return {
            'num_clusters': len(unique_labels),
            'cluster_sizes': cluster_sizes,
            'clustered_vehicles': clustered,
            'clustering_score': round(score, 1),
        }

    def _simple_cluster_labels(self, positions):
        """Greedy O(n²) fallback clustering when sklearn unavailable."""
        n = len(positions)
        labels = np.full(n, -1, dtype=int)
        label_id = 0
        prox = self.config['proximity_threshold']
        min_size = self.config['min_cluster_size']

        for i in range(n):
            if labels[i] != -1:
                continue
            neighbours = [i]
            for j in range(n):
                if j == i:
                    continue
                if np.linalg.norm(positions[i] - positions[j]) <= prox:
                    neighbours.append(j)
            if len(neighbours) >= min_size:
                for idx in neighbours:
                    if labels[idx] == -1:
                        labels[idx] = label_id
                label_id += 1
        return labels

    def _score_speed_variance(self, detections):
        """
        IQR-trimmed speed variance score with None handling
        """
        # ✅ FIX: Filter out None speeds
        speeds = [d['speed'] for d in detections 
                  if d.get('speed') is not None and isinstance(d.get('speed'), (int, float))]
        
        if len(speeds) < 3:
            return 30.0  # Neutral
        
        arr = np.array(speeds, dtype=float)
        q25, q75 = np.percentile(arr, [25, 75])
        trimmed = arr[(arr >= q25) & (arr <= q75)]
        if len(trimmed) < 2:
            trimmed = arr
        
        mean_spd = float(np.mean(trimmed))
        var_spd = float(np.var(trimmed))
        
        # Low speed + low variance = stalled queue (high congestion)
        # High speed + high variance = merging traffic (moderate)
        if mean_spd < 8 and var_spd < 8:
            return 85.0   # Stalled
        elif mean_spd < 15:
            return 60.0
        elif mean_spd < 30:
            return 35.0
        else:
            return max(0.0, 20.0 - var_spd * 0.5)

    # ──────────────────────────────────────────────────────────────────────────
    # ✅ NEW: Incident detection with safe speed handling
    # ──────────────────────────────────────────────────────────────────────────

    def _check_incidents(self, detections, cluster_info):
        """
        Detect potential incidents (accidents, stalled vehicles)
        FIXED: Handle None speed values properly
        """
        incidents = []
        
        # Get thresholds from config
        incident_thresh_speed = self.config.get('incident_speed_threshold', 2.0)
        incident_thresh_dur = self.config.get('incident_duration_threshold', 30)
        incident_cluster_size = self.config.get('incident_cluster_size', 5)
        
        # Check individual stalled vehicles
        for det in detections:
            # ✅ FIX: Safely get speed with None check
            speed = det.get('speed')
            tid = det.get('track_id')
            dur = self.vehicle_stationary_sec.get(tid, 0) if tid else 0
            
            # Skip if speed is None (unknown) - use the safe comparator
            if not self._safe_speed_compare(speed, incident_thresh_speed, 'le'):
                continue
            
            # Now safe to check duration
            if dur >= incident_thresh_dur:
                incidents.append({
                    'track_id': tid,
                    'duration': dur,
                    'location': det.get('center'),
                    'type': 'stalled_vehicle',
                    'class_name': det.get('class_name', 'unknown'),
                    'speed': speed,
                })
                logger.debug(f"⚠️ Stalled vehicle detected: ID={tid}, duration={dur:.1f}s")
        
        # Check for large stationary clusters (possible accident)
        if cluster_info and cluster_info.get('num_clusters', 0) > 0:
            for i, size in enumerate(cluster_info.get('cluster_sizes', [])):
                if size >= incident_cluster_size:
                    incidents.append({
                        'cluster_index': i,
                        'size': size,
                        'type': 'stationary_cluster',
                        'location': 'unknown',  # Would need centroid calculation
                    })
                    logger.info(f"⚠️ Large stationary cluster detected: {size} vehicles")
        
        return incidents

    def _estimate_queue_length(self, detections):
        """
        Rough estimate of queue length in pixels with None handling
        """
        stationary = []
        for d in detections:
            tid = d.get('track_id')
            if tid and tid in self.vehicle_stationary_sec:
                if self.vehicle_stationary_sec[tid] > 1.0:
                    stationary.append(d)
        
        if len(stationary) < 2:
            return 0
        
        pts = np.array([d['center'] for d in stationary], dtype=float)
        span = pts.max(axis=0) - pts.min(axis=0)
        return int(max(span))

    # ──────────────────────────────────────────────────────────────────────────
    # Smoothing & level determination
    # ──────────────────────────────────────────────────────────────────────────

    def _score_to_level(self, score):
        thresholds = self.config['level_thresholds']
        for level in ['severe', 'heavy', 'moderate', 'light', 'none']:
            lo, hi = thresholds[level]
            if score >= lo:
                return level
        return 'none'

    def _apply_hysteresis(self, raw_level):
        """
        Asymmetric hysteresis:
        - Congestion can worsen quickly (upgrade_threshold frames)
        - Congestion clears slowly    (downgrade_threshold frames)
        """
        level_order = ['none', 'light', 'moderate', 'heavy', 'severe']
        current_idx = level_order.index(self.last_congestion_level)
        new_idx = level_order.index(raw_level)

        if new_idx > current_idx:
            # Upgrading (worsening)
            if raw_level == self._pending_level:
                self._upgrade_counter += 1
                self._downgrade_counter = 0
            else:
                self._pending_level = raw_level
                self._upgrade_counter = 1
            if self._upgrade_counter >= self.config['upgrade_threshold']:
                self.last_congestion_level = raw_level
                self._upgrade_counter = 0
        elif new_idx < current_idx:
            # Downgrading (clearing)
            if raw_level == self._pending_level:
                self._downgrade_counter += 1
                self._upgrade_counter = 0
            else:
                self._pending_level = raw_level
                self._downgrade_counter = 1
            if self._downgrade_counter >= self.config['downgrade_threshold']:
                self.last_congestion_level = raw_level
                self._downgrade_counter = 0
        else:
            # No change — reset both counters
            self._upgrade_counter = 0
            self._downgrade_counter = 0
            self._pending_level = raw_level

        return self.last_congestion_level

    def _compute_onset_rate(self, current_score):
        """EMA of score delta — positive = congestion building."""
        delta = current_score - self._score_prev
        self._onset_rate = 0.3 * delta + 0.7 * self._onset_rate
        self._score_prev = current_score
        return round(self._onset_rate, 2)

    def _ema_score(self, raw_score):
        """Exponential moving average over score history."""
        self.congestion_score_history.append(raw_score)
        n = len(self.congestion_score_history)
        if n == 0:
            return raw_score
        weights = np.exp(np.linspace(-2, 0, n))
        weights /= weights.sum()
        return float(np.dot(list(self.congestion_score_history), weights))

    # ──────────────────────────────────────────────────────────────────────────
    # Main entry point (FIXED with validation)
    # ──────────────────────────────────────────────────────────────────────────

    def detect_congestion(self, detections, fps):
        """
        Main congestion detection — FIXED: Handles None speeds properly
        
        Args:
            detections: list of vehicle detection dicts (must have 'track_id', 'center', optionally 'speed')
            fps: video frame rate
        
        Returns:
            dict with congestion info
        """
        # ✅ FIX: Validate detections first
        detections = self._validate_detections(detections)
        
        n = len(detections)
        current_time = self.frame_count / fps if fps > 0 else 0

        # Update stationary timers
        stationary_count = self._update_stationary_timers(detections, fps)

        # ── Factor scores ──────────────────────────────────────────────────
        w = self.config['weights']

        count_score = self._score_vehicle_count(n)
        density_score = self.calculate_density(detections)
        stat_score = self._score_stationary(detections, fps)
        cluster_info = self.detect_clusters(detections)
        cluster_score = cluster_info['clustering_score']
        speed_score = self._score_speed_variance(detections)

        raw_score = (
            count_score * w['vehicle_count'] +
            density_score * w['density'] +
            stat_score * w['stationary'] +
            cluster_score * w['clustering'] +
            speed_score * w['speed_variance']
        )
        raw_score = max(0.0, min(100.0, raw_score))

        # EMA smoothing
        smooth_score = self._ema_score(raw_score)
        onset_rate = self._compute_onset_rate(smooth_score)

        # Level determination with hysteresis
        raw_level = self._score_to_level(smooth_score)
        smoothed_lvl = self._apply_hysteresis(raw_level)

        # Derived metrics
        queue_len = self._estimate_queue_length(detections)
        
        # ✅ FIX: Check for incidents with safe speed handling
        incident_data = self._check_incidents(detections, cluster_info)

        # Track congestion event
        self._track_congestion_event(smoothed_lvl, current_time, n, stationary_count, smooth_score)

        # Stats
        self.stats['total_vehicles_processed'] += n
        self.stats['max_simultaneous_vehicles'] = max(self.stats['max_simultaneous_vehicles'], n)
        self.stats['total_frames'] += 1
        self.frame_count += 1

        # Count long stationary vehicles safely
        long_stationary = 0
        for d in detections:
            tid = d.get('track_id')
            if tid and tid in self.vehicle_stationary_sec:
                if self.vehicle_stationary_sec[tid] >= self.config['stationary_duration_seconds']:
                    long_stationary += 1

        return {
            # ── Original fields ───────────────────────────────────────────
            'level': smoothed_lvl,
            'total_vehicles': n,
            'stationary_vehicles': stationary_count,
            'congestion_score': int(smooth_score),
            'current_event': self.current_congestion if smoothed_lvl != 'none' else None,
            'timestamp': current_time,

            # ── Enhanced fields ────────────────────────────────────────────
            'raw_score': round(raw_score, 1),
            'smooth_score': round(smooth_score, 1),
            'onset_rate': onset_rate,
            'score_breakdown': {
                'vehicle_count': round(count_score, 1),
                'density': round(density_score, 1),
                'stationary': round(stat_score, 1),
                'clustering': round(cluster_score, 1),
                'speed_variance': round(speed_score, 1),
            },
            'clustering_info': cluster_info,
            'queue_length_px': queue_len,
            'long_stationary_vehicles': long_stationary,
            'incidents': incident_data,  # ✅ Added incidents data
        }

    def _track_congestion_event(self, level, current_time, n_vehicles, stationary, score):
        if level != 'none':
            if self.current_congestion['level'] == 'none':
                self.current_congestion = {
                    'level': level,
                    'start_time': current_time,
                    'vehicles_count': n_vehicles,
                    'stationary_count': stationary,
                    'peak_score': score,
                }
            else:
                self.current_congestion['vehicles_count'] = max(self.current_congestion['vehicles_count'], n_vehicles)
                self.current_congestion['stationary_count'] = max(self.current_congestion['stationary_count'], stationary)
                self.current_congestion['level'] = level
                self.current_congestion['peak_score'] = max(self.current_congestion['peak_score'], score)
        else:
            if self.current_congestion['level'] != 'none':
                duration = current_time - (self.current_congestion['start_time'] or current_time)
                if duration >= self.config['min_congestion_duration']:
                    self.congestion_events.append({
                        'level': self.current_congestion['level'],
                        'start_time': self.current_congestion['start_time'],
                        'end_time': current_time,
                        'duration': duration,
                        'max_vehicles': self.current_congestion['vehicles_count'],
                        'max_stationary': self.current_congestion['stationary_count'],
                        'peak_score': self.current_congestion['peak_score'],
                    })
                self.current_congestion = self._empty_congestion()

    # ──────────────────────────────────────────────────────────────────────────
    # Summary (Django model compatible)
    # ──────────────────────────────────────────────────────────────────────────

    def get_congestion_summary(self):
        """Returns summary compatible with Django TrafficAnalysis model"""
        total_time = sum(e['duration'] for e in self.congestion_events)
        by_level = defaultdict(int)
        time_by_level = defaultdict(float)
        
        for e in self.congestion_events:
            by_level[e['level']] += 1
            time_by_level[e['level']] += e['duration']

        avg_dur = (total_time / len(self.congestion_events)) if self.congestion_events else 0.0

        return {
            'total_events': len(self.congestion_events),
            'total_congestion_time': total_time,
            'events_by_level': dict(by_level),
            'time_by_level': dict(time_by_level),
            'average_event_duration': avg_dur,
            'current_level': self.current_congestion['level'],
            'stats': self.stats,
        }