import threading
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
    MODEL_PATH = 'yolov8l.pt'
    VEHICLE_CLASSES = {
        2: 'car',
        3: 'motorcycle', 
        5: 'bus',
        7: 'truck',
        1: 'bicycle'
    }
    CONFIDENCE_THRESHOLD = 0.3  # Lower threshold for better detection
    PROCESS_EVERY_N_FRAMES = 1  # Process every frame for better counting accuracy
    
    # Counting zone settings (will be set dynamically)
    ZONE_HEIGHT_RATIO = (0.60, 0.85)  # 60% to 85% of frame height
    ZONE_WIDTH_RATIO = (0.05, 0.95)   # 5% to 95% of frame width

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
        """Setup higher counting zone to capture vehicles earlier"""
        height, width = frame.shape[:2]
        
        # HIGHER COUNTING ZONE: Positioned in the upper part of the frame
        # Use 30% to 60% of frame height (moved much higher)
        self.zone_top = int(height * 0.30)     # 30% from top (much higher)
        self.zone_bottom = int(height * 0.60)  # 60% from top (still high)
        
        # Maintain wide horizontal coverage
        self.zone_left = int(width * 0.05)     # 5% from left
        self.zone_right = int(width * 0.95)    # 95% from left
        
        # Visual settings
        self.zone_color = (0, 255, 255)  # Bright yellow
        self.zone_thickness = 3
        
        print(f"✓ HIGHER Counting zone configured: {self.zone_top}-{self.zone_bottom}px height")
        print(f"  Covers {self.zone_bottom - self.zone_top}px tall area")
        print(f"  Position: Top {int((self.zone_top/height)*100)}% to {int((self.zone_bottom/height)*100)}% of frame")
        
        return {
            'top': self.zone_top, 'bottom': self.zone_bottom,
            'left': self.zone_left, 'right': self.zone_right
        }

    def is_in_counting_zone(self, x, y, w, h):
        """Enhanced detection for higher counting zone position"""
        center_x, center_y = x + w/2, y + h/2
        
        # For higher zone, be more sensitive to vehicles entering from top
        # Option 1: Center point in zone (standard)
        center_in_zone = (self.zone_left <= center_x <= self.zone_right and 
                        self.zone_top <= center_y <= self.zone_bottom)
        
        # Option 2: Any corner in zone
        corners = [
            (x, y),           # top-left
            (x + w, y),       # top-right  
            (x, y + h),       # bottom-left
            (x + w, y + h)    # bottom-right
        ]
        
        any_corner_in_zone = any(
            self.zone_left <= corner_x <= self.zone_right and 
            self.zone_top <= corner_y <= self.zone_bottom
            for corner_x, corner_y in corners
        )
        
        # Option 3: Significant overlap with zone
        bbox_in_zone = (
            x < self.zone_right and x + w > self.zone_left and
            y < self.zone_bottom and y + h > self.zone_top
        )
        
        # Option 4: For higher zone, also count if bottom of vehicle enters zone
        # This helps catch vehicles as they first appear
        bottom_center_in_zone = (
            self.zone_left <= center_x <= self.zone_right and
            self.zone_top <= (y + h) <= self.zone_bottom
        )
        
        # Use multiple conditions for better detection in higher position
        return center_in_zone or any_corner_in_zone or bbox_in_zone or bottom_center_in_zone

    def draw_detection_info(self, frame, detections, frame_number, fps, total_vehicles):
        """Draw detection information with clear higher counting zone visualization"""
        height, width = frame.shape[:2]
        
        # Draw the higher counting zone with enhanced visibility
        # Main counting zone rectangle
        cv2.rectangle(frame, 
                    (self.zone_left, self.zone_top), 
                    (self.zone_right, self.zone_bottom), 
                    self.zone_color, self.zone_thickness)
        
        # Add semi-transparent fill with different color for higher zone
        overlay = frame.copy()
        cv2.rectangle(overlay,
                    (self.zone_left, self.zone_top),
                    (self.zone_right, self.zone_bottom),
                    (255, 255, 0), -1)  # Cyan fill for higher zone
        cv2.addWeighted(overlay, 0.08, frame, 0.92, 0, frame)
        
        # Draw zone boundary again
        cv2.rectangle(frame, 
                    (self.zone_left, self.zone_top), 
                    (self.zone_right, self.zone_bottom), 
                    self.zone_color, self.zone_thickness)
        
        # Draw zone label with "HIGHER ZONE" indication
        zone_label = "HIGHER COUNTING ZONE"
        label_bg_size = cv2.getTextSize(zone_label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        
        # Label background
        cv2.rectangle(frame,
                    (self.zone_left, self.zone_top - label_bg_size[1] - 10),
                    (self.zone_left + label_bg_size[0] + 10, self.zone_top),
                    (0, 0, 0), -1)
        
        # Zone label text
        cv2.putText(frame, zone_label, (self.zone_left + 5, self.zone_top - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Draw zone position indicator
        position_text = f"Position: Top {int((self.zone_top/height)*100)}%-{int((self.zone_bottom/height)*100)}%"
        cv2.putText(frame, position_text, (self.zone_left, self.zone_bottom + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.zone_color, 1)
        
        # Draw entry direction indicator (since zone is higher)
        direction_text = "↑ Vehicles counted as they enter frame ↑"
        text_size = cv2.getTextSize(direction_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        text_x = (width - text_size[0]) // 2
        cv2.putText(frame, direction_text, (text_x, self.zone_top - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw detections with enhanced visualization for higher zone
        for detection in detections:
            x1, y1, w, h = detection['bbox']
            class_name = detection['class_name']
            confidence = detection['confidence']
            track_id = detection.get('track_id', 0)
            in_zone = detection.get('in_zone', False)
            zone_entry = detection.get('zone_entry')
            
            color = self.colors.get(class_name, self.colors['other'])
            
            # Thicker bounding box and different color for vehicles in counting zone
            thickness = 4 if in_zone else 2
            bbox_color = (0, 255, 0) if in_zone else color  # Green when in zone
            
            cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), bbox_color, thickness)
            
            # Draw label
            label = f"{class_name} {confidence:.2f} ID:{track_id}"
            if in_zone:
                label += " ✓IN ZONE"
            
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # Label background
            label_bg_color = (0, 100, 0) if in_zone else color
            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                        (x1 + label_size[0], y1), label_bg_color, -1)
            
            # Label text
            cv2.putText(frame, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Draw center point
            center_x, center_y = x1 + w//2, y1 + h//2
            point_color = (0, 255, 0) if in_zone else color
            cv2.circle(frame, (center_x, center_y), 5, point_color, -1)
            
            # Draw entry point if available
            if zone_entry:
                cv2.circle(frame, (int(zone_entry[0]), int(zone_entry[1])), 8, (0, 255, 255), -1)
                cv2.circle(frame, (int(zone_entry[0]), int(zone_entry[1])), 8, (0, 0, 0), 2)
            
            # Draw track history (emphasized for vehicles that entered zone)
            if track_id in self.track_history and in_zone:
                points = list(self.track_history[track_id])
                for i in range(1, len(points)):
                    # Use gradient color - darker for older points
                    alpha = i / len(points)
                    line_color = (
                        int(color[0] * alpha),
                        int(color[1] * alpha), 
                        int(color[2] * alpha)
                    )
                    cv2.line(frame, points[i-1], points[i], line_color, 2)
        
        # Draw statistics overlay
        self.draw_statistics_overlay(frame, frame_number, fps, total_vehicles, detections)
        
        return frame

    def draw_statistics_overlay(self, frame, frame_number, fps, total_vehicles, detections):
        """Draw enhanced statistics overlay for higher counting zone"""
        height, width = frame.shape[:2]
        
        # Create semi-transparent overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (380, 240), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Current time in video
        current_time = frame_number / fps if fps > 0 else 0
        minutes = int(current_time // 60)
        seconds = int(current_time % 60)
        
        # Count vehicles currently in zone
        vehicles_in_zone = sum(1 for d in detections if d.get('in_zone', False))
        
        # Enhanced statistics with higher zone info
        stats = [
            f"Time: {minutes:02d}:{seconds:02d}",
            f"Frame: {frame_number}",
            f"FPS: {fps:.1f}",
            f"TOTAL COUNTED: {sum(self.vehicle_counts.values())}",
            f"IN HIGHER ZONE NOW: {vehicles_in_zone}",
            f"Zone Position: Top {int((self.zone_top/height)*100)}%-{int((self.zone_bottom/height)*100)}%",
            f"Zone Size: {self.zone_bottom - self.zone_top}h x {self.zone_right - self.zone_left}w",
            "CURRENT IN ZONE:"
        ]
        
        # Add vehicle counts currently in zone
        current_counts = {}
        for detection in detections:
            if detection.get('in_zone', False):
                class_name = detection['class_name']
                current_counts[class_name] = current_counts.get(class_name, 0) + 1
        
        for class_name in sorted(current_counts.keys()):
            stats.append(f"  {class_name}: {current_counts[class_name]}")
        
        # Draw statistics with color coding
        y_offset = 40
        for i, text in enumerate(stats):
            color = (255, 255, 255)  # White default
            
            if i == 3:  # Total counted line
                color = (0, 255, 255)  # Yellow
            elif i == 4:  # In zone now line
                color = (0, 255, 0)    # Green
            elif i == 5:  # Zone position
                color = (255, 255, 0)  # Cyan
            elif i >= 7:  # Vehicle counts
                class_name = text.split(':')[0].strip()
                color = self.colors.get(class_name, (255, 255, 255))
            
            cv2.putText(frame, text, (20, y_offset + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
    def detect_and_track(self, frame, frame_number):
        """Perform detection and tracking with enhanced logic for higher counting zone"""
        if frame_number % Config.PROCESS_EVERY_N_FRAMES != 0 and frame_number > 0:
            return self.get_previous_counts(), []

        with torch.no_grad():
            results = self.model.track(
                frame, persist=True, conf=self.conf_threshold,
                classes=list(self.vehicle_classes.keys()), verbose=False,
                device=Config.DEVICE, tracker="bytetrack.yaml"
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

                    # Enhanced counting logic for higher zone
                    in_zone = self.is_in_counting_zone(x1, y1, w, h)
                    
                    if in_zone:
                        current_counts[class_name] += 1
                        
                        # Only count if this track_id hasn't been counted recently
                        # For higher zone, we might see vehicles for longer, so track carefully
                        if track_id not in self.crossed_objects:
                            self.vehicle_counts[class_name] += 1
                            self.crossed_objects.add(track_id)
                            print(f"✓ Counted {class_name} (ID: {track_id}) in HIGHER zone")
                            
                            # Optional: Add small delay before allowing re-count (for vehicles that linger)
                            # This prevents double-counting in higher zones where vehicles stay visible longer
                            threading.Timer(2.0, self._remove_from_crossed, [track_id]).start()

                        active_detections.append({
                            'track_id': int(track_id), 
                            'class_name': class_name,
                            'bbox': [x1, y1, w, h], 
                            'confidence': float(conf),
                            'center': (center_x, center_y),
                            'in_zone': True,
                            'zone_entry': self._get_zone_entry_point(track_id)
                        })
                    else:
                        active_detections.append({
                            'track_id': int(track_id), 
                            'class_name': class_name,
                            'bbox': [x1, y1, w, h], 
                            'confidence': float(conf),
                            'center': (center_x, center_y),
                            'in_zone': False
                        })

        return current_counts, active_detections

    def _remove_from_crossed(self, track_id):
        """Remove track_id from crossed objects after delay to prevent double-counting"""
        if track_id in self.crossed_objects:
            self.crossed_objects.remove(track_id)

    def _get_zone_entry_point(self, track_id):
        """Get the point where vehicle entered the counting zone"""
        if track_id in self.track_history:
            points = list(self.track_history[track_id])
            for point in reversed(points):  # Check from most recent backwards
                if (self.zone_left <= point[0] <= self.zone_right and 
                    self.zone_top <= point[1] <= self.zone_bottom):
                    return point
        return None

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