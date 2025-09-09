from django.db import models
from django.utils import timezone
import uuid

class VideoFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='videos/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)
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

    def __str__(self):
        return f"{self.filename} - {self.processing_status}"

class VehicleType(models.Model):
    name = models.CharField(max_length=50, unique=True)  # car, truck, bus, motorcycle, etc.
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class Location(models.Model):
    """Traffic monitoring locations in Zamboanga City"""
    name = models.CharField(max_length=100)  # baliwasan, sanroque, downtown
    display_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.display_name

class Detection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_file = models.ForeignKey(VideoFile, on_delete=models.CASCADE, related_name='detections')
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField()  # When the vehicle was detected in the video
    frame_number = models.IntegerField()
    confidence = models.FloatField()  # YOLOv8 confidence score
    bbox_x = models.FloatField()  # Bounding box coordinates
    bbox_y = models.FloatField()
    bbox_width = models.FloatField()
    bbox_height = models.FloatField()
    track_id = models.IntegerField(null=True, blank=True)  # For vehicle tracking
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['vehicle_type', 'timestamp']),
            models.Index(fields=['location', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.vehicle_type.display_name} at {self.timestamp}"

class HourlyTrafficSummary(models.Model):
    """Aggregated hourly traffic data for faster querying"""
    date = models.DateField()
    hour = models.IntegerField()  # 0-23
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    count = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['date', 'hour', 'vehicle_type']
        indexes = [
            models.Index(fields=['date', 'hour']),
        ]

class DailyTrafficSummary(models.Model):
    """Aggregated daily traffic data"""
    date = models.DateField()
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE)
    total_count = models.IntegerField()
    peak_hour = models.IntegerField()  # Hour with most traffic
    peak_hour_count = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['date', 'vehicle_type']

class TrafficPrediction(models.Model):
    day_of_week = models.IntegerField(default=0)  # 0 = Monday, 6 = Sunday
    hour_of_day = models.IntegerField(default=0)  # 0–23
    predicted_congestion = models.FloatField(default=0.0)
    confidence_interval_lower = models.FloatField(default=0.0)
    confidence_interval_upper = models.FloatField(default=0.0)
    model_version = models.CharField(max_length=50, default="v1")  # version tag for tracking
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Day {self.day_of_week}, Hour {self.hour_of_day} → {self.predicted_congestion:.2f}"