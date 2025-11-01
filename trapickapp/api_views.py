# trapickapp/api_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse, JsonResponse, FileResponse
from django.views.static import serve
from django.conf import settings
from .models import VideoFile, TrafficAnalysis, Location
from .serializers import *
import threading
from ml.vehicle_detector import RTXVehicleDetector
from django.core.files.storage import FileSystemStorage
import os
from django.utils import timezone
from datetime import timedelta
from .progress import ProgressTracker
from .models import VideoFile, TrafficAnalysis, Location, AnalysisSession, ProcessingProfile, VehicleType, Detection, TrafficReport, FrameAnalysis, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction, SystemConfig
from django.db import models
import csv
import json
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
import openpyxl
from datetime import datetime
from .tasks import process_video_task, process_session_task

# Update these API views to use real data:

class AnalysisOverviewAPI(APIView):
    def get(self, request):
        """Provide overview data for the Home page with REAL data"""
        from .services import calculate_real_weekly_data, get_system_overview_stats, get_peak_hours_analysis
        
        try:
            # Get real data
            weekly_data = calculate_real_weekly_data()
            system_stats = get_system_overview_stats()
            areas_data = get_peak_hours_analysis()
            
            # Ensure weekly_data is always a 7-element array
            if not weekly_data or len(weekly_data) != 7:
                weekly_data = [0, 0, 0, 0, 0, 0, 0]
            
            total_vehicles = sum(weekly_data)
            
            # Ensure we have valid peak hour data
            peak_hour = '8:00 AM'
            if system_stats.get('peak_hour'):
                peak_hour = system_stats['peak_hour']
            
            # Ensure we have valid areas data
            if not areas_data:
                areas_data = [
                    {
                        'name': 'No data available',
                        'morning_peak': 'N/A',
                        'evening_peak': 'N/A', 
                        'morning_volume': 0,
                        'evening_volume': 0,
                        'total_analysis_vehicles': 0
                    }
                ]
            
            response_data = {
                'weekly_data': weekly_data,
                'total_vehicles': total_vehicles,
                'congested_roads': system_stats.get('congested_roads', 0),
                'peak_hour': peak_hour,
                'daily_average': total_vehicles // 7 if total_vehicles > 0 else 0,
                'system_stats': system_stats,
                'areas': areas_data
            }
            
            print("📊 Sending overview data:", response_data)
            return Response(response_data)
            
        except Exception as e:
            print(f"❌ Error in AnalysisOverviewAPI: {e}")
            import traceback
            traceback.print_exc()
            
            # Return safe fallback data
            return Response({
                'weekly_data': [0, 0, 0, 0, 0, 0, 0],
                'total_vehicles': 0,
                'congested_roads': 0,
                'peak_hour': 'N/A',
                'daily_average': 0,
                'system_stats': {},
                'areas': [],
                'error': 'Error loading data'
            }, status=200)  # Still return 200 to prevent frontend error

    def get_real_areas_data(self):
        """Get real area data from recent analyses"""
        try:
            recent_analyses = TrafficAnalysis.objects.filter(
                location__isnull=False
            ).select_related('location').order_by('-analyzed_at')[:5]
            
            areas = []
            for analysis in recent_analyses:
                # Calculate metrics for this area
                video_duration_hours = analysis.video_file.duration_seconds / 3600 if analysis.video_file.duration_seconds else 1
                vehicles_per_hour = analysis.total_vehicles / video_duration_hours if video_duration_hours > 0 else 0
                
                areas.append({
                    'name': analysis.location.display_name,
                    'morning_peak': '7:30 - 9:00 AM',
                    'evening_peak': '4:30 - 6:30 PM',
                    'morning_volume': int(vehicles_per_hour * 0.4),
                    'evening_volume': int(vehicles_per_hour * 0.35),
                    'total_analysis_vehicles': analysis.total_vehicles
                })
            
            # If no real data, return empty
            if not areas:
                return [
                    {
                        'name': 'No data available',
                        'morning_peak': 'N/A',
                        'evening_peak': 'N/A', 
                        'morning_volume': 0,
                        'evening_volume': 0,
                        'total_analysis_vehicles': 0
                    }
                ]
            
            return areas
            
        except Exception as e:
            print(f"Error getting areas data: {e}")
            return []

class VehicleStatsAPI(APIView):
    def get(self, request):
        """Provide vehicle statistics with REAL data and filtering"""
        from .services import calculate_real_vehicle_stats
        
        try:
            # Get filter parameters
            period = request.GET.get('period', 'today')
            location_id = request.GET.get('location_id')
            date_range = request.GET.get('date_range', 'last_7_days')
            
            vehicle_data = calculate_real_vehicle_stats(period, location_id, date_range)
            return Response(vehicle_data)
        except Exception as e:
            print(f"Error calculating vehicle stats: {e}")
            return Response({
                'today': {'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0},
                'yesterday': {'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0},
                'summary': {'total_analyses': 0, 'average_daily': 0, 'data_source': 'Error loading data'}
            })

class CongestionDataAPI(APIView):
    def get(self, request):
        """Provide congestion data with REAL data"""
        from .services import calculate_real_congestion_data
        
        try:
            congestion_data = calculate_real_congestion_data()
            return Response(congestion_data)
        except Exception as e:
            print(f"Error calculating congestion data: {e}")
            return Response([])  # Return empty array instead of fake data

class DebugDataAPI(APIView):
    """Debug endpoint to check what data exists"""
    def get(self, request):
        from .models import VideoFile, TrafficAnalysis, Detection
        
        stats = {
            'total_videos': VideoFile.objects.count(),
            'processed_videos': VideoFile.objects.filter(processed=True).count(),
            'total_analyses': TrafficAnalysis.objects.count(),
            'total_detections': Detection.objects.count(),
            'recent_analyses': TrafficAnalysis.objects.order_by('-analyzed_at').values('id', 'video_file__filename', 'analyzed_at', 'total_vehicles')[:5],
            'recent_detections': Detection.objects.order_by('-timestamp').values('id', 'vehicle_type__name', 'timestamp')[:5]
        }
        
        return Response(stats)

class VideoUploadAPI(APIView):
    def post(self, request):
        print("🔍 DEBUG: VideoUploadAPI called")
        print(f"🔍 Request method: {request.method}")
        print(f"🔍 Request FILES: {list(request.FILES.keys())}")
        print(f"🔍 Request data: {dict(request.POST)}")

        try:
            if 'video' not in request.FILES:
                print("❌ ERROR: No video file in request.FILES")
                return Response(
                    {'error': 'No video file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            video_file = request.FILES['video']
            print(f"✅ Video file received: {video_file.name} ({video_file.size} bytes)")

            allowed_types = ['video/mp4', 'video/avi', 'video/mov', 'video/webm']
            if video_file.content_type not in allowed_types:
                print(f"❌ ERROR: Invalid file type: {video_file.content_type}")
                return Response(
                    {'error': 'Invalid file type. Please upload MP4, AVI, MOV, or WebM.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            max_size = 2 * 1024 * 1024 * 1024  # 2GB
            if video_file.size > max_size:
                print(f"❌ ERROR: File too large: {video_file.size} bytes")
                return Response(
                    {'error': 'File too large. Maximum size is 2GB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            title = request.POST.get('title', video_file.name)
            location_id = request.POST.get('location_id')
            video_date = request.POST.get('video_date')
            session_id = request.POST.get('session_id')

            print(f"📝 Form data - Title: {title}, Location: {location_id}, Date: {video_date}, Session ID: {session_id}")

            if not video_date:
                return Response(
                    {'error': 'Video recording date is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate session_id if provided
            associated_session = None
            if session_id:
                try:
                    associated_session = AnalysisSession.objects.get(id=session_id)
                    print(f"📍 Video will be associated with session: {associated_session.name} (ID: {session_id})")

                    session_start = associated_session.start_datetime.date()
                    session_end = associated_session.end_datetime.date()
                    video_date_obj = datetime.strptime(video_date, '%Y-%m-%d').date()

                    if not (session_start <= video_date_obj <= session_end):
                        return Response({
                            'error': f'Video date {video_date_obj} is outside session range {session_start} to {session_end}'
                        }, status=status.HTTP_400_BAD_REQUEST)

                except AnalysisSession.DoesNotExist:
                    print(f"❌ ERROR: Session ID {session_id} does not exist.")
                    return Response(
                        {'error': f'Session with ID {session_id} not found.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Save video file
            fs = FileSystemStorage()
            filename = fs.save(f'videos/{video_file.name}', video_file)
            video_path = fs.path(filename)
            print(f"💾 Video saved to: {video_path}")

            # Create VideoFile record (initially without session if not provided)
            video_obj = VideoFile.objects.create(
                filename=video_file.name,
                file_path=filename,
                title=title,
                video_date=video_date,
                video_start_time=request.POST.get('start_time'),
                video_end_time=request.POST.get('end_time'),
                processing_status='uploaded',
                uploaded_at=timezone.now(),
                analysis_session=associated_session  # May be None
            )

            print(f"📄 Video record created: {video_obj.id}, session: {associated_session.id if associated_session else None}")

            # 🔥 AUTO-GROUPING LOGIC (only if no session was explicitly provided)
            if not session_id and video_obj.video_date and location_id:
                try:
                    video_date_obj = datetime.strptime(video_obj.video_date, '%Y-%m-%d').date()
                    existing_session = AnalysisSession.objects.filter(
                        start_datetime__date=video_date_obj,
                        location_id=location_id,
                        status='pending_upload'
                    ).first()

                    if existing_session:
                        video_obj.analysis_session = existing_session
                        video_obj.save()
                        associated_session = existing_session  # Update reference for later logic
                        print(f"✅ Auto-added to existing session: {existing_session.name}")
                except Exception as e:
                    print(f"⚠️  Warning during auto-grouping: {str(e)}")

            # Determine processing logic based on final session association
            if associated_session:
                print("ℹ️  Video uploaded to session. Individual processing skipped.")
                return Response({
                    'status': 'success',
                    'message': f'Video uploaded successfully to session "{associated_session.name}". Session processing will start separately.',
                    'upload_id': str(video_obj.id),
                    'session_id': str(associated_session.id),
                    'video_info': {
                        'filename': video_file.name,
                        'size': video_file.size,
                        'type': video_file.content_type
                    }
                })
            else:
                # Process individually
                print("📍 Processing without session association via Celery task.")
                try:
                    task = process_video_task.delay(video_obj.id, location_id=location_id)
                    print(f"✅ Celery task started: {task.id} for video {video_obj.id}")

                    return Response({
                        'status': 'success',
                        'message': 'Video uploaded and processing started (via Celery)',
                        'upload_id': str(video_obj.id),
                        'task_id': task.id,
                        'video_info': {
                            'filename': video_file.name,
                            'size': video_file.size,
                            'type': video_file.content_type
                        }
                    })

                except Exception as e:
                    print(f"❌ Error starting Celery processing: {str(e)}")
                    video_obj.processing_status = 'failed'
                    video_obj.save()
                    return Response(
                        {'error': f'Failed to start processing via Celery: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

        except Exception as e:
            print(f"💥 UPLOAD ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Upload failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VideoProgressAPI(APIView):
    def get(self, request, video_id):
        """Get progress for a video processing"""
        progress_tracker = ProgressTracker(video_id)
        progress_data = progress_tracker.get_progress()
        
        if progress_data:
            return Response(progress_data)
        else:
            return Response({'progress': 0, 'message': 'No progress data available'})
    
    # Add this method to handle WebSocket connections
    def dispatch(self, request, *args, **kwargs):
        if request.META.get('HTTP_UPGRADE', '').lower() == 'websocket':
            # Handle WebSocket connection here or return appropriate response
            return Response({'error': 'WebSocket not supported via HTTP'}, status=400)
        return super().dispatch(request, *args, **kwargs)

class AnalysisResultsAPI(APIView):
    def get(self, request, upload_id):
        try:
            video_obj = VideoFile.objects.get(id=upload_id)
            
            if video_obj.processing_status != 'completed':
                return Response({
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
                
                serializer = AnalysisSummarySerializer(analysis_data)
                return Response({
                    'status': 'completed',
                    'analysis': serializer.data,
                    'video_info': {
                        'filename': video_obj.filename,
                        'uploaded_at': video_obj.uploaded_at.isoformat(),
                        'duration': video_obj.duration_seconds
                    }
                })
            else:
                return Response({
                    'status': 'completed',
                    'message': 'No analysis data available'
                })
                
        except VideoFile.DoesNotExist:
            return Response(
                {'error': 'Video not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class VideoListAPI(APIView):
    def get(self, request):
        videos = VideoFile.objects.all().order_by('-uploaded_at')
        serializer = VideoFileSerializer(videos, many=True)
        return Response(serializer.data)

class LocationListAPI(APIView):
    """Handle location listing and creation"""
    
    def get(self, request):
        """Get all locations"""
        locations = Location.objects.all()
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new location"""
        serializer = LocationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LocationDetailAPI(APIView):
    """Handle individual location operations (GET, PUT, DELETE)"""
    
    def get_object(self, location_id):
        try:
            return Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            return None

    def get(self, request, location_id):
        """Get a specific location"""
        location = self.get_object(location_id)
        if location is None:
            return Response({'error': 'Location not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = LocationSerializer(location)
        return Response(serializer.data)

    def put(self, request, location_id):
        """Update a location - ADD DEBUG LOGGING"""
        print(f"📍 UPDATE REQUEST for location {location_id}")
        print(f"📦 Request data: {request.data}")
        
        location = self.get_object(location_id)
        if location is None:
            print("❌ Location not found")
            return Response({'error': 'Location not found'}, status=status.HTTP_404_NOT_FOUND)
        
        print(f"📝 Current location: {location.display_name}")
        
        serializer = LocationSerializer(location, data=request.data)
        if serializer.is_valid():
            serializer.save()
            print(f"✅ Location updated: {serializer.data}")
            return Response(serializer.data)
        else:
            print(f"❌ Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, location_id):
        """Delete a location"""
        location = self.get_object(location_id)
        if location is None:
            return Response({'error': 'Location not found'}, status=status.HTTP_404_NOT_FOUND)
        
        location.delete()
        return Response({'message': 'Location deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

class ProcessingProfileListAPI(APIView):
    """Handle processing profile listing and creation"""
    
    def get(self, request):
        """Get all processing profiles"""
        profiles = ProcessingProfile.objects.filter(active=True)
        serializer = ProcessingProfileSerializer(profiles, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new processing profile"""
        serializer = ProcessingProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProcessingProfileDetailAPI(APIView):
    """Handle individual processing profile operations"""
    
    def get_object(self, profile_id):
        try:
            return ProcessingProfile.objects.get(id=profile_id)
        except ProcessingProfile.DoesNotExist:
            return None

    def get(self, request, profile_id):
        """Get a specific processing profile"""
        profile = self.get_object(profile_id)
        if profile is None:
            return Response({'error': 'Processing profile not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProcessingProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request, profile_id):
        """Update a processing profile"""
        profile = self.get_object(profile_id)
        if profile is None:
            return Response({'error': 'Processing profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ProcessingProfileSerializer(profile, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, profile_id):
        """Delete a processing profile (soft delete)"""
        profile = self.get_object(profile_id)
        if profile is None:
            return Response({'error': 'Processing profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if any locations are using this profile
        if profile.locations.exists():
            return Response({
                'error': 'Cannot delete processing profile. It is being used by one or more locations.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        profile.delete()
        return Response({'message': 'Processing profile deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

class HealthCheckAPI(APIView):
    def get(self, request):
        return Response({
            'status': 'healthy',
            'ml_available': True,
            'video_count': VideoFile.objects.count(),
            'analysis_count': TrafficAnalysis.objects.count()
        })

class VideoDeleteAPI(APIView):
    """
    DELETE /api/videos/{video_id}/
    """
    def delete(self, request, video_id):
        try:
            print(f"🗑️ DELETE request for video: {video_id}")
            
            # Get the video object
            video_obj = VideoFile.objects.get(id=video_id)
            filename = video_obj.filename
            
            print(f"📹 Video found: {filename}, status: {video_obj.processing_status}")
            
            # Check if video is currently processing
            if video_obj.processing_status == 'processing':
                return Response(
                    {'error': 'Video is currently processing. Stop processing first or wait for it to complete.'},
                    status=status.HTTP_423_LOCKED
                )
            
            # Delete files from filesystem
            files_deleted = []
            if video_obj.file_path and os.path.exists(video_obj.file_path.path):
                os.remove(video_obj.file_path.path)
                files_deleted.append('original video')
                print(f"✓ Deleted original video file")
            
            if video_obj.processed_video_path and os.path.exists(video_obj.processed_video_path.path):
                os.remove(video_obj.processed_video_path.path)
                files_deleted.append('processed video') 
                print(f"✓ Deleted processed video file")
            
            # Delete from database
            video_obj.delete()
            print(f"✅ Database record deleted")
            
            return Response({
                'status': 'success',
                'message': f'Video "{filename}" deleted successfully',
                'files_deleted': files_deleted
            })
            
        except VideoFile.DoesNotExist:
            print(f"❌ Video not found: {video_id}")
            return Response(
                {'error': 'Video not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error deleting video {video_id}: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Error deleting video: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class ProcessedVideoViewAPI(APIView):
    def get(self, request, video_id):
        """
        Serve processed video for viewing (inline)
        Frontend calls: GET /api/video/{video_id}/view/
        """
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            
            # Check if processing is completed
            if video_obj.processing_status != 'completed':
                return Response(
                    {'error': 'Video processing not completed yet'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Priority 1: Check processed_video_path in database
            if video_obj.processed_video_path and os.path.exists(video_obj.processed_video_path.path):
                file_path = video_obj.processed_video_path.path
                print(f"✓ Serving processed video from database path: {file_path}")
                
                # Serve the file with inline content disposition for viewing
                response = FileResponse(open(file_path, 'rb'), content_type='video/mp4')
                response['Content-Disposition'] = f'inline; filename="processed_{video_obj.filename}"'
                return response
            
            # Priority 2: Look in processed_videos directory
            processed_videos_dir = 'media/processed_videos'
            if os.path.exists(processed_videos_dir):
                # Try to find by video ID or filename
                video_base_name = os.path.splitext(video_obj.filename)[0]
                
                for filename in os.listdir(processed_videos_dir):
                    if (video_base_name in filename or 
                        str(video_obj.id) in filename or 
                        'processed' in filename.lower()):
                        
                        file_path = os.path.join(processed_videos_dir, filename)
                        if os.path.exists(file_path):
                            print(f"✓ Found processed video in directory: {file_path}")
                            
                            # Update database with found path for future reference
                            relative_path = file_path.replace('media/', '')
                            video_obj.processed_video_path = relative_path
                            video_obj.save()
                            
                            response = FileResponse(open(file_path, 'rb'), content_type='video/mp4')
                            response['Content-Disposition'] = f'inline; filename="processed_{video_obj.filename}"'
                            return response
            
            # No processed video found
            return Response(
                {'error': 'Processed video not found. The video may still be processing or encountered an error.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
        except VideoFile.DoesNotExist:
            return Response(
                {'error': 'Video analysis not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error serving video {video_id}: {e}")
            return Response(
                {'error': f'Error serving video file: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProcessedVideoDownloadAPI(APIView):
    def get(self, request, video_id):
        """Download processed video file"""
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            
            # Check if we have a processed video path
            if video_obj.processed_video_path and os.path.exists(video_obj.processed_video_path.path):
                print(f"Serving processed video for download: {video_obj.processed_video_path.path}")
                response = FileResponse(open(video_obj.processed_video_path.path, 'rb'), content_type='video/mp4')
                response['Content-Disposition'] = f'attachment; filename="processed_{video_obj.filename}"'
                return response
            
            # Fallback: look for processed video files
            processed_videos_dir = 'media/processed_videos'
            if os.path.exists(processed_videos_dir):
                matching_files = []
                video_base_name = os.path.splitext(video_obj.filename)[0]
                
                for filename in os.listdir(processed_videos_dir):
                    if video_base_name in filename or str(video_obj.id) in filename:
                        matching_files.append(filename)
                
                if matching_files:
                    latest_file = max(matching_files, key=lambda x: os.path.getctime(os.path.join(processed_videos_dir, x)))
                    file_path = os.path.join(processed_videos_dir, latest_file)
                    print(f"Found matching processed video for download: {file_path}")
                    
                    response = FileResponse(open(file_path, 'rb'), content_type='video/mp4')
                    response['Content-Disposition'] = f'attachment; filename="processed_{video_obj.filename}"'
                    return response
            
            return Response({'error': 'No processed video available for download'}, status=404)
            
        except VideoFile.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)
        except Exception as e:
            print(f"Error serving video download: {e}")
            return Response({'error': 'Error serving video file'}, status=500)

# Simple direct file serving endpoint for development
class ProcessedVideoDirectAPI(APIView):
    def get(self, request, video_id):
        """
        Simple direct video serving endpoint (fallback)
        Frontend calls: GET /api/video/{video_id}/direct/
        """
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            
            if video_obj.processing_status != 'completed':
                return Response(
                    {'error': 'Video processing not completed'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Try multiple locations for the processed video
            possible_locations = []
            
            # 1. Database path
            if video_obj.processed_video_path:
                possible_locations.append(video_obj.processed_video_path.path)
            
            # 2. Processed videos directory
            processed_videos_dir = 'media/processed_videos'
            if os.path.exists(processed_videos_dir):
                for filename in os.listdir(processed_videos_dir):
                    if any(keyword in filename.lower() for keyword in ['processed', str(video_obj.id), os.path.splitext(video_obj.filename)[0]]):
                        possible_locations.append(os.path.join(processed_videos_dir, filename))
            
            # 3. Try the first valid file found
            for file_path in possible_locations:
                if os.path.exists(file_path):
                    print(f"✓ Direct serving video: {file_path}")
                    response = FileResponse(open(file_path, 'rb'), content_type='video/mp4')
                    response['Content-Disposition'] = f'inline; filename="processed_{video_obj.filename}"'
                    return response
            
            return Response(
                {'error': 'No processed video file found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
        except VideoFile.DoesNotExist:
            return Response(
                {'error': 'Video not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error in direct video serving: {e}")
            return Response(
                {'error': 'Error serving video file'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class ExportAnalysisCSVAPI(APIView):
    def get(self, request, video_id):
        """Export analysis data as CSV"""
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            
            if not hasattr(video_obj, 'traffic_analysis'):
                return Response({'error': 'No analysis data available'}, status=404)
            
            analysis = video_obj.traffic_analysis
            
            # Create CSV response
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="analysis_{video_obj.filename}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            writer = csv.writer(response)
            
            # Write header
            writer.writerow(['Traffic Analysis Report', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow(['Video File:', video_obj.filename])
            writer.writerow(['Upload Date:', video_obj.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")])
            writer.writerow(['Duration:', f"{video_obj.duration_seconds or 0} seconds"])
            writer.writerow([])
            
            # Summary section
            writer.writerow(['SUMMARY'])
            writer.writerow(['Total Vehicles:', analysis.total_vehicles])
            writer.writerow(['Processing Time:', f"{analysis.processing_time_seconds} seconds"])
            writer.writerow(['Congestion Level:', analysis.congestion_level])
            writer.writerow(['Traffic Pattern:', analysis.traffic_pattern])
            writer.writerow([])
            
            # Vehicle breakdown
            writer.writerow(['VEHICLE BREAKDOWN'])
            writer.writerow(['Vehicle Type', 'Count'])
            writer.writerow(['Cars', analysis.car_count])
            writer.writerow(['Trucks', analysis.truck_count])
            writer.writerow(['Motorcycles', analysis.motorcycle_count])
            writer.writerow(['Buses', analysis.bus_count])
            writer.writerow(['Bicycles', analysis.bicycle_count])
            writer.writerow(['Others', analysis.other_count])
            writer.writerow([])
            
            # Metrics
            writer.writerow(['METRICS'])
            writer.writerow(['Peak Traffic:', analysis.peak_traffic])
            writer.writerow(['Average Traffic:', analysis.average_traffic])
            
            return response
            
        except VideoFile.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class ExportAnalysisPDFAPI(APIView):
    def get(self, request, video_id):
        """Export analysis data as PDF"""
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            
            if not hasattr(video_obj, 'traffic_analysis'):
                return Response({'error': 'No analysis data available'}, status=404)
            
            analysis = video_obj.traffic_analysis
            
            # Create PDF in memory
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                textColor=colors.HexColor('#1e40af')
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=12,
                spaceAfter=12,
                textColor=colors.HexColor('#374151')
            )
            
            # Build PDF content
            content = []
            
            # Title
            content.append(Paragraph('Traffic Analysis Report', title_style))
            content.append(Paragraph(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', styles['Normal']))
            content.append(Spacer(1, 20))
            
            # Video Information
            content.append(Paragraph('Video Information', heading_style))
            video_info = [
                ['Filename:', video_obj.filename],
                ['Upload Date:', video_obj.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")],
                ['Duration:', f"{video_obj.duration_seconds or 0} seconds"],
                ['Processing Status:', video_obj.processing_status]
            ]
            video_table = Table(video_info, colWidths=[150, 300])
            video_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            content.append(video_table)
            content.append(Spacer(1, 20))
            
            # Analysis Summary
            content.append(Paragraph('Analysis Summary', heading_style))
            summary_data = [
                ['Total Vehicles:', str(analysis.total_vehicles)],
                ['Processing Time:', f"{analysis.processing_time_seconds} seconds"],
                ['Congestion Level:', analysis.congestion_level],
                ['Traffic Pattern:', analysis.traffic_pattern]
            ]
            summary_table = Table(summary_data, colWidths=[150, 300])
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ]))
            content.append(summary_table)
            content.append(Spacer(1, 20))
            
            # Vehicle Breakdown
            content.append(Paragraph('Vehicle Breakdown', heading_style))
            vehicle_data = [
                ['Vehicle Type', 'Count'],
                ['Cars', str(analysis.car_count)],
                ['Trucks', str(analysis.truck_count)],
                ['Motorcycles', str(analysis.motorcycle_count)],
                ['Buses', str(analysis.bus_count)],
                ['Bicycles', str(analysis.bicycle_count)],
                ['Other Vehicles', str(analysis.other_count)]
            ]
            vehicle_table = Table(vehicle_data, colWidths=[200, 100])
            vehicle_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
            ]))
            content.append(vehicle_table)
            
            # Build PDF
            doc.build(content)
            
            # Get PDF value from buffer
            pdf = buffer.getvalue()
            buffer.close()
            
            # Create HTTP response
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="analysis_{video_obj.filename}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
            response.write(pdf)
            
            return response
            
        except VideoFile.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class ExportAnalysisExcelAPI(APIView):
    def get(self, request, video_id):
        """Export analysis data as Excel"""
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            
            if not hasattr(video_obj, 'traffic_analysis'):
                return Response({'error': 'No analysis data available'}, status=404)
            
            analysis = video_obj.traffic_analysis
            
            # Create Excel workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Traffic Analysis"
            
            # Add headers and data
            ws.append(['Traffic Analysis Report', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            ws.append(['Video File:', video_obj.filename])
            ws.append([])
            
            # Summary section
            ws.append(['SUMMARY'])
            ws.append(['Total Vehicles:', analysis.total_vehicles])
            ws.append(['Processing Time:', analysis.processing_time_seconds])
            ws.append(['Congestion Level:', analysis.congestion_level])
            ws.append([])
            
            # Vehicle breakdown
            ws.append(['VEHICLE BREAKDOWN'])
            ws.append(['Vehicle Type', 'Count'])
            ws.append(['Cars', analysis.car_count])
            ws.append(['Trucks', analysis.truck_count])
            ws.append(['Motorcycles', analysis.motorcycle_count])
            ws.append(['Buses', analysis.bus_count])
            ws.append(['Bicycles', analysis.bicycle_count])
            ws.append(['Others', analysis.other_count])
            
            # Save to BytesIO
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            # Create HTTP response
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="analysis_{video_obj.filename}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
            
            return response
            
        except VideoFile.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
class GeneratePredictionsAPI(APIView):
    def post(self, request):
        try:
            from .services import generate_traffic_predictions  # Use the new function

            location_id = request.data.get('location_id')
            days_ahead = int(request.data.get('days_ahead', 7))

            predictions = generate_traffic_predictions(location_id, days_ahead)

            return Response({
                'status': 'success',
                'message': f'Generated {len(predictions)} traffic predictions from historical analysis data',
                'predictions_count': len(predictions),
                'days_ahead': days_ahead,
                'data_source': 'TrafficAnalysis'
            })

        except Exception as e:
            print(f"Error generating predictions: {e}")
            return Response({
                'status': 'error',
                'message': f'Failed to generate predictions: {str(e)}'
            }, status=500)

class GetPredictionsAPI(APIView):
    """Get traffic predictions for a specific date"""
    
    def get(self, request):
        try:
            from .services import get_traffic_predictions_for_date
            from .serializers import TrafficPredictionSerializer
            
            date_str = request.GET.get('date')
            location_id = request.GET.get('location_id')
            
            if date_str:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date = None
            
            predictions = get_traffic_predictions_for_date(date, location_id)
            serializer = TrafficPredictionSerializer(predictions, many=True)
            
            return Response({
                'date': date.isoformat() if date else (timezone.now().date() + timedelta(days=1)).isoformat(),
                'predictions': serializer.data,
                'total_predictions': len(predictions)
            })
            
        except Exception as e:
            print(f"Error getting predictions: {e}")
            return Response({
                'status': 'error',
                'message': f'Failed to get predictions: {str(e)}'
            }, status=500)

class PeakHoursPredictionAPI(APIView):
    """Get predicted peak traffic hours"""
    
    def get(self, request):
        try:
            from .services import get_peak_prediction_hours
            
            date_str = request.GET.get('date')
            location_id = request.GET.get('location_id')
            
            if date_str:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date = None
            
            peak_hours = get_peak_prediction_hours(date, location_id)
            
            return Response({
                'date': date.isoformat() if date else (timezone.now().date() + timedelta(days=1)).isoformat(),
                'peak_hours': peak_hours,
                'location_id': location_id
            })
            
        except Exception as e:
            print(f"Error getting peak hours: {e}")
            return Response({
                'status': 'error', 
                'message': f'Failed to get peak hours: {str(e)}'
            }, status=500)

class PredictionInsightsAPI(APIView):
    """Get overall prediction insights and trends based on actual patterns"""
    
    def get(self, request):
        try:
            from .models import TrafficPrediction
            from django.db.models import Avg, Max, Min
            
            # Get predictions for next 3 days
            next_3_days = [timezone.now().date() + timedelta(days=i) for i in range(1, 4)]
            
            insights = {
                'next_3_days': [],
                'peak_hours_by_day': {},
                'overall_peak': None,
                'average_confidence': 0,
                'total_predictions': 0
            }
            
            all_predictions = []
            
            for date in next_3_days:
                day_predictions = TrafficPrediction.objects.filter(prediction_date=date)
                
                if day_predictions.exists():
                    # Find peak hours for this day
                    hourly_data = {}
                    for pred in day_predictions:
                        hourly_data[pred.hour_of_day] = hourly_data.get(pred.hour_of_day, 0) + pred.predicted_vehicle_count
                    
                    # Get top 3 peak hours
                    peak_hours = sorted(hourly_data.items(), key=lambda x: x[1], reverse=True)[:3]
                    
                    day_peak = day_predictions.order_by('-predicted_vehicle_count').first()
                    day_avg_vehicles = day_predictions.aggregate(avg=Avg('predicted_vehicle_count'))['avg'] or 0
                    day_avg_confidence = day_predictions.aggregate(avg=Avg('confidence_score'))['avg'] or 0
                    
                    insights['next_3_days'].append({
                        'date': date.isoformat(),
                        'day_name': date.strftime('%A'),
                        'peak_hours': [{'hour': f"{h:02d}:00", 'vehicles': v} for h, v in peak_hours],
                        'peak_vehicles': day_peak.predicted_vehicle_count if day_peak else 0,
                        'average_vehicles': round(day_avg_vehicles),
                        'average_confidence': round(day_avg_confidence, 2),
                        'total_hours': day_predictions.count()
                    })
                    
                    insights['peak_hours_by_day'][date.strftime('%A')] = [
                        {'hour': f"{h:02d}:00", 'vehicles': v, 'congestion': 'high'} 
                        for h, v in peak_hours
                    ]
                    
                    all_predictions.extend(list(day_predictions))
            
            if all_predictions:
                overall_peak = max(all_predictions, key=lambda x: x.predicted_vehicle_count)
                insights['overall_peak'] = {
                    'date': overall_peak.prediction_date.isoformat(),
                    'day_name': overall_peak.prediction_date.strftime('%A'),
                    'hour': f"{overall_peak.hour_of_day:02d}:00",
                    'vehicles': overall_peak.predicted_vehicle_count,
                    'congestion': overall_peak.predicted_congestion
                }
                
                total_confidence = sum(p.confidence_score for p in all_predictions)
                insights['average_confidence'] = round(total_confidence / len(all_predictions), 2)
                insights['total_predictions'] = len(all_predictions)
            
            return Response(insights)
            
        except Exception as e:
            print(f"Error getting prediction insights: {e}")
            return Response({
                'status': 'error',
                'message': f'Failed to get insights: {str(e)}'
            }, status=500)

class AnalysisSessionListAPI(APIView):
    """Handle listing and creating Analysis Sessions"""
    def get(self, request):
        sessions = AnalysisSession.objects.all().order_by('-created_at')
        serializer = AnalysisSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Validate required fields
        required_fields = ['name', 'location', 'start_datetime', 'end_datetime']
        for field in required_fields:
            if field not in request.data:
                return Response({'error': f'{field} is required'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AnalysisSessionSerializer(data=request.data)
        if serializer.is_valid():
            session = serializer.save()
            return Response(AnalysisSessionSerializer(session).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AnalysisSessionDetailAPI(APIView):
    def get_object(self, session_id):
        try:
            return AnalysisSession.objects.get(id=session_id)
        except AnalysisSession.DoesNotExist:
            return None

    def get(self, request, session_id):
        """GET /api/sessions/{session_id}/"""
        session = self.get_object(session_id)
        if session is None:
            return Response({'error': 'Session not found'}, status=404)
        serializer = AnalysisSessionSerializer(session)
        return Response(serializer.data)

    def delete(self, request, session_id):
        """DELETE /api/sessions/{session_id}/"""
        try:
            print(f"🗑️ DELETE request for session: {session_id}")
            
            session = self.get_object(session_id)
            if session is None:
                return Response({'error': 'Session not found'}, status=404)

            # Check if session is processing
            if session.status == 'processing':
                return Response(
                    {'error': 'Session is currently processing. Stop processing first or wait for it to complete.'},
                    status=423
                )
            
            session_name = session.name
            video_count = session.video_files.count()
            
            print(f"📁 Session found: {session_name}, videos: {video_count}, status: {session.status}")
            
            # Delete session (this will cascade delete videos due to ForeignKey)
            session.delete()
            
            print(f"✅ Successfully deleted session: {session_name}")
            
            return Response({
                'message': f'Session "{session_name}" and {video_count} associated videos deleted successfully'
            })
            
        except Exception as e:
            print(f"❌ Error deleting session {session_id}: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Error deleting session: {str(e)}'},
                status=500
            )
        
class AnalysisSessionVideoListAPI(APIView):
    """Handle listing videos associated with a specific Analysis Session"""
    def get(self, request, session_id):
        session = AnalysisSession.objects.filter(id=session_id).first()
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        videos = session.video_files.all().order_by('video_date', 'video_start_time') # Order by date/time
        serializer = VideoFileSerializer(videos, many=True)
        return Response(serializer.data)
    
class ProcessAnalysisSessionAPI(APIView):
    """Initiate processing for an Analysis Session - UPDATED FOR CELERY"""
    
    def post(self, request, session_id):
        session = AnalysisSession.objects.filter(id=session_id).first()
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        if session.status in ['processing', 'completed']:
            return Response({'error': f'Session is already {session.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if there are videos associated with the session
        video_files = session.video_files.filter(
            processing_status__in=['uploaded', 'completed']
        ).order_by('video_date', 'video_start_time')
        
        print(f"🔍 Found {video_files.count()} videos ready for session processing in session {session_id}")

        if not video_files.exists():
            # Debug: Check if there are ANY videos linked to the session at all
            all_session_videos = session.video_files.all()
            print(f"🔍 Found {all_session_videos.count()} total videos linked to session {session_id}")
            for v in all_session_videos:
                print(f"   - Video {v.id}: {v.filename}, Status: {v.processing_status}, Processed: {v.processed}")
            # End Debug

            return Response({'error': 'No videos found in the session to process.'}, status=status.HTTP_400_BAD_REQUEST)

        # Update session status
        session.status = 'processing'
        session.save()

        # Start Celery task
        try:
            task = process_session_task.delay(session.id)
            print(f"✅ Celery session task started: {task.id} for session {session.id}")
            return Response({
                'message': f'Processing started for session {session.name}',
                'session_id': session.id,
                'task_id': task.id # Return task ID if needed for frontend tracking
            })
        except Exception as e:
            session.status = 'failed'
            session.save()
            return Response({'error': f'Failed to start processing via Celery: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class SessionVideoDownloadAPI(APIView):
    """
    Download the processed video for an Analysis Session.
    Frontend calls: GET /api/session-video/{session_id}/download/
    """
    
    def get(self, request, session_id):
        try:
            session_obj = AnalysisSession.objects.get(id=session_id)

            # Check if processing is completed
            if session_obj.status != 'completed':
                return Response(
                    {'error': 'Session processing not completed yet'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if the processed video path field has content
            if not session_obj.processed_session_video_path:
                return Response(
                    {'error': 'Processed session video path not found in database. The session might not have been processed correctly or the video path was not saved.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Construct the full file system path
            try:
                full_video_path = session_obj.processed_session_video_path.path
                print(f"🔍 Using FileField.path: {full_video_path}")
            except Exception as e:
                print(f"❌ Error getting FileField.path: {e}")
                # Fallback: manually construct path
                relative_path = session_obj.processed_session_video_path.name
                full_video_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                print(f"🔍 Using manual path construction: {full_video_path}")

            # Check if the file exists
            if not os.path.exists(full_video_path):
                print(f"❌ Session video file NOT FOUND at: {full_video_path}")
                return Response(
                    {
                        'error': f'Processed session video file is missing on the server. '
                                 f'Expected path: {full_video_path}'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            print(f"✓ Downloading session video from: {full_video_path}")

            # Verify file is readable and not empty
            try:
                file_size = os.path.getsize(full_video_path)
                if file_size == 0:
                    return Response(
                        {'error': 'Processed session video file is empty (0 bytes)'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                print(f"✓ Video file size: {file_size} bytes")
            except OSError as e:
                return Response(
                    {'error': f'Cannot access video file: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Serve the file with attachment content disposition for downloading
            response = FileResponse(open(full_video_path, 'rb'), content_type='video/mp4')
            response['Content-Disposition'] = f'attachment; filename="session_{session_obj.name}_{session_obj.id}.mp4"'
            response['Content-Length'] = str(file_size)
            return response

        except AnalysisSession.DoesNotExist:
            return Response(
                {'error': 'Analysis session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except FileNotFoundError:
            return Response(
                {'error': 'Processed session video file could not be opened. It might have been deleted.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR in SessionVideoDownloadAPI for session {session_id}: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Unexpected error downloading session video file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SessionVideoViewAPI(APIView):
    """
    Serve the processed video for an Analysis Session.
    Frontend calls: GET /api/session-video/{session_id}/view/
    """
    
    def get(self, request, session_id):
        try:
            session_obj = AnalysisSession.objects.get(id=session_id)

            # Check if processing is completed
            if session_obj.status != 'completed':
                return Response(
                    {'error': 'Session processing not completed yet'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if the processed video path field has content
            if not session_obj.processed_session_video_path:
                return Response(
                    {'error': 'Processed session video path not found in database. The session might not have been processed correctly or the video path was not saved.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Construct the full file system path
            try:
                full_video_path = session_obj.processed_session_video_path.path
                print(f"🔍 Using FileField.path: {full_video_path}")
            except Exception as e:
                print(f"❌ Error getting FileField.path: {e}")
                # Fallback: manually construct path
                relative_path = session_obj.processed_session_video_path.name
                full_video_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                print(f"🔍 Using manual path construction: {full_video_path}")

            # Check if the file exists
            if not os.path.exists(full_video_path):
                print(f"❌ Session video file NOT FOUND at: {full_video_path}")
                return Response(
                    {
                        'error': f'Processed session video file is missing on the server. '
                                 f'Expected path: {full_video_path}'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            print(f"✓ Serving session video from: {full_video_path}")

            # Verify file is readable and not empty
            try:
                file_size = os.path.getsize(full_video_path)
                if file_size == 0:
                    return Response(
                        {'error': 'Processed session video file is empty (0 bytes)'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                print(f"✓ Video file size: {file_size} bytes")
            except OSError as e:
                return Response(
                    {'error': f'Cannot access video file: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Serve the file with inline content disposition for viewing
            response = FileResponse(open(full_video_path, 'rb'), content_type='video/mp4')
            response['Content-Disposition'] = f'inline; filename="session_{session_obj.name}.mp4"'
            response['Content-Length'] = str(file_size)
            return response

        except AnalysisSession.DoesNotExist:
            return Response(
                {'error': 'Analysis session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except FileNotFoundError:
            return Response(
                {'error': 'Processed session video file could not be opened. It might have been deleted.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR in SessionVideoViewAPI for session {session_id}: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Unexpected error serving session video file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SessionTrafficAnalysesListAPI(APIView):
    def get(self, request, session_id):
        try:
            session = AnalysisSession.objects.filter(id=session_id).first()
            if not session:
                return Response(
                    {'error': 'Analysis session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # FIXED: Look for analyses where analysis_session matches the session ID
            # Also include analyses that might be linked via other methods
            session_analyses = TrafficAnalysis.objects.filter(
                models.Q(analysis_session_id=session_id) | 
                models.Q(video_file__analysis_session_id=session_id)
            ).distinct()
            
            print(f"🔍 Found {session_analyses.count()} analyses for session {session_id}")
            
            if session_analyses.exists():
                for analysis in session_analyses:
                    print(f"   - Analysis ID: {analysis.id}, Session ID: {analysis.analysis_session_id if analysis.analysis_session else 'None'}")
                    print(f"   - Video Session ID: {analysis.video_file.analysis_session_id if analysis.video_file and analysis.video_file.analysis_session else 'None'}")
            else:
                print(f"⚠️  No analyses found for session {session_id}")
                # Try to create an aggregated analysis if session is completed but no analysis exists
                if session.status == 'completed':
                    print(f"🔄 Session {session_id} is completed but has no analysis. Checking for individual video analyses...")
                    
                    # Get all individual analyses from session videos
                    individual_analyses = TrafficAnalysis.objects.filter(
                        video_file__analysis_session_id=session_id
                    )
                    
                    if individual_analyses.exists():
                        print(f"📊 Found {individual_analyses.count()} individual analyses, creating aggregated summary...")
                        
                        # Create aggregated analysis from individual analyses
                        total_vehicles = sum(analysis.total_vehicles for analysis in individual_analyses if analysis.total_vehicles)
                        car_count = sum(analysis.car_count for analysis in individual_analyses if analysis.car_count)
                        truck_count = sum(analysis.truck_count for analysis in individual_analyses if analysis.truck_count)
                        motorcycle_count = sum(analysis.motorcycle_count for analysis in individual_analyses if analysis.motorcycle_count)
                        
                        # Create aggregated analysis record
                        aggregated_analysis = TrafficAnalysis.objects.create(
                            analysis_session=session,
                            location=session.location,
                            total_vehicles=total_vehicles,
                            processing_time_seconds=sum(analysis.processing_time_seconds for analysis in individual_analyses if analysis.processing_time_seconds),
                            analyzed_at=timezone.now(),
                            car_count=car_count,
                            truck_count=truck_count,
                            motorcycle_count=motorcycle_count,
                            bus_count=sum(analysis.bus_count for analysis in individual_analyses if analysis.bus_count),
                            bicycle_count=sum(analysis.bicycle_count for analysis in individual_analyses if analysis.bicycle_count),
                            congestion_level=self.calculate_aggregated_congestion(individual_analyses),
                            traffic_pattern='aggregated',
                            analysis_data={
                                'summary': {
                                    'total_vehicles_counted': total_vehicles,
                                    'vehicle_breakdown': {
                                        'cars': car_count,
                                        'trucks': truck_count,
                                        'motorcycles': motorcycle_count
                                    }
                                },
                                'metadata': {
                                    'aggregated_from_individual': True,
                                    'individual_analyses_count': individual_analyses.count()
                                }
                            },
                            metrics_summary={
                                'aggregated_from_individual_analyses': True,
                                'individual_analyses_count': individual_analyses.count(),
                                'source': 'auto_generated_from_individuals'
                            }
                        )
                        session_analyses = TrafficAnalysis.objects.filter(id=aggregated_analysis.id)
                        print(f"✅ Created aggregated analysis: {aggregated_analysis.id}")
            
            serializer = TrafficAnalysisSerializer(session_analyses, many=True)
            return Response(serializer.data)

        except Exception as e:
            print(f"Error fetching analyses for session {session_id}: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to fetch analyses for session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def calculate_aggregated_congestion(self, analyses):
        """Calculate aggregated congestion level from individual analyses"""
        if not analyses:
            return 'low'
        
        congestion_levels = {
            'very_low': 0,
            'low': 1, 
            'medium': 2,
            'high': 3,
            'severe': 4
        }
        
        total_vehicles = sum(analysis.total_vehicles for analysis in analyses if analysis.total_vehicles)
        analysis_count = analyses.count()
        
        if analysis_count == 0:
            return 'low'
            
        avg_vehicles = total_vehicles / analysis_count
        
        if avg_vehicles > 100:
            return 'severe'
        elif avg_vehicles > 70:
            return 'high'
        elif avg_vehicles > 40:
            return 'medium'
        elif avg_vehicles > 20:
            return 'low'
        else:
            return 'very_low'

class ExportSessionCSVAPI(APIView):
    def get(self, request, session_id):
        try:
            session = AnalysisSession.objects.get(id=session_id)
            analysis = TrafficAnalysis.objects.filter(analysis_session=session).first()
            
            if not analysis:
                return Response({'error': 'No aggregated analysis data found for this session'}, status=404)

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="session_analysis_{session.name}_{session_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

            writer = csv.writer(response)

            writer.writerow(['Session Analysis Report', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow(['Session Name:', session.name])
            writer.writerow(['Location:', session.location.display_name])
            writer.writerow(['Date Range:', f"{session.start_datetime} to {session.end_datetime}"])
            writer.writerow(['Status:', session.status])
            writer.writerow(['Videos Processed:', session.video_files.count()])
            writer.writerow([])

            writer.writerow(['SUMMARY'])
            writer.writerow(['Total Vehicles:', analysis.total_vehicles])
            writer.writerow(['Processing Time:', f"{analysis.processing_time_seconds} seconds"])
            writer.writerow(['Congestion Level:', analysis.congestion_level])
            writer.writerow(['Traffic Pattern:', analysis.traffic_pattern])
            writer.writerow([])

            writer.writerow(['VEHICLE BREAKDOWN'])
            writer.writerow(['Vehicle Type', 'Count'])
            writer.writerow(['Cars', analysis.car_count])
            writer.writerow(['Trucks', analysis.truck_count])
            writer.writerow(['Motorcycles', analysis.motorcycle_count])
            writer.writerow(['Buses', analysis.bus_count])
            writer.writerow(['Bicycles', analysis.bicycle_count])
            writer.writerow(['Others', analysis.other_count])
            writer.writerow([])

            writer.writerow(['METRICS'])
            writer.writerow(['Peak Traffic:', analysis.peak_traffic])
            writer.writerow(['Average Traffic:', analysis.average_traffic])

            return response

        except AnalysisSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class ExportSessionPDFAPI(APIView):
    def get(self, request, session_id):
        try:
            session = AnalysisSession.objects.get(id=session_id)
            analysis = TrafficAnalysis.objects.filter(analysis_session=session).first()
            
            if not analysis:
                return Response({'error': 'No aggregated analysis data found for this session'}, status=404)

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                textColor=colors.HexColor('#1e40af')
            )

            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=12,
                spaceAfter=12,
                textColor=colors.HexColor('#374151')
            )

            content = []
            content.append(Paragraph('Session Traffic Analysis Report', title_style))
            content.append(Paragraph(f'Session: {session.name}', styles['Normal']))
            content.append(Paragraph(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', styles['Normal']))
            content.append(Spacer(1, 20))

            content.append(Paragraph('Session Information', heading_style))
            session_info_data = [
                ['Session Name:', session.name],
                ['Location:', session.location.display_name],
                ['Date Range:', f"{session.start_datetime.strftime('%Y-%m-%d %H:%M:%S')} to {session.end_datetime.strftime('%Y-%m-%d %H:%M:%S')}"],
                ['Status:', session.status],
                ['Videos Processed:', str(session.video_files.count())]
            ]
            session_info_table = Table(session_info_data, colWidths=[150, 300])
            session_info_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            content.append(session_info_table)
            content.append(Spacer(1, 20))

            content.append(Paragraph('Analysis Summary', heading_style))
            summary_data = [
                ['Total Vehicles:', str(analysis.total_vehicles)],
                ['Processing Time:', f"{analysis.processing_time_seconds} seconds"],
                ['Congestion Level:', analysis.congestion_level],
                ['Traffic Pattern:', analysis.traffic_pattern]
            ]
            summary_table = Table(summary_data, colWidths=[150, 300])
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ]))
            content.append(summary_table)
            content.append(Spacer(1, 20))

            content.append(Paragraph('Vehicle Breakdown', heading_style))
            vehicle_data = [
                ['Vehicle Type', 'Count'],
                ['Cars', str(analysis.car_count)],
                ['Trucks', str(analysis.truck_count)],
                ['Motorcycles', str(analysis.motorcycle_count)],
                ['Buses', str(analysis.bus_count)],
                ['Bicycles', str(analysis.bicycle_count)],
                ['Other Vehicles', str(analysis.other_count)]
            ]
            vehicle_table = Table(vehicle_data, colWidths=[200, 100])
            vehicle_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
            ]))
            content.append(vehicle_table)

            doc.build(content)

            pdf = buffer.getvalue()
            buffer.close()

            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="session_analysis_{session.name}_{session_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
            response.write(pdf)

            return response

        except AnalysisSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class ExportSessionExcelAPI(APIView):
    def get(self, request, session_id):
        try:
            session = AnalysisSession.objects.get(id=session_id)
            analysis = TrafficAnalysis.objects.filter(analysis_session=session).first()

            if not analysis:
                return Response({'error': 'No aggregated analysis data found for this session'}, status=404)

            wb = openpyxl.Workbook()
            ws = wb.active

            sanitized_session_name = (
                session.name.replace(":", "_")
                .replace("\\", "_")
                .replace("/", "_")
                .replace("?", "_")
                .replace("*", "_")
                .replace("[", "_")
                .replace("]", "_")
            )
            sheet_title = f"Session_{sanitized_session_name}"[:31]
            ws.title = sheet_title

            ws.append(['Session Analysis Report', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            ws.append(['Session Name:', session.name])
            ws.append(['Location:', session.location.display_name])
            ws.append(['Date Range:', f"{session.start_datetime} to {session.end_datetime}"])
            ws.append(['Status:', session.status])
            ws.append(['Videos Processed:', session.video_files.count()])
            ws.append([])

            ws.append(['SUMMARY'])
            ws.append(['Total Vehicles:', analysis.total_vehicles])
            ws.append(['Processing Time:', analysis.processing_time_seconds])
            ws.append(['Congestion Level:', analysis.congestion_level])
            ws.append([])

            ws.append(['VEHICLE BREAKDOWN'])
            ws.append(['Vehicle Type', 'Count'])
            ws.append(['Cars', analysis.car_count])
            ws.append(['Trucks', analysis.truck_count])
            ws.append(['Motorcycles', analysis.motorcycle_count])
            ws.append(['Buses', analysis.bus_count])
            ws.append(['Bicycles', analysis.bicycle_count])
            ws.append(['Others', analysis.other_count])

            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = (
                f'attachment; filename="session_analysis_{session.name}_{session_id}_'
                f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
            )

            return response

        except AnalysisSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class QuickProcessSessionAPI(APIView):
    def post(self, request, session_id):
        """One-click session processing"""
        try:
            from .tasks import process_session_task
            
            session = AnalysisSession.objects.get(id=session_id)
            
            if session.status != 'pending_upload':
                return Response(
                    {'error': f'Session is already {session.status}. Cannot process again.'}, 
                    status=400
                )
            
            # Check if session has videos
            if session.video_files.count() == 0:
                return Response(
                    {'error': 'Session has no videos to process'}, 
                    status=400
                )
            
            # Start the parallel processing
            task = process_session_task.delay(session_id)
            
            return Response({
                'status': 'started',
                'message': f'Session processing started for {session.video_files.count()} videos',
                'task_id': task.id,
                'videos_count': session.video_files.count()
            })
            
        except AnalysisSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        
class StopProcessingAPI(APIView):
    """Stop processing for a video or session"""
    
    def post(self, request, item_id, item_type):
        try:
            if item_type == 'video':
                item = VideoFile.objects.get(id=item_id)
                if item.processing_status == 'processing':
                    item.processing_status = 'cancelled'
                    item.save()
                    return Response({'message': 'Video processing stopped'})
                else:
                    return Response({'error': 'Video is not processing'}, status=400)
                    
            elif item_type == 'session':
                session = AnalysisSession.objects.get(id=item_id)
                if session.status == 'processing':
                    # Stop all processing videos in this session
                    processing_videos = session.video_files.filter(processing_status='processing')
                    for video in processing_videos:
                        video.processing_status = 'cancelled'
                        video.save()
                    
                    session.status = 'cancelled'
                    session.save()
                    return Response({'message': 'Session processing stopped'})
                else:
                    return Response({'error': 'Session is not processing'}, status=400)
                    
            else:
                return Response({'error': 'Invalid item type'}, status=400)
                
        except (VideoFile.DoesNotExist, AnalysisSession.DoesNotExist):
            return Response({'error': 'Item not found'}, status=404)