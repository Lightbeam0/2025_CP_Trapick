# ml/baliwasan_yjunction_detector.py
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

class BaliwasanYJunctionDetector(BaseDetector):
    def __init__(self, model_path=None, top_zone_threshold=0.40):
        super().__init__()

        print("\n" + "="*70)
        print("🚦 BALIWASAN Y-JUNCTION DETECTOR - COLLISION4 MODEL")
        print("="*70)

        # AUTO-LOAD COLLISION4 MODEL
        if model_path is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parents[2]  # TRAPICK/

            # UPDATED: Use collision4_model path
            model_path = project_root / "runs" / "detect" / "collision4_model" / "weights" / "best.pt"
            
            if not model_path.exists():
                raise FileNotFoundError(
                    f"❌ Collision4 model not found at: {model_path}\n"
                    f"   Expected: runs/detect/collision4_model/weights/best.pt"
                )
                
            print(f"📂 AUTO-LOADED COLLISION4 MODEL:")
            print(f"   → {model_path.relative_to(project_root)}")
        else:
            model_path = Path(model_path)
            print(f"📂 MANUAL MODEL PATH:")
            print(f"   → {model_path}")

        # LOAD COLLISION4 MODEL (YOLOv8s)
        print(f"\n⏳ Loading collision4 model: {model_path.name}")
        self.model = YOLO(str(model_path))

        # FORCE GPU
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        print(f"✅ Device: {self.device.upper()}")

        # UPDATED: COLLISION4 MODEL CLASSES (excluding VehicleCrash=0 and person=4)
        self.class_names = {
            1: 'car',
            2: 'jeep', 
            3: 'motorcycle',
            5: 'tricycle',
            6: 'truck'
        }

        # Which ones to count (all vehicle classes)
        self.counted_classes = list(self.class_names.values())

        # CONFIGURABLE TOP ZONE THRESHOLD (percentage of frame height)
        self.top_zone_threshold = top_zone_threshold

        print(f"\n🎯 COLLISION4 MODEL CONFIGURATION:")
        print(f"   Architecture: YOLOv8s")
        print(f"   Vehicle classes ({len(self.class_names)} types):")
        for i, name in self.class_names.items():
            print(f"      [{i}] {name.upper()}")
        
        print(f"\n   EXCLUDED from tracking:")
        print(f"      [0] VehicleCrash")
        print(f"      [4] person")
        print(f"\n   DIRECTIONAL COUNTING:")
        print(f"      Top zone threshold: {self.top_zone_threshold*100}% of frame height")
        print(f"      Counting: Vehicles from TOP → BOTTOM only")

        # UPDATED: Colors for collision4 model vehicle classes
        self.colors = {
            "car": (100, 100, 255),       # Purple
            "jeep": (255, 165, 0),        # Orange
            "motorcycle": (255, 255, 0),  # Yellow
            "tricycle": (255, 0, 255),    # Magenta
            "truck": (0, 0, 255),         # Red
        }

        self.reset_tracking_state()
        print("\n" + "="*70)
        print("✅ BALIWASAN Y-JUNCTION DETECTOR WITH COLLISION4 MODEL READY!")
        print("="*70 + "\n")

    def reset_tracking_state(self):
        """Reset all tracking state variables"""
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status = {}
        self.vehicle_type_counts = defaultdict(int)
        self.vehicle_crossed = set()
        self.frame_count = 0
        self.total_count = 0
        self.setup_enhanced_metrics()

    def setup_counting_zone(self, frame_height, frame_width):
        """Setup counting zone with configurable top threshold"""
        # Top zone - where vehicles must originate from
        self.origin_top = 0
        self.origin_bottom = int(frame_height * self.top_zone_threshold)
        
        # Counting zone - where we detect crossings
        self.zone_top = int(frame_height * 0.40)
        self.zone_bottom = int(frame_height * 0.80)
        
        # Counting line in the middle of the zone
        self.line_start = (int(frame_width * 0.1), int(frame_height * 0.60))
        self.line_end = (int(frame_width * 0.9), int(frame_height * 0.60))
        
        print(f"🎯 DIRECTIONAL COUNTING ZONE CONFIGURED:")
        print(f"   Origin zone (TOP): Y={self.origin_top}-{self.origin_bottom}")
        print(f"   Counting zone: Y={self.zone_top}-{self.zone_bottom}")
        print(f"   Counting line: {self.line_start} → {self.line_end}")

    def is_coming_from_top(self, track_history):
        """Check if vehicle originated from the top zone"""
        if len(track_history) < 5:
            return False
            
        # Check early positions in tracking history
        early_points = list(track_history)[:5]
        early_ys = [point[1] for point in early_points]
        
        # Vehicle must have started in the top origin zone
        avg_early_y = sum(early_ys) / len(early_ys)
        return avg_early_y <= self.origin_bottom

    def is_moving_downward(self, track_history):
        """Check if vehicle is consistently moving downward"""
        if len(track_history) < 3:
            return False
            
        recent_points = list(track_history)[-5:]  # Last 5 points
        if len(recent_points) < 3:
            return True  # Not enough data, assume valid
            
        ys = [point[1] for point in recent_points]
        
        # Calculate movement trend
        y_changes = [ys[i+1] - ys[i] for i in range(len(ys)-1)]
        downward_movements = [change for change in y_changes if change > 2]  # Moving down
        
        return len(downward_movements) >= len(y_changes) * 0.6  # At least 60% downward movement

    def process_frame(self, frame, frame_number, fps):
        """Process a single frame for vehicle detection and counting"""
        counts = defaultdict(int)
        detections = []

        # Run YOLO tracking with collision4 model
        results = self.model.track(
            frame, 
            persist=True, 
            conf=0.4, 
            classes=list(self.class_names.keys()),  # Only track vehicle classes
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
                # Only process vehicle classes we're tracking
                if cid not in self.class_names:
                    continue
                    
                x1, y1, x2, y2 = map(int, box)
                name = self.class_names[int(cid)]

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                color = self.colors.get(name, (255, 255, 255))
                speed = self.calculate_speed(tid, (cx, cy), frame_number, fps)

                if tid not in self.vehicle_status:
                    self.vehicle_status[tid] = {
                        "name": name, 
                        "crossed": False, 
                        "last_y": cy,
                        "from_top": False,
                        "valid_direction": False
                    }

                self.track_history[tid].append((cx, cy))
                status = self.vehicle_status[tid]
                
                # Check if vehicle originated from top zone
                if not status["from_top"]:
                    status["from_top"] = self.is_coming_from_top(self.track_history[tid])
                
                # Check if moving in valid downward direction
                status["valid_direction"] = self.is_moving_downward(self.track_history[tid])
                
                in_zone = self.zone_top <= cy <= self.zone_bottom
                line_y = self.get_line_y(cx)

                # Crossing detection logic - ONLY COUNT IF FROM TOP AND MOVING DOWN
                if (in_zone and not status["crossed"] and 
                    status["from_top"] and status["valid_direction"]):
                    
                    if status["last_y"] < line_y <= cy:
                        status["crossed"] = True
                        self.total_count += 1
                        self.vehicle_type_counts[name] += 1
                        print(f"✓ #{self.total_count:03d} {name.upper()} ID:{tid} COUNTED (TOP→BOTTOM)")

                    status["last_y"] = cy

                if in_zone:
                    counts[name] += 1

                detections.append({
                    "track_id": int(tid),
                    "class_name": name,
                    "bbox": [x1, y1, x2-x1, y2-y1],
                    "confidence": float(conf),
                    "center": (cx, cy),
                    "in_zone": in_zone,
                    "speed": speed,
                    "color": color,
                    "from_top": status["from_top"],
                    "valid_direction": status["valid_direction"]
                })

                if speed:
                    self.speed_data[name].append(speed)

        return counts, detections

    def get_line_y(self, x):
        """Calculate Y coordinate of counting line at given X position"""
        x1, y1 = self.line_start
        x2, y2 = self.line_end
        if x2 == x1: 
            return y1
        return int(y1 + (y2 - y1) * (x - x1) / (x2 - x1))

    def draw_detections(self, frame, detections, fps):
        """Draw detection boxes and information on frame"""
        h, w = frame.shape[:2]

        # Header with model info
        cv2.putText(frame, "BALIWASAN Y-JUNCTION | COLLISION4 MODEL (YOLOv8s)", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(frame, f"TOTAL COUNT: {self.total_count}", (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

        # Draw counting zones
        # Origin zone (top) - semi-transparent
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, self.origin_top), (w, self.origin_bottom), (0, 100, 255), -1)
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
        cv2.rectangle(frame, (0, self.origin_top), (w, self.origin_bottom), (0, 100, 255), 2)
        cv2.putText(frame, "ORIGIN ZONE", (10, self.origin_bottom - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 100, 255), 2)
        
        # Counting zone - semi-transparent
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, self.zone_top), (w, self.zone_bottom), (255, 0, 0), -1)
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
        cv2.rectangle(frame, (0, self.zone_top), (w, self.zone_bottom), (255, 0, 0), 2)
        cv2.putText(frame, "COUNTING ZONE", (10, self.zone_bottom - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # HIGHLY VISIBLE COUNTING LINE - THICK WITH ARROWS AND LABELS
        # Draw thick main line
        cv2.line(frame, self.line_start, self.line_end, (0, 255, 0), 6)
        
        # Draw dashed effect for better visibility
        line_length = np.sqrt((self.line_end[0]-self.line_start[0])**2 + (self.line_end[1]-self.line_start[1])**2)
        dash_length = 20
        gap_length = 10
        if line_length > 0:
            direction = ((self.line_end[0]-self.line_start[0])/line_length, 
                        (self.line_end[1]-self.line_start[1])/line_length)
            
            current_pos = 0
            while current_pos < line_length:
                start_pos = (int(self.line_start[0] + direction[0] * current_pos),
                           int(self.line_start[1] + direction[1] * current_pos))
                end_pos = (int(self.line_start[0] + direction[0] * min(current_pos + dash_length, line_length)),
                         int(self.line_start[1] + direction[1] * min(current_pos + dash_length, line_length)))
                cv2.line(frame, start_pos, end_pos, (0, 255, 255), 3)  # Yellow dashes
                current_pos += dash_length + gap_length
        
        # Draw directional arrows along the line
        arrow_spacing = 100
        num_arrows = max(1, int(line_length / arrow_spacing))
        
        for i in range(num_arrows + 1):
            t = i / (num_arrows + 1)
            arrow_x = int(self.line_start[0] + t * (self.line_end[0] - self.line_start[0]))
            arrow_y = int(self.line_start[1] + t * (self.line_end[1] - self.line_start[1]))
            
            # Draw downward pointing arrows
            arrow_size = 15
            cv2.arrowedLine(frame, 
                          (arrow_x, arrow_y - arrow_size), 
                          (arrow_x, arrow_y + arrow_size), 
                          (0, 255, 0), 4, tipLength=0.5)
        
        # Add prominent COUNTING LINE label
        label_bg_size = cv2.getTextSize("COUNTING LINE", cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        label_bg_x = (self.line_start[0] + self.line_end[0] - label_bg_size[0]) // 2
        label_bg_y = self.line_start[1] - 20
        
        # Label background
        cv2.rectangle(frame, 
                     (label_bg_x - 10, label_bg_y - label_bg_size[1] - 10),
                     (label_bg_x + label_bg_size[0] + 10, label_bg_y + 10),
                     (0, 0, 0), -1)
        cv2.rectangle(frame, 
                     (label_bg_x - 10, label_bg_y - label_bg_size[1] - 10),
                     (label_bg_x + label_bg_size[0] + 10, label_bg_y + 10),
                     (0, 255, 0), 2)
        
        # Label text
        cv2.putText(frame, "COUNTING LINE", (label_bg_x, label_bg_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Draw each detection
        for d in detections:
            x, y, wb, hb = d["bbox"]
            name = d["class_name"]
            color = d["color"]
            speed = d.get("speed")
            
            # Build label with directional info
            label = f"{name.upper()} {d['confidence']:.2f}"
            if speed: 
                label += f" {speed:.0f}kmh"
            
            # Add directional status
            if d["from_top"] and d["valid_direction"]:
                label += " ✓TOP"
            elif not d["from_top"]:
                label += " ✗ORIGIN"
            else:
                label += " ✗DIR"
                
            if d["in_zone"]: 
                label += " IN ZONE"

            # Draw bounding box with color coding
            if d["from_top"] and d["valid_direction"]:
                thickness = 4  # Thick for valid vehicles
                box_color = (0, 255, 0)  # Green for valid
            else:
                thickness = 2  # Thin for invalid
                box_color = color  # Regular color for invalid
                
            cv2.rectangle(frame, (x, y), (x + wb, y + hb), box_color, thickness)
            
            # Draw label background
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x, y - th - 10), (x + tw + 10, y), box_color, -1)
            
            # Draw label text
            cv2.putText(frame, label, (x + 5, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Display directional counting info
        info_y = 130
        cv2.putText(frame, f"DIRECTIONAL COUNTING: TOP→BOTTOM ONLY", (20, info_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Top zone threshold: {self.top_zone_threshold*100}%", (20, info_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return frame

    def analyze_video(self, video_path, progress_callback=None, save_output=True, roi_normalized=None, **kwargs):
            """
            Main video analysis method for BaliwasanYJunctionDetector
            Compatible with task.py expectations
            
            Args:
                video_path: Path to video file
                progress_callback: Optional callback for progress updates
                save_output: Whether to save annotated video
                roi_normalized: Not used by this detector (uses predefined Y-junction zones)
                **kwargs: Additional parameters (ignored)
            """
            # Note: This detector uses predefined Y-junction zones, not custom ROI
            if roi_normalized:
                print(f"⚠️  ROI parameter provided but not used by BaliwasanYJunctionDetector")
                print(f"    This detector uses predefined directional counting zones")
            
            print("\n" + "="*70)
            print(f"🎬 STARTING BALIWASAN Y-JUNCTION ANALYSIS WITH COLLISION4")
            print("="*70)
            print(f"📹 Video: {video_path}")
            
            import cv2
            from datetime import datetime
            
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise Exception(f"❌ Cannot open video file: {video_path}")

            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0

            print(f"📊 Video Properties:")
            print(f"   Resolution: {width}x{height}")
            print(f"   FPS: {fps:.2f}")
            print(f"   Total frames: {total_frames}")
            print(f"   Duration: {duration:.2f} seconds")

            # Reset tracking state for new video
            self.reset_tracking_state()
            
            # Setup counting zone with configurable top threshold
            ret, first_frame = cap.read()
            if not ret:
                raise Exception("❌ Cannot read video frame")
            
            self.setup_counting_zone(height, width)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to start

            # Setup video writer if saving output
            output_path = None
            out = None
            if save_output:
                import os
                os.makedirs('media/processed_videos', exist_ok=True)
                original_filename = os.path.basename(str(video_path))
                name_without_ext = os.path.splitext(original_filename)[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"collision4_{name_without_ext}_{timestamp}.mp4"
                output_path = os.path.join('media/processed_videos', output_filename)
                
                print(f"💾 Output will be saved to: {output_path}")
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                
                if not out.isOpened():
                    print("⚠️ Failed to initialize video writer")
                    output_path = None
                else:
                    print("✅ Video writer initialized")

            # Start processing
            frame_number = 0
            analysis_start = time.time()
            frames_written = 0

            print(f"\n⏳ Processing {total_frames} frames...")

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Process frame
                counts, detections = self.process_frame(frame, frame_number, fps)
                
                # Draw detections on frame
                annotated_frame = self.draw_detections(frame.copy(), detections, fps)
                
                # Write to output video
                if out is not None:
                    out.write(annotated_frame)
                    frames_written += 1
                
                # FIXED: Progress callback that matches task expectations
                if progress_callback and frame_number % 50 == 0:
                    # Calculate actual progress percentage (15% to 88% range)
                    progress_percent = min(88, 15 + int((frame_number / total_frames) * 73))
                    message = f"Processing frame {frame_number}/{total_frames}"
                    
                    # Call with THREE parameters as expected by task
                    progress_callback(progress_percent, total_frames, message)

                frame_number += 1

            # Cleanup
            total_processing_time = time.time() - analysis_start
            cap.release()
            
            if out is not None:
                out.release()
                print(f"✅ Processed video saved: {output_path}")

            print(f"\n✅ Analysis completed in {total_processing_time:.2f} seconds")
            print(f"📈 Total vehicles counted: {self.total_count}")
            print(f"📊 Breakdown: {dict(self.vehicle_type_counts)}")
            
            # Generate report
            report = self.generate_report(total_frames, total_processing_time, fps, {})
            
            # Add output path if video was saved
            if output_path:
                report['output_video_path'] = output_path
                report['frames_written'] = frames_written
                
            return report

    def generate_report(self, total_frames, proc_time, fps, enhanced):
        """Generate comprehensive analysis report"""
        duration = total_frames / fps if fps > 0 else 0
        vpm = (self.total_count / duration) * 60 if duration > 0 else 0
        
        # Assess congestion level
        if vpm > 100:
            level = "High Congestion"
        elif vpm > 50:
            level = "Moderate Congestion"
        else:
            level = "Light Traffic"

        # Assess traffic pattern
        if len(self.track_history) > 0:
            pattern = "Stable"  # Can be enhanced with more logic
        else:
            pattern = "Stable"

        # Vehicle breakdown - COLLISION4 FORMAT
        breakdown = {
            'total_vehicles_counted': self.total_count,
            'vehicle_breakdown': {c: self.vehicle_type_counts.get(c, 0) for c in self.counted_classes}
        }

        return {
            "metadata": {
                "duration": duration,
                "processing_time": proc_time,
                "date": time.strftime("%Y-%m-%d %H:%M"),
                "model_used": "collision4_model (YOLOv8s)",
                "model_architecture": "YOLOv8s",
                "tracked_classes": self.counted_classes,
                "excluded_classes": ["VehicleCrash", "person"],
                "confidence_threshold": 0.4,
                "iou_threshold": 0.7,
                "top_zone_threshold": f"{self.top_zone_threshold*100}%",
                "counting_direction": "TOP→BOTTOM only"
            },
            "summary": {
                "total_vehicles_counted": self.total_count,
                "vehicle_breakdown": {c: self.vehicle_type_counts.get(c, 0) for c in self.counted_classes},
                "peak_traffic": max([len(self.track_history.get(tid, [])) for tid in self.track_history.keys()]) if self.track_history else 0,
                "average_traffic_density": self.total_count / duration if duration > 0 else 0
            },
            "metrics": {
                "vehicles_per_minute": round(vpm, 1),
                "congestion_level": level,
                "traffic_pattern": pattern
            },
            "enhanced": enhanced
        }


# TEST FUNCTION
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 TESTING BALIWASAN Y-JUNCTION DETECTOR WITH COLLISION4 MODEL")
    print("="*70)
    
    # Test with different top zone thresholds
    for threshold in [0.30, 0.40, 0.50]:
        print(f"\n🔧 Testing with top_zone_threshold={threshold}")
        detector = BaliwasanYJunctionDetector(top_zone_threshold=threshold)
        
        test_video = "test_video.mp4"
        if os.path.exists(test_video):
            report = detector.analyze_video(test_video, save_output=True)
            print(f"\n📊 RESULT (threshold={threshold}):")
            print(f"   Total: {report['summary']['total_vehicles_counted']}")
            print(f"   Breakdown: {report['summary']['vehicle_breakdown']}")
        else:
            print(f"⚠️  Test video not found: {test_video}")
            break