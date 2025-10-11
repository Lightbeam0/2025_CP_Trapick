# trapickapp/views.py
import json
import threading
import os
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from .models import AnalysisSession, VideoFile, TrafficAnalysis

# Import your ML module
try:
    from ml.vehicle_detector import RTXVehicleDetector
    ML_AVAILABLE = True
    print("✓ ML module imported successfully")
except ImportError as e:
    print(f"✗ ML module import error: {e}")
    ML_AVAILABLE = False

def process_video_background(video_id, video_path):
    """Process video in background thread"""
    if not ML_AVAILABLE:
        print("ML module not available - skipping video processing")
        return
        
    try:
        video_obj = VideoFile.objects.get(id=video_id)
        video_obj.processing_status = 'processing'
        video_obj.save()
        
        print(f"Starting video analysis for: {video_obj.filename}")
        
        # Analyze video
        detector = RTXVehicleDetector()
        report = detector.analyze_video(video_path)
        
        print(f"Analysis completed. Creating database record...")
        
        # Create TrafficAnalysis record
        analysis = TrafficAnalysis.objects.create(
            video_file=video_obj,
            total_vehicles=report['summary']['total_vehicles_counted'],
            processing_time_seconds=report['metadata']['processing_time'],
            analyzed_at=timezone.now(),
            car_count=report['summary']['vehicle_breakdown'].get('car', 0),
            truck_count=report['summary']['vehicle_breakdown'].get('truck', 0),
            motorcycle_count=report['summary']['vehicle_breakdown'].get('motorcycle', 0),
            bus_count=report['summary']['vehicle_breakdown'].get('bus', 0),
            bicycle_count=report['summary']['vehicle_breakdown'].get('bicycle', 0),
            peak_traffic=report['summary']['peak_traffic'],
            average_traffic=report['summary']['average_traffic_density'],
            congestion_level=report['metrics']['congestion_level'],
            traffic_pattern=report['metrics']['traffic_pattern'],
            analysis_data=report
        )
        
        # Update video status
        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()
        video_obj.save()
        
        print(f"✓ Video processing completed: {video_obj.filename}")
        
    except Exception as e:
        print(f"✗ Video processing failed: {e}")
        video_obj = VideoFile.objects.get(id=video_id)
        video_obj.processing_status = 'failed'
        video_obj.save()

@csrf_exempt
def upload_video(request):
    if request.method == 'POST' and request.FILES.get('video'):
        try:
            video_file = request.FILES['video']
            fs = FileSystemStorage()
            
            # Save video file
            filename = fs.save(f'videos/{video_file.name}', video_file)
            video_path = fs.path(filename)
            
            # Create VideoFile record
            video_obj = VideoFile.objects.create(
                filename=video_file.name,
                file_path=filename,
                processing_status='uploaded'
            )
            
            # Start background processing if ML is available
            if ML_AVAILABLE:
                thread = threading.Thread(
                    target=process_video_background,
                    args=(video_obj.id, video_path)
                )
                thread.daemon = True
                thread.start()
                message = 'Video uploaded and processing started'
            else:
                video_obj.processing_status = 'completed'
                video_obj.save()
                message = 'Video uploaded (ML processing disabled)'
            
            return JsonResponse({
                'status': 'success',
                'message': message,
                'upload_id': str(video_obj.id)
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@csrf_exempt
def get_analysis_results(request, upload_id):
    """Get analysis results for a video"""
    try:
        video_obj = VideoFile.objects.get(id=upload_id)
        
        if video_obj.processing_status != 'completed':
            return JsonResponse({
                'status': video_obj.processing_status,
                'message': 'Processing not completed yet'
            })
        
        # Check if analysis exists
        if hasattr(video_obj, 'traffic_analysis'):
            analysis = video_obj.traffic_analysis
            analysis_data = {
                'total_vehicles': analysis.total_vehicles,
                'vehicle_breakdown': analysis.get_vehicle_breakdown(),
                'processing_time': analysis.processing_time_seconds,
                'congestion_level': analysis.congestion_level,
                'traffic_pattern': analysis.traffic_pattern,
                'analyzed_at': analysis.analyzed_at.isoformat()
            }
        else:
            analysis_data = {'message': 'No analysis data available'}
        
        return JsonResponse({
            'status': 'completed',
            'analysis': analysis_data,
            'video_info': {
                'filename': video_obj.filename,
                'uploaded_at': video_obj.uploaded_at.isoformat()
            }
        })
        
    except VideoFile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Video not found'})

def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'ml_available': ML_AVAILABLE,
        'video_count': VideoFile.objects.count(),
        'analysis_count': TrafficAnalysis.objects.count()
    })

def view_processed_video(request, video_id):
    """Serve processed videos for viewing"""
    video = get_object_or_404(VideoFile, id=video_id)
    
    if video.processed_video_path:
        video_path = video.processed_video_path.path
        if os.path.exists(video_path):
            with open(video_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='video/mp4')
                response['Content-Disposition'] = f'inline; filename="{video.filename}_processed.mp4"'
                return response
    
    return HttpResponse("Video not found", status=404)

def view_session_video(request, session_id):
    """Serve processed session videos for viewing"""
    session = get_object_or_404(AnalysisSession, id=session_id)
    
    if session.processed_session_video_path:
        video_path = session.processed_session_video_path.path
        if os.path.exists(video_path):
            with open(video_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='video/mp4')
                response['Content-Disposition'] = f'inline; filename="session_{session.name}_processed.mp4"'
                return response
    
    return HttpResponse("Session video not found", status=404)

def download_processed_video(request, video_id):
    """Download processed videos"""
    video = get_object_or_404(VideoFile, id=video_id)
    
    if video.processed_video_path:
        video_path = video.processed_video_path.path
        if os.path.exists(video_path):
            with open(video_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='video/mp4')
                response['Content-Disposition'] = f'attachment; filename="{video.filename}_processed.mp4"'
                return response
    
    return HttpResponse("Video not found", status=404)

def download_session_video(request, session_id):
    """Download processed session videos"""
    session = get_object_or_404(AnalysisSession, id=session_id)
    
    if session.processed_session_video_path:
        video_path = session.processed_session_video_path.path
        if os.path.exists(video_path):
            with open(video_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='video/mp4')
                response['Content-Disposition'] = f'attachment; filename="session_{session.name}_processed.mp4"'
                return response
    
    return HttpResponse("Session video not found", status=404)