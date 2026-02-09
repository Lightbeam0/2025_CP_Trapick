# ml/directional_detectors/horizontal_right_left.py
"""
Horizontal Right→Left Directional Detector
Counts vehicles moving from RIGHT to LEFT of frame
Counting line at left 1/3, vehicles must exit leftward
"""

import cv2
import numpy as np
from .base_directional import BaseDirectionalDetector


class HorizontalRightLeftDetector(BaseDirectionalDetector):
    """Count vehicles moving from RIGHT to LEFT"""
    
    def __init__(self, model_path='yolov8l.pt'):
        super().__init__(direction_name="Horizontal Right→Left", model_path=model_path)
    
    def setup_counting_line(self, frame_width, frame_height):
        """Set counting line at left 1/3 of frame"""
        line_start = (int(frame_width * 0.3), int(frame_height * 0.3))
        line_end = (int(frame_width * 0.3), int(frame_height * 0.7))
        valid_direction = (-1, 0)  # Moving leftward
        return line_start, line_end, valid_direction
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """Use enhanced direction validation"""
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)