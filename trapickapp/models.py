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
    
    # Just the detector type - no complex configuration
    DETECTOR_TYPES = [
        ('vertical_top_bottom', 'Vertical Top→Bottom'),
        ('vertical_bottom_top', 'Vertical Bottom→Top'),
        ('horizontal_left_right', 'Horizontal Left→Right'),
        ('horizontal_right_left', 'Horizontal Right→Left'),
        ('diagonal_ne_sw', 'Diagonal NE→SW'),
        ('diagonal_nw_se', 'Diagonal NW→SE'),
        ('diagonal_se_nw', 'Diagonal SE→NW'),
        ('diagonal_sw_ne', 'Diagonal SW→NE'),
        ('congestion_time', 'Congestion Time Detector'),
        ('baliwasan_yjunction', 'Baliwasan Y-Junction'),
    ]
    
    detector_type = models.CharField(
        max_length=50,
        choices=DETECTOR_TYPES,
        default='vertical_top_bottom',
        help_text="Type of detector to use"
    )
    
    # Simple congestion settings
    enable_congestion_detection = models.BooleanField(default=True)
    congestion_threshold = models.IntegerField(default=5)
    
    # Road type for organization
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
    
    # ✅ ADD THIS FIELD - CONFIGURATION PARAMETERS
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
        """Get detector instance - simple approach"""
        from ml.directional_detectors import get_detector
        
        try:
            # Get the detector
            detector = get_detector(self.detector_type)
            
            # Apply simple congestion settings if supported
            if hasattr(detector, 'enable_congestion_detection'):
                detector.enable_congestion_detection = self.enable_congestion_detection
            
            if hasattr(detector, 'congestion_threshold'):
                detector.congestion_threshold = self.congestion_threshold
            
            # ✅ APPLY CONFIGURATION PARAMETERS IF AVAILABLE
            if self.config_parameters:
                for key, value in self.config_parameters.items():
                    if hasattr(detector, key):
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
    
    # Updated to support directional detectors
    processing_profile = models.ForeignKey(
        ProcessingProfile,
        on_delete=models.PROTECT,
        related_name='locations',
        help_text="Processing profile with directional settings"
    )
    
    # Directional counting configuration for this location
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
        """Get counting direction for this location"""
        profile = self.processing_profile
        if profile.detector_type in ['vertical_top_bottom', 'vertical_bottom_top', 
                                    'horizontal_left_right', 'horizontal_right_left',
                                    'diagonal_ne_sw', 'diagonal_nw_se', 
                                    'diagonal_se_nw', 'diagonal_sw_ne']:
            return profile.get_detector_type_display()
        return "Unknown"


class LocationDateGroup(models.Model):
    """Groups processed videos by location and date"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='date_groups')
    date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Directional statistics
    total_directional_count = models.IntegerField(default=0, help_text="Total vehicles counted in specific direction")
    average_directional_flow = models.FloatField(default=0.0, help_text="Average vehicles per hour in counting direction")
    peak_directional_flow = models.IntegerField(default=0, help_text="Peak vehicles in counting direction")
    
    class Meta:
        unique_together = ['location', 'date']
        ordering = ['-date', 'location__display_name']
        verbose_name = "Location Date Group"
        verbose_name_plural = "Location Date Groups"

    def __str__(self):
        return f"{self.location.display_name} - {self.date}"

    def get_videos_by_time(self):
        """Get videos sorted by time"""
        return self.videos.all().order_by('video_start_time')

    # ✅ ADD THIS METHOD - IT'S MISSING!
    def get_time_range(self):
        """
        Calculate time range for videos in this group.
        Returns a formatted string showing start time to end time.
        """
        videos = self.videos.filter(processing_status='completed').order_by('video_start_time')
        
        if not videos.exists():
            return "No time data"
        
        # Get earliest start time and latest end time
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
        
        # Format as "HH:MM - HH:MM"
        return f"{earliest.strftime('%H:%M')} - {latest.strftime('%H:%M')}"

    def get_total_vehicles(self):
        """Calculate total vehicles in this group"""
        analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=self)
        return sum(analysis.total_vehicles for analysis in analyses) if analyses else 0

    def get_directional_count(self):
        """Get vehicles counted in specific direction"""
        analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=self)
        return sum(analysis.directional_count for analysis in analyses) if analyses else 0

    def update_statistics(self):
        """Update directional statistics for this group"""
        analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=self)
        
        if analyses:
            self.total_directional_count = sum(a.directional_count for a in analyses)
            
            # Calculate average flow (vehicles per hour)
            total_duration = sum(a.duration_seconds for a in analyses if a.duration_seconds)
            if total_duration > 0:
                self.average_directional_flow = (self.total_directional_count / total_duration) * 3600
            
            self.peak_directional_flow = max((a.peak_directional_flow for a in analyses), default=0)
            self.save()


class VideoFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='videos/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    # VIDEO METADATA FIELDS
    video_date = models.DateField(null=True, blank=True, help_text="Date when video was recorded")
    video_start_time = models.TimeField(null=True, blank=True, help_text="Start time of video recording")
    video_end_time = models.TimeField(null=True, blank=True, help_text="End time of video recording")
    original_duration = models.FloatField(null=True, blank=True, help_text="Original video duration in seconds")

    # LINK TO LOCATION DATE GROUP
    location_date_group = models.ForeignKey(
        LocationDateGroup, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='videos'
    )

    # PROCESSING STATUS FIELDS
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
        default='pending'
    )
    
    # PROGRESS TRACKING FIELDS
    processing_progress = models.IntegerField(default=0, help_text="Processing progress percentage (0-100)")
    processing_message = models.CharField(max_length=255, default='Waiting to start...', help_text="Current processing status message")
    last_progress_update = models.DateTimeField(auto_now=True, help_text="Last time progress was updated")
    
    # Video properties
    duration_seconds = models.FloatField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    total_frames = models.IntegerField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    resolution = models.CharField(max_length=20, null=True, blank=True)
    
    # Directional processing info
    processing_profile = models.ForeignKey(
        ProcessingProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Processing profile used for this video"
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
        """Update processing progress and message"""
        self.processing_progress = max(0, min(100, progress))
        self.processing_message = message
        self.save(update_fields=['processing_progress', 'processing_message', 'last_progress_update'])
        return self
    
    def get_processing_profile_info(self):
        """Get processing profile information"""
        if self.processing_profile:
            return {
                'name': self.processing_profile.display_name,
                'detector_type': self.processing_profile.get_detector_type_display(),
                'direction': self.processing_profile.get_direction_info(),
                'congestion_detection': self.processing_profile.enable_congestion_detection,
            }
        return None


class TrafficAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.OneToOneField(
        VideoFile, 
        on_delete=models.CASCADE, 
        related_name='traffic_analysis'
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    
    # VEHICLE COUNTS - KEEP EXISTING FOR COMPATIBILITY
    total_vehicles = models.IntegerField(default=0)
    processing_time_seconds = models.FloatField(default=0)
    analyzed_at = models.DateTimeField(default=timezone.now)
    
    # VEHICLE TYPE COUNTS
    car_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    motorcycle_count = models.IntegerField(default=0)
    bus_count = models.IntegerField(default=0)
    bicycle_count = models.IntegerField(default=0)
    other_count = models.IntegerField(default=0)
    
    # DIRECTIONAL COUNTING RESULTS - NEW FIELDS
    directional_count = models.IntegerField(default=0, help_text="Vehicles counted in specific direction")
    directional_vehicles_per_minute = models.FloatField(default=0.0, help_text="Vehicles per minute in counting direction")
    peak_directional_flow = models.IntegerField(default=0, help_text="Peak directional flow in 5-minute window")
    
    # CONGESTION DETECTION RESULTS - NEW FIELDS
    congestion_events_count = models.IntegerField(default=0, help_text="Number of congestion events detected")
    total_congestion_time = models.FloatField(default=0.0, help_text="Total congestion time in seconds")
    congestion_percentage = models.FloatField(default=0.0, help_text="Percentage of video with congestion")
    
    # Congestion levels breakdown
    congestion_none_time = models.FloatField(default=0.0, help_text="Time with no congestion")
    congestion_light_time = models.FloatField(default=0.0, help_text="Time with light congestion")
    congestion_moderate_time = models.FloatField(default=0.0, help_text="Time with moderate congestion")
    congestion_heavy_time = models.FloatField(default=0.0, help_text="Time with heavy congestion")
    congestion_severe_time = models.FloatField(default=0.0, help_text="Time with severe congestion")
    
    # Video properties
    duration_seconds = models.FloatField(default=0.0, help_text="Video duration in seconds")
    fps = models.FloatField(default=0.0, help_text="Video frames per second")
    total_frames = models.IntegerField(default=0, help_text="Total frames processed")
    
    # TRAFFIC METRICS
    peak_traffic = models.IntegerField(default=0)
    average_traffic = models.FloatField(default=0)
    congestion_level = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('very_low', 'Very Low'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('severe', 'Severe')
        ],
        default='none'
    )
    
    traffic_pattern = models.CharField(
        max_length=20,
        choices=[
            ('increasing', 'Increasing'),
            ('decreasing', 'Decreasing'),
            ('stable', 'Stable'),
            ('fluctuating', 'Fluctuating')
        ],
        default='stable'
    )
    
    # ANALYSIS DATA
    analysis_data = models.JSONField(default=dict)
    metrics_summary = models.JSONField(default=dict)
    frame_data = models.JSONField(
        default=list,
        blank=True,
        help_text="Per-frame data for dashboard visualization"
    )
    congestion_events = models.JSONField(
        default=list,
        blank=True,
        help_text="Detailed congestion events data"
    )

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
        model_name = model_info['model_name']
        direction = self.get_direction_info()
        return f"{self.video_file.filename} - {self.directional_count} vehicles {direction} ({model_name})"

    def get_vehicle_breakdown(self):
        """
        Get vehicle breakdown with directional detector support
        """
        metrics = self.metrics_summary or {}
        detector_type = metrics.get('detector_type', '')
        
        if 'directional' in detector_type.lower() or 'congestion' in detector_type.lower():
            # Directional detector breakdown
            return {
                'car': self.car_count,
                'truck': self.truck_count,
                'motorcycle': self.motorcycle_count,
                'bus': self.bus_count,
                'bicycle': self.bicycle_count,
                'other': self.other_count,
                'total': self.total_vehicles,
                'directional_total': self.directional_count,
            }
        else:
            # Legacy model breakdown
            return {
                'cars': self.car_count,
                'trucks': self.truck_count,
                'motorcycles': self.motorcycle_count,
                'buses': self.bus_count,
                'bicycles': self.bicycle_count,
                'others': self.other_count,
                'total': self.total_vehicles,
            }
    
    def get_direction_info(self):
        """Get counting direction information"""
        metrics = self.metrics_summary or {}
        return metrics.get('counting_direction', 'Unknown direction')
    
    def get_congestion_summary(self):
        """Get congestion summary"""
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
        """Get analysis type (directional/congestion)"""
        metrics = self.metrics_summary or {}
        detector_type = metrics.get('detector_type', '')
        
        if 'directional' in detector_type.lower():
            return 'directional'
        elif 'congestion' in detector_type.lower():
            return 'congestion'
        else:
            return 'standard'
    
    def get_model_info(self):
        """Get information about which model was used"""
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
        related_name='directional_analyses'
    )
    
    # Direction information
    direction_name = models.CharField(max_length=50, help_text="Name of counting direction")
    direction_angle = models.IntegerField(default=0, help_text="Counting angle in degrees")
    
    # Counting line information
    line_start_x = models.FloatField(default=0.0)
    line_start_y = models.FloatField(default=0.0)
    line_end_x = models.FloatField(default=0.0)
    line_end_y = models.FloatField(default=0.0)
    
    # Vehicle counts by type in this direction
    directional_car_count = models.IntegerField(default=0)
    directional_truck_count = models.IntegerField(default=0)
    directional_motorcycle_count = models.IntegerField(default=0)
    directional_bus_count = models.IntegerField(default=0)
    directional_bicycle_count = models.IntegerField(default=0)
    
    # Temporal data
    analyzed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Directional Analysis"
        verbose_name_plural = "Directional Analyses"
        ordering = ['-analyzed_at']
    
    def __str__(self):
        return f"{self.direction_name} - {self.get_total_count()} vehicles"

    def get_total_count(self):
        """Get total directional count"""
        return (
            self.directional_car_count + 
            self.directional_truck_count + 
            self.directional_motorcycle_count + 
            self.directional_bus_count + 
            self.directional_bicycle_count
        )


class CongestionEvent(models.Model):
    """Detailed congestion event data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traffic_analysis = models.ForeignKey(
        TrafficAnalysis, 
        on_delete=models.CASCADE, 
        related_name='detailed_congestion_events'
    )
    
    # Event timing
    start_frame = models.IntegerField()
    end_frame = models.IntegerField()
    start_time_seconds = models.FloatField()
    end_time_seconds = models.FloatField()
    duration_seconds = models.FloatField()
    
    # Congestion details
    level = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light'),
            ('moderate', 'Moderate'),
            ('heavy', 'Heavy'),
            ('severe', 'Severe')
        ]
    )
    
    # Vehicle counts during congestion
    peak_vehicles = models.IntegerField(default=0)
    average_vehicles = models.FloatField(default=0.0)
    stationary_vehicles = models.IntegerField(default=0)
    
    # Additional data
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Congestion Event"
        verbose_name_plural = "Congestion Events"
        ordering = ['start_time_seconds']
    
    def __str__(self):
        return f"{self.level.capitalize()} congestion: {self.duration_seconds:.1f}s"


# Keep the existing models below, they should work with the new system
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
        null=True, 
        blank=True, 
        related_name='detections'
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
    
    # Directional fields
    in_counting_zone = models.BooleanField(default=True)
    counted_directionally = models.BooleanField(default=False, help_text="Whether vehicle was counted in specific direction")
    direction_valid = models.BooleanField(default=False, help_text="Whether vehicle was moving in valid direction")
    
    speed_estimate = models.FloatField(null=True, blank=True)
    direction = models.CharField(
        max_length=10,
        choices=[
            ('incoming', 'Incoming'),
            ('outgoing', 'Outgoing'),
            ('stationary', 'Stationary')
        ],
        null=True,
        blank=True
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
    traffic_analysis = models.ForeignKey(TrafficAnalysis, on_delete=models.CASCADE, related_name='frame_analyses')
    frame_number = models.IntegerField()
    timestamp_seconds = models.FloatField()
    
    # Vehicle counts
    car_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    motorcycle_count = models.IntegerField(default=0)
    bus_count = models.IntegerField(default=0)
    bicycle_count = models.IntegerField(default=0)
    total_vehicles = models.IntegerField(default=0)
    
    # Directional counts
    directional_count = models.IntegerField(default=0, help_text="Vehicles counted in specific direction this frame")
    
    # Congestion data
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


# Keep existing models below (unchanged except for minor updates)
class TrafficReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traffic_analysis = models.ForeignKey(TrafficAnalysis, on_delete=models.CASCADE, related_name='reports')
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
    
    # Directional data
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
    
    # Directional counts
    directional_count = models.IntegerField(default=0, help_text="Vehicles counted in specific direction")
    
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
    
    # Directional totals
    directional_total = models.IntegerField(default=0, help_text="Total directional count for the day")
    
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
    
    # Directional predictions
    predicted_directional_count = models.FloatField(default=0.0, help_text="Predicted count in specific direction")
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


# SIGNAL HANDLERS
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=TrafficAnalysis)
def update_video_file_status(sender, instance, created, **kwargs):
    """Update VideoFile status when analysis is created"""
    if created and instance.video_file:
        instance.video_file.processing_status = 'completed'
        instance.video_file.processed = True
        instance.video_file.processed_at = timezone.now()
        instance.video_file.save()


@receiver(post_save, sender=Detection)
def update_traffic_analysis_counts(sender, instance, created, **kwargs):
    """Update TrafficAnalysis counts when new detections are added"""
    if created and instance.traffic_analysis:
        analysis = instance.traffic_analysis
        
        # Update directional count if vehicle was counted
        if instance.counted_directionally:
            analysis.directional_count = Detection.objects.filter(
                traffic_analysis=analysis, 
                counted_directionally=True
            ).count()
        
        # Update vehicle type counts
        vehicle_type_name = instance.vehicle_type.name.lower()
        
        if vehicle_type_name == 'car':
            analysis.car_count = Detection.objects.filter(
                traffic_analysis=analysis, 
                vehicle_type__name='car'
            ).count()
        elif vehicle_type_name == 'truck':
            analysis.truck_count = Detection.objects.filter(
                traffic_analysis=analysis, 
                vehicle_type__name='truck'
            ).count()
        elif vehicle_type_name == 'motorcycle':
            analysis.motorcycle_count = Detection.objects.filter(
                traffic_analysis=analysis, 
                vehicle_type__name='motorcycle'
            ).count()
        elif vehicle_type_name == 'bus':
            analysis.bus_count = Detection.objects.filter(
                traffic_analysis=analysis, 
                vehicle_type__name='bus'
            ).count()
        elif vehicle_type_name == 'bicycle':
            analysis.bicycle_count = Detection.objects.filter(
                traffic_analysis=analysis, 
                vehicle_type__name='bicycle'
            ).count()
        elif vehicle_type_name == 'other':
            analysis.other_count = Detection.objects.filter(
                traffic_analysis=analysis, 
                vehicle_type__name='other'
            ).count()
        
        # Update total vehicles
        analysis.total_vehicles = (
            analysis.car_count + analysis.truck_count + 
            analysis.motorcycle_count + analysis.bus_count + 
            analysis.bicycle_count + analysis.other_count
        )
        analysis.save()


@receiver(post_save, sender=TrafficAnalysis)
def auto_group_video_after_analysis(sender, instance, created, **kwargs):
    """
    Auto-group video after analysis is created.
    ONLY runs if video is not already assigned to a group to prevent conflicts.
    """
    logger.info(f"🔔 AUTO-GROUP SIGNAL FIRED for analysis {instance.id}")
    logger.info(f"   Created: {created}")
    logger.info(f"   Video: {getattr(instance.video_file, 'id', 'None')}")
    logger.info(f"   Location: {getattr(instance.location, 'id', 'None')}")
    logger.info(f"   Video's current group: {getattr(instance.video_file, 'location_date_group', 'None')}")
    
    # Check if we have required fields
    if not created or not instance.video_file or not instance.location:
        logger.warning(f"❌ Cannot auto-group: missing required fields (created={created}, video={bool(instance.video_file)}, location={bool(instance.location)})")
        return

    # Check if video is already grouped
    if hasattr(instance.video_file, 'location_date_group') and instance.video_file.location_date_group:
        logger.info(f"ℹ️ Video {instance.video_file.id} is already in group {instance.video_file.location_date_group.id}, skipping signal grouping.")
        return

    try:
        video = instance.video_file
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
            
        logger.info(f"   Using {date_source}: {group_date}")
        
        # Get or create the location-date group
        group, group_created = LocationDateGroup.objects.get_or_create(
            location=location,
            date=group_date
        )
        
        logger.info(f"   Group: {group.id} (created={group_created})")
        
        # Assign video to the group
        if not video.location_date_group:
            old_group = video.location_date_group
            video.location_date_group = group
            video.save(update_fields=['location_date_group'])
            
            if old_group:
                logger.info(f"✅ Video {video.id} moved from group {old_group.id} to {group.id}")
            else:
                logger.info(f"✅ Video {video.id} assigned to group {group.id}")
        else:
            logger.info(f"ℹ️ Video {video.id} already assigned to group {video.location_date_group.id} during signal execution.")
        
        # Update video's date if it was missing
        if date_source == "analysis_date" and not video.video_date:
            video.video_date = group_date
            video.save(update_fields=['video_date'])
            logger.info(f"📅 Updated video {video.id} date to {group_date}")
            
    except Exception as e:
        logger.error(f"❌ Failed to auto-group video {getattr(instance.video_file, 'id', 'unknown')}: {e}")
        import traceback
        traceback.print_exc()