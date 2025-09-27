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
from .models import Detection
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

class AnalysisOverviewAPI(APIView):
    def get(self, request):
        """Provide overview data for the Home page"""
        # Get last 7 days of analysis
        one_week_ago = timezone.now() - timedelta(days=7)
        recent_analyses = TrafficAnalysis.objects.filter(analyzed_at__gte=one_week_ago)
        
        # Calculate weekly data (simplified for demo)
        weekly_data = [12500, 11800, 13200, 12700, 14200, 9800, 8500]  # Default data
        
        if recent_analyses.exists():
            # Real data calculation would go here
            weekly_data = [analysis.total_vehicles for analysis in recent_analyses]
            # Pad with default data if we don't have 7 days
            while len(weekly_data) < 7:
                weekly_data.append(8500)
        
        total_vehicles = sum(weekly_data)
        
        return Response({
            'weekly_data': weekly_data,
            'total_vehicles': total_vehicles,
            'congested_roads': 12,  # This would be calculated from real data
            'peak_hour': '8:00 AM',
            'daily_average': total_vehicles // 7,
            'areas': [
                {
                    'name': 'Baliwasan Area',
                    'morning_peak': '7:30 - 9:00 AM',
                    'evening_peak': '4:30 - 6:30 PM',
                    'morning_volume': 2450,
                    'evening_volume': 2150
                },
                {
                    'name': 'San Roque Area', 
                    'morning_peak': '7:45 - 9:15 AM',
                    'evening_peak': '5:00 - 6:30 PM',
                    'morning_volume': 1950,
                    'evening_volume': 1800
                }
            ]
        })

class VehicleStatsAPI(APIView):
    def get(self, request):
        """Provide vehicle statistics for VehiclesPassing page"""
        # Get today's date and calculate vehicle counts
        today = timezone.now().date()
        
        # This would be calculated from actual Detection data
        # For now, using sample data that matches your React component
        vehicle_data = {
            'today': {
                'cars': 1245,
                'trucks': 456,
                'tricycles': 789,
                'motorcycles': 934
            },
            'yesterday': {
                'cars': 1100,
                'trucks': 420,
                'tricycles': 750,
                'motorcycles': 880
            }
        }
        
        return Response(vehicle_data)

class CongestionDataAPI(APIView):
    def get(self, request):
        """Provide congestion data for CongestedRoads page"""
        congestion_data = [
            {
                'road': 'Baliwasan Road',
                'area': 'Baliwasan Area',
                'time': '7:30 - 9:00 AM',
                'congestion_level': 'High',
                'vehicles_per_hour': 2450,
                'trend': 'increasing'
            },
            {
                'road': 'San Roque Highway',
                'area': 'San Roque Area', 
                'time': '7:45 - 9:15 AM',
                'congestion_level': 'High',
                'vehicles_per_hour': 1950,
                'trend': 'stable'
            },
            {
                'road': 'Zamboanga City Boulevard',
                'area': 'Downtown Area',
                'time': '8:00 - 9:30 AM',
                'congestion_level': 'Medium', 
                'vehicles_per_hour': 1650,
                'trend': 'decreasing'
            },
            {
                'road': 'Tumaga Road',
                'area': 'Tumaga Area',
                'time': '4:30 - 6:30 PM', 
                'congestion_level': 'High',
                'vehicles_per_hour': 2150,
                'trend': 'increasing'
            },
            {
                'road': 'Gov. Camins Avenue',
                'area': 'San Jose Area',
                'time': '5:00 - 6:30 PM',
                'congestion_level': 'Medium',
                'vehicles_per_hour': 1800,
                'trend': 'stable'
            }
        ]
        
        return Response(congestion_data)

class VideoUploadAPI(APIView):
    def post(self, request):
        try:
            if 'video' not in request.FILES:
                return Response(
                    {'error': 'No video file provided'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            video_file = request.FILES['video']
            title = request.POST.get('title', video_file.name)
            location_id = request.POST.get('location_id')
            
            # Save video file
            fs = FileSystemStorage()
            filename = fs.save(f'videos/{video_file.name}', video_file)
            video_path = fs.path(filename)
            
            # Create VideoFile record
            video_obj = VideoFile.objects.create(
                filename=video_file.name,
                file_path=filename,
                title=title,
                processing_status='uploaded'
            )
            
            # Start background processing
            thread = threading.Thread(
                target=self.process_video_background,
                args=(video_obj.id, video_path, location_id)
            )
            thread.daemon = True
            thread.start()
            
            serializer = VideoFileSerializer(video_obj)
            return Response({
                'status': 'success',
                'message': 'Video uploaded and processing started',
                'upload_id': str(video_obj.id),
                'video': serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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
    def get(self, request):
        locations = Location.objects.filter(active=True)
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data)

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