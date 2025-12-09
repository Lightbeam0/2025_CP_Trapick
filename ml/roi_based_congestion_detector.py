# ml/roi_based_congestion_detector.py
import cv2
import numpy as np
from collections import defaultdict, deque
from .base_detector import BaseDetector
import logging

logger = logging.getLogger(__name__)


class ROIBasedCongestionDetector(BaseDetector):
    """
    A standalone detector for congestion monitoring within a user-defined normalized ROI.
    Does NOT depend on RTXVehicleDetector or any other external detector.
    Replace `run_detection()` and `simple_tracker()` with your real model when ready.
    """

    def __init__(self, **config):
        super().__init__()
        self.config = config
        self.setup_enhanced_metrics()

        # Congestion thresholds (override via ProcessingProfile.config_parameters)
        self.speed_threshold_kph = float(config.get('congestion_speed_threshold', 5.0))
        self.density_threshold = float(config.get('congestion_density_threshold', 0.2))
        self.min_vehicles = int(config.get('min_vehicles_for_congestion', 2))

        # Tracking state (no external detector)
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.previous_positions = {}
        self.vehicle_timestamps = defaultdict(list)

    def run_detection(self, frame):
        """
        🔧 REPLACE THIS with your actual model (e.g., collision4_model YOLOv8).
        For now: returns mock detections for testing.
        Returns: list of {'bbox': (x1,y1,x2,y2), 'class_id': int, 'confidence': float}
        """
        # Example mock detections (remove in production)
        h, w = frame.shape[:2]
        return [
            {'bbox': (w*0.2, h*0.4, w*0.3, h*0.6), 'class_id': 1, 'confidence': 0.92},   # car
            {'bbox': (w*0.7, h*0.3, w*0.8, h*0.5), 'class_id': 3, 'confidence': 0.88},   # motorcycle
        ]

    def simple_tracker(self, detections, frame_num):
        """
        🔧 REPLACE THIS with ByteTrack/DeepSORT in production.
        For now: assigns deterministic fake IDs for demo.
        Returns: list of tracks with 'id', 'cx', 'cy', 'class_name'
        """
        tracks = []
        class_names = {1: 'car', 2: 'jeep', 3: 'motorcycle', 5: 'tricycle', 6: 'truck'}

        for idx, det in enumerate(detections):
            x1, y1, x2, y2 = det['bbox']
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            cls_id = det['class_id']
            cls_name = class_names.get(cls_id, 'other')
            # Fake but stable ID: (class_id * 10000) + frame-based index
            track_id = cls_id * 10000 + (frame_num % 1000) * 10 + idx

            tracks.append({
                'id': track_id,
                'cx': cx,
                'cy': cy,
                'class_id': cls_id,
                'class_name': cls_name,
                'bbox': det['bbox']
            })
        return tracks

    def point_in_polygon(self, point, polygon):
        """Ray-casting algorithm to test point-in-polygon"""
        if len(polygon) < 3:
            return False
        x, y = point
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def polygon_area(self, polygon):
        """Shoelace formula for polygon area in pixels"""
        n = len(polygon)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += polygon[i][0] * polygon[j][1]
            area -= polygon[j][0] * polygon[i][1]
        return abs(area) / 2.0

    def analyze_video(self, video_path, progress_callback=None, save_output=False, roi_normalized=None, **kwargs):
        """
        Analyze video and compute congestion inside normalized ROI.
        Fully compatible with trapickapp/tasks.py.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        roi_pixels = None
        if roi_normalized and len(roi_normalized) >= 3:
            roi_pixels = [(int(x * width), int(y * height)) for x, y in roi_normalized]
            logger.info(f"📍 Using normalized ROI: {roi_normalized}")

        frame_data_list = []
        total_vehicles_in_roi = 0

        for frame_num in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break

            # 🔥 Standalone detection + tracking (no RTXVehicleDetector)
            detections = self.run_detection(frame)
            tracks = self.simple_tracker(detections, frame_num)

            # Filter tracks inside ROI
            tracks_in_roi = tracks
            if roi_pixels:
                tracks_in_roi = [
                    t for t in tracks
                    if self.point_in_polygon((t['cx'], t['cy']), roi_pixels)
                ]

            # Compute speed and congestion
            speeds = []
            for t in tracks_in_roi:
                speed = self.calculate_speed(t['id'], (t['cx'], t['cy']), frame_num, fps)
                if speed is not None:
                    speeds.append(speed)

            avg_speed = float(np.mean(speeds)) if speeds else 0.0
            roi_area = self.polygon_area(roi_pixels) if roi_pixels else (width * height)
            density = len(tracks_in_roi) / max(roi_area, 1e-6)

            is_congested = False
            if len(tracks_in_roi) >= self.min_vehicles:
                is_congested = (avg_speed < self.speed_threshold_kph) and (density > self.density_threshold)

            frame_data_list.append({
                'frame_number': frame_num,
                'roi_congested': is_congested,
                'roi_vehicle_count': len(tracks_in_roi),
                'roi_avg_speed_kph': avg_speed,
                'timestamp_seconds': frame_num / fps,
            })
            total_vehicles_in_roi += len(tracks_in_roi)

            if progress_callback:
                progress = 10 + int((frame_num / total_frames) * 78)
                try:
                    progress_callback(progress, total_frames, f"Frame {frame_num}/{total_frames}")
                except TypeError:
                    progress_callback(frame_num, total_frames, f"Frame {frame_num}/{total_frames}")

        cap.release()

        # Build vehicle breakdown (update when using real model)
        vehicle_breakdown = defaultdict(int)
        for f in frame_data_list:
            for t in [1] * f['roi_vehicle_count']:  # placeholder
                vehicle_breakdown['car'] += 1

        congestion_ratio = sum(f['roi_congested'] for f in frame_data_list) / len(frame_data_list) if frame_data_list else 0

        return {
            'summary': {
                'total_vehicles_counted': total_vehicles_in_roi,
                'vehicle_breakdown': dict(vehicle_breakdown),
                'peak_traffic': max(f['roi_vehicle_count'] for f in frame_data_list) if frame_data_list else 0,
                'average_traffic_density': np.mean([f['roi_vehicle_count'] for f in frame_data_list]) if frame_data_list else 0
            },
            'frame_data': frame_data_list,
            'metadata': {
                'processing_time': 0,
                'model_used': 'ROIBasedCongestionDetector (standalone)'
            },
            'metrics': {
                'congestion_level': self._map_congestion_level(congestion_ratio),
                'traffic_pattern': 'stable'
            }
        }

    def _map_congestion_level(self, ratio):
        if ratio >= 0.7:
            return 'Severe Congestion'
        elif ratio >= 0.4:
            return 'High Congestion'
        elif ratio >= 0.1:
            return 'Moderate Congestion'
        else:
            return 'Light Traffic'