# ml/directional_detectors/base_directional.py
import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
import time
import os
from pathlib import Path
from ultralytics import YOLO
import torch

from ..base_detector import BaseDetector
from ..congestion_module import CongestionModule

class BaseDirectionalDetector(BaseDetector):
    """
    Base class for all 8 directional detectors
    Enhanced with ROI support for congestion detection
    
    Handles:
    - YOLO detection
    - Directional counting logic (full frame)
    - ROI-based congestion detection
    - Result storage
    """
    
    def __init__(self, direction_name, model_path='yolov8l.pt'):
        super().__init__()
        
        print(f"\n{'='*70}")
        print(f"🚦 {direction_name.upper()} DIRECTIONAL DETECTOR WITH ROI")
        print(f"{'='*70}")
        
        # Load YOLO model
        print(f"📂 Loading YOLOv8 model: {model_path}")
        self.model = YOLO(model_path)
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        print(f"✅ Device: {self.device.upper()}")
        
        # Vehicle classes (COCO)
        self.class_names = {
            2: 'car',
            3: 'motorcycle',
            5: 'bus',
            7: 'truck'
        }
        self.counted_classes = list(self.class_names.values())
        self.vehicle_class_ids = list(self.class_names.keys())
        
        # Colors for visualization
        self.colors = {
            "car": (100, 100, 255),       # Purple
            "motorcycle": (255, 255, 0),  # Yellow
            "bus": (0, 255, 0),           # Green
            "truck": (0, 0, 255),         # Red
        }
        
        # Direction name for reporting
        self.direction_name = direction_name
        
        # ROI configuration
        self.roi_enabled = False
        self.roi_normalized = None  # Will store normalized coordinates
        self.roi_pixels = None      # Will store pixel coordinates
        self.roi_polygon = None     # For point-in-polygon tests
        
        # Initialize congestion module
        self.congestion_module = CongestionModule()
        
        # Reset tracking state
        self.reset_tracking_state()
        
        print(f"\n🎯 Configuration:")
        print(f"   Direction: {direction_name}")
        print(f"   Model: YOLOv8 (COCO)")
        print(f"   Counting: {len(self.counted_classes)} vehicle types (full frame)")
        print(f"   Congestion: ROI-based detection (configurable)")
        print(f"{'='*70}\n")
    
    def set_roi(self, roi_normalized):
        """
        Set Region of Interest for congestion detection
        
        Args:
            roi_normalized: List of normalized [x, y] coordinates (0.0 to 1.0)
                           Example: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
                           None to disable ROI (use full frame)
        """
        if roi_normalized is None or len(roi_normalized) == 0:
            self.roi_enabled = False
            self.roi_normalized = None
            self.roi_pixels = None
            self.roi_polygon = None
            print("🔲 ROI disabled - using full frame for congestion detection")
            return
        
        # Validate ROI
        if len(roi_normalized) < 3:
            raise ValueError("ROI must have at least 3 points")
        
        # Store normalized coordinates
        self.roi_normalized = roi_normalized
        self.roi_enabled = True
        
        print(f"✅ ROI set with {len(roi_normalized)} points")
        print(f"   Normalized coordinates: {roi_normalized}")
        print(f"   Congestion will be detected within ROI only")
    
    def _setup_roi_pixels(self, frame_width, frame_height):
        """Convert normalized ROI to pixel coordinates"""
        if not self.roi_enabled or self.roi_normalized is None:
            return
        
        # Convert normalized coordinates to pixels
        self.roi_pixels = [
            [int(x * frame_width), int(y * frame_height)]
            for x, y in self.roi_normalized
        ]
        
        # Create polygon for point-in-polygon tests
        self.roi_polygon = np.array(self.roi_pixels, dtype=np.int32)
        
        print(f"📐 ROI pixel coordinates: {self.roi_pixels}")
        print(f"   Frame size: {frame_width}x{frame_height}")
    
    def _is_point_in_roi(self, x, y):
        """Check if point is inside ROI"""
        if not self.roi_enabled:
            return True  # No ROI = everything is valid
        
        # Use OpenCV's pointPolygonTest
        point = (float(x), float(y))
        result = cv2.pointPolygonTest(self.roi_polygon, point, False)
        return result >= 0  # >= 0 means inside or on the boundary
    
    def reset_tracking_state(self):
        """Reset all tracking state"""
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status = {}
        self.vehicle_counts = defaultdict(int)
        self.counted_vehicles = set()
        self.total_count = 0
        self.frame_count = 0
        
        # Congestion module reset
        self.congestion_module.reset_state()
        
        # Results storage
        self.results = {
            'vehicle_counts': defaultdict(int),
            'congestion_events': [],
            'frame_data': [],
            'roi_config': {
                'enabled': self.roi_enabled,
                'normalized': self.roi_normalized,
                'pixels': self.roi_pixels
            }
        }
    
    def setup_counting_line(self, frame_width, frame_height):
        """
        OVERRIDE THIS in each specific detector
        Set up counting line position and orientation
        Returns: (line_start, line_end, valid_direction_vector)
        """
        raise NotImplementedError("Each detector must implement setup_counting_line")
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """
        OVERRIDE THIS based on direction type
        Check if vehicle is moving in valid direction
        """
        raise NotImplementedError("Each detector must implement is_valid_direction")
    
    def process_frame(self, frame, frame_number, fps):
        """Process single frame for counting AND ROI-based congestion"""
        # Initialize counting line and ROI on first frame
        if not hasattr(self, 'counting_line_setup'):
            h, w = frame.shape[:2]
            self.line_start, self.line_end, self.valid_direction = self.setup_counting_line(w, h)
            self._setup_roi_pixels(w, h)
            self.counting_line_setup = True
        
        # Run YOLO detection (on entire frame)
        results = self.model.track(
            frame,
            persist=True,
            conf=0.4,
            classes=self.vehicle_class_ids,
            tracker="bytetrack.yaml",
            verbose=False,
            device=self.device
        )
        
        detections = []
        detections_in_roi = []  # For congestion detection
        current_counts = defaultdict(int)
        
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
                
                # Center point
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                
                # Check if vehicle is in ROI
                in_roi = self._is_point_in_roi(cx, cy)
                
                # Add to track history
                self.track_history[tid].append((cx, cy))
                
                # Initialize vehicle status if new
                if tid not in self.vehicle_status:
                    self.vehicle_status[tid] = {
                        'name': name,
                        'crossed': False,
                        'valid_direction': False
                    }
                
                status = self.vehicle_status[tid]
                
                # Check direction validity (for counting - full frame)
                if not status['valid_direction']:
                    status['valid_direction'] = self.is_valid_direction(
                        self.track_history[tid], self.valid_direction
                    )
                
                # Check if crossing counting line (directional counting - full frame)
                if (status['valid_direction'] and not status['crossed'] and 
                    len(self.track_history[tid]) >= 2):
                    
                    prev_point = list(self.track_history[tid])[-2]
                    current_point = (cx, cy)
                    
                    if self.check_line_crossing(prev_point, current_point):
                        status['crossed'] = True
                        self.total_count += 1
                        self.vehicle_counts[name] += 1
                        self.counted_vehicles.add(tid)
                        
                        print(f"✓ #{self.total_count:03d} {name.upper()} ID:{tid} COUNTED")
                
                # Create detection dict for ALL vehicles
                detection_data = {
                    'track_id': int(tid),
                    'class_name': name,
                    'center': (cx, cy),
                    'bbox': [x1, y1, x2-x1, y2-y1],
                    'confidence': float(conf),
                    'color': self.colors[name],
                    'counted': status['crossed'],
                    'valid_direction': status['valid_direction'],
                    'in_roi': in_roi  # NEW: Track ROI status
                }
                
                detections.append(detection_data)
                
                # Add to ROI detections for congestion analysis
                if in_roi:
                    detections_in_roi.append(detection_data)
                
                # Count vehicles in current frame
                current_counts[name] += 1
        
        # Detect congestion (ONLY for vehicles in ROI)
        congestion_info = self.congestion_module.detect_congestion(detections_in_roi, fps)
        
        # Add ROI statistics to congestion info
        congestion_info['total_vehicles_full_frame'] = len(detections)
        congestion_info['total_vehicles_in_roi'] = len(detections_in_roi)
        congestion_info['roi_enabled'] = self.roi_enabled
        
        # Store frame data for dashboard
        frame_data = {
            'frame_number': frame_number,
            'timestamp': frame_number / fps if fps > 0 else 0,
            'vehicle_count_full_frame': sum(current_counts.values()),
            'vehicle_count_in_roi': len(detections_in_roi),
            'counted_this_frame': self.total_count - self.results['vehicle_counts'].get('total', 0),
            'congestion_level': congestion_info['level'],
            'stationary_vehicles': congestion_info['stationary_vehicles'],
            'roi_enabled': self.roi_enabled
        }
        self.results['frame_data'].append(frame_data)
        
        # Update total counts
        self.results['vehicle_counts']['total'] = self.total_count
        for name, count in self.vehicle_counts.items():
            self.results['vehicle_counts'][name] = count
        
        return current_counts, detections, congestion_info
    
    def check_line_crossing(self, prev_point, current_point):
        """
        Check if line segment (prev_point -> current_point) crosses counting line
        using line-line intersection
        """
        x1, y1 = prev_point
        x2, y2 = current_point
        x3, y3 = self.line_start
        x4, y4 = self.line_end
        
        # Calculate determinants
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        
        if denom == 0:
            return False  # Lines are parallel
        
        # Intersection point
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        # Check if intersection is within both line segments
        return 0 <= t <= 1 and 0 <= u <= 1
    
    def draw_detections(self, frame, detections, congestion_info, fps):
        """Draw detection boxes, counting line, ROI, and congestion info"""
        h, w = frame.shape[:2]
        
        # Draw ROI polygon FIRST (as background)
        if self.roi_enabled and self.roi_polygon is not None:
            # Semi-transparent ROI overlay
            overlay = frame.copy()
            cv2.fillPoly(overlay, [self.roi_polygon], (0, 255, 255))  # Yellow fill
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            
            # ROI border
            cv2.polylines(frame, [self.roi_polygon], True, (0, 255, 255), 3)
            
            # ROI label
            roi_center_x = int(np.mean([p[0] for p in self.roi_pixels]))
            roi_center_y = int(np.mean([p[1] for p in self.roi_pixels]))
            cv2.putText(frame, "CONGESTION ROI", (roi_center_x - 100, roi_center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # Header
        cv2.putText(frame, f"{self.direction_name.upper()} DETECTOR (ROI ENABLED)" if self.roi_enabled else f"{self.direction_name.upper()} DETECTOR", 
                   (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        # Total count
        cv2.putText(frame, f"TOTAL: {self.total_count}", (20, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        
        # Draw counting line (thick with arrows)
        cv2.line(frame, self.line_start, self.line_end, (0, 255, 0), 4)
        
        # Draw direction arrows along line
        line_length = np.sqrt((self.line_end[0]-self.line_start[0])**2 + 
                             (self.line_end[1]-self.line_start[1])**2)
        if line_length > 0:
            dx = (self.line_end[0] - self.line_start[0]) / line_length
            dy = (self.line_end[1] - self.line_start[1]) / line_length
            
            # Draw multiple arrows
            num_arrows = max(1, int(line_length / 100))
            for i in range(num_arrows + 1):
                t = i / num_arrows
                x = int(self.line_start[0] + t * (self.line_end[0] - self.line_start[0]))
                y = int(self.line_start[1] + t * (self.line_end[1] - self.line_start[1]))
                
                # Draw perpendicular arrow
                if dx != 0:
                    perp_dy = -dx
                    perp_dx = dy
                else:
                    perp_dx = -dy
                    perp_dy = dx
                
                arrow_len = 20
                arrow_start = (int(x - perp_dx * arrow_len), int(y - perp_dy * arrow_len))
                arrow_end = (int(x + perp_dx * arrow_len), int(y + perp_dy * arrow_len))
                
                cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 255, 0), 3, tipLength=0.5)
        
        # Congestion status
        congestion_colors = {
            'none': (0, 255, 0),
            'light': (0, 255, 255),
            'moderate': (0, 165, 255),
            'heavy': (0, 0, 255),
            'severe': (128, 0, 128)
        }
        
        level = congestion_info['level']
        color = congestion_colors.get(level, (255, 255, 255))
        
        # Congestion info box (expanded to show ROI info)
        box_height = 160 if self.roi_enabled else 120
        cv2.rectangle(frame, (w - 300, 20), (w - 20, 20 + box_height), (0, 0, 0), -1)
        cv2.rectangle(frame, (w - 300, 20), (w - 20, 20 + box_height), color, 2)
        
        cv2.putText(frame, f"CONGESTION: {level.upper()}", (w - 280, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        if self.roi_enabled:
            cv2.putText(frame, f"Full Frame: {congestion_info['total_vehicles_full_frame']}", (w - 280, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(frame, f"In ROI: {congestion_info['total_vehicles']}", (w - 280, 105),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"Stationary: {congestion_info['stationary_vehicles']}", (w - 280, 130),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(frame, "ROI MODE", (w - 280, 155),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        else:
            cv2.putText(frame, f"Vehicles: {congestion_info['total_vehicles']}", (w - 280, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(frame, f"Stationary: {congestion_info['stationary_vehicles']}", (w - 280, 105),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Draw each detection
        for det in detections:
            x, y, wb, hb = det['bbox']
            name = det['class_name']
            color = det['color']
            counted = det['counted']
            valid = det['valid_direction']
            in_roi = det.get('in_roi', True)
            
            # Box color based on status
            if counted:
                box_color = (0, 255, 0)  # Green - already counted
                thickness = 3
            elif valid:
                # If ROI enabled, dim vehicles outside ROI
                if self.roi_enabled and not in_roi:
                    box_color = tuple(int(c * 0.5) for c in color)  # Dimmed color
                    thickness = 1
                else:
                    box_color = color  # Normal color - valid direction
                    thickness = 2
            else:
                box_color = (128, 128, 128)  # Gray - invalid direction
                thickness = 1
            
            cv2.rectangle(frame, (x, y), (x + wb, y + hb), box_color, thickness)
            
            # Label
            label = f"{name.upper()}"
            if counted:
                label += " ✓"
            elif not valid:
                label += " ✗DIR"
            elif self.roi_enabled and not in_roi:
                label += " [OUT]"
            
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x, y - th - 10), (x + tw + 10, y), box_color, -1)
            cv2.putText(frame, label, (x + 5, y - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def analyze_video(self, video_path, progress_callback=None, save_output=True, roi_normalized=None, **kwargs):
        """
        Main video analysis method with ROI support
        
        Args:
            video_path: Path to video file
            progress_callback: Progress update function
            save_output: Whether to save annotated video
            roi_normalized: ROI coordinates in normalized format (0.0-1.0)
                           [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        print(f"\n{'='*70}")
        print(f"🎬 STARTING {self.direction_name.upper()} ANALYSIS WITH ROI")
        print(f"{'='*70}")
        print(f"📹 Video: {video_path}")
        
        # Set ROI if provided
        if roi_normalized is not None:
            self.set_roi(roi_normalized)
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"❌ Cannot open video: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"📊 {width}x{height}, {fps:.2f} FPS, {total_frames} frames")
        if self.roi_enabled:
            print(f"🔲 ROI enabled with {len(self.roi_normalized)} points")
        else:
            print(f"🔲 ROI disabled - using full frame")
        
        # Setup video writer
        output_path = None
        out = None
        if save_output:
            os.makedirs('media/processed_videos', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            roi_suffix = "_roi" if self.roi_enabled else ""
            output_filename = f"{self.direction_name}_{timestamp}{roi_suffix}.mp4"
            output_path = os.path.join('media/processed_videos', output_filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            print(f"💾 Output: {output_path}")
        
        # Reset state
        self.reset_tracking_state()
        
        # Process frames
        frame_number = 0
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame (counting + ROI-based congestion)
            counts, detections, congestion = self.process_frame(frame, frame_number, fps)
            
            # Draw visualizations
            annotated = self.draw_detections(frame.copy(), detections, congestion, fps)
            
            if out is not None:
                out.write(annotated)
            
            # Progress callback
            if progress_callback and frame_number % 50 == 0:
                progress = min(88, 15 + int((frame_number / total_frames) * 73))
                message = f"Processing {frame_number}/{total_frames}"
                progress_callback(progress, total_frames, message)
            
            frame_number += 1
        
        # Cleanup
        cap.release()
        if out is not None:
            out.release()
        
        processing_time = time.time() - start_time
        
        print(f"\n✅ Analysis completed in {processing_time:.2f}s")
        print(f"📈 Vehicles counted: {self.total_count}")
        print(f"📊 Breakdown: {dict(self.vehicle_counts)}")
        
        # Generate final report
        report = self.generate_report(total_frames, processing_time, fps)
        
        if output_path:
            report['output_video_path'] = output_path
        
        return report
    
    def generate_report(self, total_frames, proc_time, fps):
        """Generate comprehensive report with ROI information"""
        duration = total_frames / fps if fps > 0 else 0
        
        # Get congestion summary
        congestion_summary = self.congestion_module.get_congestion_summary()
        
        # Calculate vehicles per minute
        vpm = (self.total_count / duration) * 60 if duration > 0 else 0
        
        return {
            'metadata': {
                'direction': self.direction_name,
                'duration_seconds': round(duration, 1),
                'processing_time_seconds': round(proc_time, 1),
                'frames_processed': total_frames,
                'fps': round(fps, 2),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'model': 'YOLOv8',
                'vehicle_classes': self.counted_classes,
                'roi_enabled': self.roi_enabled,
                'roi_normalized': self.roi_normalized
            },
            'counting_results': {
                'total_vehicles': self.total_count,
                'vehicle_breakdown': dict(self.vehicle_counts),
                'vehicles_per_minute': round(vpm, 1),
                'counted_tracks': len(self.counted_vehicles),
                'counting_area': 'Full Frame'
            },
            'congestion_results': {
                'total_events': congestion_summary['total_events'],
                'total_congestion_time': round(congestion_summary['total_congestion_time'], 1),
                'events_by_level': dict(congestion_summary['events_by_level']),
                'average_event_duration': round(congestion_summary['average_event_duration'], 1),
                'final_congestion_level': congestion_summary['current_level'],
                'detection_area': 'ROI' if self.roi_enabled else 'Full Frame',
                'roi_configuration': self.roi_normalized if self.roi_enabled else None
            },
            'raw_data': {
                'frame_data': self.results['frame_data'],
                'congestion_events': self.congestion_module.congestion_events,
                'vehicle_counts': dict(self.results['vehicle_counts']),
                'roi_config': self.results['roi_config']
            }
        }