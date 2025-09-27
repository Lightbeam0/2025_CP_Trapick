# test_video_upload_real.py
import requests
import os

def test_video_upload():
    print("=== TESTING VIDEO UPLOAD ===")
    
    # Create a simple test video
    test_video_path = "test_upload_video.mp4"
    
    # Create a quick test video using OpenCV
    import cv2
    import numpy as np
    
    height, width = 480, 640
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(test_video_path, fourcc, 10, (width, height))
    
    print("Creating test video for upload...")
    for i in range(30):  # 3-second video
        frame = np.random.randint(50, 200, (height, width, 3), dtype=np.uint8)
        # Add some vehicle-like shapes
        cv2.rectangle(frame, (100, 200), (200, 250), [0, 0, 255], -1)  # Car
        cv2.rectangle(frame, (300, 180), (450, 260), [255, 165, 0], -1)  # Truck
        out.write(frame)
    out.release()
    
    print("Uploading video to Django...")
    try:
        with open(test_video_path, 'rb') as f:
            files = {'video': f}
            data = {'title': 'System Test Video'}
            response = requests.post('http://127.0.0.1:8000/api/upload/video/', files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("✓ Video upload successful!")
            print(f"Response: {result}")
            
            # Check the upload status
            upload_id = result.get('upload_id')
            if upload_id:
                print(f"Upload ID: {upload_id}")
                # Check analysis status
                status_response = requests.get(f'http://127.0.0.1:8000/api/analysis/{upload_id}/')
                print(f"Analysis status: {status_response.json()}")
        else:
            print(f"✗ Upload failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"✗ Upload test failed: {e}")
    
    # Cleanup
    if os.path.exists(test_video_path):
        os.remove(test_video_path)
        print("✓ Test video cleaned up")

if __name__ == "__main__":
    test_video_upload()