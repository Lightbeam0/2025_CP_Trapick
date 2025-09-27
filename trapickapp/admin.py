# trapickapp/admin.py
from django.contrib import admin
from .models import *

@admin.register(VideoFile)
class VideoFileAdmin(admin.ModelAdmin):
    list_display = ['filename', 'processing_status', 'uploaded_at', 'processed']
    list_filter = ['processing_status', 'processed', 'uploaded_at']
    search_fields = ['filename']
    readonly_fields = ['uploaded_at', 'processed_at']

@admin.register(TrafficAnalysis)
class TrafficAnalysisAdmin(admin.ModelAdmin):
    list_display = ['video_file', 'total_vehicles', 'congestion_level', 'analyzed_at']
    list_filter = ['congestion_level', 'traffic_pattern', 'analyzed_at']
    search_fields = ['video_file__filename']
    readonly_fields = ['analyzed_at']

@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'created_at']

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'active']
    list_filter = ['active']

@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin):
    list_display = ['vehicle_type', 'video_file', 'frame_number', 'confidence']
    list_filter = ['vehicle_type', 'video_file']

@admin.register(TrafficReport)
class TrafficReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'generated_at']

# Register other models
admin.site.register(FrameAnalysis)
admin.site.register(HourlyTrafficSummary)
admin.site.register(DailyTrafficSummary)
admin.site.register(TrafficPrediction)
admin.site.register(SystemConfig)