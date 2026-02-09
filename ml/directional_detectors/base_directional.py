# ml/directional_detectors/base_directional.py
"""
UPDATED Base Directional Detector with Enhanced Congestion Detection
REPLACES: Original base_directional.py

Key Changes:
✅ Uses enhanced CongestionModule with multi-factor scoring
✅ Adds speed calculation for vehicles
✅ Enhanced visualization showing clustering and scores
✅ Backward compatible - same API
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
import time
import os
from pathlib import Path
from ultralytics import YOLO
import torch

# FIXED IMPORT - use the correct class name
from ..enhanced_tracker import EnhancedByteTrackWrapper
from ..base_detector import BaseDetector
from ..congestion_module import CongestionModule  # ✅ Now uses enhanced version


class BaseDirectionalDetector(BaseDetector):
    """
    Base class for all 8 directional detectors
    ✅ NOW ENHANCED with ROI support and advanced congestion detection
    
    Handles:
    - YOLO detection
    - Directional counting logic (full frame)
    - ROI-based congestion detection with clustering
    - Result storage
    """
    
    def __init__(self, direction_name, model_path='yolov8l.pt'):
        print(f"\n{'='*70}")
        print(f"🚦 {direction_name.upper()} DIRECTIONAL DETECTOR (ENHANCED)")
        print(f"{'='*70}")
        
        # Load YOLO model
        print(f"📂 Loading YOLOv8 model: {model_path}")
        self.model = YOLO(model_path)
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        print(f"✅ Device: {self.device.upper()}")

        # Initialize enhanced tracker
        self.tracker = EnhancedByteTrackWrapper()
        print(f"✓ Enhanced tracker initialized")
        
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
        
        # Class-specific confidence thresholds
        self.class_confidence_thresholds = {
            'car': 0.3,
            'motorcycle': 0.25,
            'bus': 0.35,
            'truck': 0.35
        }
        
        # Direction name for reporting
        self.direction_name = direction_name
        
        # ROI configuration
        self.roi_enabled = False
        self.roi_normalized = None
        self.roi_pixels = None
        self.roi_polygon = None
        self.roi_area = None
        
        # ✅ ENHANCED: Initialize congestion module (now with advanced features)
        self.congestion_module = CongestionModule()
        
        # Reset tracking state
        self.reset_tracking_state()
        
        print(f"\n🎯 Configuration:")
        print(f"   Direction: {direction_name}")
        print(f"   Model: YOLOv8 (COCO)")
        print(f"   Counting: {len(self.counted_classes)} vehicle types (full frame)")
        print(f"   Congestion: Enhanced multi-factor detection")
        print(f"   Features: Density + Clustering + Smoothing ✓")
        print(f"{'='*70}\n")
    
    def reset_tracking_state(self):
        """Reset all tracking state"""
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
    
    def set_roi(self, roi_normalized):
        """
        Set Region of Interest for congestion detection
        
        Args:
            roi_normalized: List of normalized [x, y] coordinates (0.0 to 1.0)
                           None to disable ROI (use full frame)
        """
        if roi_normalized is None or len(roi_normalized) == 0:
            self.roi_enabled = False
            self.roi_normalized = None
            self.roi_pixels = None
            self.roi_polygon = None
            self.roi_area = None
            print("🔲 ROI disabled - using full frame for congestion detection")
            return
        
        if len(roi_normalized) < 3:
            raise ValueError("ROI must have at least 3 points")
        
        # Validate and normalize coordinates
        valid_coords = []
        for x, y in roi_normalized:
            x = max(0.0, min(1.0, float(x)))
            y = max(0.0, min(1.0, float(y)))
            valid_coords.append([x, y])
        
        self.roi_normalized = valid_coords
        self.roi_enabled = True
        
        print(f"✅ ROI set with {len(self.roi_normalized)} points")
        print(f"   Normalized coordinates: {self.roi_normalized}")
        print(f"   Congestion will be detected within ROI only")
    
    def _setup_roi_pixels(self, frame_width, frame_height):
        """Convert normalized ROI to pixel coordinates"""
        if not self.roi_enabled or self.roi_normalized is None:
            # If no ROI, use full frame area
            self.roi_area = frame_width * frame_height
            return
        
        # Convert normalized coordinates to pixels
        self.roi_pixels = [
            [int(x * frame_width), int(y * frame_height)]
            for x, y in self.roi_normalized
        ]
        
        # Create polygon for point-in-polygon tests
        self.roi_polygon = np.array(self.roi_pixels, dtype=np.int32)
        
        # ✅ ENHANCED: Calculate ROI area using Shoelace formula
        x = [p[0] for p in self.roi_pixels]
        y = [p[1] for p in self.roi_pixels]
        self.roi_area = 0.5 * abs(sum(x[i]*y[i+1] - x[i+1]*y[i] 
                                     for i in range(len(x)-1)))
        
        print(f"📐 ROI pixel coordinates: {self.roi_pixels}")
        print(f"   Frame size: {frame_width}x{frame_height}")
        print(f"   ROI area: {self.roi_area:.0f} pixels²")  # ✅ NEW
    
    def _is_point_in_roi(self, x, y):
        """Check if point is inside ROI"""
        if not self.roi_enabled:
            return True  # No ROI = everything is valid
        
        point = (float(x), float(y))
        result = cv2.pointPolygonTest(self.roi_polygon, point, False)
        return result >= 0
    
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
    
    def enhanced_is_valid_direction(self, history, valid_direction_vector):
        """Enhanced direction validation"""
        if len(history) < 5:
            return False
        
        points = list(history)
        dx_values = []
        dy_values = []
        
        for i in range(len(points)-1):
            dx = points[i+1][0] - points[i][0]
            dy = points[i+1][1] - points[i][1]
            
            if abs(dx) > 2 or abs(dy) > 2:
                dx_values.append(dx)
                dy_values.append(dy)
        
        if not dx_values or not dy_values:
            return False
        
        expected_dx, expected_dy = valid_direction_vector
        valid_movements = 0
        
        for dx, dy in zip(dx_values, dy_values):
            if expected_dx != 0:
                if (expected_dx > 0 and dx > 2) or (expected_dx < 0 and dx < -2):
                    valid_movements += 1
            if expected_dy != 0:
                if (expected_dy > 0 and dy > 2) or (expected_dy < 0 and dy < -2):
                    valid_movements += 1
        
        return valid_movements >= len(dx_values) * 0.6

    def check_line_crossing(self, prev_point, current_point):
        """Check if line segment crosses counting line"""
        x1, y1 = prev_point
        x2, y2 = current_point
        x3, y3 = self.line_start
        x4, y4 = self.line_end
        
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        
        if denom == 0:
            return False
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        return 0 <= t <= 1 and 0 <= u <= 1

    def enhanced_check_line_crossing(self, prev_point, current_point):
        """Enhanced line crossing with distance check"""
        if prev_point is None or current_point is None:
            return False
        
        crosses = self.check_line_crossing(prev_point, current_point)
        
        if not crosses:
            return False
        
        distance = np.sqrt(
            (current_point[0] - prev_point[0])**2 + 
            (current_point[1] - prev_point[1])**2
        )
        
        return distance > 5
    
    def process_frame(self, frame, frame_number, fps):
        """✅ ENHANCED: Process single frame with speed calculation and advanced congestion"""
        # Initialize counting line and ROI on first frame
        if not hasattr(self, 'counting_line_setup'):
            h, w = frame.shape[:2]
            self.line_start, self.line_end, self.valid_direction = self.setup_counting_line(w, h)
            self._setup_roi_pixels(w, h)
            self.counting_line_setup = True
        
        # Run YOLO detection with enhanced ByteTrack
        results = self.model.track(
            frame,
            persist=True,
            conf=0.3,
            classes=self.vehicle_class_ids,
            tracker="bytetrack.yaml",
            verbose=False,
            device=self.device
        )
        
        # Process tracks
        processed_tracks = self.tracker.postprocess_tracks(results, frame_number, fps)
        
        detections = []
        detections_in_roi = []
        current_counts = defaultdict(int)
        
        for track in processed_tracks:
            if not track.get('is_valid', True):
                continue
            
            track_id = track['track_id']
            box = track['box']
            cx, cy = track['center']
            
            class_id = track.get('class_id')
            if class_id not in self.class_names:
                continue
            name = self.class_names[class_id]
            
            confidence = track.get('confidence', 0.0)
            threshold = self.class_confidence_thresholds.get(name, 0.3)
            if confidence < threshold:
                continue
            
            # Check ROI
            in_roi = self._is_point_in_roi(cx, cy)
            
            # Get history
            history_points = self.tracker.get_track_history(track_id)
            
            # Initialize status
            if track_id not in self.vehicle_status:
                self.vehicle_status[track_id] = {
                    'name': name,
                    'crossed': False,
                    'valid_direction': False,
                    'history': deque(maxlen=10)
                }
            
            status = self.vehicle_status[track_id]
            status['history'].append((cx, cy))
            
            # Check direction
            if not status['valid_direction'] and len(status['history']) >= 5:
                status['valid_direction'] = self.enhanced_is_valid_direction(
                    status['history'], self.valid_direction
                )
            
            # Check crossing
            if (status['valid_direction'] and not status['crossed'] and 
                len(status['history']) >= 3):
                
                if len(status['history']) >= 2:
                    prev_points = list(status['history'])
                    prev_cx, prev_cy = prev_points[-2]
                    
                    if self.enhanced_check_line_crossing((prev_cx, prev_cy), (cx, cy)):
                        status['crossed'] = True
                        self.total_count += 1
                        self.vehicle_counts[name] += 1
                        self.counted_vehicles.add(track_id)
                        
                        print(f"✓ #{self.total_count:03d} {name.upper()} ID:{track_id}")
            
            # ✅ ENHANCED: Calculate speed for congestion analysis
            speed = None
            if len(status['history']) >= 2:
                prev_points = list(status['history'])
                p1 = prev_points[-2]
                p2 = prev_points[-1]
                distance_pixels = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                
                # Rough conversion: 10 pixels = 1 meter
                pixels_per_meter = 10
                time_elapsed = 1 / fps if fps > 0 else 0.033
                distance_meters = distance_pixels / pixels_per_meter
                
                if time_elapsed > 0:
                    speed_mps = distance_meters / time_elapsed
                    speed = min(speed_mps * 3.6, 200)  # km/h, capped at 200
            
            # Create detection
            detection_data = {
                'track_id': track_id,
                'class_name': name,
                'center': (cx, cy),
                'bbox': box,
                'confidence': confidence,
                'color': self.colors[name],
                'counted': status['crossed'],
                'valid_direction': status['valid_direction'],
                'stability': track.get('stability', 0.0),
                'in_roi': in_roi,
                'speed': speed  # ✅ ENHANCED: Add speed
            }
            
            detections.append(detection_data)
            
            if in_roi:
                detections_in_roi.append(detection_data)
            
            current_counts[name] += 1
        
        # ✅ ENHANCED: Advanced congestion detection with all new features
        congestion_info = self.congestion_module.detect_congestion(detections_in_roi, fps)
        
        # Add extra statistics
        congestion_info['total_vehicles_full_frame'] = len(detections)
        congestion_info['total_vehicles_in_roi'] = len(detections_in_roi)
        congestion_info['roi_enabled'] = self.roi_enabled
        
        # ✅ ENHANCED: Store detailed frame data
        frame_data = {
            'frame_number': frame_number,
            'timestamp': frame_number / fps if fps > 0 else 0,
            'vehicle_count_full_frame': sum(current_counts.values()),
            'vehicle_count_in_roi': len(detections_in_roi),
            'counted_this_frame': self.total_count - self.results['vehicle_counts'].get('total', 0),
            'congestion_level': congestion_info['level'],
            'congestion_score': congestion_info.get('congestion_score', 0),  # ✅ NEW
            'stationary_vehicles': congestion_info['stationary_vehicles'],
            'clustering_info': congestion_info.get('clustering_info', {}),  # ✅ NEW
            'score_breakdown': congestion_info.get('score_breakdown', {}),  # ✅ NEW
            'roi_enabled': self.roi_enabled
        }
        self.results['frame_data'].append(frame_data)
        
        self.frame_count = frame_number
        
        return current_counts, detections, congestion_info
    
    def draw_detections(self, frame, detections, congestion_info, fps):
        """✅ ENHANCED: Draw with clustering visualization and detailed scores"""
        h, w = frame.shape[:2]
        
        # Draw ROI polygon
        if self.roi_enabled and self.roi_polygon is not None:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [self.roi_polygon], (0, 255, 255))
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            cv2.polylines(frame, [self.roi_polygon], True, (0, 255, 255), 3)
            
            # ROI label
            roi_center_x = int(np.mean([p[0] for p in self.roi_pixels]))
            roi_center_y = int(np.mean([p[1] for p in self.roi_pixels]))
            cv2.putText(frame, "CONGESTION ROI", (roi_center_x - 100, roi_center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # Header
        title = f"{self.direction_name.upper()} DETECTOR (ENHANCED)" if self.roi_enabled else f"{self.direction_name.upper()} DETECTOR"
        cv2.putText(frame, title, (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        # Total count
        cv2.putText(frame, f"TOTAL: {self.total_count}", (20, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        
        # Draw counting line with arrows
        cv2.line(frame, self.line_start, self.line_end, (0, 255, 0), 4)
        
        # Direction arrows
        line_length = np.sqrt((self.line_end[0]-self.line_start[0])**2 + 
                             (self.line_end[1]-self.line_start[1])**2)
        if line_length > 0:
            dx = (self.line_end[0] - self.line_start[0]) / line_length
            dy = (self.line_end[1] - self.line_start[1]) / line_length
            
            num_arrows = max(1, int(line_length / 100))
            for i in range(num_arrows + 1):
                t = i / num_arrows
                x = int(self.line_start[0] + t * (self.line_end[0] - self.line_start[0]))
                y = int(self.line_start[1] + t * (self.line_end[1] - self.line_start[1]))
                
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
        
        # ✅ ENHANCED: Congestion info box with clustering details
        congestion_colors = {
            'none': (0, 255, 0),
            'light': (0, 255, 255),
            'moderate': (0, 165, 255),
            'heavy': (0, 0, 255),
            'severe': (128, 0, 128)
        }
        
        level = congestion_info['level']
        color = congestion_colors.get(level, (255, 255, 255))
        score = congestion_info.get('congestion_score', 0)
        
        # Larger info box for enhanced data
        box_height = 220 if self.roi_enabled else 180
        cv2.rectangle(frame, (w - 320, 20), (w - 20, 20 + box_height), (0, 0, 0), -1)
        cv2.rectangle(frame, (w - 320, 20), (w - 20, 20 + box_height), color, 2)
        
        y_offset = 50
        line_height = 25
        
        cv2.putText(frame, f"CONGESTION: {level.upper()}", (w - 300, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        y_offset += line_height
        
        # ✅ ENHANCED: Show congestion score
        cv2.putText(frame, f"Score: {score}/100", (w - 300, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += line_height
        
        if self.roi_enabled:
            cv2.putText(frame, f"Full Frame: {congestion_info['total_vehicles_full_frame']}", (w - 300, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset += line_height - 5
            cv2.putText(frame, f"In ROI: {congestion_info['total_vehicles']}", (w - 300, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            y_offset += line_height
        else:
            cv2.putText(frame, f"Vehicles: {congestion_info.get('total_vehicles', 0)}", (w - 300, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            y_offset += line_height
        
        cv2.putText(frame, f"Stationary: {congestion_info.get('stationary_vehicles', 0)}", (w - 300, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += line_height
        
        # ✅ ENHANCED: Show clustering info
        cluster_info = congestion_info.get('clustering_info', {})
        num_clusters = cluster_info.get('num_clusters', 0)
        clustered = cluster_info.get('clustered_vehicles', 0)
        
        cv2.putText(frame, f"Clusters: {num_clusters}", (w - 300, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        y_offset += line_height - 5
        
        cv2.putText(frame, f"Clustered: {clustered}", (w - 300, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        y_offset += line_height
        
        if self.roi_enabled:
            cv2.putText(frame, "ROI MODE", (w - 300, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
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
                box_color = (0, 255, 0)
                thickness = 3
            elif valid:
                if self.roi_enabled and not in_roi:
                    box_color = tuple(int(c * 0.5) for c in color)
                    thickness = 1
                else:
                    box_color = color
                    thickness = 2
            else:
                box_color = (128, 128, 128)
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
        """Main video analysis method with ROI support"""
        print(f"\n{'='*70}")
        print(f"🎬 STARTING {self.direction_name.upper()} ANALYSIS (ENHANCED)")
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
        """✅ ENHANCED: Generate comprehensive report with clustering stats"""
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
                'video_fps': round(fps, 2),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'model': 'YOLOv8',
                'congestion_module': 'Enhanced Multi-Factor',  # ✅ NEW
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
                'frame_data': self.results['frame_data'][-1000:],
                'congestion_events': self.congestion_module.congestion_events,
                'vehicle_counts': dict(self.results['vehicle_counts']),
                'roi_config': self.results['roi_config']
            }
        }