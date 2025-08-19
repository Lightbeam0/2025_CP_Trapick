from django.db import models
from django.db.models import JSONField
from django.utils import timezone

# Create your models here.
class VideoUpload(models.Model):
    video_file = models.FileField(upload_to='videos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
class VehicleDetection(models.Model):
    video = models.ForeignKey(VideoUpload, on_delete=models.CASCADE)
    frame_number = models.IntegerField()
    timestamp = models.FloatField()  # seconds from start
    vehicle_type = models.CharField(max_length=50)  # car, truck, etc.
    confidence = models.FloatField()
    
class TrafficAnalysis(models.Model):
    video = models.ForeignKey(VideoUpload, on_delete=models.CASCADE)
    day_of_week = models.IntegerField()  # 0=Monday, 6=Sunday
    hour_of_day = models.IntegerField()  # 0-23
    vehicle_count = models.IntegerField()
    vehicle_types = JSONField()  # {'car': 50, 'truck': 10}
    created_at = models.DateTimeField(auto_now_add=True)
    
class TrafficPrediction(models.Model):
    day_of_week = models.IntegerField()
    hour_of_day = models.IntegerField()
    predicted_congestion = models.FloatField()  # 0-1 scale
    generated_at = models.DateTimeField(auto_now_add=True)