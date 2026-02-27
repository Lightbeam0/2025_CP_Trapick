# ml/directional_detectors/horizontal_right_left.py
"""Horizontal Right→Left — vehicles moving from RIGHT to LEFT."""
from .base_directional import BaseDirectionalDetector

class HorizontalRightLeftDetector(BaseDirectionalDetector):
    def __init__(self, model_path=None):
        super().__init__("Horizontal Right→Left", model_path)

    def setup_counting_line(self, w, h):
        # Line at 35% width
        start = (int(w * 0.35), int(h * 0.15))
        end   = (int(w * 0.35), int(h * 0.85))
        print(f"🎯 Line: {start} → {end}  direction: ←")
        return start, end, (-1, 0)  # −X = leftward

    def is_valid_direction(self, track_history, valid_direction_vector):
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)