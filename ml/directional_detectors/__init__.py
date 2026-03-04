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
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(BASE_DIR, 'runs', 'detect', 'custom_model', 'weights', 'best.pt')


# FIX-IN1: Cache only the YOLO model, not the stateful detector instance.
#
# The original _load_cached_detector cached the full detector object. Since
# lru_cache returns the exact same Python object on every call, two concurrent
# Celery tasks running on the same worker would share mutable state
# (vehicle_status, counted_vehicles, total_count, frame_data, etc.), causing
# counts to be corrupted mid-analysis.
#
# Solution: Cache the YOLO model weights (the slow part — 2-5 s disk load)
# and create a fresh detector instance on every get_detector() call (the fast
# part — in-memory object creation only). The fresh instance receives the
# already-loaded model object, so no extra disk I/O occurs.
#
# Celery prefork safety: lru_cache is populated after the worker forks, so
# each forked worker maintains its own independent model cache. GPU tensors
# are not shared across processes. ✅

@lru_cache(maxsize=4)
def _load_cached_model(model_path: str):
    """
    Load and cache a YOLO model by path.

    Returns the YOLO model object (shared — read-only during inference).
    Loading only happens once per (model_path, worker process) combination.
    """
    from ultralytics import YOLO
    import torch

    model = YOLO(model_path)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device)
    return model


def _load_cached_detector(direction_name: str, model_path: str):
    """
    Return a fresh detector instance backed by the cached YOLO model.

    FIX-IN1: This function no longer caches detector instances. Each call
    returns a new, clean detector object that shares the cached (pre-loaded)
    YOLO model. This eliminates the concurrency hazard while preserving the
    original latency benefit.

    Kept as a public symbol for callers that imported it directly.
    """
    if direction_name not in DIRECTIONAL_DETECTORS:
        available = list(DIRECTIONAL_DETECTORS.keys())
        raise ValueError(
            f"Unknown direction: {direction_name}. "
            f"Available directions: {available}"
        )

    # Ensure the model is loaded/cached
    cached_model = _load_cached_model(model_path)

    # Create a fresh stateful detector instance
    detector_class = DIRECTIONAL_DETECTORS[direction_name]
    instance = detector_class(model_path)

    # Replace its freshly-loaded model with the cached one (no extra disk I/O)
    instance.model = cached_model

    return instance


def get_detector(direction_name, model_path=None):
    """
    Factory function to create a directional detector backed by a cached model.

    Each call returns a FRESH detector instance (clean state — safe for
    concurrent Celery tasks), but the underlying YOLO model object is shared
    from the process-level cache (no repeated disk loads).

    Args:
        direction_name (str): One of the available direction keys.
        model_path (str, optional): Path to YOLO weights.

    Returns:
        Fresh detector instance with cached model loaded.

    Raises:
        ValueError: If direction_name is not recognized.
    """
    resolved_path = model_path or _get_default_model_path()
    return _load_cached_detector(direction_name, resolved_path)


def list_available_detectors():
    """List all available directional detectors with descriptions."""
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
    '_load_cached_model',
    'list_available_detectors',
    'DIRECTIONAL_DETECTORS',
    'DETECTOR_NAMES',
]