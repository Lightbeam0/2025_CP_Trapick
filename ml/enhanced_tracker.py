# ml/enhanced_tracker.py
import numpy as np
from collections import deque, defaultdict
import cv2
import time
from pathlib import Path

class EnhancedByteTrackWrapper:
    """
    Wrapper around ByteTrack with additional features for traffic detection
    """
    
    def __init__(self, config_path="bytetrack.yaml"):
        self.config_path = config_path
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.track_confidences = defaultdict(lambda: deque(maxlen=10))
        self.missing_tracks = {}  # Track lost tracks
        self.min_track_length = 5  # Minimum frames to consider a track valid
        
        # Vehicle class-specific settings
        self.class_tracking_params = {
            'car': {'min_size': 400, 'stability_threshold': 0.7},
            'motorcycle': {'min_size': 200, 'stability_threshold': 0.6},
            'bus': {'min_size': 1000, 'stability_threshold': 0.8},
            'truck': {'min_size': 800, 'stability_threshold': 0.8}
        }
    
    def postprocess_tracks(self, yolo_results, frame_number, fps):
        """
        Process YOLO tracking results and enhance with additional metrics
        This method should handle the actual ByteTrack processing
        """
        processed_tracks = []
        
        if not yolo_results or len(yolo_results) == 0:
            return processed_tracks
            
        result = yolo_results[0]  # Get first (and usually only) result
        
        if result.boxes is None or result.boxes.id is None:
            return processed_tracks
            
        boxes = result.boxes.xyxy.cpu().numpy()
        track_ids = result.boxes.id.int().cpu().numpy()
        class_ids = result.boxes.cls.int().cpu().numpy()
        confidences = result.boxes.conf.float().cpu().numpy()
        
        for i, (box, track_id, class_id, confidence) in enumerate(zip(boxes, track_ids, class_ids, confidences)):
            x1, y1, x2, y2 = box
            width = x2 - x1
            height = y2 - y1
            area = width * height
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Store in track history
            self.track_history[track_id].append((center_x, center_y, width, height))
            self.track_confidences[track_id].append(confidence)
            
            # Calculate stability (based on consistent movement and size)
            stability = self._calculate_stability(track_id, fps)
            
            # Get class name
            class_names = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
            class_name = class_names.get(int(class_id), 'unknown')
            
            # Apply class-specific validation
            is_valid = self._validate_track(track_id, class_name, area, stability)
            
            track_data = {
                'track_id': int(track_id),
                'box': [int(x1), int(y1), int(width), int(height)],
                'center': (int(center_x), int(center_y)),
                'raw_center': (center_x, center_y),
                'class_id': int(class_id),
                'confidence': float(confidence),
                'stability': float(stability),
                'is_valid': bool(is_valid),
                'area': float(area),
                'frame_number': frame_number
            }
            
            processed_tracks.append(track_data)
        
        # Clean up old tracks
        self._cleanup_old_tracks(frame_number)
        
        return processed_tracks
    
    def _calculate_stability(self, track_id, fps):
        """Calculate track stability based on movement consistency"""
        if track_id not in self.track_history or len(self.track_history[track_id]) < 3:
            return 0.0
        
        history = list(self.track_history[track_id])
        if len(history) < 3:
            return 0.0
        
        # Calculate velocity consistency
        velocities = []
        for i in range(1, len(history)):
            prev_x, prev_y, _, _ = history[i-1]
            curr_x, curr_y, _, _ = history[i]
            dx = curr_x - prev_x
            dy = curr_y - prev_y
            velocity = np.sqrt(dx*dx + dy*dy)
            velocities.append(velocity)
        
        if len(velocities) < 2:
            return 0.5
        
        # Stability is inverse of velocity variance
        velocity_std = np.std(velocities)
        max_velocity = max(velocities) if velocities else 1.0
        
        # Normalize stability (0-1 range)
        if max_velocity > 0:
            stability = 1.0 - min(velocity_std / max_velocity, 1.0)
        else:
            stability = 0.5
        
        return stability
    
    def _validate_track(self, track_id, class_name, area, stability):
        """Validate track based on class-specific criteria"""
        if class_name not in self.class_tracking_params:
            return True  # Default to valid for unknown classes
        
        params = self.class_tracking_params[class_name]
        
        # Check minimum size
        if area < params['min_size']:
            return False
        
        # Check stability threshold
        if stability < params['stability_threshold']:
            return False
        
        # Check minimum track length
        if len(self.track_history[track_id]) < self.min_track_length:
            return False
        
        return True
    
    def _cleanup_old_tracks(self, current_frame, max_missing_frames=30):
        """Clean up tracks that haven't been seen for too long"""
        tracks_to_remove = []
        for track_id in self.track_history:
            # In a real implementation, you'd track last seen frame
            # For now, we'll keep it simple and not remove anything
            pass
    
    def get_track_history(self, track_id):
        """Get position history for a track"""
        if track_id not in self.track_history:
            return []
        
        positions = list(self.track_history[track_id])
        return [(x, y) for x, y, _, _ in positions]  # Extract only (x, y)