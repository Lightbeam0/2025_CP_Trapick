# ml/directional_detectors/__init__.py

import os
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
    Resolves relative to this file's location: ml/directional_detectors -> ml -> project_root -> runs/detect/...
    """
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(BASE_DIR, 'runs', 'detect', 'custom_model', 'weights', 'best.pt')

def get_detector(direction_name, model_path=None):
    """
    Factory function to create a directional detector instance.
    
    Args:
        direction_name (str): One of the available direction keys (e.g., 'vertical_top_bottom').
        model_path (str, optional): Path to the YOLO model weights. 
                                    If None, defaults to 'runs/detect/custom_model/weights/best.pt'.
        
    Returns:
        Instance of the requested detector class.
        
    Raises:
        ValueError: If direction_name is not recognized.
        NotImplementedError: If a placeholder detector is requested.
    """
    if direction_name not in DIRECTIONAL_DETECTORS:
        available = list(DIRECTIONAL_DETECTORS.keys())
        raise ValueError(
            f"Unknown direction: {direction_name}. "
            f"Available directions: {available}"
        )
    
    # Resolve model path
    if model_path is None:
        model_path = _get_default_model_path()
    
    detector_class = DIRECTIONAL_DETECTORS[direction_name]
    
    # Check if it's a placeholder (for non-directional types added dynamically)
    if detector_class == _placeholder_detector:
        raise NotImplementedError(f"Detector '{direction_name}' is not implemented in the directional module.")
    
    return detector_class(model_path)

def _placeholder_detector(model_path='yolov8l.pt'):
    """Placeholder for non-directional detectors that might be referenced but not implemented here."""
    raise NotImplementedError("This detector type is not implemented in directional_detectors")


def list_available_detectors():
    """List all available directional detectors with descriptions"""
    print("\n" + "="*70)
    print("🔄 AVAILABLE DIRECTIONAL DETECTORS")
    print("="*70)
    
    for key, name in DETECTOR_NAMES.items():
        print(f"🔹 {key}: {name}")
    
    print("="*70)
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
    'list_available_detectors',
    'DIRECTIONAL_DETECTORS',
    'DETECTOR_NAMES',
]