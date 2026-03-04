# ml/directional_detectors/diagonal_ne_sw.py
"""
Diagonal NE→SW detector - vehicles moving from NORTHEAST to SOUTHWEST.
"""

from .base_directional import BaseDirectionalDetector


class DiagonalNESWDetector(BaseDirectionalDetector):
    """Count vehicles moving from NORTHEAST to SOUTHWEST."""

    def __init__(self, model_path=None):
        super().__init__(direction_name="Diagonal NE→SW", model_path=model_path)
        # Even lower threshold for diagonal movement
        self.DIRECTION_THRESHOLD = 0.20

    def setup_counting_line(self, frame_width, frame_height):
        """
        Set counting line for NE→SW movement.
        Line from upper-right to lower-left.
        """
        line_start = (int(frame_width * 0.90), int(frame_height * 0.30))
        line_end = (int(frame_width * 0.30), int(frame_height * 0.90))
        valid_direction = (-1, 1)  # Southwest: -X, +Y

        return line_start, line_end, valid_direction

    def is_valid_direction(self, track_history, valid_direction_vector):
        """Check if vehicle is moving Southwest."""
        return self.enhanced_is_valid_direction(
            track_history, valid_direction_vector,
            threshold=self.DIRECTION_THRESHOLD
        )