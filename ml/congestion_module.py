# ml/congestion_module.py
import numpy as np
from collections import defaultdict, deque
import time

class CongestionModule:
    """
    Shared congestion detection module for all directional detectors
    Features:
    - Full-frame congestion detection
    - Based on vehicle count AND stationary time
    - Multiple congestion levels
    - Event tracking with timestamps
    """
    
    def __init__(self, config=None):
        self.config = config or {
            'min_vehicles_for_congestion': 5,
            'stationary_threshold_seconds': 10,
            'congestion_levels': {
                'light': {'min_vehicles': 5, 'min_stationary': 2},
                'moderate': {'min_vehicles': 8, 'min_stationary': 5},
                'heavy': {'min_vehicles': 12, 'min_stationary': 8},
                'severe': {'min_vehicles': 15, 'min_stationary': 10}
            },
            'min_congestion_duration': 30  # seconds
        }
        
        self.reset_state()
        
    def reset_state(self):
        """Reset congestion tracking state"""
        self.vehicle_positions = {}
        self.vehicle_stationary_time = defaultdict(float)
        self.congestion_events = []
        self.current_congestion = {
            'level': 'none',
            'start_time': None,
            'vehicles_count': 0,
            'stationary_count': 0
        }
        self.frame_count = 0
        self.last_update_time = time.time()
        
    def update_vehicle_positions(self, detections, fps):
        """Update vehicle positions and stationary times"""
        current_time = self.frame_count / fps if fps > 0 else time.time()
        
        # Reset positions for new frame
        new_positions = {}
        
        for det in detections:
            track_id = det['track_id']
            center = det['center']
            
            # Check if vehicle is stationary
            if track_id in self.vehicle_positions:
                prev_pos = self.vehicle_positions[track_id]
                distance = np.sqrt((center[0] - prev_pos[0])**2 + 
                                 (center[1] - prev_pos[1])**2)
                
                # If moved less than 5 pixels, consider stationary
                if distance < 5:
                    self.vehicle_stationary_time[track_id] += 1/fps
                else:
                    self.vehicle_stationary_time[track_id] = 0
            else:
                self.vehicle_stationary_time[track_id] = 0
                
            new_positions[track_id] = center
            
        self.vehicle_positions = new_positions
        self.frame_count += 1
        
        return current_time
        
    def detect_congestion(self, detections, fps):
        """
        Detect congestion level based on:
        1. Total vehicle count in frame
        2. Number of stationary vehicles
        3. Duration of stationary vehicles
        """
        current_time = self.update_vehicle_positions(detections, fps)
        
        total_vehicles = len(detections)
        
        # Count stationary vehicles (stationary for > threshold)
        stationary_vehicles = 0
        for track_id, stationary_time in self.vehicle_stationary_time.items():
            if stationary_time >= self.config['stationary_threshold_seconds']:
                stationary_vehicles += 1
        
        # Determine congestion level
        congestion_level = 'none'
        
        for level_name, criteria in self.config['congestion_levels'].items():
            if (total_vehicles >= criteria['min_vehicles'] and 
                stationary_vehicles >= criteria['min_stationary']):
                congestion_level = level_name
        
        # Track congestion events
        if congestion_level != 'none':
            if self.current_congestion['level'] == 'none':
                # New congestion event started
                self.current_congestion = {
                    'level': congestion_level,
                    'start_time': current_time,
                    'vehicles_count': total_vehicles,
                    'stationary_count': stationary_vehicles
                }
            else:
                # Update existing congestion
                self.current_congestion.update({
                    'level': congestion_level,
                    'vehicles_count': total_vehicles,
                    'stationary_count': stationary_vehicles
                })
        else:
            # Congestion ended
            if self.current_congestion['level'] != 'none':
                event_duration = current_time - self.current_congestion['start_time']
                
                if event_duration >= self.config['min_congestion_duration']:
                    congestion_event = {
                        'level': self.current_congestion['level'],
                        'start_time': self.current_congestion['start_time'],
                        'end_time': current_time,
                        'duration': event_duration,
                        'max_vehicles': self.current_congestion['vehicles_count'],
                        'max_stationary': self.current_congestion['stationary_count']
                    }
                    self.congestion_events.append(congestion_event)
                
                # Reset current congestion
                self.current_congestion = {
                    'level': 'none',
                    'start_time': None,
                    'vehicles_count': 0,
                    'stationary_count': 0
                }
        
        return {
            'level': congestion_level,
            'total_vehicles': total_vehicles,
            'stationary_vehicles': stationary_vehicles,
            'current_event': self.current_congestion if congestion_level != 'none' else None
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