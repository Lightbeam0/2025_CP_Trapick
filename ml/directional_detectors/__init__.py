# ml/directional_detectors/__init__.py

import os
from functools import lru_cache

from .vertical_top_bottom import VerticalTopBottomDetector
from .vertical_bottom_top import VerticalBottomTopDetector
from .horizontal_left_right import HorizontalLeftRightDetector
from .horizontal_right_left import HorizontalRightLeftDetector
from .diagonal_ne_sw import DiagonalNESWDetector
from .diagonal_nw_se import DiagonalNWSEDetector
from .diagonal_se_nw import DiagonalSENWDetector
from .diagonal_sw_ne import DiagonalSWNEDetector
from .base_directional import BaseDirectionalDetector

# Map of all available detectors
DIRECTIONAL_DETECTORS = {
    'vertical_top_bottom': VerticalTopBottomDetector,
    'vertical_bottom_top': VerticalBottomTopDetector,
    'horizontal_left_right': HorizontalLeftRightDetector,
    'horizontal_right_left': HorizontalRightLeftDetector,
    'diagonal_ne_sw': DiagonalNESWDetector,
    'diagonal_nw_se': DiagonalNWSEDetector,
    'diagonal_se_nw': DiagonalSENWDetector,
    'diagonal_sw_ne': DiagonalSWNEDetector,
}

# Human-readable names
DETECTOR_NAMES = {
    'vertical_top_bottom': "Vertical Top→Bottom",
    'vertical_bottom_top': "Vertical Bottom→Top",
    'horizontal_left_right': "Horizontal Left→Right",
    'horizontal_right_left': "Horizontal Right→Left",
    'diagonal_ne_sw': "Diagonal NE→SW",
    'diagonal_nw_se': "Diagonal NW→SE",
    'diagonal_se_nw': "Diagonal SE→NW",
    'diagonal_sw_ne': "Diagonal SW→NE",
}


def _get_default_model_path():
    """
    Constructs the default path to the custom trained model.
    Resolves relative to this file's location:
      ml/directional_detectors -> ml -> project_root -> runs/detect/...
    """
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(BASE_DIR, 'runs', 'detect', 'custom_model', 'weights', 'best.pt')


# FIX #11: Cache loaded detector instances at the process level so the YOLO
# model (2-5 second load time) is paid only once per worker process per
# (detector_type, model_path) combination.
#
# IMPORTANT — Celery prefork safety:
#   lru_cache is populated AFTER the worker forks, so each forked worker
#   maintains its own independent cache.  GPU tensors are not shared across
#   processes, which is the correct behaviour.
#
# maxsize=4 covers all realistic combinations (one profile per location type).
@lru_cache(maxsize=4)
def _load_cached_detector(direction_name: str, model_path: str):
    """
    Return a cached detector instance.  The YOLO model is loaded from disk
    only on the first call for a given (direction_name, model_path) pair.

    Args:
        direction_name: One of the DIRECTIONAL_DETECTORS keys.
        model_path:     Absolute path to the .pt weights file.

    Returns:
        Detector instance (shared across calls with the same arguments).

    Note:
        Callers that mutate detector state (e.g. setting ROI or resetting
        tracking) must call detector.reset_tracking_state() before each video
        so the shared instance starts clean.
    """
    if direction_name not in DIRECTIONAL_DETECTORS:
        available = list(DIRECTIONAL_DETECTORS.keys())
        raise ValueError(
            f"Unknown direction: {direction_name}. "
            f"Available directions: {available}"
        )

    detector_class = DIRECTIONAL_DETECTORS[direction_name]
    instance = detector_class(model_path)
    return instance


def get_detector(direction_name, model_path=None):
    """
    Factory function to create (or return a cached) directional detector.

    Args:
        direction_name (str): One of the available direction keys.
        model_path (str, optional): Path to YOLO weights.  Defaults to
                                    runs/detect/custom_model/weights/best.pt.

    Returns:
        Detector instance (may be cached — caller must reset state before use).

    Raises:
        ValueError: If direction_name is not recognized.
    """
    resolved_path = model_path or _get_default_model_path()
    return _load_cached_detector(direction_name, resolved_path)


def list_available_detectors():
    """List all available directional detectors with descriptions"""
    print("\n" + "=" * 70)
    print("🔄 AVAILABLE DIRECTIONAL DETECTORS")
    print("=" * 70)

    for key, name in DETECTOR_NAMES.items():
        print(f"🔹 {key}: {name}")

    print("=" * 70)
    return list(DIRECTIONAL_DETECTORS.keys())


# Convenience imports
__all__ = [
    'VerticalTopBottomDetector',
    'VerticalBottomTopDetector',
    'HorizontalLeftRightDetector',
    'HorizontalRightLeftDetector',
    'DiagonalNESWDetector',
    'DiagonalNWSEDetector',
    'DiagonalSENWDetector',
    'DiagonalSWNEDetector',
    'BaseDirectionalDetector',
    'get_detector',
    '_load_cached_detector',
    'list_available_detectors',
    'DIRECTIONAL_DETECTORS',
    'DETECTOR_NAMES',
]