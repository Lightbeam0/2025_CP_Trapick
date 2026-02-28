# ml/directional_detectors/vertical_bottom_top.py
"""Vertical Bottom→Top — vehicles moving from BOTTOM to TOP."""
from .base_directional import BaseDirectionalDetector


class VerticalBottomTopDetector(BaseDirectionalDetector):
    def __init__(self, model_path=None):
        super().__init__("Vertical Bottom→Top", model_path)

    def setup_counting_line(self, w, h):
        # Horizontal line at 35% height — vehicles approach from below
        start = (int(w * 0.10), int(h * 0.35))
        end   = (int(w * 0.90), int(h * 0.35))
        print(f"🎯 Line: {start} → {end}  direction: ↑")
        return start, end, (0, -1)  # −Y = upward

    def is_valid_direction(self, track_history, valid_direction_vector):
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)