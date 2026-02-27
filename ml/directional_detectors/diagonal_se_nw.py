# ml/directional_detectors/diagonal_se_nw.py
"""Diagonal SE→NW — vehicles moving from SOUTHEAST to NORTHWEST."""
from .base_directional import BaseDirectionalDetector

class DiagonalSENWDetector(BaseDirectionalDetector):
    def __init__(self, model_path=None):
        super().__init__("Diagonal SE→NW", model_path)

    def setup_counting_line(self, w, h):
        start = (int(w * 0.80), int(h * 0.75))
        end   = (int(w * 0.25), int(h * 0.20))
        print(f"🎯 Line: {start} → {end}  direction: NW (−X −Y)")
        return start, end, (-1, -1)

    def is_valid_direction(self, track_history, valid_direction_vector):
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector,
                                                threshold=0.48)