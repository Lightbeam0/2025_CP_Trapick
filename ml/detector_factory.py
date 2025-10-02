from .baliwasan_yjunction_detector import BaliwasanYJunctionDetector
from .vehicle_detector import RTXVehicleDetector

class DetectorFactory:
    @staticmethod
    def get_detector(processing_profile):
        """Get detector instance from ProcessingProfile object"""
        print(f"🔧 [DEBUG] Getting detector for profile: {processing_profile.display_name}")
        print(f"🔧 [DEBUG] Looking in module: {processing_profile.detector_module}")
        print(f"🔧 [DEBUG] For class: {processing_profile.detector_class}")
        
        try:
            # Use the profile's configured detector
            detector = processing_profile.get_detector_instance()
            print(f"✅ [DEBUG] Successfully loaded: {type(detector).__name__}")
            return detector
        except Exception as e:
            print(f"❌ [DEBUG] Error loading {processing_profile.detector_class}: {e}")
            print("🔄 [DEBUG] Using fallback RTXVehicleDetector...")
            # Fallback to default detector
            return RTXVehicleDetector()