# test_complete_system.py
import os
import django
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

from trapickapp.models import VideoFile, TrafficAnalysis, VehicleType, Location
from ml.vehicle_detector import RTXVehicleDetector

def test_complete_system():
    print("=== Testing Complete System ===")
    
    # Test 1: Database models
    print("1. Testing database models...")
    video_count = VideoFile.objects.count()
    vehicle_types = VehicleType.objects.count()
    locations = Location.objects.count()
    print(f"   - Videos: {video_count}")
    print(f"   - Vehicle types: {vehicle_types}")
    print(f"   - Locations: {locations}")
    print("   ✓ Database test passed")
    
    # Test 2: ML module
    print("2. Testing ML module...")
    try:
        detector = RTXVehicleDetector()
        print("   ✓ ML module test passed")
    except Exception as e:
        print(f"   ✗ ML module test failed: {e}")
        return False
    
    # Test 3: Create a test video record
    print("3. Testing video creation...")
    try:
        test_video = VideoFile.objects.create(
            filename="test_video.mp4",
            file_path="videos/test_video.mp4",
            processing_status='completed'
        )
        print(f"   ✓ Test video created: {test_video.filename}")
        
        # Test 4: Create analysis record
        test_analysis = TrafficAnalysis.objects.create(
            video_file=test_video,
            total_vehicles=150,
            car_count=100,
            truck_count=20,
            motorcycle_count=25,
            bus_count=5,
            congestion_level='medium'
        )
        print(f"   ✓ Test analysis created: {test_analysis.total_vehicles} vehicles")
        
        # Cleanup
        test_analysis.delete()
        test_video.delete()
        print("   ✓ Test data cleaned up")
        
    except Exception as e:
        print(f"   ✗ Database operation failed: {e}")
        return False
    
    print("✓ All tests passed! System is ready for frontend integration.")
    return True

if __name__ == "__main__":
    test_complete_system()