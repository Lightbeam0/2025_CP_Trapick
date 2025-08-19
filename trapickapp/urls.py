from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('api/upload/', views.VideoUploadView.as_view(), name='video-upload'),
    path('api/analyze/', views.TrafficAnalysisView.as_view(), name='traffic-analysis'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)