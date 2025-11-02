from .vehicle_detector import RTXVehicleDetector
from .baliwasan_yjunction_detector import BaliwasanYJunctionDetector

class DetectorFactory:
    @staticmethod
    def get_detector(processing_profile):
        """Get detector instance from ProcessingProfile object"""
        print(f"🔧 Getting detector for profile: {processing_profile.display_name}")
        
        try:
            # Use the profile's configured detector
            detector = processing_profile.get_detector_instance()
            print(f"✅ Successfully loaded: {type(detector).__name__}")
            return detector
        except Exception as e:
            print(f"❌ Error loading {processing_profile.detector_class}: {e}")
            print("🔄 Using fallback RTXVehicleDetector...")
            return RTXVehicleDetector()

    @staticmethod
    def get_detector_by_name(detector_name):
        """Get detector by name for simple cases"""
        detectors = {
            'RTXVehicleDetector': RTXVehicleDetector,
            'BaliwasanYJunctionDetector': BaliwasanYJunctionDetector,
        }
        detector_class = detectors.get(detector_name, RTXVehicleDetector)
        return detector_class()