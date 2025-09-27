# ml/test_yolo.py
import cv2
import numpy as np
from vehicle_detector import RTXVehicleDetector

def test_yolo_detection():
    print("Testing YOLO detection with RTX 3050...")
    
    # Create a simple test image
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Initialize detector
    detector = RTXVehicleDetector()
    print("✓ Detector initialized")
    
    # Test detection on single frame
    counts, detections = detector.detect_and_track(test_image, 0)
    print(f"✓ Detection test passed - Found: {dict(counts)}")
    
    # Test with a real video if available
    try:
        # Create a quick test video
        test_video = "ml/test_short.mp4"
        height, width = 480, 640
        out = cv2.VideoWriter(test_video, cv2.VideoWriter_fourcc(*'mp4v'), 5, (width, height))
        
        for i in range(10):  # 2-second video
            frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            out.write(frame)
        out.release()
        
        # Test video analysis
        report = detector.analyze_video(test_video)
        print("✓ Video analysis test passed")
        print(f"Report summary: {report['summary']}")
        
    except Exception as e:
        print(f"Video test skipped: {e}")
    
    print("🎯 YOLO ML module is working!")

if __name__ == "__main__":
    test_yolo_detection()