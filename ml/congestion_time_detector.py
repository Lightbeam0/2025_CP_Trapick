# ml/congestion_time_detector.py
import cv2
import torch
import numpy as np
import time
import os
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime
from ultralytics import YOLO
from .base_detector import BaseDetector

class CongestionTimeDetector(BaseDetector):
    """
    Full-Frame Congestion Time Detector - Monitors 100% of screen area
    Tracks congestion duration regardless of vehicle movement direction
    """
    
    def __init__(self, model_path=None, roi_normalized=None, **config):
        super().__init__()
        
        print("\n" + "="*70)
        print("🚦 FULL-FRAME CONGESTION TIME DETECTOR - 100% SCREEN COVERAGE")
        print("="*70)

        # Auto-load collision4 model
        if model_path is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parents[2]
            model_path = project_root / "runs" / "detect" / "collision4_model" / "weights" / "best.pt"
            
            if not model_path.exists():
                raise FileNotFoundError(f"❌ Collision4 model not found at: {model_path}")

        print(f"📂 Loading collision4 model: {Path(model_path).name}")
        self.model = YOLO(str(model_path))
        
        # Device configuration
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        print(f"✅ Device: {self.device.upper()}")

        # Collision4 model classes
        self.class_names = {
            1: 'car',
            2: 'jeep', 
            3: 'motorcycle',
            5: 'tricycle',
            6: 'truck'
        }
        self.counted_classes = list(self.class_names.values())

        # Colors for visualization
        self.colors = {
            "car": (100, 100, 255),
            "jeep": (255, 165, 0),
            "motorcycle": (255, 255, 0),
            "tricycle": (255, 0, 255),
            "truck": (0, 0, 255),
        }

        # FULL-FRAME CONGESTION DETECTION CONFIGURATION
        self.config = {
            # Speed threshold (km/h) - vehicles below this are considered slow/stuck
            'speed_threshold': config.get('speed_threshold', 5.0),
            
            # Stationary threshold (seconds) - vehicles not moving for this long
            'stationary_threshold': config.get('stationary_threshold', 10.0),
            
            # Density threshold - minimum vehicles in FULL FRAME to consider congestion
            'min_vehicles_for_congestion': config.get('min_vehicles_for_congestion', 5),
            
            # Percentage of slow vehicles needed to flag congestion
            'slow_vehicle_ratio': config.get('slow_vehicle_ratio', 0.3),
            
            # Minimum congestion duration to record (seconds)
            'min_congestion_duration': config.get('min_congestion_duration', 30.0),
            
            # FULL FRAME ROI - 100% of screen
            'roi_normalized': [(0.0, 0.0), (1.0, 1.0)],  # ENTIRE FRAME
            
            # Frame sampling rate for efficiency
            'process_every_n_frames': config.get('process_every_n_frames', 2),
            
            # Full-frame specific settings
            'severe_congestion_threshold': config.get('severe_congestion_threshold', 15),
            'high_congestion_threshold': config.get('high_congestion_threshold', 10),
            'moderate_congestion_threshold': config.get('moderate_congestion_threshold', 6)
        }

        print(f"\n🎯 FULL-FRAME CONGESTION CONFIGURATION:")
        print(f"   📺 ROI: 100% OF SCREEN - COMPLETE COVERAGE")
        print(f"   🚗 Min vehicles for congestion: {self.config['min_vehicles_for_congestion']}")
        print(f"   📏 Speed threshold: {self.config['speed_threshold']} km/h")
        print(f"   ⏱️ Stationary threshold: {self.config['stationary_threshold']}s")
        print(f"   🐌 Slow vehicle ratio: {self.config['slow_vehicle_ratio']*100}%")
        print(f"   ⏰ Min congestion duration: {self.config['min_congestion_duration']}s")
        print(f"   🔴 Severe congestion: >{self.config['severe_congestion_threshold']} vehicles")
        print(f"   🟠 High congestion: >{self.config['high_congestion_threshold']} vehicles")
        print(f"   🟡 Moderate congestion: >{self.config['moderate_congestion_threshold']} vehicles")
        print("="*70 + "\n")

        self.reset_tracking_state()

    def reset_tracking_state(self):
        """Reset all tracking state variables"""
        self.track_history = defaultdict(lambda: deque(maxlen=90))  # 3 seconds at 30 FPS
        self.vehicle_status = {}
        self.vehicle_speeds = defaultdict(list)
        self.vehicle_stationary_time = defaultdict(float)
        self.congestion_start_time = None
        self.congestion_durations = []
        self.current_congestion_level = "none"
        self.frame_count = 0
        self.total_vehicles_detected = 0
        
        # Enhanced metrics for full-frame analysis
        self.peak_vehicle_count = 0
        self.average_vehicle_count = 0
        self.vehicle_count_history = []
        
        self.setup_enhanced_metrics()
        
        # Full-frame ROI coordinates (entire screen)
        self.roi_polygon = None
        self.frame_width = 0
        self.frame_height = 0

    def setup_roi(self, frame_width, frame_height):
        """Setup FULL FRAME ROI - 100% of screen"""
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # FULL FRAME ROI - entire screen
        self.roi_polygon = np.array([
            [0, 0],  # Top-left
            [frame_width, 0],  # Top-right
            [frame_width, frame_height],  # Bottom-right
            [0, frame_height]  # Bottom-left
        ], np.int32)
        
        print(f"🎯 FULL-FRAME ROI Setup: {frame_width}x{frame_height}")
        print(f"   ✅ Monitoring 100% of screen area")
        print(f"   📐 Area: {frame_width * frame_height} pixels")

    def point_in_roi(self, point):
        """ALL points are in ROI since we're monitoring full frame"""
        return True  # Every point is in the full-frame ROI

    def calculate_congestion_metrics(self, detections, fps):
        """Calculate congestion metrics for FULL FRAME analysis"""
        if fps <= 0:
            return "none", 0, 0
        
        # ALL vehicles are in ROI with full-frame monitoring
        vehicles_in_frame = detections
        total_vehicles = len(vehicles_in_frame)
        
        # Update vehicle count history for averaging
        self.vehicle_count_history.append(total_vehicles)
        if len(self.vehicle_count_history) > 100:  # Keep last 100 frames
            self.vehicle_count_history.pop(0)
        
        self.average_vehicle_count = np.mean(self.vehicle_count_history) if self.vehicle_count_history else 0
        self.peak_vehicle_count = max(self.peak_vehicle_count, total_vehicles)
        
        if total_vehicles < self.config['min_vehicles_for_congestion']:
            return "none", total_vehicles, 0
        
        # Metric 1: Speed-based analysis
        slow_vehicles = 0
        stationary_vehicles = 0
        current_time = self.frame_count / fps
        
        for vehicle in vehicles_in_frame:
            speed = vehicle.get('speed')
            if speed is not None and speed < self.config['speed_threshold']:
                slow_vehicles += 1
            
            # Check stationary vehicles
            track_id = vehicle['track_id']
            if track_id in self.vehicle_stationary_time:
                if current_time - self.vehicle_stationary_time[track_id] > self.config['stationary_threshold']:
                    stationary_vehicles += 1
        
        speed_ratio = slow_vehicles / total_vehicles if total_vehicles > 0 else 0
        stationary_ratio = stationary_vehicles / total_vehicles if total_vehicles > 0 else 0
        
        # FULL-FRAME CONGESTION LEVELS based on vehicle count + movement
        if total_vehicles >= self.config['severe_congestion_threshold'] and speed_ratio > 0.5:
            level = "severe"
        elif total_vehicles >= self.config['high_congestion_threshold'] and speed_ratio > 0.4:
            level = "high"
        elif total_vehicles >= self.config['moderate_congestion_threshold'] and speed_ratio > 0.3:
            level = "moderate"
        elif total_vehicles >= self.config['min_vehicles_for_congestion']:
            level = "light"
        else:
            level = "none"
        
        # Combined congestion score (0-100)
        congestion_score = min(100, int(
            (total_vehicles / self.config['severe_congestion_threshold']) * 40 +  # Vehicle count contribution
            (speed_ratio * 40) +  # Speed ratio contribution
            (stationary_ratio * 20)  # Stationary ratio contribution
        ))
        
        return level, total_vehicles, congestion_score

    def update_stationary_times(self, detections, fps):
        """Update stationary time for each vehicle in FULL FRAME"""
        current_time = self.frame_count / fps
        
        # Track all vehicles in frame
        active_track_ids = set()
        
        for detection in detections:
            track_id = detection['track_id']
            active_track_ids.add(track_id)
            
            # Check if vehicle is moving
            if track_id in self.track_history and len(self.track_history[track_id]) >= 2:
                recent_points = list(self.track_history[track_id])[-5:]
                if len(recent_points) >= 2:
                    # Calculate movement in last few frames
                    movement = np.sqrt(
                        (recent_points[-1][0] - recent_points[0][0])**2 + 
                        (recent_points[-1][1] - recent_points[0][1])**2
                    )
                    
                    # If movement is minimal, increment stationary time
                    if movement < 5:  # pixels threshold
                        if track_id not in self.vehicle_stationary_time:
                            self.vehicle_stationary_time[track_id] = current_time
                    else:
                        # Vehicle moved, reset stationary time
                        if track_id in self.vehicle_stationary_time:
                            del self.vehicle_stationary_time[track_id]
            else:
                # Not enough history, assume moving
                if track_id in self.vehicle_stationary_time:
                    del self.vehicle_stationary_time[track_id]
        
        # Clean up stationary times for vehicles that are no longer tracked
        expired_tracks = set(self.vehicle_stationary_time.keys()) - active_track_ids
        for track_id in expired_tracks:
            del self.vehicle_stationary_time[track_id]

    def track_congestion_duration(self, congestion_level, fps):
        """Track how long congestion persists in FULL FRAME"""
        current_time = self.frame_count / fps
        
        if congestion_level != "none":
            if self.congestion_start_time is None:
                self.congestion_start_time = current_time
                print(f"🚦 CONGESTION STARTED: {congestion_level.upper()} at {current_time:.1f}s")
        else:
            if self.congestion_start_time is not None:
                duration = current_time - self.congestion_start_time
                if duration >= self.config['min_congestion_duration']:
                    self.congestion_durations.append({
                        'start_time': self.congestion_start_time,
                        'end_time': current_time,
                        'duration': duration,
                        'level': self.current_congestion_level
                    })
                    print(f"📊 CONGESTION ENDED: {self.current_congestion_level.upper()} "
                          f"duration: {duration:.1f}s")
                self.congestion_start_time = None
        
        self.current_congestion_level = congestion_level

    def process_frame(self, frame, frame_number, fps):
        """Process a single frame for FULL-FRAME congestion analysis"""
        self.frame_count = frame_number
        
        # Initialize FULL-FRAME ROI on first frame
        if self.roi_polygon is None:
            h, w = frame.shape[:2]
            self.setup_roi(w, h)

        # Skip frames for efficiency
        if frame_number % self.config['process_every_n_frames'] != 0:
            return defaultdict(int), []

        counts = defaultdict(int)
        detections = []

        # Run YOLO tracking on FULL FRAME
        results = self.model.track(
            frame, 
            persist=True, 
            conf=0.4, 
            classes=list(self.class_names.keys()),
            tracker="bytetrack.yaml", 
            verbose=False, 
            device=self.device
        )

        if results[0].boxes and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            ids = results[0].boxes.id.int().cpu().numpy()
            cls = results[0].boxes.cls.int().cpu().numpy()
            confs = results[0].boxes.conf.float().cpu().numpy()

            for box, tid, cid, conf in zip(boxes, ids, cls, confs):
                if cid not in self.class_names:
                    continue
                    
                x1, y1, x2, y2 = map(int, box)
                name = self.class_names[int(cid)]

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                color = self.colors.get(name, (255, 255, 255))
                
                # Calculate speed
                speed = self.calculate_speed(tid, (cx, cy), frame_number, fps)

                # Update track history
                self.track_history[tid].append((cx, cy))
                
                # ALL vehicles are in ROI with full-frame monitoring
                in_roi = True

                if tid not in self.vehicle_status:
                    self.vehicle_status[tid] = {
                        "name": name,
                        "first_seen": frame_number,
                        "in_roi": True  # Always true for full-frame
                    }

                status = self.vehicle_status[tid]
                status["in_roi"] = True

                detection_data = {
                    "track_id": int(tid),
                    "class_name": name,
                    "bbox": [x1, y1, x2-x1, y2-y1],
                    "confidence": float(conf),
                    "center": (cx, cy),
                    "in_roi": True,  # Always true for full-frame
                    "speed": speed,
                    "color": color,
                    "stationary_time": self.vehicle_stationary_time.get(tid, 0)
                }

                detections.append(detection_data)

                # Count ALL vehicles (full frame)
                counts[name] += 1
                self.total_vehicles_detected += 1

                if speed:
                    self.speed_data[name].append(speed)

        # Update stationary times for ALL vehicles
        self.update_stationary_times(detections, fps)
        
        # Calculate FULL-FRAME congestion metrics
        congestion_level, vehicles_in_frame, congestion_score = self.calculate_congestion_metrics(detections, fps)
        
        # Track congestion duration
        self.track_congestion_duration(congestion_level, fps)
        
        # Add congestion info to all detections
        for detection in detections:
            detection.update({
                'congestion_level': congestion_level,
                'congestion_score': congestion_score,
                'vehicles_in_frame': vehicles_in_frame
            })

        return counts, detections

    def draw_detections(self, frame, detections, fps):
        """Draw detection boxes with FULL-FRAME congestion visualization"""
        h, w = frame.shape[:2]
        
        # Draw FULL-FRAME background overlay based on congestion level
        overlay = frame.copy()
        
        # Background color based on congestion level
        bg_colors = {
            "none": (0, 20, 0),       # Very dark green
            "light": (0, 30, 30),     # Dark yellow-green
            "moderate": (0, 50, 50),  # Dark orange
            "high": (0, 0, 30),       # Dark red
            "severe": (20, 0, 20)     # Dark purple
        }
        
        bg_color = bg_colors.get(self.current_congestion_level, (0, 0, 20))
        cv2.rectangle(overlay, (0, 0), (w, h), bg_color, -1)
        cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)
        
        # Draw FULL-FRAME border
        border_colors = {
            "none": (0, 255, 0),      # Green
            "light": (0, 255, 255),   # Yellow
            "moderate": (0, 165, 255), # Orange
            "high": (0, 0, 255),      # Red
            "severe": (128, 0, 128)   # Purple
        }
        
        border_color = border_colors.get(self.current_congestion_level, (255, 255, 255))
        cv2.rectangle(frame, (0, 0), (w-1, h-1), border_color, 8)

        # Header with FULL-FRAME congestion info
        cv2.putText(frame, "FULL-FRAME CONGESTION DETECTOR - 100% SCREEN COVERAGE", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        congestion_info = f"CONGESTION: {self.current_congestion_level.upper()}"
        cv2.putText(frame, congestion_info, (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, border_color, 2)
        
        # Current congestion duration
        if self.congestion_start_time is not None:
            duration = (self.frame_count / fps) - self.congestion_start_time
            cv2.putText(frame, f"Duration: {duration:.1f}s", (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, border_color, 2)
        
        # FULL-FRAME statistics
        current_vehicles = len([d for d in detections if d.get('in_roi', False)])
        cv2.putText(frame, f"Vehicles in Frame: {current_vehicles}", (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        total_duration = sum(cd['duration'] for cd in self.congestion_durations)
        cv2.putText(frame, f"Total Congestion: {total_duration:.1f}s", (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.putText(frame, f"Congestion Events: {len(self.congestion_durations)}", (20, 160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.putText(frame, f"Peak Vehicles: {self.peak_vehicle_count}", (20, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.putText(frame, f"Avg Vehicles: {self.average_vehicle_count:.1f}", (20, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Draw each detection with congestion-aware coloring
        for d in detections:
            x, y, wb, hb = d["bbox"]
            name = d["class_name"]
            color = d["color"]
            speed = d.get("speed")
            stationary_time = d.get("stationary_time", 0)
            
            # Color code based on movement status
            if stationary_time > self.config['stationary_threshold']:
                box_color = (0, 0, 255)  # Red for stationary
                thickness = 3
            elif speed and speed < self.config['speed_threshold']:
                box_color = (0, 165, 255)  # Orange for slow
                thickness = 2
            else:
                box_color = color  # Normal color for moving
                thickness = 1
            
            # Draw bounding box
            cv2.rectangle(frame, (x, y), (x + wb, y + hb), box_color, thickness)
            
            # Build label
            label = f"{name.upper()}"
            if speed: 
                label += f" {speed:.0f}kmh"
            if stationary_time > 0:
                label += f" ST:{stationary_time:.0f}s"
            
            # Draw label background
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x, y - th - 8), (x + tw + 10, y), box_color, -1)
            
            # Draw label text
            cv2.putText(frame, label, (x + 5, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Draw center point with movement history
            if d['track_id'] in self.track_history:
                points = list(self.track_history[d['track_id']])
                for i in range(1, len(points)):
                    alpha = i / len(points)
                    line_color = (
                        int(box_color[0] * alpha),
                        int(box_color[1] * alpha), 
                        int(box_color[2] * alpha)
                    )
                    cv2.line(frame, points[i-1], points[i], line_color, 2)

        return frame

    def analyze_video(self, video_path, progress_callback=None, save_output=True, roi_normalized=None, **kwargs):
        """Main video analysis method for FULL-FRAME monitoring"""
        print(f"\n🎬 STARTING FULL-FRAME CONGESTION TIME ANALYSIS")
        print(f"📹 Video: {video_path}")
        print(f"📺 Monitoring: 100% OF SCREEN AREA")
        
        import cv2
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"❌ Cannot open video file: {video_path}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"📊 Video Properties: {width}x{height}, {fps:.2f} FPS, {total_frames} frames")
        print(f"🎯 Monitoring Area: {width} x {height} pixels = {width * height} total pixels")

        # Reset tracking state
        self.reset_tracking_state()
        
        # Setup output video if requested
        output_path = None
        out = None
        if save_output:
            os.makedirs('media/processed_videos', exist_ok=True)
            original_filename = os.path.basename(str(video_path))
            name_without_ext = os.path.splitext(original_filename)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"fullframe_congestion_{name_without_ext}_{timestamp}.mp4"
            output_path = os.path.join('media/processed_videos', output_filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        # Process frames
        frame_number = 0
        analysis_start = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Process frame
            counts, detections = self.process_frame(frame, frame_number, fps)
            
            # Draw detections
            annotated_frame = self.draw_detections(frame.copy(), detections, fps)
            
            # Write output
            if out is not None:
                out.write(annotated_frame)
            
            # Progress callback
            if progress_callback and frame_number % 50 == 0:
                progress_percent = min(88, 15 + int((frame_number / total_frames) * 73))
                message = f"Full-frame processing {frame_number}/{total_frames}"
                progress_callback(progress_percent, total_frames, message)

            frame_number += 1

        # Cleanup
        total_processing_time = time.time() - analysis_start
        cap.release()
        if out is not None:
            out.release()
            print(f"✅ Processed video saved: {output_path}")

        print(f"\n✅ FULL-FRAME Analysis completed in {total_processing_time:.2f} seconds")
        
        # Generate comprehensive report
        report = self.generate_report(total_frames, total_processing_time, fps, {})
        
        if output_path:
            report['output_video_path'] = output_path
            
        return report

    def generate_report(self, total_frames, proc_time, fps, enhanced):
        """Generate comprehensive FULL-FRAME congestion analysis report"""
        duration = total_frames / fps if fps > 0 else 0
        
        # Calculate congestion statistics
        total_congestion_time = sum(cd['duration'] for cd in self.congestion_durations)
        congestion_percentage = (total_congestion_time / duration) * 100 if duration > 0 else 0
        
        # Categorize congestion events
        severe_events = [cd for cd in self.congestion_durations if cd['level'] == 'severe']
        high_events = [cd for cd in self.congestion_durations if cd['level'] == 'high']
        moderate_events = [cd for cd in self.congestion_durations if cd['level'] == 'moderate']
        light_events = [cd for cd in self.congestion_durations if cd['level'] == 'light']
        
        # Overall congestion assessment
        if congestion_percentage > 50:
            overall_level = "Chronic Gridlock"
        elif congestion_percentage > 25:
            overall_level = "Frequent Congestion"
        elif congestion_percentage > 10:
            overall_level = "Moderate Congestion"
        elif congestion_percentage > 5:
            overall_level = "Occasional Congestion"
        else:
            overall_level = "Free Flow Conditions"

        return {
            "metadata": {
                "duration": duration,
                "processing_time": proc_time,
                "date": time.strftime("%Y-%m-%d %H:%M"),
                "model_used": "collision4_model (YOLOv8s)",
                "detection_method": "FULL-FRAME multi-metric congestion analysis",
                "monitoring_coverage": "100% of screen area",
                "congestion_thresholds": self.config
            },
            "congestion_summary": {
                "total_congestion_time_seconds": round(total_congestion_time, 1),
                "congestion_percentage": round(congestion_percentage, 1),
                "total_congestion_events": len(self.congestion_durations),
                "overall_congestion_level": overall_level,
                "current_congestion_level": self.current_congestion_level
            },
            "vehicle_statistics": {
                "total_vehicles_detected": self.total_vehicles_detected,
                "peak_vehicle_count": self.peak_vehicle_count,
                "average_vehicle_count": round(self.average_vehicle_count, 1),
                "vehicles_per_minute": round((self.total_vehicles_detected / duration) * 60, 1) if duration > 0 else 0
            },
            "congestion_breakdown": {
                "severe_events": len(severe_events),
                "severe_duration": sum(cd['duration'] for cd in severe_events),
                "high_events": len(high_events),
                "high_duration": sum(cd['duration'] for cd in high_events),
                "moderate_events": len(moderate_events),
                "moderate_duration": sum(cd['duration'] for cd in moderate_events),
                "light_events": len(light_events),
                "light_duration": sum(cd['duration'] for cd in light_events)
            },
            "congestion_events": [
                {
                    "level": cd['level'],
                    "start_time": cd['start_time'],
                    "end_time": cd['end_time'],
                    "duration": cd['duration']
                }
                for cd in self.congestion_durations
            ],
            "metrics": {
                "average_congestion_duration": total_congestion_time / len(self.congestion_durations) if self.congestion_durations else 0,
                "longest_congestion_event": max([cd['duration'] for cd in self.congestion_durations]) if self.congestion_durations else 0,
                "congestion_frequency_per_hour": (len(self.congestion_durations) / duration) * 3600 if duration > 0 else 0
            }
        }
    def generate_report(self, total_frames, proc_time, fps, enhanced):
        """Generate comprehensive FULL-FRAME congestion analysis report"""
        duration = total_frames / fps if fps > 0 else 0
        
        # Calculate congestion statistics
        total_congestion_time = sum(cd['duration'] for cd in self.congestion_durations)
        congestion_percentage = (total_congestion_time / duration) * 100 if duration > 0 else 0
        
        # Categorize congestion events
        severe_events = [cd for cd in self.congestion_durations if cd['level'] == 'severe']
        high_events = [cd for cd in self.congestion_durations if cd['level'] == 'high']
        moderate_events = [cd for cd in self.congestion_durations if cd['level'] == 'moderate']
        light_events = [cd for cd in self.congestion_durations if cd['level'] == 'light']
        
        # Overall congestion assessment
        if congestion_percentage > 50:
            overall_level = "Chronic Gridlock"
        elif congestion_percentage > 25:
            overall_level = "Frequent Congestion"
        elif congestion_percentage > 10:
            overall_level = "Moderate Congestion"
        elif congestion_percentage > 5:
            overall_level = "Occasional Congestion"
        else:
            overall_level = "Free Flow Conditions"

        # ENSURE COMPATIBLE REPORT STRUCTURE
        report = {
            "metadata": {
                "duration": duration,
                "processing_time": proc_time,
                "date": time.strftime("%Y-%m-%d %H:%M"),
                "model_used": "collision4_model (YOLOv8s)",
                "detection_method": "FULL-FRAME multi-metric congestion analysis",
                "monitoring_coverage": "100% of screen area",
                "congestion_thresholds": self.config
            },
            # Add summary section for compatibility with task expectations
            "summary": {
                "total_vehicles_counted": self.total_vehicles_detected,
                "vehicle_breakdown": {
                    "car": 0,  # Congestion detector doesn't track per-class counts
                    "jeep": 0,
                    "motorcycle": 0, 
                    "tricycle": 0,
                    "truck": 0
                },
                "peak_traffic": self.peak_vehicle_count,
                "average_traffic_density": round(self.average_vehicle_count, 1)
            },
            "congestion_summary": {
                "total_congestion_time_seconds": round(total_congestion_time, 1),
                "congestion_percentage": round(congestion_percentage, 1),
                "total_congestion_events": len(self.congestion_durations),
                "overall_congestion_level": overall_level,
                "current_congestion_level": self.current_congestion_level
            },
            "vehicle_statistics": {
                "total_vehicles_detected": self.total_vehicles_detected,
                "peak_vehicle_count": self.peak_vehicle_count,
                "average_vehicle_count": round(self.average_vehicle_count, 1),
                "vehicles_per_minute": round((self.total_vehicles_detected / duration) * 60, 1) if duration > 0 else 0
            },
            "congestion_breakdown": {
                "severe_events": len(severe_events),
                "severe_duration": sum(cd['duration'] for cd in severe_events),
                "high_events": len(high_events),
                "high_duration": sum(cd['duration'] for cd in high_events),
                "moderate_events": len(moderate_events),
                "moderate_duration": sum(cd['duration'] for cd in moderate_events),
                "light_events": len(light_events),
                "light_duration": sum(cd['duration'] for cd in light_events)
            },
            "metrics": {
                "congestion_level": overall_level.lower().replace(' ', '_'),
                "traffic_pattern": "congestion_based",
                "average_congestion_duration": total_congestion_time / len(self.congestion_durations) if self.congestion_durations else 0,
                "longest_congestion_event": max([cd['duration'] for cd in self.congestion_durations]) if self.congestion_durations else 0,
                "congestion_frequency_per_hour": (len(self.congestion_durations) / duration) * 3600 if duration > 0 else 0
            },
            "congestion_events": [
                {
                    "level": cd['level'],
                    "start_time": cd['start_time'],
                    "end_time": cd['end_time'],
                    "duration": cd['duration']
                }
                for cd in self.congestion_durations
            ]
        }
        
        return report

# Update ml/__init__.py to include the new detector
# Add this line: from .congestion_time_detector import CongestionTimeDetector