# trapickapp/serializers.py
from rest_framework import serializers
from .models import LocationDateGroup, VehicleType, Location, VideoFile, TrafficAnalysis, Detection, TrafficPrediction, ProcessingProfile


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'display_name']

class ProcessingProfileSerializer(serializers.ModelSerializer):
    location_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcessingProfile
        fields = [
            'id', 'name', 'display_name', 'description', 
            'detector_class', 'detector_module', 'config_parameters',
            'road_type', 'active', 'created_at', 'updated_at', 'location_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'location_count']
    
    def get_location_count(self, obj):
        return obj.locations.count()

class LocationSerializer(serializers.ModelSerializer):
    processing_profile_details = ProcessingProfileSerializer(source='processing_profile', read_only=True)
    
    class Meta:
        model = Location
        fields = [
            'id', 'name', 'display_name', 'description',
            'latitude', 'longitude', 'processing_profile', 'processing_profile_details',
            'detection_config', 'active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class VideoFileSerializer(serializers.ModelSerializer):
    video_date_display = serializers.SerializerMethodField()
    time_range = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    has_analysis = serializers.SerializerMethodField()
    
    class Meta:
        model = VideoFile
        fields = [
            'id', 'filename', 'processing_status', 'uploaded_at',
            'processed', 'duration_seconds', 'title',
            'video_date', 'video_start_time', 'video_end_time',
            'video_date_display', 'time_range', 'location_name',
            'has_analysis', 'location_date_group'
        ]
    
    def get_video_date_display(self, obj):
        if not obj.video_date:
            return "Unknown"
        if isinstance(obj.video_date, str):
            return obj.video_date
        try:
            return obj.video_date.strftime("%Y-%m-%d")
        except AttributeError:
            return str(obj.video_date)
    
    def get_time_range(self, obj):
        return obj.get_video_time_range()
    
    def get_location_name(self, obj):
        if hasattr(obj, 'traffic_analysis') and obj.traffic_analysis.location:
            return obj.traffic_analysis.location.display_name
        return "Not assigned"
    
    def get_has_analysis(self, obj):
        return hasattr(obj, 'traffic_analysis')

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

class TrafficPredictionSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.display_name', read_only=True, allow_null=True)
    
    class Meta:
        model = TrafficPrediction
        fields = [
            'id', 'location', 'location_name', 'prediction_date', 
            'day_of_week', 'hour_of_day', 'predicted_vehicle_count',
            'predicted_congestion', 'confidence_score', 
            'confidence_interval_lower', 'confidence_interval_upper',
            'model_version', 'prediction_generated_at'
        ]
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Convert hour to readable format
        data['hour_display'] = f"{instance.hour_of_day:02d}:00"
        data['day_name'] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][instance.day_of_week]
        return data
    
class LocationDateGroupSerializer(serializers.ModelSerializer):
    location_details = LocationSerializer(source='location', read_only=True)
    video_count = serializers.SerializerMethodField()
    total_vehicles = serializers.SerializerMethodField()
    
    class Meta:
        model = LocationDateGroup
        fields = [
            'id', 'location', 'location_details', 'date', 
            'created_at', 'updated_at', 'video_count', 'total_vehicles'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_video_count(self, obj):
        return obj.videos.count()
    
    def get_total_vehicles(self, obj):
        analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=obj)
        return sum(analysis.total_vehicles for analysis in analyses)


