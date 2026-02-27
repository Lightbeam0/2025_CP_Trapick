# trapickapp/services/migrations.py
"""
Migration helpers for upgrading existing data to use the enhanced aggregation system.
Run these once after implementing Phase 3.
"""
import logging
from django.db import transaction
from trapickapp.services.aggregation_service import VideoAggregationService

logger = logging.getLogger(__name__)


def migrate_to_enhanced_peak_hours(location_date_group=None):
    """
    Migrate existing LocationDateGroup records to enhanced peak hours system.
    Updates coverage metrics and calculates peak hour data using VideoAggregationService.

    Args:
        location_date_group: Optional specific group to migrate. If None, migrates all.

    Returns:
        dict with total_groups, updated, errors counts
    """
    # Import here to avoid circular imports
    from trapickapp.models import LocationDateGroup

    total_groups = 0
    updated = 0
    errors = 0

    if location_date_group:
        groups = LocationDateGroup.objects.filter(id=location_date_group.id)
    else:
        groups = LocationDateGroup.objects.filter(
            videos__processing_status='completed'
        ).distinct()

    total_groups = groups.count()
    logger.info(f"Starting migration for {total_groups} groups...")

    for group in groups:
        try:
            with transaction.atomic():
                service = VideoAggregationService(group)

                # Run weighted aggregation (this calculates confidence, overlaps, gaps)
                weighted_data = service.weighted_aggregation()

                # Run peak hour analysis
                peak_analysis = service.peak_hour_analysis()

                # Update the group's coverage metrics directly
                group.calculate_coverage_metrics()
                group.calculate_hourly_distribution()

                # Store peak hour summary in hourly_distribution if not already set
                # (hourly_distribution is the closest existing field for this data)
                logger.info(
                    f"  ✅ {group.location.display_name} - {group.date}: "
                    f"{weighted_data['total_vehicles']} vehicles, "
                    f"{weighted_data['confidence_score']}% confidence"
                )
                updated += 1

        except Exception as e:
            logger.error(f"  ❌ Migration error for group {group.id}: {e}")
            errors += 1

    logger.info(f"Migration complete: {updated} updated, {errors} errors")
    return {
        'total_groups': total_groups,
        'updated': updated,
        'errors': errors
    }