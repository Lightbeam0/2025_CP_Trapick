# ml/base_detector.py
import cv2
import numpy as np
from collections import defaultdict, deque
import time
from datetime import datetime

class BaseDetector:
    """Base class with common functionality for all detectors"""
    
    def __init__(self):
        self.vehicle_classes = {}
        self.track_history = defaultdict(lambda: deque(maxlen=30))
    
    def analyze_video(self, video_path, progress_callback=None, save_output=False, roi_normalized=None, **kwargs):
        """
        Analyze a video file and return traffic analysis report.
        
        This is the main entry point that ALL detector subclasses must implement
        with this EXACT signature for compatibility with the Celery task system.
        
        Args:
            video_path (str): Path to the video file
            progress_callback (callable, optional): Progress update callback
                Should accept (progress_percent, total_frames, message_string)
            save_output (bool): Whether to save annotated video
            roi_normalized (list, optional): Normalized ROI coordinates [(x,y), ...]
                where x,y are in range [0, 1]. Some detectors may ignore this.
            **kwargs: Additional detector-specific parameters
            
        Returns:
            dict: Analysis report with structure:
                {
                    'summary': {
                        'total_vehicles_counted': int,
                        'vehicle_breakdown': dict,
                        'peak_traffic': int,
                        'average_traffic_density': float
                    },
                    'metadata': {
                        'processing_time': float,
                        'model_used': str,
                        ...
                    },
                    'metrics': {
                        'congestion_level': str,
                        'traffic_pattern': str,
                        ...
                    },
                    'output_video_path': str (optional, if save_output=True)
                }
                
        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement analyze_video() with this signature:\n"
            "def analyze_video(self, video_path, progress_callback=None, save_output=False, "
            "roi_normalized=None, **kwargs)"
        )
        
    def setup_enhanced_metrics(self):
        """Initialize data structures for enhanced metrics"""
        self.hourly_data = defaultdict(lambda: defaultdict(int))
        self.speed_data = defaultdict(list)
        self.detection_confidences = []
        self.frame_vehicle_counts = []
        
        # CRITICAL: Initialize tracking attributes used by calculate_speed
        if not hasattr(self, 'previous_positions'):
            self.previous_positions = {}
        if not hasattr(self, 'vehicle_timestamps'):
            self.vehicle_timestamps = defaultdict(list)
        
    def calculate_speed(self, track_id, current_position, current_frame, fps):
        """Calculate speed for a tracked vehicle"""
        if track_id in self.previous_positions:
            prev_frame, prev_position = self.previous_positions[track_id]
            
            # Only calculate if we have recent data (within 10 frames)
            if current_frame - prev_frame <= 10:
                # Calculate distance moved (pixels)
                distance_pixels = ((current_position[0] - prev_position[0])**2 + 
                                 (current_position[1] - prev_position[1])**2)**0.5
                
                # Time between detections in seconds
                time_seconds = (current_frame - prev_frame) / fps
                
                if time_seconds > 0:
                    # Convert to real-world speed (approximation)
                    # Calibration factor: adjust based on your camera setup
                    pixels_per_meter = 8.0  # You may need to calibrate this
                    distance_meters = distance_pixels / pixels_per_meter
                    speed_mps = distance_meters / time_seconds
                    speed_kph = speed_mps * 3.6  # Convert to km/h
                    
                    return speed_kph
        
        # Update position for next calculation
        self.previous_positions[track_id] = (current_frame, current_position)
        return None
    
    def update_hourly_data(self, current_counts, current_time_seconds):
        """Update hourly breakdown data"""
        current_hour = int(current_time_seconds // 3600)  # 0, 1, 2, etc.
        for vehicle_type, count in current_counts.items():
            self.hourly_data[current_hour][vehicle_type] += count
    
    def update_quality_metrics(self, detections, current_counts):
        """Update quality tracking metrics"""
        for detection in detections:
            self.detection_confidences.append(detection.get('confidence', 0.5))
        
        self.frame_vehicle_counts.append(sum(current_counts.values()))
    
    def calculate_traffic_flow_metrics(self, total_vehicles, video_duration, fps, frame_width):
        """Calculate professional traffic flow metrics"""
        metrics = {}
        
        # Traffic Flow Rate (vehicles per hour)
        video_duration_hours = video_duration / 3600 if video_duration > 0 else 0
        metrics['traffic_flow_rate'] = total_vehicles / video_duration_hours if video_duration_hours > 0 else 0
        
        # Density (vehicles per kilometer) - approximation
        # Assume visible road length is about 50 meters (adjust based on your camera)
        road_length_km = 0.05  # 50 meters in kilometers
        if self.frame_vehicle_counts:
            avg_vehicles_in_frame = np.mean(self.frame_vehicle_counts)
            metrics['density_vehicles_per_km'] = avg_vehicles_in_frame / road_length_km
        else:
            metrics['density_vehicles_per_km'] = 0
        
        # Average Gap (time between vehicles)
        if total_vehicles > 1 and video_duration > 0:
            metrics['average_gap_seconds'] = video_duration / total_vehicles
        else:
            metrics['average_gap_seconds'] = 0
        
        return metrics
    
    def calculate_quality_metrics(self, total_frames):
        """Calculate detection quality metrics"""
        metrics = {}
        
        # Average detection confidence
        if self.detection_confidences:
            metrics['average_confidence'] = float(np.mean(self.detection_confidences))
        else:
            metrics['average_confidence'] = 0.0
        
        # Detection consistency (how stable are vehicle counts)
        if len(self.frame_vehicle_counts) > 1:
            mean_count = np.mean(self.frame_vehicle_counts)
            if mean_count > 0:
                cv = np.std(self.frame_vehicle_counts) / mean_count  # Coefficient of variation
                metrics['detection_consistency'] = float(max(0, 1 - cv))  # Higher = more consistent
            else:
                metrics['detection_consistency'] = 1.0
        else:
            metrics['detection_consistency'] = 1.0
        
        # Overall quality score (combine confidence and consistency)
        metrics['processing_quality_score'] = float(
            (metrics['average_confidence'] * 0.7) + (metrics['detection_consistency'] * 0.3)
        )
        
        # Simple detection accuracy (based on confidence)
        metrics['detection_accuracy'] = metrics['average_confidence']
        
        # Frames processed
        metrics['frames_processed'] = total_frames
        
        return metrics
    
    def calculate_average_speeds(self):
        """Calculate average speeds for each vehicle type"""
        avg_speeds = {}
        for vehicle_type, speeds in self.speed_data.items():
            if speeds:  # Only calculate if we have data
                # Remove outliers (speeds beyond reasonable range 0-120 km/h)
                filtered_speeds = [s for s in speeds if 0 <= s <= 120]
                if filtered_speeds:
                    avg_speeds[vehicle_type] = float(np.mean(filtered_speeds))
        return avg_speeds
    
    def get_enhanced_metrics_report(self, total_vehicles, video_duration, fps, frame_width, total_frames):
        """Generate comprehensive enhanced metrics report"""
        return {
            'hourly_breakdown': dict(self.hourly_data),
            'speed_analysis': self.calculate_average_speeds(),
            'traffic_flow_metrics': self.calculate_traffic_flow_metrics(total_vehicles, video_duration, fps, frame_width),
            'quality_metrics': self.calculate_quality_metrics(total_frames)
        }