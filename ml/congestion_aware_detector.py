# ml/congestion_aware_detector.py
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


class CongestionAwareDetector(BaseDetector):
    """
    Custom detector for congestion monitoring in a user-defined rectangular ROI.
    - Uses collision4_model (car, jeep, motorcycle, tricycle, truck)
    - Counts vehicles crossing a blue line (top → bottom) - DOWNWARD DIRECTION ONLY
    - Flags congestion when vehicles in configured ROI are slow/stopped

    Notes:
      * The detector expects an Ultralitycs YOLO model (YOLOv8) at the provided path.
      * Calibration (pixels_per_meter) must be tuned per camera for accurate speeds.
    """

    def __init__(self, model_path=None, roi=None, counting_line_y=None, roi_width_ratio=0.5):
        super().__init__()

        print("\n" + "=" * 70)
        print("🚦 CONGESTION-AWARE DETECTOR - CUSTOM FOR ROI-BASED CONGESTION")
        print("=" * 70)

        # Resolve default model path relative to project root (two parents up)
        if model_path is None:
            current_file = Path(__file__).resolve()
            project_root = current_file.parents[2]
            model_path = project_root / "runs" / "detect" / "collision4_model" / "weights" / "best.pt"
            if not model_path.exists():
                raise FileNotFoundError(f"❌ collision4_model not found at: {model_path}")

        print(f"📂 Loading model: {Path(model_path).name}")
        self.model = YOLO(str(model_path))

        # move to device if applicable (YOLO wrapper may manage device automatically)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            # Some ultralytics versions use self.model.model.to(device)
            if hasattr(self.model, "model") and hasattr(self.model.model, "to"):
                self.model.model.to(self.device)
        except Exception:
            # If device move fails, continue — the wrapper typically handles it.
            pass

        print(f"✅ Device: {self.device.upper()}")

        # collision4 classes mapping (NOTE: class indices depend on training)
        # Provided mapping intentionally excludes index 0 (VehicleCrash) and 4 (person)
        self.class_names = {1: "car", 2: "jeep", 3: "motorcycle", 5: "tricycle", 6: "truck"}
        self.counted_classes = list(self.class_names.values())

        # Visualization colors (BGR)
        self.colors = {
            "car": (100, 100, 255),
            "jeep": (255, 165, 0),
            "motorcycle": (255, 255, 0),
            "tricycle": (255, 0, 255),
            "truck": (0, 0, 255),
        }

        # ROI configuration
        self.roi_width_ratio = float(roi_width_ratio)
        if roi is None:
            # marker default; will be computed in process_frame
            self.roi = [0, 0, 0, 0]
        else:
            assert len(roi) == 4, "roi must be [x1, y1, x2, y2]"
            self.roi = list(map(int, roi))

        # Counting line y coordinate (horizontal line); computed if None
        self.counting_line_y = int(counting_line_y) if counting_line_y is not None else None

        # Congestion heuristics
        self.min_vehicles_for_congestion = 3
        self.max_speed_for_congestion = 5.0  # km/h threshold to consider "slow/stopped"

        print(f"\n🎯 CONFIGURATION:")
        print(f"   ROI (red box): Auto-sized to {self.roi_width_ratio*100:.0f}% of screen width (if not provided)")
        print(f"   Counting line Y: {self.counting_line_y} (will be set to bottom 25% if None)")
        print(f"   Counting direction: DOWNWARD ONLY")
        print(f"   Congestion: ≥{self.min_vehicles_for_congestion} vehicles in ROI with speed ≤{self.max_speed_for_congestion} km/h")
        print("=" * 70 + "\n")

        # Internal tracking and metrics
        self.reset_tracking_state()

    def reset_tracking_state(self):
        """Reset all tracking-related state (use at start of video)."""
        self.track_history = defaultdict(lambda: deque(maxlen=60))  # store pixel centers
        self.vehicle_status = {}  # per-track status (crossed, direction)
        self.vehicle_type_counts = defaultdict(int)
        self.vehicle_crossed = set()
        self.total_count = 0
        self.congestion_flags = []  # per-frame boolean
        self.setup_enhanced_metrics()

    def setup_enhanced_metrics(self):
        """Initialize additional storage needed for speed estimation."""
        self.vehicle_positions = defaultdict(list)    # list of (x,y) per track
        self.vehicle_timestamps = defaultdict(list)  # corresponding timestamps (seconds)
        self.frame_timestamps = []

    def calculate_speed(self, track_id, current_position, frame_number, fps):
        """
        Estimate speed in km/h using recent pixel displacements.
        - track_id: unique tracker id for the object
        - current_position: (x, y) center in pixels
        - frame_number: current frame index (int)
        - fps: frames per second

        Return:
            speed_kmh (float) or None if insufficient data
        """
        if fps is None or fps <= 0:
            return None

        # timestamp in seconds
        current_time = frame_number / fps

        # append current
        self.vehicle_positions[track_id].append(current_position)
        self.vehicle_timestamps[track_id].append(current_time)

        # keep only last N seconds of history for smoothing
        max_history_time = 2.0  # seconds
        while (self.vehicle_timestamps[track_id] and
               current_time - self.vehicle_timestamps[track_id][0] > max_history_time):
            self.vehicle_positions[track_id].pop(0)
            self.vehicle_timestamps[track_id].pop(0)

        # need at least two points to compute speed
        if len(self.vehicle_positions[track_id]) < 2:
            return None

        positions = self.vehicle_positions[track_id]
        timestamps = self.vehicle_timestamps[track_id]

        total_distance = 0.0
        for i in range(1, len(positions)):
            x1, y1 = positions[i - 1]
            x2, y2 = positions[i]
            total_distance += float(np.hypot(x2 - x1, y2 - y1))

        total_time = timestamps[-1] - timestamps[0]
        if total_time <= 0 or total_distance <= 0:
            return 0.0

        # Convert pixels to meters — this MUST be calibrated for your camera
        pixels_per_meter = 10.0  # <-- change based on calibration
        distance_meters = total_distance / pixels_per_meter
        speed_mps = distance_meters / total_time
        speed_kmh = speed_mps * 3.6

        return speed_kmh

    def get_movement_direction(self, track_id, current_position):
        """
        Determine vertical movement direction ('downward', 'upward', 'stationary') based on history.
        Returns None if not enough history.
        """
        history = self.track_history.get(track_id, None)
        if history is None or len(history) < 2:
            return None

        # use up to last 5 positions for smoothing
        recent = list(history)[-5:]
        y_positions = [p[1] for p in recent]
        if len(y_positions) < 2:
            return None

        # compute average delta
        deltas = [y_positions[i] - y_positions[i - 1] for i in range(1, len(y_positions))]
        avg_delta = float(np.mean(deltas))

        # thresholds in pixels to consider movement direction
        threshold_px = 2.0
        if avg_delta > threshold_px:
            return "downward"
        elif avg_delta < -threshold_px:
            return "upward"
        else:
            return "stationary"

    def is_point_in_roi(self, point, roi):
        """Check if a point (x,y) is inside rectangular ROI [x1,y1,x2,y2]."""
        x, y = point
        x1, y1, x2, y2 = roi
        return (x1 <= x <= x2) and (y1 <= y <= y2)

    def process_frame(self, frame, frame_number, fps, frame_width, frame_height):
        """
        Process a single frame: run tracking, update counts, estimate speeds, and detect congestion.

        Returns:
            counts: dict mapping class_name -> count (in ROI this frame)
            detections: list of detection dicts (for drawing or further processing)
        """
        counts = defaultdict(int)
        detections = []

        # Compute default ROI if not provided: left portion by roi_width_ratio
        if self.roi == [0, 0, 0, 0]:
            left_width = int(frame_width * self.roi_width_ratio)
            self.roi = [0, 0, left_width, frame_height]

        # Default counting line -> 75% height (bottom 25%)
        if self.counting_line_y is None:
            self.counting_line_y = int(frame_height * 0.75)

        # Run YOLO track
        # Use reasonable defaults for conf & tracker. Adjust as needed.
        results = self.model.track(
            frame,
            persist=True,
            conf=0.4,
            classes=list(self.class_names.keys()),
            tracker="bytetrack.yaml",
            verbose=False,
            device=self.device,
        )

        # results is a list; we take first result object for the frame
        if len(results) == 0:
            # nothing detected
            self.congestion_flags.append(False)
            return counts, detections

        res = results[0]

        # Ensure res.boxes exists and contains fields
        boxes_obj = getattr(res, "boxes", None)
        if boxes_obj is None or len(boxes_obj) == 0:
            # no boxes this frame
            self.congestion_flags.append(False)
            return counts, detections

        # Extract arrays safely (different ultralytics versions may have slightly different attributes)
        try:
            boxes_xyxy = boxes_obj.xyxy.cpu().numpy()  # N x 4
        except Exception:
            boxes_xyxy = np.array([])

        try:
            ids_arr = boxes_obj.id.int().cpu().numpy()
        except Exception:
            # if tracker didn't assign ids, create temporary unique ids from indices
            ids_arr = np.arange(len(boxes_xyxy), dtype=int)

        try:
            cls_arr = boxes_obj.cls.int().cpu().numpy()
        except Exception:
            cls_arr = np.zeros((len(boxes_xyxy),), dtype=int)

        try:
            confs = boxes_obj.conf.float().cpu().numpy()
        except Exception:
            confs = np.ones((len(boxes_xyxy),), dtype=float)

        # iterate through detections
        for i, box in enumerate(boxes_xyxy):
            tid = int(ids_arr[i]) if i < len(ids_arr) else i
            cid = int(cls_arr[i]) if i < len(cls_arr) else None
            conf = float(confs[i]) if i < len(confs) else 0.0

            if cid not in self.class_names:
                # class not in our mapping -> skip
                continue

            x1, y1, x2, y2 = map(int, box[:4])
            name = self.class_names[int(cid)]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            color = self.colors.get(name, (255, 255, 255))

            # update track history
            self.track_history[tid].append((cx, cy))
            if tid not in self.vehicle_status:
                self.vehicle_status[tid] = {"crossed": False, "direction": None}

            # estimate speed
            speed = self.calculate_speed(tid, (cx, cy), frame_number, fps)

            # detect movement direction
            direction = self.get_movement_direction(tid, (cx, cy))
            if direction is not None:
                self.vehicle_status[tid]["direction"] = direction

            # counting logic: crossing the blue line downward only
            status = self.vehicle_status[tid]
            if not status["crossed"] and self.counting_line_y is not None:
                # crossing check: box intersects the counting line and center below/above as needed
                crossing_downward = (y1 < self.counting_line_y <= y2)
                is_moving_downward = (status.get("direction") == "downward")
                if crossing_downward and is_moving_downward:
                    status["crossed"] = True
                    self.total_count += 1
                    self.vehicle_type_counts[name] += 1
                    # optional debug print
                    print(f"✓ COUNTED #{self.total_count}: {name.upper()} ID:{tid} (DOWNWARD)")

            # in ROI?
            in_roi = self.is_point_in_roi((cx, cy), self.roi)
            if in_roi:
                counts[name] += 1

            detections.append({
                "track_id": int(tid),
                "class_name": name,
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "confidence": float(conf),
                "center": (int(cx), int(cy)),
                "in_roi": bool(in_roi),
                "speed": float(speed) if speed is not None else None,
                "direction": direction,
                "color": color,
            })

        # Congestion detection: count slow vehicles inside ROI
        slow_in_roi = 0
        total_in_roi = 0
        for d in detections:
            if d["in_roi"]:
                total_in_roi += 1
                if d["speed"] is not None and d["speed"] <= self.max_speed_for_congestion:
                    slow_in_roi += 1

        congested = (
            total_in_roi >= self.min_vehicles_for_congestion and
            slow_in_roi >= 2  # at least 2 slow vehicles to raise flag
        )

        self.congestion_flags.append(bool(congested))

        return counts, detections

    def draw_detections(self, frame, detections, fps=None):
        """
        Draw detections, ROI, counting line, and indicators on a copy of the frame.
        Returns annotated frame.
        """
        h, w = frame.shape[:2]

        # Draw ROI (red rectangle)
        x1, y1, x2, y2 = self.roi
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)  # RED
        cv2.putText(frame, "CONGESTION MONITORING ZONE", (max(10, x1 + 10), max(30, y1 + 30)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # ROI size info
        roi_w = x2 - x1
        roi_h = y2 - y1
        cv2.putText(frame, f"ROI Size: {roi_w}x{roi_h} ({self.roi_width_ratio*100:.0f}% width)",
                    (max(10, x1 + 10), max(60, y1 + 60)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Counting line (blue)
        if self.counting_line_y:
            cv2.line(frame, (0, self.counting_line_y), (w, self.counting_line_y), (255, 0, 0), 3)
            cv2.putText(frame, "COUNTING LINE (DOWNWARD ONLY)", (20, self.counting_line_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            pct = int((self.counting_line_y / h) * 100)
            cv2.putText(frame, f"Line Pos: {pct}% from top", (20, self.counting_line_y - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

        # Stats (total count & congestion)
        cv2.putText(frame, f"TOTAL COUNT: {self.total_count}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        congested_now = self.congestion_flags[-1] if self.congestion_flags else False
        cv2.putText(frame, f"CONGESTION: {'YES' if congested_now else 'NO'}", (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255) if congested_now else (0, 255, 255), 2)

        # Draw each detection
        for d in detections:
            x, y, wb, hb = d["bbox"]
            track_id = d["track_id"]
            cname = d["class_name"]
            conf = d["confidence"]
            speed = d.get("speed")
            direction = d.get("direction")
            in_roi = d.get("in_roi", False)

            # highlight slow-in-roi in red
            is_slow_in_roi = in_roi and (speed is not None) and (speed <= self.max_speed_for_congestion)
            draw_color = (0, 0, 255) if is_slow_in_roi else tuple(d.get("color", (255, 255, 255)))
            thickness = 3 if in_roi else 2

            # Bounding box
            cv2.rectangle(frame, (x, y), (x + wb, y + hb), draw_color, thickness)

            # Label text
            label = f"{cname.upper()} {conf:.2f}"
            if speed is not None:
                label += f" {speed:.0f}kmh"
            if direction:
                label += f" {direction.upper()}"
            if in_roi:
                label += " (IN ROI)"

            # background for label
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x, y - th - 8), (x + tw + 6, y), draw_color, -1)
            cv2.putText(frame, label, (x + 2, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # direction arrow (if we have at least 2 positions)
            hist = self.track_history.get(track_id, None)
            if direction in ["downward", "upward"] and hist is not None and len(hist) >= 2:
                prev = hist[-2]
                curr = hist[-1]
                arrow_color = (0, 255, 0) if direction == "downward" else (0, 255, 255)
                cv2.arrowedLine(frame, (int(prev[0]), int(prev[1])), (int(curr[0]), int(curr[1])),
                                arrow_color, 2, tipLength=0.3)

        return frame

    def analyze_video(self, video_path, progress_callback=None, save_output=True, roi_normalized=None, **kwargs):
        """
        Analyze a video file and return a report dictionary.

        Args:
            video_path: path to input video
            progress_callback: optional function(progress_percent:int, frames_total:int, message:str)
            save_output: whether to save an annotated video to media/processed_videos
            roi_normalized: not used (kept for API compatibility)
            **kwargs: reserved
        Returns:
            report (dict) containing summary and metrics
        """
        if roi_normalized:
            print("⚠️ ROI parameter provided but not used by CongestionAwareDetector (uses roi_width_ratio or explicit roi).")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise Exception(f"❌ Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        # Reset state for this run
        self.reset_tracking_state()
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Prepare output writer if requested
        out = None
        output_path = None
        if save_output:
            os.makedirs("media/processed_videos", exist_ok=True)
            base = Path(video_path).stem
            output_path = f"media/processed_videos/congestion_{base}_{int(time.time())}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frame_number = 0
        start_time = time.time()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                counts, detections = self.process_frame(frame, frame_number, fps, width, height)
                annotated = self.draw_detections(frame.copy(), detections, fps)

                if out is not None:
                    out.write(annotated)

                # optional progress callback
                if progress_callback and total_frames > 0 and frame_number % 30 == 0:
                    progress = min(100, int((frame_number / total_frames) * 100))
                    progress_callback(progress, total_frames, f"Frame {frame_number}/{total_frames}")

                frame_number += 1

        finally:
            cap.release()
            if out is not None:
                out.release()

        duration = (total_frames / fps) if fps > 0 else 0
        proc_time = time.time() - start_time
        congested_ratio = (sum(self.congestion_flags) / len(self.congestion_flags)) if self.congestion_flags else 0.0

        if congested_ratio > 0.4:
            congestion_level = "High Congestion"
        elif congested_ratio > 0.15:
            congestion_level = "Moderate Congestion"
        else:
            congestion_level = "Light Traffic"

        # Build vehicle breakdown for reported classes (ensure all counted classes present)
        vehicle_breakdown = {c: int(self.vehicle_type_counts.get(c, 0)) for c in self.counted_classes}

        report = {
            "metadata": {
                "duration_seconds": duration,
                "processing_time_seconds": proc_time,
                "model_used": "collision4_model (YOLO)",
                "roi": self.roi,
                "roi_width_percentage": f"{self.roi_width_ratio*100:.0f}%",
                "counting_line_y": self.counting_line_y,
                "counting_line_position": f"{int((self.counting_line_y / height) * 100) if height else None}% from top",
                "counting_direction": "downward_only",
            },
            "summary": {
                "total_vehicles_counted": int(self.total_count),
                "vehicle_breakdown": vehicle_breakdown,
                "congested_frames": int(sum(self.congestion_flags)),
                "total_frames": int(len(self.congestion_flags)),
                "average_traffic_density_per_sec": (self.total_count / duration) if duration > 0 else 0.0,
            },
            "metrics": {
                "congestion_level": congestion_level,
                "congested_frame_ratio": round(congested_ratio, 3),
            },
            "output_video_path": output_path,
        }

        return report
