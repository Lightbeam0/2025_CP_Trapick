# trapickapp/models.py
from django.db import models
from django.utils import timezone
import uuid
import os
import logging
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# trapickapp/models.py - Update ProcessingProfile model
class ProcessingProfile(models.Model):
    """Customizable processing profiles"""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    
    # Detector configuration
    detector_class = models.CharField(
        max_length=100,
        default='RTXVehicleDetector',
        help_text="Python class name of the detector to use"
    )
    detector_module = models.CharField(
        max_length=200,
        default='ml.vehicle_detector',
        help_text="Python module path where detector class is located"
    )
    
    # Configuration parameters
    config_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON configuration for this processing profile"
    )
    
    # Road type categorization
    ROAD_TYPES = [
        ('highway', 'Highway'),
        ('intersection', 'Intersection'),
        ('y_junction', 'Y-Junction'),
        ('t_intersection', 'T-Intersection'),
        ('roundabout', 'Roundabout'),
        ('urban', 'Urban Street'),
        ('generic', 'Generic'),
        ('custom', 'Custom'),
    ]
    road_type = models.CharField(
        max_length=50,
        choices=ROAD_TYPES,
        default='generic'
    )
    
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)  # ADD THIS LINE
    
    class Meta:
        ordering = ['road_type', 'display_name']
    
    def __str__(self):
        return f"{self.display_name} ({self.get_road_type_display()})"
    
    def get_detector_instance(self):
        """Dynamically import and return the detector instance"""
        try:
            module = __import__(self.detector_module, fromlist=[self.detector_class])
            detector_class = getattr(module, self.detector_class)
            return detector_class(**self.config_parameters)
        except (ImportError, AttributeError) as e:
            print(f"❌ [DETECTOR] Error loading detector {self.detector_class}: {e}")
            from ml.vehicle_detector import RTXVehicleDetector
            return RTXVehicleDetector()

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
        related_name='locations'
    )
    
    detection_config = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.display_name}"

class LocationDateGroup(models.Model):
    """Groups processed videos by location and date"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='date_groups')
    date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['location', 'date']
        ordering = ['-date', 'location__display_name']

    def __str__(self):
        return f"{self.location.display_name} - {self.date}"

    def get_videos_by_time(self):
        """Get videos sorted by time"""
        return self.videos.all().order_by('video_start_time')

    def get_total_vehicles(self):
        """Calculate total vehicles in this group"""
        analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=self)
        return sum(analysis.total_vehicles for analysis in analyses) if analyses else 0

    def get_time_range(self):
        """Get time range for videos in this group"""
        videos = self.videos.all()
        if not videos:
            return "No time data"
        
        times = []
        for video in videos:
            if video.video_start_time:
                times.append(video.video_start_time)
            if video.video_end_time:
                times.append(video.video_end_time)
        
        if times:
            return f"{min(times).strftime('%H:%M')} - {max(times).strftime('%H:%M')}"
        return "Time range not available"

    @classmethod
    def get_or_create_group(cls, location, date):
        """Get existing group or create new one"""
        group, created = cls.objects.get_or_create(
            location=location,
            date=date
        )
        if created:
            print(f"✅ Created new group: {location.display_name} - {date}")
        return group, created

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
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    duration_seconds = models.FloatField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    total_frames = models.IntegerField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    resolution = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['processing_status']),
            models.Index(fields=['location_date_group', 'video_date']),
        ]

    def __str__(self):
        return f"{self.filename} - {self.video_date if self.video_date else 'Unknown Date'}"

    def get_video_time_range(self):
        if self.video_start_time and self.video_end_time:
            return f"{self.video_start_time.strftime('%H:%M')} - {self.video_end_time.strftime('%H:%M')}"
        return "Time unknown"

class TrafficAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.OneToOneField(
        VideoFile, 
        on_delete=models.CASCADE, 
        related_name='traffic_analysis'
    )
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    
    # VEHICLE COUNTS
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
    
    # TRAFFIC METRICS
    peak_traffic = models.IntegerField(default=0)
    average_traffic = models.FloatField(default=0)
    congestion_level = models.CharField(
        max_length=20,
        choices=[
            ('very_low', 'Very Low'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('severe', 'Severe')
        ],
        default='low'
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

    class Meta:
        verbose_name_plural = "Traffic Analyses"
        ordering = ['-analyzed_at']

    def get_vehicle_breakdown(self):
        return {
            'cars': self.car_count,
            'trucks': self.truck_count,
            'motorcycles': self.motorcycle_count,
            'buses': self.bus_count,
            'bicycles': self.bicycle_count,
            'others': self.other_count,
            'total': self.total_vehicles
        }

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
    
    in_counting_zone = models.BooleanField(default=True)
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
        ]
        ordering = ['timestamp', 'frame_number']

    def __str__(self):
        return f"{self.vehicle_type.name} at frame {self.frame_number} (conf: {self.confidence:.2f})"


class FrameAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    traffic_analysis = models.ForeignKey(TrafficAnalysis, on_delete=models.CASCADE, related_name='frame_analyses')
    frame_number = models.IntegerField()
    timestamp_seconds = models.FloatField()
    
    car_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    motorcycle_count = models.IntegerField(default=0)
    bus_count = models.IntegerField(default=0)
    bicycle_count = models.IntegerField(default=0)
    total_vehicles = models.IntegerField(default=0)
    
    congestion_level = models.CharField(max_length=20, default='low')
    detection_data = models.JSONField(default=dict)
    
    class Meta:
        unique_together = ['traffic_analysis', 'frame_number']
        indexes = [
            models.Index(fields=['traffic_analysis', 'timestamp_seconds']),
        ]
        ordering = ['frame_number']

    def __str__(self):
        return f"Frame {self.frame_number} - {self.total_vehicles} vehicles"


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
    ]
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default='detailed')
    
    title = models.CharField(max_length=200)
    executive_summary = models.TextField(blank=True)
    key_findings = models.JSONField(default=dict)
    insights = models.TextField(blank=True)
    predictions = models.JSONField(default=dict)
    recommendations = models.TextField(blank=True)
    
    total_vehicles_period = models.IntegerField(default=0)
    average_daily_traffic = models.FloatField(default=0)
    peak_hours = models.JSONField(default=list)
    congestion_trends = models.JSONField(default=dict)
    
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
        return f"{self.date} {self.hour:02d}:00 - {self.vehicle_type}: {self.count}"


class DailyTrafficSummary(models.Model):
    date = models.DateField()
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    total_count = models.IntegerField()
    peak_hour = models.IntegerField()
    peak_hour_count = models.IntegerField()
    average_daily_congestion = models.CharField(max_length=20, default='low')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['date', 'vehicle_type', 'location']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['location', 'date']),
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} - {self.vehicle_type}: {self.total_count}"


class TrafficPrediction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    prediction_date = models.DateField()
    day_of_week = models.IntegerField()
    hour_of_day = models.IntegerField()
    
    predicted_vehicle_count = models.FloatField(default=0.0)
    predicted_congestion = models.CharField(max_length=20, default='low')
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
        
        # Use the vehicle type name to update the appropriate count
        vehicle_type_name = instance.vehicle_type.name.lower()
        
        # Update counts based on vehicle type
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
    ONLY runs if video is not already assigned to a group to prevent conflicts with Celery task.
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

    # CRITICAL FIX: Check if video is already grouped BEFORE processing
    if hasattr(instance.video_file, 'location_date_group') and instance.video_file.location_date_group:
        logger.info(f"ℹ️ Video {instance.video_file.id} is already in group {instance.video_file.location_date_group.id}, skipping signal grouping.")
        return # Exit early if already grouped - prevents race condition!

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
        
        # Assign video to the group (this is the critical part that was causing conflicts)
        if not video.location_date_group: # Double-check before assignment
            old_group = video.location_date_group
            video.location_date_group = group
            video.save(update_fields=['location_date_group']) # Only save the group field to minimize race conditions
            
            if old_group:
                logger.info(f"✅ Video {video.id} moved from group {old_group.id} to {group.id}")
            else:
                logger.info(f"✅ Video {video.id} assigned to group {group.id}")
        else:
            logger.info(f"ℹ️ Video {video.id} already assigned to group {video.location_date_group.id} during signal execution.")
        
        # Update video's date if it was missing (only if we're using analysis date and video_date is empty)
        if date_source == "analysis_date" and not video.video_date:
            video.video_date = group_date
            video.save(update_fields=['video_date'])
            logger.info(f"📅 Updated video {video.id} date to {group_date}")
            
    except Exception as e:
        logger.error(f"❌ Failed to auto-group video {getattr(instance.video_file, 'id', 'unknown')}: {e}")
        import traceback
        traceback.print_exc()