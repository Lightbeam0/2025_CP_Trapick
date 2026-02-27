# trapickapp/management/commands/update_coverage.py
from django.core.management.base import BaseCommand
from trapickapp.models import LocationDateGroup
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update coverage metrics for all existing location-date groups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group-id',
            type=str,
            help='Specific group ID to update (optional)'
        )

    def handle(self, *args, **options):
        group_id = options.get('group_id')
        
        if group_id:
            groups = LocationDateGroup.objects.filter(id=group_id)
        else:
            groups = LocationDateGroup.objects.all()
        
        self.stdout.write(f"Found {groups.count()} groups to update")
        
        for group in groups:
            try:
                self.stdout.write(f"Updating group: {group.location.display_name} - {group.date}")
                
                # Update coverage metrics
                coverage = group.calculate_coverage_metrics()
                
                # Update hourly distribution
                hourly = group.calculate_hourly_distribution()
                
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Coverage: {coverage['total_coverage_minutes']} minutes, "
                    f"{coverage['continuity_score']}% continuous"
                ))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ✗ Error updating group {group.id}: {e}"
                ))
        
        self.stdout.write(self.style.SUCCESS("Coverage update completed!"))