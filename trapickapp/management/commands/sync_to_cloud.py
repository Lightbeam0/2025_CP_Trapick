# trapickapp/management/commands/sync_to_cloud.py
from django.core.management.base import BaseCommand
from django.conf import settings
from trapickapp.models import (
    Location, ProcessingProfile, VideoUpload,
    LocationDateGroup, VehicleType, VideoAnalysis
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
            'locations': self._serialize_locations(),
            'profiles': self._serialize_profiles(),
            'groups': self._serialize_groups(),
            'videos': self._serialize_videos(),
            'analyses': self._serialize_analyses(),
        }
        
        # Show summary
        self.stdout.write('')
        self.stdout.write('📋 Sync Summary:')
        for key, items in sync_data.items():
            self.stdout.write(f'  • {key}: {len(items)} items')
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✅ Dry run complete'))
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

    def _serialize_locations(self):
        return [
            {
                'id': loc.id,
                'name': loc.name,
                'latitude': float(loc.latitude) if loc.latitude else None,
                'longitude': float(loc.longitude) if loc.longitude else None,
                'description': loc.description or '',
            }
            for loc in Location.objects.all()
        ]

    def _serialize_profiles(self):
        return [
            {
                'id': profile.id,
                'name': profile.name,
                'config': profile.config or {},
            }
            for profile in ProcessingProfile.objects.all()
        ]

    def _serialize_groups(self):
        return [
            {
                'id': str(group.id),
                'location_id': group.location_id,
                'date': group.date.isoformat(),
                'name': group.name or '',
            }
            for group in LocationDateGroup.objects.all()
        ]

    def _serialize_videos(self):
        return [
            {
                'id': str(video.id),
                'location_id': video.location_id,
                'group_id': str(video.group_id) if video.group_id else None,
                'filename': video.filename,
                'uploaded_at': video.uploaded_at.isoformat(),
                'duration': float(video.duration) if video.duration else None,
                'fps': float(video.fps) if video.fps else None,
                'width': video.width,
                'height': video.height,
            }
            for video in VideoUpload.objects.filter(status='completed')
        ]

    def _serialize_analyses(self):
        analyses = []
        for analysis in VideoAnalysis.objects.all():
            analyses.append({
                'id': analysis.id,
                'video_id': str(analysis.video_id),
                'total_vehicles': analysis.total_vehicles or 0,
                'vehicle_counts': analysis.vehicle_counts or {},
                'average_speed': float(analysis.average_speed) if analysis.average_speed else None,
                'congestion_level': analysis.congestion_level or 'low',
                'analyzed_at': analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
            })
        return analyses