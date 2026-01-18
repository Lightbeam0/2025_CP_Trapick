#ml/directional_detectors/diagonal_sw_ne.py
import cv2
import numpy as np

from .base_directional import BaseDirectionalDetector


class DiagonalSWNEDetector(BaseDirectionalDetector):
    """Count vehicles moving from SOUTHWEST to NORTHEAST"""
    
    def __init__(self, model_path='yolov8l.pt'):
        # Call parent's __init__ with proper direction name
        super().__init__(direction_name="Diagonal SW→NE", model_path=model_path)
        
        # Direction-specific attributes
        self.valid_direction = (1, -1)  # Moving NE (increase X, decrease Y)
    
    def setup_counting_line(self, frame_width, frame_height):
        """Set diagonal counting line from SW to NE"""
        # Line from bottom-left to top-right
        line_start = (int(frame_width * 0.2), int(frame_height * 0.8))  # SW
        line_end = (int(frame_width * 0.8), int(frame_height * 0.2))    # NE
        
        # Valid direction: moving NE (increase X, decrease Y)
        valid_direction = (1, -1)
        
        print(f"🎯 Counting line set:")
        print(f"   Start (SW): {line_start}")
        print(f"   End (NE): {line_end}")
        print(f"   Direction: Northeast (X increasing, Y decreasing)")
        
        return line_start, line_end, valid_direction
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """Check if vehicle is moving NE (increasing X, decreasing Y)"""
        if len(track_history) < 5:
            return False
        
        points = list(track_history)
        recent_points = points[-5:] if len(points) >= 5 else points
        
        vectors = []
        for i in range(len(recent_points)-1):
            dx = recent_points[i+1][0] - recent_points[i][0]
            dy = recent_points[i+1][1] - recent_points[i][1]
            
            if abs(dx) > 2 or abs(dy) > 2:
                vectors.append((dx, dy))
        
        if not vectors:
            return False
        
        ne_vectors = 0
        for dx, dy in vectors:
            # For NE: dx should be positive, dy should be negative
            if dx > 0 and dy < 0:
                ne_vectors += 1
        
        return ne_vectors >= len(vectors) * 0.6
