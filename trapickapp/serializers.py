from rest_framework import serializers
from .models import (
    LocationDateGroup, VehicleType, Location, VideoFile, TrafficAnalysis, 
    Detection, TrafficPrediction, ProcessingProfile, DirectionalAnalysis, 
    CongestionEvent, FrameAnalysis,
)


# ──────────────────────────────────────────────────────────────────────────
# ENHANCED: ProcessingProfileSerializer with new feature flags
# ──────────────────────────────────────────────────────────────────────────

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
            'config_parameters',
            'active',
            'created_at',
            'location_count',
            # ✅ NEW: Enhanced feature flags
            'enable_lane_detection',
            'enable_turning_movement',
            'enable_stopped_vehicle_detection',
            'enable_night_enhancement',
            'enable_trajectory_prediction',
            # ✅ ADD NEW: Missing ML feature flags
            'enable_enhanced_congestion',
            'enable_class_confidence_tracking',
            'enable_multi_pass',
            'enable_stabilization',
            'lane_config',
            'congestion_sensitivity',
            'weather_adaptation',
        ]
        read_only_fields = ['id', 'created_at', 'location_count']

    def get_location_count(self, obj):
        return obj.locations.count()

    def create(self, validated_data):
        # Mirror direct model fields into config_parameters so both stay in sync
        config = validated_data.get('config_parameters', {}) or {}
        config['enable_congestion_detection'] = validated_data.get('enable_congestion_detection', True)
        config['congestion_threshold'] = validated_data.get('congestion_threshold', 5)
        
        # ✅ NEW: Mirror enhanced fields to config_parameters
        config['enable_lane_detection'] = validated_data.get('enable_lane_detection', False)
        config['enable_turning_movement'] = validated_data.get('enable_turning_movement', False)
        config['enable_stopped_vehicle_detection'] = validated_data.get('enable_stopped_vehicle_detection', False)
        config['enable_night_enhancement'] = validated_data.get('enable_night_enhancement', False)
        config['enable_trajectory_prediction'] = validated_data.get('enable_trajectory_prediction', False)
        
        # ✅ ADD NEW: Mirror missing ML feature flags
        config['enable_enhanced_congestion'] = validated_data.get('enable_enhanced_congestion', False)
        config['enable_class_confidence_tracking'] = validated_data.get('enable_class_confidence_tracking', False)
        config['enable_multi_pass'] = validated_data.get('enable_multi_pass', False)
        config['enable_stabilization'] = validated_data.get('enable_stabilization', False)
        
        config['lane_config'] = validated_data.get('lane_config', {})
        config['congestion_sensitivity'] = validated_data.get('congestion_sensitivity', 'medium')
        config['weather_adaptation'] = validated_data.get('weather_adaptation', True)
        
        validated_data['config_parameters'] = config
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Mirror direct model fields into config_parameters on update too
        config = validated_data.get('config_parameters', instance.config_parameters or {})
        config['enable_congestion_detection'] = validated_data.get(
            'enable_congestion_detection', instance.enable_congestion_detection
        )
        config['congestion_threshold'] = validated_data.get(
            'congestion_threshold', instance.congestion_threshold
        )
        
        # ✅ NEW: Mirror enhanced fields on update
        config['enable_lane_detection'] = validated_data.get(
            'enable_lane_detection', instance.enable_lane_detection
        )
        config['enable_turning_movement'] = validated_data.get(
            'enable_turning_movement', instance.enable_turning_movement
        )
        config['enable_stopped_vehicle_detection'] = validated_data.get(
            'enable_stopped_vehicle_detection', instance.enable_stopped_vehicle_detection
        )
        config['enable_night_enhancement'] = validated_data.get(
            'enable_night_enhancement', instance.enable_night_enhancement
        )
        config['enable_trajectory_prediction'] = validated_data.get(
            'enable_trajectory_prediction', instance.enable_trajectory_prediction
        )
        
        # ✅ ADD NEW: Mirror missing ML feature flags on update
        config['enable_enhanced_congestion'] = validated_data.get(
            'enable_enhanced_congestion', instance.enable_enhanced_congestion
        )
        config['enable_class_confidence_tracking'] = validated_data.get(
            'enable_class_confidence_tracking', instance.enable_class_confidence_tracking
        )
        config['enable_multi_pass'] = validated_data.get(
            'enable_multi_pass', instance.enable_multi_pass
        )
        config['enable_stabilization'] = validated_data.get(
            'enable_stabilization', instance.enable_stabilization
        )
        
        config['lane_config'] = validated_data.get('lane_config', instance.lane_config)
        config['congestion_sensitivity'] = validated_data.get(
            'congestion_sensitivity', instance.congestion_sensitivity
        )
        config['weather_adaptation'] = validated_data.get(
            'weather_adaptation', instance.weather_adaptation
        )
        
        validated_data['config_parameters'] = config
        return super().update(instance, validated_data)


# ──────────────────────────────────────────────────────────────────────────
# ENHANCED: TrafficAnalysisSerializer with new metrics
# ──────────────────────────────────────────────────────────────────────────

class TrafficAnalysisSerializer(serializers.ModelSerializer):
    """Enhanced serializer with directional detector support and new metrics"""
    video_file = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    vehicle_breakdown = serializers.SerializerMethodField()
    model_info = serializers.SerializerMethodField()
    
    # ✅ NEW: Enhanced metrics field
    enhanced_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = TrafficAnalysis
        fields = [
            'id', 'video_file', 'location', 'total_vehicles', 'processing_time_seconds',
            'analyzed_at', 'car_count', 'truck_count', 'motorcycle_count', 'bus_count',
            'bicycle_count', 'other_count', 'peak_traffic', 'average_traffic',
            'congestion_level', 'traffic_pattern', 'vehicle_breakdown', 
            'model_info',
            # ✅ NEW: Enhanced fields
            'enhanced_metrics',
            'avg_speed_kmh', 'p85_speed_kmh', 'max_speed_kmh',
            'stopped_vehicles_count', 'detector_version',
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
    
    # ✅ NEW: Enhanced metrics getter
    def get_enhanced_metrics(self, obj):
        """Get enhanced metrics if available"""
        return obj.get_enhanced_metrics()


class TrafficAnalysisDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single analysis view with enhanced data"""
    video_file_detail = serializers.SerializerMethodField()
    location_detail = serializers.SerializerMethodField()
    vehicle_breakdown = serializers.SerializerMethodField()
    model_info = serializers.SerializerMethodField()
    enhanced_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = TrafficAnalysis
        fields = [
            'id', 'video_file_detail', 'location_detail', 'total_vehicles', 
            'processing_time_seconds', 'analyzed_at', 'car_count', 'truck_count', 
            'motorcycle_count', 'bus_count', 'bicycle_count', 'other_count', 
            'peak_traffic', 'average_traffic', 'congestion_level', 'traffic_pattern',
            'vehicle_breakdown', 'model_info', 'analysis_data', 
            'metrics_summary',
            # ✅ NEW: Enhanced fields
            'enhanced_metrics',
            'lane_statistics', 'turning_movements',
            'congestion_index', 'queue_length_meters', 'incident_risk_score', 'congestion_trend',
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
                'road_type': obj.location.processing_profile.road_type,
                # ✅ NEW: Include enhanced flags
                'enhanced_features': {
                    'lane_detection': obj.location.processing_profile.enable_lane_detection,
                    'turning_movement': obj.location.processing_profile.enable_turning_movement,
                    'stopped_vehicle': obj.location.processing_profile.enable_stopped_vehicle_detection,
                } if hasattr(obj.location.processing_profile, 'enable_lane_detection') else None,
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
    
    def get_enhanced_metrics(self, obj):
        """Get all enhanced metrics in one structured dict"""
        return obj.get_enhanced_metrics()


# ──────────────────────────────────────────────────────────────────────────
# ENHANCED: DirectionalAnalysisSerializer with lane/turning data
# ──────────────────────────────────────────────────────────────────────────

class DirectionalAnalysisSerializer(serializers.ModelSerializer):
    lane_summary = serializers.SerializerMethodField()
    total_count = serializers.IntegerField(source='get_total_count', read_only=True)
    
    class Meta:
        model = DirectionalAnalysis
        fields = [
            'id', 'direction_name', 'direction_angle',
            'line_start_x', 'line_start_y', 'line_end_x', 'line_end_y',
            'directional_car_count', 'directional_truck_count', 
            'directional_motorcycle_count', 'directional_bus_count',
            'directional_bicycle_count', 'total_count',
            'analyzed_at',
            # ✅ NEW: Enhanced fields
            'lane_counts', 'turning_counts', 'lane_speeds', 'lane_summary',
        ]
    
    def get_lane_summary(self, obj):
        """Get lane-based summary"""
        return obj.get_lane_summary()


# ──────────────────────────────────────────────────────────────────────────
# ENHANCED: FrameAnalysisSerializer with new fields
# ──────────────────────────────────────────────────────────────────────────

class FrameAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = FrameAnalysis
        fields = [
            'id', 'frame_number', 'timestamp_seconds',
            'car_count', 'truck_count', 'motorcycle_count', 
            'bus_count', 'bicycle_count', 'total_vehicles',
            'directional_count', 'congestion_level', 'stationary_vehicles',
            # ✅ NEW: Enhanced frame fields
            'avg_speed_frame', 'lane_assignments', 'stopped_vehicles_frame',
            'detection_data',
        ]


# ──────────────────────────────────────────────────────────────────────────
# PRESERVED: Existing serializers (unchanged, but re-exported)
# ──────────────────────────────────────────────────────────────────────────

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


class CongestionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CongestionEvent
        fields = '__all__'