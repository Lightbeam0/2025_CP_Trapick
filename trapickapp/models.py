# trapickapp/models.py
from django.db import models
from django.utils import timezone
import uuid
from django.contrib.auth.models import User

class VideoFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='videos/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)
    processed_video_path = models.FileField(upload_to='processed_videos/', null=True, blank=True)
    processing_status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    duration_seconds = models.FloatField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    total_frames = models.IntegerField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    resolution = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.filename} - {self.processing_status}"

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

class Location(models.Model):
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.display_name

class TrafficAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.OneToOneField(VideoFile, on_delete=models.CASCADE, related_name='traffic_analysis')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    
    total_vehicles = models.IntegerField(default=0)
    processing_time_seconds = models.FloatField(default=0)
    analyzed_at = models.DateTimeField(default=timezone.now)
    
    car_count = models.IntegerField(default=0)
    truck_count = models.IntegerField(default=0)
    motorcycle_count = models.IntegerField(default=0)
    bus_count = models.IntegerField(default=0)
    bicycle_count = models.IntegerField(default=0)
    other_count = models.IntegerField(default=0)
    
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
    
    analysis_data = models.JSONField(default=dict)
    metrics_summary = models.JSONField(default=dict)
    
    class Meta:
        verbose_name_plural = "Traffic Analyses"
        indexes = [
            models.Index(fields=['analyzed_at']),
            models.Index(fields=['location', 'analyzed_at']),
        ]

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

    def __str__(self):
        return f"Analysis for {self.video_file.filename}"

class Detection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.ForeignKey(VideoFile, on_delete=models.CASCADE, related_name='detections')
    traffic_analysis = models.ForeignKey(TrafficAnalysis, on_delete=models.CASCADE, null=True, blank=True, related_name='detections')
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
        ]

    def __str__(self):
        return f"{self.vehicle_type.name} at frame {self.frame_number}"

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

    def __str__(self):
        return f"{self.prediction_date} {self.hour_of_day:02d}:00 → {self.predicted_congestion}"

class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

# Signal handlers
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=TrafficAnalysis)
def update_video_file_status(sender, instance, created, **kwargs):
    """Update VideoFile status when analysis is created"""
    if created:
        instance.video_file.processing_status = 'completed'
        instance.video_file.processed = True
        instance.video_file.processed_at = timezone.now()
        instance.video_file.save()

@receiver(post_save, sender=Detection)
def update_traffic_analysis_counts(sender, instance, created, **kwargs):
    """Update TrafficAnalysis counts when new detections are added"""
    if created and instance.traffic_analysis:
        analysis = instance.traffic_analysis
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
        
        analysis.total_vehicles = (
            analysis.car_count + analysis.truck_count + 
            analysis.motorcycle_count + analysis.bus_count + 
            analysis.bicycle_count + analysis.other_count
        )
        analysis.save()