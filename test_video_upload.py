# test_video_upload.py
import os
import django
import sys
import requests

# Setup Django for database operations
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

from trapickapp.models import VideoFile
import json

def test_api_endpoints():
    print("=== Testing API Endpoints ===")
    base_url = "http://127.0.0.1:8000/api/"
    
    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}health/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print("   ✓ Health endpoint working")
    except Exception as e:
        print(f"   ✗ Health endpoint failed: {e}")
    
    # Test 2: Locations endpoint
    print("2. Testing locations endpoint...")
    try:
        response = requests.get(f"{base_url}locations/")
        print(f"   Status: {response.status_code}")
        locations = response.json()
        print(f"   Found {len(locations)} locations")
        for loc in locations[:3]:  # Show first 3
            print(f"     - {loc['display_name']}")
        print("   ✓ Locations endpoint working")
    except Exception as e:
        print(f"   ✗ Locations endpoint failed: {e}")
    
    # Test 3: Videos endpoint
    print("3. Testing videos endpoint...")
    try:
        response = requests.get(f"{base_url}videos/")
        print(f"   Status: {response.status_code}")
        videos = response.json()
        print(f"   Found {len(videos)} videos in database")
        print("   ✓ Videos endpoint working")
    except Exception as e:
        print(f"   ✗ Videos endpoint failed: {e}")

def test_with_sample_video():
    """Test the complete video processing pipeline"""
    print("\n=== Testing Video Processing ===")
    
    # Create a simple test video using OpenCV
    import cv2
    import numpy as np
    
    # Create a test video file
    test_video_path = "test_sample_video.mp4"
    print(f"Creating test video: {test_video_path}")
    
    # Create a simple 5-second test video
    out = cv2.VideoWriter(test_video_path, cv2.VideoWriter_fourcc(*'mp4v'), 10, (640, 480))
    for i in range(50):  # 5 seconds at 10 fps
        # Create frames with moving rectangles to simulate vehicles
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 50  # Gray background
        
        # Add moving "vehicles"
        if i % 10 < 5:  # Simulate cars moving
            cv2.rectangle(frame, (i*10, 200), (i*10+80, 250), (255, 0, 0), -1)  # Blue car
        
        out.write(frame)
    out.release()
    print("✓ Test video created")
    
    # Test upload via API
    print("Testing video upload via API...")
    try:
        with open(test_video_path, 'rb') as f:
            files = {'video': f}
            data = {
                'title': 'Test Traffic Video - Zamboanga',
                'location_id': '1'  # Use first location
            }
            response = requests.post('http://127.0.0.1:8000/api/upload/video/', files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Upload successful: {result['message']}")
            print(f"   Upload ID: {result.get('upload_id', 'N/A')}")
            
            # Check video status in database
            from trapickapp.models import VideoFile
            latest_video = VideoFile.objects.last()
            print(f"   Video status: {latest_video.processing_status}")
            print(f"   Video filename: {latest_video.filename}")
            
        else:
            print(f"   ✗ Upload failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"   ✗ Upload test failed: {e}")
    
    # Cleanup
    if os.path.exists(test_video_path):
        os.remove(test_video_path)
        print("✓ Test video cleaned up")

if __name__ == "__main__":
    test_api_endpoints()
    test_with_sample_video()