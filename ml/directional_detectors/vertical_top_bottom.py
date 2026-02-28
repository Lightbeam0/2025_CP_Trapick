# ml/directional_detectors/vertical_top_bottom.py
"""Vertical Top→Bottom — vehicles moving from TOP to BOTTOM."""
from .base_directional import BaseDirectionalDetector


class VerticalTopBottomDetector(BaseDirectionalDetector):
    def __init__(self, model_path=None):
        super().__init__("Vertical Top→Bottom", model_path)

    def setup_counting_line(self, w, h):
        # Horizontal line at 65% height — vehicles have enough room above it
        start = (int(w * 0.10), int(h * 0.65))
        end   = (int(w * 0.90), int(h * 0.65))
        print(f"🎯 Line: {start} → {end}  direction: ↓")
        return start, end, (0, 1)   # +Y = downward

    def is_valid_direction(self, track_history, valid_direction_vector):
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector)