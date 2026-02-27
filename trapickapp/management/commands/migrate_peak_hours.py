# trapickapp/management/commands/migrate_peak_hours.py
from django.core.management.base import BaseCommand
from trapickapp.services.migrations import migrate_to_enhanced_peak_hours


class Command(BaseCommand):
    help = 'Migrate existing groups to enhanced peak hours system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group-id',
            type=str,
            default=None,
            help='Specific group UUID to migrate (optional, defaults to all groups)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("🔄 MIGRATING TO ENHANCED PEAK HOURS"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        group_id = options.get('group_id')

        location_date_group = None
        if group_id:
            from trapickapp.models import LocationDateGroup
            try:
                location_date_group = LocationDateGroup.objects.get(id=group_id)
                self.stdout.write(f"Migrating specific group: {location_date_group}")
            except LocationDateGroup.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Group {group_id} not found"))
                return

        result = migrate_to_enhanced_peak_hours(location_date_group)

        self.stdout.write(self.style.SUCCESS(f"\n✅ Migration complete!"))
        self.stdout.write(f"   Total groups: {result['total_groups']}")
        self.stdout.write(f"   Updated:      {result['updated']}")

        if result['errors'] > 0:
            self.stdout.write(self.style.WARNING(f"   Errors:       {result['errors']}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"   Errors:       0"))