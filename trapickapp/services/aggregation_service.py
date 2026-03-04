#trapickapp/services/aggregation_service.py
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db.models import Sum, Avg, Count
import numpy as np

logger = logging.getLogger(__name__)


class VideoAggregationService:
    """
    Service for intelligently aggregating data from multiple video segments
    Now with enhanced metrics support (Phase 1 + ML v4.2 Report fields)
    """
    
    def __init__(self, location_date_group):
        """
        Initialize with a LocationDateGroup instance
        
        Args:
            location_date_group: LocationDateGroup object
        """
        self.group = location_date_group
        self.location = location_date_group.location
        self.date = location_date_group.date
        
        # Get all completed videos in this group, ordered by start time
        self.videos = list(location_date_group.videos.filter(
            processing_status='completed'
        ).order_by('video_start_time').select_related('traffic_analysis'))
        
        logger.info(f"📊 AggregationService initialized for {self.location.display_name} - {self.date}")
        logger.info(f"   Found {len(self.videos)} videos in group")
    
    def analyze_segments(self):
        """
        Analyze all video segments for overlaps and gaps
        
        Returns:
            Dictionary with segment analysis results
        """
        if not self.videos:
            return {
                'segments': [],
                'overlaps': [],
                'gaps': [],
                'total_duration_minutes': 0,
                'coverage_quality': 'no_data'
            }
        
        # Helper function to convert time to minutes since midnight
        def time_to_minutes(t):
            if not t:
                return None
            return t.hour * 60 + t.minute
        
        # Collect all segments with time data
        segments = []
        for video in self.videos:
            if video.video_start_time and video.video_end_time:
                start_minutes = time_to_minutes(video.video_start_time)
                end_minutes = time_to_minutes(video.video_end_time)
                
                # Handle overnight recordings
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                
                # Get vehicle data if analysis exists
                vehicles = 0
                vehicles_per_minute = 0
                vehicle_breakdown = {}
                
                if hasattr(video, 'traffic_analysis'):
                    analysis = video.traffic_analysis
                    vehicles = analysis.total_vehicles
                    duration_minutes = (end_minutes - start_minutes)
                    if duration_minutes > 0:
                        vehicles_per_minute = vehicles / duration_minutes
                    
                    vehicle_breakdown = {
                        'car': analysis.car_count,
                        'truck': analysis.truck_count,
                        'motorcycle': analysis.motorcycle_count,
                        'bus': analysis.bus_count,
                        'bicycle': analysis.bicycle_count,
                        'other': analysis.other_count
                    }
                
                segments.append({
                    'video_id': str(video.id),
                    'filename': video.filename,
                    'start': video.video_start_time.strftime('%H:%M'),
                    'end': video.video_end_time.strftime('%H:%M'),
                    'start_minutes': start_minutes,
                    'end_minutes': end_minutes,
                    'duration_minutes': end_minutes - start_minutes,
                    'vehicles': vehicles,
                    'vehicles_per_minute': vehicles_per_minute,
                    'vehicle_breakdown': vehicle_breakdown,
                    'congestion_level': analysis.congestion_level if hasattr(video, 'traffic_analysis') else 'unknown',
                    # ✅ NEW: Include enhanced metrics if available
                    'avg_speed': analysis.avg_speed_kmh if hasattr(analysis, 'avg_speed_kmh') else None,
                    'lane_stats': analysis.lane_statistics if hasattr(analysis, 'lane_statistics') else {},
                    'turning_movements': analysis.turning_movements if hasattr(analysis, 'turning_movements') else {},
                    # ✅ ADD NEW: ML v4.2 Report Fields
                    'tracker_stats': analysis.tracker_stats if hasattr(analysis, 'tracker_stats') else {},
                    'congestion_timeline': analysis.congestion_timeline if hasattr(analysis, 'congestion_timeline') else [],
                    'trajectory_summary': analysis.trajectory_summary if hasattr(analysis, 'trajectory_summary') else {},
                    'features_used': analysis.features_used if hasattr(analysis, 'features_used') else {},
                })
        
        # Sort by start time
        segments.sort(key=lambda x: x['start_minutes'])
        
        # Detect overlaps and gaps
        overlaps = []
        gaps = []
        
        for i in range(len(segments) - 1):
            current_end = segments[i]['end_minutes']
            next_start = segments[i + 1]['start_minutes']
            
            # Check for overlap
            if current_end > next_start:
                overlap_minutes = current_end - next_start
                overlaps.append({
                    'segment1': {
                        'video_id': segments[i]['video_id'],
                        'filename': segments[i]['filename'],
                        'range': f"{segments[i]['start']} - {segments[i]['end']}"
                    },
                    'segment2': {
                        'video_id': segments[i + 1]['video_id'],
                        'filename': segments[i + 1]['filename'],
                        'range': f"{segments[i + 1]['start']} - {segments[i + 1]['end']}"
                    },
                    'overlap_minutes': round(overlap_minutes, 1),
                    'overlap_start': self._minutes_to_time_str(next_start),
                    'overlap_end': self._minutes_to_time_str(current_end)
                })
            
            # Check for gap
            elif next_start > current_end:
                gap_minutes = next_start - current_end
                if gap_minutes > 1:  # Ignore tiny gaps (< 1 minute)
                    gaps.append({
                        'segment1': {
                            'video_id': segments[i]['video_id'],
                            'filename': segments[i]['filename'],
                            'end': segments[i]['end']
                        },
                        'segment2': {
                            'video_id': segments[i + 1]['video_id'],
                            'filename': segments[i + 1]['filename'],
                            'start': segments[i + 1]['start']
                        },
                        'gap_minutes': round(gap_minutes, 1),
                        'gap_start': self._minutes_to_time_str(current_end),
                        'gap_end': self._minutes_to_time_str(next_start)
                    })
        
        # Calculate total duration (excluding overlaps)
        total_duration = sum(s['duration_minutes'] for s in segments)
        
        # Determine coverage quality
        if not segments:
            coverage_quality = 'no_data'
        elif overlaps and gaps:
            coverage_quality = 'mixed_issues'
        elif overlaps:
            coverage_quality = 'has_overlaps'
        elif gaps:
            coverage_quality = 'has_gaps'
        else:
            coverage_quality = 'perfect'
        
        return {
            'segments': segments,
            'overlaps': overlaps,
            'gaps': gaps,
            'total_duration_minutes': round(total_duration, 1),
            'coverage_quality': coverage_quality,
            'segment_count': len(segments),
            'has_overlaps': len(overlaps) > 0,
            'has_gaps': len(gaps) > 0
        }
    
    def _minutes_to_time_str(self, minutes):
        """Convert minutes since midnight to time string"""
        minutes = minutes % (24 * 60)  # Handle overnight
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    
    def resolve_overlaps(self, segments, overlaps):
        """
        Resolve overlapping segments by creating a non-overlapping timeline
        
        Args:
            segments: List of segments
            overlaps: List of detected overlaps
            
        Returns:
            List of resolved, non-overlapping segments
        """
        if not overlaps:
            return segments
        
        logger.info(f"Resolving {len(overlaps)} overlaps...")
        
        # Create a merged timeline
        timeline = []
        for seg in segments:
            timeline.append({
                'time': seg['start_minutes'],
                'type': 'start',
                'segment': seg
            })
            timeline.append({
                'time': seg['end_minutes'],
                'type': 'end',
                'segment': seg
            })
        
        # Sort by time
        timeline.sort(key=lambda x: x['time'])
        
        # Process timeline to create non-overlapping intervals
        resolved = []
        active_segments = []
        current_start = None
        
        for event in timeline:
            if event['type'] == 'start':
                if not active_segments and current_start is not None:
                    # End previous interval
                    if current_start < event['time']:
                        resolved.append({
                            'start_minutes': current_start,
                            'end_minutes': event['time'],
                            'active_segments': active_segments.copy()
                        })
                
                active_segments.append(event['segment'])
                current_start = event['time']
            
            else:  # 'end' event
                if len(active_segments) == 1 and current_start is not None:
                    # End interval
                    if current_start < event['time']:
                        resolved.append({
                            'start_minutes': current_start,
                            'end_minutes': event['time'],
                            'active_segments': active_segments.copy()
                        })
                    current_start = None
                
                # Remove this segment from active list
                active_segments = [s for s in active_segments 
                                 if s['video_id'] != event['segment']['video_id']]
        
        return resolved
    
    def weighted_aggregation(self):
        """
        Perform weighted aggregation across all video segments
        
        Returns:
            Dictionary with aggregated data including confidence scores
        """
        # First, analyze segments
        analysis = self.analyze_segments()
        
        if not analysis['segments']:
            return {
                'total_vehicles': 0,
                'vehicle_breakdown': {},
                'total_duration_minutes': 0,
                'weighted_vehicles_per_hour': 0,
                'confidence_score': 0,
                'segment_count': 0,
                'warnings': ['No video segments found']
            }
        
        segments = analysis['segments']
        overlaps = analysis['overlaps']
        
        # Check for issues
        warnings = []
        if overlaps:
            warnings.append(f"⚠️ {len(overlaps)} overlapping segments detected")
        if analysis['gaps']:
            warnings.append(f"⚠️ {len(analysis['gaps'])} gaps detected")
        
        # Resolve overlaps if any
        if overlaps:
            resolved_intervals = self.resolve_overlaps(segments, overlaps)
            
            # Aggregate using resolved intervals
            total_vehicles = 0
            weighted_breakdown = defaultdict(float)
            total_weighted_minutes = 0
            
            for interval in resolved_intervals:
                interval_duration = interval['end_minutes'] - interval['start_minutes']
                active_count = len(interval['active_segments'])
                
                if active_count > 0:
                    # Average across active segments
                    for seg in interval['active_segments']:
                        # Weight by interval duration and divide by active count
                        weight = interval_duration / active_count
                        
                        total_vehicles += seg['vehicles_per_minute'] * weight
                        total_weighted_minutes += weight
                        
                        for vtype, count in seg['vehicle_breakdown'].items():
                            if count > 0:
                                vpm = count / seg['duration_minutes'] if seg['duration_minutes'] > 0 else 0
                                weighted_breakdown[vtype] += vpm * weight
            
            # Calculate confidence score (lower confidence when overlaps exist)
            base_confidence = 80  # Start at 80%
            overlap_penalty = min(30, len(overlaps) * 5)  # 5% per overlap, max 30%
            confidence = max(50, base_confidence - overlap_penalty)
            
        else:
            # No overlaps - simple weighted aggregation
            total_duration = analysis['total_duration_minutes']
            total_vehicles = 0
            weighted_breakdown = defaultdict(float)
            
            for seg in segments:
                weight = seg['duration_minutes'] / total_duration if total_duration > 0 else 0
                total_vehicles += seg['vehicles'] * weight
                
                for vtype, count in seg['vehicle_breakdown'].items():
                    weighted_breakdown[vtype] += count * weight
            
            # Calculate confidence based on gaps
            base_confidence = 95  # Start at 95%
            gap_penalty = min(30, len(analysis['gaps']) * 10)  # 10% per gap, max 30%
            confidence = max(65, base_confidence - gap_penalty)
        
        # Calculate vehicles per hour
        vehicles_per_hour = (total_vehicles / analysis['total_duration_minutes']) * 60 if analysis['total_duration_minutes'] > 0 else 0
        
        return {
            'total_vehicles': round(total_vehicles),
            'vehicle_breakdown': {k: round(v) for k, v in weighted_breakdown.items()},
            'total_duration_minutes': round(analysis['total_duration_minutes'], 1),
            'total_duration_hours': round(analysis['total_duration_minutes'] / 60, 2),
            'weighted_vehicles_per_hour': round(vehicles_per_hour, 1),
            'confidence_score': round(confidence, 1),
            'segment_count': len(segments),
            'warnings': warnings,
            'has_overlaps': analysis['has_overlaps'],
            'has_gaps': analysis['has_gaps']
        }
    
    def hourly_aggregation(self):
        """
        Aggregate data by hour of day
        
        Returns:
            Dictionary with hourly vehicle distribution
        """
        hourly_data = {hour: {
            'vehicles': 0,
            'minutes_recorded': 0,
            'segments': 0,
            'confidence': 0,
            # ✅ NEW: Enhanced metrics per hour
            'avg_speed': 0,
            'total_speed_samples': 0,
            'lane_usage': defaultdict(int),
        } for hour in range(24)}
        
        for video in self.videos:
            if not (video.video_start_time and video.video_end_time and hasattr(video, 'traffic_analysis')):
                continue
            
            analysis = video.traffic_analysis
            
            # Convert to minutes
            start_minutes = video.video_start_time.hour * 60 + video.video_start_time.minute
            end_minutes = video.video_end_time.hour * 60 + video.video_end_time.minute
            
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            
            duration = end_minutes - start_minutes
            
            if duration <= 0:
                continue
            
            vehicles_per_minute = analysis.total_vehicles / duration
            
            # ✅ NEW: Enhanced metrics per minute
            speed_per_minute = analysis.avg_speed_kmh if analysis.avg_speed_kmh else 0
            
            # Distribute across hours
            current_minute = start_minutes
            while current_minute < end_minutes:
                hour = (current_minute // 60) % 24
                
                # Calculate minutes in this hour
                next_hour = ((hour + 1) * 60) % (24 * 60)
                if next_hour < hour * 60:
                    next_hour += 24 * 60
                
                minutes_in_hour = min(next_hour, end_minutes) - current_minute
                
                if minutes_in_hour > 0:
                    hourly_data[hour]['vehicles'] += vehicles_per_minute * minutes_in_hour
                    hourly_data[hour]['minutes_recorded'] += minutes_in_hour
                    hourly_data[hour]['segments'] += 1
                    
                    # ✅ NEW: Aggregate enhanced metrics
                    if speed_per_minute:
                        hourly_data[hour]['avg_speed'] += speed_per_minute * minutes_in_hour
                        hourly_data[hour]['total_speed_samples'] += minutes_in_hour
                
                current_minute += minutes_in_hour
        
        # Calculate confidence and averages for each hour
        max_minutes = 60  # Maximum possible minutes in an hour
        for hour in hourly_data:
            if hourly_data[hour]['minutes_recorded'] > 0:
                coverage_percentage = (hourly_data[hour]['minutes_recorded'] / max_minutes) * 100
                hourly_data[hour]['confidence'] = round(min(100, coverage_percentage), 1)
                hourly_data[hour]['vehicles'] = round(hourly_data[hour]['vehicles'])
                
                # ✅ NEW: Calculate average speed for the hour
                if hourly_data[hour]['total_speed_samples'] > 0:
                    hourly_data[hour]['avg_speed'] = round(
                        hourly_data[hour]['avg_speed'] / hourly_data[hour]['total_speed_samples'], 1
                    )
                else:
                    hourly_data[hour]['avg_speed'] = None
            else:
                hourly_data[hour]['confidence'] = 0
                hourly_data[hour]['avg_speed'] = None
            
            # Convert defaultdict to dict for JSON serialization
            hourly_data[hour]['lane_usage'] = dict(hourly_data[hour]['lane_usage'])
        
        return hourly_data
    
    def peak_hour_analysis(self):
        """
        Identify peak hours with confidence scores
        
        Returns:
            Dictionary with peak hour information
        """
        hourly = self.hourly_aggregation()
        
        # Find morning peak (6 AM - 11 AM)
        morning_hours = {h: hourly[h] for h in range(6, 12) if hourly[h]['vehicles'] > 0}
        # Find evening peak (4 PM - 8 PM)
        evening_hours = {h: hourly[h] for h in range(16, 21) if hourly[h]['vehicles'] > 0}
        
        morning_peak = None
        evening_peak = None
        
        if morning_hours:
            morning_peak_hour = max(morning_hours.items(), key=lambda x: x[1]['vehicles'])[0]
            morning_peak = {
                'hour': morning_peak_hour,
                'time_range': f"{morning_peak_hour:02d}:00 - {morning_peak_hour + 1:02d}:00",
                'vehicles': morning_hours[morning_peak_hour]['vehicles'],
                'confidence': morning_hours[morning_peak_hour]['confidence'],
                'minutes_recorded': morning_hours[morning_peak_hour]['minutes_recorded'],
                # ✅ NEW: Include average speed at peak hour
                'avg_speed': morning_hours[morning_peak_hour]['avg_speed'],
            }
        
        if evening_hours:
            evening_peak_hour = max(evening_hours.items(), key=lambda x: x[1]['vehicles'])[0]
            evening_peak = {
                'hour': evening_peak_hour,
                'time_range': f"{evening_peak_hour:02d}:00 - {evening_peak_hour + 1:02d}:00",
                'vehicles': evening_hours[evening_peak_hour]['vehicles'],
                'confidence': evening_hours[evening_peak_hour]['confidence'],
                'minutes_recorded': evening_hours[evening_peak_hour]['minutes_recorded'],
                # ✅ NEW: Include average speed at peak hour
                'avg_speed': evening_hours[evening_peak_hour]['avg_speed'],
            }
        
        return {
            'morning_peak': morning_peak,
            'evening_peak': evening_peak,
            'hourly_distribution': hourly
        }
    
    def generate_timeline_view(self):
        """
        Generate a visual timeline of coverage
        
        Returns:
            Dictionary with timeline data for frontend visualization
        """
        analysis = self.analyze_segments()
        
        timeline = []
        for seg in analysis['segments']:
            timeline.append({
                'start': seg['start'],
                'end': seg['end'],
                'duration': seg['duration_minutes'],
                'vehicles': seg['vehicles'],
                'vehicles_per_minute': round(seg['vehicles_per_minute'], 1),
                'filename': seg['filename'],
                'video_id': seg['video_id'],
                'has_analysis': seg['vehicles'] > 0,
                # ✅ NEW: Include enhanced data in timeline
                'avg_speed': seg.get('avg_speed'),
                'congestion_level': seg.get('congestion_level', 'unknown'),
                # ✅ ADD NEW: ML v4.2 Report Fields
                'tracker_stats': seg.get('tracker_stats', {}),
                'congestion_timeline': seg.get('congestion_timeline', []),
                'trajectory_summary': seg.get('trajectory_summary', {}),
                'features_used': seg.get('features_used', {}),
            })
        
        return {
            'segments': timeline,
            'overlaps': analysis['overlaps'],
            'gaps': analysis['gaps'],
            'total_duration': analysis['total_duration_minutes'],
            'coverage_quality': analysis['coverage_quality']
        }
    
    # ──────────────────────────────────────────────────────────────────────────
    # ✅ NEW: Enhanced aggregation methods (Phase 1 + ML v4.2 Report)
    # ──────────────────────────────────────────────────────────────────────────
    
    def get_tracker_performance_summary(self):
        """
        Get tracker performance metrics across videos
        
        Returns:
            Dictionary with aggregated tracker statistics
        """
        tracker_stats = []
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.tracker_stats:
                tracker_stats.append(video.traffic_analysis.tracker_stats)
        
        if not tracker_stats:
            return {}
        
        # Aggregate numeric fields safely
        def safe_mean(values, key, default=0):
            valid = [v.get(key, default) for v in values if isinstance(v.get(key), (int, float))]
            return np.mean(valid) if valid else default
        
        def safe_sum(values, key, default=0):
            valid = [v.get(key, default) for v in values if isinstance(v.get(key), (int, float))]
            return sum(valid)
        
        return {
            'avg_prediction_confidence': round(safe_mean(tracker_stats, 'avg_prediction_confidence'), 2),
            'total_ghost_recoveries': safe_sum(tracker_stats, 'ghost_recoveries'),
            'avg_track_length': round(safe_mean(tracker_stats, 'avg_track_length'), 1),
            'total_tracks': safe_sum(tracker_stats, 'total_tracks'),
            'avg_id_switches': round(safe_mean(tracker_stats, 'id_switches'), 1),
            'reid_success_rate': round(safe_mean(tracker_stats, 'reid_success_rate') * 100, 1) if any('reid_success_rate' in s for s in tracker_stats) else None,
            'sample_count': len(tracker_stats),
        }
    
    def get_congestion_timeline_aggregated(self):
        """
        Aggregate congestion timelines across videos
        
        Returns:
            List of aggregated timeline entries with absolute timestamps
        """
        all_timelines = []
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.congestion_timeline:
                timeline = video.traffic_analysis.congestion_timeline
                # Adjust timestamps relative to video start
                if video.video_start_time:
                    base_seconds = video.video_start_time.hour * 3600 + video.video_start_time.minute * 60
                    for entry in timeline:
                        adjusted = dict(entry)
                        adjusted['absolute_time'] = base_seconds + entry.get('timestamp', 0)
                        adjusted['video_id'] = str(video.id)
                        adjusted['filename'] = video.filename
                        all_timelines.append(adjusted)
        
        # Sort by absolute time
        all_timelines.sort(key=lambda x: x.get('absolute_time', 0))
        
        return all_timelines
    
    def get_trajectory_summary_aggregated(self):
        """
        Aggregate trajectory summaries across videos
        
        Returns:
            Dictionary with combined trajectory statistics
        """
        trajectory_summaries = []
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.trajectory_summary:
                trajectory_summaries.append(video.traffic_analysis.trajectory_summary)
        
        if not trajectory_summaries:
            return {}
        
        # Merge common fields
        merged = {
            'total_trajectories': sum(s.get('total_trajectories', 0) for s in trajectory_summaries),
            'avg_trajectory_length': np.mean([s.get('avg_trajectory_length', 0) for s in trajectory_summaries if s.get('avg_trajectory_length')]),
            'common_paths': self._merge_common_paths(trajectory_summaries),
            'turning_patterns': self._merge_turning_patterns(trajectory_summaries),
        }
        
        return {k: v for k, v in merged.items() if v is not None}
    
    def _merge_common_paths(self, summaries):
        """Merge common path data from multiple trajectory summaries"""
        path_counts = defaultdict(int)
        for summary in summaries:
            for path, count in summary.get('common_paths', {}).items():
                path_counts[path] += count
        # Return top 10 most common paths
        return dict(sorted(path_counts.items(), key=lambda x: x[1], reverse=True)[:10])
    
    def _merge_turning_patterns(self, summaries):
        """Merge turning pattern data from multiple trajectory summaries"""
        turning = defaultdict(lambda: defaultdict(int))
        for summary in summaries:
            for entry_point, turns in summary.get('turning_patterns', {}).items():
                for turn_type, count in turns.items():
                    turning[entry_point][turn_type] += count
        return {k: dict(v) for k, v in turning.items()}
    
    def _aggregate_features_used(self):
        """
        Aggregate feature flags used across all videos
        
        Returns:
            Dictionary with feature usage summary
        """
        feature_counts = defaultdict(int)
        total_videos = 0
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.features_used:
                total_videos += 1
                features = video.traffic_analysis.features_used
                for feature, enabled in features.items():
                    if enabled:
                        feature_counts[feature] += 1
        
        if total_videos == 0:
            return {}
        
        return {
            feature: {
                'enabled_count': count,
                'percentage': round(count / total_videos * 100, 1)
            }
            for feature, count in feature_counts.items()
        }
    
    def get_speed_profile(self):
        """
        Get speed profile across all analyses
        
        Returns:
            Dictionary with speed statistics
        """
        speeds = []
        p85_speeds = []
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.avg_speed_kmh:
                analysis = video.traffic_analysis
                speeds.append(analysis.avg_speed_kmh)
                if analysis.p85_speed_kmh:
                    p85_speeds.append(analysis.p85_speed_kmh)
        
        if not speeds:
            return {}
        
        return {
            'overall_avg_speed': round(np.mean(speeds), 1),
            'overall_p85_speed': round(np.mean(p85_speeds), 1) if p85_speeds else None,
            'min_speed': round(min(speeds), 1),
            'max_speed': round(max(speeds), 1),
            'speed_distribution': self._get_speed_distribution(speeds),
            'time_of_day_speeds': self._get_speed_by_time(),
        }
    
    def _get_speed_distribution(self, speeds):
        """Get speed distribution histogram"""
        if not speeds:
            return {}
        
        # Create histogram bins
        bins = [0, 10, 20, 30, 40, 50, 60, 80, 100]
        hist = {}
        for i in range(len(bins)-1):
            label = f"{bins[i]}-{bins[i+1]}"
            count = sum(1 for s in speeds if bins[i] <= s < bins[i+1])
            hist[label] = count
        
        return hist
    
    def _get_speed_by_time(self):
        """Get average speed by time of day"""
        speeds_by_hour = defaultdict(list)
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.avg_speed_kmh:
                if video.video_start_time:
                    hour = video.video_start_time.hour
                    speeds_by_hour[hour].append(video.traffic_analysis.avg_speed_kmh)
        
        return {
            hour: round(sum(speeds)/len(speeds), 1)
            for hour, speeds in speeds_by_hour.items()
        }
    
    def get_lane_distribution(self):
        """
        Get lane usage statistics
        
        Returns:
            Dictionary with per-lane counts and percentages
        """
        lane_counts = defaultdict(int)
        total_vehicles_with_lane = 0
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.lane_statistics:
                lane_stats = video.traffic_analysis.lane_statistics
                for lane, count in lane_stats.items():
                    lane_counts[lane] += count
                    total_vehicles_with_lane += count
        
        if total_vehicles_with_lane == 0:
            return {}
        
        return {
            lane: {
                'count': count,
                'percentage': round(count / total_vehicles_with_lane * 100, 1)
            }
            for lane, count in lane_counts.items()
        }
    
    def get_turning_patterns(self):
        """
        Get turning movement patterns
        
        Returns:
            Dictionary with turn counts by vehicle class
        """
        turning_totals = defaultdict(lambda: defaultdict(int))
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.turning_movements:
                turns = video.traffic_analysis.turning_movements
                for vehicle_class, movements in turns.items():
                    for turn_type, count in movements.items():
                        turning_totals[vehicle_class][turn_type] += count
        
        # Convert nested defaultdict to dict
        result = {}
        for vehicle_class, movements in turning_totals.items():
            result[vehicle_class] = dict(movements)
        
        return result
    
    def get_incident_timeline(self):
        """
        Get timeline of incidents/hotspots
        
        Returns:
            List of incident events
        """
        incidents = []
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis'):
                analysis = video.traffic_analysis
                
                # Check for high incident risk
                if analysis.incident_risk_score and analysis.incident_risk_score > 0.5:
                    incidents.append({
                        'video_id': str(video.id),
                        'timestamp': analysis.analyzed_at.isoformat(),
                        'risk_score': round(analysis.incident_risk_score, 2),
                        'queue_length': analysis.queue_length_meters,
                        'location': self.location.display_name,
                        'congestion_index': analysis.congestion_index,
                    })
                
                # Check for stopped vehicles
                if analysis.stopped_vehicles_count > 3:
                    incidents.append({
                        'video_id': str(video.id),
                        'timestamp': analysis.analyzed_at.isoformat(),
                        'type': 'multiple_stopped_vehicles',
                        'stopped_count': analysis.stopped_vehicles_count,
                        'location': self.location.display_name,
                    })
        
        return incidents
    
    def get_congestion_summary_enhanced(self):
        """
        Get enhanced congestion summary
        
        Returns:
            Dictionary with congestion metrics
        """
        indices = []
        queue_lengths = []
        risks = []
        
        for video in self.videos:
            if hasattr(video, 'traffic_analysis'):
                analysis = video.traffic_analysis
                if analysis.congestion_index:
                    indices.append(analysis.congestion_index)
                if analysis.queue_length_meters:
                    queue_lengths.append(analysis.queue_length_meters)
                if analysis.incident_risk_score:
                    risks.append(analysis.incident_risk_score)
        
        return {
            'avg_congestion_index': round(np.mean(indices), 2) if indices else None,
            'max_queue_length': round(max(queue_lengths), 1) if queue_lengths else None,
            'avg_queue_length': round(np.mean(queue_lengths), 1) if queue_lengths else None,
            'avg_incident_risk': round(np.mean(risks), 2) if risks else None,
            'trend': self._get_congestion_trend(),
        }
    
    def _get_congestion_trend(self):
        """Analyze congestion trend over time"""
        if len(self.videos) < 3:
            return 'stable'
        
        # Get videos with congestion index
        videos_with_index = [
            v for v in self.videos 
            if hasattr(v, 'traffic_analysis') and v.traffic_analysis.congestion_index
        ]
        
        if len(videos_with_index) < 3:
            return 'stable'
        
        # Sort by time
        sorted_videos = sorted(videos_with_index, key=lambda v: v.video_start_time or v.uploaded_at)
        indices = [v.traffic_analysis.congestion_index for v in sorted_videos]
        
        # Simple trend detection
        first_third = np.mean(indices[:len(indices)//3])
        last_third = np.mean(indices[-len(indices)//3:])
        
        if last_third > first_third * 1.2:
            return 'worsening'
        elif last_third < first_third * 0.8:
            return 'improving'
        else:
            return 'stable'
    
    def get_aggregation_summary(self):
        """
        Get a complete summary of all aggregation results
        
        Returns:
            Dictionary with comprehensive aggregation data
        """
        weighted = self.weighted_aggregation()
        peaks = self.peak_hour_analysis()
        timeline = self.generate_timeline_view()
        
        # ✅ NEW: Enhanced summaries
        speed_profile = self.get_speed_profile()
        lane_distribution = self.get_lane_distribution()
        turning_patterns = self.get_turning_patterns()
        incidents = self.get_incident_timeline()
        congestion_enhanced = self.get_congestion_summary_enhanced()
        
        # ✅ ADD NEW: ML v4.2 Report aggregations
        tracker_performance = self.get_tracker_performance_summary()
        congestion_timeline = self.get_congestion_timeline_aggregated()
        trajectory_summary = self.get_trajectory_summary_aggregated()
        features_used = self._aggregate_features_used()
        
        return {
            'location': {
                'id': str(self.location.id),
                'name': self.location.display_name
            },
            'date': self.date.isoformat(),
            'aggregated_data': weighted,
            'peak_hours': peaks,
            'timeline': timeline,
            'segment_analysis': {
                'total_segments': len(self.videos),
                'segments_with_data': sum(1 for v in self.videos if hasattr(v, 'traffic_analysis')),
                'coverage_quality': timeline['coverage_quality']
            },
            # ✅ NEW: Enhanced sections
            'enhanced': {
                'speed_profile': speed_profile,
                'lane_distribution': lane_distribution,
                'turning_patterns': turning_patterns,
                'incidents': incidents,
                'congestion': congestion_enhanced,
                # ✅ ADD NEW: ML v4.2 Report Fields
                'tracker_performance': tracker_performance,
                'congestion_timeline': congestion_timeline,
                'trajectory_summary': trajectory_summary,
                'features_used': features_used,
            }
        }