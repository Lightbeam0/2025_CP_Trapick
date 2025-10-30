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
            # Check if video file exists
            if 'video' not in request.FILES:
                print("❌ ERROR: No video file in request.FILES")
                return Response(
                    {'error': 'No video file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            video_file = request.FILES['video']
            print(f"✅ Video file received: {video_file.name} ({video_file.size} bytes)")

            # Validate file type
            allowed_types = ['video/mp4', 'video/avi', 'video/mov', 'video/webm']
            if video_file.content_type not in allowed_types:
                print(f"❌ ERROR: Invalid file type: {video_file.content_type}")
                return Response(
                    {'error': 'Invalid file type. Please upload MP4, AVI, MOV, or WebM.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # *** UPDATE: Validate file size (max 2GB to match frontend) ***
            max_size = 2 * 1024 * 1024 * 1024  # 2GB in bytes
            if video_file.size > max_size:
                print(f"❌ ERROR: File too large: {video_file.size} bytes")
                # *** UPDATE: Error message to reflect the new limit ***
                return Response(
                    {'error': 'File too large. Maximum size is 2GB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get form data
            title = request.POST.get('title', video_file.name)
            location_id = request.POST.get('location_id')
            video_date = request.POST.get('video_date')
            # NEW: Get session_id from request data
            session_id = request.POST.get('session_id')

            print(f"📝 Form data - Title: {title}, Location: {location_id}, Date: {video_date}, Session ID: {session_id}")

            # Validate required fields
            if not video_date:
                return Response(
                    {'error': 'Video recording date is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # NEW: Validate session_id if provided
            associated_session = None
            if session_id:
                try:
                    associated_session = AnalysisSession.objects.get(id=session_id)
                    print(f"📍 Video will be associated with session: {associated_session.name} (ID: {session_id})")
                    
                    # Validate video date is within session date range
                    from datetime import datetime
                    session_start = associated_session.start_datetime.date()
                    session_end = associated_session.end_datetime.date()
                    video_date_obj = datetime.strptime(video_date, '%Y-%m-%d').date()
                    
                    if not (session_start <= video_date_obj <= session_end):
                        return Response({
                            'error': f'Video date {video_date_obj} is outside session range {session_start} to {session_end}'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Optionally, check session status here if needed (e.g., only allow uploads to 'pending_upload' sessions)
                    # if associated_session.status != 'pending_upload':
                    #     return Response({'error': f'Cannot upload to session with status: {associated_session.status}'}, status=status.HTTP_400_BAD_REQUEST)
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

            # Create VideoFile record
            video_obj = VideoFile.objects.create(
                filename=video_file.name,
                file_path=filename,
                title=title,
                video_date=video_date,
                video_start_time=request.POST.get('start_time'),
                video_end_time=request.POST.get('end_time'),
                processing_status='uploaded',
                uploaded_at=timezone.now(),
                # NEW: Link to session if provided
                analysis_session=associated_session
            )

            print(f"📄 Video record created: {video_obj.id}, associated with session: {associated_session.id if associated_session else None}")

            # Determine processing logic based on session association
            if associated_session:
                # If associated with a session, do NOT start individual processing yet.
                # The session processing will handle all videos in the session later.
                print("ℹ️  Video uploaded to session. Individual processing skipped. Session processing must be initiated separately.")
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
                # If NOT associated with a session, start individual processing as before
                print("📍 Processing without session association.")
                try:
                    if location_id:
                        location = Location.objects.get(id=location_id)
                        print(f"📍 Processing with location: {location.display_name}")

                        thread = threading.Thread(
                            target=self.process_video_with_location_profile,
                            args=(video_obj.id, video_path, location_id)
                        )
                    else:
                        print("📍 Processing with default detector")
                        thread = threading.Thread(
                            target=self.process_video_background,
                            args=(video_obj.id, video_path)
                        )

                    thread.daemon = True
                    thread.start()

                    print("✅ Background processing started successfully")

                    return Response({
                        'status': 'success',
                        'message': 'Video uploaded and processing started',
                        'upload_id': str(video_obj.id),
                        'video_info': {
                            'filename': video_file.name,
                            'size': video_file.size,
                            'type': video_file.content_type
                        }
                    })

                except Exception as e:
                    print(f"❌ Error starting processing: {str(e)}")
                    video_obj.processing_status = 'failed'
                    video_obj.save()

                    return Response(
                        {'error': f'Failed to start processing: {str(e)}'},
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
    
    def process_video_with_location_profile(self, video_id, video_path, location_id):
        """Process video using location-specific detector"""
        from ml.detector_factory import DetectorFactory
        from .progress import ProgressTracker
        
        print("🔄 STARTING BACKGROUND PROCESSING")
        print(f"   - Video ID: {video_id}")
        print(f"   - Video Path: {video_path}")
        print(f"   - Location ID: {location_id}")
        
        progress_tracker = ProgressTracker(video_id)
        detector = None  # Initialize detector variable
        
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            location = Location.objects.get(id=location_id)
            
            print(f"📍 LOCATION DETAILS:")
            print(f"   - Name: {location.display_name}")
            print(f"   - Profile: {location.processing_profile.display_name}")
            print(f"   - Detector: {location.processing_profile.detector_class}")
            
            video_obj.processing_status = 'processing'
            video_obj.save()
            
            print("🔧 CREATING DETECTOR...")
            # Get detector instance - FIXED: This was causing the NameError
            detector = DetectorFactory.get_detector(location.processing_profile)
            print(f"✅ DETECTOR CREATED: {type(detector).__name__}")
            
            progress_tracker.set_progress(5, f"Starting {location.processing_profile.display_name}...")
            
            # Analyze video with progress tracking and save_output=True
            print(f"🎯 Starting video analysis with {type(detector).__name__}...")
            report = detector.analyze_video(video_path, progress_tracker, save_output=True)
            
            # Check if this is Baliwasan report
            if 'baliwasan_specific' in report:
                print("✅ BALIWASAN Y-JUNCTION ANALYSIS COMPLETED!")
                print(f"   - Total vehicles: {report['summary']['total_vehicles_counted']}")
            else:
                print("ℹ️  Generic analysis completed")
            
            progress_tracker.set_progress(95, "Saving location-optimized results...")
            
            # Create TrafficAnalysis record
            analysis = TrafficAnalysis.objects.create(
                video_file=video_obj,
                location=location,
                total_vehicles=report['summary']['total_vehicles_counted'],
                processing_time_seconds=report['metadata']['processing_time'],
                car_count=report['summary']['vehicle_breakdown'].get('car', 0),
                truck_count=report['summary']['vehicle_breakdown'].get('truck', 0),
                motorcycle_count=report['summary']['vehicle_breakdown'].get('motorcycle', 0),
                bus_count=report['summary']['vehicle_breakdown'].get('bus', 0),
                bicycle_count=report['summary']['vehicle_breakdown'].get('bicycle', 0),
                peak_traffic=report['summary']['peak_traffic'],
                average_traffic=report['summary']['average_traffic_density'],
                congestion_level=report['metrics']['congestion_level'],
                traffic_pattern=report['metrics']['traffic_pattern'],
                analysis_data=report,
                metrics_summary={
                    'processing_profile': location.processing_profile.name,
                    'location_name': location.display_name,
                    'detector_type': location.processing_profile.display_name,
                    'detector_class': type(detector).__name__
                }
            )
            
            # ✅ CRITICAL: Save processed video path to database - CORRECTED LOGIC
            if 'output_video_path' in report and report['output_video_path']:
                from django.conf import settings # Import settings
                import os # Import os

                # Get the absolute path returned by the detector
                absolute_output_path = report['output_video_path']
                print(f"🔍 Detector returned absolute path: {absolute_output_path}")

                # Convert the absolute path to a path relative to MEDIA_ROOT
                media_root_normalized = os.path.normpath(settings.MEDIA_ROOT)
                absolute_output_path_normalized = os.path.normpath(absolute_output_path)

                if absolute_output_path_normalized.startswith(media_root_normalized + os.sep):
                    relative_path = absolute_output_path_normalized[len(media_root_normalized) + len(os.sep):]
                    print(f"✅ Calculated relative path: {relative_path}")
                else:
                    print(f"❌ WARNING: Output path {absolute_output_path} is not within MEDIA_ROOT {settings.MEDIA_ROOT}")
                    relative_path = absolute_output_path

                video_obj.processed_video_path = relative_path
                video_obj.save()
                print(f"✅ Saved processed video path to database: {relative_path}")
            else:
                print("⚠️  No output_video_path in report - video may not be saved")
            
            # Update video status
            video_obj.processing_status = 'completed'
            video_obj.processed = True
            video_obj.processed_at = timezone.now()
            video_obj.save()
            
            progress_tracker.set_progress(100, f"{location.processing_profile.display_name} completed successfully!")
            progress_tracker.complete_processing("Video analysis completed!")
            
            print(f"✅ Location-based processing completed for {video_obj.filename}")
            print(f"✅ Detector used: {type(detector).__name__}")
            print(f"✅ Total vehicles counted: {analysis.total_vehicles}")
            
        except Exception as e:
            print(f"❌ Location-based processing failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Update progress with error
            progress_tracker.set_progress(0, f"Processing failed: {str(e)}")
            
            try:
                video_obj = VideoFile.objects.get(id=video_id)
                video_obj.processing_status = 'failed'
                video_obj.save()
            except:
                pass
    
    def process_video_background(self, video_id, video_path, location_id=None):
        """Process video in background thread with progress tracking"""
        from .progress import ProgressTracker
        from ml.vehicle_detector import RTXVehicleDetector
        
        progress_tracker = ProgressTracker(video_id)
        output_video_path = None
        
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'processing'
            video_obj.save()
            
            progress_tracker.set_progress(0, "Starting video analysis...")
            
            # Analyze video with progress tracking
            detector = RTXVehicleDetector()
            report = detector.analyze_video(video_path, progress_tracker, save_output=True)
            
            progress_tracker.set_progress(95, "Saving results to database...")
            
            # Get location if provided
            location = None
            if location_id:
                try:
                    location = Location.objects.get(id=location_id)
                except Location.DoesNotExist:
                    pass
            
            # Create TrafficAnalysis record
            analysis = TrafficAnalysis.objects.create(
                video_file=video_obj,
                location=location,
                total_vehicles=report['summary']['total_vehicles_counted'],
                processing_time_seconds=report['metadata']['processing_time'],
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
            
            # Save processed video path if available - CORRECTED LOGIC
            if 'output_video_path' in report and report['output_video_path']:
                from django.conf import settings # Import settings
                import os # Import os

                # Get the absolute path returned by the detector
                absolute_output_path = report['output_video_path']
                print(f"🔍 Detector returned absolute path: {absolute_output_path}")

                # Convert the absolute path to a path relative to MEDIA_ROOT
                media_root_normalized = os.path.normpath(settings.MEDIA_ROOT)
                absolute_output_path_normalized = os.path.normpath(absolute_output_path)

                if absolute_output_path_normalized.startswith(media_root_normalized + os.sep):
                    relative_path = absolute_output_path_normalized[len(media_root_normalized) + len(os.sep):]
                    print(f"✅ Calculated relative path: {relative_path}")
                else:
                    print(f"❌ WARNING: Output path {absolute_output_path} is not within MEDIA_ROOT {settings.MEDIA_ROOT}")
                    relative_path = absolute_output_path

                video_obj.processed_video_path = relative_path
                output_video_path = report['output_video_path'] # Keep original for logging
                print(f"✓ Saved processed video path: {relative_path}")
            
            # Update video status
            video_obj.processing_status = 'completed'
            video_obj.processed = True
            video_obj.save()
            
            progress_tracker.set_progress(100, "Analysis completed successfully!")
            
            print(f"✓ Video processing completed: {video_obj.filename}")
            if output_video_path:
                print(f"✓ Processed video available at: {output_video_path}")
            
        except Exception as e:
            print(f"✗ Video processing failed: {e}")
            progress_tracker.set_progress(0, f"Processing failed: {str(e)}")
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'failed'
            video_obj.save()
        finally:
            # Clear progress after 5 minutes
            import threading
            def clear_progress():
                import time
                time.sleep(300)
                progress_tracker.clear_progress()
            
            threading.Thread(target=clear_progress).start()

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
    def delete(self, request, video_id):
        """
        Delete a video analysis and associated files
        Frontend calls: DELETE /api/videos/{video_id}/
        """
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            
            # Store filename for success message
            filename = video_obj.filename
            
            # Delete associated files from filesystem
            if video_obj.file_path:
                if os.path.isfile(video_obj.file_path.path):
                    os.remove(video_obj.file_path.path)
                    print(f"✓ Deleted original video: {video_obj.file_path.path}")
            
            if video_obj.processed_video_path:
                if os.path.isfile(video_obj.processed_video_path.path):
                    os.remove(video_obj.processed_video_path.path)
                    print(f"✓ Deleted processed video: {video_obj.processed_video_path.path}")
            
            # Delete database record (this will cascade to related records)
            video_obj.delete()
            
            return Response({
                'status': 'success', 
                'message': f'Video analysis for "{filename}" deleted successfully'
            })
            
        except VideoFile.DoesNotExist:
            return Response(
                {'error': 'Video not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error deleting video {video_id}: {e}")
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
    """Generate traffic predictions based on historical data"""
    
    def post(self, request):
        try:
            from .services import generate_traffic_predictions
            
            location_id = request.data.get('location_id')
            days_ahead = int(request.data.get('days_ahead', 7))
            
            predictions = generate_traffic_predictions(location_id, days_ahead)
            
            return Response({
                'status': 'success',
                'message': f'Generated {len(predictions)} traffic predictions',
                'predictions_count': len(predictions),
                'days_ahead': days_ahead
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
            return Response({
                'status': 'error',
                'message': f'Failed to generate predictions: {str(e)}'
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
    """Handle retrieving, updating, or deleting a specific Analysis Session"""
    def get_object(self, session_id):
        try:
            return AnalysisSession.objects.get(id=session_id)
        except AnalysisSession.DoesNotExist:
            return None

    def get(self, request, session_id):
        session = self.get_object(session_id)
        if session is None:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AnalysisSessionSerializer(session)
        return Response(serializer.data)

    def put(self, request, session_id):
        session = self.get_object(session_id)
        if session is None:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        # Allow updating status, name, etc., but be careful about times if processing has started
        serializer = AnalysisSessionSerializer(session, data=request.data, partial=True) # Use partial=True for flexibility
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, session_id):
        session = self.get_object(session_id)
        if session is None:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if session is currently processing before allowing deletion
        if session.status == 'processing':
            return Response({'error': 'Cannot delete a session that is currently processing.'}, status=status.HTTP_400_BAD_REQUEST)

        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
    """Initiate processing for an Analysis Session - FIXED VERSION"""
    
    def post(self, request, session_id):
        session = AnalysisSession.objects.filter(id=session_id).first()
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        if session.status in ['processing', 'completed']:
            return Response({'error': f'Session is already {session.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check ffmpeg availability
        if not self.check_ffmpeg_available():
            return Response({
                'error': 'FFmpeg not found. Please install FFmpeg to process video sessions.'
            }, status=status.HTTP_400_BAD_REQUEST)

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

        # Start background processing task
        try:
            thread = threading.Thread(
                target=self.process_session_background,
                args=(session,)
            )
            thread.daemon = True
            thread.start()
            return Response({'message': f'Processing started for session {session.name}', 'session_id': session.id})
        except Exception as e:
            session.status = 'failed'
            session.save()
            return Response({'error': f'Failed to start processing: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def check_ffmpeg_available(self):
        """Check if ffmpeg is available in system PATH"""
        import subprocess
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            print("❌ FFmpeg not found in system PATH")
            return False

    def process_session_background(self, session, progress_tracker=None):
        """Background task to concatenate videos and run analysis - FIXED VERSION"""
        import subprocess
        import tempfile
        import os
        import threading
        
        # Create progress tracker if not provided
        if progress_tracker is None:
            from .progress import ProgressTracker
            progress_tracker = ProgressTracker(session.id)

        try:
            progress_tracker.set_progress(0, "Starting session processing...")
            session.status = 'processing'
            session.save()

            # Get sorted list of video files
            video_files = session.video_files.filter(
                processing_status__in=['uploaded', 'completed']
            ).order_by('video_date', 'video_start_time')
            
            if not video_files.exists():
                raise ValueError("No video files found in the session for processing.")

            print(f"🔄 Processing {video_files.count()} videos in session {session.name}")

            # Check if we have multiple videos to concatenate
            if video_files.count() == 1:
                # Single video - no need for concatenation
                progress_tracker.set_progress(20, "Processing single video...")
                single_video = video_files.first()
                video_path = single_video.file_path.path
                print(f"📹 Processing single video: {single_video.filename}")
                
            else:
                # Multiple videos - concatenate them
                progress_tracker.set_progress(10, "Concatenating video files...")
                
                # Create a temporary file list for ffmpeg
                temp_list_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
                temp_output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name

                try:
                    for vf in video_files:
                        # Ensure the path is absolute if needed by ffmpeg
                        abs_path = os.path.abspath(vf.file_path.path)
                        temp_list_file.write(f"file '{abs_path}'\n")
                        print(f"📹 Added video to concatenation list: {vf.filename}")
                    temp_list_file.close()

                    # Use ffmpeg to concatenate with better error handling
                    cmd = [
                        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', temp_list_file.name,
                        '-c', 'copy',
                        temp_output_path, '-y'
                    ]
                    print(f"🎬 Running ffmpeg command: {' '.join(cmd)}")
                    
                    # Run with timeout and capture output
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                          text=True, timeout=300)  # 5 minute timeout
                    
                    if result.returncode != 0:
                        print(f"❌ FFmpeg error output: {result.stderr}")
                        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

                    video_path = temp_output_path
                    progress_tracker.set_progress(30, "Concatenated successfully, starting analysis...")

                except subprocess.TimeoutExpired:
                    raise RuntimeError("FFmpeg concatenation timed out after 5 minutes")
                except Exception as e:
                    raise RuntimeError(f"Video concatenation failed: {str(e)}")

            # Load detector based on session.location.processing_profile
            from ml.detector_factory import DetectorFactory

            print(f"📍 Loading detector for session {session.name} based on location: {session.location.display_name}")
            print(f"📍 Location's profile: {session.location.processing_profile.display_name}")
            print(f"📍 Profile's detector class: {session.location.processing_profile.detector_class}")
            
            detector = DetectorFactory.get_detector(session.location.processing_profile)
            print(f"✅ Detector loaded: {type(detector).__name__}")

            # Analyze the video using the dynamically loaded detector
            report = detector.analyze_video(video_path, progress_tracker=progress_tracker, save_output=True)

            progress_tracker.set_progress(90, "Saving aggregated results...")

            # Create or update TrafficAnalysis record
            aggregated_analysis, created = TrafficAnalysis.objects.get_or_create(
                analysis_session=session,
                defaults={
                    'location': session.location,
                    'total_vehicles': report['summary']['total_vehicles_counted'],
                    'processing_time_seconds': report['metadata']['processing_time'],
                    'analyzed_at': timezone.now(),
                    'car_count': report['summary']['vehicle_breakdown'].get('car', 0),
                    'truck_count': report['summary']['vehicle_breakdown'].get('truck', 0),
                    'motorcycle_count': report['summary']['vehicle_breakdown'].get('motorcycle', 0),
                    'bus_count': report['summary']['vehicle_breakdown'].get('bus', 0),
                    'bicycle_count': report['summary']['vehicle_breakdown'].get('bicycle', 0),
                    'peak_traffic': report['summary']['peak_traffic'],
                    'average_traffic': report['summary']['average_traffic_density'],
                    'congestion_level': report['metrics']['congestion_level'],
                    'traffic_pattern': report['metrics']['traffic_pattern'],
                    'analysis_data': report,
                    'metrics_summary': {
                        'source_session_id': str(session.id),
                        'videos_processed_count': video_files.count(),
                        'aggregated_from_individual_analyses': False,
                        'detector_used_for_session': type(detector).__name__
                    }
                }
            )
            
            # If the analysis already existed, update it
            if not created:
                aggregated_analysis.total_vehicles = report['summary']['total_vehicles_counted']
                aggregated_analysis.processing_time_seconds = report['metadata']['processing_time']
                aggregated_analysis.analyzed_at = timezone.now()
                aggregated_analysis.car_count = report['summary']['vehicle_breakdown'].get('car', 0)
                aggregated_analysis.truck_count = report['summary']['vehicle_breakdown'].get('truck', 0)
                aggregated_analysis.motorcycle_count = report['summary']['vehicle_breakdown'].get('motorcycle', 0)
                aggregated_analysis.bus_count = report['summary']['vehicle_breakdown'].get('bus', 0)
                aggregated_analysis.bicycle_count = report['summary']['vehicle_breakdown'].get('bicycle', 0)
                aggregated_analysis.peak_traffic = report['summary']['peak_traffic']
                aggregated_analysis.average_traffic = report['summary']['average_traffic_density']
                aggregated_analysis.congestion_level = report['metrics']['congestion_level']
                aggregated_analysis.traffic_pattern = report['metrics']['traffic_pattern']
                aggregated_analysis.analysis_data = report
                aggregated_analysis.metrics_summary = {
                    'source_session_id': str(session.id),
                    'videos_processed_count': video_files.count(),
                    'aggregated_from_individual_analyses': False,
                    'detector_used_for_session': type(detector).__name__
                }
                aggregated_analysis.save()

            print(f"✅ Aggregated analysis {'created' if created else 'updated'}: {aggregated_analysis.id}")

            # === ENHANCED PATH HANDLING LOGIC ===
            if 'output_video_path' in report and report['output_video_path']:
                from django.conf import settings
                import os

                output_path = report['output_video_path']
                print(f"🔍 Detector returned path: {output_path}")
                print(f"🔍 MEDIA_ROOT: {settings.MEDIA_ROOT}")

                # Normalize the path (handles mixed slashes, etc.)
                normalized_path = os.path.normpath(output_path)
                
                # Check if it's already a valid path within MEDIA_ROOT
                media_root_normalized = os.path.normpath(settings.MEDIA_ROOT)
                
                # Try different approaches to find the correct relative path
                relative_path = None
                
                # Approach 1: Path is already absolute and within MEDIA_ROOT
                if os.path.isabs(normalized_path) and normalized_path.startswith(media_root_normalized):
                    relative_path = normalized_path[len(media_root_normalized):].lstrip(os.sep)
                    print(f"✅ Approach 1: Absolute path within MEDIA_ROOT → relative: {relative_path}")
                
                # Approach 2: Path is relative and starts with 'media/'
                elif normalized_path.replace('\\', '/').startswith('media/'):
                    # Remove the 'media/' prefix since MEDIA_ROOT already points to media directory
                    relative_path = normalized_path.replace('\\', '/')[6:]  # Remove 'media/'
                    print(f"✅ Approach 2: Relative path with 'media/' prefix → relative: {relative_path}")
                
                # Approach 3: Path is relative but doesn't start with 'media/'
                elif not os.path.isabs(normalized_path):
                    relative_path = normalized_path
                    print(f"✅ Approach 3: Plain relative path → using as-is: {relative_path}")
                
                # Approach 4: Try to find the path by other means
                else:
                    # Test if the path exists as-is
                    if os.path.exists(normalized_path):
                        # Try to make it relative to MEDIA_ROOT
                        try:
                            relative_path = os.path.relpath(normalized_path, media_root_normalized)
                            print(f"✅ Approach 4: Made path relative to MEDIA_ROOT: {relative_path}")
                        except ValueError:
                            # Path is on different drive, etc.
                            print(f"❌ Path is on different drive or cannot be made relative")
                            relative_path = None
                
                # Validate and assign the path
                if relative_path:
                    # Test that the file actually exists
                    test_absolute_path = os.path.join(media_root_normalized, relative_path)
                    if os.path.exists(test_absolute_path):
                        session.processed_session_video_path.name = relative_path
                        print(f"✅ Session processed video path saved: {session.processed_session_video_path.name}")
                        print(f"✅ File verified at: {test_absolute_path}")
                    else:
                        print(f"❌ Calculated path does not exist: {test_absolute_path}")
                        # Try to find the file by other means
                        found_path = self._find_video_file(settings.MEDIA_ROOT, normalized_path)
                        if found_path:
                            session.processed_session_video_path.name = found_path
                            print(f"✅ Found alternative path: {found_path}")
                        else:
                            print(f"⚠️  Could not locate video file, but saving path anyway for debugging")
                            session.processed_session_video_path.name = relative_path
                else:
                    print(f"❌ Could not determine valid relative path for: {output_path}")
                    # Don't fail the entire session just because of path issues
                    print(f"⚠️  Proceeding without video path due to path resolution issue")

            else:
                print("⚠️  No 'output_video_path' key found in the detector's report. Session video path not saved.")

            # Ensure session status and processed_at are set correctly before saving
            session.status = 'completed'
            session.processed_at = timezone.now()
            session.save()
            
            progress_tracker.set_progress(100, "Session processing completed!")
            progress_tracker.complete_processing("Session analysis completed!")

            print(f"✅ Session {session.name} processing completed successfully!")
            print(f"✅ Total vehicles counted: {aggregated_analysis.total_vehicles}")
            print(f"✅ Detector used: {type(detector).__name__}")

            # Clean up temporary files
            try:
                if 'temp_list_file' in locals():
                    os.unlink(temp_list_file.name)
                if 'temp_output_path' in locals() and video_files.count() > 1:
                    os.unlink(temp_output_path)
                print("✅ Temporary files cleaned up")
            except OSError as e:
                print(f"⚠️  Error cleaning up temporary files: {e}")

        except Exception as e:
            print(f"❌ Error processing session {session.id}: {e}")
            import traceback
            traceback.print_exc()
            session.status = 'failed'
            session.save()
            progress_tracker.set_progress(0, f"Session processing failed: {str(e)}")

    def _find_video_file(self, media_root, original_path):
        """
        Helper method to find video file when path resolution fails
        """
        import os
        import glob
        
        print(f"🔍 Searching for video file: {original_path}")
        
        # Extract filename from path
        filename = os.path.basename(original_path)
        print(f"🔍 Looking for filename: {filename}")
        
        # Search recursively in media_root
        search_pattern = os.path.join(media_root, '**', filename)
        matching_files = glob.glob(search_pattern, recursive=True)
        
        if matching_files:
            found_path = matching_files[0]
            # Convert to relative path
            relative_path = os.path.relpath(found_path, media_root)
            print(f"✅ Found video file at: {found_path}")
            print(f"✅ Relative path: {relative_path}")
            return relative_path
        
        print(f"❌ Could not find video file: {filename}")
        return None
    
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
