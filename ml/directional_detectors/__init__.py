# ml/directional_detectors/__init__.py

from .vertical_top_bottom import VerticalTopBottomDetector
from .vertical_bottom_top import VerticalBottomTopDetector
from .horizontal_left_right import HorizontalLeftRightDetector
from .horizontal_right_left import HorizontalRightLeftDetector
from .diagonal_ne_sw import DiagonalNESWDetector
from .diagonal_nw_se import DiagonalNWSEDetector
from .diagonal_se_nw import DiagonalSENWDetector
from .diagonal_sw_ne import DiagonalSWNEDetector

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

# For congestion_time and baliwasan_yjunction, you'll need to import them separately
# Add them to your factory if they exist in your system
# For now, let's add them with placeholders that will raise errors
def _placeholder_detector(model_path='yolov8l.pt'):
    """Placeholder for non-directional detectors"""
    raise NotImplementedError("This detector type is not implemented in directional_detectors")

DIRECTIONAL_DETECTORS['congestion_time'] = _placeholder_detector
DIRECTIONAL_DETECTORS['baliwasan_yjunction'] = _placeholder_detector

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
    'congestion_time': "Congestion Time Detector",
    'baliwasan_yjunction': "Baliwasan Y-Junction",
}

def get_detector(direction_name, model_path='yolov8l.pt'):
    """
    Factory function to create directional detector.
    
    Args:
        direction_name: One of the 8 direction names
        model_path: Path to YOLO model
        
    Returns:
        Instance of the requested detector
        
    Raises:
        ValueError: If direction_name is not recognized
    """
    if direction_name not in DIRECTIONAL_DETECTORS:
        available = list(DIRECTIONAL_DETECTORS.keys())
        raise ValueError(
            f"Unknown direction: {direction_name}. "
            f"Available directions: {available}"
        )
    
    detector_class = DIRECTIONAL_DETECTORS[direction_name]
    return detector_class(model_path)

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
    'get_detector',
    'list_available_detectors',
    'DIRECTIONAL_DETECTORS',
    'DETECTOR_NAMES',
]