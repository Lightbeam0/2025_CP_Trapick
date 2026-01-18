# ml/directional_detectors/vertical_bottom_top.py
"""
Vertical Bottom→Top Directional Detector
Counts vehicles moving from BOTTOM to TOP of frame
Counting line at top 1/3, vehicles must exit upward
"""

import cv2
import numpy as np
import torch
from collections import defaultdict, deque
from ultralytics import YOLO

from ..base_detector import BaseDetector


class VerticalBottomTopDetector(BaseDetector):
    """Count vehicles moving from BOTTOM to TOP"""
    
    def __init__(self, model_path='yolov8l.pt'):
        super().__init__()
        
        print(f"\n{'='*70}")
        print(f"🚦 VERTICAL BOTTOM→TOP DIRECTIONAL DETECTOR")
        print(f"{'='*70}")
        
        # Load YOLO model
        print(f"📂 Loading YOLOv8 model: {model_path}")
        self.model = YOLO(model_path)
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        print(f"✅ Device: {self.device.upper()}")
        
        # Direction-specific attributes
        self.direction_name = "Vertical Bottom→Top"
        self.valid_direction = (0, -1)  # Moving upward (negative Y)
        
        print(f"\n🎯 Configuration:")
        print(f"   Direction: {self.direction_name}")
        print(f"   Counting line: Top 1/3 of frame")
        print(f"   Valid movement: Upward (Y decreasing)")
        print(f"   Vehicle classes: {len(self.counted_classes)} types")
        print(f"{'='*70}\n")
    
    def setup_counting_line(self, frame_width, frame_height):
        """Set counting line at top 1/3 of frame"""
        # Counting line near top (vehicles exiting upward)
        line_start = (int(frame_width * 0.2), int(frame_height * 0.3))
        line_end = (int(frame_width * 0.8), int(frame_height * 0.3))
        
        # Valid direction: pointing upward (negative Y)
        valid_direction = (0, -1)
        
        print(f"🎯 Counting line set:")
        print(f"   Start: {line_start}")
        print(f"   End: {line_end}")
        print(f"   Direction: Upward (negative Y)")
        
        return line_start, line_end, valid_direction
    
    def is_valid_direction(self, track_history, valid_direction_vector):
        """Check if vehicle is moving upward (Y decreasing)"""
        if len(track_history) < 3:
            return False
        
        # Get recent trajectory points
        points = list(track_history)
        if len(points) < 5:
            recent_points = points
        else:
            recent_points = points[-5:]
        
        # Check Y movement (should be decreasing = moving up)
        ys = [p[1] for p in recent_points]
        
        # Calculate Y changes
        if len(ys) < 2:
            return False
            
        y_changes = [ys[i+1] - ys[i] for i in range(len(ys)-1)]
        
        # Must have majority of movements upward (negative change)
        upward_moves = sum(1 for change in y_changes if change < -2)
        downward_moves = sum(1 for change in y_changes if change > 2)
        
        # More upward than downward movement
        return upward_moves > downward_moves and upward_moves >= len(y_changes) * 0.5
    
    def check_line_crossing(self, prev_point, current_point):
        """Check if vehicle crossed the counting line (upward only)"""
        if prev_point is None or current_point is None:
            return False
            
        x1, y1 = prev_point
        x2, y2 = current_point
        x3, y3 = self.line_start
        x4, y4 = self.line_end
        
        # Line intersection formula
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        
        if denom == 0:
            return False  # Lines are parallel
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        # Check if intersection is within both line segments
        # AND vehicle is moving upward (y2 < y1)
        return (0 <= t <= 1 and 0 <= u <= 1 and y2 < y1)
    
    def process_frame(self, frame, frame_number, fps):
        """Process single frame for detection and counting"""
        # Initialize counting line on first frame
        if not hasattr(self, 'line_start'):
            h, w = frame.shape[:2]
            self.line_start, self.line_end, self.valid_direction = self.setup_counting_line(w, h)
        
        counts = defaultdict(int)
        detections = []
        
        # Run YOLO detection
        results = self.model.track(
            frame,
            persist=True,
            conf=0.4,
            classes=self.vehicle_class_ids,
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
                
                # Center point
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                
                # Add to track history
                self.track_history[tid].append((cx, cy))
                
                # Initialize vehicle status if new
                if tid not in self.vehicle_status:
                    self.vehicle_status[tid] = {
                        'name': name,
                        'crossed': False,
                        'valid_direction': False,
                        'last_position': (cx, cy)
                    }
                
                status = self.vehicle_status[tid]
                prev_position = status['last_position']
                
                # Check direction validity
                if not status['valid_direction']:
                    status['valid_direction'] = self.is_valid_direction(
                        self.track_history[tid], self.valid_direction
                    )
                
                # Check if crossing counting line
                if (status['valid_direction'] and not status['crossed'] and 
                    len(self.track_history[tid]) >= 2):
                    
                    if self.check_line_crossing(prev_position, (cx, cy)):
                        status['crossed'] = True
                        self.total_count += 1
                        self.vehicle_counts[name] += 1
                        self.counted_vehicles.add(tid)
                        
                        print(f"✓ #{self.total_count:03d} {name.upper()} ID:{tid} COUNTED (BOTTOM→TOP)")
                
                # Update last position
                status['last_position'] = (cx, cy)
                
                # Calculate speed
                speed = self.calculate_speed(tid, (cx, cy), frame_number, fps)
                
                # Create detection dict
                detection_data = {
                    'track_id': int(tid),
                    'class_name': name,
                    'center': (cx, cy),
                    'bbox': [x1, y1, x2-x1, y2-y1],
                    'confidence': float(conf),
                    'color': self.colors[name],
                    'counted': status['crossed'],
                    'valid_direction': status['valid_direction'],
                    'speed': speed
                }
                
                detections.append(detection_data)
                counts[name] += 1
        
        # Calculate congestion
        congestion_info = self.calculate_congestion_level(detections, fps)
        
        # Update frame counter
        self.frame_count = frame_number
        
        return counts, detections, congestion_info
    
    def draw_detections(self, frame, detections, congestion_info, fps):
        """Draw visualizations for this direction"""
        h, w = frame.shape[:2]
        
        # Header
        cv2.putText(frame, "VERTICAL BOTTOM→TOP DETECTOR", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        # Total count
        cv2.putText(frame, f"TOTAL: {self.total_count}", (20, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        
        # Draw counting line (thick green line)
        cv2.line(frame, self.line_start, self.line_end, (0, 255, 0), 4)
        
        # Draw upward arrows along line
        line_length = np.sqrt((self.line_end[0]-self.line_start[0])**2 + 
                             (self.line_end[1]-self.line_start[1])**2)
        if line_length > 0:
            dx = (self.line_end[0] - self.line_start[0]) / line_length
            dy = (self.line_end[1] - self.line_start[1]) / line_length
            
            # Draw multiple upward arrows
            num_arrows = max(1, int(line_length / 100))
            for i in range(num_arrows + 1):
                t = i / num_arrows
                x = int(self.line_start[0] + t * (self.line_end[0] - self.line_start[0]))
                y = int(self.line_start[1] + t * (self.line_end[1] - self.line_start[1]))
                
                # Draw upward arrow
                arrow_len = 25
                arrow_start = (x, y + arrow_len)
                arrow_end = (x, y - arrow_len)
                
                cv2.arrowedLine(frame, arrow_start, arrow_end, (0, 255, 0), 3, tipLength=0.5)
        
        # Add direction label
        cv2.putText(frame, "COUNTING LINE (BOTTOM→TOP)", 
                   (self.line_start[0], self.line_start[1] - 15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
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
        
        # Congestion info box
        cv2.rectangle(frame, (w - 300, 20), (w - 20, 120), (0, 0, 0), -1)
        cv2.rectangle(frame, (w - 300, 20), (w - 20, 120), color, 2)
        
        cv2.putText(frame, f"CONGESTION: {level.upper()}", (w - 280, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, f"Vehicles: {congestion_info['total_vehicles']}", (w - 280, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(frame, f"Stationary: {congestion_info['stationary_vehicles']}", (w - 280, 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Draw each detection
        for det in detections:
            x, y, wb, hb = det['bbox']
            name = det['class_name']
            color = det['color']
            counted = det['counted']
            valid = det['valid_direction']
            speed = det.get('speed')
            
            # Box color based on status
            if counted:
                box_color = (0, 255, 0)  # Green - counted
                thickness = 3
            elif valid:
                box_color = color  # Normal color
                thickness = 2
            else:
                box_color = (128, 128, 128)  # Gray - invalid
                thickness = 1
            
            cv2.rectangle(frame, (x, y), (x + wb, y + hb), box_color, thickness)
            
            # Label
            label = f"{name.upper()}"
            if speed: 
                label += f" {speed:.0f}kmh"
            if counted:
                label += " ✓"
            elif not valid:
                label += " ✗DIR"
            
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x, y - th - 10), (x + tw + 10, y), box_color, -1)
            cv2.putText(frame, label, (x + 5, y - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame