# trapickapp/models.py
from django.db import models
from django.utils import timezone
import uuid
import os
import logging
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class ProcessingProfile(models.Model):
    """Simple processing profiles for directional detectors"""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    DETECTOR_TYPES = [
        ('vertical_top_bottom', 'Vertical Top→Bottom'),
        ('vertical_bottom_top', 'Vertical Bottom→Top'),
        ('horizontal_left_right', 'Horizontal Left→Right'),
        ('horizontal_right_left', 'Horizontal Right→Left'),
        ('diagonal_ne_sw', 'Diagonal NE→SW'),
        ('diagonal_nw_se', 'Diagonal NW→SE'),
        ('diagonal_se_nw', 'Diagonal SE→NW'),
        ('diagonal_sw_ne', 'Diagonal SW→NE'),
    ]

    detector_type = models.CharField(
        max_length=50,
        choices=DETECTOR_TYPES,
        default='vertical_top_bottom',
        help_text="Type of detector to use"
    )

    enable_congestion_detection = models.BooleanField(default=True)
    congestion_threshold = models.IntegerField(default=5)

    ROAD_TYPES = [
        ('highway', 'Highway'),
        ('intersection', 'Intersection'),
        ('urban', 'Urban Street'),
        ('generic', 'Generic'),
    ]

    road_type = models.CharField(
        max_length=50,
        choices=ROAD_TYPES,
        default='generic'
    )

    config_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON configuration parameters for this processing profile"
    )

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['road_type', 'display_name']
        verbose_name = "Processing Profile"
        verbose_name_plural = "Processing Profiles"

    def __str__(self):
        return f"{self.display_name} ({self.get_road_type_display()})"

    def get_detector_instance(self):
        """
        Get detector instance.
        Uses a process-level LRU cache so the YOLO model is loaded only once
        per (detector_type, model_path) combination per worker process.
        """
        from ml.directional_detectors import _load_cached_detector

        BASE_DIR = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        )
        custom_model_path = os.path.join(
            BASE_DIR, 'runs', 'detect', 'custom_model', 'weights', 'best.pt'
        )

        model_path = self.config_parameters.get('model_path', custom_model_path)

        try:
            detector = _load_cached_detector(self.detector_type, model_path)

            if hasattr(detector, 'enable_congestion_detection'):
                detector.enable_congestion_detection = self.enable_congestion_detection

            if hasattr(detector, 'congestion_threshold'):
                detector.congestion_threshold = self.congestion_threshold

            if self.config_parameters:
                for key, value in self.config_parameters.items():
                    if key != 'model_path' and hasattr(detector, key):
                        setattr(detector, key, value)

            return detector

        except Exception as e:
            logger.error(f"Error creating detector {self.detector_type}: {e}")
            raise RuntimeError(f"Failed to create detector: {e}")


class Location(models.Model):
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    processing_profile = models.ForeignKey(
        ProcessingProfile,
        on_delete=models.PROTECT,
        related_name='locations',
        help_text="Processing profile with directional settings"
    )

    counting_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Location-specific counting configuration"
    )

    class Meta:
        ordering = ['display_name']
        verbose_name_plural = "Locations"

    def __str__(self):
        return f"{self.display_name}"

    def get_counting_direction(self):
        profile = self.processing_profile
        if profile.detector_type in [
            'vertical_top_bottom', 'vertical_bottom_top',
            'horizontal_left_right', 'horizontal_right_left',
            'diagonal_ne_sw', 'diagonal_nw_se',
            'diagonal_se_nw', 'diagonal_sw_ne',
        ]:
            return profile.get_detector_type_display()
        return "Unknown"


class LocationDateGroup(models.Model):
    """Groups processed videos by location and date with coverage tracking"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='date_groups')
    date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Directional statistics
    total_directional_count = models.IntegerField(default=0)
    average_directional_flow = models.FloatField(default=0.0)
    peak_directional_flow = models.IntegerField(default=0)

    # Coverage tracking
    total_coverage_minutes = models.FloatField(default=0.0)
    coverage_gaps = models.JSONField(default=list, blank=True)
    coverage_continuity_score = models.FloatField(default=100.0)
    coverage_segments = models.JSONField(default=list, blank=True)

    # Aggregated data
    hourly_distribution = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['location', 'date']
        ordering = ['-date', 'location__display_name']
        verbose_name = "Location Date Group"
        verbose_name_plural = "Location Date Groups"

    def __str__(self):
        return f"{self.location.display_name} - {self.date}"

    def get_videos_by_time(self):
        return self.videos.all().order_by('video_start_time')

    def get_time_range(self):
        """Returns a formatted string showing start time to end time."""
        videos = self.videos.filter(processing_status='completed').order_by('video_start_time')

        if not videos.exists():
            return "No time data"

        times = []
        for video in videos:
            if video.video_start_time:
                times.append(video.video_start_time)
            if video.video_end_time:
                times.append(video.video_end_time)

        if not times:
            return "No time data"

        earliest = min(times)
        latest = max(times)
        return f"{earliest.strftime('%H:%M')} - {latest.strftime('%H:%M')}"

    def get_detailed_time_range(self):
        """Calculate detailed time range showing actual coverage pattern."""
        videos = self.videos.filter(processing_status='completed').order_by('video_start_time')

        if not videos.exists():
            return {
                'full_range': 'No data',
                'segments': [],
                'gaps': [],
                'total_coverage_minutes': 0,
                'coverage_percentage': 0,
                'has_gaps': False,
                'gap_count': 0,
                'continuity': 'No data',
            }

        segments = []
        total_minutes = 0

        def time_to_minutes(t):
            return t.hour * 60 + t.minute

        def minutes_to_time_str(minutes):
            minutes = minutes % (24 * 60)
            return f"{minutes // 60:02d}:{minutes % 60:02d}"

        for video in videos:
            if video.video_start_time and video.video_end_time:
                start_minutes = time_to_minutes(video.video_start_time)
                end_minutes = time_to_minutes(video.video_end_time)

                if end_minutes < start_minutes:
                    end_minutes += 24 * 60

                duration = end_minutes - start_minutes

                vehicles = 0
                if hasattr(video, 'traffic_analysis'):
                    vehicles = video.traffic_analysis.total_vehicles

                segments.append({
                    'start': video.video_start_time.strftime('%H:%M'),
                    'end': video.video_end_time.strftime('%H:%M'),
                    'start_minutes': start_minutes,
                    'end_minutes': end_minutes,
                    'duration': duration,
                    'video_id': str(video.id),
                    'filename': video.filename,
                    'vehicles': vehicles,
                    'vehicles_per_minute': round(vehicles / duration, 1) if duration > 0 else 0,
                })
                total_minutes += duration

        segments.sort(key=lambda x: x['start_minutes'])

        gaps = []
        for i in range(len(segments) - 1):
            gap_minutes = segments[i + 1]['start_minutes'] - segments[i]['end_minutes']
            if gap_minutes > 1:
                gaps.append({
                    'start': minutes_to_time_str(segments[i]['end_minutes']),
                    'end': minutes_to_time_str(segments[i + 1]['start_minutes']),
                    'duration': gap_minutes,
                })

        if segments:
            total_span = segments[-1]['end_minutes'] - segments[0]['start_minutes']
            coverage_percentage = (total_minutes / total_span * 100) if total_span > 0 else 100
        else:
            coverage_percentage = 0

        clean_segments = [
            {
                'start': s['start'],
                'end': s['end'],
                'duration': s['duration'],
                'video_id': s['video_id'],
                'filename': s['filename'],
                'vehicles': s['vehicles'],
                'vehicles_per_minute': s['vehicles_per_minute'],
            }
            for s in segments
        ]

        return {
            'full_range': f"{segments[0]['start']} - {segments[-1]['end']}" if segments else 'No data',
            'segments': clean_segments,
            'gaps': gaps,
            'total_coverage_minutes': round(total_minutes, 1),
            'coverage_percentage': round(coverage_percentage, 1),
            'has_gaps': len(gaps) > 0,
            'gap_count': len(gaps),
            'continuity': 'Continuous' if not gaps else f'{len(gaps)} gap(s) detected',
        }

    def calculate_coverage_metrics(self):
        """Calculate and store coverage metrics from all videos in this group."""
        videos = self.videos.filter(processing_status='completed').order_by('video_start_time')

        if not videos.exists():
            self.total_coverage_minutes = 0
            self.coverage_gaps = []
            self.coverage_continuity_score = 0
            self.coverage_segments = []
            self.save(update_fields=[
                'total_coverage_minutes', 'coverage_gaps',
                'coverage_continuity_score', 'coverage_segments',
            ])
            return {'total_coverage_minutes': 0, 'coverage_gaps': [], 'continuity_score': 0, 'segments': []}

        def time_to_minutes(t):
            return t.hour * 60 + t.minute

        def minutes_to_time_str(minutes):
            minutes = minutes % (24 * 60)
            return f"{minutes // 60:02d}:{minutes % 60:02d}"

        segments = []
        for video in videos:
            if video.video_start_time and video.video_end_time:
                start_minutes = time_to_minutes(video.video_start_time)
                end_minutes = time_to_minutes(video.video_end_time)
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                segments.append({
                    'start': video.video_start_time.strftime('%H:%M'),
                    'end': video.video_end_time.strftime('%H:%M'),
                    'start_minutes': start_minutes,
                    'end_minutes': end_minutes,
                    'duration': end_minutes - start_minutes,
                    'video_id': str(video.id),
                    'filename': video.filename,
                })

        segments.sort(key=lambda x: x['start_minutes'])
        total_minutes = sum(s['duration'] for s in segments)

        gaps = []
        for i in range(len(segments) - 1):
            gap_minutes = segments[i + 1]['start_minutes'] - segments[i]['end_minutes']
            if gap_minutes > 1:
                gaps.append({
                    'start': minutes_to_time_str(segments[i]['end_minutes']),
                    'end': minutes_to_time_str(segments[i + 1]['start_minutes']),
                    'duration_minutes': gap_minutes,
                    'between': f"{segments[i]['filename']} and {segments[i + 1]['filename']}",
                })

        if segments:
            total_span = segments[-1]['end_minutes'] - segments[0]['start_minutes']
            continuity_score = (
                ((total_span - sum(g['duration_minutes'] for g in gaps)) / total_span * 100)
                if total_span > 0 else 100
            )
        else:
            continuity_score = 0

        clean_segments = [
            {'start': s['start'], 'end': s['end'], 'duration': s['duration'],
             'video_id': s['video_id'], 'filename': s['filename']}
            for s in segments
        ]

        self.total_coverage_minutes = total_minutes
        self.coverage_gaps = gaps
        self.coverage_continuity_score = round(continuity_score, 1)
        self.coverage_segments = clean_segments
        self.save(update_fields=[
            'total_coverage_minutes', 'coverage_gaps',
            'coverage_continuity_score', 'coverage_segments',
        ])

        return {
            'total_coverage_minutes': total_minutes,
            'coverage_gaps': gaps,
            'continuity_score': round(continuity_score, 1),
            'segments': clean_segments,
        }

    # FIX #9: Replace O(n) Python sum with a single DB aggregation query.
    # Old get_total_vehicles() / get_directional_count() did two separate
    # queryset iterations in Python.  This single method does one SQL query.
    def get_aggregated_stats(self):
        """Return total_vehicles and directional_count in a single DB query."""
        from django.db.models import Sum
        result = TrafficAnalysis.objects.filter(
            video_file__location_date_group=self
        ).aggregate(
            total_vehicles=Sum('total_vehicles'),
            directional_count=Sum('directional_count'),
        )
        return {
            'total_vehicles': result['total_vehicles'] or 0,
            'directional_count': result['directional_count'] or 0,
        }

    # Keep these as thin wrappers so existing call-sites don't break.
    def get_total_vehicles(self):
        return self.get_aggregated_stats()['total_vehicles']

    def get_directional_count(self):
        return self.get_aggregated_stats()['directional_count']

    def update_statistics(self):
        from django.db.models import Sum, Max
        agg = TrafficAnalysis.objects.filter(
            video_file__location_date_group=self
        ).aggregate(
            total_dir=Sum('directional_count'),
            total_dur=Sum('duration_seconds'),
            peak=Max('peak_directional_flow'),
        )

        self.total_directional_count = agg['total_dir'] or 0
        total_duration = agg['total_dur'] or 0
        if total_duration > 0:
            self.average_directional_flow = (self.total_directional_count / total_duration) * 3600
        self.peak_directional_flow = agg['peak'] or 0
        self.calculate_coverage_metrics()
        self.save()

    def calculate_hourly_distribution(self):
        analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=self)
        hourly_data = {hour: {'vehicles': 0, 'videos': 0, 'minutes': 0} for hour in range(24)}

        for analysis in analyses:
            video = analysis.video_file
            if video.video_start_time and video.video_end_time:
                start_minutes = video.video_start_time.hour * 60 + video.video_start_time.minute
                end_minutes = video.video_end_time.hour * 60 + video.video_end_time.minute
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                duration = end_minutes - start_minutes
                if duration > 0:
                    vehicles_per_minute = analysis.total_vehicles / duration
                    current_minute = start_minutes
                    while current_minute < end_minutes:
                        hour = (current_minute // 60) % 24
                        hour_end = ((hour + 1) * 60) % (24 * 60)
                        if hour_end < hour * 60:
                            hour_end += 24 * 60
                        minutes_in_hour = min(hour_end, end_minutes) - current_minute
                        if minutes_in_hour > 0:
                            hourly_data[hour]['vehicles'] += vehicles_per_minute * minutes_in_hour
                            hourly_data[hour]['minutes'] += minutes_in_hour
                            hourly_data[hour]['videos'] += 1
                        current_minute += minutes_in_hour

        for hour in hourly_data:
            hourly_data[hour]['vehicles'] = round(hourly_data[hour]['vehicles'])

        self.hourly_distribution = hourly_data
        self.save(update_fields=['hourly_distribution'])
        return hourly_data

    def get_coverage_summary(self):
        if self.total_coverage_minutes == 0:
            return {
                'text': "No coverage data",
                'hours': 0, 'minutes': 0,
                'gap_count': 0, 'continuity_score': 0, 'has_gaps': False,
            }

        hours = int(self.total_coverage_minutes // 60)
        minutes = int(self.total_coverage_minutes % 60)
        gap_count = len(self.coverage_gaps) if self.coverage_gaps else 0
        gap_summary = f", {gap_count} gap(s) detected" if gap_count > 0 else ", seamless coverage"

        return {
            'text': f"{hours}h {minutes}m total coverage{gap_summary} ({self.coverage_continuity_score:.1f}% continuous)",
            'hours': hours, 'minutes': minutes,
            'gap_count': gap_count,
            'continuity_score': self.coverage_continuity_score,
            'has_gaps': gap_count > 0,
        }


class VideoFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='videos/', null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    video_date = models.DateField(null=True, blank=True)
    video_start_time = models.TimeField(null=True, blank=True)
    video_end_time = models.TimeField(null=True, blank=True)
    original_duration = models.FloatField(null=True, blank=True)

    location_date_group = models.ForeignKey(
        LocationDateGroup,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='videos',
    )

    processed = models.BooleanField(default=False)
    processed_video_path = models.FileField(upload_to='processed_videos/', null=True, blank=True)
    processing_status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('uploaded', 'Uploaded'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
    )

    processing_progress = models.IntegerField(default=0)
    processing_message = models.CharField(max_length=255, default='Waiting to start...')
    last_progress_update = models.DateTimeField(auto_now=True)

    duration_seconds = models.FloatField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    total_frames = models.IntegerField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    resolution = models.CharField(max_length=20, null=True, blank=True)

    processing_profile = models.ForeignKey(
        ProcessingProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['processing_status']),
            models.Index(fields=['location_date_group', 'video_date']),
            models.Index(fields=['processing_status', 'processing_progress']),
            models.Index(fields=['processing_profile']),
        ]

    def __str__(self):
        return f"{self.filename} - {self.video_date if self.video_date else 'Unknown Date'}"

    def get_video_time_range(self):
        if self.video_start_time and self.video_end_time:
            return f"{self.video_start_time.strftime('%H:%M')} - {self.video_end_time.strftime('%H:%M')}"
        return "Time unknown"

    def update_progress(self, progress, message):
        self.processing_progress = max(0, min(100, progress))
        self.processing_message = message
        self.save(update_fields=['processing_progress', 'processing_message', 'last_progress_update'])
        return self

    def get_processing_profile_info(self):
        if self.processing_profile:
            return {
                'name': self.processing_profile.display_name,
                'detector_type': self.processing_profile.get_detector_type_display(),
                'congestion_detection': self.processing_profile.enable_congestion_detection,
            }
        return None


class TrafficAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.OneToOneField(
        VideoFile,
        on_delete=models.CASCADE,
        related_name='traffic_analysis',
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)

    total_vehicles = models.IntegerField(default=0)
    processing_time_seconds = models.FloatField(default=0)
    analyzed_at = models.DateTimeField(default=timezone.now)

    # Vehicle type counts
    # Note: bus_count stores 'jeep', bicycle_count stores 'tricycle' for custom model
    car_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    motorcycle_count = models.IntegerField(default=0)
    bus_count = models.IntegerField(default=0)
    bicycle_count = models.IntegerField(default=0)
    other_count = models.IntegerField(default=0)

    # Directional counting
    directional_count = models.IntegerField(default=0)
    directional_vehicles_per_minute = models.FloatField(default=0.0)
    peak_directional_flow = models.IntegerField(default=0)

    # Congestion detection
    congestion_events_count = models.IntegerField(default=0)
    total_congestion_time = models.FloatField(default=0.0)
    congestion_percentage = models.FloatField(default=0.0)
    congestion_none_time = models.FloatField(default=0.0)
    congestion_light_time = models.FloatField(default=0.0)
    congestion_moderate_time = models.FloatField(default=0.0)
    congestion_heavy_time = models.FloatField(default=0.0)
    congestion_severe_time = models.FloatField(default=0.0)

    # Video properties
    duration_seconds = models.FloatField(default=0.0)
    fps = models.FloatField(default=0.0)
    total_frames = models.IntegerField(default=0)

    # Traffic metrics
    peak_traffic = models.IntegerField(default=0)
    average_traffic = models.FloatField(default=0)
    congestion_level = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'), ('very_low', 'Very Low'), ('low', 'Low'),
            ('medium', 'Medium'), ('high', 'High'), ('severe', 'Severe'),
        ],
        default='none',
    )
    traffic_pattern = models.CharField(
        max_length=20,
        choices=[
            ('increasing', 'Increasing'), ('decreasing', 'Decreasing'),
            ('stable', 'Stable'), ('fluctuating', 'Fluctuating'),
        ],
        default='stable',
    )

    analysis_data = models.JSONField(default=dict)
    metrics_summary = models.JSONField(default=dict)
    frame_data = models.JSONField(default=list, blank=True)
    congestion_events = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Traffic Analysis"
        verbose_name_plural = "Traffic Analyses"
        ordering = ['-analyzed_at']
        indexes = [
            models.Index(fields=['location', 'analyzed_at']),
            models.Index(fields=['video_file']),
            models.Index(fields=['congestion_level']),
            models.Index(fields=['directional_count']),
        ]

    def __str__(self):
        model_info = self.get_model_info()
        direction = self.get_direction_info()
        return f"{self.video_file.filename} - {self.directional_count} vehicles {direction} ({model_info['model_name']})"

    def get_vehicle_breakdown(self):
        return {
            'car': self.car_count,
            'truck': self.truck_count,
            'motorcycle': self.motorcycle_count,
            'jeep': self.bus_count,
            'tricycle': self.bicycle_count,
            'other': self.other_count,
            'total': self.total_vehicles,
            'directional_total': self.directional_count,
        }

    def get_direction_info(self):
        metrics = self.metrics_summary or {}
        return metrics.get('counting_direction', 'Unknown direction')

    def get_congestion_summary(self):
        return {
            'total_events': self.congestion_events_count,
            'total_time': self.total_congestion_time,
            'percentage': self.congestion_percentage,
            'level_breakdown': {
                'none': self.congestion_none_time,
                'light': self.congestion_light_time,
                'moderate': self.congestion_moderate_time,
                'heavy': self.congestion_heavy_time,
                'severe': self.congestion_severe_time,
            },
            'dominant_level': self.congestion_level,
        }

    def get_analysis_type(self):
        metrics = self.metrics_summary or {}
        detector_type = metrics.get('detector_type', '')
        if 'directional' in detector_type.lower():
            return 'directional'
        elif 'congestion' in detector_type.lower():
            return 'congestion'
        return 'standard'

    def get_model_info(self):
        metrics = self.metrics_summary or {}
        return {
            'model_name': metrics.get('model_used', 'Unknown'),
            'model_architecture': metrics.get('model_architecture', 'Unknown'),
            'detector_type': metrics.get('detector_type', 'Unknown'),
            'counting_direction': metrics.get('counting_direction', 'Unknown'),
            'congestion_enabled': metrics.get('congestion_enabled', False),
            'tracked_classes': metrics.get('tracked_classes', []),
            'is_directional': 'directional' in metrics.get('detector_type', '').lower(),
            'is_congestion': 'congestion' in metrics.get('detector_type', '').lower(),
        }


class DirectionalAnalysis(models.Model):
    """Detailed directional analysis data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traffic_analysis = models.ForeignKey(
        TrafficAnalysis,
        on_delete=models.CASCADE,
        related_name='directional_analyses',
    )

    direction_name = models.CharField(max_length=50)
    direction_angle = models.IntegerField(default=0)

    line_start_x = models.FloatField(default=0.0)
    line_start_y = models.FloatField(default=0.0)
    line_end_x = models.FloatField(default=0.0)
    line_end_y = models.FloatField(default=0.0)

    directional_car_count = models.IntegerField(default=0)
    directional_truck_count = models.IntegerField(default=0)
    directional_motorcycle_count = models.IntegerField(default=0)
    directional_bus_count = models.IntegerField(default=0)
    directional_bicycle_count = models.IntegerField(default=0)

    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Directional Analysis"
        verbose_name_plural = "Directional Analyses"
        ordering = ['-analyzed_at']

    def __str__(self):
        return f"{self.direction_name} - {self.get_total_count()} vehicles"

    def get_total_count(self):
        return (
            self.directional_car_count + self.directional_truck_count +
            self.directional_motorcycle_count + self.directional_bus_count +
            self.directional_bicycle_count
        )


class CongestionEvent(models.Model):
    """Detailed congestion event data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traffic_analysis = models.ForeignKey(
        TrafficAnalysis,
        on_delete=models.CASCADE,
        related_name='detailed_congestion_events',
    )

    start_frame = models.IntegerField()
    end_frame = models.IntegerField()
    start_time_seconds = models.FloatField()
    end_time_seconds = models.FloatField()
    duration_seconds = models.FloatField()

    level = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light'), ('moderate', 'Moderate'),
            ('heavy', 'Heavy'), ('severe', 'Severe'),
        ],
    )

    peak_vehicles = models.IntegerField(default=0)
    average_vehicles = models.FloatField(default=0.0)
    stationary_vehicles = models.IntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Congestion Event"
        verbose_name_plural = "Congestion Events"
        ordering = ['start_time_seconds']

    def __str__(self):
        return f"{self.level.capitalize()} congestion: {self.duration_seconds:.1f}s"


class VehicleType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.name.capitalize()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name

    class Meta:
        ordering = ['display_name']


class Detection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.ForeignKey(VideoFile, on_delete=models.CASCADE, related_name='detections')
    traffic_analysis = models.ForeignKey(
        TrafficAnalysis,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='detections',
    )
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField()
    frame_number = models.IntegerField()
    confidence = models.FloatField()
    bbox_x = models.FloatField()
    bbox_y = models.FloatField()
    bbox_width = models.FloatField()
    bbox_height = models.FloatField()
    track_id = models.IntegerField(null=True, blank=True)

    in_counting_zone = models.BooleanField(default=True)
    counted_directionally = models.BooleanField(default=False)
    direction_valid = models.BooleanField(default=False)

    speed_estimate = models.FloatField(null=True, blank=True)
    direction = models.CharField(
        max_length=10,
        choices=[
            ('incoming', 'Incoming'),
            ('outgoing', 'Outgoing'),
            ('stationary', 'Stationary'),
        ],
        null=True, blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['vehicle_type', 'timestamp']),
            models.Index(fields=['location', 'timestamp']),
            models.Index(fields=['traffic_analysis', 'frame_number']),
            models.Index(fields=['video_file', 'frame_number']),
            models.Index(fields=['counted_directionally']),
        ]
        ordering = ['timestamp', 'frame_number']

    def __str__(self):
        direction_marker = "✓" if self.counted_directionally else "✗"
        return f"{direction_marker} {self.vehicle_type.name} at frame {self.frame_number}"


class FrameAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traffic_analysis = models.ForeignKey(
        TrafficAnalysis, on_delete=models.CASCADE, related_name='frame_analyses'
    )
    frame_number = models.IntegerField()
    timestamp_seconds = models.FloatField()

    car_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    motorcycle_count = models.IntegerField(default=0)
    bus_count = models.IntegerField(default=0)
    bicycle_count = models.IntegerField(default=0)
    total_vehicles = models.IntegerField(default=0)
    directional_count = models.IntegerField(default=0)
    congestion_level = models.CharField(max_length=20, default='none')
    stationary_vehicles = models.IntegerField(default=0)
    detection_data = models.JSONField(default=dict)

    class Meta:
        unique_together = ['traffic_analysis', 'frame_number']
        indexes = [
            models.Index(fields=['traffic_analysis', 'timestamp_seconds']),
            models.Index(fields=['traffic_analysis', 'congestion_level']),
        ]
        ordering = ['frame_number']

    def __str__(self):
        return f"Frame {self.frame_number} - {self.total_vehicles} vehicles ({self.directional_count} directional)"


class TrafficReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traffic_analysis = models.ForeignKey(
        TrafficAnalysis, on_delete=models.CASCADE, related_name='reports'
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)

    REPORT_TYPES = [
        ('quick', 'Quick Summary'),
        ('detailed', 'Detailed Analysis'),
        ('predictive', 'Predictive Report'),
        ('comparative', 'Comparative Report'),
        ('directional', 'Directional Analysis Report'),
        ('congestion', 'Congestion Analysis Report'),
    ]
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default='detailed')

    title = models.CharField(max_length=200)
    executive_summary = models.TextField(blank=True)
    key_findings = models.JSONField(default=dict)
    insights = models.TextField(blank=True)
    predictions = models.JSONField(default=dict)
    recommendations = models.TextField(blank=True)
    directional_analysis = models.JSONField(default=dict, blank=True)
    congestion_analysis = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['generated_at']),
            models.Index(fields=['location', 'generated_at']),
        ]
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.title} - {self.report_type}"


class HourlyTrafficSummary(models.Model):
    date = models.DateField()
    hour = models.IntegerField()
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    count = models.IntegerField()
    directional_count = models.IntegerField(default=0)
    average_confidence = models.FloatField(default=0)
    peak_5min_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['date', 'hour', 'vehicle_type', 'location']
        indexes = [
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['location', 'date', 'hour']),
        ]
        ordering = ['date', 'hour']

    def __str__(self):
        return f"{self.date} {self.hour:02d}:00 - {self.vehicle_type}: {self.count} ({self.directional_count} directional)"


class DailyTrafficSummary(models.Model):
    date = models.DateField()
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    total_count = models.IntegerField()
    directional_total = models.IntegerField(default=0)
    peak_hour = models.IntegerField()
    peak_hour_count = models.IntegerField()
    average_daily_congestion = models.CharField(max_length=20, default='none')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['date', 'vehicle_type', 'location']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['location', 'date']),
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} - {self.vehicle_type}: {self.total_count} ({self.directional_total} directional)"


class TrafficPrediction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    prediction_date = models.DateField()
    day_of_week = models.IntegerField()
    hour_of_day = models.IntegerField()

    predicted_vehicle_count = models.FloatField(default=0.0)
    predicted_directional_count = models.FloatField(default=0.0)
    predicted_congestion = models.CharField(max_length=20, default='none')
    confidence_score = models.FloatField(default=0.0)
    confidence_interval_lower = models.FloatField(default=0.0)
    confidence_interval_upper = models.FloatField(default=0.0)

    model_version = models.CharField(max_length=50, default="v1.0")
    prediction_generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['location', 'prediction_date', 'hour_of_day']
        indexes = [
            models.Index(fields=['prediction_date', 'hour_of_day']),
            models.Index(fields=['location', 'prediction_date']),
        ]
        ordering = ['prediction_date', 'hour_of_day']

    def __str__(self):
        location_str = self.location.display_name if self.location else "General"
        return f"{location_str} - {self.prediction_date} {self.hour_of_day:02d}:00 → {self.predicted_congestion}"


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

    class Meta:
        ordering = ['key']


# ============================================================
# SIGNAL HANDLERS
# ============================================================

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=TrafficAnalysis)
def update_video_file_status(sender, instance, created, **kwargs):
    """
    Update VideoFile status when a new analysis is created.
    Only fires on creation; avoids overwriting status mid-task.
    """
    if not created:
        return
    if not instance.video_file:
        return

    video = instance.video_file
    if video.processing_status == 'completed' and video.processed:
        return

    video.processing_status = 'completed'
    video.processed = True
    video.processed_at = timezone.now()
    video.save(update_fields=['processing_status', 'processed', 'processed_at'])


@receiver(post_save, sender=Detection)
def update_traffic_analysis_counts(sender, instance, created, **kwargs):
    """
    FIX #8: Use F() expressions instead of COUNT(*) queries on every Detection save.
    Old code fired a full COUNT(*) query per Detection insert — O(n) total queries
    for n detections.  F() expressions issue a single atomic UPDATE instead.
    """
    if not created or not instance.traffic_analysis:
        return

    from django.db.models import F

    analysis = instance.traffic_analysis

    # Build the incremental update dict
    update_kwargs = {}

    if instance.counted_directionally:
        update_kwargs['directional_count'] = F('directional_count') + 1

    vehicle_type_name = instance.vehicle_type.name.lower()
    count_field_map = {
        'car': 'car_count',
        'truck': 'truck_count',
        'motorcycle': 'motorcycle_count',
        'bus': 'bus_count',
        'bicycle': 'bicycle_count',
        'other': 'other_count',
    }

    if vehicle_type_name in count_field_map:
        field = count_field_map[vehicle_type_name]
        update_kwargs[field] = F(field) + 1
        update_kwargs['total_vehicles'] = F('total_vehicles') + 1

    if update_kwargs:
        TrafficAnalysis.objects.filter(pk=analysis.pk).update(**update_kwargs)


@receiver(post_save, sender=TrafficAnalysis)
def auto_group_video_after_analysis(sender, instance, created, **kwargs):
    """
    Auto-group video after analysis is created.
    Safety net only — the Celery task handles grouping explicitly.
    Uses select_for_update() to prevent race conditions.
    """
    if not created:
        return
    if not instance.video_file or not instance.location:
        logger.warning(
            f"❌ Cannot auto-group: missing required fields "
            f"(video={bool(instance.video_file)}, location={bool(instance.location)})"
        )
        return

    try:
        from django.db import transaction

        with transaction.atomic():
            video = VideoFile.objects.select_for_update().get(pk=instance.video_file.pk)

            if video.location_date_group_id and video.processing_status == 'completed':
                logger.info(
                    f"ℹ️ Video {video.id} already grouped and completed – skipping signal."
                )
                return

            location = instance.location

            if video.video_date:
                group_date = video.video_date
                date_source = "video_date"
            elif instance.analyzed_at:
                group_date = instance.analyzed_at.date()
                date_source = "analysis_date"
            else:
                logger.warning(f"❌ Cannot group: no date available for video {video.id}")
                return

            group, group_created = LocationDateGroup.objects.get_or_create(
                location=location,
                date=group_date,
            )

            video.location_date_group = group
            save_fields = ['location_date_group']

            if date_source == "analysis_date" and not video.video_date:
                video.video_date = group_date
                save_fields.append('video_date')

            video.save(update_fields=save_fields)
            logger.info(f"✅ Signal: video {video.id} assigned to group {group.id} (created={group_created})")

    except Exception as e:
        logger.error(
            f"❌ Failed to auto-group video "
            f"{getattr(instance.video_file, 'id', 'unknown')}: {e}"
        )
        import traceback
        traceback.print_exc()