import cv2
from ultralytics import YOLO
import numpy as np
from collections import defaultdict
from django.db import transaction
import time
from scipy.spatial import distance
from scipy.optimize import linear_sum_assignment

class VehicleDetector:
    def __init__(self, model_size='n', frame_skip=5, min_confidence=0.5):
        """
        Enhanced vehicle detector with tracking and speed estimation.
        
        Args:
            model_size (str): Model size (n, s, m, l, x)
            frame_skip (int): Process every nth frame for performance
            min_confidence (float): Minimum detection confidence threshold
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
        self.frame_skip = frame_skip
        self.min_confidence = min_confidence
        self.tracker = VehicleTracker()
        self.previous_detections = []

    def process_video(self, video_path, progress_callback=None, px_to_meters=0.1):
        """
        Process video with enhanced tracking and speed estimation.
        
        Args:
            video_path (str): Path to video file
            progress_callback (func): Progress reporting callback
            px_to_meters (float): Pixel to meters conversion factor
            
        Returns:
            dict: Enhanced detection results with tracking and speed data
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
        speed_data = []

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                timestamp = frame_count / fps
                
                if frame_count % self.frame_skip == 0:
                    # Process frame and filter by confidence
                    detections = self.model(frame, classes=self.vehicle_classes, verbose=False)
                    current_detections = []
                    
                    for detection in detections:
                        for box in detection.boxes:
                            if float(box.conf) < self.min_confidence:
                                continue
                                
                            class_id = int(box.cls)
                            vehicle_type = detection.names[class_id]
                            bbox = box.xyxy[0].tolist()
                            
                            current_detections.append({
                                'frame': frame_count,
                                'timestamp': timestamp,
                                'vehicle_type': vehicle_type,
                                'confidence': float(box.conf),
                                'bbox': bbox
                            })
                    
                    # Track vehicles and estimate speed
                    if self.previous_detections:
                        tracked_detections = self.tracker.update(current_detections)
                        speeds = self.estimate_speed(
                            self.previous_detections,
                            tracked_detections,
                            fps,
                            px_to_meters
                        )
                        speed_data.extend(speeds)
                        
                        for det, speed in zip(tracked_detections, speeds):
                            det['speed'] = speed
                            results.append(det)
                    else:
                        results.extend(self.tracker.update(current_detections))
                    
                    self.previous_detections = current_detections.copy()
                    
                    # Update counts
                    for det in current_detections:
                        hour = int(timestamp / 3600) % 24
                        hourly_counts[hour][det['vehicle_type']] += 1
                        vehicle_types[det['vehicle_type']] += 1
                
                if progress_callback and frame_count % 100 == 0:
                    progress = (frame_count / total_frames) * 100
                    progress_callback(progress)
                    
        finally:
            cap.release()
        
        avg_speed = np.mean(speed_data) if speed_data else 0
        
        return {
            'detections': results,
            'hourly_counts': hourly_counts,
            'vehicle_types': dict(vehicle_types),
            'speed_data': speed_data,
            'average_speed': avg_speed,
            'total_frames': total_frames,
            'processed_frames': frame_count
        }

    def estimate_speed(self, prev_detections, curr_detections, fps, px_to_meters):
        """
        Estimate vehicle speed between frames using bounding box movement.
        """
        speeds = []
        for curr in curr_detections:
            for prev in prev_detections:
                if curr.get('vehicle_id') == prev.get('vehicle_id'):
                    # Calculate centroid movement
                    prev_center = self._get_bbox_center(prev['bbox'])
                    curr_center = self._get_bbox_center(curr['bbox'])
                    
                    # Calculate distance in meters
                    distance_px = distance.euclidean(prev_center, curr_center)
                    distance_m = distance_px * px_to_meters
                    
                    # Calculate speed (km/h)
                    time_elapsed = self.frame_skip / fps  # seconds between processed frames
                    speed_mps = distance_m / time_elapsed
                    speed_kph = speed_mps * 3.6
                    
                    speeds.append(speed_kph)
                    break
        return speeds

    def _get_bbox_center(self, bbox):
        """Calculate bounding box center coordinates."""
        return [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]

    @staticmethod
    @transaction.atomic
    def save_detection_results(video_id, results):
        """Save results to database with enhanced data."""
        from .models import VehicleDetection, TrafficAnalysis
        
        # Batch processing for efficiency
        batch_size = 1000
        detections = [
            VehicleDetection(
                video_id=video_id,
                frame_number=det['frame'],
                timestamp=det['timestamp'],
                vehicle_type=det['vehicle_type'],
                confidence=det['confidence'],
                bbox=det.get('bbox', []),
                speed=det.get('speed', None),
                vehicle_id=det.get('vehicle_id', None)
            ) for det in results['detections']
        ]
        
        for i in range(0, len(detections), batch_size):
            VehicleDetection.objects.bulk_create(detections[i:i+batch_size])
        
        # Save traffic analysis
        for hour, counts in results['hourly_counts'].items():
            TrafficAnalysis.objects.create(
                video_id=video_id,
                hour_of_day=hour,
                vehicle_count=sum(counts.values()),
                vehicle_types=dict(counts),
                average_speed=results.get('average_speed', 0)
            )
        
        return len(detections)


class VehicleTracker:
    """Enhanced vehicle tracker with IOU matching."""
    
    def __init__(self, max_disappeared=5):
        self.next_id = 0
        self.tracks = {}
        self.max_disappeared = max_disappeared
        self.disappeared = {}

    def update(self, detections):
        """Update tracks with new detections using IOU matching."""
        if len(detections) == 0:
            self._update_disappeared()
            return []
            
        # Initialize track IDs for new detections
        if len(self.tracks) == 0:
            for det in detections:
                self._add_new_track(det)
            return detections
            
        # Match existing tracks to detections
        det_boxes = [det['bbox'] for det in detections]
        track_ids = list(self.tracks.keys())
        track_boxes = [self.tracks[tid]['bbox'] for tid in track_ids]
        
        # Calculate IOU matrix
        iou_matrix = self._calculate_iou_matrix(track_boxes, det_boxes)
        
        # Match using Hungarian algorithm
        matched_pairs = self._match_tracks(iou_matrix)
        
        # Update matched tracks
        for tid_idx, det_idx in matched_pairs:
            tid = track_ids[tid_idx]
            self.tracks[tid] = detections[det_idx]
            detections[det_idx]['vehicle_id'] = tid
            self.disappeared[tid] = 0
            
        # Handle unmatched tracks and detections
        self._handle_unmatched(detections, track_ids, matched_pairs)
        
        return detections

    def _add_new_track(self, detection):
        tid = self.next_id
        self.next_id += 1
        detection['vehicle_id'] = tid
        self.tracks[tid] = detection
        self.disappeared[tid] = 0

    def _calculate_iou_matrix(self, boxes1, boxes2):
        """Calculate Intersection over Union matrix."""
        iou_matrix = np.zeros((len(boxes1), len(boxes2)))
        for i, box1 in enumerate(boxes1):
            for j, box2 in enumerate(boxes2):
                iou_matrix[i,j] = self._calculate_iou(box1, box2)
        return iou_matrix

    def _calculate_iou(self, box1, box2):
        """Calculate Intersection over Union for two bounding boxes."""
        # Calculate intersection area
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        
        # Calculate union area
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0

    def _match_tracks(self, iou_matrix):
        """Match tracks to detections using Hungarian algorithm."""
        row_ind, col_ind = linear_sum_assignment(-iou_matrix)
        return [(r, c) for r, c in zip(row_ind, col_ind) if iou_matrix[r,c] > 0.3]

    def _update_disappeared(self):
        """Handle disappeared tracks."""
        to_delete = []
        for tid in self.disappeared:
            self.disappeared[tid] += 1
            if self.disappeared[tid] > self.max_disappeared:
                to_delete.append(tid)
        
        for tid in to_delete:
            del self.tracks[tid]
            del self.disappeared[tid]

    def _handle_unmatched(self, detections, track_ids, matched_pairs):
        """Handle unmatched tracks and detections."""
        # Get indices of all tracks and detections
        all_track_indices = set(range(len(track_ids)))
        all_det_indices = set(range(len(detections)))
        
        # Get matched indices
        matched_track_indices = {pair[0] for pair in matched_pairs}
        matched_det_indices = {pair[1] for pair in matched_pairs}
        
        # Find unmatched tracks and detections
        unmatched_track_indices = all_track_indices - matched_track_indices
        unmatched_det_indices = all_det_indices - matched_det_indices
        
        # Mark unmatched tracks as disappeared
        for tid_idx in unmatched_track_indices:
            tid = track_ids[tid_idx]
            self.disappeared[tid] += 1
            if self.disappeared[tid] > self.max_disappeared:
                del self.tracks[tid]
                del self.disappeared[tid]
        
        # Add new tracks for unmatched detections
        for det_idx in unmatched_det_indices:
            self._add_new_track(detections[det_idx])