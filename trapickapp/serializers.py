# trapickapp/serializers.py - FIXED VideoFileSerializer

from rest_framework import serializers
from .models import (
    LocationDateGroup, VehicleType, Location, VideoFile, TrafficAnalysis, 
    Detection, TrafficPrediction, ProcessingProfile, DirectionalAnalysis, 
    CongestionEvent
)


class ProcessingProfileSerializer(serializers.ModelSerializer):
    location_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcessingProfile
        fields = [
            'id', 'name', 'display_name', 'description', 
            'detector_type',
            'enable_congestion_detection',
            'congestion_threshold',
            'road_type',
            'active',
            'created_at',
            'location_count'
        ]
        read_only_fields = ['id', 'created_at', 'location_count']
    
    def get_location_count(self, obj):
        return obj.locations.count()


class LocationSerializer(serializers.ModelSerializer):
    processing_profile_details = ProcessingProfileSerializer(source='processing_profile', read_only=True)
    
    class Meta:
        model = Location
        fields = [
            'id', 'name', 'display_name', 'description',
            'latitude', 'longitude', 'processing_profile', 'processing_profile_details',
            'counting_config', 'active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class VideoFileSerializer(serializers.ModelSerializer):
    video_date_display = serializers.SerializerMethodField()
    time_range = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    has_analysis = serializers.SerializerMethodField()
    analysis_model = serializers.SerializerMethodField()
    
    class Meta:
        model = VideoFile
        fields = [
            'id', 'filename', 'processing_status', 'uploaded_at',
            'processed', 'duration_seconds', 'title',
            'video_date', 'video_start_time', 'video_end_time',
            'video_date_display', 'time_range', 'location_name',
            'has_analysis', 'analysis_model', 'location_date_group'
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
    
    def get_analysis_model(self, obj):
        """Get which model was used for analysis - FIXED"""
        if hasattr(obj, 'traffic_analysis'):
            model_info = obj.traffic_analysis.get_model_info()
            
            # ✅ FIX: Use the keys that actually exist in model_info
            return {
                'model_name': model_info.get('model_name', 'Unknown'),
                'detector_type': model_info.get('detector_type', 'Unknown'),
                'is_directional': model_info.get('is_directional', False),
                'is_congestion': model_info.get('is_congestion', False)
            }
        return None


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


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name', 'display_name']


class DetectionSerializer(serializers.ModelSerializer):
    vehicle_type = VehicleTypeSerializer(read_only=True)
    
    class Meta:
        model = Detection
        fields = [
            'id', 'vehicle_type', 'frame_number', 'confidence', 'timestamp',
            'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height', 'track_id'
        ]


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


class UploadVideoSerializer(serializers.Serializer):
    """Serializer for video upload"""
    video = serializers.FileField()
    title = serializers.CharField(required=False, allow_blank=True)
    location_id = serializers.UUIDField(required=False)


class AnalysisSummarySerializer(serializers.Serializer):
    """Serializer for analysis summary data"""
    total_vehicles = serializers.IntegerField()
    vehicle_breakdown = serializers.DictField()
    processing_time = serializers.FloatField()
    congestion_level = serializers.CharField()
    traffic_pattern = serializers.CharField()
    analyzed_at = serializers.DateTimeField()
    location = serializers.DictField(required=False)
    model_used = serializers.CharField(required=False)
    model_architecture = serializers.CharField(required=False)


class TrafficAnalysisSerializer(serializers.ModelSerializer):
    """Enhanced serializer with directional detector support"""
    video_file = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    vehicle_breakdown = serializers.SerializerMethodField()
    model_info = serializers.SerializerMethodField()
    
    class Meta:
        model = TrafficAnalysis
        fields = [
            'id', 'video_file', 'location', 'total_vehicles', 'processing_time_seconds',
            'analyzed_at', 'car_count', 'truck_count', 'motorcycle_count', 'bus_count',
            'bicycle_count', 'other_count', 'peak_traffic', 'average_traffic',
            'congestion_level', 'traffic_pattern', 'vehicle_breakdown', 
            'model_info'
        ]
    
    def get_video_file(self, obj):
        """Lightweight video file info"""
        return {
            'id': obj.video_file.id,
            'filename': obj.video_file.filename,
            'title': obj.video_file.title or obj.video_file.filename
        }
    
    def get_location(self, obj):
        """Location info with processing profile"""
        if not obj.location:
            return None
        return {
            'id': obj.location.id,
            'name': obj.location.display_name,
            'processing_profile': obj.location.processing_profile.display_name if obj.location.processing_profile else 'Default'
        }
    
    def get_vehicle_breakdown(self, obj):
        """Get vehicle breakdown based on model type"""
        return obj.get_vehicle_breakdown()
    
    def get_model_info(self, obj):
        """Get model information"""
        return obj.get_model_info()


class TrafficAnalysisDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single analysis view"""
    video_file_detail = serializers.SerializerMethodField()
    location_detail = serializers.SerializerMethodField()
    vehicle_breakdown = serializers.SerializerMethodField()
    model_info = serializers.SerializerMethodField()
    
    class Meta:
        model = TrafficAnalysis
        fields = [
            'id', 'video_file_detail', 'location_detail', 'total_vehicles', 
            'processing_time_seconds', 'analyzed_at', 'car_count', 'truck_count', 
            'motorcycle_count', 'bus_count', 'bicycle_count', 'other_count', 
            'peak_traffic', 'average_traffic', 'congestion_level', 'traffic_pattern',
            'vehicle_breakdown', 'model_info', 'analysis_data', 
            'metrics_summary'
        ]
    
    def get_video_file_detail(self, obj):
        """Full video file details"""
        return {
            'id': obj.video_file.id,
            'filename': obj.video_file.filename,
            'title': obj.video_file.title,
            'uploaded_at': obj.video_file.uploaded_at,
            'duration_seconds': obj.video_file.duration_seconds,
            'fps': obj.video_file.fps,
            'total_frames': obj.video_file.total_frames,
            'video_date': obj.video_file.video_date,
            'video_start_time': obj.video_file.video_start_time,
            'video_end_time': obj.video_file.video_end_time
        }
    
    def get_location_detail(self, obj):
        """Full location details"""
        if not obj.location:
            return None
        return {
            'id': obj.location.id,
            'name': obj.location.name,
            'display_name': obj.location.display_name,
            'description': obj.location.description,
            'processing_profile': {
                'id': obj.location.processing_profile.id,
                'name': obj.location.processing_profile.display_name,
                'detector_type': obj.location.processing_profile.detector_type,
                'road_type': obj.location.processing_profile.road_type
            } if obj.location.processing_profile else None
        }
    
    def get_vehicle_breakdown(self, obj):
        """Vehicle breakdown with formatting"""
        breakdown = obj.get_vehicle_breakdown()
        
        # Format based on detector type
        model_info = obj.get_model_info()
        is_directional = model_info.get('is_directional', False)
        
        if is_directional:
            return {
                'data': breakdown,
                'format': 'directional',
                'labels': {
                    'car': 'Cars',
                    'motorcycle': 'Motorcycles',
                    'bus': 'Buses',
                    'truck': 'Trucks',
                    'bicycle': 'Bicycles'
                }
            }
        else:
            return {
                'data': breakdown,
                'format': 'standard',
                'labels': {
                    'cars': 'Cars',
                    'trucks': 'Trucks',
                    'motorcycles': 'Motorcycles',
                    'buses': 'Buses',
                    'bicycles': 'Bicycles',
                    'others': 'Others'
                }
            }
    
    def get_model_info(self, obj):
        """Model information"""
        return obj.get_model_info()