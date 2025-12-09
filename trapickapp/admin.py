# trapickapp/admin.py
from django.contrib import admin
from .models import *

class ProcessingProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'road_type', 'active']
    list_filter = ['road_type', 'active']
    search_fields = ['name', 'display_name']

class LocationAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'processing_profile', 'active']
    list_filter = ['active', 'processing_profile']
    search_fields = ['name', 'display_name']

class VideoFileAdmin(admin.ModelAdmin):
    list_display = ['filename', 'video_date', 'processing_status', 'processed']
    list_filter = ['processing_status', 'processed', 'video_date']
    search_fields = ['filename']

class TrafficAnalysisAdmin(admin.ModelAdmin):
    list_display = ['video_file', 'location', 'total_vehicles', 'congestion_level']
    list_filter = ['congestion_level', 'location']
    search_fields = ['video_file__filename']

# Register your models with custom admin classes
admin.site.register(ProcessingProfile, ProcessingProfileAdmin)
admin.site.register(Location, LocationAdmin)
admin.site.register(VideoFile, VideoFileAdmin)
admin.site.register(TrafficAnalysis, TrafficAnalysisAdmin)

# Register other models simply
admin.site.register(LocationDateGroup)
admin.site.register(VehicleType)
admin.site.register(Detection)
admin.site.register(FrameAnalysis)
admin.site.register(TrafficReport)
admin.site.register(HourlyTrafficSummary)
admin.site.register(DailyTrafficSummary)
admin.site.register(TrafficPrediction)
admin.site.register(SystemConfig)