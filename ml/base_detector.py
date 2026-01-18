# ml/base_detector.py
"""
Base Detector Class for Vehicle Counting and Congestion Detection
All directional detectors will inherit from this base class.
"""

import cv2
import numpy as np
from collections import defaultdict, deque
from datetime import datetime
import time
import os
from pathlib import Path
from abc import ABC, abstractmethod


class BaseDetector(ABC):
    """
    Abstract base class for all directional traffic detectors.
    
    Key Features:
    - Vehicle detection and tracking
    - Directional counting logic
    - Congestion detection
    - Video processing pipeline
    - Results generation and storage
    """
    
    def __init__(self):
        """Initialize base detector with common attributes"""
        self.model = None
        self.device = None
        
        # Vehicle classes (COCO standard)
        self.class_names = {
            2: 'car',
            3: 'motorcycle',
            5: 'bus',
            7: 'truck'
        }
        
        # Colors for visualization
        self.colors = {
            "car": (100, 100, 255),       # Purple
            "motorcycle": (255, 255, 0),  # Yellow
            "bus": (0, 255, 0),           # Green
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
        
        print(f"🔧 BaseDetector initialized with {len(self.counted_classes)} vehicle classes")
    
    def setup_enhanced_metrics(self):
        """Initialize enhanced metrics for speed and performance tracking"""
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
        
        # Reset congestion
        self.congestion_events = []
        self.current_congestion = None
        self.frame_data = []
        
        # Reset metrics
        if hasattr(self, 'speed_data'):
            self.speed_data.clear()
            self.trajectory_data.clear()
            self.detection_confidence.clear()
        
        print("🔄 Tracking state reset")
    
    def calculate_speed(self, track_id, current_position, frame_number, fps):
        """
        Calculate vehicle speed based on trajectory.
        Override this method for more sophisticated speed calculation.
        
        Args:
            track_id: Vehicle tracking ID
            current_position: (x, y) current center
            frame_number: Current frame number
            fps: Video frame rate
            
        Returns:
            Speed in km/h or None if not enough data
        """
        if track_id not in self.track_history:
            return None
            
        history = list(self.track_history[track_id])
        if len(history) < 2:
            return None
        
        # Get recent positions
        recent_positions = history[-5:] if len(history) >= 5 else history
        recent_positions.append(current_position)
        
        # Calculate total distance traveled
        total_distance = 0
        for i in range(len(recent_positions) - 1):
            x1, y1 = recent_positions[i]
            x2, y2 = recent_positions[i + 1]
            distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            total_distance += distance
        
        # Convert to real-world speed (approximate)
        # Assuming 10 pixels = 1 meter (adjust based on camera calibration)
        pixels_per_meter = 10
        time_elapsed = len(recent_positions) / fps
        distance_meters = total_distance / pixels_per_meter
        
        if time_elapsed > 0:
            speed_mps = distance_meters / time_elapsed
            speed_kmh = speed_mps * 3.6
            return min(speed_kmh, 200)  # Cap at 200 km/h
            
        return None
    
    def calculate_congestion_level(self, detections, fps):
        """
        Calculate congestion level based on vehicle density and movement.
        Override this for custom congestion algorithms.
        
        Args:
            detections: List of vehicle detections
            fps: Video frame rate
            
        Returns:
            Dictionary with congestion info
        """
        total_vehicles = len(detections)
        
        # Simple congestion logic - override in child classes
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
        
        # Calculate stationary vehicles
        stationary_count = 0
        for det in detections:
            if det.get('speed', 100) < 5:  # Less than 5 km/h
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
        """
        Track congestion events over time.
        
        Args:
            congestion_info: Current congestion data
            fps: Video frame rate
        """
        current_time = self.frame_count / fps if fps > 0 else 0
        current_level = congestion_info['level']
        
        if current_level != 'none':
            # Congestion is happening
            if self.current_congestion is None:
                # Start new congestion event
                self.current_congestion = {
                    'level': current_level,
                    'start_time': current_time,
                    'start_frame': self.frame_count,
                    'peak_vehicles': congestion_info['total_vehicles'],
                    'peak_stationary': congestion_info['stationary_vehicles']
                }
            else:
                # Update existing congestion
                if congestion_info['total_vehicles'] > self.current_congestion['peak_vehicles']:
                    self.current_congestion['peak_vehicles'] = congestion_info['total_vehicles']
                if congestion_info['stationary_vehicles'] > self.current_congestion['peak_stationary']:
                    self.current_congestion['peak_stationary'] = congestion_info['stationary_vehicles']
                
                # Update level if it changed
                level_order = ['none', 'light', 'moderate', 'heavy', 'severe']
                if level_order.index(current_level) > level_order.index(self.current_congestion['level']):
                    self.current_congestion['level'] = current_level
        else:
            # Congestion ended
            if self.current_congestion is not None:
                event_duration = current_time - self.current_congestion['start_time']
                
                # Only record events longer than minimum duration
                if event_duration >= 10:  # 10 seconds minimum
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
        """
        Store per-frame data for dashboard analysis.
        
        Args:
            frame_number: Current frame number
            fps: Video frame rate
            counts: Vehicle counts per class
            congestion_info: Current congestion data
        """
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
        """
        ABSTRACT METHOD - Must be implemented by child classes.
        Set up counting line position and orientation for specific direction.
        
        Args:
            frame_width: Video frame width
            frame_height: Video frame height
            
        Returns:
            Tuple of (line_start, line_end, valid_direction_vector)
        """
        pass
    
    @abstractmethod
    def is_valid_direction(self, track_history, valid_direction_vector):
        """
        ABSTRACT METHOD - Must be implemented by child classes.
        Check if vehicle is moving in the valid counting direction.
        
        Args:
            track_history: Deque of vehicle's past positions
            valid_direction_vector: (dx, dy) vector representing valid direction
            
        Returns:
            Boolean indicating if vehicle direction is valid
        """
        pass
    
    @abstractmethod
    def process_frame(self, frame, frame_number, fps):
        """
        ABSTRACT METHOD - Must be implemented by child classes.
        Process a single frame for vehicle detection and counting.
        
        Args:
            frame: Input video frame
            frame_number: Current frame number
            fps: Video frame rate
            
        Returns:
            Tuple of (counts_dict, detections_list, congestion_info)
        """
        pass
    
    @abstractmethod
    def draw_detections(self, frame, detections, congestion_info, fps):
        """
        ABSTRACT METHOD - Must be implemented by child classes.
        Draw detection boxes, counting line, and information on frame.
        
        Args:
            frame: Input frame
            detections: List of vehicle detections
            congestion_info: Current congestion data
            fps: Video frame rate
            
        Returns:
            Annotated frame
        """
        pass
    
    def analyze_video(self, video_path, progress_callback=None, save_output=True, **kwargs):
        """
        Main video analysis pipeline.
        Can be overridden by child classes for custom processing.
        
        Args:
            video_path: Path to input video
            progress_callback: Function to report progress (optional)
            save_output: Whether to save processed video
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with analysis results
        """
        print(f"\n{'='*70}")
        print(f"🎬 STARTING VIDEO ANALYSIS")
        print(f"{'='*70}")
        
        # Open video
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
        print(f"   Frames: {total_frames}")
        print(f"   Duration: {duration:.2f} seconds")
        
        # Setup counting line
        self.setup_counting_line(width, height)
        
        # Setup video writer if saving output
        output_path = None
        out = None
        if save_output:
            os.makedirs('media/processed_videos', exist_ok=True)
            original_filename = Path(video_path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            detector_name = self.__class__.__name__.lower().replace('detector', '')
            output_filename = f"{detector_name}_{original_filename}_{timestamp}.mp4"
            output_path = Path('media/processed_videos') / output_filename
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            print(f"💾 Output will be saved to: {output_path}")
        
        # Reset tracking state
        self.reset_tracking_state()
        
        # Process frames
        frame_number = 0
        start_time = time.time()
        self.fps = fps
        
        print(f"\n⏳ Processing {total_frames} frames...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame
            frame_start = time.time()
            counts, detections, congestion_info = self.process_frame(frame, frame_number, fps)
            frame_time = time.time() - frame_start
            
            # Track congestion event
            self.track_congestion_event(congestion_info, fps)
            
            # Store frame data
            self.store_frame_data(frame_number, fps, counts, congestion_info)
            
            # Draw visualizations
            if out is not None or progress_callback:
                annotated_frame = self.draw_detections(frame.copy(), detections, congestion_info, fps)
                if out is not None:
                    out.write(annotated_frame)
            
            # Update progress
            if progress_callback and frame_number % 50 == 0:
                progress = min(88, 15 + int((frame_number / total_frames) * 73))
                message = f"Processing frame {frame_number}/{total_frames}"
                progress_callback(progress, total_frames, message)
            
            frame_number += 1
            self.processing_time += frame_time
        
        # Cleanup
        cap.release()
        if out is not None:
            out.release()
            print(f"✅ Processed video saved: {output_path}")
        
        total_time = time.time() - start_time
        print(f"\n✅ Analysis completed in {total_time:.2f} seconds")
        print(f"📈 Vehicles counted: {self.total_count}")
        print(f"📊 Vehicle breakdown: {dict(self.vehicle_counts)}")
        
        # Generate final report
        report = self.generate_report(total_frames, total_time, fps)
        
        if output_path:
            report['output_video_path'] = str(output_path)
        
        return report
    
    def generate_report(self, total_frames, proc_time, fps):
        """
        Generate comprehensive analysis report.
        Can be overridden by child classes for custom reporting.
        
        Args:
            total_frames: Total frames processed
            proc_time: Total processing time in seconds
            fps: Video frame rate
            
        Returns:
            Dictionary with analysis results
        """
        duration = total_frames / fps if fps > 0 else 0
        
        # Calculate vehicles per minute
        vpm = (self.total_count / duration) * 60 if duration > 0 else 0
        
        # Determine traffic level based on VPM
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
        
        # Summarize congestion events
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
        
        # Calculate detection efficiency
        detection_efficiency = {
            'frames_per_second': total_frames / proc_time if proc_time > 0 else 0,
            'processing_ratio': proc_time / duration if duration > 0 else 0,
            'vehicles_per_frame': self.total_count / total_frames if total_frames > 0 else 0
        }
        
        return {
            'metadata': {
                'detector_name': self.__class__.__name__,
                'video_duration': round(duration, 2),
                'processing_time': round(proc_time, 2),
                'processing_date': datetime.now().isoformat(),
                'total_frames': total_frames,
                'video_fps': round(fps, 2),
                'vehicle_classes': self.counted_classes
            },
            'counting_results': {
                'total_vehicles': self.total_count,
                'vehicle_breakdown': dict(self.vehicle_counts),
                'vehicles_per_minute': round(vpm, 2),
                'traffic_level': traffic_level,
                'detection_efficiency': detection_efficiency
            },
            'congestion_results': {
                'total_congestion_events': congestion_summary['total_events'],
                'total_congestion_duration': round(congestion_summary['total_duration'], 2),
                'congestion_events_by_level': dict(congestion_summary['events_by_level']),
                'average_congestion_duration': round(congestion_summary['average_duration'], 2),
                'congestion_percentage': round(
                    (congestion_summary['total_duration'] / duration * 100) if duration > 0 else 0, 2
                )
            },
            'raw_data': {
                'frame_data': self.frame_data[-1000:],  # Last 1000 frames for dashboard
                'congestion_events': self.congestion_events,
                'vehicle_counts_history': self.get_vehicle_counts_history()
            }
        }
    
    def get_vehicle_counts_history(self):
        """
        Get historical vehicle counts per frame.
        
        Returns:
            List of vehicle counts over time
        """
        history = []
        for frame in self.frame_data[-500:]:  # Last 500 frames
            history.append({
                'frame': frame['frame_number'],
                'timestamp': frame['timestamp'],
                'total_vehicles': frame['total_vehicles'],
                'counted_vehicles': frame.get('counted_vehicles', 0)
            })
        return history
    
    def export_results(self, output_path=None):
        """
        Export analysis results to JSON file.
        
        Args:
            output_path: Path to save JSON file (optional)
            
        Returns:
            Dictionary with all results
        """
        import json
        from datetime import datetime
        
        # Generate report
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
        """Print summary of analysis results"""
        print(f"\n{'='*70}")
        print(f"📊 ANALYSIS SUMMARY")
        print(f"{'='*70}")
        print(f"Detector: {self.__class__.__name__}")
        print(f"Frames processed: {self.frame_count}")
        print(f"Total vehicles counted: {self.total_count}")
        print(f"Vehicle breakdown:")
        for vehicle_type, count in self.vehicle_counts.items():
            print(f"  {vehicle_type.upper()}: {count}")
        print(f"Congestion events: {len(self.congestion_events)}")
        if self.congestion_events:
            total_duration = sum(e['duration'] for e in self.congestion_events)
            print(f"Total congestion time: {total_duration:.1f} seconds")
        print(f"{'='*70}")
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'model'):
            del self.model
        if hasattr(self, 'track_history'):
            self.track_history.clear()
        if hasattr(self, 'vehicle_status'):
            self.vehicle_status.clear()
        
        print("🧹 Resources cleaned up")