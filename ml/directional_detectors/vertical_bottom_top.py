# ml/directional_detectors/vertical_bottom_top.py
"""
Vertical Bottom→Top Directional Detector
Counts vehicles moving from BOTTOM to TOP of frame
Counting line at top 1/3, vehicles must exit upward
"""

import cv2
import numpy as np
from .base_directional import BaseDirectionalDetector


class VerticalBottomTopDetector(BaseDirectionalDetector):
    """Count vehicles moving from BOTTOM to TOP"""
    
    def __init__(self, model_path='yolov8l.pt'):
        super().__init__(direction_name="Vertical Bottom→Top", model_path=model_path)
    
    def setup_counting_line(self, frame_width, frame_height):
        """Set counting line at top 1/3 of frame"""
        line_start = (int(frame_width * 0.2), int(frame_height * 0.3))
        line_end = (int(frame_width * 0.8), int(frame_height * 0.3))
        valid_direction = (0, -1)  # Moving upward
        return line_start, line_end, valid_direction
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """Use enhanced direction validation"""
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)