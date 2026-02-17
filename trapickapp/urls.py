# trapickapp/urls.py - REORGANIZED AND CLEANED
from django.urls import path, re_path
from . import api_views

urlpatterns = [
    # ==================== VIDEO PROCESSING ENDPOINTS ====================
    path('api/upload/video/', api_views.VideoUploadAPI.as_view(), name='upload_video'),
    path('api/progress/<uuid:video_id>/', api_views.VideoProgressAPI.as_view(), name='video_progress'),
    path('api/progress/active/', api_views.ActiveVideosProgressAPI.as_view(), name='active_progress'),
    path('api/analysis/<uuid:upload_id>/', api_views.AnalysisResultsAPI.as_view(), name='analysis_results'),

    # ==================== VIDEO FILE SERVING ====================
    path('api/video/<uuid:video_id>/view/', api_views.ProcessedVideoViewAPI.as_view(), name='view_processed_video'),
    path('api/video/<uuid:video_id>/download/', api_views.ProcessedVideoDownloadAPI.as_view(), name='download_processed_video'),
    path('api/video/<uuid:video_id>/direct/', api_views.ProcessedVideoDirectAPI.as_view(), name='direct_processed_video'),

    # ==================== VIDEO MANAGEMENT ====================
    path('api/videos/', api_views.VideoListAPI.as_view(), name='video_list'),
    path('api/videos/<uuid:video_id>/manage/', api_views.VideoManagementAPI.as_view(), name='video_manage'),
    path('api/videos/<uuid:video_id>/delete/', api_views.VideoDeleteAPI.as_view(), name='video_delete'),
    path('api/videos/ungrouped/', api_views.UngroupedVideosAPI.as_view(), name='ungrouped_videos'),

    # ==================== LOCATION MANAGEMENT ====================
    path('api/locations/', api_views.LocationListAPI.as_view(), name='location_list'),
    path('api/locations/<int:location_id>/', api_views.LocationDetailAPI.as_view(), name='location_detail'),

    # ==================== LOCATION GROUP ENDPOINTS ====================
    path('api/location-groups/', api_views.LocationDateGroupListAPI.as_view(), name='location_group_list'),
    path('api/location-groups/<uuid:group_id>/', api_views.LocationDateGroupDetailAPI.as_view(), name='location_group_detail'),
    path('api/location-groups/<uuid:group_id>/videos/', api_views.GroupVideosAPI.as_view(), name='group_videos'),
    path('api/location-groups/with-videos/', api_views.LocationGroupsWithVideosAPI.as_view(), name='location_groups_with_videos'),
    path('api/location-groups/auto-group/', api_views.AutoGroupVideosAPI.as_view(), name='auto_group_videos'),

    # ==================== LOCATION-BASED GROUP ENDPOINTS ====================
    path('api/locations/<int:location_id>/groups/', api_views.LocationGroupsAPI.as_view(), name='location_groups'),
    path('api/locations/<int:location_id>/groups/<uuid:group_id>/videos/', api_views.LocationGroupVideosAPI.as_view(), name='location_group_videos'),

    # ==================== GENERAL GROUP ENDPOINTS ====================
    path('api/groups/', api_views.AllGroupsAPI.as_view(), name='all_groups'),
    path('api/groups/<uuid:group_id>/analysis/', api_views.GroupAnalysisDetailAPI.as_view(), name='group_analysis_detail'),

    # ==================== PROCESSING PROFILES ====================
    path('api/processing-profiles/', api_views.ProcessingProfileListAPI.as_view(), name='processing_profile_list'),
    path('api/processing-profiles/<int:profile_id>/', api_views.ProcessingProfileDetailAPI.as_view(), name='processing_profile_detail'),

    # ==================== DATA & ANALYTICS ENDPOINTS ====================
    path('api/analyze/', api_views.AnalysisOverviewAPI.as_view(), name='analysis_overview'),
    path('api/vehicles/', api_views.VehicleStatsAPI.as_view(), name='vehicle_stats'),
    path('api/congestion/', api_views.CongestionDataAPI.as_view(), name='congestion_data'),

    # ==================== PREDICTION ENDPOINTS ====================
    path('api/predictions/generate/', api_views.GeneratePredictionsAPI.as_view(), name='generate_predictions'),
    path('api/predictions/', api_views.GetPredictionsAPI.as_view(), name='get_predictions'),
    path('api/predictions/insights/', api_views.PredictionInsightsAPI.as_view(), name='prediction_insights'),
    path('api/predictions/peak-hours/', api_views.PeakHoursPredictionAPI.as_view(), name='peak_hours'),

    # ==================== SYSTEM & DEBUG ENDPOINTS ====================
    path('api/health/', api_views.HealthCheckAPI.as_view(), name='health_check'),
    path('api/debug/data/', api_views.DebugDataAPI.as_view(), name='debug_data'),
    path('api/debug/urls/', api_views.DebugURLsAPI.as_view(), name='debug_urls'),
    path('api/groups/<uuid:group_id>/videos/simple/', 
     api_views.SimpleGroupVideosAPI.as_view(), 
     name='simple_group_videos'),
    path('api/debug/websocket-test/<uuid:video_id>/', api_views.DebugWebSocketTestAPI.as_view(), name='debug-websocket-test'),
    path('api/sessions/<uuid:group_id>/video-analyses/', api_views.SessionVideoAnalysesAPI.as_view(), name='session-video-analyses'),
    # ==================== AUTHENTICATION ENDPOINTS ====================
    path('api/auth/login/', api_views.LoginAPI.as_view(), name='login'),
    path('api/auth/logout/', api_views.LogoutAPI.as_view(), name='logout'),
    path('api/auth/current-user/', api_views.CurrentUserAPI.as_view(), name='current_user'),
    path('api/auth/register/', api_views.RegisterAPI.as_view(), name='register'),
    path('api/auth/check-auth/', api_views.CheckAuthAPI.as_view(), name='check_auth'),
    path('api/sync/', api_views.DataSyncAPI.as_view(), name='data_sync'),
    path('api/sync/status/', api_views.SyncStatusAPI.as_view(), name='sync_status'),
    path('api/sync/execute/', api_views.SyncExecuteAPI.as_view(), name='sync_execute'),
]