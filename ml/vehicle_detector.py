import cv2
import numpy as np
from ultralytics import YOLO
import torch
from collections import defaultdict, deque
import time
from datetime import datetime
import os

class Config:
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    MODEL_PATH = 'yolov11s.pt'
    VEHICLE_CLASSES = {
        2: 'car',
        3: 'motorcycle', 
        5: 'bus',
        7: 'truck',
        1: 'bicycle'
    }
    CONFIDENCE_THRESHOLD = 0.4
    PROCESS_EVERY_N_FRAMES = 2  # Process more frames for better accuracy

class RTXVehicleDetector:
    def __init__(self, model_path=Config.MODEL_PATH):
        print("Initializing YOLO model with GPU support...")
        self.model = YOLO(model_path)
        if Config.DEVICE == 'cuda':
            self.model.model.to(Config.DEVICE)
        
        self.vehicle_classes = Config.VEHICLE_CLASSES
        self.conf_threshold = Config.CONFIDENCE_THRESHOLD
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_counts = defaultdict(int)
        self.crossed_objects = set()
        self.frame_analyses = []
        
        # Colors for different vehicle types
        self.colors = {
            'car': (0, 255, 0),      # Green
            'truck': (255, 165, 0),  # Orange
            'bus': (0, 0, 255),      # Red
            'motorcycle': (255, 255, 0), # Yellow
            'bicycle': (255, 0, 255), # Magenta
            'other': (128, 128, 128) # Gray
        }
        
        print("✓ RTXVehicleDetector initialized successfully")

    def setup_counting_zone(self, frame):
        """Setup counting zone with visual indicators"""
        height, width = frame.shape[:2]
        self.zone_top = int(height * 0.3)
        self.zone_bottom = int(height * 0.7)
        self.zone_left = int(width * 0.2)
        self.zone_right = int(width * 0.8)
        
        # Zone visualization properties
        self.zone_color = (0, 255, 255)  # Yellow
        self.zone_thickness = 2
        
        return {
            'top': self.zone_top, 'bottom': self.zone_bottom,
            'left': self.zone_left, 'right': self.zone_right
        }

    def is_in_counting_zone(self, x, y, w, h):
        center_x, center_y = x + w/2, y + h/2
        return (self.zone_left <= center_x <= self.zone_right and 
                self.zone_top <= center_y <= self.zone_bottom)

    def draw_detection_info(self, frame, detections, frame_number, fps, total_vehicles):
        """Draw detection information on the frame"""
        height, width = frame.shape[:2]
        
        # Draw counting zone
        cv2.rectangle(frame, 
                     (self.zone_left, self.zone_top), 
                     (self.zone_right, self.zone_bottom), 
                     self.zone_color, self.zone_thickness)
        
        # Draw zone label
        cv2.putText(frame, "COUNTING ZONE", (self.zone_left, self.zone_top - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.zone_color, 1)
        
        # Draw detections
        for detection in detections:
            x1, y1, w, h = detection['bbox']
            class_name = detection['class_name']
            confidence = detection['confidence']
            track_id = detection.get('track_id', 0)
            
            color = self.colors.get(class_name, self.colors['other'])
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), color, 2)
            
            # Draw label with class name and confidence
            label = f"{class_name} {confidence:.2f} ID:{track_id}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # Background for label
            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                         (x1 + label_size[0], y1), color, -1)
            
            # Text
            cv2.putText(frame, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Draw center point
            center_x, center_y = x1 + w//2, y1 + h//2
            cv2.circle(frame, (center_x, center_y), 4, color, -1)
            
            # Draw track history
            if track_id in self.track_history:
                points = list(self.track_history[track_id])
                for i in range(1, len(points)):
                    cv2.line(frame, points[i-1], points[i], color, 2)
        
        # Draw statistics overlay
        self.draw_statistics_overlay(frame, frame_number, fps, total_vehicles, detections)
        
        return frame

    def draw_statistics_overlay(self, frame, frame_number, fps, total_vehicles, detections):
        """Draw statistics overlay on the frame"""
        height, width = frame.shape[:2]
        
        # Create semi-transparent overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (300, 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Current time in video
        current_time = frame_number / fps if fps > 0 else 0
        minutes = int(current_time // 60)
        seconds = int(current_time % 60)
        
        # Statistics text
        stats = [
            f"Time: {minutes:02d}:{seconds:02d}",
            f"Frame: {frame_number}",
            f"FPS: {fps:.1f}",
            f"Total Vehicles: {total_vehicles}",
            f"Current Detections: {len(detections)}",
            "Vehicle Counts:"
        ]
        
        # Add vehicle counts
        current_counts = {}
        for detection in detections:
            class_name = detection['class_name']
            current_counts[class_name] = current_counts.get(class_name, 0) + 1
        
        for class_name in sorted(current_counts.keys()):
            stats.append(f"  {class_name}: {current_counts[class_name]}")
        
        # Draw statistics
        y_offset = 40
        for i, text in enumerate(stats):
            color = (255, 255, 255)  # White
            if i == 3:  # Total vehicles line
                color = (0, 255, 255)  # Yellow
            elif i >= 5:  # Vehicle counts
                class_name = text.split(':')[0].strip()
                color = self.colors.get(class_name, (255, 255, 255))
            
            cv2.putText(frame, text, (20, y_offset + i * 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def detect_and_track(self, frame, frame_number):
        """Perform detection and tracking on a single frame"""
        if frame_number % Config.PROCESS_EVERY_N_FRAMES != 0 and frame_number > 0:
            # Use previous detections for skipped frames (for tracking continuity)
            return self.get_previous_counts(), []

        with torch.no_grad():
            results = self.model.track(
                frame, persist=True, conf=self.conf_threshold,
                classes=list(self.vehicle_classes.keys()), verbose=False,
                device=Config.DEVICE, tracker="bytetrack.yaml"  # Use ByteTrack for better tracking
            )

        current_counts = defaultdict(int)
        active_detections = []

        if results[0].boxes is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy() if results[0].boxes.id is not None else np.arange(len(boxes))
            class_ids = results[0].boxes.cls.int().cpu().numpy()
            confidences = results[0].boxes.conf.float().cpu().numpy()

            for i, (box, track_id, class_id, conf) in enumerate(zip(boxes, track_ids, class_ids, confidences)):
                if class_id in self.vehicle_classes:
                    x1, y1, x2, y2 = map(int, box)
                    w, h = x2 - x1, y2 - y1
                    class_name = self.vehicle_classes[class_id]

                    # Update track history
                    center_x, center_y = x1 + w//2, y1 + h//2
                    self.track_history[track_id].append((center_x, center_y))

                    if self.is_in_counting_zone(x1, y1, w, h):
                        current_counts[class_name] += 1
                        
                        if track_id not in self.crossed_objects:
                            self.vehicle_counts[class_name] += 1
                            self.crossed_objects.add(track_id)

                        active_detections.append({
                            'track_id': int(track_id), 
                            'class_name': class_name,
                            'bbox': [x1, y1, w, h], 
                            'confidence': float(conf),
                            'center': (center_x, center_y)
                        })

        return current_counts, active_detections

    def get_previous_counts(self):
        """Get counts from previous frame for tracking continuity"""
        if not self.frame_analyses:
            return defaultdict(int)
        return defaultdict(int, self.frame_analyses[-1]['current_counts'])

    def analyze_video(self, video_path, progress_tracker=None, save_output=True):
        """Main function to analyze entire video with optional video output"""
        print(f"Starting video analysis: {video_path}")
        
        if progress_tracker:
            progress_tracker.set_progress(0, "Initializing video analysis...")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception(f"Cannot open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"Video info: {width}x{height}, {fps} FPS, {total_frames} frames")

        # Setup video writer for output - FIXED PATH HANDLING
        output_path = None
        out = None
        if save_output:
            # Create output directory if it doesn't exist
            os.makedirs('media/processed_videos', exist_ok=True)
            original_filename = os.path.basename(video_path)
            name_without_ext = os.path.splitext(original_filename)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"processed_{name_without_ext}_{timestamp}.mp4"
            output_path = os.path.join('media/processed_videos', output_filename)
            
            print(f"Output video will be saved to: {output_path}")
            
            # Use same codec and FPS as input
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                print("✗ Failed to initialize video writer")
                output_path = None
            else:
                print("✓ Video writer initialized successfully")

        if progress_tracker:
            progress_tracker.set_progress(5, f"Video info: {total_frames} frames, {fps:.2f} FPS")

        # Setup counting zone
        ret, frame = cap.read()
        if not ret:
            raise Exception("Cannot read video frame")
        self.setup_counting_zone(frame)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        frame_number = 0
        analysis_start = time.time()
        frames_written = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_counts, detections = self.detect_and_track(frame, frame_number)
            total_current_vehicles = sum(current_counts.values())
            
            # Draw detection information on frame
            annotated_frame = self.draw_detection_info(
                frame.copy(), detections, frame_number, fps, total_current_vehicles
            )
            
            # Write to output video
            if out is not None:
                out.write(annotated_frame)
                frames_written += 1
            
            timestamp = frame_number / fps
            frame_analysis = {
                'frame_number': frame_number, 
                'timestamp': timestamp,
                'current_counts': dict(current_counts), 
                'detections': detections,
                'total_vehicles': total_current_vehicles
            }
            self.frame_analyses.append(frame_analysis)

            # Update progress
            if progress_tracker and frame_number % 50 == 0:
                progress = min(95, int((frame_number / total_frames) * 100))
                message = f"Processing frame {frame_number}/{total_frames} ({progress}%)"
                progress_tracker.set_progress(progress, message)

            frame_number += 1

        total_processing_time = time.time() - analysis_start
        cap.release()
        
        if out is not None:
            out.release()
            print(f"✓ Processed video saved: {output_path}")
            print(f"✓ Frames written: {frames_written}/{total_frames}")

        if progress_tracker:
            progress_tracker.set_progress(100, "Analysis completed! Generating report...")

        print(f"Analysis completed in {total_processing_time:.2f} seconds")
        
        report = self.generate_comprehensive_report(duration, total_processing_time)
        if output_path:
            report['output_video_path'] = output_path
            
        return report

    def generate_comprehensive_report(self, video_duration, processing_time):
        """Generate detailed analysis report"""
        total_vehicles = sum(self.vehicle_counts.values())
        avg_vehicles_per_minute = (total_vehicles / video_duration) * 60 if video_duration > 0 else 0
        
        frame_totals = [frame['total_vehicles'] for frame in self.frame_analyses]
        peak_traffic = max(frame_totals) if frame_totals else 0
        avg_traffic = np.mean(frame_totals) if frame_totals else 0

        # Calculate accuracy metrics
        detection_confidence = []
        for frame in self.frame_analyses:
            for detection in frame['detections']:
                detection_confidence.append(detection['confidence'])
        
        avg_confidence = np.mean(detection_confidence) if detection_confidence else 0

        report = {
            'metadata': {
                'video_duration': video_duration, 
                'processing_time': processing_time,
                'total_frames_processed': len(self.frame_analyses),
                'analysis_date': datetime.now().isoformat(),
                'model_confidence_threshold': self.conf_threshold,
                'average_detection_confidence': round(avg_confidence, 3)
            },
            'summary': {
                'total_vehicles_counted': total_vehicles,
                'vehicle_breakdown': dict(self.vehicle_counts),
                'peak_traffic': peak_traffic,
                'average_traffic_density': round(avg_traffic, 2)
            },
            'metrics': {
                'vehicles_per_minute': round(avg_vehicles_per_minute, 2),
                'congestion_level': self.assess_congestion_level(avg_traffic),
                'traffic_pattern': self.identify_traffic_pattern(),
                'processing_efficiency': round(len(self.frame_analyses) / processing_time, 2) if processing_time > 0 else 0
            },
            'performance': {
                'hardware_used': 'GPU' if Config.DEVICE == 'cuda' else 'CPU',
                'frames_per_second': len(self.frame_analyses) / processing_time if processing_time > 0 else 0,
                'real_time_factor': processing_time / video_duration if video_duration > 0 else 0
            },
            'visualization': {
                'counting_zone': {
                    'top': self.zone_top,
                    'bottom': self.zone_bottom,
                    'left': self.zone_left,
                    'right': self.zone_right
                },
                'colors_used': self.colors
            }
        }
        
        return report

    def assess_congestion_level(self, avg_traffic):
        if avg_traffic > 8: return 'High Congestion'
        elif avg_traffic > 4: return 'Moderate Congestion'
        else: return 'Light Traffic'

    def identify_traffic_pattern(self):
        if len(self.frame_analyses) < 10: return 'Insufficient Data'
        first_half = np.mean([f['total_vehicles'] for f in self.frame_analyses[:len(self.frame_analyses)//2]])
        second_half = np.mean([f['total_vehicles'] for f in self.frame_analyses[len(self.frame_analyses)//2:]])
        if second_half > first_half * 1.2: return 'Increasing'
        elif second_half < first_half * 0.8: return 'Decreasing'
        else: return 'Stable'