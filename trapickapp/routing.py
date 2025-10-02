# trapickapp/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/video-progress/(?P<video_id>[^/]+)/$', consumers.VideoProgressConsumer.as_asgi()),
    re_path(r'ws/progress/(?P<video_id>[^/]+)/$', consumers.VideoProgressConsumer.as_asgi()),  # Add this for frontend compatibility
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]