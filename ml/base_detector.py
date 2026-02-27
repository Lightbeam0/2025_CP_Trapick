# ml/base_detector.py
"""
Base Detector Class for Vehicle Counting and Congestion Detection (v2 - Stabilized & Multi-pass)
All directional detectors will inherit from this base class.

UPDATED FOR CUSTOM YOLO MODEL:
- Model: runs/detect/custom_model/weights/best.pt
- Classes: car(1), jeep(2), motorcycle(3), tricycle(5), truck(6)
- Excluded: VehicleCrash(0), person(4)

NEW FEATURES:
- Video Stabilization (ORB-based homography) for shaky cameras
- Multi-pass Processing for adaptive threshold refinement
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
import time
import os
from pathlib import Path
from abc import ABC, abstractmethod
from ultralytics import YOLO
import torch


# ✅ CUSTOM MODEL PATH - Update this if you retrain
CUSTOM_MODEL_PATH = str(Path(__file__).parent.parent / 'runs' / 'detect' / 'custom_model' / 'weights' / 'best.pt')


class BaseDetector(ABC):
    """
    Abstract base class for all directional traffic detectors.
    
    Key Features:
    - Vehicle detection and tracking with custom YOLO model
    - Directional counting logic
    - Congestion detection
    - Video stabilization (optional)
    - Multi-pass adaptive analysis (optional)
    - Results generation and storage
    """
    
    # ✅ CUSTOM MODEL CLASS CONFIGURATION
    CUSTOM_CLASS_NAMES = {
        1: 'car',
        2: 'jeep',
        3: 'motorcycle',
        5: 'tricycle',
        6: 'truck',
    }
    
    # Classes to EXCLUDE from counting
    EXCLUDED_CLASS_IDS = {0, 4}  # VehicleCrash, person
    
    def __init__(self, model_path=None):
        """Initialize base detector with common attributes"""
        self.model_path = model_path or CUSTOM_MODEL_PATH
        self.model = None
        self.device = None
        
        # ✅ Vehicle classes from custom model
        self.class_names = self.CUSTOM_CLASS_NAMES.copy()
        
        # Colors for visualization
        self.colors = {
            "car": (100, 100, 255),       # Purple
            "jeep": (255, 165, 0),        # Orange
            "motorcycle": (255, 255, 0),  # Yellow
            "tricycle": (0, 255, 255),    # Cyan
            "truck": (0, 0, 255),         # Red
        }
        
        # Counting configuration
        self.counted_classes = list(self.class_names.values())
        self.vehicle_class_ids = list(self.class_names.keys())
        
        # Tracking state
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status = {}
        self.vehicle_counts = defaultdict(int)
        self.counted_vehicles = set()
        self.total_count = 0
        
        # Congestion state
        self.congestion_events = []
        self.current_congestion = None
        self.frame_data = []
        
        # Processing metrics
        self.frame_count = 0
        self.processing_time = 0
        self.fps = 30
        
        # Results storage
        self.results = {
            'metadata': {},
            'counting_results': {},
            'congestion_results': {},
            'raw_data': {}
        }

        # ✅ NEW: Stabilization State
        self.stabilizer_enabled = False
        self.prev_gray = None
        self.feature_detector = cv2.ORB_create(nfeatures=1000)
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # ✅ NEW: Multi-pass State
        self.multi_pass_enabled = False
        self.pass_stats = {
            'avg_density': 0.0,
            'peak_density': 0.0,
            'total_frames_sampled': 0
        }
        
        print(f"🔧 BaseDetector v2 initialized")
        print(f"   Model: {self.model_path}")
        print(f"   Classes: {self.counted_classes}")
        print(f"   Excluded: {self.EXCLUDED_CLASS_IDS}")
    
    def load_model(self, model_path=None):
        """Load the YOLO model"""
        path = model_path or self.model_path
        
        if not os.path.exists(path):
            print(f"⚠️ Model not found at {path}, trying fallback...")
            path = 'yolov8m.pt'
        
        self.model = YOLO(path)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        
        print(f"✅ Model loaded: {path}")
        print(f"✅ Device: {self.device.upper()}")
        
        return self.model
    
    def setup_enhanced_metrics(self):
        """Initialize enhanced metrics"""
        self.speed_data = defaultdict(list)
        self.trajectory_data = defaultdict(list)
        self.detection_confidence = defaultdict(list)
        
    def reset_tracking_state(self):
        """Reset all tracking counters and history"""
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status = {}
        self.vehicle_counts = defaultdict(int)
        self.counted_vehicles = set()
        self.total_count = 0
        self.frame_count = 0
        
        self.congestion_events = []
        self.current_congestion = None
        self.frame_data = []
        
        # Reset stabilization state
        self.prev_gray = None
        
        if hasattr(self, 'speed_data'):
            self.speed_data.clear()
            self.trajectory_data.clear()
            self.detection_confidence.clear()
        
        print("🔄 Tracking state reset")
    
    def is_excluded_class(self, class_id):
        return int(class_id) in self.EXCLUDED_CLASS_IDS
    
    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Video Stabilization
    # ──────────────────────────────────────────────────────────────────────────

    def stabilize_frame(self, frame):
        """
        Simple frame stabilization using ORB feature matching and homography.
        Returns the stabilized frame.
        """
        if not self.stabilizer_enabled:
            return frame

        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Initialize reference frame
        if self.prev_gray is None:
            self.prev_gray = curr_gray
            return frame
        
        # Detect features
        kp1, des1 = self.feature_detector.detectAndCompute(self.prev_gray, None)
        kp2, des2 = self.feature_detector.detectAndCompute(curr_gray, None)
        
        stabilized_frame = frame
        
        if des1 is not None and des2 is not None and len(des1) > 10 and len(des2) > 10:
            matches = self.bf_matcher.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)[:30] # Keep top 30
            
            if len(matches) > 10:
                src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
                
                H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                
                if H is not None:
                    h, w = frame.shape[:2]
                    # Warp current frame to align with previous
                    stabilized_frame = cv2.warpPerspective(frame, H, (w, h), borderMode=cv2.BORDER_REPLICATE)
                else:
                    # Fallback if homography fails
                    pass
            else:
                # Not enough matches, skip stabilization for this frame
                pass
        else:
            # Feature detection failed
            pass
        
        # Update reference frame (slowly adapt to prevent drift, or keep static if camera is fixed but shaky)
        # For traffic cams, usually we want to align to a stable reference. 
        # Here we update prev_gray to current to track relative motion frame-to-frame.
        self.prev_gray = curr_gray
        
        return stabilized_frame

    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Multi-pass Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _run_first_pass(self, video_path, total_frames):
        """
        Run a quick first pass to estimate traffic density and scene characteristics.
        Returns statistics to tune the second pass.
        """
        print("🔄 Running First Pass (Statistics Gathering)...")
        cap = cv2.VideoCapture(str(video_path))
        
        densities = []
        sample_interval = max(1, total_frames // 100) # Sample ~100 frames
        
        f_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if f_idx % sample_interval == 0:
                # Quick inference with high confidence to just count obvious cars
                # We assume model is already loaded
                results = self.model.track(
                    frame, 
                    persist=False, 
                    conf=0.6, # High conf for speed
                    iou=0.7,
                    classes=self.vehicle_class_ids,
                    verbose=False,
                    device=self.device
                )
                
                if results and results[0].boxes is not None:
                    count = len(results[0].boxes.id) if results[0].boxes.id is not None else len(results[0].boxes)
                    densities.append(count)
            
            f_idx += 1
            
        cap.release()
        
        if densities:
            avg_d = float(np.mean(densities))
            peak_d = float(np.max(densities))
            print(f"📊 First Pass Complete: Avg Density={avg_d:.1f}, Peak={peak_d:.1f}")
            return {'avg_density': avg_d, 'peak_density': peak_d, 'total_frames_sampled': len(densities)}
        
        return {'avg_density': 0, 'peak_density': 0, 'total_frames_sampled': 0}

    def _apply_multi_pass_tuning(self, stats):
        """Adjust internal parameters based on first pass stats."""
        if stats['avg_density'] > 10:
            print("🚦 High density detected. Lowering confidence threshold for better recall.")
            # Example: Adjust base confidence if the child class exposes it
            if hasattr(self, '_min_conf_base'):
                self._min_conf_base *= 0.85 # Lower threshold
            if hasattr(self, '_min_conf'):
                self._min_conf *= 0.85
        elif stats['avg_density'] < 2:
            print("🚦 Low density detected. Increasing confidence to reduce false positives.")
            if hasattr(self, '_min_conf_base'):
                self._min_conf_base *= 1.1
            if hasattr(self, '_min_conf'):
                self._min_conf *= 1.1
        
        self.pass_stats = stats

    # ──────────────────────────────────────────────────────────────────────────
    # Core Logic (Speed, Congestion, etc.)
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_speed(self, track_id, current_position, frame_number, fps):
        if track_id not in self.track_history:
            return None
            
        history = list(self.track_history[track_id])
        if len(history) < 2:
            return None
        
        recent_positions = history[-5:] if len(history) >= 5 else history
        recent_positions.append(current_position)
        
        total_distance = 0
        for i in range(len(recent_positions) - 1):
            x1, y1 = recent_positions[i]
            x2, y2 = recent_positions[i + 1]
            distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            total_distance += distance
        
        pixels_per_meter = 10
        time_elapsed = len(recent_positions) / fps
        distance_meters = total_distance / pixels_per_meter
        
        if time_elapsed > 0:
            speed_mps = distance_meters / time_elapsed
            speed_kmh = speed_mps * 3.6
            return min(speed_kmh, 200)
            
        return None
    
    def calculate_congestion_level(self, detections, fps):
        total_vehicles = len(detections)
        
        if total_vehicles >= 15:
            level = "severe"
        elif total_vehicles >= 10:
            level = "heavy"
        elif total_vehicles >= 8:
            level = "moderate"
        elif total_vehicles >= 5:
            level = "light"
        else:
            level = "none"
        
        stationary_count = 0
        for det in detections:
            speed = det.get('speed')
            if speed is None:
                continue
            elif speed < 5:
                stationary_count += 1
        
        congestion_score = min(100, int((total_vehicles / 20) * 100))
        
        return {
            'level': level,
            'total_vehicles': total_vehicles,
            'stationary_vehicles': stationary_count,
            'congestion_score': congestion_score,
            'timestamp': self.frame_count / fps if fps > 0 else 0
        }
    
    def track_congestion_event(self, congestion_info, fps):
        current_time = self.frame_count / fps if fps > 0 else 0
        current_level = congestion_info['level']
        
        if current_level != 'none':
            if self.current_congestion is None:
                self.current_congestion = {
                    'level': current_level,
                    'start_time': current_time,
                    'start_frame': self.frame_count,
                    'peak_vehicles': congestion_info['total_vehicles'],
                    'peak_stationary': congestion_info['stationary_vehicles']
                }
            else:
                if congestion_info['total_vehicles'] > self.current_congestion['peak_vehicles']:
                    self.current_congestion['peak_vehicles'] = congestion_info['total_vehicles']
                if congestion_info['stationary_vehicles'] > self.current_congestion['peak_stationary']:
                    self.current_congestion['peak_stationary'] = congestion_info['stationary_vehicles']
                
                level_order = ['none', 'light', 'moderate', 'heavy', 'severe']
                if level_order.index(current_level) > level_order.index(self.current_congestion['level']):
                    self.current_congestion['level'] = current_level
        else:
            if self.current_congestion is not None:
                event_duration = current_time - self.current_congestion['start_time']
                if event_duration >= 10:
                    congestion_event = {
                        'level': self.current_congestion['level'],
                        'start_time': self.current_congestion['start_time'],
                        'end_time': current_time,
                        'duration': event_duration,
                        'start_frame': self.current_congestion['start_frame'],
                        'end_frame': self.frame_count,
                        'peak_vehicles': self.current_congestion['peak_vehicles'],
                        'peak_stationary': self.current_congestion['peak_stationary']
                    }
                    self.congestion_events.append(congestion_event)
                
                self.current_congestion = None
    
    def store_frame_data(self, frame_number, fps, counts, congestion_info):
        frame_data = {
            'frame_number': frame_number,
            'timestamp': frame_number / fps if fps > 0 else 0,
            'total_vehicles': sum(counts.values()),
            'vehicle_breakdown': dict(counts),
            'congestion_level': congestion_info['level'],
            'congestion_score': congestion_info['congestion_score'],
            'stationary_vehicles': congestion_info['stationary_vehicles'],
            'counted_vehicles': self.total_count
        }
        self.frame_data.append(frame_data)
    
    @abstractmethod
    def setup_counting_line(self, frame_width, frame_height):
        pass
    
    @abstractmethod
    def is_valid_direction(self, track_history, valid_direction_vector):
        pass
    
    @abstractmethod
    def process_frame(self, frame, frame_number, fps):
        pass
    
    @abstractmethod
    def draw_detections(self, frame, detections, congestion_info, fps):
        pass
    
    def analyze_video(self, video_path, progress_callback=None, save_output=True, **kwargs):
        """
        Main video analysis pipeline with optional Stabilization and Multi-pass.
        """
        print(f"\n{'='*70}")
        print(f"🎬 STARTING VIDEO ANALYSIS (v2)")
        print(f"{'='*70}")
        
        # Load model if not already loaded
        if self.model is None:
            self.load_model()
        
        # Check for new flags
        self.stabilizer_enabled = kwargs.get('stabilize', False)
        self.multi_pass_enabled = kwargs.get('multi_pass', False)
        
        if self.stabilizer_enabled:
            print("🎥 Video stabilization ENABLED")
        if self.multi_pass_enabled:
            print("🔄 Multi-pass analysis ENABLED")
            
            # Run First Pass
            cap_temp = cv2.VideoCapture(str(video_path))
            total_frames_temp = int(cap_temp.get(cv2.CAP_PROP_FRAME_COUNT))
            cap_temp.release()
            
            stats = self._run_first_pass(video_path, total_frames_temp)
            self._apply_multi_pass_tuning(stats)

        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"❌ Cannot open video file: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"📊 Video Properties:")
        print(f"   Resolution: {width}x{height}")
        print(f"   FPS: {fps:.2f}")
        print(f"   Frames: {total_frames}")
        print(f"   Duration: {duration:.2f} seconds")
        
        self.setup_counting_line(width, height)
        
        output_path = None
        out = None
        if save_output:
            os.makedirs('media/processed_videos', exist_ok=True)
            original_filename = Path(video_path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            detector_name = self.__class__.__name__.lower().replace('detector', '')
            suffix = "_stab" if self.stabilizer_enabled else ""
            output_filename = f"{detector_name}_{original_filename}_{timestamp}{suffix}.mp4"
            output_path = Path('media/processed_videos') / output_filename
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            print(f"💾 Output will be saved to: {output_path}")
        
        self.reset_tracking_state()
        
        frame_number = 0
        start_time = time.time()
        self.fps = fps
        
        print(f"\n⏳ Processing {total_frames} frames...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # ✅ Apply Stabilization
            if self.stabilizer_enabled:
                frame = self.stabilize_frame(frame)
            
            frame_start = time.time()
            counts, detections, congestion_info = self.process_frame(frame, frame_number, fps)
            frame_time = time.time() - frame_start
            
            self.track_congestion_event(congestion_info, fps)
            self.store_frame_data(frame_number, fps, counts, congestion_info)
            
            if out is not None or progress_callback:
                annotated_frame = self.draw_detections(frame.copy(), detections, congestion_info, fps)
                if out is not None:
                    out.write(annotated_frame)
            
            if progress_callback and frame_number % 50 == 0:
                progress = min(88, 15 + int((frame_number / total_frames) * 73))
                message = f"Processing frame {frame_number}/{total_frames}"
                progress_callback(progress, total_frames, message)
            
            frame_number += 1
            self.processing_time += frame_time
        
        cap.release()
        if out is not None:
            out.release()
            print(f"✅ Processed video saved: {output_path}")
        
        total_time = time.time() - start_time
        print(f"\n✅ Analysis completed in {total_time:.2f} seconds")
        print(f"📈 Vehicles counted: {self.total_count}")
        print(f"📊 Vehicle breakdown: {dict(self.vehicle_counts)}")
        
        report = self.generate_report(total_frames, total_time, fps)
        
        if output_path:
            report['output_video_path'] = str(output_path)
        
        # Add multi-pass info to report if used
        if self.multi_pass_enabled:
            report['metadata']['multi_pass_stats'] = self.pass_stats
            report['metadata']['stabilization_used'] = self.stabilizer_enabled
        
        return report
    
    def generate_report(self, total_frames, proc_time, fps):
        duration = total_frames / fps if fps > 0 else 0
        vpm = (self.total_count / duration) * 60 if duration > 0 else 0
        
        if vpm > 100:
            traffic_level = "Very Heavy"
        elif vpm > 60:
            traffic_level = "Heavy"
        elif vpm > 30:
            traffic_level = "Moderate"
        elif vpm > 10:
            traffic_level = "Light"
        else:
            traffic_level = "Very Light"
        
        congestion_summary = {
            'total_events': len(self.congestion_events),
            'total_duration': sum(event['duration'] for event in self.congestion_events),
            'events_by_level': defaultdict(int),
            'average_duration': 0
        }
        
        for event in self.congestion_events:
            congestion_summary['events_by_level'][event['level']] += 1
        
        if self.congestion_events:
            congestion_summary['average_duration'] = (
                congestion_summary['total_duration'] / len(self.congestion_events)
            )
        
        detection_efficiency = {
            'frames_per_second': total_frames / proc_time if proc_time > 0 else 0,
            'processing_ratio': proc_time / duration if duration > 0 else 0,
            'vehicles_per_frame': self.total_count / total_frames if total_frames > 0 else 0
        }
        
        return {
            'metadata': {
                'detector_name': self.__class__.__name__,
                'direction': getattr(self, 'direction_name', 'Unknown'),
                'video_duration': round(duration, 2),
                'duration_seconds': round(duration, 2),
                'processing_time': round(proc_time, 2),
                'processing_time_seconds': round(proc_time, 2),
                'processing_date': datetime.now().isoformat(),
                'total_frames': total_frames,
                'frames_processed': total_frames,
                'fps': round(fps, 2),
                'video_fps': round(fps, 2),
                'vehicle_classes': self.counted_classes,
                'model_path': self.model_path,
                'excluded_classes': ['VehicleCrash', 'person'],
                'stabilization_used': self.stabilizer_enabled,
                'multi_pass_used': self.multi_pass_enabled,
            },
            'counting_results': {
                'total_vehicles': self.total_count,
                'vehicle_breakdown': dict(self.vehicle_counts),
                'vehicles_per_minute': round(vpm, 2),
                'traffic_level': traffic_level,
                'detection_efficiency': detection_efficiency
            },
            'congestion_results': {
                'total_events': congestion_summary['total_events'],
                'total_congestion_time': round(congestion_summary['total_duration'], 2),
                'events_by_level': dict(congestion_summary['events_by_level']),
                'average_congestion_duration': round(congestion_summary['average_duration'], 2),
                'congestion_percentage': round(
                    (congestion_summary['total_duration'] / duration * 100) if duration > 0 else 0, 2
                ),
                'final_congestion_level': self._determine_final_congestion_level(congestion_summary)
            },
            'raw_data': {
                'frame_data': self.frame_data[-1000:],
                'congestion_events': self.congestion_events,
                'vehicle_counts_history': self.get_vehicle_counts_history()
            }
        }

    def _determine_final_congestion_level(self, congestion_summary):
        if not congestion_summary['events_by_level']:
            return 'none'
        level_priority = ['severe', 'heavy', 'moderate', 'light', 'none']
        for level in level_priority:
            if congestion_summary['events_by_level'].get(level, 0) > 0:
                return level
        return 'none'
    
    def get_vehicle_counts_history(self):
        history = []
        for frame in self.frame_data[-500:]:
            history.append({
                'frame': frame['frame_number'],
                'timestamp': frame['timestamp'],
                'total_vehicles': frame['total_vehicles'],
                'counted_vehicles': frame.get('counted_vehicles', 0)
            })
        return history
    
    def export_results(self, output_path=None):
        import json
        report = self.generate_report(
            self.frame_count,
            self.processing_time,
            self.fps
        )
        
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"📄 Results exported to: {output_path}")
        
        return report
    
    def print_summary(self):
        print(f"\n{'='*70}")
        print(f"📊 ANALYSIS SUMMARY")
        print(f"{'='*70}")
        print(f"Detector: {self.__class__.__name__}")
        print(f"Model: {self.model_path}")
        print(f"Frames processed: {self.frame_count}")
        print(f"Total vehicles counted: {self.total_count}")
        print(f"Vehicle breakdown:")
        for vehicle_type, count in self.vehicle_counts.items():
            print(f"  {vehicle_type.upper()}: {count}")
        print(f"Congestion events: {len(self.congestion_events)}")
        if self.congestion_events:
            total_duration = sum(e['duration'] for e in self.congestion_events)
            print(f"Total congestion time: {total_duration:.1f} seconds")
        if self.stabilizer_enabled:
            print("Stabilization: Active")
        if self.multi_pass_enabled:
            print(f"Multi-pass: Active (Avg Density: {self.pass_stats['avg_density']:.1f})")
        print(f"{'='*70}")
    
    def cleanup(self):
        if hasattr(self, 'model'):
            del self.model
        if hasattr(self, 'track_history'):
            self.track_history.clear()
        if hasattr(self, 'vehicle_status'):
            self.vehicle_status.clear()
        self.prev_gray = None
        print("🧹 Resources cleaned up")