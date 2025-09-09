from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import action
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from celery import shared_task
from django.db.models import Sum
import os
from django.views.generic import TemplateView
from .models import VideoFile, Detection, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction, VehicleType
from .serializers import VideoFileSerializer
from .utils.detection import VehicleDetector
from .utils.analysis import analyze_traffic_patterns, predict_congestion
import sklearn



# ------------------ API HELLO ------------------
@method_decorator(csrf_exempt, name='dispatch')
class HelloAPI(View):
    def get(self, request):
        return JsonResponse({
            'message': 'Hello from Django API!',
            'status': 'success'
        })


# ------------------ VIDEO UPLOAD ------------------
class VideoFileViewSet(viewsets.ModelViewSet):
    queryset = VideoFile.objects.all()
    serializer_class = VideoFileSerializer

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        video = self.get_object()
        if video.processed:
            return Response({'status': 'already processed'})

        # Start async task
        process_video.delay(str(video.id))
        return Response({'status': 'processing started'})


class VideoUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        serializer = VideoFileSerializer(data=request.data)
        if serializer.is_valid():
            video = serializer.save()

            # Run detection immediately (or you can delegate to Celery)
            detector = VehicleDetector()
            results = detector.process_video(video.file_path.path)

            # Save detections
            for det in results.get("detections", []):
                Detection.objects.create(
                    video_file=video,
                    frame_number=det["frame"],
                    timestamp=det["timestamp"],
                    vehicle_type=VehicleType.objects.get_or_create(name=det["vehicle_type"])[0],
                    confidence=det["confidence"],
                    bbox_x=det["bbox"][0],
                    bbox_y=det["bbox"][1],
                    bbox_width=det["bbox"][2],
                    bbox_height=det["bbox"][3],
                )

            # Save hourly summaries
            for hour, counts in results.get("hourly_counts", {}).items():
                for vtype, count in counts.items():
                    vobj, _ = VehicleType.objects.get_or_create(name=vtype)
                    HourlyTrafficSummary.objects.create(
                        date=video.uploaded_at.date(),
                        hour=hour,
                        vehicle_type=vobj,
                        count=count,
                    )

            video.processed = True
            video.processing_status = "completed"
            video.save()

            return Response({"status": "success", "video_id": str(video.id)})

        return Response(serializer.errors, status=400)


# ------------------ BACKGROUND TASK ------------------
@shared_task
def process_video(video_id):
    try:
        video = VideoFile.objects.get(id=video_id)
        detector = VehicleDetector()
        video_path = os.path.join(settings.MEDIA_ROOT, video.file_path.name)
        results = detector.process_video(video_path)

        # Save detections
        for det in results.get("detections", []):
            Detection.objects.create(
                video_file=video,
                frame_number=det["frame"],
                timestamp=det["timestamp"],
                vehicle_type=VehicleType.objects.get_or_create(name=det["vehicle_type"])[0],
                confidence=det["confidence"],
                bbox_x=det["bbox"][0],
                bbox_y=det["bbox"][1],
                bbox_width=det["bbox"][2],
                bbox_height=det["bbox"][3],
            )

        # Save hourly summaries
        for hour, counts in results.get("hourly_counts", {}).items():
            for vtype, count in counts.items():
                vobj, _ = VehicleType.objects.get_or_create(name=vtype)
                HourlyTrafficSummary.objects.create(
                    date=video.uploaded_at.date(),
                    hour=hour,
                    vehicle_type=vobj,
                    count=count,
                )

        video.processed = True
        video.processing_status = "completed"
        video.save()

        # Trigger prediction task
        predict_congestion.delay()

    except Exception as e:
        video = VideoFile.objects.get(id=video_id)
        video.processing_status = "failed"
        video.save()
        raise e


# ------------------ TRAFFIC ANALYSIS ------------------
class TrafficAnalysisView(APIView):
    def get(self, request):
        data = (
            HourlyTrafficSummary.objects.values("hour")
            .annotate(total_vehicles=Sum("count"))
            .order_by("hour")
        )
        return Response({"data": list(data)})


class ReactAppView(TemplateView):
    template_name = "index.html"