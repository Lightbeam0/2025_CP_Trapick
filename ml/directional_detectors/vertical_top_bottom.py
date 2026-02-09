# ml/directional_detectors/vertical_top_bottom.py
"""
Vertical Top→Bottom Directional Detector
Counts vehicles moving from TOP to BOTTOM of frame
Counting line at bottom 1/3, vehicles must exit downward
"""

import cv2
import numpy as np
from .base_directional import BaseDirectionalDetector


class VerticalTopBottomDetector(BaseDirectionalDetector):
    """Count vehicles moving from TOP to BOTTOM"""
    
    def __init__(self, model_path='yolov8l.pt'):
        super().__init__(direction_name="Vertical Top→Bottom", model_path=model_path)
    
    def setup_counting_line(self, frame_width, frame_height):
        """Set counting line at bottom 1/3 of frame"""
        line_start = (int(frame_width * 0.2), int(frame_height * 0.7))
        line_end = (int(frame_width * 0.8), int(frame_height * 0.7))
        valid_direction = (0, 1)  # Moving downward
        return line_start, line_end, valid_direction
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """Use enhanced direction validation"""
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)