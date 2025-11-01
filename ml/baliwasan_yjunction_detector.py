import cv2
import torch
from ultralytics import YOLO
import os
import numpy as np
import time
from collections import defaultdict, deque
import threading

# ADD THIS IMPORT
from .base_detector import BaseDetector

class BaliwasanYJunctionDetector(BaseDetector):
    def __init__(self, model_path='yolov8x.pt'):
        # Initialize base class
        super().__init__()
        
        print("🚀 Initializing YOLO model for Baliwasan Y-Junction...")
        
        # FORCE DEDICATED GPU USAGE
        import os
        os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Force GPU 0
        
        # Check GPU availability
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🖥️  Using device: {self.device}")
        
        if self.device == 'cuda':
            print(f"🎮 GPU: {torch.cuda.get_device_name()}")
            print(f"🎮 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        
        # Load model with EXACT SAME SETTINGS as old detector
        self.model = YOLO(model_path)
        
        # Move model to GPU (ONLY performance change)
        if self.device == 'cuda':
            self.model.model.to(self.device)
            print("✅ Model moved to GPU")
        
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
        
        # Vehicle type colors and names
        self.vehicle_colors = {
            2: (0, 255, 0),    # car - green
            3: (255, 255, 0),  # motorcycle - yellow
            5: (0, 0, 255),    # bus - red
            7: (255, 0, 0)     # truck - blue
        }
        
        self.vehicle_names = {
            2: "car",
            3: "motorcycle", 
            5: "bus",
            7: "truck"
        }
        
        # Tracking variables (will be reset for each video)
        self.track_history = None
        self.vehicle_status = None
        self.vehicle_type_counts = None
        self.vehicle_crossed = None
        self.frame_count = 0
        self.total_count = 0
        
        print("✅ Baliwasan Y-Junction Detector initialized successfully")

    def analyze_video(self, video_path, progress_tracker=None, save_output=True):
        """EXACT SAME as old detector but with GPU acceleration"""
        print(f"🎯 Starting Baliwasan Y-Junction analysis: {video_path}")
        
        # Initialize tracking for this video (SAME AS OLD)
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status = {}
        self.vehicle_type_counts = defaultdict(int)
        self.vehicle_crossed = set()
        self.frame_count = 0
        self.total_count = 0
        
        # ENHANCED: Initialize enhanced metrics
        self.setup_enhanced_metrics()
        
        if progress_tracker:
            progress_tracker.set_progress(10, "Opening video file...")
        
        # Open the provided video path
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            error_msg = f"❌ Error: Could not open video file: {video_path}"
            print(error_msg)
            raise Exception(error_msg)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"📊 Video Info: {width}x{height}, {fps:.1f} FPS, {total_frames} frames")

        # Setup counting zone for Baliwasan Y-Junction (SAME AS OLD)
        OFFSET_Y = -90
        self.line_start = (0, int(height * 0.45) + OFFSET_Y)
        self.line_end = (width - 1, int(height * 0.38) + OFFSET_Y)
        
        # Create counting zone (buffer area around the line)
        ZONE_BUFFER = 25  # pixels
        self.counting_zone_top = self.line_start[1] - ZONE_BUFFER
        self.counting_zone_bottom = self.line_start[1] + ZONE_BUFFER

        # Setup output video if requested (SAME AS OLD)
        output_video_path = None
        out = None
        if save_output:
            os.makedirs('media/processed_videos', exist_ok=True)
            original_filename = os.path.basename(video_path)
            name_without_ext = os.path.splitext(original_filename)[0]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_filename = f"baliwasan_processed_{name_without_ext}_{timestamp}.mp4"
            output_video_path = os.path.join('media/processed_videos', output_filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
            print(f"💾 Saving output to: {output_video_path}")

        if progress_tracker:
            progress_tracker.set_progress(20, "Starting vehicle detection with enhanced metrics...")

        print(f"📏 Counting line: {self.line_start} to {self.line_end}")
        print("🎯 Starting vehicle counting with enhanced metrics...")

        processing_times = []
        analysis_start = time.time()

        # Main processing loop - PROCESS EVERY FRAME LIKE OLD DETECTOR
        while cap.isOpened():
            frame_start = time.time()
            ret, frame = cap.read()
            if not ret:
                break

            self.frame_count += 1
            
            # NO FRAME SKIPPING - PROCESS EVERY FRAME LIKE OLD DETECTOR
            frame_copy = frame.copy()
            
            # Draw counting zone background for better visibility (SAME AS OLD)
            zone_overlay = frame_copy.copy()
            cv2.rectangle(zone_overlay, (0, self.counting_zone_top), (width, self.counting_zone_bottom), (0, 100, 0), -1)
            cv2.addWeighted(zone_overlay, 0.2, frame_copy, 0.8, 0, frame_copy)
            
            # Draw counting line with better visibility (SAME AS OLD)
            cv2.line(frame_copy, self.line_start, self.line_end, (0, 0, 255), 4)
            cv2.putText(frame_copy, "COUNTING LINE", (self.line_start[0], self.line_start[1] - 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            # Process frame with EXACT SAME LOGIC as old detector
            current_counts, detections = self.process_frame(frame, self.frame_count, fps)
            
            # ENHANCED: UPDATE ALL METRICS
            current_time_seconds = self.frame_count / fps if fps > 0 else 0
            
            # 1. Update hourly breakdown
            self.update_hourly_data(current_counts, current_time_seconds)
            
            # 2. Update quality metrics
            self.update_quality_metrics(detections, current_counts)
            
            # Draw detection information (SAME AS OLD)
            annotated_frame = self.draw_detection_info(
                frame_copy, detections, self.frame_count, fps, sum(current_counts.values())
            )
            
            # Write to output video
            if out is not None:
                out.write(annotated_frame)

            # Calculate processing time
            processing_time = time.time() - frame_start
            processing_times.append(processing_time)
            
            # Update progress (SAME AS OLD)
            if progress_tracker and self.frame_count % 10 == 0:
                progress = min(90, 20 + int((self.frame_count / total_frames) * 70))
                message = f"Processing frame {self.frame_count}/{total_frames} - Enhanced metrics collection"
                progress_tracker.set_progress(progress, message)

        # Cleanup
        cap.release()
        if out is not None:
            out.release()
            print(f"✅ Processed video saved: {output_video_path}")

        total_processing_time = time.time() - analysis_start
        print(f"✅ Baliwasan analysis completed in {total_processing_time:.2f}s")
        
        if progress_tracker:
            progress_tracker.set_progress(95, "Generating enhanced analysis report...")

        # GENERATE ENHANCED REPORT
        enhanced_metrics = self.get_enhanced_metrics_report(
            total_vehicles=self.total_count,
            video_duration=total_frames / fps if fps > 0 else 0,
            fps=fps,
            frame_width=width,
            total_frames=self.frame_count
        )

        # Generate comprehensive report
        report = self.generate_comprehensive_report(total_frames, total_processing_time, fps, enhanced_metrics)
        if output_video_path:
            report['output_video_path'] = output_video_path
            
        return report

    def process_frame(self, frame, frame_number, fps):
        """EXACT SAME LOGIC as old detector process_frame method"""
        current_counts = defaultdict(int)
        active_detections = []

        # USE EXACT SAME SETTINGS AS OLD DETECTOR
        results = self.model.track(
            frame, 
            persist=True, 
            conf=0.4,  # SAME AS OLD: 0.4 confidence
            classes=self.vehicle_classes, 
            tracker="bytetrack.yaml",
            verbose=False,
            # NO imgsz parameter (let YOLO use default like old detector)
            # ONLY ADD GPU SETTINGS FOR PERFORMANCE:
            device=self.device,  # Use GPU if available
            # NO half precision (might affect accuracy)
            # NO max_det limit (use default like old detector)
        )

        if results[0].boxes is not None and results[0].boxes.id is not None:
            # Move tensors to CPU for processing
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy()
            class_ids = results[0].boxes.cls.int().cpu().numpy()
            confidences = results[0].boxes.conf.float().cpu().numpy()

            for i, (box, track_id, class_id, conf) in enumerate(zip(boxes, track_ids, class_ids, confidences)):
                x1, y1, x2, y2 = map(int, box)
                track_id = int(track_id)
                class_id = int(class_id)
                confidence = float(conf)

                # Calculate center point (SAME AS OLD)
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                # Get vehicle color and name (SAME AS OLD)
                vehicle_name = self.vehicle_names.get(class_id, "unknown")
                vehicle_color = self.vehicle_colors.get(class_id, (255, 255, 255))

                # Initialize tracking for new vehicles (SAME AS OLD)
                if track_id not in self.vehicle_status:
                    self.vehicle_status[track_id] = {
                        'class_id': class_id,
                        'class_name': vehicle_name,
                        'crossed': False,
                        'last_y': cy,
                        'first_seen': frame_number,
                        'confidence': confidence
                    }

                # Update track history (SAME AS OLD)
                self.track_history[track_id].append((cx, cy))
                current_status = self.vehicle_status[track_id]

                # Calculate line Y position at current X (SAME AS OLD)
                line_y_at_cx = self.get_line_y_at_x(cx)

                # Check if vehicle is in counting zone (SAME AS OLD)
                in_counting_zone = self.counting_zone_top <= cy <= self.counting_zone_bottom

                # ENHANCED: CALCULATE SPEED (optional addition)
                speed = self.calculate_speed(track_id, (cx, cy), frame_number, fps)

                # COUNTING LOGIC - EXACT SAME AS OLD DETECTOR
                if in_counting_zone and not current_status['crossed']:
                    prev_y = current_status['last_y']
                    current_y = cy

                    # EXACT SAME CROSSING DETECTION AS OLD
                    if (prev_y < line_y_at_cx and current_y >= line_y_at_cx and 
                        self.is_valid_trajectory(self.track_history[track_id], current_y, line_y_at_cx)):
                        
                        # Vehicle crossed the line top → bottom
                        current_status['crossed'] = True
                        self.vehicle_crossed.add(track_id)
                        self.total_count += 1
                        self.vehicle_type_counts[class_id] += 1

                        print(f"✅ #{self.total_count:03d} {vehicle_name} ID:{track_id} "
                              f"crossed at ({cx},{cy}) - Conf: {confidence:.2f}")

                    # Update last position
                    current_status['last_y'] = current_y

                # Count current vehicles in zone (SAME AS OLD)
                if in_counting_zone:
                    current_counts[vehicle_name] += 1

                active_detections.append({
                    'track_id': track_id,
                    'class_name': vehicle_name,
                    'bbox': [x1, y1, x2-x1, y2-y1],  # SAME FORMAT AS OLD
                    'confidence': confidence,
                    'center': (cx, cy),
                    'in_zone': in_counting_zone,
                    'speed': speed  # Optional enhancement
                })

                # ENHANCED: STORE SPEED DATA (optional)
                if speed is not None:
                    self.speed_data[vehicle_name].append(speed)

        return current_counts, active_detections

    def get_line_y_at_x(self, cx):
        """Calculate line Y position at given X coordinate (SAME AS OLD)"""
        x1_l, y1_l = self.line_start
        x2_l, y2_l = self.line_end
        if x2_l != x1_l:
            slope = (y2_l - y1_l) / (x2_l - x1_l)
            return y1_l + slope * (cx - x1_l)
        return y1_l

    def is_valid_trajectory(self, positions, current_y, line_y):
        """EXACT SAME as old detector trajectory validation"""
        if len(positions) < 3:
            return True  # Not enough data yet
        
        # Check if vehicle is consistently moving downward
        recent_positions = list(positions)[-5:]  # Last 5 positions
        if len(recent_positions) < 2:
            return True
            
        y_values = [pos[1] for pos in recent_positions]
        if all(y2 >= y1 for y1, y2 in zip(y_values[:-1], y_values[1:])):
            return True  # Consistently moving downward
        
        return False

    # Keep the rest of your methods exactly the same as your old detector
    def draw_detection_info(self, frame, detections, frame_number, fps, total_current_vehicles):
        """EXACT SAME as old detector"""
        height, width = frame.shape[:2]
        
        # Enhanced statistics panel
        stats = [
            f"BALIWASAN Y-JUNCTION ANALYSIS",
            f"Total Count: {self.total_count}",
            f"Frame: {frame_number}",
            f"Current in zone: {total_current_vehicles}",
            f"Active tracks: {len(self.track_history)}"
        ]
        
        # Draw statistics
        for i, text in enumerate(stats):
            color = (255, 255, 255)
            if "BALIWASAN" in text:
                color = (0, 255, 255)  # Yellow for title
            elif "Total Count" in text:
                color = (0, 255, 0)    # Green for count
            cv2.putText(frame, text, (20, 30 + i * 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # Draw detections
        for detection in detections:
            x1, y1, w, h = detection['bbox']
            class_name = detection['class_name']
            confidence = detection['confidence']
            track_id = detection['track_id']
            in_zone = detection['in_zone']
            speed = detection.get('speed')

            color = self.vehicle_colors.get(
                list(self.vehicle_names.keys())[list(self.vehicle_names.values()).index(class_name)], 
                (255, 255, 255)
            )

            # Draw bounding box
            thickness = 3 if in_zone else 2
            cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), color, thickness)
            
            # Draw label with speed information
            label = f"{class_name} {confidence:.2f}"
            if speed:
                label += f" {speed:.1f}km/h"
            if in_zone:
                label += " ✓IN ZONE"
            
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                        (x1 + label_size[0], y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame

    def generate_comprehensive_report(self, total_frames, processing_time, fps, enhanced_metrics):
        """EXACT SAME as old detector"""
        total_vehicles = self.total_count
        video_duration = total_frames / fps if fps > 0 else 0
        
        # Calculate vehicle breakdown
        vehicle_breakdown = {}
        for class_id, count in self.vehicle_type_counts.items():
            vehicle_name = self.vehicle_names.get(class_id, "unknown")
            vehicle_breakdown[vehicle_name.lower()] = count

        # Ensure all vehicle types are present
        for vehicle_name in ['car', 'truck', 'bus', 'motorcycle']:
            if vehicle_name not in vehicle_breakdown:
                vehicle_breakdown[vehicle_name] = 0

        # Calculate metrics
        avg_vehicles_per_minute = (total_vehicles / video_duration) * 60 if video_duration > 0 else 0
        
        # Determine congestion level
        if avg_vehicles_per_minute > 100:
            congestion_level = 'high'
        elif avg_vehicles_per_minute > 50:
            congestion_level = 'medium'
        else:
            congestion_level = 'low'

        report = {
            'metadata': {
                'video_duration': video_duration,
                'processing_time': processing_time,
                'total_frames_processed': total_frames,
                'analysis_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'detector_type': 'BaliwasanYJunctionDetector',
                'location_specific': True
            },
            'summary': {
                'total_vehicles_counted': total_vehicles,
                'vehicle_breakdown': vehicle_breakdown,
                'peak_traffic': max(self.vehicle_type_counts.values()) if self.vehicle_type_counts else 0,
                'average_traffic_density': total_vehicles / video_duration if video_duration > 0 else 0
            },
            'metrics': {
                'vehicles_per_minute': round(avg_vehicles_per_minute, 2),
                'congestion_level': congestion_level,
                'traffic_pattern': 'stable',
                'processing_efficiency': round(total_frames / processing_time, 2) if processing_time > 0 else 0
            },
            'baliwasan_specific': {
                'counting_zone_top': self.counting_zone_top,
                'counting_zone_bottom': self.counting_zone_bottom,
                'unique_tracks_counted': len(self.vehicle_crossed),
                'y_junction_optimized': True
            },
            'enhanced_metrics': enhanced_metrics
        }
        
        return report

# For standalone testing
if __name__ == "__main__":
    detector = BaliwasanYJunctionDetector()
    detector.analyze_video("test_video.mp4")