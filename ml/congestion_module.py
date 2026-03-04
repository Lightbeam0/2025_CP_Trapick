# ml/congestion_module.py
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
    """

    def __init__(self, config=None):
        self.config = {**self._default_config(), **(config or {})}

        # FIX-CM1: Initialize _enhanced_cache BEFORE reset_state() so that
        #          reset_state()'s call to self._enhanced_cache.clear() succeeds.
        self._enhanced_cache = {}

        self.reset_state()

        # Score history for smoothing and trend detection
        self.congestion_score_history = deque(maxlen=self.config['smoothing_window'])
        self.level_history = deque(maxlen=self.config['smoothing_window'])

        # Feature-level toggle for backward compatibility
        self._feature_level = 'basic'  # 'basic' or 'enhanced'

        # FIX-CM2: Separate weather multiplier — never mutates config thresholds
        self._weather_threshold_multiplier = 1.0

        logger.info("🚦 Congestion Module v2.3 initialised")
        logger.info(f"   Clustering: {'DBSCAN' if CLUSTERING_AVAILABLE else 'simple greedy'}")
        logger.info(f"   Smoothing window: {self.config['smoothing_window']} frames")
        logger.info(f"   Feature level: {self._feature_level.upper()}")

    # ──────────────────────────────────────────────────────────────────────────
    # Compatibility layer methods
    # ──────────────────────────────────────────────────────────────────────────

    def enable_enhanced_features(self, enabled=True):
        self._feature_level = 'enhanced' if enabled else 'basic'
        if enabled:
            logger.info("🚦 Congestion Module: ENHANCED mode enabled")
        else:
            logger.info("🚦 Congestion Module: BASIC mode (backward compatible)")
        return self

    def get_enhanced_results(self):
        if self._feature_level != 'enhanced' or not self._enhanced_cache:
            return {}
        return {
            key: value for key, value in self._enhanced_cache.items()
            if key in [
                'flow_rate_vehicles_per_min',
                'density_vehicles_per_km',
                'queue_length_meters',
                'congestion_index',
                'congestion_level_enhanced',
                'travel_time_estimate_sec',
                'weather_factor',
                'incident_risk_score',
                'incident_warning',
                'anomaly_score',
            ]
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Config
    # ──────────────────────────────────────────────────────────────────────────

    def _default_config(self):
        return {
            'stationary_speed_threshold':   4.0,
            'stationary_pixel_threshold':   4,
            'stationary_duration_seconds':  8.0,
            'proximity_threshold':          75,
            'min_cluster_size':             3,
            'smoothing_window':             20,
            'upgrade_threshold':            3,
            'downgrade_threshold':          10,
            'weights': {
                'vehicle_count':  0.25,
                'density':        0.20,
                'stationary':     0.25,
                'clustering':     0.20,
                'speed_variance': 0.10,
            },
            'level_thresholds': {
                'none':     (0,  20),
                'light':    (20, 40),
                'moderate': (40, 60),
                'heavy':    (60, 80),
                'severe':   (80, 100),
            },
            'min_congestion_duration':       20,
            'incident_speed_threshold':       2.0,
            'incident_duration_threshold':   30,
            'incident_cluster_size':          5,
            'flow_calculation_window':       60,
            'congestion_index_thresholds': {
                'free_flow':  (0,   0.3),
                'stable':     (0.3, 0.5),
                'unstable':   (0.5, 0.7),
                'congested':  (0.7, 0.9),
                'gridlock':   (0.9, 1.0),
            },
            'avg_vehicle_length_m':          4.5,
            'queue_density_threshold':        0.7,
            'px_per_meter_estimate':         10,
            'anomaly_threshold':              3.0,
            'prediction_horizon':            30,
            'incident_risk_decay':            0.05,
            'incident_risk_increment':        0.1,
            'weather_adaptation_enabled':    False,
            'weather_light_threshold':       80,
            'rain_detection_enabled':        True,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # State management
    # ──────────────────────────────────────────────────────────────────────────

    def reset_state(self):
        self.vehicle_positions      = {}
        self.vehicle_stationary_sec = defaultdict(float)
        self.vehicle_speeds         = {}
        self.vehicle_last_frame     = {}

        self.congestion_events  = []
        self.current_congestion = self._empty_congestion()

        self.frame_count           = 0
        self.last_congestion_level = 'none'

        self._upgrade_counter   = 0
        self._downgrade_counter = 0
        self._pending_level     = 'none'

        self._score_prev = 0.0
        self._onset_rate = 0.0

        self.stats = {
            'total_vehicles_processed':  0,
            'max_simultaneous_vehicles': 0,
            'total_frames':              0,
        }

        # FIX-CM1: _enhanced_cache is guaranteed to exist before this runs
        self._enhanced_cache.clear()

        if hasattr(self, 'flow_history'):
            self.flow_history.clear()
        if hasattr(self, 'anomaly_detection_window'):
            self.anomaly_detection_window.clear()
        if hasattr(self, 'incident_risk_score'):
            self.incident_risk_score = 0.0
        if hasattr(self, 'weather_factor'):
            self.weather_factor = 1.0

        # FIX-CM2: Reset weather multiplier
        self._weather_threshold_multiplier = 1.0

    def _empty_congestion(self):
        return {
            'level':          'none',
            'start_time':     None,
            'vehicles_count': 0,
            'stationary_count': 0,
            'peak_score':     0.0,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Safety helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _safe_speed_compare(self, speed, threshold, operator='le'):
        if speed is None or not isinstance(speed, (int, float)) or math.isnan(speed):
            return False
        ops = {
            'le': lambda a, b: a <= b,
            'lt': lambda a, b: a < b,
            'ge': lambda a, b: a >= b,
            'gt': lambda a, b: a > b,
        }
        return ops.get(operator, ops['le'])(speed, threshold)

    def _validate_detections(self, detections):
        valid_detections = []
        for det in detections:
            if not isinstance(det, dict) or 'track_id' not in det:
                continue
            if ('center' not in det
                    or not isinstance(det['center'], (tuple, list))
                    or len(det['center']) != 2):
                continue
            if 'speed' in det:
                speed = det['speed']
                if speed is None or not isinstance(speed, (int, float)) or math.isnan(speed):
                    det['speed'] = None
            if 'class_name' not in det:
                class_id = det.get('class_id')
                mapping  = {1: 'car', 2: 'jeep', 3: 'motorcycle',
                             5: 'tricycle', 6: 'truck'}
                det['class_name'] = mapping.get(class_id, 'unknown')
            valid_detections.append(det)
        return valid_detections

    # ──────────────────────────────────────────────────────────────────────────
    # Factor calculations
    # ──────────────────────────────────────────────────────────────────────────

    def _score_vehicle_count(self, n):
        """
        FIX-CM6: Explicit 0.0 for n=0 prevents floating-point rounding
        from ever returning a tiny positive score on empty frames.
        """
        if n == 0:
            return 0.0
        return min(100.0, (1 - math.exp(-n / 10.0)) * 110)

    def calculate_density(self, detections, roi_area=None):
        """
        FIX-CM4: Guard against zero bounding-box area when all vehicles share
        the same pixel position (e.g. a single detection). Previously this
        caused a division-by-zero through the max(span[0]*span[1], 1.0) path
        only if span was exactly zero in both axes simultaneously; now we also
        handle the case where roi_area is explicitly provided but is zero.
        """
        n = len(detections)
        if n < 2:
            return 0.0
        positions = np.array([d['center'] for d in detections], dtype=float)
        if roi_area and roi_area > 0:
            area = roi_area
        else:
            span = positions.max(axis=0) - positions.min(axis=0)
            area = max(span[0] * span[1], 100.0)   # FIX-CM4: raise floor to 100 px²
        raw_density = n / area
        return min(100.0, raw_density / (1.0 / 5000.0) * 100.0)

    def _update_stationary_timers(self, detections, fps):
        dt       = 1.0 / fps if fps > 0 else 1.0 / 30.0
        seen_ids = set()

        for det in detections:
            tid   = det['track_id']
            cx, cy = det['center']
            speed  = det.get('speed')
            seen_ids.add(tid)

            is_stationary = False
            if speed is not None:
                is_stationary = speed < self.config['stationary_speed_threshold']
            elif tid in self.vehicle_positions:
                prev          = self.vehicle_positions[tid]
                is_stationary = (
                    math.hypot(cx - prev[0], cy - prev[1])
                    < self.config['stationary_pixel_threshold']
                )

            self.vehicle_stationary_sec[tid] = (
                self.vehicle_stationary_sec[tid] + dt if is_stationary else 0.0
            )
            self.vehicle_positions[tid]   = (cx, cy)
            self.vehicle_last_frame[tid]  = self.frame_count

        stationary_count = sum(
            1 for d in detections
            if d.get('track_id') in self.vehicle_stationary_sec
            and self.vehicle_stationary_sec[d['track_id']] > 0
        )

        for tid in list(self.vehicle_last_frame):
            if (tid not in seen_ids
                    and self.frame_count - self.vehicle_last_frame[tid] > fps * 5):
                self.vehicle_positions.pop(tid, None)
                self.vehicle_stationary_sec.pop(tid, None)
                self.vehicle_last_frame.pop(tid, None)

        return stationary_count

    def _score_stationary(self, detections, fps):
        if not detections:
            return 0.0
        n = len(detections)
        long_stationary = sum(
            1 for d in detections
            if d.get('track_id') in self.vehicle_stationary_sec
            and self.vehicle_stationary_sec[d['track_id']] >= self.config['stationary_duration_seconds']
        )
        short_stationary = sum(
            1 for d in detections
            if d.get('track_id') in self.vehicle_stationary_sec
            and 0 < self.vehicle_stationary_sec[d['track_id']] < self.config['stationary_duration_seconds']
        )
        frac_long  = long_stationary  / n if n > 0 else 0
        frac_short = short_stationary / n if n > 0 else 0
        return min(100.0, frac_long * 100.0 + frac_short * 40.0)

    def detect_clusters(self, detections):
        n = len(detections)
        if n < self.config['min_cluster_size']:
            return {
                'num_clusters': 0, 'cluster_sizes': [],
                'clustered_vehicles': 0, 'clustering_score': 0.0,
            }
        positions = np.array([d['center'] for d in detections], dtype=float)
        if CLUSTERING_AVAILABLE:
            labels = DBSCAN(
                eps=self.config['proximity_threshold'],
                min_samples=self.config['min_cluster_size']
            ).fit_predict(positions)
        else:
            labels = self._simple_cluster_labels(positions)
        unique_labels  = [l for l in set(labels) if l != -1]
        cluster_sizes  = [int(np.sum(labels == l)) for l in unique_labels]
        clustered      = sum(cluster_sizes)
        avg_size       = np.mean(cluster_sizes) if cluster_sizes else 0
        score = min(100.0, (clustered / n) * 70.0 + avg_size * 3.0) if n > 0 else 0.0
        return {
            'num_clusters':       len(unique_labels),
            'cluster_sizes':      cluster_sizes,
            'clustered_vehicles': clustered,
            'clustering_score':   round(score, 1),
        }

    def _simple_cluster_labels(self, positions):
        n        = len(positions)
        labels   = np.full(n, -1, dtype=int)
        label_id = 0
        prox     = self.config['proximity_threshold']
        min_size = self.config['min_cluster_size']
        for i in range(n):
            if labels[i] != -1:
                continue
            neighbours = [j for j in range(n)
                          if np.linalg.norm(positions[i] - positions[j]) <= prox]
            if len(neighbours) >= min_size:
                for idx in neighbours:
                    if labels[idx] == -1:
                        labels[idx] = label_id
                label_id += 1
        return labels

    def _score_speed_variance(self, detections):
        """
        FIX-CM3: Return 0.0 (not 30.0) when fewer than 3 speed samples exist.

        The original default of 30.0 injected a constant moderate-congestion
        signal even on completely empty or near-empty roads. Since this factor
        is weighted at only 0.10 in the composite score, returning 0.0 is safe
        for any traffic level above 'none' because the other four factors
        (vehicle_count, density, stationary, clustering) will dominate.
        """
        speeds = [
            d['speed'] for d in detections
            if d.get('speed') is not None and isinstance(d.get('speed'), (int, float))
        ]
        if len(speeds) < 3:
            return 0.0   # FIX-CM3: was 30.0

        arr          = np.array(speeds, dtype=float)
        q25, q75     = np.percentile(arr, [25, 75])
        trimmed      = arr[(arr >= q25) & (arr <= q75)]
        if len(trimmed) < 2:
            trimmed = arr
        mean_spd = float(np.mean(trimmed))
        var_spd  = float(np.var(trimmed))

        if   mean_spd < 8  and var_spd < 8:  return 85.0
        elif mean_spd < 15:                   return 60.0
        elif mean_spd < 30:                   return 35.0
        else:                                 return max(0.0, 20.0 - var_spd * 0.5)

    # ──────────────────────────────────────────────────────────────────────────
    # Enhanced metrics calculators
    # ──────────────────────────────────────────────────────────────────────────

    def _calculate_traffic_flow(self, detections, fps):
        if not detections or len(detections) < 2:
            return 0.0
        moving = sum(1 for d in detections
                     if self._safe_speed_compare(d.get('speed'), 5, 'gt'))
        if moving > 0:
            window_sec = self.config['flow_calculation_window']
            flow_rate  = moving * (60.0 / max(1, window_sec))
            return round(flow_rate, 1)
        return 0.0

    def _calculate_traffic_density(self, detections, roi_area=None):
        if not detections:
            return 0.0
        positions    = np.array([d['center'] for d in detections], dtype=float)
        span         = positions.max(axis=0) - positions.min(axis=0)
        road_length_m = np.sqrt(np.sum(span**2)) / self.config.get('px_per_meter_estimate', 10)
        if road_length_m > 0:
            density = (len(detections) / road_length_m) * 1000
            return round(min(density, 500), 1)
        return 0.0

    def _estimate_queue_length_meters(self, detections):
        stationary = [
            d for d in detections
            if d.get('track_id') in self.vehicle_stationary_sec
            and self.vehicle_stationary_sec[d['track_id']] > 1.0
        ]
        if len(stationary) < 2:
            return 0.0
        positions = np.array([d['center'] for d in stationary], dtype=float)
        if len(positions) > 1:
            distances    = np.linalg.norm(positions[:, np.newaxis] - positions, axis=2)
            max_dist_px  = np.max(distances)
            px_per_m     = self.config.get('px_per_meter_estimate', 10)
            return round(max_dist_px / px_per_m, 1)
        return 0.0

    def _calculate_congestion_index(self, score, flow_rate, density):
        score_idx   = score / 100.0
        flow_idx    = min(1.0, flow_rate / 100.0)
        density_idx = min(1.0, density / 200.0)
        weights     = {'score': 0.4, 'flow': 0.3, 'density': 0.3}
        index       = (
            score_idx * weights['score']
            + (1 - flow_idx) * weights['flow']
            + density_idx * weights['density']
        )
        return round(min(1.0, max(0.0, index)), 2)

    def _index_to_level(self, index):
        thresholds = self.config['congestion_index_thresholds']
        for level, (low, high) in thresholds.items():
            if low <= index < high:
                return level
        return 'unknown'

    def _detect_anomalies(self, detections, fps):
        if len(detections) < 3:
            return 0.0
        speeds = [
            d['speed'] for d in detections
            if d.get('speed') is not None and isinstance(d.get('speed'), (int, float))
        ]
        if not speeds:
            return 0.0
        avg_speed     = np.mean(speeds)
        speed_std     = np.std(speeds) + 0.1
        vehicle_count = len(detections)

        if not hasattr(self, 'anomaly_detection_window'):
            self.anomaly_detection_window = deque(maxlen=600)

        self.anomaly_detection_window.append({
            'avg_speed': avg_speed,
            'speed_std': speed_std,
            'count':     vehicle_count,
        })

        if len(self.anomaly_detection_window) < 30:
            return 0.0

        hist       = list(self.anomaly_detection_window)
        mean_speed = np.mean([h['avg_speed'] for h in hist])
        std_speed  = np.std([h['avg_speed'] for h in hist]) + 0.1
        mean_count = np.mean([h['count'] for h in hist])
        std_count  = np.std([h['count'] for h in hist]) + 0.1

        speed_anomaly = abs(avg_speed - mean_speed) / std_speed
        count_anomaly = abs(vehicle_count - mean_count) / std_count

        if avg_speed < mean_speed * 0.5 and vehicle_count > mean_count * 1.5:
            return round(speed_anomaly + count_anomaly, 2)
        return round(max(speed_anomaly, count_anomaly), 2)

    def _estimate_travel_time(self, queue_length_m, flow_rate):
        if flow_rate == 0 or queue_length_m == 0:
            return None
        free_flow_speed   = 50
        congestion_factor = getattr(self, '_current_congestion_index', 0.5)
        effective_speed   = max(5, free_flow_speed * (1 - congestion_factor))
        travel_time       = (queue_length_m / 1000) / (effective_speed / 3600)
        return round(travel_time, 1)

    def _apply_weather_adaptation(self, weather_info):
        """
        FIX-CM2: Weather adaptation now stores a multiplier separately instead
        of mutating self.config['level_thresholds'] in place.
        The multiplier is applied at evaluation time in _score_to_level.
        This prevents threshold values from compounding toward zero over time.
        """
        if not self.config.get('weather_adaptation_enabled', False) or not weather_info:
            self.weather_factor = 1.0
            self._weather_threshold_multiplier = 1.0
            return

        if (weather_info.get('is_night', False)
                or weather_info.get('brightness', 100) < self.config['weather_light_threshold']):
            self.weather_factor = 0.85
        elif (self.config.get('rain_detection_enabled')
              and weather_info.get('rain_intensity', 0) > 0):
            self.weather_factor = max(0.6, 1.0 - weather_info['rain_intensity'] * 0.4)
        else:
            self.weather_factor = 1.0

        # FIX-CM2: Store multiplier; DO NOT mutate config thresholds
        self._weather_threshold_multiplier = 0.9 if self.weather_factor < 0.8 else 1.0

    # ──────────────────────────────────────────────────────────────────────────
    # Basic fallback detection
    # ──────────────────────────────────────────────────────────────────────────

    def _basic_detect_congestion(self, detections, fps):
        n = len(detections)
        if   n > 15: level = 'severe'
        elif n > 10: level = 'heavy'
        elif n > 5:  level = 'moderate'
        elif n > 2:  level = 'light'
        else:        level = 'none'

        stationary_count = sum(
            1 for d in detections
            if d.get('is_stationary', False)
            or (d.get('speed') is not None and d['speed'] < 4.0)
        )

        return {
            'level':                n and level or 'none',
            'total_vehicles':       n,
            'stationary_vehicles':  stationary_count,
            'congestion_score':     min(100, n * 6),
            'timestamp':            self.frame_count / fps if fps > 0 else 0,
            'raw_score':            min(100, n * 6),
            'smooth_score':         min(100, n * 6),
            'onset_rate':           0.0,
            'score_breakdown':      {'vehicle_count': min(100, n * 6)},
            'clustering_info':      {'num_clusters': 0},
            'queue_length_px':      0,
            'long_stationary_vehicles': stationary_count,
            'incidents':            [],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Smoothing & level determination
    # FIX-CM2: _score_to_level now applies _weather_threshold_multiplier at
    #          evaluation time rather than permanently lowering stored thresholds.
    # ──────────────────────────────────────────────────────────────────────────

    def _score_to_level(self, score):
        thresholds = self.config['level_thresholds']
        # FIX-CM2: Apply weather multiplier at read time (non-destructive)
        multiplier = getattr(self, '_weather_threshold_multiplier', 1.0)
        for level in ['severe', 'heavy', 'moderate', 'light', 'none']:
            lo, hi     = thresholds[level]
            effective_lo = lo * multiplier
            if score >= effective_lo:
                return level
        return 'none'

    def _apply_hysteresis(self, raw_level):
        level_order  = ['none', 'light', 'moderate', 'heavy', 'severe']
        current_idx  = level_order.index(self.last_congestion_level)
        new_idx      = level_order.index(raw_level)

        if new_idx > current_idx:
            if raw_level == self._pending_level:
                self._upgrade_counter   += 1
                self._downgrade_counter  = 0
            else:
                self._pending_level    = raw_level
                self._upgrade_counter  = 1
            if self._upgrade_counter >= self.config['upgrade_threshold']:
                self.last_congestion_level = raw_level
                self._upgrade_counter      = 0
        elif new_idx < current_idx:
            if raw_level == self._pending_level:
                self._downgrade_counter += 1
                self._upgrade_counter    = 0
            else:
                self._pending_level      = raw_level
                self._downgrade_counter  = 1
            if self._downgrade_counter >= self.config['downgrade_threshold']:
                self.last_congestion_level = raw_level
                self._downgrade_counter    = 0
        else:
            self._upgrade_counter   = 0
            self._downgrade_counter = 0
            self._pending_level     = raw_level
        return self.last_congestion_level

    def _compute_onset_rate(self, current_score):
        delta        = current_score - self._score_prev
        self._onset_rate = 0.3 * delta + 0.7 * self._onset_rate
        self._score_prev = current_score
        return round(self._onset_rate, 2)

    def _ema_score(self, raw_score):
        self.congestion_score_history.append(raw_score)
        n = len(self.congestion_score_history)
        if n == 0:
            return raw_score
        weights = np.exp(np.linspace(-2, 0, n))
        weights /= weights.sum()
        return float(np.dot(list(self.congestion_score_history), weights))

    # ──────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────────────────────

    def detect_congestion(self, detections, fps, weather_info=None, roi_area=None):
        """
        FIX-CM5: Accept optional roi_area so that calculate_density can use
        the real scene area rather than the bounding-box of detections alone.
        BaseDirectionalDetector already computes self.roi_area and can pass it
        through as a keyword argument.
        """
        try:
            detections   = self._validate_detections(detections)
            n            = len(detections)
            current_time = self.frame_count / fps if fps > 0 else 0

            stationary_count = self._update_stationary_timers(detections, fps)

            w            = self.config['weights']
            count_score  = self._score_vehicle_count(n)
            # FIX-CM5: pass roi_area when available
            density_score = self.calculate_density(detections, roi_area=roi_area)
            stat_score   = self._score_stationary(detections, fps)
            cluster_info = self.detect_clusters(detections)
            cluster_score = cluster_info['clustering_score']
            speed_score  = self._score_speed_variance(detections)

            raw_score = (
                count_score  * w['vehicle_count']
                + density_score * w['density']
                + stat_score  * w['stationary']
                + cluster_score * w['clustering']
                + speed_score * w['speed_variance']
            )
            raw_score = max(0.0, min(100.0, raw_score))

            smooth_score = self._ema_score(raw_score)
            onset_rate   = self._compute_onset_rate(smooth_score)

            raw_level   = self._score_to_level(smooth_score)
            smoothed_lvl = self._apply_hysteresis(raw_level)

            queue_len      = self._estimate_queue_length(detections)
            incident_data  = self._check_incidents(detections, cluster_info)

            self._track_congestion_event(smoothed_lvl, current_time, n,
                                         stationary_count, smooth_score)

            self.stats['total_vehicles_processed']  += n
            self.stats['max_simultaneous_vehicles']  = max(
                self.stats['max_simultaneous_vehicles'], n
            )
            self.stats['total_frames'] += 1
            self.frame_count           += 1

            long_stationary = sum(
                1 for d in detections
                if d.get('track_id') in self.vehicle_stationary_sec
                and self.vehicle_stationary_sec[d['track_id']] >= self.config['stationary_duration_seconds']
            )

            base_result = {
                'level':                smoothed_lvl,
                'total_vehicles':       n,
                'stationary_vehicles':  stationary_count,
                'congestion_score':     int(smooth_score),
                'current_event':        self.current_congestion if smoothed_lvl != 'none' else None,
                'timestamp':            current_time,
                'raw_score':            round(raw_score, 1),
                'smooth_score':         round(smooth_score, 1),
                'onset_rate':           onset_rate,
                'score_breakdown': {
                    'vehicle_count': round(count_score,   1),
                    'density':       round(density_score, 1),
                    'stationary':    round(stat_score,    1),
                    'clustering':    round(cluster_score, 1),
                    'speed_variance': round(speed_score,  1),
                },
                'clustering_info':          cluster_info,
                'queue_length_px':          queue_len,
                'long_stationary_vehicles': long_stationary,
                'incidents':                incident_data,
            }

            if self._feature_level == 'enhanced':
                try:
                    if weather_info and self.config.get('weather_adaptation_enabled'):
                        self._apply_weather_adaptation(weather_info)

                    flow_rate        = self._calculate_traffic_flow(detections, fps)
                    density          = self._calculate_traffic_density(detections, roi_area)
                    queue_length_m   = self._estimate_queue_length_meters(detections)
                    congestion_index = self._calculate_congestion_index(
                        smooth_score, flow_rate, density
                    )

                    self._current_congestion_index = congestion_index

                    anomaly_score = self._detect_anomalies(detections, fps)
                    if not hasattr(self, 'incident_risk_score'):
                        self.incident_risk_score = 0.0

                    if anomaly_score > self.config['anomaly_threshold']:
                        self.incident_risk_score = min(
                            1.0,
                            self.incident_risk_score + self.config['incident_risk_increment']
                        )
                    else:
                        self.incident_risk_score = max(
                            0.0,
                            self.incident_risk_score - self.config['incident_risk_decay']
                        )

                    incident_warning = None
                    if anomaly_score > self.config['anomaly_threshold']:
                        incident_warning = {
                            'risk_level':          'high' if self.incident_risk_score > 0.7 else 'medium',
                            'anomaly_score':       round(anomaly_score, 2),
                            'recommended_action':  'reduce_speed' if self.incident_risk_score > 0.5 else 'caution',
                        }

                    travel_time = self._estimate_travel_time(queue_length_m, flow_rate)

                    self._enhanced_cache = {
                        'flow_rate_vehicles_per_min':  flow_rate,
                        'density_vehicles_per_km':     density,
                        'queue_length_meters':         queue_length_m,
                        'congestion_index':            congestion_index,
                        'congestion_level_enhanced':   self._index_to_level(congestion_index),
                        'travel_time_estimate_sec':    travel_time,
                        'weather_factor':              getattr(self, 'weather_factor', 1.0),
                        'incident_risk_score':         round(self.incident_risk_score, 2),
                        'incident_warning':            incident_warning,
                        'anomaly_score':               round(anomaly_score, 2),
                    }

                    for key, value in self._enhanced_cache.items():
                        if key not in base_result:
                            base_result[key] = value

                    if not hasattr(self, 'flow_history'):
                        self.flow_history = deque(maxlen=300)
                    self.flow_history.append({
                        'timestamp':        current_time,
                        'flow_rate':        flow_rate,
                        'congestion_index': congestion_index,
                        'level':            smoothed_lvl,
                    })

                except Exception as e:
                    logger.warning(
                        f"Enhanced metrics computation failed: {e}. Returning base result only."
                    )

            return base_result

        except Exception as e:
            logger.error(f"Congestion detection error: {e}. Falling back to basic detection.")
            return self._basic_detect_congestion(detections, fps)

    def _check_incidents(self, detections, cluster_info):
        incidents = []
        cfg       = self.config

        for det in detections:
            speed = det.get('speed')
            tid   = det.get('track_id')
            dur   = self.vehicle_stationary_sec.get(tid, 0) if tid else 0

            if not self._safe_speed_compare(speed, cfg['incident_speed_threshold'], 'le'):
                continue
            if dur >= cfg['incident_duration_threshold']:
                incidents.append({
                    'track_id':   tid,
                    'duration':   dur,
                    'location':   det.get('center'),
                    'type':       'stalled_vehicle',
                    'class_name': det.get('class_name', 'unknown'),
                    'speed':      speed,
                    'severity':   'high' if dur > 60 else 'medium',
                })

        if cluster_info and cluster_info.get('num_clusters', 0) > 0:
            for i, size in enumerate(cluster_info.get('cluster_sizes', [])):
                if size >= cfg['incident_cluster_size']:
                    incidents.append({
                        'cluster_index': i,
                        'size':          size,
                        'type':          'stationary_cluster',
                        'location':      'unknown',
                        'severity':      'high' if size > 8 else 'medium',
                    })

        return incidents

    def _estimate_queue_length(self, detections):
        stationary = [
            d for d in detections
            if d.get('track_id') in self.vehicle_stationary_sec
            and self.vehicle_stationary_sec[d['track_id']] > 1.0
        ]
        if len(stationary) < 2:
            return 0
        pts  = np.array([d['center'] for d in stationary], dtype=float)
        span = pts.max(axis=0) - pts.min(axis=0)
        return int(max(span))

    def _track_congestion_event(self, level, current_time, n_vehicles, stationary, score):
        if level != 'none':
            if self.current_congestion['level'] == 'none':
                self.current_congestion = {
                    'level':           level,
                    'start_time':      current_time,
                    'vehicles_count':  n_vehicles,
                    'stationary_count': stationary,
                    'peak_score':      score,
                }
            else:
                self.current_congestion['vehicles_count']  = max(
                    self.current_congestion['vehicles_count'], n_vehicles
                )
                self.current_congestion['stationary_count'] = max(
                    self.current_congestion['stationary_count'], stationary
                )
                self.current_congestion['level']      = level
                self.current_congestion['peak_score'] = max(
                    self.current_congestion['peak_score'], score
                )
        else:
            if self.current_congestion['level'] != 'none':
                duration = current_time - (self.current_congestion['start_time'] or current_time)
                if duration >= self.config['min_congestion_duration']:
                    self.congestion_events.append({
                        'level':          self.current_congestion['level'],
                        'start_time':     self.current_congestion['start_time'],
                        'end_time':       current_time,
                        'duration':       duration,
                        'max_vehicles':   self.current_congestion['vehicles_count'],
                        'max_stationary': self.current_congestion['stationary_count'],
                        'peak_score':     self.current_congestion['peak_score'],
                    })
                self.current_congestion = self._empty_congestion()

    # ──────────────────────────────────────────────────────────────────────────
    # Summary & reporting
    # ──────────────────────────────────────────────────────────────────────────

    def get_congestion_summary(self):
        total_time    = sum(e['duration'] for e in self.congestion_events)
        by_level      = defaultdict(int)
        time_by_level = defaultdict(float)

        for e in self.congestion_events:
            by_level[e['level']]      += 1
            time_by_level[e['level']] += e['duration']

        avg_dur = (total_time / len(self.congestion_events)) if self.congestion_events else 0.0

        result = {
            'total_events':           len(self.congestion_events),
            'total_congestion_time':  total_time,
            'events_by_level':        dict(by_level),
            'time_by_level':          dict(time_by_level),
            'average_event_duration': avg_dur,
            'current_level':          self.current_congestion['level'],
            'stats':                  self.stats,
        }

        if self._feature_level == 'enhanced' and hasattr(self, '_current_congestion_index'):
            result['current_congestion_index'] = self._current_congestion_index
            result['incident_risk_score']       = getattr(self, 'incident_risk_score', 0.0)

        return result