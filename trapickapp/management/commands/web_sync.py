# trapickapp/management/commands/check_sync_status.py
from django.core.management.base import BaseCommand
from django.conf import settings
from trapickapp.models import (
    Location, ProcessingProfile, VideoFile,
    LocationDateGroup, TrafficAnalysis
)

class Command(BaseCommand):
    help = 'Check what data is available to sync'

    def handle(self, *args, **options):
        if settings.IS_CLOUD_DEPLOYMENT:
            self.stdout.write(self.style.ERROR('❌ This is a cloud deployment'))
            return

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('📊 SYNC STATUS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        profiles = ProcessingProfile.objects.count()
        locations = Location.objects.count()
        groups = LocationDateGroup.objects.count()
        videos = VideoFile.objects.filter(processing_status='completed').count()
        analyses = TrafficAnalysis.objects.count()
        
        self.stdout.write(f'\n📍 Locations: {locations}')
        self.stdout.write(f'📋 Processing Profiles: {profiles}')
        self.stdout.write(f'📅 Date Groups: {groups}')
        self.stdout.write(f'🎥 Completed Videos: {videos}')
        self.stdout.write(f'📊 Analyses: {analyses}')
        
        self.stdout.write(f'\n🌐 Cloud URL: {settings.CLOUD_SYNC_URL}')
        self.stdout.write(f'🔑 API Key: {"✅ Set" if settings.CLOUD_SYNC_API_KEY else "❌ Not set"}')
        
        self.stdout.write(f'\n💡 To sync this data to cloud, run:')
        self.stdout.write(f'   python manage.py sync_to_cloud')