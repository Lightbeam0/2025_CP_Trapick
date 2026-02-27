# ml/directional_detectors/horizontal_left_right.py
"""Horizontal Left→Right — vehicles moving from LEFT to RIGHT."""
from .base_directional import BaseDirectionalDetector

class HorizontalLeftRightDetector(BaseDirectionalDetector):
    def __init__(self, model_path=None):
        super().__init__("Horizontal Left→Right", model_path)

    def setup_counting_line(self, w, h):
        # Line at 65% width — gives vehicles entry room on the left
        start = (int(w * 0.65), int(h * 0.15))
        end   = (int(w * 0.65), int(h * 0.85))
        print(f"🎯 Line: {start} → {end}  direction: →")
        return start, end, (1, 0)   # +X = rightward

    def is_valid_direction(self, track_history, valid_direction_vector):
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)