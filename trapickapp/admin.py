# trapickapp/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import *

@admin.register(ProcessingProfile)
class ProcessingProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'road_type', 'detector_class', 'active', 'created_at']
    list_filter = ['road_type', 'active', 'created_at']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['active']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'road_type', 'active')
        }),
        ('Detector Configuration', {
            'fields': ('detector_class', 'detector_module', 'config_parameters')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'processing_profile', 'active', 'created_at']
    list_filter = ['active', 'processing_profile__road_type', 'created_at']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['created_at']
    list_editable = ['active']
    autocomplete_fields = ['processing_profile']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'active')
        }),
        ('Geographic Information', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Processing Configuration', {
            'fields': ('processing_profile', 'detection_config')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(AnalysisSession)
class AnalysisSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'status', 'start_datetime', 'end_datetime', 'created_at', 'video_files_count', 'processed_session_video_link']
    list_filter = ['status', 'location', 'created_at']
    search_fields = ['name', 'location__display_name']
    readonly_fields = ['created_at', 'processed_at', 'video_files_count_display']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['location']
    
    def video_files_count(self, obj):
        return obj.video_files.count()
    video_files_count.short_description = 'Videos'
    
    def video_files_count_display(self, obj):
        return obj.video_files.count()
    video_files_count_display.short_description = 'Number of Videos'
    
    def processed_session_video_link(self, obj):
        if obj.processed_session_video_path:
            return format_html(
                '<a href="{}" target="_blank">View Video</a>',
                reverse('admin:view_session_video', args=[obj.id])
            )
        return "Not available"
    processed_session_video_link.short_description = 'Processed Video'
    
    fieldsets = (
        ('Session Information', {
            'fields': ('name', 'location', 'status')
        }),
        ('Time Period', {
            'fields': ('start_datetime', 'end_datetime')
        }),
        ('Video Information', {
            'fields': ('video_files_count_display', 'processed_session_video_path')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(VideoFile)
class VideoFileAdmin(admin.ModelAdmin):
    list_display = [
        'filename', 'title', 'video_date', 'processing_status', 
        'processed', 'uploaded_at', 'analysis_session_link', 'processed_video_link'
    ]
    list_filter = [
        'processing_status', 'processed', 'uploaded_at', 'video_date',
        'analysis_session__name'
    ]
    search_fields = ['filename', 'title', 'analysis_session__name']
    readonly_fields = [
        'uploaded_at', 'processed_at', 'duration_seconds', 'fps', 
        'total_frames', 'resolution', 'analysis_session_link_display'
    ]
    date_hierarchy = 'uploaded_at'
    autocomplete_fields = ['analysis_session', 'uploaded_by']
    
    def analysis_session_link(self, obj):
        if obj.analysis_session:
            url = reverse('admin:trapickapp_analysissession_change', args=[obj.analysis_session.id])
            return format_html('<a href="{}">{}</a>', url, obj.analysis_session.name)
        return "None"
    analysis_session_link.short_description = 'Analysis Session'
    
    def analysis_session_link_display(self, obj):
        return self.analysis_session_link(obj)
    analysis_session_link_display.short_description = 'Analysis Session'
    
    def processed_video_link(self, obj):
        if obj.processed_video_path:
            return format_html(
                '<a href="{}" target="_blank">View</a>',
                reverse('admin:view_processed_video', args=[obj.id])
            )
        return "Not available"
    processed_video_link.short_description = 'Processed Video'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('filename', 'title', 'file_path', 'uploaded_by')
        }),
        ('Video Metadata', {
            'fields': (
                'video_date', 'video_start_time', 'video_end_time',
                'original_duration', 'duration_seconds', 'fps', 
                'total_frames', 'resolution'
            )
        }),
        ('Processing Information', {
            'fields': (
                'processing_status', 'processed', 'processed_video_path',
                'processed_at'
            )
        }),
        ('Session Information', {
            'fields': ('analysis_session_link_display',)
        }),
        ('Timestamps', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'created_at']
    search_fields = ['name', 'display_name']
    readonly_fields = ['created_at']

@admin.register(TrafficAnalysis)
class TrafficAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'analysis_source', 'location', 'total_vehicles', 'congestion_level', 
        'processing_time_seconds', 'analyzed_at'
    ]
    list_filter = ['congestion_level', 'traffic_pattern', 'analyzed_at', 'location']
    search_fields = [
        'video_file__filename', 'analysis_session__name', 'location__display_name'
    ]
    readonly_fields = ['analyzed_at', 'processing_time_seconds']
    date_hierarchy = 'analyzed_at'
    autocomplete_fields = ['video_file', 'analysis_session', 'location']
    
    def analysis_source(self, obj):
        if obj.video_file:
            return f"Video: {obj.video_file.filename}"
        elif obj.analysis_session:
            return f"Session: {obj.analysis_session.name}"
        return "Unknown Source"
    analysis_source.short_description = 'Analysis Source'
    
    fieldsets = (
        ('Source Information', {
            'fields': ('video_file', 'analysis_session', 'location')
        }),
        ('Vehicle Counts', {
            'fields': (
                'total_vehicles', 'car_count', 'truck_count', 
                'motorcycle_count', 'bus_count', 'bicycle_count', 'other_count'
            )
        }),
        ('Traffic Metrics', {
            'fields': (
                'peak_traffic', 'average_traffic', 'congestion_level', 
                'traffic_pattern', 'processing_time_seconds'
            )
        }),
        ('Analysis Data', {
            'fields': ('analysis_data', 'metrics_summary'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('analyzed_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin):
    list_display = [
        'vehicle_type', 'video_file', 'traffic_analysis_source', 
        'frame_number', 'confidence', 'timestamp'
    ]
    list_filter = ['vehicle_type', 'video_file', 'timestamp', 'in_counting_zone']
    search_fields = [
        'video_file__filename', 'vehicle_type__name', 
        'traffic_analysis__video_file__filename'
    ]
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    autocomplete_fields = ['video_file', 'traffic_analysis', 'vehicle_type', 'location']
    
    def traffic_analysis_source(self, obj):
        if obj.traffic_analysis:
            if obj.traffic_analysis.video_file:
                return f"Video Analysis"
            elif obj.traffic_analysis.analysis_session:
                return f"Session Analysis"
        return "No Analysis"
    traffic_analysis_source.short_description = 'Analysis Type'

@admin.register(FrameAnalysis)
class FrameAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'traffic_analysis_source', 'frame_number', 'timestamp_seconds', 
        'total_vehicles', 'congestion_level'
    ]
    list_filter = ['congestion_level', 'traffic_analysis__location']
    search_fields = ['traffic_analysis__video_file__filename']
    readonly_fields = ['timestamp_seconds']
    autocomplete_fields = ['traffic_analysis']
    
    def traffic_analysis_source(self, obj):
        analysis = obj.traffic_analysis
        if analysis.video_file:
            return f"Video: {analysis.video_file.filename}"
        elif analysis.analysis_session:
            return f"Session: {analysis.analysis_session.name}"
        return "Unknown Source"
    traffic_analysis_source.short_description = 'Analysis Source'

@admin.register(TrafficReport)
class TrafficReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'location', 'generated_at']
    list_filter = ['report_type', 'location', 'generated_at']
    search_fields = ['title', 'executive_summary', 'location__display_name']
    readonly_fields = ['generated_at']
    date_hierarchy = 'generated_at'
    autocomplete_fields = ['traffic_analysis', 'location']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('title', 'report_type', 'traffic_analysis', 'location')
        }),
        ('Content', {
            'fields': ('executive_summary', 'key_findings', 'insights', 'recommendations')
        }),
        ('Data Summary', {
            'fields': ('total_vehicles_period', 'average_daily_traffic', 'peak_hours', 'congestion_trends')
        }),
        ('Predictions', {
            'fields': ('predictions',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('generated_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(HourlyTrafficSummary)
class HourlyTrafficSummaryAdmin(admin.ModelAdmin):
    list_display = ['date', 'hour', 'vehicle_type', 'location', 'count', 'average_confidence']
    list_filter = ['date', 'vehicle_type', 'location']
    search_fields = ['location__display_name', 'vehicle_type__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'date'
    autocomplete_fields = ['vehicle_type', 'location']

@admin.register(DailyTrafficSummary)
class DailyTrafficSummaryAdmin(admin.ModelAdmin):
    list_display = ['date', 'vehicle_type', 'location', 'total_count', 'peak_hour', 'average_daily_congestion']
    list_filter = ['date', 'vehicle_type', 'location', 'average_daily_congestion']
    search_fields = ['location__display_name', 'vehicle_type__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'date'
    autocomplete_fields = ['vehicle_type', 'location']

@admin.register(TrafficPrediction)
class TrafficPredictionAdmin(admin.ModelAdmin):
    list_display = [
        'prediction_date', 'hour_of_day', 'location', 'predicted_vehicle_count', 
        'predicted_congestion', 'confidence_score', 'model_version'
    ]
    list_filter = [
        'prediction_date', 'location', 'predicted_congestion', 'model_version'
    ]
    search_fields = ['location__display_name']
    readonly_fields = ['prediction_generated_at']
    date_hierarchy = 'prediction_date'
    autocomplete_fields = ['location']

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'description', 'updated_at']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Configuration', {
            'fields': ('key', 'value', 'description')
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )