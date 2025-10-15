from django.urls import path, re_path

from .import views
from . import api_views

urlpatterns = [
    # ==================== VIDEO PROCESSING ENDPOINTS ====================
    path('api/upload/video/', api_views.VideoUploadAPI.as_view(), name='upload_video'),
    path('api/progress/<uuid:video_id>/', api_views.VideoProgressAPI.as_view(), name='video_progress'),
    path('api/analysis/<uuid:upload_id>/', api_views.AnalysisResultsAPI.as_view(), name='analysis_results'),
    
    # ==================== VIDEO FILE SERVING ====================
    path('api/video/<uuid:video_id>/view/', api_views.ProcessedVideoViewAPI.as_view(), name='view_processed_video'),
    path('api/video/<uuid:video_id>/download/', api_views.ProcessedVideoDownloadAPI.as_view(), name='download_processed_video'),
    path('api/video/<uuid:video_id>/direct/', api_views.ProcessedVideoDirectAPI.as_view(), name='direct_processed_video'),
    
    # ==================== VIDEO MANAGEMENT ====================
    path('api/videos/', api_views.VideoListAPI.as_view(), name='video_list'),
    path('api/videos/<uuid:video_id>/', api_views.VideoDeleteAPI.as_view(), name='video_delete'),
    
    # ==================== DATA ENDPOINTS ====================
    path('api/analyze/', api_views.AnalysisOverviewAPI.as_view(), name='analysis_overview'),
    path('api/vehicles/', api_views.VehicleStatsAPI.as_view(), name='vehicle_stats'),
    path('api/congestion/', api_views.CongestionDataAPI.as_view(), name='congestion_data'),
    path('api/locations/', api_views.LocationListAPI.as_view(), name='location_list'),
    path('api/locations/<int:location_id>/', api_views.LocationDetailAPI.as_view(), name='location_detail'),
    
    # ==================== PROCESSING PROFILES ====================
    path('api/processing-profiles/', api_views.ProcessingProfileListAPI.as_view(), name='processing_profile_list'),
    path('api/processing-profiles/<int:profile_id>/', api_views.ProcessingProfileDetailAPI.as_view(), name='processing_profile_detail'),
    
    # ==================== EXPORT ENDPOINTS ====================
    path('api/export/<uuid:video_id>/csv/', api_views.ExportAnalysisCSVAPI.as_view(), name='export_csv'),
    path('api/export/<uuid:video_id>/pdf/', api_views.ExportAnalysisPDFAPI.as_view(), name='export_pdf'),
    path('api/export/<uuid:video_id>/excel/', api_views.ExportAnalysisExcelAPI.as_view(), name='export_excel'),
    
    # ==================== PREDICTION ENDPOINTS ====================
    path('api/predictions/generate/', api_views.GeneratePredictionsAPI.as_view(), name='generate_predictions'),
    path('api/predictions/', api_views.GetPredictionsAPI.as_view(), name='get_predictions'),
    path('api/predictions/insights/', api_views.PredictionInsightsAPI.as_view(), name='prediction_insights'),
    path('api/predictions/peak-hours/', api_views.PeakHoursPredictionAPI.as_view(), name='peak_hours'),
    
    # ==================== SYSTEM ENDPOINTS ====================
    path('api/health/', api_views.HealthCheckAPI.as_view(), name='health_check'),
    path('api/debug/data/', api_views.DebugDataAPI.as_view(), name='debug_data'),
    re_path(r'ws/video-progress/(?P<video_id>[^/]+)/$', api_views.VideoProgressAPI.as_view()),
    path('api/sessions/', api_views.AnalysisSessionListAPI.as_view(), name='session_list'),
    path('api/sessions/<uuid:session_id>/', api_views.AnalysisSessionDetailAPI.as_view(), name='session_detail'),
    path('api/sessions/<uuid:session_id>/videos/', api_views.AnalysisSessionVideoListAPI.as_view(), name='session_videos'),
    path('api/sessions/<uuid:session_id>/process/', api_views.ProcessAnalysisSessionAPI.as_view(), name='process_session'),
    path('api/session-video/<uuid:session_id>/view/', api_views.SessionVideoViewAPI.as_view(), name='view_session_video'),
    path('api/video/<uuid:video_id>/view/', views.view_processed_video, name='view_processed_video'),
    path('api/video/<uuid:video_id>/download/', views.download_processed_video, name='download_processed_video'),
    path('api/session-video/<uuid:session_id>/view/', views.view_session_video, name='view_session_video'),
    path('api/session-video/<uuid:session_id>/download/', views.download_session_video, name='download_session_video'),
    path('api/sessions/<uuid:session_id>/traffic-analyses/', api_views.SessionTrafficAnalysesListAPI.as_view(), name='session_traffic_analyses'),
]