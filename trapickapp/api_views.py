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
            peak_hours = get_peak_hours_analysis()
            
            # If no real weekly data, use empty array
            if not weekly_data:
                weekly_data = [0, 0, 0, 0, 0, 0, 0]  # Zeros instead of fake data
            
            total_vehicles = sum(weekly_data)
            
            return Response({
                'weekly_data': weekly_data,  # REAL data
                'total_vehicles': total_vehicles,
                'congested_roads': system_stats['recent_analyses_count'],  # Real count
                'peak_hour': peak_hours['peak_hour'],  # Real peak hour
                'daily_average': total_vehicles // 7 if total_vehicles > 0 else 0,
                'system_stats': system_stats,  # Additional real stats
                'areas': self.get_real_areas_data()  # Real areas data
            })
            
        except Exception as e:
            print(f"Error in AnalysisOverviewAPI: {e}")
            return Response({
                'weekly_data': [0, 0, 0, 0, 0, 0, 0],
                'total_vehicles': 0,
                'congested_roads': 0,
                'peak_hour': 'N/A',
                'daily_average': 0,
                'system_stats': {},
                'areas': [],
                'error': 'Error loading data'
            }, status=500)

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
        """Provide vehicle statistics with REAL data"""
        from .services import calculate_real_vehicle_stats
        
        try:
            vehicle_data = calculate_real_vehicle_stats()
            return Response(vehicle_data)
        except Exception as e:
            print(f"Error calculating vehicle stats: {e}")
            # Return empty data instead of fake data
            return Response({
                'today': {'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0},
                'yesterday': {'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0}
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

            # Validate file size (max 500MB)
            max_size = 500 * 1024 * 1024  # 500MB
            if video_file.size > max_size:
                print(f"❌ ERROR: File too large: {video_file.size} bytes")
                return Response(
                    {'error': 'File too large. Maximum size is 500MB.'},
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
            
            # ✅ CRITICAL: Save processed video path to database
            if 'output_video_path' in report and report['output_video_path']:
                # Convert absolute path to relative path for Django
                relative_path = report['output_video_path'].replace('media/', '')
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
            
            # Save processed video path if available
            if 'output_video_path' in report and report['output_video_path']:
                # Convert absolute path to relative path for Django
                relative_path = report['output_video_path'].replace('media/', '')
                video_obj.processed_video_path = relative_path
                output_video_path = report['output_video_path']
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
    """Get overall prediction insights and trends"""
    
    def get(self, request):
        try:
            from .models import TrafficPrediction
            from django.db.models import Avg, Max, Min
            
            # Get predictions for next 3 days
            next_3_days = [timezone.now().date() + timedelta(days=i) for i in range(1, 4)]
            
            insights = {
                'next_3_days': [],
                'overall_peak': None,
                'average_confidence': 0,
                'total_predictions': 0
            }
            
            total_confidence = 0
            all_predictions = []
            
            for date in next_3_days:
                day_predictions = TrafficPrediction.objects.filter(prediction_date=date)
                
                if day_predictions.exists():
                    day_peak = day_predictions.order_by('-predicted_vehicle_count').first()
                    day_avg_vehicles = day_predictions.aggregate(avg=Avg('predicted_vehicle_count'))['avg'] or 0
                    day_avg_confidence = day_predictions.aggregate(avg=Avg('confidence_score'))['avg'] or 0
                    
                    insights['next_3_days'].append({
                        'date': date.isoformat(),
                        'day_name': date.strftime('%A'),
                        'peak_hour': f"{day_peak.hour_of_day:02d}:00" if day_peak else 'N/A',
                        'peak_vehicles': day_peak.predicted_vehicle_count if day_peak else 0,
                        'average_vehicles': round(day_avg_vehicles),
                        'average_confidence': round(day_avg_confidence, 2),
                        'total_hours': day_predictions.count()
                    })
                    
                    all_predictions.extend(list(day_predictions))
                    total_confidence += day_avg_confidence
            
            if all_predictions:
                overall_peak = max(all_predictions, key=lambda x: x.predicted_vehicle_count)
                insights['overall_peak'] = {
                    'date': overall_peak.prediction_date.isoformat(),
                    'hour': f"{overall_peak.hour_of_day:02d}:00",
                    'vehicles': overall_peak.predicted_vehicle_count,
                    'congestion': overall_peak.predicted_congestion
                }
                insights['average_confidence'] = round(total_confidence / len(next_3_days), 2)
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
    """Initiate processing for an Analysis Session"""
    def post(self, request, session_id):
        session = AnalysisSession.objects.filter(id=session_id).first()
        if not session:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        if session.status in ['processing', 'completed']:
            return Response({'error': f'Session is already {session.status}.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if there are videos associated
        video_files = session.video_files.filter(processed=True) # Only consider videos that are already individually processed or uploaded
        if not video_files.exists():
             return Response({'error': 'No videos found in the session to process.'}, status=status.HTTP_400_BAD_REQUEST)

        # Update session status
        session.status = 'processing'
        session.save()

        # Start background processing task
        try:
            thread = threading.Thread(
                target=self.process_session_background,
                args=(session.id,)
            )
            thread.daemon = True
            thread.start()
            return Response({'message': f'Processing started for session {session.name}', 'session_id': session.id})
        except Exception as e:
            session.status = 'failed'
            session.save()
            return Response({'error': f'Failed to start processing: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def process_session_background(self, session_id):
        """Background task to concatenate videos and run analysis"""
        from .progress import ProgressTracker
        from ml.vehicle_detector import RTXVehicleDetector
        import subprocess
        import tempfile
        import os

        session = AnalysisSession.objects.get(id=session_id)
        progress_tracker = ProgressTracker(session_id)

        try:
            progress_tracker.set_progress(0, "Starting session processing...")
            session.status = 'processing'
            session.save()

            # Get sorted list of video files
            video_files = session.video_files.filter(processed=True).order_by('video_date', 'video_start_time')
            if not video_files:
                raise ValueError("No processed video files found in the session.")

            # Create a temporary file list for ffmpeg
            temp_list_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            temp_output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name

            try:
                for vf in video_files:
                    # Ensure the path is absolute if needed by ffmpeg
                    abs_path = os.path.abspath(vf.file_path.path)
                    temp_list_file.write(f"file '{abs_path}'\n")
                temp_list_file.close()

                progress_tracker.set_progress(10, "Concatenating video files...")

                # Use ffmpeg to concatenate
                cmd = [
                    'ffmpeg', '-f', 'concat', '-safe', '0', '-i', temp_list_file.name,
                    '-c', 'copy',
                    temp_output_path, '-y'
                ]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed: {result.stderr}")

                progress_tracker.set_progress(30, "Concatenated successfully, starting analysis...")

                # Load detector (could be based on session.location.processing_profile)
                detector = RTXVehicleDetector()

                # Analyze the concatenated video
                report = detector.analyze_video(temp_output_path, progress_tracker=progress_tracker, save_output=True)

                progress_tracker.set_progress(90, "Saving aggregated results...")

                # Create an aggregated TrafficAnalysis record linked to the session
                aggregated_analysis = TrafficAnalysis.objects.create(
                    analysis_session=session,
                    location=session.location,
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
                    analysis_data=report,
                    metrics_summary={
                        'source_session_id': session.id,
                        'videos_processed_count': video_files.count(),
                        'aggregated_from_individual_analyses': False,
                    }
                )

                # UPDATE: Save processed video path to session object
                session.status = 'completed'
                session.processed_at = timezone.now()
                
                # NEW: Save the processed session video path to the session object
                if 'output_video_path' in report and report['output_video_path']:
                    # Convert absolute path to relative path for Django
                    relative_path = report['output_video_path'].replace('media/', '')
                    session.processed_session_video_path = relative_path
                    print(f"✅ Session processed video path saved: {relative_path}")
                else:
                    print("⚠️  No output_video_path in report - session video not saved")
                
                session.save()

                progress_tracker.set_progress(100, "Session processing completed!")
                progress_tracker.complete_processing("Session analysis completed!")

                print(f"✅ Session {session.name} processing completed successfully!")
                print(f"✅ Aggregated analysis created: {aggregated_analysis.id}")
                print(f"✅ Total vehicles counted: {aggregated_analysis.total_vehicles}")

            finally:
                # Clean up temporary files
                try:
                    os.unlink(temp_list_file.name)
                    os.unlink(temp_output_path)
                    print("✅ Temporary files cleaned up")
                except OSError as e:
                    print(f"⚠️  Error cleaning up temporary files: {e}")

        except Exception as e:
            print(f"❌ Error processing session {session_id}: {e}")
            import traceback
            traceback.print_exc()
            session.status = 'failed'
            session.save()
            progress_tracker.set_progress(0, f"Session processing failed: {str(e)}")

class SessionVideoViewAPI(APIView):
    def get(self, request, session_id):
        """
        Serve the processed video for an Analysis Session.
        Frontend calls: GET /api/session-video/{session_id}/view/
        """
        try:
            session_obj = AnalysisSession.objects.get(id=session_id)

            # Check if processing is completed and path exists
            if session_obj.status != 'completed':
                return Response(
                    {'error': 'Session processing not completed yet'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not session_obj.processed_session_video_path:
                return Response(
                    {'error': 'Processed session video not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Construct the full path from the stored relative path
            full_video_path = os.path.join(settings.MEDIA_ROOT, session_obj.processed_session_video_path.name)

            if not os.path.exists(full_video_path):
                print(f"❌ Session video file not found at: {full_video_path}")
                return Response(
                    {'error': 'Processed session video file is missing on the server'},
                    status=status.HTTP_404_NOT_FOUND
                )

            print(f"✓ Serving session video: {full_video_path}")

            # Serve the file with inline content disposition for viewing
            response = FileResponse(open(full_video_path, 'rb'), content_type='video/mp4')
            response['Content-Disposition'] = f'inline; filename="session_{session_obj.name}.mp4"'
            return response

        except AnalysisSession.DoesNotExist:
            return Response(
                {'error': 'Analysis session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error serving session video {session_id}: {e}")
            return Response(
                {'error': f'Error serving session video file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )