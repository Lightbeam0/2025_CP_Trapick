# ml/base_detector.py
"""
Base Detector Class for Vehicle Counting and Congestion Detection (v2.1)

Fixes vs v2:
  - FIX #7:  Dead calculate_congestion_level() removed.  It was never called
             for directional detectors (CongestionModule is used instead) and
             contained stale None-speed logic.
  - FIX #10: _run_first_pass() now uses model.predict() instead of
             model.track() so ByteTrack state is not initialised/wasted for
             the statistics-only first pass.
  - FIX #12: frame_data is now a deque(maxlen=1000) ring buffer.
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


# ✅ CUSTOM MODEL PATH
CUSTOM_MODEL_PATH = str(
    Path(__file__).parent.parent / 'runs' / 'detect' / 'custom_model' / 'weights' / 'best.pt'
)


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

    CUSTOM_CLASS_NAMES = {
        1: 'car',
        2: 'jeep',
        3: 'motorcycle',
        5: 'tricycle',
        6: 'truck',
    }

    EXCLUDED_CLASS_IDS = {0, 4}   # VehicleCrash, person

    def __init__(self, model_path=None):
        self.model_path = model_path or CUSTOM_MODEL_PATH
        self.model      = None
        self.device     = None

        self.class_names = self.CUSTOM_CLASS_NAMES.copy()

        self.colors = {
            "car":        (100, 100, 255),
            "jeep":       (255, 165,   0),
            "motorcycle": (255, 255,   0),
            "tricycle":   (  0, 255, 255),
            "truck":      (  0,   0, 255),
        }

        self.counted_classes   = list(self.class_names.values())
        self.vehicle_class_ids = list(self.class_names.keys())

        # Tracking state
        self.track_history  = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status = {}
        self.vehicle_counts = defaultdict(int)
        self.counted_vehicles = set()
        self.total_count    = 0

        self.congestion_events  = []
        self.current_congestion = None
        # FIX #12: Ring buffer — never stores more than 1 000 entries
        self.frame_data = deque(maxlen=1000)

        self.frame_count      = 0
        self.processing_time  = 0
        self.fps              = 30

        self.results = {
            'metadata':          {},
            'counting_results':  {},
            'congestion_results': {},
            'raw_data':          {}
        }

        # Stabilization state
        self.stabilizer_enabled  = False
        self.prev_gray           = None
        self.feature_detector    = cv2.ORB_create(nfeatures=1000)
        self.bf_matcher          = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        # Multi-pass state
        self.multi_pass_enabled = False
        self.pass_stats = {
            'avg_density':          0.0,
            'peak_density':         0.0,
            'total_frames_sampled': 0,
        }

        print(f"🔧 BaseDetector v2.1 initialized")
        print(f"   Model  : {self.model_path}")
        print(f"   Classes: {self.counted_classes}")
        print(f"   Excluded: {self.EXCLUDED_CLASS_IDS}")

    def load_model(self, model_path=None):
        path = model_path or self.model_path

        if not os.path.exists(path):
            print(f"⚠️ Model not found at {path}, trying fallback...")
            path = 'yolov8m.pt'

        self.model  = YOLO(path)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)

        print(f"✅ Model loaded: {path}")
        print(f"✅ Device: {self.device.upper()}")
        return self.model

    def setup_enhanced_metrics(self):
        self.speed_data          = defaultdict(list)
        self.trajectory_data     = defaultdict(list)
        self.detection_confidence = defaultdict(list)

    def reset_tracking_state(self):
        self.track_history    = defaultdict(lambda: deque(maxlen=30))
        self.vehicle_status   = {}
        self.vehicle_counts   = defaultdict(int)
        self.counted_vehicles = set()
        self.total_count      = 0
        self.frame_count      = 0

        self.congestion_events  = []
        self.current_congestion = None
        # FIX #12: reset ring buffer
        self.frame_data = deque(maxlen=1000)

        self.prev_gray = None

        if hasattr(self, 'speed_data'):
            self.speed_data.clear()
            self.trajectory_data.clear()
            self.detection_confidence.clear()

        print("🔄 Tracking state reset")

    def is_excluded_class(self, class_id):
        return int(class_id) in self.EXCLUDED_CLASS_IDS

    # ──────────────────────────────────────────────────────────────────────────
    # Video stabilization
    # ──────────────────────────────────────────────────────────────────────────

    def stabilize_frame(self, frame):
        if not self.stabilizer_enabled:
            return frame

        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.prev_gray is None:
            self.prev_gray = curr_gray
            return frame

        kp1, des1 = self.feature_detector.detectAndCompute(self.prev_gray, None)
        kp2, des2 = self.feature_detector.detectAndCompute(curr_gray, None)

        stabilized_frame = frame

        if (des1 is not None and des2 is not None
                and len(des1) > 10 and len(des2) > 10):
            matches = self.bf_matcher.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)[:30]

            if len(matches) > 10:
                src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
                H, _    = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

                if H is not None:
                    h, w = frame.shape[:2]
                    stabilized_frame = cv2.warpPerspective(
                        frame, H, (w, h), borderMode=cv2.BORDER_REPLICATE
                    )

        self.prev_gray = curr_gray
        return stabilized_frame

    # ──────────────────────────────────────────────────────────────────────────
    # FIX #10: Multi-pass — first pass uses model.predict (no tracker overhead)
    # ──────────────────────────────────────────────────────────────────────────

    def _run_first_pass(self, video_path, total_frames):
        """
        Quick first pass to estimate traffic density.

        FIX #10: Uses model.predict() instead of model.track().
        The first pass only needs raw box counts per frame — there is no reason
        to initialise ByteTrack state (which is discarded anyway) and pay the
        associated matching overhead.
        """
        print("🔄 Running First Pass (Statistics Gathering)...")
        cap = cv2.VideoCapture(str(video_path))

        densities       = []
        sample_interval = max(1, total_frames // 100)

        f_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if f_idx % sample_interval == 0:
                # FIX #10: predict (no tracking) — cheaper and correct for density estimation
                results = self.model.predict(
                    frame,
                    conf=0.6,
                    iou=0.7,
                    classes=self.vehicle_class_ids,
                    verbose=False,
                    device=self.device,
                )
                if results and results[0].boxes is not None:
                    densities.append(len(results[0].boxes))

            f_idx += 1

        cap.release()

        if densities:
            avg_d = float(np.mean(densities))
            peak_d = float(np.max(densities))
            print(f"📊 First Pass Complete: Avg Density={avg_d:.1f}, Peak={peak_d:.1f}")
            return {'avg_density': avg_d, 'peak_density': peak_d,
                    'total_frames_sampled': len(densities)}

        return {'avg_density': 0.0, 'peak_density': 0.0, 'total_frames_sampled': 0}

    def _apply_multi_pass_tuning(self, stats):
        """Adjust confidence thresholds based on first-pass density stats."""
        if stats['avg_density'] > 10:
            print("🚦 High density detected — lowering confidence for better recall.")
            if hasattr(self, '_min_conf_base'):
                self._min_conf_base = max(0.10, self._min_conf_base * 0.85)
            if hasattr(self, '_min_conf'):
                self._min_conf = max(0.10, self._min_conf * 0.85)
        elif stats['avg_density'] < 2:
            print("🚦 Low density detected — raising confidence to reduce FP.")
            if hasattr(self, '_min_conf_base'):
                self._min_conf_base = min(0.70, self._min_conf_base * 1.10)
            if hasattr(self, '_min_conf'):
                self._min_conf = min(0.70, self._min_conf * 1.10)

        self.pass_stats = stats

    # ──────────────────────────────────────────────────────────────────────────
    # Speed / congestion helpers
    # ──────────────────────────────────────────────────────────────────────────

    def calculate_speed(self, track_id, current_position, frame_number, fps):
        if track_id not in self.track_history:
            return None

        history = list(self.track_history[track_id])
        if len(history) < 2:
            return None

        recent_positions = history[-5:] if len(history) >= 5 else history
        recent_positions.append(current_position)

        total_distance = sum(
            np.sqrt((recent_positions[i+1][0] - recent_positions[i][0])**2 +
                    (recent_positions[i+1][1] - recent_positions[i][1])**2)
            for i in range(len(recent_positions) - 1)
        )

        pixels_per_meter = 10
        time_elapsed     = len(recent_positions) / fps
        distance_meters  = total_distance / pixels_per_meter

        if time_elapsed > 0:
            return min((distance_meters / time_elapsed) * 3.6, 200.0)

        return None

    # FIX #7: calculate_congestion_level() has been REMOVED.
    # It was dead code — directional detectors use CongestionModule.detect_congestion()
    # and the base class method was never called from any active code path.
    # If you need a simple per-frame congestion estimate outside of CongestionModule,
    # add it as a standalone utility function rather than a method on BaseDetector.

    def track_congestion_event(self, congestion_info, fps):
        current_time  = self.frame_count / fps if fps > 0 else 0
        current_level = congestion_info['level']

        if current_level != 'none':
            if self.current_congestion is None:
                self.current_congestion = {
                    'level':          current_level,
                    'start_time':     current_time,
                    'start_frame':    self.frame_count,
                    'peak_vehicles':  congestion_info['total_vehicles'],
                    'peak_stationary': congestion_info['stationary_vehicles'],
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
                    self.congestion_events.append({
                        'level':          self.current_congestion['level'],
                        'start_time':     self.current_congestion['start_time'],
                        'end_time':       current_time,
                        'duration':       event_duration,
                        'start_frame':    self.current_congestion['start_frame'],
                        'end_frame':      self.frame_count,
                        'peak_vehicles':  self.current_congestion['peak_vehicles'],
                        'peak_stationary': self.current_congestion['peak_stationary'],
                    })
                self.current_congestion = None

    def store_frame_data(self, frame_number, fps, counts, congestion_info):
        frame_entry = {
            'frame_number':     frame_number,
            'timestamp':        frame_number / fps if fps > 0 else 0,
            'total_vehicles':   sum(counts.values()),
            'vehicle_breakdown': dict(counts),
            'congestion_level': congestion_info['level'],
            'congestion_score': congestion_info['congestion_score'],
            'stationary_vehicles': congestion_info['stationary_vehicles'],
            'counted_vehicles': self.total_count,
        }
        # FIX #12: append to ring buffer (auto-evicts oldest when full)
        self.frame_data.append(frame_entry)

    # ──────────────────────────────────────────────────────────────────────────
    # Abstract interface
    # ──────────────────────────────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────────────────────────────
    # Main pipeline
    # ──────────────────────────────────────────────────────────────────────────

    def analyze_video(self, video_path, progress_callback=None, save_output=True, **kwargs):
        print(f"\n{'='*70}")
        print(f"🎬 STARTING VIDEO ANALYSIS (v2.1)")
        print(f"{'='*70}")

        if self.model is None:
            self.load_model()

        self.stabilizer_enabled = kwargs.get('stabilize', False)
        self.multi_pass_enabled = kwargs.get('multi_pass', False)

        if self.stabilizer_enabled:
            print("🎥 Video stabilization ENABLED")
        if self.multi_pass_enabled:
            print("🔄 Multi-pass analysis ENABLED")
            cap_temp     = cv2.VideoCapture(str(video_path))
            total_frames_tmp = int(cap_temp.get(cv2.CAP_PROP_FRAME_COUNT))
            cap_temp.release()
            stats = self._run_first_pass(video_path, total_frames_tmp)  # FIX #10
            self._apply_multi_pass_tuning(stats)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"❌ Cannot open video file: {video_path}")

        fps          = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration     = total_frames / fps if fps > 0 else 0

        print(f"📊 Video: {width}×{height}  {fps:.2f}fps  {total_frames}f  {duration:.1f}s")

        self.setup_counting_line(width, height)

        output_path = None
        out         = None
        if save_output:
            os.makedirs('media/processed_videos', exist_ok=True)
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            det_name = self.__class__.__name__.lower().replace('detector', '')
            suffix   = "_stab" if self.stabilizer_enabled else ""
            output_path = Path('media/processed_videos') / f"{det_name}_{Path(video_path).stem}_{ts}{suffix}.mp4"
            out = cv2.VideoWriter(str(output_path),
                                  cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
            print(f"💾 Output: {output_path}")

        self.reset_tracking_state()

        frame_number  = 0
        start_time    = time.time()
        self.fps      = fps

        print(f"\n⏳ Processing {total_frames} frames...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if self.stabilizer_enabled:
                frame = self.stabilize_frame(frame)

            frame_start = time.time()
            counts, detections, congestion_info = self.process_frame(frame, frame_number, fps)
            frame_time  = time.time() - frame_start

            self.track_congestion_event(congestion_info, fps)
            self.store_frame_data(frame_number, fps, counts, congestion_info)

            if out is not None or progress_callback:
                annotated = self.draw_detections(frame.copy(), detections, congestion_info, fps)
                if out is not None:
                    out.write(annotated)

            if progress_callback and frame_number % 50 == 0:
                progress = min(88, 15 + int((frame_number / total_frames) * 73))
                progress_callback(progress, total_frames,
                                  f"Processing frame {frame_number}/{total_frames}")

            frame_number         += 1
            self.processing_time += frame_time

        cap.release()
        if out:
            out.release()
            print(f"✅ Processed video saved: {output_path}")

        total_time = time.time() - start_time
        print(f"\n✅ Completed in {total_time:.2f}s | Counted: {self.total_count}")

        report = self.generate_report(total_frames, total_time, fps)
        if output_path:
            report['output_video_path'] = str(output_path)

        if self.multi_pass_enabled:
            report['metadata']['multi_pass_stats']      = self.pass_stats
            report['metadata']['stabilization_used']    = self.stabilizer_enabled

        return report

    # ──────────────────────────────────────────────────────────────────────────
    # Report
    # ──────────────────────────────────────────────────────────────────────────

    def generate_report(self, total_frames, proc_time, fps):
        duration = total_frames / fps if fps > 0 else 0
        vpm      = (self.total_count / duration) * 60 if duration > 0 else 0

        if   vpm > 100: traffic_level = "Very Heavy"
        elif vpm > 60:  traffic_level = "Heavy"
        elif vpm > 30:  traffic_level = "Moderate"
        elif vpm > 10:  traffic_level = "Light"
        else:           traffic_level = "Very Light"

        congestion_summary = {
            'total_events':    len(self.congestion_events),
            'total_duration':  sum(e['duration'] for e in self.congestion_events),
            'events_by_level': defaultdict(int),
            'average_duration': 0.0,
        }
        for event in self.congestion_events:
            congestion_summary['events_by_level'][event['level']] += 1

        if self.congestion_events:
            congestion_summary['average_duration'] = (
                congestion_summary['total_duration'] / len(self.congestion_events)
            )

        detection_efficiency = {
            'frames_per_second': total_frames / proc_time if proc_time > 0 else 0,
            'processing_ratio':  proc_time / duration    if duration  > 0 else 0,
            'vehicles_per_frame': self.total_count / total_frames if total_frames > 0 else 0,
        }

        # FIX #12: convert deque → list for JSON serialisation
        frame_data_list = list(self.frame_data)

        return {
            'metadata': {
                'detector_name':      self.__class__.__name__,
                'direction':          getattr(self, 'direction_name', 'Unknown'),
                'video_duration':     round(duration, 2),
                'duration_seconds':   round(duration, 2),
                'processing_time':    round(proc_time, 2),
                'processing_time_seconds': round(proc_time, 2),
                'processing_date':    datetime.now().isoformat(),
                'total_frames':       total_frames,
                'frames_processed':   total_frames,
                'fps':                round(fps, 2),
                'vehicle_classes':    self.counted_classes,
                'model_path':         self.model_path,
                'excluded_classes':   ['VehicleCrash', 'person'],
                'stabilization_used': self.stabilizer_enabled,
                'multi_pass_used':    self.multi_pass_enabled,
            },
            'counting_results': {
                'total_vehicles':     self.total_count,
                'vehicle_breakdown':  dict(self.vehicle_counts),
                'vehicles_per_minute': round(vpm, 2),
                'traffic_level':      traffic_level,
                'detection_efficiency': detection_efficiency,
            },
            'congestion_results': {
                'total_events':              congestion_summary['total_events'],
                'total_congestion_time':     round(congestion_summary['total_duration'], 2),
                'events_by_level':           dict(congestion_summary['events_by_level']),
                'average_congestion_duration': round(congestion_summary['average_duration'], 2),
                'congestion_percentage':     round(
                    (congestion_summary['total_duration'] / duration * 100) if duration > 0 else 0, 2
                ),
                'final_congestion_level':    self._determine_final_congestion_level(congestion_summary),
            },
            'raw_data': {
                'frame_data':               frame_data_list,
                'congestion_events':        self.congestion_events,
                'vehicle_counts_history':   self.get_vehicle_counts_history(),
            },
        }

    def _determine_final_congestion_level(self, congestion_summary):
        if not congestion_summary['events_by_level']:
            return 'none'
        for level in ['severe', 'heavy', 'moderate', 'light', 'none']:
            if congestion_summary['events_by_level'].get(level, 0) > 0:
                return level
        return 'none'

    def get_vehicle_counts_history(self):
        return [
            {
                'frame':            f['frame_number'],
                'timestamp':        f['timestamp'],
                'total_vehicles':   f['total_vehicles'],
                'counted_vehicles': f.get('counted_vehicles', 0),
            }
            for f in list(self.frame_data)[-500:]
        ]

    def export_results(self, output_path=None):
        import json
        report = self.generate_report(self.frame_count, self.processing_time, self.fps)
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"📄 Results exported to: {output_path}")
        return report

    def print_summary(self):
        print(f"\n{'='*70}")
        print(f"📊 ANALYSIS SUMMARY — {self.__class__.__name__}")
        print(f"   Model         : {self.model_path}")
        print(f"   Frames        : {self.frame_count}")
        print(f"   Total counted : {self.total_count}")
        for vtype, count in self.vehicle_counts.items():
            print(f"     {vtype.upper()}: {count}")
        print(f"   Congestion events: {len(self.congestion_events)}")
        if self.congestion_events:
            print(f"   Total congestion : {sum(e['duration'] for e in self.congestion_events):.1f}s")
        if self.stabilizer_enabled:
            print("   Stabilization    : Active")
        if self.multi_pass_enabled:
            print(f"   Multi-pass       : Active (AvgDensity={self.pass_stats['avg_density']:.1f})")
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