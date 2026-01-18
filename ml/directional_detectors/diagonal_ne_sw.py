# ml/directional_detectors/diagonal_ne_sw.py
import cv2
import numpy as np
from .base_directional import BaseDirectionalDetector


class DiagonalNESWDetector(BaseDirectionalDetector):
    """Count vehicles moving from NORTHEAST to SOUTHWEST"""
    
    def __init__(self, model_path='yolov8l.pt'):
        # Call parent's __init__ with proper direction name
        super().__init__(direction_name="Diagonal NE→SW", model_path=model_path)
        
        # Direction-specific attributes
        self.valid_direction = (-1, 1)  # Moving SW (decrease X, increase Y)
    
    def setup_counting_line(self, frame_width, frame_height):
        """Set diagonal counting line from NE to SW, positioned in LOWER RIGHT corner"""
        # Diagonal line in the lower-right quadrant of the frame
        # Line goes from upper-right area to lower-left area of that quadrant
        line_start = (int(frame_width * 1.10), int(frame_height * 0.40))  # NE position (moved more right and higher)
        line_end = (int(frame_width * 0.40), int(frame_height * 1.10))    # SW position (expanded length, lower-left)
        
        # Valid direction: moving SW (decrease X, increase Y)
        valid_direction = (-1, 1)
        
        print(f"🎯 Counting line set (LOWER RIGHT quadrant):")
        print(f"   Start (NE): {line_start} - at ({line_start[0]/frame_width*100:.1f}%, {line_start[1]/frame_height*100:.1f}%)")
        print(f"   End (SW): {line_end} - at ({line_end[0]/frame_width*100:.1f}%, {line_end[1]/frame_height*100:.1f}%)")
        print(f"   Direction: Southwest (X decreasing, Y increasing)")
        print(f"   Coverage: Lower-right quadrant of frame")
        
        return line_start, line_end, valid_direction
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """Check if vehicle is moving SW (decreasing X, increasing Y)"""
        if len(track_history) < 5:
            return False
        
        points = list(track_history)
        recent_points = points[-5:] if len(points) >= 5 else points
        
        # Calculate movement vectors
        vectors = []
        for i in range(len(recent_points)-1):
            dx = recent_points[i+1][0] - recent_points[i][0]
            dy = recent_points[i+1][1] - recent_points[i][1]
            
            # Only consider significant movements
            if abs(dx) > 2 or abs(dy) > 2:
                vectors.append((dx, dy))
        
        if not vectors:
            return False
        
        # Check if majority of vectors align with SW direction
        sw_vectors = 0
        for dx, dy in vectors:
            # For SW: dx should be negative, dy should be positive
            if dx < 0 and dy > 0:
                sw_vectors += 1
        
        return sw_vectors >= len(vectors) * 0.6