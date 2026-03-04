# trapickapp/management/commands/test_aggregation.py
from django.core.management.base import BaseCommand
from trapickapp.models import LocationDateGroup
from services.aggregation_service import VideoAggregationService
import json

class Command(BaseCommand):
    help = 'Test video aggregation service'

    def add_arguments(self, parser):
        parser.add_argument('--group-id', type=str, help='Specific group ID to test')
        parser.add_argument('--verbose', action='store_true', help='Show detailed output')

    def handle(self, *args, **options):
        group_id = options.get('group_id')
        verbose = options.get('verbose', False)
        
        self.stdout.write(self.style.SUCCESS("="*70))
        self.stdout.write(self.style.SUCCESS("🧪 TESTING VIDEO AGGREGATION SERVICE"))
        self.stdout.write(self.style.SUCCESS("="*70))
        
        # Get groups to test
        if group_id:
            groups = LocationDateGroup.objects.filter(id=group_id)
        else:
            groups = LocationDateGroup.objects.all()[:3]  # Test first 3 groups
        
        for group in groups:
            self.stdout.write(f"\n📍 Testing group: {group.location.display_name} - {group.date}")
            
            # Initialize service
            service = VideoAggregationService(group)
            
            # Test segment analysis
            self.stdout.write("   📊 Analyzing segments...")
            analysis = service.analyze_segments()
            
            self.stdout.write(f"      Segments: {analysis['segment_count']}")
            self.stdout.write(f"      Total duration: {analysis['total_duration_minutes']} minutes")
            self.stdout.write(f"      Overlaps: {len(analysis['overlaps'])}")
            self.stdout.write(f"      Gaps: {len(analysis['gaps'])}")
            self.stdout.write(f"      Quality: {analysis['coverage_quality']}")
            
            if verbose and analysis['overlaps']:
                self.stdout.write(self.style.WARNING("\n      Overlaps detected:"))
                for o in analysis['overlaps']:
                    self.stdout.write(f"         {o['overlap_minutes']} min: {o['overlap_start']} - {o['overlap_end']}")
            
            if verbose and analysis['gaps']:
                self.stdout.write(self.style.WARNING("\n      Gaps detected:"))
                for g in analysis['gaps']:
                    self.stdout.write(f"         {g['gap_minutes']} min: {g['gap_start']} - {g['gap_end']}")
            
            # Test weighted aggregation
            self.stdout.write("\n   ⚖️ Performing weighted aggregation...")
            weighted = service.weighted_aggregation()
            
            self.stdout.write(self.style.SUCCESS(
                f"      Total vehicles: {weighted['total_vehicles']}"
            ))
            self.stdout.write(
                f"      Vehicles/hour: {weighted['weighted_vehicles_per_hour']}"
            )
            self.stdout.write(
                f"      Confidence: {weighted['confidence_score']}%"
            )
            
            if weighted['warnings']:
                for warning in weighted['warnings']:
                    self.stdout.write(self.style.WARNING(f"      ⚠️ {warning}"))
            
            if verbose:
                self.stdout.write("\n      Vehicle breakdown:")
                for vtype, count in weighted['vehicle_breakdown'].items():
                    if count > 0:
                        self.stdout.write(f"         {vtype}: {count}")
            
            # Test peak hour analysis
            self.stdout.write("\n   📈 Analyzing peak hours...")
            peaks = service.peak_hour_analysis()
            
            if peaks['morning_peak']:
                mp = peaks['morning_peak']
                self.stdout.write(
                    f"      Morning peak: {mp['time_range']} - {mp['vehicles']} vehicles "
                    f"(confidence: {mp['confidence']}%)"
                )
            
            if peaks['evening_peak']:
                ep = peaks['evening_peak']
                self.stdout.write(
                    f"      Evening peak: {ep['time_range']} - {ep['vehicles']} vehicles "
                    f"(confidence: {ep['confidence']}%)"
                )
            
            self.stdout.write("\n   " + "-"*50)
        
        self.stdout.write(self.style.SUCCESS("\n✅ Aggregation service test complete!"))