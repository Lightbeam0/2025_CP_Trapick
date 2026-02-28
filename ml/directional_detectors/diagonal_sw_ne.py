# ml/directional_detectors/diagonal_sw_ne.py
"""Diagonal SW→NE — vehicles moving from SOUTHWEST to NORTHEAST."""
from .base_directional import BaseDirectionalDetector


class DiagonalSWNEDetector(BaseDirectionalDetector):
    def __init__(self, model_path=None):
        super().__init__("Diagonal SW→NE", model_path)

    def setup_counting_line(self, w, h):
        start = (int(w * 0.15), int(h * 0.85))
        end   = (int(w * 0.85), int(h * 0.15))
        print(f"🎯 Line: {start} → {end}  direction: NE (+X −Y)")
        return start, end, (1, -1)

    def is_valid_direction(self, track_history, valid_direction_vector):
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector,
                                                threshold=0.45)