from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from .views import HelloAPI

urlpatterns = [
    path('upload/', views.VideoUploadView.as_view(), name='video-upload'),
    path('analyze/', views.TrafficAnalysisView.as_view(), name='traffic-analysis'),
    path('hello/', HelloAPI.as_view(), name='hello_api'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
