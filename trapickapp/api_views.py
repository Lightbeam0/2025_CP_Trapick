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
from django.core.exceptions import ValidationError
import os
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
from .progress import ProgressTracker
from .models import VideoFile, TrafficAnalysis, Location, ProcessingProfile, VehicleType, Detection, TrafficReport, FrameAnalysis, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction, SystemConfig, LocationDateGroup
from django.db import models
from django.db.models import Prefetch, Q, Sum
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
from .tasks import process_video_task

class VideoUploadAPI(APIView):
    def post(self, request):
        print("🔍 DEBUG: VideoUploadAPI called")
        print(f"🔍 Request FILES: {list(request.FILES.keys())}")
        print(f"🔍 Request POST data: {request.POST}")

        try:
            if 'video' not in request.FILES:
                return Response(
                    {'error': 'No video file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            video_file = request.FILES['video']
            print(f"✅ Video file received: {video_file.name} ({video_file.size} bytes)")

            # Validate file type
            allowed_types = ['video/mp4', 'video/avi', 'video/mov', 'video/webm']
            if video_file.content_type not in allowed_types:
                return Response(
                    {'error': 'Invalid file type. Please upload MP4, AVI, MOV, or WebM.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file size
            max_size = 2 * 1024 * 1024 * 1024  # 2GB
            if video_file.size > max_size:
                return Response(
                    {'error': 'File too large. Maximum size is 2GB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get form data
            title = request.POST.get('title', video_file.name)
            location_id = request.POST.get('location_id')
            video_date = request.POST.get('video_date')
            video_start_time_str = request.POST.get('start_time')
            video_end_time_str = request.POST.get('end_time')

            # Validate required fields
            if not location_id:
                return Response(
                    {'error': 'Location is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not video_date:
                return Response(
                    {'error': 'Video recording date is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate location exists
            try:
                location = Location.objects.get(id=location_id)
            except Location.DoesNotExist:
                return Response(
                    {'error': 'Location not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Save video file
            fs = FileSystemStorage()
            filename = fs.save(f'videos/{video_file.name}', video_file)
            video_path = fs.path(filename)
            print(f"💾 Video saved to: {video_path}")

            # Parse time strings if provided
            video_start_time_obj = None
            video_end_time_obj = None

            if video_start_time_str:
                try:
                    if len(video_start_time_str) == 8:  # HH:MM:SS
                        video_start_time_obj = datetime.strptime(video_start_time_str, '%H:%M:%S').time()
                    elif len(video_start_time_str) == 5:  # HH:MM
                        video_start_time_obj = datetime.strptime(video_start_time_str, '%H:%M').time()
                    else:
                        print(f"Warning: Could not parse start time format: {video_start_time_str}")
                except ValueError:
                    print(f"Warning: Error parsing start time '{video_start_time_str}'")

            if video_end_time_str:
                try:
                    if len(video_end_time_str) == 8:  # HH:MM:SS
                        video_end_time_obj = datetime.strptime(video_end_time_str, '%H:%M:%S').time()
                    elif len(video_end_time_str) == 5:  # HH:MM
                        video_end_time_obj = datetime.strptime(video_end_time_str, '%H:%M').time()
                    else:
                        print(f"Warning: Could not parse end time format: {video_end_time_str}")
                except ValueError:
                    print(f"Warning: Error parsing end time '{video_end_time_str}'")

            video_obj = VideoFile.objects.create(
                filename=video_file.name,
                file_path=filename,
                title=title,
                video_date=video_date,
                video_start_time=video_start_time_obj,
                video_end_time=video_end_time_obj,
                processing_status='uploaded',
                processing_progress=0,
                processing_message='Upload complete, starting processing...',
                uploaded_at=timezone.now()
            )

            print(f"📄 Video record created: {video_obj.id}, Start: {video_obj.video_start_time}, End: {video_obj.video_end_time}")

            # Start processing immediately via Celery
            try:
                task = process_video_task.delay(str(video_obj.id), location_id=location_id)
                print(f"✅ Celery task started: {task.id} for video {video_obj.id}")

                # CRITICAL FIX: Use 'video_id' consistently (not 'upload_id')
                response_data = {
                    'status': 'success',
                    'message': 'Video uploaded and processing started',
                    'video_id': str(video_obj.id),      # ✅ PRIMARY: Use video_id
                    'upload_id': str(video_obj.id),     # ✅ BACKWARD COMPATIBILITY: Keep upload_id
                    'id': str(video_obj.id),            # ✅ ADDITIONAL: Add id for flexibility
                    'task_id': task.id,
                    'video_info': {
                        'filename': video_file.name,
                        'size': video_file.size,
                        'type': video_file.content_type
                    }
                }

                # Include start/end time in response if they were provided/parsed
                if video_start_time_obj:
                    response_data['video_info']['start_time'] = video_start_time_str
                if video_end_time_obj:
                    response_data['video_info']['end_time'] = video_end_time_str

                print(f"📤 Sending response with video_id: {video_obj.id}")
                return Response(response_data)

            except Exception as e:
                print(f"❌ Error starting Celery processing: {str(e)}")
                video_obj.processing_status = 'failed'
                video_obj.save()
                return Response(
                    {'error': f'Failed to start processing: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except ValidationError as ve:
            print(f"Validation error: {ve}")
            return Response(
                {'error': f'Validation error: {str(ve)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"💥 UPLOAD ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Upload failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LocationDateGroupListAPI(APIView):
    """Handle location-date groups"""
    
    def get(self, request):
        groups = LocationDateGroup.objects.all().select_related('location').order_by('-date')
        serializer = LocationDateGroupSerializer(groups, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new location-date group"""
        serializer = LocationDateGroupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LocationDateGroupDetailAPI(APIView):
    """Handle individual location-date group operations"""
    
    def get_object(self, group_id):
        try:
            return LocationDateGroup.objects.get(id=group_id)
        except LocationDateGroup.DoesNotExist:
            return None

    def get(self, request, group_id):
        group = self.get_object(group_id)
        if group is None:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = LocationDateGroupSerializer(group)
        return Response(serializer.data)

    def put(self, request, group_id):
        group = self.get_object(group_id)
        if group is None:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = LocationDateGroupSerializer(group, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, group_id):
        group = self.get_object(group_id)
        if group is None:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if group has videos
        if group.videos.exists():
            return Response({
                'error': 'Cannot delete group that contains videos. Remove videos first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        group.delete()
        return Response({'message': 'Group deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

class GroupVideosAPI(APIView):
    """Add/remove videos from location-date groups"""
    
    def post(self, request, group_id):
        """Add videos to a group"""
        try:
            group = LocationDateGroup.objects.get(id=group_id)
            video_ids = request.data.get('video_ids', [])
            
            if not video_ids:
                return Response({'error': 'No video IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get videos that are completed and not already in a group
            videos = VideoFile.objects.filter(
                id__in=video_ids,
                processing_status='completed',
                location_date_group__isnull=True
            )
            
            updated_count = 0
            for video in videos:
                video.location_date_group = group
                video.save()
                updated_count += 1
            
            return Response({
                'message': f'Successfully added {updated_count} videos to group',
                'group_id': str(group_id),
                'videos_added': updated_count
            })
            
        except LocationDateGroup.DoesNotExist:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, group_id):
        """Remove videos from a group"""
        try:
            group = LocationDateGroup.objects.get(id=group_id)
            video_ids = request.data.get('video_ids', [])
            
            if not video_ids:
                return Response({'error': 'No video IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            videos = VideoFile.objects.filter(
                id__in=video_ids,
                location_date_group=group
            )
            
            updated_count = 0
            for video in videos:
                video.location_date_group = None
                video.save()
                updated_count += 1
            
            return Response({
                'message': f'Successfully removed {updated_count} videos from group',
                'videos_removed': updated_count
            })
            
        except LocationDateGroup.DoesNotExist:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

class UngroupedVideosAPI(APIView):
    """Get videos that are not in any group"""
    
    def get(self, request):
        videos = VideoFile.objects.filter(
            processing_status='completed',
            location_date_group__isnull=True
        ).order_by('-uploaded_at')
        
        serializer = VideoFileSerializer(videos, many=True)
        return Response(serializer.data)

class GroupAnalysisAPI(APIView):
    """Get aggregated analysis for a location-date group"""
    
    def get(self, request, group_id):
        try:
            group = LocationDateGroup.objects.get(id=group_id)
            videos = group.videos.filter(processing_status='completed')
            
            # Get all analyses for videos in this group
            analyses = TrafficAnalysis.objects.filter(video_file__in=videos)
            
            if not analyses.exists():
                return Response({'error': 'No analyses found for this group'}, status=status.HTTP_404_NOT_FOUND)
            
            # Calculate aggregated statistics
            aggregated_data = {
                'total_vehicles': sum(analysis.total_vehicles for analysis in analyses),
                'car_count': sum(analysis.car_count for analysis in analyses),
                'truck_count': sum(analysis.truck_count for analysis in analyses),
                'motorcycle_count': sum(analysis.motorcycle_count for analysis in analyses),
                'bus_count': sum(analysis.bus_count for analysis in analyses),
                'bicycle_count': sum(analysis.bicycle_count for analysis in analyses),
                'other_count': sum(analysis.other_count for analysis in analyses),
                'total_processing_time': sum(analysis.processing_time_seconds for analysis in analyses),
                'video_count': videos.count(),
                'time_range': self.get_time_range(videos),
                'average_congestion': self.get_average_congestion(analyses)
            }
            
            return Response(aggregated_data)
            
        except LocationDateGroup.DoesNotExist:
            return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def get_time_range(self, videos):
        """Calculate time range for videos in group"""
        times = []
        for video in videos:
            if video.video_start_time:
                times.append(video.video_start_time)
            if video.video_end_time:
                times.append(video.video_end_time)
        
        if times:
            return f"{min(times).strftime('%H:%M')} - {max(times).strftime('%H:%M')}"
        return "Time range not available"
    
    def get_average_congestion(self, analyses):
        """Calculate average congestion level"""
        congestion_levels = {
            'very_low': 0,
            'low': 1, 
            'medium': 2,
            'high': 3,
            'severe': 4
        }
        
        if not analyses:
            return 'low'
        
        total_score = sum(congestion_levels.get(analysis.congestion_level, 0) for analysis in analyses)
        avg_score = total_score / len(analyses)
        
        for level, score in congestion_levels.items():
            if avg_score <= score:
                return level
        return 'severe'

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


class VideoProgressAPI(APIView):
    """Simple progress API that just reads from database"""
    
    def get(self, request, video_id):
        try:
            video = VideoFile.objects.get(id=video_id)
            
            return Response({
                'progress': video.processing_progress,
                'message': video.processing_message,
                'status': video.processing_status,
                'filename': video.filename,
                'title': video.title,
                'last_update': video.last_progress_update.isoformat()
            })
            
        except VideoFile.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)

class ActiveVideosProgressAPI(APIView):
    """Get progress for all active videos"""
    
    def get(self, request):
        # Get videos that are currently processing or uploaded
        active_videos = VideoFile.objects.filter(
            processing_status__in=['uploaded', 'processing']
        ).only('id', 'filename', 'title', 'processing_progress', 'processing_message', 'processing_status')
        
        progress_data = {}
        for video in active_videos:
            progress_data[str(video.id)] = {
                'progress': video.processing_progress,
                'message': video.processing_message,
                'status': video.processing_status,
                'filename': video.filename,
                'title': video.title or video.filename
            }
        
        return Response(progress_data)

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
        
    
class AllGroupsAPI(APIView):
    """Get all location-date groups with summary data - FIXED VERSION"""
    
    def get(self, request):
        try:
            print("🔍 [AllGroupsAPI] Fetching all groups with detailed info...")
            
            # Get all groups with their related data
            groups = LocationDateGroup.objects.all().select_related('location').prefetch_related(
                Prefetch(
                    'videos',
                    queryset=VideoFile.objects.filter(processing_status='completed')
                )
            ).order_by('-date', 'location__display_name')
            
            print(f"🔍 [AllGroupsAPI] Found {groups.count()} groups total")
            
            group_data = []
            for group in groups:
                # Get videos for this group
                videos = group.videos.filter(processing_status='completed')
                video_count = videos.count()
                
                # Get analyses for videos in this group
                analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=group)
                total_vehicles = sum(analysis.total_vehicles for analysis in analyses) if analyses else 0
                
                group_info = {
                    'id': str(group.id),
                    'location': {
                        'id': group.location.id,
                        'name': group.location.display_name,
                        'display_name': group.location.display_name
                    },
                    'date': group.date.isoformat(),
                    'video_count': video_count,
                    'total_vehicles': total_vehicles,
                    'time_range': group.get_time_range(),
                    'created_at': group.created_at.isoformat(),
                    'has_videos': video_count > 0
                }
                
                # Debug info for each group
                print(f"🔍 [AllGroupsAPI] Group: {group.location.display_name} - {group.date}")
                print(f"   📹 Videos in group: {video_count}")
                print(f"   🚗 Total vehicles: {total_vehicles}")
                
                group_data.append(group_info)
            
            # Also show ungrouped videos for debugging
            ungrouped_videos = VideoFile.objects.filter(
                processing_status='completed',
                location_date_group__isnull=True
            ).count()
            print(f"🔍 [AllGroupsAPI] Ungrouped videos: {ungrouped_videos}")
            
            return Response({
                'groups': group_data,
                'ungrouped_videos_count': ungrouped_videos,
                'total_groups': len(group_data)
            })
            
        except Exception as e:
            print(f"❌ [AllGroupsAPI] ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)
        
class GroupAnalysisDetailAPI(APIView):
    """Get detailed analysis for a specific location-date group"""
    
    def get(self, request, group_id):
        try:
            print(f"🔍 DEBUG: Fetching group analysis for {group_id}")
            
            group = LocationDateGroup.objects.select_related('location').prefetch_related(
                Prefetch(
                    'videos',
                    queryset=VideoFile.objects.filter(processing_status='completed').order_by('video_start_time')
                )
            ).get(id=group_id)
            
            # Get all analyses for this group
            analyses = TrafficAnalysis.objects.filter(
                video_file__location_date_group=group
            ).select_related('video_file')
            
            # Calculate aggregated statistics
            total_vehicles = sum(analysis.total_vehicles for analysis in analyses)
            car_count = sum(analysis.car_count for analysis in analyses)
            truck_count = sum(analysis.truck_count for analysis in analyses)
            motorcycle_count = sum(analysis.motorcycle_count for analysis in analyses)
            bus_count = sum(analysis.bus_count for analysis in analyses)
            bicycle_count = sum(analysis.bicycle_count for analysis in analyses)
            other_count = sum(analysis.other_count for analysis in analyses)
            total_processing_time = sum(analysis.processing_time_seconds for analysis in analyses)
            
            aggregated_data = {
                'total_vehicles': total_vehicles,
                'car_count': car_count,
                'truck_count': truck_count,
                'motorcycle_count': motorcycle_count,
                'bus_count': bus_count,
                'bicycle_count': bicycle_count,
                'other_count': other_count,
                'total_processing_time': total_processing_time,
                'average_congestion': self.calculate_average_congestion(analyses),
                'peak_traffic': max(analysis.peak_traffic for analysis in analyses) if analyses else 0,
                'video_count': group.videos.count(),
                'time_range': group.get_time_range()
            }
            
            # Get individual video analyses
            video_analyses = []
            for analysis in analyses:
                video_analyses.append({
                    'video_id': analysis.video_file.id,
                    'filename': analysis.video_file.filename,
                    'title': analysis.video_file.title,
                    'start_time': analysis.video_file.video_start_time.strftime('%H:%M') if analysis.video_file.video_start_time else 'Unknown',
                    'end_time': analysis.video_file.video_end_time.strftime('%H:%M') if analysis.video_file.video_end_time else 'Unknown',
                    'duration': analysis.video_file.duration_seconds,
                    'total_vehicles': analysis.total_vehicles,
                    'congestion_level': analysis.congestion_level,
                    'processing_time': analysis.processing_time_seconds,
                    'vehicle_breakdown': {
                        'cars': analysis.car_count,
                        'trucks': analysis.truck_count,
                        'motorcycles': analysis.motorcycle_count,
                        'buses': analysis.bus_count,
                        'bicycles': analysis.bicycle_count,
                        'others': analysis.other_count
                    }
                })
            
            response_data = {
                'group': {
                    'id': group.id,
                    'location': {
                        'id': group.location.id,
                        'name': group.location.display_name,
                        'processing_profile': group.location.processing_profile.display_name if group.location.processing_profile else 'Default'
                    },
                    'date': group.date.isoformat(),
                    'description': group.description
                },
                'aggregated_analysis': aggregated_data,
                'video_analyses': video_analyses,
                'videos': [
                    {
                        'id': video.id,
                        'filename': video.filename,
                        'title': video.title,
                        'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else 'Unknown',
                        'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else 'Unknown',
                        'duration': video.duration_seconds
                    }
                    for video in group.videos.all()
                ]
            }
            
            print(f"✅ DEBUG: Successfully returning group analysis for {group_id}")
            return Response(response_data)
            
        except LocationDateGroup.DoesNotExist:
            print(f"❌ DEBUG: Group {group_id} not found")
            return Response({'error': 'Group not found'}, status=404)
        except Exception as e:
            print(f"❌ DEBUG: Error in GroupAnalysisDetailAPI: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)
    
    def calculate_average_congestion(self, analyses):
        if not analyses:
            return 'low'
        
        congestion_levels = {
            'very_low': 0,
            'low': 1, 
            'medium': 2,
            'high': 3,
            'severe': 4
        }
        
        total_score = sum(congestion_levels.get(analysis.congestion_level, 0) for analysis in analyses)
        avg_score = total_score / len(analyses)
        
        for level, score in congestion_levels.items():
            if avg_score <= score:
                return level
        return 'severe'
    
class LocationGroupsAPI(APIView):
    """Get all groups for a specific location with filtering support"""
    
    def get(self, request, location_id):
        try:
            print(f"🔍 [LocationGroupsAPI] Fetching groups for location: {location_id}")
            
            # Get query parameters for filtering
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            search_term = request.GET.get('search', '').strip()

            # Start with the base query for the specific location
            groups = LocationDateGroup.objects.filter(
                location_id=location_id
            ).select_related('location').prefetch_related('videos')

            # Apply date filters
            if start_date_str:
                start_date = parse_date(start_date_str)
                if start_date:
                    groups = groups.filter(date__gte=start_date)
                    print(f"   📅 Applying start date filter: >= {start_date}")
                else:
                    return Response(
                        {'error': 'Invalid start_date format. Use YYYY-MM-DD.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            if end_date_str:
                end_date = parse_date(end_date_str)
                if end_date:
                    groups = groups.filter(date__lte=end_date)
                    print(f"   📅 Applying end date filter: <= {end_date}")
                else:
                    return Response(
                        {'error': 'Invalid end_date format. Use YYYY-MM-DD.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Apply search filter
            if search_term:
                # Try to parse as date first
                search_date = parse_date(search_term)
                if search_date:
                    # If it's a valid date, search by exact date
                    groups = groups.filter(date=search_date)
                    print(f"   🔍 Applying date search: = {search_date}")
                else:
                    # Otherwise search in date string representation and video filenames
                    groups = groups.filter(
                        Q(date__icontains=search_term) |
                        Q(videos__filename__icontains=search_term)
                    ).distinct()
                    print(f"   🔍 Applying text search: '{search_term}'")

            # Order by date descending (most recent first)
            groups = groups.order_by('-date')
            
            print(f"✅ [LocationGroupsAPI] Found {groups.count()} groups after filtering")
            
            # Prefetch traffic analyses to avoid N+1 queries
            group_ids = groups.values_list('id', flat=True)
            
            # Get total vehicles per group in a single query
            from django.db.models import Count
            vehicle_counts = (
                TrafficAnalysis.objects
                .filter(video_file__location_date_group_id__in=group_ids)
                .values('video_file__location_date_group_id')
                .annotate(total_vehicles_sum=Sum('total_vehicles'))
            )
            
            # Convert to dictionary for easy lookup
            vehicle_count_dict = {
                item['video_file__location_date_group_id']: item['total_vehicles_sum'] or 0
                for item in vehicle_counts
            }
            
            group_data = []
            for group in groups:
                total_vehicles = vehicle_count_dict.get(group.id, 0)
                
                group_data.append({
                    'id': group.id,
                    'date': group.date.isoformat(),
                    'video_count': group.videos.count(),
                    'total_vehicles': total_vehicles,
                    'time_range': group.get_time_range(),
                    'created_at': group.created_at.isoformat()
                })
            
            return Response(group_data)
            
        except Exception as e:
            print(f"❌ [LocationGroupsAPI] Error: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LocationGroupVideosAPI(APIView):
    """Get all videos for a specific location group - FIXED VERSION"""
    
    def dispatch(self, request, *args, **kwargs):
        print(f"🔍 [LocationGroupVideosAPI] Received {request.method} request")
        print(f"🔍 [LocationGroupVideosAPI] Location ID: {kwargs.get('location_id')}")
        print(f"🔍 [LocationGroupVideosAPI] Group ID: {kwargs.get('group_id')}")
        print(f"🔍 [LocationGroupVideosAPI] Full path: {request.path}")
        print(f"🔍 [LocationGroupVideosAPI] Query params: {request.GET}")
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, location_id, group_id):
        try:
            print(f"🔍 [LocationGroupVideosAPI] GET - Fetching videos for location {location_id}, group {group_id}")
            
            # Verify the group belongs to the specified location
            group = LocationDateGroup.objects.select_related('location').get(
                id=group_id, 
                location_id=location_id
            )
            
            print(f"✅ [LocationGroupVideosAPI] Found group: {group.location.display_name} - {group.date}")
            
            # Get videos sorted by start time
            videos = group.videos.filter(
                processing_status='completed'
            ).order_by('video_start_time')
            
            print(f"✅ [LocationGroupVideosAPI] Found {videos.count()} videos")
            
            videos_data = []
            for video in videos:
                video_analysis = TrafficAnalysis.objects.filter(video_file=video).first()
                
                # Build video data with proper error handling
                video_info = {
                    'id': video.id,
                    'filename': video.filename,
                    'title': video.title or video.filename,
                    'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else 'Unknown',
                    'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else 'Unknown',
                    'duration': video.duration_seconds or 0,
                    'vehicle_count': video_analysis.total_vehicles if video_analysis else 0,
                    'processing_status': video.processing_status,
                    'uploaded_at': video.uploaded_at.isoformat() if video.uploaded_at else None
                }
                videos_data.append(video_info)
            
            response_data = {
                'group': {
                    'id': group.id,
                    'date': group.date.isoformat(),
                    'time_range': group.get_time_range(),
                    'location': {
                        'id': group.location.id,
                        'display_name': group.location.display_name,
                        'name': group.location.name
                    }
                },
                'videos': videos_data,
                'summary': {
                    'total_videos': len(videos_data),
                    'total_vehicles': sum(video['vehicle_count'] for video in videos_data),
                    'time_range': group.get_time_range()
                }
            }
            
            print(f"✅ [LocationGroupVideosAPI] Successfully returning {len(videos_data)} videos")
            return Response(response_data)
            
        except LocationDateGroup.DoesNotExist:
            print(f"❌ [LocationGroupVideosAPI] Group not found or doesn't belong to location")
            return Response(
                {'error': 'Group not found or does not belong to this location'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ [LocationGroupVideosAPI] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Server error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, location_id, group_id):
        """Handle POST requests with proper error message"""
        print(f"❌ [LocationGroupVideosAPI] POST method not allowed for this endpoint")
        return Response(
            {
                'error': 'Method not allowed',
                'message': 'GET method is required for this endpoint',
                'supported_methods': ['GET']
            }, 
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def put(self, request, location_id, group_id):
        """Handle PUT requests with proper error message"""
        print(f"❌ [LocationGroupVideosAPI] PUT method not allowed for this endpoint")
        return Response(
            {
                'error': 'Method not allowed', 
                'message': 'GET method is required for this endpoint',
                'supported_methods': ['GET']
            }, 
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def patch(self, request, location_id, group_id):
        """Handle PATCH requests with proper error message"""
        print(f"❌ [LocationGroupVideosAPI] PATCH method not allowed for this endpoint")
        return Response(
            {
                'error': 'Method not allowed',
                'message': 'GET method is required for this endpoint',
                'supported_methods': ['GET']
            }, 
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def delete(self, request, location_id, group_id):
        """Handle DELETE requests with proper error message"""
        print(f"❌ [LocationGroupVideosAPI] DELETE method not allowed for this endpoint")
        return Response(
            {
                'error': 'Method not allowed',
                'message': 'GET method is required for this endpoint',
                'supported_methods': ['GET']
            }, 
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def options(self, request, *args, **kwargs):
        """Handle OPTIONS requests to show allowed methods"""
        response = super().options(request, *args, **kwargs)
        response.data = {
            'allowed_methods': ['GET', 'OPTIONS'],
            'description': 'Get videos for a specific location-date group'
        }
        return response


class LocationGroupDetailAPI(APIView):
    """Get detailed information about a specific location group"""
    
    def get(self, request, group_id):
        try:
            group = LocationDateGroup.objects.select_related('location').prefetch_related('videos').get(id=group_id)
            
            # Get analyses for videos in this group
            analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=group)
            
            group_data = {
                'id': group.id,
                'location': {
                    'id': group.location.id,
                    'name': group.location.display_name,
                    'display_name': group.location.display_name
                },
                'date': group.date.isoformat(),
                'description': "",
                'video_count': group.videos.count(),
                'total_vehicles': sum(analysis.total_vehicles for analysis in analyses),
                'time_range': group.get_time_range(),
                'videos': [
                    {
                        'id': video.id,
                        'filename': video.filename,
                        'title': video.title,
                        'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else 'Unknown',
                        'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else 'Unknown',
                        'duration': video.duration_seconds,
                        'vehicle_count': video.traffic_analysis.total_vehicles if hasattr(video, 'traffic_analysis') else 0
                    }
                    for video in group.videos.all().order_by('video_start_time')
                ]
            }
            
            return Response(group_data)
            
        except LocationDateGroup.DoesNotExist:
            return Response({'error': 'Group not found'}, status=404)
        except Exception as e:
            print(f"Error getting group detail: {e}")
            return Response({'error': str(e)}, status=500)

class CreateLocationGroupAPI(APIView):
    """Create a new location group"""
    
    def post(self, request):
        serializer = LocationDateGroupSerializer(data=request.data)
        if serializer.is_valid():
            group = serializer.save()
            return Response(LocationDateGroupSerializer(group).data, status=201)
        return Response(serializer.errors, status=400)
    
class LocationGroupsWithVideosAPI(APIView):
    """Get location groups with their videos - SIMPLIFIED VERSION with filtering"""
    
    def get(self, request):
        try:
            print("🔍 DEBUG: Fetching location groups with videos...")
            
            # Get query parameters for filtering
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            search_term = request.GET.get('search', '').strip()
            location_id = request.GET.get('location') # Optional: filter by specific location

            # Start with the base query for all groups
            groups = LocationDateGroup.objects.all().select_related('location').prefetch_related('videos')

            # Apply location filter if provided
            if location_id:
                groups = groups.filter(location_id=location_id)
                print(f"   📍 Applying location filter: {location_id}")

            # Apply date filters
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    groups = groups.filter(date__gte=start_date)
                    print(f"   📅 Applying start date filter: >= {start_date}")
                except ValueError:
                    return Response(
                        {'error': 'Invalid start_date format. Use YYYY-MM-DD.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    groups = groups.filter(date__lte=end_date)
                    print(f"   📅 Applying end date filter: <= {end_date}")
                except ValueError:
                    return Response(
                        {'error': 'Invalid end_date format. Use YYYY-MM-DD.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Apply search filter (similar logic as above)
            if search_term:
                groups = groups.filter(
                    Q(date__icontains=search_term) |
                    Q(videos__filename__icontains=search_term) |
                    Q(location__display_name__icontains=search_term) # Also search location name
                    # Note: Searching total_vehicles calculated later is complex here
                ).distinct()
                print(f"   🔍 Applying search filter: '{search_term}'")

            # Order by date descending (most recent first)
            groups = groups.order_by('-date')

            print(f"🔍 Found {groups.count()} groups after filtering...")
            
            group_data = []
            for group in groups:
                print(f"🔍 Processing group: {group.location.display_name} - {group.date}")
                
                # Get analyses for videos in this group
                analyses = TrafficAnalysis.objects.filter(video_file__location_date_group=group)
                total_vehicles = sum(analysis.total_vehicles for analysis in analyses) if analyses else 0
                
                # Get videos for this group
                videos_data = []
                for video in group.videos.all():
                    video_analysis = TrafficAnalysis.objects.filter(video_file=video).first()
                    videos_data.append({
                        'id': video.id,
                        'filename': video.filename,
                        'title': video.title,
                        'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else 'Unknown',
                        'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else 'Unknown',
                        'duration': video.duration_seconds,
                        'vehicle_count': video_analysis.total_vehicles if video_analysis else 0
                    })
                
                group_data.append({
                    'id': group.id,
                    'name': f"{group.location.display_name} - {group.date}",
                    'location': {
                        'id': group.location.id,
                        'name': group.location.display_name,
                        'display_name': group.location.display_name
                    },
                    'date': group.date.isoformat(),
                    'description': group.description or "",
                    'video_count': group.videos.count(),
                    'total_vehicles': total_vehicles,
                    'time_range': group.get_time_range(),
                    'created_at': group.created_at.isoformat(), # Add this for sorting/filtering context if needed
                    'videos': videos_data
                })
            
            print(f"✅ DEBUG: Returning {len(group_data)} groups")
            return Response(group_data)
            
        except Exception as e:
            print(f"❌ DEBUG: Error in LocationGroupsWithVideosAPI: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)
        
class AutoGroupVideosAPI(APIView):
    """Automatically group all ungrouped videos"""
    
    def post(self, request):
        try:
            print("🔍 DEBUG: Starting auto-grouping...")
            
            # Get all completed videos that aren't in any group
            ungrouped_videos = VideoFile.objects.filter(
                processing_status='completed',
                location_date_group__isnull=True
            ).select_related('traffic_analysis')
            
            grouped_count = 0
            errors = []
            
            for video in ungrouped_videos:
                try:
                    # Get location from traffic analysis
                    if hasattr(video, 'traffic_analysis') and video.traffic_analysis.location:
                        location = video.traffic_analysis.location
                        
                        # Use video date or fallback to analysis date
                        if video.video_date:
                            group_date = video.video_date
                        else:
                            group_date = video.traffic_analysis.analyzed_at.date()
                        
                        # Get or create group for this location and date
                        group, created = LocationDateGroup.objects.get_or_create(
                            location=location,
                            date=group_date
                        )
                        
                        # Add video to group
                        video.location_date_group = group
                        video.save()
                        
                        grouped_count += 1
                        print(f"✅ Auto-grouped: {video.filename} → {location.display_name} - {group_date}")
                    else:
                        errors.append(f"Video {video.filename} has no location assigned")
                        
                except Exception as e:
                    errors.append(f"Error grouping {video.filename}: {str(e)}")
            
            result = {
                'grouped_count': grouped_count,
                'errors': errors,
                'remaining_ungrouped': VideoFile.objects.filter(
                    processing_status='completed',
                    location_date_group__isnull=True
                ).count()
            }
            
            return Response({
                'status': 'success',
                'message': f'Auto-grouping completed: {grouped_count} videos grouped',
                'details': result
            })
            
        except Exception as e:
            print(f"❌ Error in auto-grouping: {e}")
            return Response({
                'error': f'Auto-grouping failed: {str(e)}'
            }, status=500)
        
class VideoManagementAPI(APIView):
    """Handle video metadata updates and management - FIXED VERSION"""
    
    def put(self, request, video_id):
        """Update video metadata (date, time, location) - FIXED"""
        try:
            print(f"🔍 UPDATE VIDEO: Processing update for video {video_id}")
            print(f"📦 Request data: {request.data}")
            
            video = VideoFile.objects.get(id=video_id)
            
            # Allowed fields to update
            allowed_fields = ['video_date', 'video_start_time', 'video_end_time', 'title']
            update_data = {}
            
            # Parse date/time fields properly
            for field in allowed_fields:
                if field in request.data:
                    value = request.data.get(field)
                    if value:  # Only update if value is provided and not empty
                        if field == 'video_date':
                            # Parse date string to Date object
                            try:
                                update_data[field] = datetime.strptime(value, '%Y-%m-%d').date()
                            except ValueError:
                                return Response(
                                    {'error': f'Invalid date format for {field}. Use YYYY-MM-DD.'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        elif field in ['video_start_time', 'video_end_time']:
                            # Parse time string to Time object
                            try:
                                update_data[field] = datetime.strptime(value, '%H:%M').time()
                            except ValueError:
                                return Response(
                                    {'error': f'Invalid time format for {field}. Use HH:MM.'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        else:
                            update_data[field] = value
            
            print(f"📝 Parsed fields to update: {update_data}")
            
            # Handle location change
            new_location_id = request.data.get('location_id')
            if new_location_id:
                try:
                    new_location = Location.objects.get(id=new_location_id)
                    # Update associated traffic analysis if exists
                    if hasattr(video, 'traffic_analysis'):
                        video.traffic_analysis.location = new_location
                        video.traffic_analysis.save()
                        print(f"📍 Updated location to: {new_location.display_name}")
                except Location.DoesNotExist:
                    return Response(
                        {'error': 'Location not found'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Update video fields
            for field, value in update_data.items():
                setattr(video, field, value)
                print(f"✅ Updated {field} to: {value}")
            
            video.save()
            
            # If date changed, update the location-date group
            if 'video_date' in update_data:
                self.update_video_grouping(video)
            
            # Return the updated video with properly formatted dates/times
            serializer = VideoFileSerializer(video)
            response_data = {
                'status': 'success',
                'message': 'Video metadata updated successfully',
                'video': serializer.data
            }
            
            print(f"✅ UPDATE COMPLETE: Video {video_id} updated successfully")
            return Response(response_data)
            
        except VideoFile.DoesNotExist:
            return Response(
                {'error': 'Video not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error updating video: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Error updating video: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update_video_grouping(self, video):
        """Update video's location-date group after date change"""
        try:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.location:
                location = video.traffic_analysis.location
                group_date = video.video_date
                
                if group_date:
                    # Get or create new group for updated date
                    group, created = LocationDateGroup.objects.get_or_create(
                        location=location,
                        date=group_date
                    )
                    
                    # Update video's group
                    video.location_date_group = group
                    video.save()
                    print(f"✅ Updated video group to: {location.display_name} - {group_date}")
                    
        except Exception as e:
            print(f"⚠️ Warning: Could not update video grouping: {e}")

class VideoDeleteAPI(APIView):
    """
    DELETE /api/videos/{video_id}/
    """
    def delete(self, request, video_id):
        try:
            print(f"🗑️ DELETE request for video: {video_id}")
            
            # Get the video object
            video = VideoFile.objects.get(id=video_id)
            filename = video.filename
            
            print(f"📹 Video found: {filename}, status: {video.processing_status}")
            
            # Check if video is currently processing
            if video.processing_status == 'processing':
                return Response(
                    {'error': 'Video is currently processing. Stop processing first or wait for it to complete.'},
                    status=status.HTTP_423_LOCKED
                )
            
            # Delete files from filesystem
            files_deleted = []
            if video.file_path and os.path.exists(video.file_path.path):
                os.remove(video.file_path.path)
                files_deleted.append('original video')
                print(f"✓ Deleted original video file")
            
            if video.processed_video_path and os.path.exists(video.processed_video_path.path):
                os.remove(video.processed_video_path.path)
                files_deleted.append('processed video') 
                print(f"✓ Deleted processed video file")
            
            # Delete from database
            video.delete()
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
        
class DebugURLsAPI(APIView):
    """Debug endpoint to check all registered URLs - FIXED VERSION"""
    
    def get(self, request):
        from django.urls import get_resolver
        
        resolver = get_resolver()
        url_patterns = []
        
        def extract_urls(patterns, prefix=''):
            for pattern in patterns:
                if hasattr(pattern, 'pattern'):
                    # This is a URLPattern or URLResolver
                    current_pattern = str(pattern.pattern)
                    full_pattern = prefix + current_pattern
                    
                    if hasattr(pattern, 'url_patterns'):
                        # This is an include - recurse
                        extract_urls(pattern.url_patterns, full_pattern)
                    else:
                        # This is a path
                        url_patterns.append({
                            'pattern': full_pattern,
                            'name': getattr(pattern, 'name', 'No name'),
                            'callback': getattr(pattern.callback, '__name__', str(pattern.callback))
                        })
        
        extract_urls(resolver.url_patterns)
        
        # Filter for our API URLs
        api_urls = [url for url in url_patterns if 'api' in url['pattern']]
        
        return Response({
            'total_api_urls': len(api_urls),
            'urls': api_urls
        })
    
class DebugProgressStoreAPI(APIView):
    """Debug endpoint to check progress store status"""
    
    def get(self, request):
        from .progress import progress_store
        return Response({
            'total_videos_tracked': len(progress_store),
            'progress_data': progress_store
        })

class DebugWebSocketTestAPI(APIView):
    """Test WebSocket connection for a video"""
    
    def post(self, request, video_id):
        from .progress import ProgressTracker
        
        try:
            progress_tracker = ProgressTracker(video_id)
            progress_tracker.set_progress(50, "Test progress update")
            
            return Response({
                'status': 'success',
                'message': f'Test progress update sent for video {video_id}',
                'progress': 50
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to send test progress: {str(e)}'
            }, status=500)
    
class SimpleGroupVideosAPI(APIView):
    """Simple endpoint to get group videos without location verification"""
    
    def get(self, request, group_id):
        try:
            print(f"🔍 [SimpleGroupVideosAPI] Fetching videos for group {group_id}")
            
            group = LocationDateGroup.objects.select_related('location').get(id=group_id)
            
            videos = group.videos.filter(processing_status='completed').order_by('video_start_time')
            
            videos_data = []
            for video in videos:
                video_analysis = TrafficAnalysis.objects.filter(video_file=video).first()
                videos_data.append({
                    'id': video.id,
                    'filename': video.filename,
                    'title': video.title,
                    'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else 'Unknown',
                    'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else 'Unknown',
                    'duration': video.duration_seconds,
                    'vehicle_count': video_analysis.total_vehicles if video_analysis else 0
                })
            
            response_data = {
                'group': {
                    'id': group.id,
                    'date': group.date.isoformat(),
                    'time_range': group.get_time_range(),
                    'location': {
                        'id': group.location.id,
                        'display_name': group.location.display_name
                    }
                },
                'videos': videos_data
            }
            
            return Response(response_data)
            
        except LocationDateGroup.DoesNotExist:
            return Response({'error': 'Group not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)