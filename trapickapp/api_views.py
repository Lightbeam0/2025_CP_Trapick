# trapickapp/api_views.py
import os
import csv
import json
import threading
import traceback
from datetime import datetime, timedelta
from io import BytesIO
from collections import Counter

from django.conf import settings
from django.http import HttpResponse, JsonResponse, FileResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.views.static import serve
from django.db import models
from django.db.models import Q, Sum, Prefetch
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas
import openpyxl

from .models import (
    VideoFile,
    TrafficAnalysis,
    Location,
    ProcessingProfile,
    LocationDateGroup,
    SystemConfig,
    TrafficReport,
    Detection,
    VehicleType,
    FrameAnalysis,
    HourlyTrafficSummary,
    DailyTrafficSummary,
    TrafficPrediction,
    DirectionalAnalysis,
    CongestionEvent,
)

from .serializers import *
from .tasks import process_video_task
from .progress import ProgressTracker



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
            processing_profile_id = request.POST.get('processing_profile_id')

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

            # Validate processing profile if provided
            processing_profile = None
            if processing_profile_id:
                try:
                    processing_profile = ProcessingProfile.objects.get(id=processing_profile_id, active=True)
                except ProcessingProfile.DoesNotExist:
                    return Response(
                        {'error': 'Processing profile not found or inactive'},
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

            # Create video object
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
                uploaded_at=timezone.now(),
                location_date_group=None  # Will be assigned after processing
            )

            # Set processing profile if provided
            if processing_profile:
                video_obj.processing_profile = processing_profile
                video_obj.save()

            print(f"📄 Video record created: {video_obj.id}, Start: {video_obj.video_start_time}, End: {video_obj.video_end_time}")

            # Start processing immediately via Celery
            try:
                task = process_video_task.delay(str(video_obj.id), location_id=location_id)
                print(f"✅ Celery task started: {task.id} for video {video_obj.id}")

                response_data = {
                    'status': 'success',
                    'message': 'Video uploaded and processing started',
                    'video_id': str(video_obj.id),
                    'upload_id': str(video_obj.id),
                    'id': str(video_obj.id),
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
                if processing_profile:
                    response_data['processing_profile'] = {
                        'id': processing_profile.id,
                        'name': processing_profile.display_name,
                        'detector_type': processing_profile.detector_type
                    }

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
        """Provide overview data for the Home page with REAL data including peak hours"""
        try:
            # Get query parameters for location filtering
            location_id = request.query_params.get('location_id', 'all')
            
            # Use services that support location filtering
            # Note: You'll need to implement or import these service functions
            weekly_data = self.calculate_real_weekly_data(location_id=location_id)
            system_stats = self.get_system_overview_stats(location_id=location_id)
            
            # ✅ NEW: Calculate real peak hours from actual data
            peak_hours_data = self.get_real_peak_hours_data(location_id)
            
            # Calculate totals
            total_vehicles = sum(weekly_data) if weekly_data else 0
            
            response_data = {
                'weekly_data': weekly_data,
                'total_vehicles': total_vehicles,
                'congested_roads': system_stats.get('congested_roads', 0),
                'peak_hour': self.calculate_overall_peak_hour(peak_hours_data),
                'daily_average': total_vehicles // 7 if total_vehicles > 0 else 0,
                'system_stats': system_stats,
                'peak_hours_data': peak_hours_data,
                'areas': self.format_peak_hours_for_frontend(peak_hours_data, location_id)
            }
            
            print(f"📊 Sending overview data with {len(peak_hours_data)} peak hour records")
            return Response(response_data)
            
        except Exception as e:
            print(f"❌ Error in AnalysisOverviewAPI: {e}")
            traceback.print_exc()
            
            # Return safe fallback data
            return Response({
                'weekly_data': [0, 0, 0, 0, 0, 0, 0],
                'total_vehicles': 0,
                'congested_roads': 0,
                'peak_hour': '8:00 AM',
                'daily_average': 0,
                'system_stats': {},
                'peak_hours_data': [],
                'areas': self.get_default_peak_hours(),
                'error': 'Error loading data'
            }, status=200)

    def calculate_real_weekly_data(self, location_id='all'):
        """Calculate weekly data based on location filter"""
        try:
            base_query = Q()
            if location_id != 'all' and location_id is not None:
                base_query &= Q(location_id=location_id)
            
            # Get analyses from last 7 days
            seven_days_ago = timezone.now() - timedelta(days=7)
            base_query &= Q(analyzed_at__gte=seven_days_ago)
            
            analyses = TrafficAnalysis.objects.filter(base_query)
            
            # Initialize weekly data (Monday=0, Sunday=6)
            weekly_data = [0] * 7
            
            for analysis in analyses:
                if analysis.video_file and analysis.video_file.video_date:
                    day_of_week = analysis.video_file.video_date.weekday()
                else:
                    day_of_week = analysis.analyzed_at.weekday()
                
                if 0 <= day_of_week <= 6:
                    weekly_data[day_of_week] += analysis.total_vehicles
            
            return weekly_data
            
        except Exception as e:
            print(f"❌ Error calculating weekly data: {e}")
            return [0, 0, 0, 0, 0, 0, 0]

    def get_system_overview_stats(self, location_id='all'):
        """Get system overview statistics"""
        try:
            base_query = Q()
            if location_id != 'all' and location_id is not None:
                base_query &= Q(location_id=location_id)
            
            total_analyses = TrafficAnalysis.objects.filter(base_query).count()
            
            # You can add more stats here like congested roads, etc.
            return {
                'total_analyses': total_analyses,
                'congested_roads': 0,  # Implement congestion logic as needed
                'active_locations': 0   # Implement location counting as needed
            }
            
        except Exception as e:
            print(f"❌ Error getting system stats: {e}")
            return {'total_analyses': 0}

    def get_real_peak_hours_data(self, location_id='all'):
        """Calculate actual peak hours from TrafficAnalysis data using video time ranges"""
        try:
            # Build base query
            base_query = Q()
            if location_id != 'all' and location_id is not None:
                base_query &= Q(location_id=location_id)
            
            # Get analyses from last 30 days for better pattern recognition
            thirty_days_ago = timezone.now() - timedelta(days=30)
            base_query &= Q(analyzed_at__gte=thirty_days_ago)
            
            # Get analyses with video file info
            analyses = TrafficAnalysis.objects.filter(base_query).select_related(
                'video_file', 'location'
            ).exclude(
                Q(video_file__video_start_time__isnull=True) | 
                Q(video_file__video_end_time__isnull=True)
            )
            
            print(f"🔍 Found {analyses.count()} analyses with time data for peak hour calculation")
            
            if not analyses.exists():
                # Fallback to analyses without exact times
                analyses = TrafficAnalysis.objects.filter(base_query).select_related(
                    'video_file', 'location'
                )
                print(f"⚠️ Using {analyses.count()} analyses (some without time data)")
            
            # Group by 15-minute intervals
            interval_data = {}  # Format: (day_of_week, interval_key): {data}
            
            for analysis in analyses:
                # Get day of week
                if analysis.video_file and analysis.video_file.video_date:
                    day_of_week = analysis.video_file.video_date.weekday()
                else:
                    day_of_week = analysis.analyzed_at.weekday()
                
                # Get time range from video
                video = analysis.video_file
                if video and video.video_start_time and video.video_end_time:
                    # Use actual video time range
                    start_hour = video.video_start_time.hour
                    start_minute = video.video_start_time.minute
                    end_hour = video.video_end_time.hour
                    end_minute = video.video_end_time.minute
                    
                    # Calculate duration in minutes
                    duration_minutes = (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)
                    if duration_minutes <= 0:
                        duration_minutes = 60  # Default 1 hour if invalid
                    
                    # Distribute vehicles across the time range
                    vehicles_per_minute = analysis.total_vehicles / duration_minutes if duration_minutes > 0 else 0
                    
                    # Add to 15-minute intervals
                    current_minute = start_hour * 60 + start_minute
                    end_minute_total = end_hour * 60 + end_minute
                    
                    while current_minute < end_minute_total:
                        interval_key_15 = f"{current_minute // 60:02d}:{((current_minute // 15) * 15) % 60:02d}"
                        
                        key = (day_of_week, interval_key_15)
                        if key not in interval_data:
                            interval_data[key] = {
                                'count': 0,
                                'analyses': set(),
                                'exact_times': []
                            }
                        
                        # Add portion of vehicles for this minute
                        interval_data[key]['count'] += vehicles_per_minute
                        interval_data[key]['analyses'].add(analysis.id)
                        interval_data[key]['exact_times'].append(f"{current_minute // 60:02d}:{current_minute % 60:02d}")
                        
                        current_minute += 1
                else:
                    # No exact time data, use analysis hour
                    hour = analysis.analyzed_at.hour
                    minute = analysis.analyzed_at.minute
                    interval_key_15 = f"{hour:02d}:{(minute // 15) * 15:02d}"
                    
                    key = (day_of_week, interval_key_15)
                    if key not in interval_data:
                        interval_data[key] = {
                            'count': 0,
                            'analyses': set(),
                            'exact_times': []
                        }
                    
                    interval_data[key]['count'] += analysis.total_vehicles
                    interval_data[key]['analyses'].add(analysis.id)
            
            # Convert to list format and aggregate by hour
            hourly_data = {}
            
            for (day_of_week, interval_key), data in interval_data.items():
                hour = int(interval_key.split(':')[0])
                
                key = (day_of_week, hour)
                if key not in hourly_data:
                    hourly_data[key] = {
                        'count': 0,
                        'analyses': set(),
                        'intervals': {},
                        'exact_times': []
                    }
                
                hourly_data[key]['count'] += data['count']
                hourly_data[key]['analyses'].update(data['analyses'])
                hourly_data[key]['intervals'][interval_key] = data['count']
                hourly_data[key]['exact_times'].extend(data['exact_times'])
            
            # Convert to result format
            result = []
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for (day_of_week, hour), data in hourly_data.items():
                # Find peak 15-minute interval within this hour
                intervals = data['intervals']
                if intervals:
                    peak_interval = max(intervals.items(), key=lambda x: x[1])[0]
                    peak_time = peak_interval
                else:
                    peak_time = f"{hour:02d}:00"
                
                # Get exact time range for this data point
                exact_times = sorted(set(data['exact_times']))
                time_range = "Multiple recordings"
                if exact_times:
                    if len(exact_times) == 1:
                        time_range = f"{exact_times[0]}"
                    else:
                        time_range = f"{exact_times[0]} - {exact_times[-1]}"
                
                result.append({
                    'day_of_week': day_of_week,
                    'day_name': day_names[day_of_week],
                    'hour': hour,
                    'peak_time': peak_time,
                    'vehicle_count': round(data['count']),
                    'analysis_count': len(data['analyses']),
                    'time_range': time_range,
                    'average_per_analysis': data['count'] / len(data['analyses']) if data['analyses'] else 0
                })
            
            # Sort by vehicle count (descending)
            result.sort(key=lambda x: x['vehicle_count'], reverse=True)
            
            print(f"✅ Generated {len(result)} peak hour records")
            return result[:100]  # Return top 100 records
            
        except Exception as e:
            print(f"❌ Error calculating peak hours: {e}")
            traceback.print_exc()
            return []

    def format_peak_hours_for_frontend(self, peak_hours_data, location_id='all'):
        """Format peak hours data for the frontend display using actual time ranges"""
        if not peak_hours_data:
            # Return default/fallback data
            return self.get_default_peak_hours()
        
        try:
            # Group by day of week
            days_data = {}
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for record in peak_hours_data:
                day_name = record['day_name']
                
                if day_name not in days_data:
                    days_data[day_name] = {
                        'hour_counts': {},
                        'time_ranges': {},
                        'peak_times': [],
                        'total_vehicles': 0,
                        'analysis_count': 0
                    }
                
                # Store hourly data with actual times
                hour = record['hour']
                day_data = days_data[day_name]
                
                if hour not in day_data['hour_counts']:
                    day_data['hour_counts'][hour] = 0
                    day_data['time_ranges'][hour] = []
                
                day_data['hour_counts'][hour] += record['vehicle_count']
                day_data['time_ranges'][hour].append({
                    'time_range': record['time_range'],
                    'peak_time': record['peak_time'],
                    'vehicle_count': record['vehicle_count'],
                    'analysis_count': record['analysis_count']
                })
                day_data['peak_times'].append(record['peak_time'])
                day_data['total_vehicles'] += record['vehicle_count']
                day_data['analysis_count'] += record['analysis_count']
            
            # Convert to frontend format
            result = []
            
            for day_name in day_names:  # Ensure correct order
                if day_name not in days_data:
                    continue
                
                day_data = days_data[day_name]
                hour_counts = day_data['hour_counts']
                
                if not hour_counts:
                    continue
                
                # Find morning peak (6 AM - 11 AM)
                morning_hours = {h: c for h, c in hour_counts.items() if 6 <= h <= 11}
                evening_hours = {h: c for h, c in hour_counts.items() if 16 <= h <= 20}
                
                # Calculate actual peak ranges based on recorded times
                morning_peak = self.calculate_actual_peak_range(
                    morning_hours, day_data['time_ranges'], "morning"
                )
                evening_peak = self.calculate_actual_peak_range(
                    evening_hours, day_data['time_ranges'], "evening"
                )
                
                # Calculate volumes based on actual data
                morning_volume = self.calculate_average_volume(morning_hours, hour_counts, day_data['total_vehicles'])
                evening_volume = self.calculate_average_volume(evening_hours, hour_counts, day_data['total_vehicles'])
                
                # Get most common peak time
                most_common_peak = self.get_most_common_peak_time(day_data['peak_times'])
                
                result.append({
                    'name': day_name,
                    'morning_peak': morning_peak,
                    'evening_peak': evening_peak,
                    'morning_volume': morning_volume,
                    'evening_volume': evening_volume,
                    'total_analysis_vehicles': day_data['total_vehicles'],
                    'analysis_count': day_data['analysis_count'],
                    'most_common_peak': most_common_peak,
                    'has_exact_times': len(day_data['time_ranges']) > 0
                })
            
            return result
            
        except Exception as e:
            print(f"❌ Error formatting peak hours: {e}")
            traceback.print_exc()
            return self.get_default_peak_hours()

    def calculate_actual_peak_range(self, hour_data, time_ranges, period_type):
        """Calculate peak range based on actual recorded time ranges"""
        if not hour_data:
            return "No data" if period_type == "morning" else "No data"
        
        # Find peak hour
        peak_hour = max(hour_data.items(), key=lambda x: x[1])[0]
        
        # Get time ranges for this peak hour
        hour_ranges = time_ranges.get(peak_hour, [])
        
        if not hour_ranges:
            # Fallback to estimated range
            if period_type == "morning":
                return f"{peak_hour:02d}:00 - {min(11, peak_hour+1):02d}:00"
            else:
                return f"{peak_hour:02d}:00 - {min(20, peak_hour+1):02d}:00"
        
        # Extract all time ranges and find common pattern
        all_times = []
        for time_range in hour_ranges:
            range_str = time_range['time_range']
            if ' - ' in range_str:
                start, end = range_str.split(' - ')
                all_times.append((start.strip(), end.strip()))
            else:
                # Single time
                all_times.append((range_str.strip(), range_str.strip()))
        
        if not all_times:
            return f"{peak_hour:02d}:00 - {peak_hour+1:02d}:00"
        
        # Find most common start and end times
        start_times = [t[0] for t in all_times]
        end_times = [t[1] for t in all_times]
        
        # Get most frequent time
        common_start = Counter(start_times).most_common(1)[0][0] if start_times else f"{peak_hour:02d}:00"
        common_end = Counter(end_times).most_common(1)[0][0] if end_times else f"{min(23, peak_hour+1):02d}:00"
        
        # Format as range
        if common_start == common_end:
            # Single time point, create 30-minute window
            hour_int = int(common_start.split(':')[0])
            minute_int = int(common_start.split(':')[1])
            start_time = f"{hour_int:02d}:{max(0, minute_int-15):02d}"
            end_time = f"{hour_int:02d}:{min(59, minute_int+15):02d}"
            return f"{start_time} - {end_time}"
        else:
            return f"{common_start} - {common_end}"

    def calculate_average_volume(self, period_hours, all_hours, total_vehicles):
        """Calculate average volume for a period"""
        if not period_hours:
            return 0
        
        # Calculate total vehicles in this period
        period_total = sum(period_hours.values())
        total_all = sum(all_hours.values())
        
        if total_all == 0:
            return 0
        
        # Calculate percentage of daily traffic in this period
        period_percentage = period_total / total_all
        
        # Estimate hourly volume
        avg_hourly = period_total / len(period_hours) if period_hours else 0
        
        return round(avg_hourly)

    def get_most_common_peak_time(self, peak_times):
        """Get the most frequently occurring peak time"""
        if not peak_times:
            return None
        
        return Counter(peak_times).most_common(1)[0][0]

    def calculate_overall_peak_hour(self, peak_hours_data):
        """Calculate the overall peak hour from the data"""
        if not peak_hours_data:
            return "8:00 AM"
        
        # Find the hour with highest average vehicles
        hourly_totals = {}
        for record in peak_hours_data:
            hour = record['hour']
            hourly_totals[hour] = hourly_totals.get(hour, 0) + record['vehicle_count']
        
        if not hourly_totals:
            return "8:00 AM"
        
        # Find peak hour
        peak_hour = max(hourly_totals.items(), key=lambda x: x[1])[0]
        
        # Convert to 12-hour format
        if peak_hour == 0:
            return "12:00 AM"
        elif peak_hour < 12:
            return f"{peak_hour}:00 AM"
        elif peak_hour == 12:
            return "12:00 PM"
        else:
            return f"{peak_hour - 12}:00 PM"

    def get_default_peak_hours(self):
        """Return default peak hours when no data is available"""
        return [
            {
                'name': 'Monday',
                'morning_peak': '07:30 - 09:00',
                'evening_peak': '17:00 - 18:30',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0,
                'analysis_count': 0,
                'most_common_peak': '08:15',
                'has_exact_times': False
            },
            {
                'name': 'Tuesday',
                'morning_peak': '07:45 - 09:15',
                'evening_peak': '17:15 - 18:45',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0,
                'analysis_count': 0,
                'most_common_peak': '08:30',
                'has_exact_times': False
            },
            {
                'name': 'Wednesday',
                'morning_peak': '08:00 - 09:30',
                'evening_peak': '17:00 - 18:30',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0,
                'analysis_count': 0,
                'most_common_peak': '08:45',
                'has_exact_times': False
            },
            {
                'name': 'Thursday',
                'morning_peak': '07:30 - 09:00',
                'evening_peak': '16:45 - 18:15',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0,
                'analysis_count': 0,
                'most_common_peak': '08:00',
                'has_exact_times': False
            },
            {
                'name': 'Friday',
                'morning_peak': '07:45 - 09:15',
                'evening_peak': '16:30 - 18:00',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0,
                'analysis_count': 0,
                'most_common_peak': '17:30',
                'has_exact_times': False
            },
            {
                'name': 'Saturday',
                'morning_peak': '09:00 - 10:30',
                'evening_peak': '18:00 - 19:30',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0,
                'analysis_count': 0,
                'most_common_peak': '09:45',
                'has_exact_times': False
            },
            {
                'name': 'Sunday',
                'morning_peak': '10:00 - 11:30',
                'evening_peak': '17:00 - 18:30',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0,
                'analysis_count': 0,
                'most_common_peak': '10:15',
                'has_exact_times': False
            }
        ]


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
                
                # CREATE location_info FIRST
                location_info = None
                if analysis.location:
                    location_info = {
                        'id': analysis.location.id,
                        'display_name': analysis.location.display_name,
                        'name': analysis.location.name
                    }
                
                analysis_data = {
                    'total_vehicles': analysis.total_vehicles,
                    'vehicle_breakdown': analysis.get_vehicle_breakdown(),
                    'processing_time': analysis.processing_time_seconds,
                    'congestion_level': analysis.congestion_level,
                    'traffic_pattern': analysis.traffic_pattern,
                    'analyzed_at': analysis.analyzed_at.isoformat(),
                    'location': location_info  # NOW THIS IS DEFINED
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


class GeneratePredictionsAPI(APIView):
    def post(self, request):
        try:
            from .services import generate_traffic_predictions

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
            print(f"🔍 [LocationGroupVideosAPI] Fetching videos for location {location_id}, group {group_id}")
            
            # Verify the group belongs to the specified location
            group = LocationDateGroup.objects.select_related('location').get(
                id=group_id, 
                location_id=location_id
            )
            
            print(f"✅ [LocationGroupVideosAPI] Found group: {group.location.display_name} - {group.date}")
            
            # Get videos sorted by start time with their analyses
            videos = group.videos.filter(
                processing_status='completed'
            ).select_related('traffic_analysis').order_by('video_start_time')
            
            print(f"✅ [LocationGroupVideosAPI] Found {videos.count()} videos")
            
            videos_data = []
            total_vehicles = 0
            
            for video in videos:
                video_analysis = None
                analysis_data = {}
                
                # Try to get traffic analysis
                if hasattr(video, 'traffic_analysis'):
                    video_analysis = video.traffic_analysis
                    
                    # Extract comprehensive analysis data
                    analysis_data = {
                        'total_vehicles': video_analysis.total_vehicles,
                        'car_count': video_analysis.car_count,
                        'truck_count': video_analysis.truck_count,
                        'motorcycle_count': video_analysis.motorcycle_count,
                        'bus_count': video_analysis.bus_count,
                        'bicycle_count': video_analysis.bicycle_count,
                        'other_count': video_analysis.other_count,
                        'congestion_level': video_analysis.congestion_level,
                        'traffic_pattern': video_analysis.traffic_pattern,
                        'peak_traffic': video_analysis.peak_traffic,
                        'average_traffic': video_analysis.average_traffic,
                        'processing_time_seconds': video_analysis.processing_time_seconds,
                        'analyzed_at': video_analysis.analyzed_at.isoformat() if video_analysis.analyzed_at else None,
                        
                        # Directional data
                        'directional_count': video_analysis.directional_count,
                        'directional_vehicles_per_minute': video_analysis.directional_vehicles_per_minute,
                        'peak_directional_flow': video_analysis.peak_directional_flow,
                        
                        # Congestion data
                        'congestion_events_count': video_analysis.congestion_events_count,
                        'total_congestion_time': video_analysis.total_congestion_time,
                        'congestion_percentage': video_analysis.congestion_percentage,
                        
                        # Model info
                        'model_info': video_analysis.get_model_info(),
                        'vehicle_breakdown': video_analysis.get_vehicle_breakdown(),
                        'metrics_summary': video_analysis.metrics_summary or {},
                        
                        # Analysis metadata
                        'duration_seconds': video_analysis.duration_seconds,
                        'fps': video_analysis.fps,
                        'total_frames': video_analysis.total_frames
                    }
                    
                    total_vehicles += video_analysis.total_vehicles
                
                # Build comprehensive video data
                video_info = {
                    'id': str(video.id),
                    'filename': video.filename,
                    'title': video.title or video.filename,
                    'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else 'Unknown',
                    'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else 'Unknown',
                    'duration': video.duration_seconds or 0,
                    'processing_status': video.processing_status,
                    'uploaded_at': video.uploaded_at.isoformat() if video.uploaded_at else None,
                    'video_date': video.video_date.isoformat() if video.video_date else None,
                    
                    # Include all analysis data
                    'analysis': analysis_data if video_analysis else None,
                    'vehicle_count': analysis_data.get('total_vehicles', 0),
                    'has_analysis': video_analysis is not None
                }
                
                videos_data.append(video_info)
            
            # Build comprehensive response
            response_data = {
                'group': {
                    'id': str(group.id),
                    'date': group.date.isoformat(),
                    'time_range': group.get_time_range(),
                    'location': {
                        'id': group.location.id,
                        'display_name': group.location.display_name,
                        'name': group.location.name,
                        'processing_profile': {
                            'id': group.location.processing_profile.id,
                            'name': group.location.processing_profile.display_name,
                            'detector_type': group.location.processing_profile.detector_type
                        } if group.location.processing_profile else None
                    }
                },
                'videos': videos_data,
                'summary': {
                    'total_videos': len(videos_data),
                    'total_vehicles': total_vehicles,
                    'time_range': group.get_time_range(),
                    'videos_with_analysis': sum(1 for v in videos_data if v['has_analysis']),
                    'average_vehicles_per_video': round(total_vehicles / len(videos_data)) if len(videos_data) > 0 else 0
                }
            }
            
            print(f"✅ [LocationGroupVideosAPI] Successfully returning {len(videos_data)} videos with full analysis data")
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
                    'created_at': group.created_at.isoformat(),
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
class SessionVideoAnalysesAPI(APIView):
    """Get all video analyses for a session/group"""
    
    def get(self, request, group_id):
        try:
            group = LocationDateGroup.objects.get(id=group_id)
            videos = group.videos.filter(processing_status='completed')
            
            analyses_data = []
            for video in videos:
                try:
                    analysis = TrafficAnalysis.objects.get(video_file=video)
                    # Get vehicle breakdown
                    vehicle_breakdown = analysis.get_vehicle_breakdown()
                    
                    # Get model info and analysis type
                    model_info = analysis.get_model_info()
                    
                    analyses_data.append({
                        'id': str(analysis.id),
                        'video_file_id': str(video.id),
                        'total_vehicles': analysis.total_vehicles,
                        'processing_time_seconds': analysis.processing_time_seconds,
                        'congestion_level': analysis.congestion_level,
                        'traffic_pattern': analysis.traffic_pattern,
                        'car_count': analysis.car_count,
                        'truck_count': analysis.truck_count,
                        'motorcycle_count': analysis.motorcycle_count,
                        'bus_count': analysis.bus_count,
                        'bicycle_count': analysis.bicycle_count,
                        'other_count': analysis.other_count,
                        'directional_count': analysis.directional_count,
                        'directional_vehicles_per_minute': analysis.directional_vehicles_per_minute,
                        'peak_directional_flow': analysis.peak_directional_flow,
                        'congestion_events_count': analysis.congestion_events_count,
                        'total_congestion_time': analysis.total_congestion_time,
                        'vehicle_breakdown': vehicle_breakdown,
                        'metrics_summary': analysis.metrics_summary or {},
                        'model_info': model_info,
                        'analysis_type': analysis.get_analysis_type(),
                        'direction_info': analysis.get_direction_info(),
                        'video_info': {
                            'id': str(video.id),
                            'filename': video.filename,
                            'title': video.title,
                            'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else None,
                            'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else None,
                            'duration': video.duration_seconds,
                            'uploaded_at': video.uploaded_at,
                            'processing_profile': video.get_processing_profile_info()
                        }
                    })
                except TrafficAnalysis.DoesNotExist:
                    # Video exists but no analysis yet
                    analyses_data.append({
                        'video_info': {
                            'id': str(video.id),
                            'filename': video.filename,
                            'title': video.title,
                            'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else None,
                            'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else None,
                            'duration': video.duration_seconds,
                            'uploaded_at': video.uploaded_at,
                            'processing_profile': video.get_processing_profile_info()
                        },
                        'total_vehicles': 0,
                        'congestion_level': 'unknown',
                        'analysis_type': 'no_analysis'
                    })
            
            return Response(analyses_data)
            
        except LocationDateGroup.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)


class DirectionalAnalysisAPI(APIView):
    """Get directional analysis data for videos"""
    
    def get(self, request, video_id):
        try:
            video = VideoFile.objects.get(id=video_id)
            
            if not hasattr(video, 'traffic_analysis'):
                return Response({'error': 'No analysis data available'}, status=404)
            
            analysis = video.traffic_analysis
            model_info = analysis.get_model_info()
            
            # Get processing profile info
            profile_info = video.get_processing_profile_info()
            
            # Get directional counts from detection data
            directional_detections = Detection.objects.filter(
                video_file=video,
                counted_directionally=True
            ).count()
            
            # Get detailed directional analysis if available
            directional_analyses = DirectionalAnalysis.objects.filter(
                traffic_analysis=analysis
            )
            
            directional_details = []
            for da in directional_analyses:
                directional_details.append({
                    'direction_name': da.direction_name,
                    'direction_angle': da.direction_angle,
                    'total_count': da.get_total_count(),
                    'car_count': da.directional_car_count,
                    'truck_count': da.directional_truck_count,
                    'motorcycle_count': da.directional_motorcycle_count,
                    'bus_count': da.directional_bus_count,
                    'bicycle_count': da.directional_bicycle_count
                })
            
            response_data = {
                'video_id': str(video.id),
                'filename': video.filename,
                'total_vehicles': analysis.total_vehicles,
                'directional_count': analysis.directional_count,
                'detection_based_directional': directional_detections,
                'directional_vehicles_per_minute': analysis.directional_vehicles_per_minute,
                'peak_directional_flow': analysis.peak_directional_flow,
                'model_info': model_info,
                'processing_profile': profile_info,
                'analysis_type': analysis.get_analysis_type(),
                'direction_info': analysis.get_direction_info(),
                'directional_details': directional_details,
                'has_directional_data': analysis.directional_count > 0,
                'directional_percentage': (analysis.directional_count / analysis.total_vehicles * 100) if analysis.total_vehicles > 0 else 0
            }
            
            return Response(response_data)
            
        except VideoFile.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)


class CongestionAnalysisAPI(APIView):
    """Get congestion analysis data for videos"""
    
    def get(self, request, video_id):
        try:
            video = VideoFile.objects.get(id=video_id)
            
            if not hasattr(video, 'traffic_analysis'):
                return Response({'error': 'No analysis data available'}, status=404)
            
            analysis = video.traffic_analysis
            congestion_summary = analysis.get_congestion_summary()
            
            # Get detailed congestion events
            detailed_events = CongestionEvent.objects.filter(
                traffic_analysis=analysis
            ).order_by('start_time_seconds')
            
            events_data = []
            for event in detailed_events:
                events_data.append({
                    'id': str(event.id),
                    'level': event.level,
                    'start_time': event.start_time_seconds,
                    'end_time': event.end_time_seconds,
                    'duration': event.duration_seconds,
                    'peak_vehicles': event.peak_vehicles,
                    'average_vehicles': event.average_vehicles,
                    'stationary_vehicles': event.stationary_vehicles,
                    'details': event.details or {}
                })
            
            # Get congestion level breakdown
            congestion_breakdown = {
                'none': analysis.congestion_none_time,
                'light': analysis.congestion_light_time,
                'moderate': analysis.congestion_moderate_time,
                'heavy': analysis.congestion_heavy_time,
                'severe': analysis.congestion_severe_time
            }
            
            response_data = {
                'video_id': str(video.id),
                'filename': video.filename,
                'congestion_summary': congestion_summary,
                'congestion_events': events_data,
                'congestion_breakdown': congestion_breakdown,
                'total_congestion_time': analysis.total_congestion_time,
                'congestion_percentage': analysis.congestion_percentage,
                'dominant_congestion_level': analysis.congestion_level,
                'total_congestion_events': analysis.congestion_events_count,
                'has_congestion_data': analysis.total_congestion_time > 0,
                'processing_profile': video.get_processing_profile_info()
            }
            
            return Response(response_data)
            
        except VideoFile.DoesNotExist:
            return Response({'error': 'Video not found'}, status=404)


class VideoAnalyticsDashboardAPI(APIView):
    """Get comprehensive analytics data for dashboard"""
    
    def get(self, request):
        try:
            # Get overall statistics
            total_videos = VideoFile.objects.count()
            processed_videos = VideoFile.objects.filter(processing_status='completed').count()
            processing_videos = VideoFile.objects.filter(processing_status='processing').count()
            pending_videos = VideoFile.objects.filter(processing_status='pending').count()
            
            # Get total vehicles across all analyses
            vehicle_stats = TrafficAnalysis.objects.aggregate(
                total_vehicles=Sum('total_vehicles'),
                directional_count=Sum('directional_count'),
                congestion_events=Sum('congestion_events_count')
            )
            
            total_vehicles = vehicle_stats['total_vehicles'] or 0
            directional_total = vehicle_stats['directional_count'] or 0
            total_congestion_events = vehicle_stats['congestion_events'] or 0
            
            # Get recent analyses with more details
            recent_analyses = TrafficAnalysis.objects.select_related(
                'video_file', 'location', 'video_file__processing_profile'
            ).order_by('-analyzed_at')[:10]
            
            recent_data = []
            for analysis in recent_analyses:
                model_info = analysis.get_model_info()
                recent_data.append({
                    'id': str(analysis.id),
                    'video_filename': analysis.video_file.filename,
                    'video_title': analysis.video_file.title or analysis.video_file.filename,
                    'location': analysis.location.display_name if analysis.location else 'Unknown',
                    'total_vehicles': analysis.total_vehicles,
                    'directional_count': analysis.directional_count,
                    'congestion_level': analysis.congestion_level,
                    'traffic_pattern': analysis.traffic_pattern,
                    'analyzed_at': analysis.analyzed_at.isoformat(),
                    'processing_time': analysis.processing_time_seconds,
                    'detector_type': model_info.get('detector_type', 'Unknown'),
                    'is_directional': model_info.get('is_directional', False),
                    'is_congestion': model_info.get('is_congestion', False)
                })
            
            # Get video processing status distribution
            status_distribution = {}
            for status_choice in VideoFile._meta.get_field('processing_status').choices:
                status_code = status_choice[0]
                count = VideoFile.objects.filter(processing_status=status_code).count()
                status_distribution[status_code] = {
                    'count': count,
                    'percentage': (count / total_videos * 100) if total_videos > 0 else 0
                }
            
            # Get detector type distribution
            detector_distribution = {}
            analyses_with_profile = TrafficAnalysis.objects.filter(
                video_file__processing_profile__isnull=False
            ).select_related('video_file__processing_profile')
            
            for analysis in analyses_with_profile:
                if analysis.video_file.processing_profile:
                    detector_type = analysis.video_file.processing_profile.detector_type
                    detector_distribution[detector_type] = detector_distribution.get(detector_type, 0) + 1
            
            # Calculate processing efficiency
            total_processing_time = TrafficAnalysis.objects.aggregate(
                total=Sum('processing_time_seconds')
            )['total'] or 0
            
            avg_processing_time = (total_processing_time / processed_videos) if processed_videos > 0 else 0
            
            response_data = {
                'overall_stats': {
                    'total_videos': total_videos,
                    'processed_videos': processed_videos,
                    'processing_videos': processing_videos,
                    'pending_videos': pending_videos,
                    'total_vehicles': total_vehicles,
                    'directional_vehicles': directional_total,
                    'total_congestion_events': total_congestion_events,
                    'processing_completion_rate': (processed_videos / total_videos * 100) if total_videos > 0 else 0,
                    'avg_processing_time_seconds': round(avg_processing_time, 2)
                },
                'status_distribution': status_distribution,
                'detector_distribution': detector_distribution,
                'recent_analyses': recent_data,
                'system_health': {
                    'videos_processed_today': VideoFile.objects.filter(
                        processed_at__date=timezone.now().date(),
                        processing_status='completed'
                    ).count(),
                    'avg_vehicles_per_video': round(total_vehicles / processed_videos, 2) if processed_videos > 0 else 0,
                    'directional_ratio': round(directional_total / total_vehicles * 100, 2) if total_vehicles > 0 else 0
                }
            }
            
            return Response(response_data)
            
        except Exception as e:
            print(f"Error in analytics dashboard: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)


class SystemHealthAPI(APIView):
    """Check system health and ML model availability"""
    
    def get(self, request):
        try:
            import sys
            import torch
            import cv2
            
            # Check Python dependencies
            python_version = sys.version.split()[0]  # Get just version number
            torch_available = torch.cuda.is_available() if hasattr(torch, 'cuda') else False
            torch_version = torch.__version__
            cv2_version = cv2.__version__
            
            # Check ML model availability for directional detectors
            ml_available = False
            ml_error = None
            ml_models = []
            
            try:
                from ml.directional_detectors import get_detector, get_available_detectors
                
                # Try to get list of available detectors
                available_detectors = get_available_detectors()
                ml_models = list(available_detectors.keys())
                
                # Try to instantiate a detector to check if it works
                try:
                    detector = get_detector('vertical_top_bottom')
                    ml_available = True
                except Exception as e:
                    ml_error = f"Failed to instantiate detector: {str(e)}"
                    
            except ImportError as e:
                ml_error = f"Failed to import directional_detectors: {str(e)}"
            except Exception as e:
                ml_error = str(e)
            
            # Check database connectivity
            db_available = True
            try:
                from django.db import connection
                connection.ensure_connection()
                # Test a simple query
                VideoFile.objects.count()
            except Exception:
                db_available = False
            
            # Check Celery
            celery_available = True
            try:
                from celery import current_app
                insp = current_app.control.inspect()
                celery_available = insp is not None and insp.active() is not None
            except Exception:
                celery_available = False
            
            # Check file system
            import tempfile
            import shutil
            fs_available = True
            fs_warning = None
            
            try:
                # Check write access to media directories
                media_dirs = ['media/videos', 'media/processed_videos']
                for dir_path in media_dirs:
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)
                    
                    # Test write access
                    test_file = os.path.join(dir_path, '.write_test')
                    try:
                        with open(test_file, 'w') as f:
                            f.write('test')
                        os.remove(test_file)
                    except Exception as e:
                        fs_warning = f"Cannot write to {dir_path}: {str(e)}"
                        fs_available = False
                        break
                        
            except Exception as e:
                fs_available = False
                fs_warning = str(e)
            
            # Check disk space
            disk_space_warning = None
            try:
                import shutil
                total, used, free = shutil.disk_usage(".")
                free_gb = free / (1024**3)
                if free_gb < 5:  # Less than 5GB free
                    disk_space_warning = f"Low disk space: {free_gb:.2f}GB free"
            except Exception:
                pass
            
            # Get system statistics
            total_videos = VideoFile.objects.count()
            processed_videos = VideoFile.objects.filter(processing_status='completed').count()
            
            health_data = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'system_info': {
                    'python_version': python_version,
                    'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                'components': {
                    'python': {
                        'version': python_version,
                        'status': 'ok'
                    },
                    'pytorch': {
                        'version': torch_version,
                        'cuda_available': torch_available,
                        'status': 'ok' if torch_available else 'warning'
                    },
                    'opencv': {
                        'version': cv2_version,
                        'status': 'ok'
                    },
                    'ml_models': {
                        'available': ml_available,
                        'error': ml_error,
                        'models': ml_models,
                        'status': 'ok' if ml_available else 'warning'
                    },
                    'database': {
                        'available': db_available,
                        'status': 'ok' if db_available else 'error'
                    },
                    'celery': {
                        'available': celery_available,
                        'status': 'ok' if celery_available else 'warning'
                    },
                    'filesystem': {
                        'available': fs_available,
                        'warning': fs_warning,
                        'status': 'ok' if fs_available else 'error'
                    }
                },
                'system_stats': {
                    'total_videos': total_videos,
                    'processed_videos': processed_videos,
                    'processing_rate': f"{(processed_videos / total_videos * 100):.1f}%" if total_videos > 0 else "0%"
                },
                'recommendations': []
            }
            
            # Add recommendations based on health status
            if not torch_available:
                health_data['recommendations'].append('CUDA not available - ML processing will use CPU (slower)')
            if not ml_available:
                health_data['recommendations'].append('ML models failed to load - check model files and dependencies')
            if not celery_available:
                health_data['recommendations'].append('Celery not running - background processing unavailable')
            if fs_warning:
                health_data['recommendations'].append(f'Filesystem issue: {fs_warning}')
            if disk_space_warning:
                health_data['recommendations'].append(disk_space_warning)
            
            # Add additional health checks
            if total_videos > 0 and processed_videos == 0:
                health_data['recommendations'].append('No videos have been processed yet - check processing configuration')
            
            # Check for recent processing errors
            recent_errors = VideoFile.objects.filter(
                processing_status='failed',
                last_progress_update__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            if recent_errors > 0:
                health_data['recommendations'].append(f'{recent_errors} video processing failures in last 24 hours')
            
            return Response(health_data)
            
        except Exception as e:
            print(f"Error in system health check: {e}")
            import traceback
            traceback.print_exc()
            return Response({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)

# trapickapp/api_views.py - ADD THESE AT THE END OF THE FILE
# ==================== AUTHENTICATION ENDPOINTS ====================

class LoginAPI(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        remember_me = request.data.get('remember_me', False)
        
        if not username or not password:
            return Response(
                {'success': False, 'message': 'Username and password required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user is not None:
            if not user.is_active:
                return Response(
                    {'success': False, 'message': 'Account is disabled'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Create or get token
            token, created = Token.objects.get_or_create(user=user)
            
            login(request, user)
            
            # Set session expiry based on remember_me
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(86400)  # 24 hours
            
            logger.info(f"User {username} logged in successfully")
            
            return Response({
                'success': True,
                'message': 'Login successful',
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                }
            })
        else:
            logger.warning(f"Failed login attempt for username: {username}")
            return Response(
                {'success': False, 'message': 'Invalid username or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        username = user.username
        
        # Delete the token
        try:
            request.user.auth_token.delete()
        except (AttributeError, Token.DoesNotExist):
            pass
        
        logout(request)
        
        logger.info(f"User {username} logged out")
        
        return Response({
            'success': True,
            'message': 'Logout successful'
        })


class CurrentUserAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
        })


class RegisterAPI(APIView):
    """Simple registration (can be disabled in production)"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        if not username or not password or not email:
            return Response({
                'success': False,
                'message': 'Username, email, and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(username=username).exists():
            return Response({
                'success': False,
                'message': 'Username already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            # Create auth token
            token = Token.objects.create(user=user)
            
            return Response({
                'success': True,
                'message': 'User registered successfully',
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                }
            }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return Response({
                'success': False,
                'message': f'Registration failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckAuthAPI(APIView):
    """Check if user is authenticated"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        if request.user.is_authenticated:
            return Response({
                'authenticated': True,
                'user': {
                    'id': request.user.id,
                    'username': request.user.username,
                    'email': request.user.email,
                    'is_staff': request.user.is_staff,
                }
            })
        else:
            return Response({
                'authenticated': False
            })