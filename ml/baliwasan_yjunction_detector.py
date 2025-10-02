# ml/baliwasan_yjunction_detector.py
import cv2
from ultralytics import YOLO
import os
import numpy as np
import time
from collections import defaultdict, deque
import threading

class BaliwasanYJunctionDetector:
    def __init__(self, model_path='yolov8x.pt'):
        print("🚀 Initializing YOLO model for Baliwasan Y-Junction...")
        self.model = YOLO(model_path)
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
        
        # Vehicle type colors and names
        self.vehicle_colors = {
            2: (0, 255, 0),    # car - green
            3: (255, 255, 0),  # motorcycle - yellow
            5: (0, 0, 255),    # bus - red
            7: (255, 0, 0)     # truck - blue
        }
        
        self.vehicle_names = {
            2: "Car",
            3: "Motorcycle", 
            5: "Bus",
            7: "Truck"
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
        """Main method to analyze video - compatible with Django system"""
        print(f"🎯 Starting Baliwasan Y-Junction analysis: {video_path}")
        
        # Initialize tracking for this video
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status = {}
        self.vehicle_type_counts = defaultdict(int)
        self.vehicle_crossed = set()
        self.frame_count = 0
        self.total_count = 0
        
        if progress_tracker:
            progress_tracker.set_progress(10, "Opening video file...")
        
        # Open the provided video path (not hardcoded)
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

        # Setup counting zone for Baliwasan Y-Junction
        OFFSET_Y = -90
        self.line_start = (0, int(height * 0.45) + OFFSET_Y)
        self.line_end = (width - 1, int(height * 0.38) + OFFSET_Y)
        
        # Create counting zone (buffer area around the line)
        ZONE_BUFFER = 25  # pixels
        self.counting_zone_top = self.line_start[1] - ZONE_BUFFER
        self.counting_zone_bottom = self.line_start[1] + ZONE_BUFFER

        # Setup output video if requested - LIKE RTXVehicleDetector
        output_video_path = None
        out = None
        if save_output:
            # Create output directory if it doesn't exist
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
            progress_tracker.set_progress(20, "Starting vehicle detection...")

        print(f"📏 Counting line: {self.line_start} to {self.line_end}")
        print("🎯 Starting vehicle counting...")

        processing_times = []
        analysis_start = time.time()

        # Main processing loop
        while cap.isOpened():
            frame_start = time.time()
            ret, frame = cap.read()
            if not ret:
                break

            self.frame_count += 1
            frame_copy = frame.copy()
            
            # Draw counting zone background for better visibility
            zone_overlay = frame_copy.copy()
            cv2.rectangle(zone_overlay, (0, self.counting_zone_top), (width, self.counting_zone_bottom), (0, 100, 0), -1)
            cv2.addWeighted(zone_overlay, 0.2, frame_copy, 0.8, 0, frame_copy)
            
            # Draw counting line with better visibility
            cv2.line(frame_copy, self.line_start, self.line_end, (0, 0, 255), 4)
            cv2.putText(frame_copy, "COUNTING LINE", (self.line_start[0], self.line_start[1] - 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            # Process frame
            current_counts, detections = self.process_frame(frame, self.frame_count)
            
            # Draw detection information
            annotated_frame = self.draw_detection_info(
                frame_copy, detections, self.frame_count, fps, sum(current_counts.values())
            )
            
            # Write to output video - LIKE RTXVehicleDetector
            if out is not None:
                out.write(annotated_frame)

            # Calculate processing time
            processing_time = time.time() - frame_start
            processing_times.append(processing_time)
            
            # Update progress
            if progress_tracker and self.frame_count % 10 == 0:
                progress = min(90, 20 + int((self.frame_count / total_frames) * 70))
                message = f"Processing frame {self.frame_count}/{total_frames} - Count: {self.total_count}"
                progress_tracker.set_progress(progress, message)

        # Cleanup
        cap.release()
        if out is not None:
            out.release()
            print(f"✅ Processed video saved: {output_video_path}")

        total_processing_time = time.time() - analysis_start
        print(f"✅ Baliwasan analysis completed in {total_processing_time:.2f}s")
        
        if progress_tracker:
            progress_tracker.set_progress(95, "Generating analysis report...")

        # Generate comprehensive report - RETURN OUTPUT PATH LIKE RTXVehicleDetector
        report = self.generate_comprehensive_report(total_frames, total_processing_time, fps)
        if output_video_path:
            report['output_video_path'] = output_video_path
            
        return report

    def process_frame(self, frame, frame_number):
        """Process a single frame for vehicle detection and tracking"""
        current_counts = defaultdict(int)
        active_detections = []

        # Use YOLO tracking with optimized settings
        results = self.model.track(
            frame, 
            persist=True, 
            conf=0.4,  # Balanced confidence
            classes=self.vehicle_classes, 
            tracker="bytetrack.yaml",
            verbose=False,
            imgsz=640  # Smaller image size for speed
        )

        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy()
            class_ids = results[0].boxes.cls.int().cpu().numpy()
            confidences = results[0].boxes.conf.float().cpu().numpy()

            for i, (box, track_id, class_id, conf) in enumerate(zip(boxes, track_ids, class_ids, confidences)):
                x1, y1, x2, y2 = map(int, box)
                track_id = int(track_id)
                class_id = int(class_id)
                confidence = float(conf)

                # Calculate center point
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                # Get vehicle color and name
                vehicle_color = self.vehicle_colors.get(class_id, (255, 255, 255))
                vehicle_name = self.vehicle_names.get(class_id, "Unknown")

                # Initialize tracking for new vehicles
                if track_id not in self.vehicle_status:
                    self.vehicle_status[track_id] = {
                        'class_id': class_id,
                        'class_name': vehicle_name,
                        'crossed': False,
                        'last_y': cy,
                        'first_seen': frame_number,
                        'confidence': confidence
                    }

                # Update track history
                self.track_history[track_id].append((cx, cy))
                current_status = self.vehicle_status[track_id]

                # Calculate line Y position at current X
                line_y_at_cx = self.get_line_y_at_x(cx)

                # Check if vehicle is in counting zone
                in_counting_zone = self.counting_zone_top <= cy <= self.counting_zone_bottom

                if in_counting_zone and not current_status['crossed']:
                    prev_y = current_status['last_y']
                    current_y = cy

                    # Enhanced crossing detection with trajectory validation
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

                # Count current vehicles in zone
                if in_counting_zone:
                    current_counts[class_id] += 1

                active_detections.append({
                    'track_id': track_id,
                    'class_name': vehicle_name,
                    'bbox': [x1, y1, x2-x1, y2-y1],
                    'confidence': confidence,
                    'center': (cx, cy),
                    'in_zone': in_counting_zone
                })

        return current_counts, active_detections

    def get_line_y_at_x(self, cx):
        """Calculate line Y position at given X coordinate"""
        x1_l, y1_l = self.line_start
        x2_l, y2_l = self.line_end
        if x2_l != x1_l:
            slope = (y2_l - y1_l) / (x2_l - x1_l)
            return y1_l + slope * (cx - x1_l)
        return y1_l

    def is_valid_trajectory(self, positions, current_y, line_y):
        """Validate if vehicle trajectory makes sense for counting"""
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

    def draw_detection_info(self, frame, detections, frame_number, fps, total_current_vehicles):
        """Draw detection information on frame"""
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

            color = self.vehicle_colors.get(
                list(self.vehicle_names.keys())[list(self.vehicle_names.values()).index(class_name)], 
                (255, 255, 255)
            )

            # Draw bounding box
            thickness = 3 if in_zone else 2
            cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), color, thickness)
            
            # Draw label
            label = f"{class_name} {confidence:.2f}"
            if in_zone:
                label += " ✓IN ZONE"
            
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                        (x1 + label_size[0], y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame

    def generate_comprehensive_report(self, total_frames, processing_time, fps):
        """Generate detailed analysis report in Django-compatible format"""
        total_vehicles = self.total_count
        video_duration = total_frames / fps if fps > 0 else 0
        
        # Calculate vehicle breakdown
        vehicle_breakdown = {}
        for class_id, count in self.vehicle_type_counts.items():
            vehicle_name = self.vehicle_names.get(class_id, "Unknown")
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
                'traffic_pattern': 'stable',  # You can enhance this with pattern analysis
                'processing_efficiency': round(total_frames / processing_time, 2) if processing_time > 0 else 0
            },
            'baliwasan_specific': {
                'counting_zone_top': self.counting_zone_top,
                'counting_zone_bottom': self.counting_zone_bottom,
                'unique_tracks_counted': len(self.vehicle_crossed),
                'y_junction_optimized': True
            }
        }
        
        return report

# For standalone testing
if __name__ == "__main__":
    detector = BaliwasanYJunctionDetector()
    detector.analyze_video("test_video.mp4")