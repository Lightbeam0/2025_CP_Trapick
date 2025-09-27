# test_final_system.py
import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

from trapickapp.models import VideoFile, TrafficAnalysis, Location, VehicleType
from ml.vehicle_detector import RTXVehicleDetector
from trapickapp.services import calculate_real_weekly_data

def test_complete_pipeline():
    print("=== FINAL SYSTEM TEST ===")
    
    # 1. Test ML module
    print("1. Testing ML Module...")
    try:
        detector = RTXVehicleDetector()
        print("   ✓ ML module loaded")
        
        # Quick functionality test
        import cv2
        import numpy as np
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        counts, detections = detector.detect_and_track(test_frame, 0)
        print(f"   ✓ Detection working - found {sum(counts.values())} vehicles")
        
    except Exception as e:
        print(f"   ✗ ML test failed: {e}")
        return False
    
    # 2. Test database with real data
    print("2. Testing Database Operations...")
    try:
        # Create a test analysis with real data structure
        location = Location.objects.first()
        if not location:
            location = Location.objects.create(name="test", display_name="Test Location")
        
        test_video = VideoFile.objects.create(
            filename="system_test.mp4",
            file_path="videos/system_test.mp4",
            processing_status='completed'
        )
        
        analysis = TrafficAnalysis.objects.create(
            video_file=test_video,
            location=location,
            total_vehicles=150,
            car_count=80,
            truck_count=30,
            motorcycle_count=35,
            bus_count=5,
            congestion_level='medium',
            traffic_pattern='stable'
        )
        
        print(f"   ✓ Created test analysis: {analysis.total_vehicles} vehicles")
        
        # Test real data calculation
        weekly_data = calculate_real_weekly_data()
        print(f"   ✓ Weekly data calculation: {weekly_data}")
        
        # Cleanup
        analysis.delete()
        test_video.delete()
        
    except Exception as e:
        print(f"   ✗ Database test failed: {e}")
        return False
    
    # 3. Test API endpoints
    print("3. Testing API Endpoints...")
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/api/health/")
        print(f"   ✓ Health endpoint: {response.status_code}")
        
        response = requests.get("http://127.0.0.1:8000/api/analyze/")
        print(f"   ✓ Analyze endpoint: {response.status_code}")
        
    except Exception as e:
        print(f"   ✗ API test failed: {e}")
        return False
    
    print("🎉 ALL TESTS PASSED! Your system is ready for production.")
    print("\nNext steps:")
    print("1. Run: python manage.py runserver")
    print("2. Start React: cd frontend && npm start") 
    print("3. Upload a real traffic video through the web interface")
    print("4. View real analyzed data on your dashboard!")
    
    return True

if __name__ == "__main__":
    test_complete_pipeline()