# trapickapp/services/__init__.py
"""
Services package for trapickapp.
"""

from .aggregation_service import VideoAggregationService
from .migrations import migrate_to_enhanced_peak_hours
from trapickapp.data_services import (
    calculate_real_vehicle_stats,
    calculate_real_congestion_data,
    calculate_real_weekly_data,
    get_system_overview_stats,
    get_peak_hours_analysis,
    generate_traffic_predictions,
    get_traffic_predictions_for_date,
    get_peak_prediction_hours,
    auto_group_all_videos,
    get_data_quality_report,
)

__all__ = [
    'VideoAggregationService',
    'migrate_to_enhanced_peak_hours',
    'calculate_real_vehicle_stats',
    'calculate_real_congestion_data',
]