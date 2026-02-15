# trapickapp/management/commands/sync_to_cloud.py
from django.core.management.base import BaseCommand
from django.conf import settings
from trapickapp.models import (
    Location, ProcessingProfile, VideoFile,
    LocationDateGroup, VehicleType, TrafficAnalysis,
    DirectionalAnalysis, CongestionEvent
)
import requests
import json
from datetime import datetime

class Command(BaseCommand):
    help = 'Sync local database to cloud deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing',
        )
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'incremental'],
            help='Type of sync: full or incremental',
        )

    def handle(self, *args, **options):
        if settings.IS_CLOUD_DEPLOYMENT:
            self.stdout.write(self.style.ERROR('❌ Cannot run sync FROM cloud deployment'))
            self.stdout.write('This command should only be run on local deployment')
            return

        dry_run = options['dry_run']
        sync_type = options['type']

        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('🔄 TRAPICK DATA SYNC TO CLOUD'))
        self.stdout.write(self.style.WARNING('=' * 60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No data will be sent'))
        
        # Verify configuration
        cloud_url = getattr(settings, 'CLOUD_SYNC_URL', None)
        api_key = getattr(settings, 'CLOUD_SYNC_API_KEY', None)
        
        if not cloud_url:
            self.stdout.write(self.style.ERROR('❌ CLOUD_SYNC_URL not configured'))
            return
        
        if not api_key:
            self.stdout.write(self.style.ERROR('❌ CLOUD_SYNC_API_KEY not configured'))
            return
        
        self.stdout.write(f'📡 Cloud URL: {cloud_url}')
        self.stdout.write('')

        # Collect data to sync
        self.stdout.write('📊 Collecting data...')
        
        sync_data = {
            'vehicle_types': self._serialize_vehicle_types(),
            'processing_profiles': self._serialize_profiles(),
            'locations': self._serialize_locations(),
            'groups': self._serialize_groups(),
            'videos': self._serialize_videos(),
            'analyses': self._serialize_analyses(),
            'directional_analyses': self._serialize_directional_analyses(),
            'congestion_events': self._serialize_congestion_events(),
        }
        
        # Show summary
        self.stdout.write('')
        self.stdout.write('📋 Sync Summary:')
        for key, items in sync_data.items():
            self.stdout.write(f'  • {key}: {len(items)} items')
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✅ Dry run complete'))
            self.stdout.write('')
            self.stdout.write('Sample data preview:')
            if sync_data['videos']:
                self.stdout.write(f"  First video: {sync_data['videos'][0]['filename']}")
            if sync_data['analyses']:
                self.stdout.write(f"  First analysis: {sync_data['analyses'][0]['total_vehicles']} vehicles")
            return
        
        # Send to cloud
        self.stdout.write('')
        self.stdout.write('🚀 Sending data to cloud...')
        
        try:
            response = requests.post(
                cloud_url,
                json={
                    'data': sync_data,
                    'sync_type': sync_type,
                },
                headers={
                    'X-Sync-API-Key': api_key,
                    'Content-Type': 'application/json',
                },
                timeout=300  # 5 minutes timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('=' * 60))
                self.stdout.write(self.style.SUCCESS('✅ SYNC SUCCESSFUL'))
                self.stdout.write(self.style.SUCCESS('=' * 60))
                self.stdout.write('')
                self.stdout.write('Results:')
                for key, count in result.get('results', {}).items():
                    self.stdout.write(f'  ✓ {key}: {count} synced')
            else:
                self.stdout.write(self.style.ERROR(f'❌ Sync failed: {response.status_code}'))
                self.stdout.write(f'Response: {response.text}')
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'❌ Connection error: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Unexpected error: {str(e)}'))

    def _serialize_vehicle_types(self):
        return [
            {
                'name': vt.name,
                'display_name': vt.display_name,
            }
            for vt in VehicleType.objects.all()
        ]

    def _serialize_profiles(self):
        return [
            {
                'id': profile.id,
                'name': profile.name,
                'display_name': profile.display_name,
                'description': profile.description,
                'detector_type': profile.detector_type,
                'enable_congestion_detection': profile.enable_congestion_detection,
                'congestion_threshold': profile.congestion_threshold,
                'road_type': profile.road_type,
                'config_parameters': profile.config_parameters,
                'active': profile.active,
            }
            for profile in ProcessingProfile.objects.all()
        ]

    def _serialize_locations(self):
        return [
            {
                'id': loc.id,
                'name': loc.name,
                'display_name': loc.display_name,
                'description': loc.description,
                'latitude': float(loc.latitude) if loc.latitude else None,
                'longitude': float(loc.longitude) if loc.longitude else None,
                'processing_profile_id': loc.processing_profile_id if loc.processing_profile else None,
                'counting_config': loc.counting_config,
                'active': loc.active,
            }
            for loc in Location.objects.all()
        ]

    def _serialize_groups(self):
        return [
            {
                'id': str(group.id),
                'location_id': group.location_id,
                'date': group.date.isoformat(),
                'total_directional_count': group.total_directional_count,
                'average_directional_flow': float(group.average_directional_flow),
                'peak_directional_flow': group.peak_directional_flow,
            }
            for group in LocationDateGroup.objects.all()
        ]

    def _serialize_videos(self):
        videos = []
        for video in VideoFile.objects.filter(processing_status='completed'):
            videos.append({
                'id': str(video.id),
                'filename': video.filename,
                'uploaded_at': video.uploaded_at.isoformat(),
                'video_date': video.video_date.isoformat() if video.video_date else None,
                
                # FIX: Convert time objects to ISO format strings with dummy date
                'video_start_time': f"2000-01-01T{video.video_start_time.isoformat()}" if video.video_start_time else None,
                'video_end_time': f"2000-01-01T{video.video_end_time.isoformat()}" if video.video_end_time else None,
                
                'original_duration': float(video.original_duration) if video.original_duration else None,
                'group_id': str(video.location_date_group_id) if video.location_date_group_id else None,
                'processing_profile_id': video.processing_profile_id if video.processing_profile else None,
                'duration_seconds': float(video.duration_seconds) if video.duration_seconds else None,
                'fps': float(video.fps) if video.fps else None,
                'total_frames': video.total_frames,
                'title': video.title,
                'resolution': video.resolution,
            })
        return videos

    def _serialize_analyses(self):
        analyses = []
        for analysis in TrafficAnalysis.objects.all():
            analyses.append({
                'id': str(analysis.id),
                'video_id': str(analysis.video_file_id),
                'location_id': analysis.location_id if analysis.location else None,
                'total_vehicles': analysis.total_vehicles,
                'processing_time_seconds': float(analysis.processing_time_seconds),
                'analyzed_at': analysis.analyzed_at.isoformat(),
                
                # Vehicle counts
                'car_count': analysis.car_count,
                'truck_count': analysis.truck_count,
                'motorcycle_count': analysis.motorcycle_count,
                'bus_count': analysis.bus_count,
                'bicycle_count': analysis.bicycle_count,
                'other_count': analysis.other_count,
                
                # Directional data
                'directional_count': analysis.directional_count,
                'directional_vehicles_per_minute': float(analysis.directional_vehicles_per_minute),
                'peak_directional_flow': analysis.peak_directional_flow,
                
                # Congestion data
                'congestion_events_count': analysis.congestion_events_count,
                'total_congestion_time': float(analysis.total_congestion_time),
                'congestion_percentage': float(analysis.congestion_percentage),
                'congestion_none_time': float(analysis.congestion_none_time),
                'congestion_light_time': float(analysis.congestion_light_time),
                'congestion_moderate_time': float(analysis.congestion_moderate_time),
                'congestion_heavy_time': float(analysis.congestion_heavy_time),
                'congestion_severe_time': float(analysis.congestion_severe_time),
                
                # Video properties
                'duration_seconds': float(analysis.duration_seconds),
                'fps': float(analysis.fps),
                'total_frames': analysis.total_frames,
                
                # Traffic metrics
                'peak_traffic': analysis.peak_traffic,
                'average_traffic': float(analysis.average_traffic),
                'congestion_level': analysis.congestion_level,
                'traffic_pattern': analysis.traffic_pattern,
                
                # JSON data
                'analysis_data': analysis.analysis_data,
                'metrics_summary': analysis.metrics_summary,
                'frame_data': analysis.frame_data,
                'congestion_events': analysis.congestion_events,
            })
        return analyses

    def _serialize_directional_analyses(self):
        analyses = []
        for dir_analysis in DirectionalAnalysis.objects.all():
            analyses.append({
                'id': str(dir_analysis.id),
                'traffic_analysis_id': str(dir_analysis.traffic_analysis_id),
                'direction_name': dir_analysis.direction_name,
                'direction_angle': dir_analysis.direction_angle,
                'line_start_x': float(dir_analysis.line_start_x),
                'line_start_y': float(dir_analysis.line_start_y),
                'line_end_x': float(dir_analysis.line_end_x),
                'line_end_y': float(dir_analysis.line_end_y),
                'directional_car_count': dir_analysis.directional_car_count,
                'directional_truck_count': dir_analysis.directional_truck_count,
                'directional_motorcycle_count': dir_analysis.directional_motorcycle_count,
                'directional_bus_count': dir_analysis.directional_bus_count,
                'directional_bicycle_count': dir_analysis.directional_bicycle_count,
            })
        return analyses

    def _serialize_congestion_events(self):
        events = []
        for event in CongestionEvent.objects.all():
            events.append({
                'id': str(event.id),
                'traffic_analysis_id': str(event.traffic_analysis_id),
                'start_frame': event.start_frame,
                'end_frame': event.end_frame,
                'start_time_seconds': float(event.start_time_seconds),
                'end_time_seconds': float(event.end_time_seconds),
                'duration_seconds': float(event.duration_seconds),
                'level': event.level,
                'peak_vehicles': event.peak_vehicles,
                'average_vehicles': float(event.average_vehicles),
                'stationary_vehicles': event.stationary_vehicles,
                'details': event.details,
            })
        return events