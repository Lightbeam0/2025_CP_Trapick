# ml/congestion_module.py
"""
ENHANCED Congestion Detection Module
Features:
- Spatial density analysis (vehicles per area)
- Vehicle clustering detection (DBSCAN)
- Temporal smoothing (prevent flickering)
- Multi-factor congestion scoring
- Improved stationary vehicle detection

REPLACES: Original simple congestion_module.py
"""

import numpy as np
from collections import defaultdict, deque
import time

# Check if scipy is available, fallback to simple clustering if not
try:
    from scipy.spatial.distance import cdist
    from sklearn.cluster import DBSCAN
    CLUSTERING_AVAILABLE = True
except ImportError:
    CLUSTERING_AVAILABLE = False
    print("⚠️  scipy/sklearn not available - using simplified clustering")


class CongestionModule:
    """
    Enhanced congestion detection module with spatial analysis and smoothing
    
    BACKWARD COMPATIBLE: Can be used as drop-in replacement
    """
    
    def __init__(self, config=None):
        self.config = config or self._default_config()
        self.reset_state()
        
        # Smoothing
        self.congestion_score_history = deque(maxlen=self.config['smoothing_window'])
        self.level_history = deque(maxlen=self.config['smoothing_window'])
        
        print("🚦 Enhanced Congestion Module initialized")
        if CLUSTERING_AVAILABLE:
            print("   ✓ DBSCAN clustering enabled")
        print(f"   ✓ Temporal smoothing: {self.config['smoothing_window']} frames")
    
    def _default_config(self):
        """Default configuration values"""
        return {
            # Basic thresholds
            'min_vehicles_for_congestion': 5,
            'stationary_threshold_seconds': 10,
            'stationary_speed_threshold': 5.0,  # km/h
            
            # Spatial analysis
            'density_threshold': 0.0001,  # vehicles per pixel²
            'proximity_threshold': 80,     # pixels for clustering
            'min_cluster_size': 3,
            
            # Smoothing
            'smoothing_window': 15,
            'level_change_threshold': 0.3,
            
            # Event tracking
            'min_congestion_duration': 30,  # seconds
            
            # Multi-factor weights
            'weights': {
                'vehicle_count': 0.25,
                'density': 0.25,
                'stationary': 0.20,
                'clustering': 0.20,
                'speed_variance': 0.10
            },
            
            # Congestion levels (backward compatible + new scoring)
            'congestion_levels': {
                'light': {'min_vehicles': 5, 'min_stationary': 2, 'min_score': 20},
                'moderate': {'min_vehicles': 8, 'min_stationary': 5, 'min_score': 40},
                'heavy': {'min_vehicles': 12, 'min_stationary': 8, 'min_score': 60},
                'severe': {'min_vehicles': 15, 'min_stationary': 10, 'min_score': 80}
            }
        }
    
    def reset_state(self):
        """Reset congestion tracking state"""
        self.vehicle_positions = {}
        self.vehicle_stationary_time = defaultdict(float)
        self.vehicle_speeds = {}
        self.vehicle_last_update = {}
        
        self.congestion_events = []
        self.current_congestion = {
            'level': 'none',
            'start_time': None,
            'vehicles_count': 0,
            'stationary_count': 0
        }
        
        self.frame_count = 0
        self.last_update_time = time.time()
        self.last_congestion_level = 'none'
        self.level_transition_counter = 0
        
        # Statistics
        self.stats = {
            'total_vehicles_processed': 0,
            'max_simultaneous_vehicles': 0,
            'max_density': 0.0,
            'max_clustering_score': 0.0
        }
    
    def calculate_density(self, detections, roi_area=None):
        """
        Calculate vehicle density (vehicles per unit area)
        
        Args:
            detections: List of vehicle detections
            roi_area: Area in pixels² (if None, calculated from detections)
            
        Returns:
            Density score (0-100)
        """
        if len(detections) < 2:
            return 0.0
        
        # Get all vehicle centers
        positions = np.array([det['center'] for det in detections])
        
        # Calculate bounding area if not provided
        if roi_area is None:
            x_min, y_min = positions.min(axis=0)
            x_max, y_max = positions.max(axis=0)
            area = max((x_max - x_min) * (y_max - y_min), 1)
        else:
            area = roi_area
        
        # Density = vehicles / area
        density = len(detections) / area
        
        # Normalize to 0-100
        density_score = min((density / self.config['density_threshold']) * 100, 100)
        
        return density_score
    
    def detect_clusters_simple(self, detections):
        """
        Simple clustering without sklearn (fallback)
        Groups vehicles within proximity_threshold distance
        """
        if len(detections) < self.config['min_cluster_size']:
            return {
                'num_clusters': 0,
                'cluster_sizes': [],
                'clustered_vehicles': 0,
                'clustering_score': 0.0
            }
        
        positions = np.array([det['center'] for det in detections])
        proximity = self.config['proximity_threshold']
        
        # Simple greedy clustering
        visited = set()
        clusters = []
        
        for i in range(len(positions)):
            if i in visited:
                continue
            
            cluster = [i]
            visited.add(i)
            
            # Find all nearby vehicles
            for j in range(i + 1, len(positions)):
                if j in visited:
                    continue
                
                # Check distance to any vehicle in cluster
                for k in cluster:
                    dist = np.sqrt((positions[j][0] - positions[k][0])**2 + 
                                 (positions[j][1] - positions[k][1])**2)
                    if dist < proximity:
                        cluster.append(j)
                        visited.add(j)
                        break
            
            if len(cluster) >= self.config['min_cluster_size']:
                clusters.append(cluster)
        
        # Calculate statistics
        cluster_sizes = [len(c) for c in clusters]
        clustered_count = sum(cluster_sizes)
        
        if len(detections) > 0:
            clustering_percentage = (clustered_count / len(detections)) * 100
            avg_cluster_size = np.mean(cluster_sizes) if cluster_sizes else 0
            size_bonus = min(avg_cluster_size * 5, 30)
            clustering_score = min(clustering_percentage + size_bonus, 100)
        else:
            clustering_score = 0.0
        
        return {
            'num_clusters': len(clusters),
            'cluster_sizes': cluster_sizes,
            'clustered_vehicles': clustered_count,
            'clustering_score': clustering_score
        }
    
    def detect_clusters(self, detections):
        """
        Detect clusters of vehicles using DBSCAN or fallback method
        
        Args:
            detections: List of vehicle detections
            
        Returns:
            Dictionary with clustering info
        """
        if not CLUSTERING_AVAILABLE:
            return self.detect_clusters_simple(detections)
        
        if len(detections) < self.config['min_cluster_size']:
            return {
                'num_clusters': 0,
                'cluster_sizes': [],
                'clustered_vehicles': 0,
                'clustering_score': 0.0
            }
        
        # Extract positions
        positions = np.array([det['center'] for det in detections])
        
        # DBSCAN clustering
        clustering = DBSCAN(
            eps=self.config['proximity_threshold'],
            min_samples=self.config['min_cluster_size']
        ).fit(positions)
        
        labels = clustering.labels_
        
        # Count clusters (excluding noise labeled as -1)
        num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        
        # Get cluster sizes
        cluster_sizes = []
        clustered_count = 0
        for label in set(labels):
            if label != -1:
                size = np.sum(labels == label)
                cluster_sizes.append(size)
                clustered_count += size
        
        # Calculate clustering score
        if len(detections) > 0:
            clustering_percentage = (clustered_count / len(detections)) * 100
            avg_cluster_size = np.mean(cluster_sizes) if cluster_sizes else 0
            size_bonus = min(avg_cluster_size * 5, 30)
            clustering_score = min(clustering_percentage + size_bonus, 100)
        else:
            clustering_score = 0.0
        
        return {
            'num_clusters': num_clusters,
            'cluster_sizes': cluster_sizes,
            'clustered_vehicles': clustered_count,
            'clustering_score': clustering_score
        }
    
    def calculate_speed_variance(self, detections):
        """
        Calculate variance in vehicle speeds
        Low variance + low speeds = congestion
        """
        speeds = []
        for det in detections:
            speed = det.get('speed')
            if speed is not None:
                speeds.append(speed)
        
        if len(speeds) < 2:
            return 50.0
        
        variance = np.var(speeds)
        mean_speed = np.mean(speeds)
        
        # Low variance + low mean = congestion
        if mean_speed < 10 and variance < 5:
            return 100.0  # High congestion indicator (inverted later)
        elif mean_speed > 30 and variance > 20:
            return 0.0  # Free flow
        else:
            normalized = min((variance / 50) * 100, 100)
            return normalized
    
    def update_vehicle_positions(self, detections, fps):
        """Update vehicle positions and stationary times"""
        current_time = self.frame_count / fps if fps > 0 else time.time()
        
        new_positions = {}
        stationary_count = 0
        
        for det in detections:
            track_id = det['track_id']
            center = det['center']
            speed = det.get('speed')
            
            # Update position tracking
            if track_id in self.vehicle_positions:
                prev_pos = self.vehicle_positions[track_id]
                distance = np.sqrt((center[0] - prev_pos[0])**2 + 
                                 (center[1] - prev_pos[1])**2)
                
                # Check if stationary (< 5 pixels movement)
                if distance < 5:
                    self.vehicle_stationary_time[track_id] += 1/fps
                else:
                    self.vehicle_stationary_time[track_id] = 0
            else:
                self.vehicle_stationary_time[track_id] = 0
            
            # Count long-term stationary
            if self.vehicle_stationary_time[track_id] >= self.config['stationary_threshold_seconds']:
                stationary_count += 1
            
            new_positions[track_id] = center
            
            if speed is not None:
                self.vehicle_speeds[track_id] = speed
            
            self.vehicle_last_update[track_id] = current_time
        
        self.vehicle_positions = new_positions
        
        # Clean up old tracks
        tracks_to_remove = []
        for track_id, last_time in self.vehicle_last_update.items():
            if current_time - last_time > 5.0:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            self.vehicle_positions.pop(track_id, None)
            self.vehicle_stationary_time.pop(track_id, None)
            self.vehicle_speeds.pop(track_id, None)
            self.vehicle_last_update.pop(track_id, None)
        
        return stationary_count
    
    def calculate_multi_factor_score(self, detections, roi_area=None):
        """
        Calculate comprehensive congestion score using multiple factors
        """
        if len(detections) == 0:
            return {
                'total_score': 0,
                'factors': {},
                'normalized_score': 0,
                'cluster_info': {}
            }
        
        weights = self.config['weights']
        factors = {}
        
        # 1. Vehicle count score
        vehicle_count_score = min((len(detections) / 20) * 100, 100)
        factors['vehicle_count'] = vehicle_count_score
        
        # 2. Density score
        density_score = self.calculate_density(detections, roi_area)
        factors['density'] = density_score
        
        # 3. Stationary vehicles score
        stationary_count = sum(1 for tid, stime in self.vehicle_stationary_time.items()
                              if stime >= self.config['stationary_threshold_seconds'])
        stationary_score = (stationary_count / len(detections)) * 100 if detections else 0
        factors['stationary'] = stationary_score
        
        # 4. Clustering score
        cluster_info = self.detect_clusters(detections)
        factors['clustering'] = cluster_info['clustering_score']
        
        # 5. Speed variance score (inverted)
        speed_var = self.calculate_speed_variance(detections)
        speed_score = 100 - speed_var
        factors['speed_variance'] = speed_score
        
        # Calculate weighted total
        total_score = sum(factors[key] * weights[key] for key in weights.keys())
        normalized_score = min(max(total_score, 0), 100)
        
        return {
            'total_score': total_score,
            'factors': factors,
            'normalized_score': normalized_score,
            'cluster_info': cluster_info
        }
    
    def smooth_congestion_level(self, current_score):
        """
        Apply temporal smoothing to prevent level flickering
        """
        self.congestion_score_history.append(current_score)
        
        # Exponential moving average
        if len(self.congestion_score_history) > 0:
            weights = np.exp(np.linspace(-1, 0, len(self.congestion_score_history)))
            weights /= weights.sum()
            smoothed_score = sum(score * weight 
                               for score, weight in zip(self.congestion_score_history, weights))
        else:
            smoothed_score = current_score
        
        # Determine level from smoothed score
        if smoothed_score < 20:
            new_level = 'none'
        elif smoothed_score < 40:
            new_level = 'light'
        elif smoothed_score < 60:
            new_level = 'moderate'
        elif smoothed_score < 80:
            new_level = 'heavy'
        else:
            new_level = 'severe'
        
        # Hysteresis: prevent rapid level changes
        if new_level != self.last_congestion_level:
            self.level_transition_counter += 1
            threshold_frames = int(self.config['smoothing_window'] * self.config['level_change_threshold'])
            
            if self.level_transition_counter < threshold_frames:
                return self.last_congestion_level
            else:
                self.level_transition_counter = 0
                self.last_congestion_level = new_level
                return new_level
        else:
            self.level_transition_counter = 0
            return new_level
    
    def detect_congestion(self, detections, fps):
        """
        Main congestion detection method
        
        BACKWARD COMPATIBLE with original API
        
        Args:
            detections: List of vehicle detections
            fps: Video frame rate
            
        Returns:
            Dictionary with congestion information
        """
        total_vehicles = len(detections)
        
        # Update tracking
        stationary_count = self.update_vehicle_positions(detections, fps)
        
        # Calculate multi-factor score
        score_breakdown = self.calculate_multi_factor_score(detections)
        
        # Apply smoothing
        smoothed_level = self.smooth_congestion_level(score_breakdown['normalized_score'])
        
        # Update statistics
        self.stats['total_vehicles_processed'] += total_vehicles
        self.stats['max_simultaneous_vehicles'] = max(
            self.stats['max_simultaneous_vehicles'], 
            total_vehicles
        )
        if score_breakdown['factors'].get('density', 0) > self.stats['max_density']:
            self.stats['max_density'] = score_breakdown['factors']['density']
        
        # Calculate congestion score (0-100)
        congestion_score = int(score_breakdown['normalized_score'])
        
        # Track events
        current_time = self.frame_count / fps if fps > 0 else 0
        self._track_congestion_event(smoothed_level, current_time, total_vehicles, 
                                     stationary_count, score_breakdown)
        
        self.frame_count += 1
        
        # Return result (backward compatible + enhanced)
        return {
            'level': smoothed_level,
            'total_vehicles': total_vehicles,
            'stationary_vehicles': stationary_count,
            'congestion_score': congestion_score,
            'current_event': self.current_congestion if smoothed_level != 'none' else None,
            
            # Enhanced fields
            'score': score_breakdown['normalized_score'],
            'score_breakdown': score_breakdown['factors'],
            'clustering_info': score_breakdown.get('cluster_info', {}),
            'timestamp': current_time
        }
    
    def _track_congestion_event(self, level, current_time, total_vehicles, 
                                stationary_count, score_breakdown):
        """Track congestion events over time"""
        if level != 'none':
            if self.current_congestion['level'] == 'none':
                # Start new event
                self.current_congestion = {
                    'level': level,
                    'start_time': current_time,
                    'vehicles_count': total_vehicles,
                    'stationary_count': stationary_count,
                    'peak_score': score_breakdown['normalized_score']
                }
            else:
                # Update existing event
                self.current_congestion['vehicles_count'] = max(
                    self.current_congestion['vehicles_count'], total_vehicles
                )
                self.current_congestion['stationary_count'] = max(
                    self.current_congestion['stationary_count'], stationary_count
                )
                self.current_congestion['level'] = level
                self.current_congestion['peak_score'] = max(
                    self.current_congestion.get('peak_score', 0),
                    score_breakdown['normalized_score']
                )
        else:
            if self.current_congestion['level'] != 'none':
                duration = current_time - self.current_congestion['start_time']
                
                if duration >= self.config['min_congestion_duration']:
                    event = {
                        'level': self.current_congestion['level'],
                        'start_time': self.current_congestion['start_time'],
                        'end_time': current_time,
                        'duration': duration,
                        'max_vehicles': self.current_congestion['vehicles_count'],
                        'max_stationary': self.current_congestion['stationary_count'],
                        'peak_score': self.current_congestion.get('peak_score', 0)
                    }
                    self.congestion_events.append(event)
                
                self.current_congestion = {
                    'level': 'none',
                    'start_time': None,
                    'vehicles_count': 0,
                    'stationary_count': 0
                }
    
    def get_congestion_summary(self):
        """Get summary of all congestion events"""
        total_congestion_time = sum(event['duration'] for event in self.congestion_events)
        
        summary = {
            'total_events': len(self.congestion_events),
            'total_congestion_time': total_congestion_time,
            'events_by_level': defaultdict(int),
            'average_event_duration': 0,
            'current_level': self.current_congestion['level']
        }
        
        if self.congestion_events:
            for event in self.congestion_events:
                summary['events_by_level'][event['level']] += 1
            
            summary['average_event_duration'] = total_congestion_time / len(self.congestion_events)
        
        return summary