from django.urls import path
from . import api_views

urlpatterns = [
    # Existing endpoints
    path('upload/video/', api_views.VideoUploadAPI.as_view(), name='upload_video'),
    path('analysis/<uuid:upload_id>/', api_views.AnalysisResultsAPI.as_view(), name='analysis_results'),
    path('videos/', api_views.VideoListAPI.as_view(), name='video_list'),
    path('locations/', api_views.LocationListAPI.as_view(), name='location_list'),
    path('health/', api_views.HealthCheckAPI.as_view(), name='health_check'),
    path('analyze/', api_views.AnalysisOverviewAPI.as_view(), name='analysis_overview'),
    path('vehicles/', api_views.VehicleStatsAPI.as_view(), name='vehicle_stats'),
    path('congestion/', api_views.CongestionDataAPI.as_view(), name='congestion_data'),
    path('progress/<uuid:video_id>/', api_views.VideoProgressAPI.as_view(), name='video_progress'),
    path('video/<uuid:video_id>/download/', api_views.ProcessedVideoDownloadAPI.as_view(), name='download_processed_video'),
    
    # NEW: Add the missing endpoints that frontend expects
    path('video/<uuid:video_id>/view/', api_views.ProcessedVideoViewAPI.as_view(), name='view_processed_video'),
    path('video/<uuid:video_id>/direct/', api_views.ProcessedVideoDirectAPI.as_view(), name='direct_processed_video'),
    path('videos/<uuid:video_id>/', api_views.VideoDeleteAPI.as_view(), name='video_delete'),
    path('export/<uuid:video_id>/csv/', api_views.ExportAnalysisCSVAPI.as_view(), name='export_csv'),
    path('export/<uuid:video_id>/pdf/', api_views.ExportAnalysisPDFAPI.as_view(), name='export_pdf'),
    path('export/<uuid:video_id>/excel/', api_views.ExportAnalysisExcelAPI.as_view(), name='export_excel'),
]