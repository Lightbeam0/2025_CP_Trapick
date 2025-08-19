from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import VideoUpload, VehicleDetection, TrafficAnalysis
from .serializers import VideoUploadSerializer
from .utils.detection import VehicleDetector
from .utils.analysis import analyze_traffic_patterns, predict_congestion
import os
from django.conf import settings
from datetime import datetime
from celery import shared_task
from django.db import transaction


class VideoUploadViewSet(viewsets.ModelViewSet):
    queryset = VideoUpload.objects.all()
    serializer_class = VideoUploadSerializer
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        video = self.get_object()
        if video.processed:
            return Response({'status': 'already processed'})
            
        # Start async processing
        process_video.delay(video.id)
        return Response({'status': 'processing started'})
    
@shared_task
def process_video(video_id):
    video = VideoUpload.objects.get(id=video_id)
    detector = VehicleDetector()
    
    video_path = os.path.join(settings.MEDIA_ROOT, video.video_file.name)
    results = detector.process_video(video_path)
    
    # Save detections
    for detection in results['detections']:
        VehicleDetection.objects.create(
            video=video,
            frame_number=detection['frame'],
            timestamp=detection['timestamp'],
            vehicle_type=detection['vehicle_type'],
            confidence=detection['confidence']
        )
    
    # Create traffic analysis
    upload_date = video.uploaded_at
    day_of_week = upload_date.weekday()  # Monday=0, Sunday=6
    
    for hour, counts in results['hourly_counts'].items():
        TrafficAnalysis.objects.create(
            video=video,
            day_of_week=day_of_week,
            hour_of_day=hour,
            vehicle_count=sum(counts.values()),
            vehicle_types=counts
        )
    
    video.processed = True
    video.save()
    
    # Generate predictions
    predict_congestion.delay()

class VideoUploadView(APIView):
    parser_classes = [MultiPartParser]
    
    def post(self, request):
        serializer = VideoUploadSerializer(data=request.data)
        if serializer.is_valid():
            video = serializer.save()
            
            # Process video in background (Celery would be better)
            detector = VehicleDetector()
            results = detector.process_video(video.video_file.path)
            # Save detection results (mimicking process_video logic)
            video_instance = video
            for detection in results.get('detections', []):
                VehicleDetection.objects.create(
                    video=video_instance,
                    frame_number=detection['frame'],
                    timestamp=detection['timestamp'],
                    vehicle_type=detection['vehicle_type'],
                    confidence=detection['confidence']
                )
            upload_date = video_instance.uploaded_at
            day_of_week = upload_date.weekday()
            for hour, counts in results.get('hourly_counts', {}).items():
                TrafficAnalysis.objects.create(
                    video=video_instance,
                    day_of_week=day_of_week,
                    hour_of_day=hour,
                    vehicle_count=sum(counts.values()),
                    vehicle_types=counts
                )
            video_instance.processed = True
            video_instance.save()
            
            return Response({'status': 'success', 'video_id': video.id})
        return Response(serializer.errors, status=400)

class TrafficAnalysisView(APIView):
    def get(self, request):
        from django.db.models import Sum
        data = TrafficAnalysis.objects.values('hour_of_day').annotate(
            total_vehicles=Sum('vehicle_count')
        ).order_by('hour_of_day')
        return Response({'data': list(data)})