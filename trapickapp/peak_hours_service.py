# trapickapp/peak_hours_service.py
"""
Dedicated service for peak hour traffic analysis with real data from processed videos.
Phase 3: Now uses VideoAggregationService for accurate overlap/gap-aware calculations.
"""

import logging
from datetime import timedelta
from collections import defaultdict
from django.db.models import Q
from django.utils import timezone

from .models import TrafficAnalysis, Location, VideoFile, LocationDateGroup

logger = logging.getLogger(__name__)


class PeakHoursService:
    """
    Service for calculating peak traffic hours from actual video analysis data.

    Phase 3 update: Uses VideoAggregationService per LocationDateGroup to handle
    overlapping/gapped video segments correctly, with confidence scoring.
    """

    def __init__(self):
        self.peak_cache = {}
        self.cache_expiry = {}
        self.CACHE_DURATION = 300  # 5 minutes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_peak_hours_analysis(self, location_id='all', days_back=30, include_warnings=True):
        """
        Get comprehensive peak hour analysis for a location or all locations.

        Args:
            location_id: Specific location ID or 'all' for all locations
            days_back: Number of days to look back for analysis
            include_warnings: Whether to include data quality warnings

        Returns:
            List of dicts, one per day of week, with peak hour info
        """
        cache_key = f"{location_id}_{days_back}"

        # Check cache
        if cache_key in self.peak_cache:
            cache_time = self.cache_expiry.get(cache_key, 0)
            if (timezone.now().timestamp() - cache_time) < self.CACHE_DURATION:
                logger.debug(f"Returning cached peak hours data for {location_id}")
                return self.peak_cache[cache_key]

        logger.info(f"Calculating peak hours for location={location_id} (last {days_back} days)")

        # Fetch relevant groups
        cutoff_date = timezone.now().date() - timedelta(days=days_back)
        groups = LocationDateGroup.objects.filter(
            date__gte=cutoff_date
        ).select_related('location').prefetch_related('videos')

        if location_id != 'all' and location_id is not None:
            groups = groups.filter(location_id=location_id)

        if not groups.exists():
            result = self._empty_structure("No traffic data available. Process videos to see peak hour analysis.")
            self._cache(cache_key, result)
            return result

        # Aggregate hourly data across all groups, keyed by day-of-week
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Structure: day_name -> hour (0-23) -> {'vehicles': float, 'minutes': float, 'confidence': float}
        day_hourly = {d: defaultdict(lambda: {'vehicles': 0.0, 'minutes': 0.0, 'confidence': 0.0, 'entries': 0})
                      for d in day_names}

        day_meta = {d: {'total_vehicles': 0, 'analysis_count': 0, 'warnings': [], 'has_exact_times': False}
                    for d in day_names}

        for group in groups:
            day_name = group.date.strftime('%A')  # e.g. 'Monday'
            if day_name not in day_names:
                continue

            # Use VideoAggregationService for this group
            from .services.aggregation_service import VideoAggregationService
            service = VideoAggregationService(group)

            weighted = service.weighted_aggregation()
            hourly = service.hourly_aggregation()

            # Accumulate
            day_meta[day_name]['total_vehicles'] += weighted['total_vehicles']
            day_meta[day_name]['analysis_count'] += weighted['segment_count']

            if include_warnings and weighted['warnings']:
                day_meta[day_name]['warnings'].extend(weighted['warnings'])

            if weighted['segment_count'] > 0:
                day_meta[day_name]['has_exact_times'] = True

            for hour, data in hourly.items():
                if data['minutes_recorded'] > 0:
                    bucket = day_hourly[day_name][hour]
                    bucket['vehicles'] += data['vehicles']
                    bucket['minutes'] += data['minutes_recorded']
                    # Weighted running average of confidence
                    bucket['confidence'] = (
                        (bucket['confidence'] * bucket['entries'] + data['confidence'])
                        / (bucket['entries'] + 1)
                    )
                    bucket['entries'] += 1

        # Build result list
        result = []
        for day_name in day_names:
            hourly_data = day_hourly[day_name]
            meta = day_meta[day_name]

            morning_peak = self._find_peak(hourly_data, hour_range=range(6, 12))
            evening_peak = self._find_peak(hourly_data, hour_range=range(16, 21))

            entry = {
                'name': day_name,
                'morning_peak': morning_peak['time_range'] if morning_peak else 'No data',
                'evening_peak': evening_peak['time_range'] if evening_peak else 'No data',
                'morning_volume': morning_peak['vehicles'] if morning_peak else 0,
                'evening_volume': evening_peak['vehicles'] if evening_peak else 0,
                'morning_confidence': morning_peak['confidence'] if morning_peak else 0,
                'evening_confidence': evening_peak['confidence'] if evening_peak else 0,
                'total_vehicles': meta['total_vehicles'],
                'analysis_count': meta['analysis_count'],
                'has_exact_times': meta['has_exact_times'],
                'warnings': list(set(meta['warnings'])) if include_warnings else [],
                # Expose full hourly breakdown for frontend charts
                'hourly_distribution': {
                    h: {
                        'vehicles': round(d['vehicles']),
                        'minutes': round(d['minutes'], 1),
                        'confidence': round(d['confidence'], 1)
                    }
                    for h, d in hourly_data.items()
                    if d['minutes'] > 0
                }
            }
            result.append(entry)

        self._cache(cache_key, result)
        logger.info(f"Peak hours calculated for {len(result)} days")
        return result

    def get_peak_hour_statistics(self, location_id='all'):
        """
        Get summary statistics for peak hours.

        Returns:
            dict with overall_peak_hour, busiest_day, averages, totals
        """
        peak_data = self.get_peak_hours_analysis(location_id)

        if not peak_data or all(d['total_vehicles'] == 0 for d in peak_data):
            return {
                'overall_peak_hour': '8:00 AM',
                'busiest_day': 'No data',
                'busiest_day_vehicles': 0,
                'average_morning_volume': 0,
                'average_evening_volume': 0,
                'total_vehicles_analyzed': 0
            }

        total_vehicles = sum(d['total_vehicles'] for d in peak_data)
        days_with_data = [d for d in peak_data if d['total_vehicles'] > 0]

        avg_morning = (sum(d['morning_volume'] for d in days_with_data) / len(days_with_data)
                       if days_with_data else 0)
        avg_evening = (sum(d['evening_volume'] for d in days_with_data) / len(days_with_data)
                       if days_with_data else 0)

        busiest = max(peak_data, key=lambda d: d['total_vehicles'])

        # Find the most common peak hour across all days
        hour_votes = defaultdict(int)
        for day in days_with_data:
            for hour, data in day.get('hourly_distribution', {}).items():
                hour_votes[int(hour)] += data['vehicles']

        if hour_votes:
            overall_peak_hour = max(hour_votes.items(), key=lambda x: x[1])[0]
            peak_hour_str = self._hour_to_12h(overall_peak_hour)
        else:
            peak_hour_str = '8:00 AM'

        return {
            'overall_peak_hour': peak_hour_str,
            'busiest_day': busiest['name'],
            'busiest_day_vehicles': busiest['total_vehicles'],
            'average_morning_volume': round(avg_morning),
            'average_evening_volume': round(avg_evening),
            'total_vehicles_analyzed': total_vehicles
        }

    def get_detailed_peak_analysis(self, location_id='all', day=None):
        """
        Get detailed peak analysis for a specific day.

        Args:
            location_id: Specific location ID or 'all'
            day: Day name string (e.g. 'Monday') or None for all days

        Returns:
            Single day dict or full list
        """
        peak_data = self.get_peak_hours_analysis(location_id)

        if day:
            for day_data in peak_data:
                if day_data['name'].lower() == day.lower():
                    return day_data
            return None

        return peak_data

    def get_location_summary(self, location_id):
        """Get peak hour summary for a specific location."""
        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            return {'location_id': location_id, 'has_data': False, 'error': 'Location not found'}

        peak_data = self.get_peak_hours_analysis(location_id)
        stats = self.get_peak_hour_statistics(location_id)

        return {
            'location_id': location_id,
            'location_name': location.display_name,
            'has_data': any(d['total_vehicles'] > 0 for d in peak_data),
            'peak_hours': peak_data,
            'statistics': stats
        }

    def get_peak_hour_trends(self, location_id='all', weeks=4):
        """Get peak hour trends over multiple weeks."""
        trends = []
        today = timezone.now().date()

        for week in range(weeks):
            week_start = today - timedelta(days=(week + 1) * 7)
            week_end = today - timedelta(days=week * 7)

            groups = LocationDateGroup.objects.filter(
                date__gte=week_start,
                date__lt=week_end
            )
            if location_id != 'all':
                groups = groups.filter(location_id=location_id)

            total = 0
            for group in groups:
                from .services.aggregation_service import VideoAggregationService
                w = VideoAggregationService(group).weighted_aggregation()
                total += w['total_vehicles']

            trends.append({
                'week': week + 1,
                'start_date': week_start.isoformat(),
                'end_date': week_end.isoformat(),
                'total_vehicles': total
            })

        trends.reverse()  # Chronological order

        if len(trends) >= 2:
            first = trends[0]['total_vehicles']
            last = trends[-1]['total_vehicles']
            if first > 0:
                change_pct = ((last - first) / first) * 100
                trend_direction = 'increasing' if change_pct > 5 else ('decreasing' if change_pct < -5 else 'stable')
            else:
                trend_direction = 'stable'
        else:
            trend_direction = 'stable'

        return {
            'location_id': location_id,
            'weeks_analyzed': len(trends),
            'trends': trends,
            'trend_direction': trend_direction
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_peak(self, hourly_data, hour_range):
        """
        Find the peak hour within a given range from the hourly_data dict.

        Args:
            hourly_data: defaultdict keyed by int hour
            hour_range: iterable of hours to consider

        Returns:
            dict with time_range, vehicles, confidence, hour — or None
        """
        candidates = {h: hourly_data[h] for h in hour_range if hourly_data[h]['minutes'] > 0}
        if not candidates:
            return None

        peak_hour = max(candidates.items(), key=lambda x: x[1]['vehicles'])[0]
        data = candidates[peak_hour]

        return {
            'hour': peak_hour,
            'time_range': f"{peak_hour:02d}:00 - {peak_hour + 1:02d}:00",
            'vehicles': round(data['vehicles']),
            'confidence': round(data['confidence'], 1),
            'minutes_recorded': round(data['minutes'], 1)
        }

    def _hour_to_12h(self, hour):
        """Convert 24-hour integer to readable 12-hour string."""
        if hour == 0:
            return '12:00 AM'
        elif hour < 12:
            return f'{hour}:00 AM'
        elif hour == 12:
            return '12:00 PM'
        else:
            return f'{hour - 12}:00 PM'

    def _empty_structure(self, message):
        """Return empty peak hours list with message on each day."""
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return [
            {
                'name': day,
                'morning_peak': 'No data',
                'evening_peak': 'No data',
                'morning_volume': 0,
                'evening_volume': 0,
                'morning_confidence': 0,
                'evening_confidence': 0,
                'total_vehicles': 0,
                'analysis_count': 0,
                'has_exact_times': False,
                'warnings': [],
                'hourly_distribution': {},
                'message': message
            }
            for day in day_names
        ]

    def _cache(self, key, result):
        """Store result in cache."""
        self.peak_cache[key] = result
        self.cache_expiry[key] = timezone.now().timestamp()


# Singleton instance used across the app
peak_hours_service = PeakHoursService()