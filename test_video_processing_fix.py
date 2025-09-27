# test_video_processing_fix.py
import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

from trapickapp.models import VideoFile
from ml.vehicle_detector import RTXVehicleDetector
import cv2
import numpy as np

def test_video_processing():
    print("=== TESTING VIDEO PROCESSING FIX ===")
    
    # Create a simple test video
    test_video_path = "media/videos/test_processing_fix.mp4"
    os.makedirs('media/videos', exist_ok=True)
    
    print("Creating test video...")
    height, width = 480, 640
    fps = 10
    duration = 3  # 3 second video
    total_frames = fps * duration
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(test_video_path, fourcc, fps, (width, height))
    
    for i in range(total_frames):
        frame = np.ones((height, width, 3), dtype=np.uint8) * 100
        # Add moving rectangle to simulate vehicle
        cv2.rectangle(frame, (i*20 % width, 200), (i*20 % width + 80, 250), [255, 0, 0], -1)
        out.write(frame)
    out.release()
    
    print(f"Test video created: {test_video_path}")
    
    # Test the detector
    print("Testing video detector with output...")
    detector = RTXVehicleDetector()
    report = detector.analyze_video(test_video_path, save_output=True)
    
    print("✓ Video processing completed")
    print(f"Output path: {report.get('output_video_path', 'Not saved')}")
    
    # Check if output file exists
    if 'output_video_path' in report and os.path.exists(report['output_video_path']):
        print("✓ Processed video file exists")
        file_size = os.path.getsize(report['output_video_path'])
        print(f"File size: {file_size} bytes")
    else:
        print("✗ Processed video file not found")
    
    # Cleanup
    if os.path.exists(test_video_path):
        os.remove(test_video_path)
    if 'output_video_path' in report and os.path.exists(report['output_video_path']):
        os.remove(report['output_video_path'])

if __name__ == "__main__":
    test_video_processing()