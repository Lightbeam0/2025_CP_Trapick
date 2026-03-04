# trapickapp/management/commands/migrate_peak_hours.py
from django.core.management.base import BaseCommand


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
        # ✅ FIX: Use fully-qualified import path instead of bare 'data_services'
        # The original `from data_services import ...` would raise ImportError
        # because Django management commands run in the project root context,
        # not inside the trapickapp package directory.
        try:
            from trapickapp.data_services import migrate_to_enhanced_peak_hours
        except ImportError:
            # Fallback: try relative import path if data_services lives elsewhere
            try:
                from data_services import migrate_to_enhanced_peak_hours
            except ImportError:
                self.stdout.write(
                    self.style.ERROR(
                        "❌ Could not import migrate_to_enhanced_peak_hours.\n"
                        "   Make sure trapickapp/data_services.py defines this function."
                    )
                )
                return

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

        try:
            result = migrate_to_enhanced_peak_hours(location_date_group)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Migration failed: {e}"))
            import traceback
            traceback.print_exc()
            return

        self.stdout.write(self.style.SUCCESS(f"\n✅ Migration complete!"))
        self.stdout.write(f"   Total groups: {result.get('total_groups', '?')}")
        self.stdout.write(f"   Updated:      {result.get('updated', '?')}")

        errors = result.get('errors', 0)
        if errors > 0:
            self.stdout.write(self.style.WARNING(f"   Errors:       {errors}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"   Errors:       0"))