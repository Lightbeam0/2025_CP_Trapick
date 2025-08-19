import cv2
from ultralytics import YOLO
import numpy as np
from collections import defaultdict
from django.db import transaction
import time

class VehicleDetector:
    def __init__(self, model_size='n'):
        """
        Initialize the vehicle detector with specified YOLOv8 model size.
        Available sizes: n (nano), s (small), m (medium), l (large), x (extra large)
        """
        model_map = {
            'n': 'yolov8n.pt',
            's': 'yolov8s.pt',
            'm': 'yolov8m.pt',
            'l': 'yolov8l.pt',
            'x': 'yolov8x.pt'
        }
        self.model = YOLO(model_map.get(model_size, 'yolov8n.pt'))
        self.vehicle_classes = [2, 3, 5, 7]  # cars, motorcycles, buses, trucks
        
    def process_video(self, video_path, progress_callback=None):
        """
        Process a video file and detect vehicles frame by frame.
        
        Args:
            video_path (str): Path to the video file
            progress_callback (function): Optional callback to report progress
            
        Returns:
            dict: Detection results including frame data, hourly counts, and vehicle types
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = 0
        
        results = []
        hourly_counts = defaultdict(lambda: defaultdict(int))
        vehicle_types = defaultdict(int)
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                timestamp = frame_count / fps
                
                # Process frame with YOLOv8 (only every 5th frame for performance)
                if frame_count % 5 == 0:
                    detections = self.model(frame, classes=self.vehicle_classes, verbose=False)
                    
                    # Extract vehicle information
                    for detection in detections:
                        for box in detection.boxes:
                            class_id = int(box.cls)
                            vehicle_type = detection.names[class_id]
                            confidence = float(box.conf)
                            
                            results.append({
                                'frame': frame_count,
                                'timestamp': timestamp,
                                'vehicle_type': vehicle_type,
                                'confidence': confidence,
                                'bbox': box.xyxy[0].tolist()  # Store bounding box coordinates
                            })
                            
                            hour = int(timestamp / 3600) % 24
                            hourly_counts[hour][vehicle_type] += 1
                            vehicle_types[vehicle_type] += 1
                
                # Report progress every 100 frames
                if progress_callback and frame_count % 100 == 0:
                    progress = (frame_count / total_frames) * 100
                    progress_callback(progress)
                    
        finally:
            cap.release()
        
        return {
            'detections': results,
            'hourly_counts': hourly_counts,
            'vehicle_types': vehicle_types,
            'total_frames': total_frames,
            'processed_frames': frame_count
        }
    
    @staticmethod
    @transaction.atomic
    def save_detection_results(video_id, results):
        """
        Save detection results to the database in bulk for efficiency.
        
        Args:
            video_id (int): ID of the associated VideoUpload
            results (dict): Detection results from process_video()
        """
        from .models import VehicleDetection, TrafficAnalysis
        
        # Batch size for bulk creation
        batch_size = 1000
        
        # Prepare detection data for bulk insert
        detections = [
            VehicleDetection(
                video_id=video_id,
                frame_number=det['frame'],
                timestamp=det['timestamp'],
                vehicle_type=det['vehicle_type'],
                confidence=det['confidence'],
                bbox=det.get('bbox', [])  # Store bounding box if available
            ) for det in results['detections']
        ]
        
        # Bulk create in batches to avoid memory issues
        for i in range(0, len(detections), batch_size):
            VehicleDetection.objects.bulk_create(detections[i:i+batch_size])
        
        # Create hourly traffic analysis
        for hour, counts in results['hourly_counts'].items():
            TrafficAnalysis.objects.create(
                video_id=video_id,
                hour_of_day=hour,
                vehicle_count=sum(counts.values()),
                vehicle_types=dict(counts)  # Convert defaultdict to regular dict
            )
        
        return len(detections)