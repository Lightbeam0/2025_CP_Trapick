# ml/directional_detectors/horizontal_left_right.py
"""
Horizontal Left→Right Directional Detector
Counts vehicles moving from LEFT to RIGHT of frame
Counting line at right 1/3, vehicles must exit rightward
"""

import cv2
import numpy as np
from .base_directional import BaseDirectionalDetector


class HorizontalLeftRightDetector(BaseDirectionalDetector):
    """Count vehicles moving from LEFT to RIGHT"""
    
    def __init__(self, model_path='yolov8l.pt'):
        super().__init__(direction_name="Horizontal Left→Right", model_path=model_path)
    
    def setup_counting_line(self, frame_width, frame_height):
        """Set counting line at right 1/3 of frame"""
        line_start = (int(frame_width * 0.7), int(frame_height * 0.3))
        line_end = (int(frame_width * 0.7), int(frame_height * 0.7))
        valid_direction = (1, 0)  # Moving rightward
        return line_start, line_end, valid_direction
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """Use enhanced direction validation"""
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)