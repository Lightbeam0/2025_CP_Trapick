# ml/directional_detectors/diagonal_ne_sw.py
"""
Diagonal NE→SW — vehicles moving from NORTHEAST to SOUTHWEST.

FIX #2: Removed self.valid_direction = (-1, 1) from __init__.
         setup_counting_line() is the only source of truth.
FIX #5: Counting line coordinates clamped to within-frame bounds (≤ 1.0).
         Old code used 1.10× multipliers, placing the line off-screen and
         causing vehicles near the edge to never trigger a crossing event.
"""
from .base_directional import BaseDirectionalDetector


class DiagonalNESWDetector(BaseDirectionalDetector):
    """Count vehicles moving from NORTHEAST to SOUTHWEST."""

    def __init__(self, model_path=None):
        super().__init__(direction_name="Diagonal NE→SW", model_path=model_path)
        # FIX #2: Do NOT set self.valid_direction here.
        #         It will be set by setup_counting_line() on first frame.

    def setup_counting_line(self, frame_width, frame_height):
        """
        Diagonal counting line across the lower-right quadrant of the frame.

        FIX #5: All coordinates are ≤ frame dimensions so the line is always
        visible and vehicle paths reliably cross it.
        """
        # NE corner of the line (upper-right area)
        line_start = (int(frame_width * 0.90), int(frame_height * 0.15))
        # SW corner of the line (lower-left area)
        line_end   = (int(frame_width * 0.15), int(frame_height * 0.85))

        # Valid direction: moving SW (decrease X, increase Y)
        valid_direction = (-1, 1)

        print(f"🎯 DiagonalNESW counting line:")
        print(f"   Start (NE): {line_start}")
        print(f"   End   (SW): {line_end}")
        print(f"   Direction : Southwest (−X, +Y)")

        return line_start, line_end, valid_direction

    def is_valid_direction(self, track_history, valid_direction_vector):
        return self.enhanced_is_valid_direction(track_history, valid_direction_vector,
                                                threshold=0.45)