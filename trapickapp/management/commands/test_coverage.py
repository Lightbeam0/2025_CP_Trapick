# trapickapp/management/commands/test_coverage.py
from django.core.management.base import BaseCommand
from trapickapp.models import LocationDateGroup
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test coverage tracking functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group-id',
            type=str,
            help='Specific group ID to test (optional)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        group_id = options.get('group_id')
        verbose = options.get('verbose', False)
        
        self.stdout.write(self.style.SUCCESS("="*70))
        self.stdout.write(self.style.SUCCESS("🧪 TESTING COVERAGE TRACKING"))
        self.stdout.write(self.style.SUCCESS("="*70))
        
        # Get groups to test
        if group_id:
            groups = LocationDateGroup.objects.filter(id=group_id)
            if not groups.exists():
                self.stdout.write(self.style.ERROR(f"❌ Group {group_id} not found"))
                return
        else:
            groups = LocationDateGroup.objects.all()
        
        if not groups.exists():
            self.stdout.write(self.style.WARNING("❌ No groups found. Process some videos first."))
            return
        
        for group in groups[:3]:  # Test first 3 groups
            self.stdout.write(f"\n📍 Testing group: {group.location.display_name} - {group.date}")
            
            # Calculate coverage metrics
            self.stdout.write("   Calculating coverage metrics...")
            coverage = group.calculate_coverage_metrics()
            
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ Total coverage: {coverage['total_coverage_minutes']} minutes"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ Continuity score: {coverage['continuity_score']}%"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ Segments: {len(coverage['segments'])}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ Gaps detected: {len(coverage['coverage_gaps'])}"
            ))
            
            # Get detailed time range
            self.stdout.write("\n   Getting detailed time range...")
            detailed = group.get_detailed_time_range()
            
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ Full range: {detailed['full_range']}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"   ✅ Coverage %: {detailed['coverage_percentage']}%"
            ))
            
            if detailed['gaps'] and verbose:
                self.stdout.write(self.style.WARNING(f"   ⚠️ Gaps found:"))
                for gap in detailed['gaps']:
                    self.stdout.write(f"      - {gap['start']} to {gap['end']} ({gap['duration']} min)")
            
            # Show segments if verbose
            if verbose and detailed['segments']:
                self.stdout.write("\n   📹 Video segments:")
                for seg in detailed['segments']:
                    self.stdout.write(
                        f"      - {seg['start']} to {seg['end']} "
                        f"({seg['duration']} min, {seg['vehicles']} vehicles)"
                    )
            
            # Calculate hourly distribution
            self.stdout.write("\n   Calculating hourly distribution...")
            hourly = group.calculate_hourly_distribution()
            
            # Show top 3 hours (filter out hours with zero vehicles)
            valid_hours = [(hour, data) for hour, data in hourly.items() 
                          if data['vehicles'] > 0]
            
            if valid_hours:
                top_hours = sorted(
                    valid_hours, 
                    key=lambda x: x[1]['vehicles'], 
                    reverse=True
                )[:3]
                
                self.stdout.write(self.style.SUCCESS(f"   ✅ Top hours:"))
                for hour, data in top_hours:
                    self.stdout.write(
                        f"      - {int(hour):02d}:00: {data['vehicles']} vehicles "
                        f"({data['minutes']} min recorded)"
                    )
            else:
                self.stdout.write(self.style.WARNING("   ⚠️ No vehicle data for this group"))
            
            # Get coverage summary - FIXED: now using dictionary properly
            summary = group.get_coverage_summary()
            self.stdout.write(f"\n   📊 Summary: {summary['text']}")
            
            self.stdout.write("\n   " + "-"*50)
        
        self.stdout.write(self.style.SUCCESS("\n✅ Coverage tracking test complete!"))