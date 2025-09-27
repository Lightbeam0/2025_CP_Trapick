# trapickapp/serializers.py
from rest_framework import serializers
from .models import *

class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'display_name']

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'display_name', 'description', 'latitude', 'longitude']

class VideoFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoFile
        fields = ['id', 'filename', 'processing_status', 'uploaded_at', 'processed', 'duration_seconds']

class TrafficAnalysisSerializer(serializers.ModelSerializer):
    video_file = VideoFileSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    
    class Meta:
        model = TrafficAnalysis
        fields = [
            'id', 'video_file', 'location', 'total_vehicles', 'processing_time_seconds',
            'analyzed_at', 'car_count', 'truck_count', 'motorcycle_count', 'bus_count',
            'bicycle_count', 'other_count', 'peak_traffic', 'average_traffic',
            'congestion_level', 'traffic_pattern'
        ]

class DetectionSerializer(serializers.ModelSerializer):
    vehicle_type = VehicleTypeSerializer(read_only=True)
    
    class Meta:
        model = Detection
        fields = [
            'id', 'vehicle_type', 'frame_number', 'confidence', 'timestamp',
            'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height', 'track_id'
        ]

class AnalysisSummarySerializer(serializers.Serializer):
    """Serializer for analysis summary data"""
    total_vehicles = serializers.IntegerField()
    vehicle_breakdown = serializers.DictField()
    processing_time = serializers.FloatField()
    congestion_level = serializers.CharField()
    traffic_pattern = serializers.CharField()
    analyzed_at = serializers.DateTimeField()

class UploadVideoSerializer(serializers.Serializer):
    """Serializer for video upload"""
    video = serializers.FileField()
    title = serializers.CharField(required=False, allow_blank=True)
    location_id = serializers.UUIDField(required=False)