# trapickapp/data_services.py
from django.db.models import Count, Avg, Max, Min, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Location, TrafficAnalysis, Detection, VideoFile, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction
import numpy as np
from .services.aggregation_service import VideoAggregationService
from .peak_hours_service import peak_hours_service
from .models import LocationDateGroup

def calculate_real_weekly_data(location_id='all'):
    try:
        base_query = Q()
        
        if location_id != 'all' and location_id is not None:
            base_query &= Q(location_id=location_id)
        
        analyses = TrafficAnalysis.objects.filter(base_query)
        
        if not analyses.exists():
            print(f"No traffic analyses found for location: {location_id}")
            return [0, 0, 0, 0, 0, 0, 0]
        
        daily_counts = [0, 0, 0, 0, 0, 0, 0]
        total_analyses = 0
        
        for analysis in analyses:
            date_to_use = None
            
            if analysis.video_file and analysis.video_file.video_date:
                date_to_use = analysis.video_file.video_date
            else:
                date_to_use = analysis.analyzed_at.date()
            
            day_of_week = date_to_use.weekday()
            daily_counts[day_of_week] += analysis.total_vehicles
            total_analyses += 1
        
        print(f"Processed {total_analyses} analyses for location {location_id}: {daily_counts}")
        return daily_counts
        
    except Exception as e:
        print(f"Error calculating weekly data for location {location_id}: {e}")
        import traceback
        traceback.print_exc()
        return [0, 0, 0, 0, 0, 0, 0]
    
def calculate_real_vehicle_stats(period='today', location_id=None, date_range='last_7_days'):
    try:
        from django.db.models import Q
        from datetime import timedelta
        
        print(f"🔄 Calculating vehicle stats - period: {period}, location: {location_id}, date_range: {date_range}")
        
        base_query = Q()
        
        if location_id and location_id != 'all':
            base_query &= Q(location_id=location_id)
            print(f"📍 Filtering by location: {location_id}")
        
        if date_range != 'all':
            if date_range == 'last_7_days':
                start_date = timezone.now() - timedelta(days=7)
            elif date_range == 'last_30_days':
                start_date = timezone.now() - timedelta(days=30)
            elif date_range == 'last_90_days':
                start_date = timezone.now() - timedelta(days=90)
            else:
                start_date = timezone.now() - timedelta(days=7)
            
            base_query &= Q(analyzed_at__gte=start_date)
            print(f"📅 Filtering by date range: {date_range} from {start_date}")
        
        analyses = TrafficAnalysis.objects.filter(base_query)
        print(f"📊 Total filtered analyses: {analyses.count()}")
        
        for i, analysis in enumerate(analyses[:3]):
            print(f"🔍 Analysis {i+1}: ID={analysis.id}, Vehicles={analysis.total_vehicles}, Date={analysis.analyzed_at}")
        
        if analyses.count() == 0:
            print("❌ No analyses found with current filters!")
            return get_fallback_data("No traffic analyses found with current filters")
        
        def get_period_counts(period_type):
            if period_type == 'today':
                target_date = timezone.now().date()
                period_analyses = analyses.filter(analyzed_at__date=target_date)
                print(f"📅 Today analyses: {period_analyses.count()} on {target_date}")
            elif period_type == 'yesterday':
                target_date = timezone.now().date() - timedelta(days=1)
                period_analyses = analyses.filter(analyzed_at__date=target_date)
                print(f"📅 Yesterday analyses: {period_analyses.count()} on {target_date}")
            else:
                period_analyses = analyses
                print(f"📅 {period_type} analyses: using all {period_analyses.count()} analyses")
            
            return {
                'cars': sum(a.car_count for a in period_analyses),
                'trucks': sum(a.truck_count for a in period_analyses),
                'buses': sum(a.bus_count for a in period_analyses),
                'motorcycles': sum(a.motorcycle_count for a in period_analyses),
                'bicycles': sum(a.bicycle_count for a in period_analyses),
                'others': sum(a.other_count for a in period_analyses)
            }
        
        today_data = get_period_counts('today')
        yesterday_data = get_period_counts('yesterday')
        week_data = get_period_counts('week')
        month_data = get_period_counts('month')
        
        total_analyses = analyses.count()
        total_vehicles = sum(a.total_vehicles for a in analyses)
        
        unique_days = analyses.dates('analyzed_at', 'day').count()
        average_daily = total_vehicles / max(1, unique_days)
        
        data_source = f"Based on {total_analyses} traffic analyses"
        if location_id and location_id != 'all':
            try:
                location = Location.objects.get(id=location_id)
                data_source += f" at {location.display_name}"
            except Location.DoesNotExist:
                pass
        
        result = {
            'today': today_data,
            'yesterday': yesterday_data,
            'week': week_data,
            'month': month_data,
            'all': today_data,
            'summary': {
                'total_analyses': total_analyses,
                'average_daily': round(average_daily),
                'data_source': data_source,
                'total_vehicles': total_vehicles,
                'unique_days': unique_days
            }
        }
        
        print(f"✅ Vehicle stats result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ Error calculating vehicle stats: {e}")
        import traceback
        traceback.print_exc()
        return get_fallback_data(f"Error: {str(e)}")

def get_fallback_data(reason):
    fallback_data = {
        'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0
    }
    
    return {
        'today': fallback_data,
        'yesterday': fallback_data,
        'week': fallback_data,
        'month': fallback_data,
        'all': fallback_data,
        'summary': {
            'total_analyses': 0,
            'average_daily': 0,
            'data_source': reason,
            'total_vehicles': 0,
            'unique_days': 0
        }
    }
        

def calculate_real_congestion_data(location_id='all'):
    """
    Return congestion rows from TrafficAnalysis records so the CongestedRoads
    page shows the levels that were actually detected in processed videos.
    """
    try:
        base_query = Q()
        if location_id != 'all' and location_id is not None:
            base_query &= Q(location_id=location_id)

        # Pull all completed analyses that have a location assigned.
        # Use select_related to avoid N+1 queries.
        analyses = (
            TrafficAnalysis.objects
            .filter(base_query, location__isnull=False)
            .select_related('location', 'video_file')
            .order_by('-analyzed_at')
        )

        congestion_data = []

        for analysis in analyses:
            video = analysis.video_file

            # Build a human-readable time range from the video's stored times.
            if video and video.video_start_time and video.video_end_time:
                time_str = (
                    f"{video.video_start_time.strftime('%I:%M %p')} – "
                    f"{video.video_end_time.strftime('%I:%M %p')}"
                )
            elif video and video.video_start_time:
                time_str = video.video_start_time.strftime('%I:%M %p')
            else:
                time_str = analysis.analyzed_at.strftime('%I:%M %p')

            # Vehicles-per-hour from the video's actual duration.
            duration_hours = 0
            if video and video.duration_seconds and video.duration_seconds > 0:
                duration_hours = video.duration_seconds / 3600
            elif analysis.duration_seconds and analysis.duration_seconds > 0:
                duration_hours = analysis.duration_seconds / 3600

            vehicles_per_hour = (
                int(analysis.total_vehicles / duration_hours)
                if duration_hours > 0
                else analysis.total_vehicles
            )

            # Traffic pattern → trend label
            trend_map = {
                'increasing':  'increasing',
                'decreasing':  'decreasing',
                'stable':      'stable',
                'fluctuating': 'fluctuating',
            }
            trend = trend_map.get(analysis.traffic_pattern, 'stable')

            # Video date label
            video_date = ''
            if video and video.video_date:
                video_date = video.video_date.strftime('%b %d, %Y')

            congestion_data.append({
                'road':               analysis.location.display_name,
                'area':               analysis.location.display_name,
                'time':               time_str,
                'video_date':         video_date,
                'congestion_level':   analysis.congestion_level,   # exact stored value
                'vehicles_per_hour':  vehicles_per_hour,
                'total_vehicles':     analysis.total_vehicles,
                'trend':              trend,
                'analysis_id':        str(analysis.id),
                # Enhanced fields (may be None on older analyses)
                'congestion_index':   analysis.congestion_index,
                'queue_length':       analysis.queue_length_meters,
                'incident_risk':      analysis.incident_risk_score,
            })

        return congestion_data

    except Exception as e:
        print(f"Error calculating congestion data: {e}")
        import traceback
        traceback.print_exc()
        return []
    
def calculate_hourly_traffic_summary(location_id='all'):
    today = timezone.now().date()
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    today_end = today_start + timedelta(days=1)
    
    base_query = Q(timestamp__range=(today_start, today_end))
    if location_id != 'all' and location_id is not None:
        base_query &= Q(analysis__location_id=location_id)
    
    detections = Detection.objects.filter(base_query)
    
    hourly_counts = {}
    for detection in detections:
        hour = detection.timestamp.hour
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
    
    hourly_summary = {f"{hour:02d}:00": count for hour, count in sorted(hourly_counts.items())}
    
    return hourly_summary

def get_system_overview_stats(location_id='all'):
    video_query = Q()
    analysis_query = Q()
    
    if location_id != 'all' and location_id is not None:
        analysis_query &= Q(location_id=location_id)
        video_query &= Q(traffic_analysis__location_id=location_id)
    
    total_videos = VideoFile.objects.filter(traffic_analysis__isnull=False).count()
    processed_videos = VideoFile.objects.filter(
        traffic_analysis__isnull=False,
        processed=True
    ).count()
    total_analyses = TrafficAnalysis.objects.filter(analysis_query).count()
    
    one_day_ago = timezone.now() - timedelta(hours=24)
    recent_analyses = TrafficAnalysis.objects.filter(
        analysis_query,
        analyzed_at__gte=one_day_ago
    )
    
    congested_roads = TrafficAnalysis.objects.filter(
        analysis_query,
        congestion_level__in=['high', 'severe']
    ).count()
    
    return {
        'total_videos': total_videos,
        'processed_videos': processed_videos,
        'total_analyses': total_analyses,
        'congested_roads': congested_roads,
        'recent_analyses_count': recent_analyses.count(),
        'processing_success_rate': (processed_videos / total_videos * 100) if total_videos > 0 else 0
    }

def get_vehicle_type_distribution(location_id='all'):
    base_query = Q()
    if location_id != 'all' and location_id is not None:
        base_query &= Q(analysis__location_id=location_id)
    
    distribution = (
        Detection.objects
        .filter(base_query)
        .values('vehicle_type__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    return {item['vehicle_type__name']: item['count'] for item in distribution}

def get_peak_hours_analysis(location_id='all'):
    try:
        base_query = Q()
        if location_id != 'all' and location_id is not None:
            base_query &= Q(location_id=location_id)
        
        all_analyses = TrafficAnalysis.objects.filter(base_query)
        print(f"🔍 Found {all_analyses.count()} total analyses for location {location_id}")
        
        if not all_analyses.exists():
            print("❌ No analyses found for peak hours")
            return [
                {
                    'name': 'No traffic data available',
                    'morning_peak': 'Process videos to see data',
                    'evening_peak': 'Process videos to see data', 
                    'morning_volume': 0,
                    'evening_volume': 0,
                    'total_analysis_vehicles': 0
                }
            ]
        
        if location_id != 'all':
            try:
                location = Location.objects.get(id=location_id)
                location_analyses = all_analyses.filter(location=location)
                
                if location_analyses.exists():
                    morning_peak, evening_peak = calculate_real_peak_hours(location_analyses)
                    morning_volume, evening_volume = calculate_real_peak_volumes(location_analyses, morning_peak, evening_peak)
                    
                    total_vehicles = sum(analysis.total_vehicles for analysis in location_analyses)
                    
                    return [{
                        'name': location.display_name,
                        'morning_peak': morning_peak,
                        'evening_peak': evening_peak,
                        'morning_volume': morning_volume,
                        'evening_volume': evening_volume,
                        'total_analysis_vehicles': total_vehicles
                    }]
                else:
                    return [{
                        'name': f'{location.display_name} - No Data',
                        'morning_peak': 'No data',
                        'evening_peak': 'No data',
                        'morning_volume': 0,
                        'evening_volume': 0,
                        'total_analysis_vehicles': 0
                    }]
            except Location.DoesNotExist:
                print(f"❌ Location {location_id} not found")
                return [{
                    'name': 'Location Not Found',
                    'morning_peak': 'N/A',
                    'evening_peak': 'N/A',
                    'morning_volume': 0,
                    'evening_volume': 0,
                    'total_analysis_vehicles': 0
                }]
        
        locations = Location.objects.filter(
            trafficanalysis__isnull=False
        ).distinct()
        
        print(f"📍 Found {locations.count()} locations with analyses")
        
        areas_data = []
        
        if locations.exists():
            for location in locations:
                location_analyses = all_analyses.filter(location=location)
                
                if location_analyses.exists():
                    morning_peak, evening_peak = calculate_real_peak_hours(location_analyses)
                    morning_volume, evening_volume = calculate_real_peak_volumes(location_analyses, morning_peak, evening_peak)
                    
                    total_vehicles = sum(analysis.total_vehicles for analysis in location_analyses)
                    
                    areas_data.append({
                        'name': location.display_name,
                        'morning_peak': morning_peak,
                        'evening_peak': evening_peak,
                        'morning_volume': morning_volume,
                        'evening_volume': evening_volume,
                        'total_analysis_vehicles': total_vehicles
                    })
                    print(f"✅ Added peak data for {location.display_name}: {morning_peak}, {evening_peak}")
        
        if not areas_data and all_analyses.exists():
            print("📊 Creating general peak analysis from all analyses")
            morning_peak, evening_peak = calculate_real_peak_hours(all_analyses)
            morning_volume, evening_volume = calculate_real_peak_volumes(all_analyses, morning_peak, evening_peak)
            
            total_vehicles = sum(analysis.total_vehicles for analysis in all_analyses)
            
            areas_data.append({
                'name': 'General Traffic',
                'morning_peak': morning_peak,
                'evening_peak': evening_peak,
                'morning_volume': morning_volume,
                'evening_volume': evening_volume,
                'total_analysis_vehicles': total_vehicles
            })
        
        if not areas_data:
            print("❌ No peak data could be generated")
            areas_data.append({
                'name': 'Processing data...',
                'morning_peak': '7:30 - 9:00 AM',
                'evening_peak': '4:30 - 6:30 PM',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0
            })
        
        print(f"✅ Returning {len(areas_data)} peak hour areas")
        return areas_data
        
    except Exception as e:
        print(f"❌ Error in get_peak_hours_analysis: {e}")
        import traceback
        traceback.print_exc()
        return [
            {
                'name': 'Error loading data',
                'morning_peak': 'Check server logs',
                'evening_peak': 'Check server logs',
                'morning_volume': 0,
                'evening_volume': 0,
                'total_analysis_vehicles': 0
            }
        ]

def calculate_real_peak_hours(analyses):
    try:
        print(f"📈 Calculating peak hours from {analyses.count()} analyses")
        
        hourly_totals = {}
        
        for analysis in analyses:
            hour = analysis.analyzed_at.hour
            hourly_totals[hour] = hourly_totals.get(hour, 0) + analysis.total_vehicles
        
        print(f"🕒 Hourly totals: {hourly_totals}")
        
        if not hourly_totals:
            return "7:30 - 9:00 AM", "4:30 - 6:30 PM"
        
        morning_hours = {h: c for h, c in hourly_totals.items() if 6 <= h <= 10}
        evening_hours = {h: c for h, c in hourly_totals.items() if 16 <= h <= 20}
        
        if morning_hours:
            peak_hour = max(morning_hours.items(), key=lambda x: x[1])[0]
            morning_peak = format_peak_time(peak_hour, "morning")
            print(f"🌅 Morning peak: {morning_peak} at hour {peak_hour}")
        else:
            morning_peak = "7:30 - 9:00 AM"
            print("🌅 Using default morning peak")
        
        if evening_hours:
            peak_hour = max(evening_hours.items(), key=lambda x: x[1])[0]
            evening_peak = format_peak_time(peak_hour, "evening")
            print(f"🌇 Evening peak: {evening_peak} at hour {peak_hour}")
        else:
            evening_peak = "4:30 - 6:30 PM"
            print("🌇 Using default evening peak")
        
        return morning_peak, evening_peak
        
    except Exception as e:
        print(f"❌ Error calculating peak hours: {e}")
        import traceback
        traceback.print_exc()
        return "7:30 - 9:00 AM", "4:30 - 6:30 PM"

def format_peak_time(hour, period):
    if period == "morning":
        start_hour = max(6, hour - 1)
        end_hour = min(11, hour + 1)
    else:
        start_hour = max(15, hour - 1)
        end_hour = min(21, hour + 1)
    
    start_period = "AM" if start_hour < 12 else "PM"
    end_period = "AM" if end_hour < 12 else "PM"
    
    start_display = start_hour if start_hour <= 12 else start_hour - 12
    end_display = end_hour if end_hour <= 12 else end_hour - 12
    
    return f"{start_display}:00 - {end_display}:00 {start_period}"

def calculate_real_peak_volumes(analyses, morning_peak, evening_peak):
    try:
        total_vehicles = sum(analysis.total_vehicles for analysis in analyses)
        analysis_count = analyses.count()
        
        if analysis_count == 0:
            return 0, 0
        
        avg_per_analysis = total_vehicles / analysis_count
        
        morning_volume = int(avg_per_analysis * 0.35)
        evening_volume = int(avg_per_analysis * 0.30)
        
        morning_volume = max(10, morning_volume)
        evening_volume = max(10, evening_volume)
        
        print(f"🚗 Peak volumes: morning={morning_volume}, evening={evening_volume}")
        return morning_volume, evening_volume
        
    except Exception as e:
        print(f"❌ Error calculating peak volumes: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def generate_traffic_predictions(location_id=None, days_ahead=7):
    from .models import TrafficPrediction, TrafficAnalysis, Detection
    from django.db.models import Count, Avg, Q
    
    TrafficPrediction.objects.all().delete()
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    historical_query = Q(analyzed_at__gte=thirty_days_ago)
    if location_id:
        historical_query &= Q(location_id=location_id)
    
    historical_analyses = TrafficAnalysis.objects.filter(historical_query)
    
    if not historical_analyses.exists():
        print("No TrafficAnalysis data available for predictions")
        return []
    
    predictions = []
    
    hourly_patterns = analyze_hourly_traffic_patterns(historical_analyses, location_id)
    
    for day_offset in range(1, days_ahead + 1):
        prediction_date = timezone.now().date() + timedelta(days=day_offset)
        day_of_week = prediction_date.weekday()
        
        for hour in range(24):
            predicted_count, confidence = predict_hourly_traffic(
                hourly_patterns, day_of_week, hour, historical_analyses
            )
            
            congestion_thresholds = calculate_congestion_thresholds(hourly_patterns)
            predicted_congestion = determine_congestion_level(predicted_count, congestion_thresholds)
            
            prediction = TrafficPrediction.objects.create(
                location_id=location_id,
                prediction_date=prediction_date,
                day_of_week=day_of_week,
                hour_of_day=hour,
                predicted_vehicle_count=predicted_count,
                predicted_congestion=predicted_congestion,
                confidence_score=confidence,
                confidence_interval_lower=max(0, predicted_count * 0.7),
                confidence_interval_upper=predicted_count * 1.3,
                model_version="v3.0-hourly-patterns"
            )
            
            predictions.append(prediction)
    
    print(f"Generated {len(predictions)} predictions from historical patterns")
    return predictions

def analyze_hourly_traffic_patterns(historical_analyses, location_id):
    from django.db.models import Count, Avg, Q
    
    patterns = {}
    
    for day in range(7):
        patterns[day] = {}
        
        day_analyses = historical_analyses.filter(
            analyzed_at__week_day=((day + 1) % 7) + 1
        )
        
        if not day_analyses.exists():
            overall_avg = historical_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 0
            for hour in range(24):
                patterns[day][hour] = {
                    'avg_vehicles': overall_avg * get_hourly_pattern_factor(hour),
                    'confidence': 0.3,
                    'data_points': 0
                }
            continue
        
        for hour in range(24):
            hour_start = hour
            hour_end = hour + 1
            
            relevant_analyses = []
            for analysis in day_analyses:
                if has_hourly_data(analysis, hour):
                    relevant_analyses.append(analysis)
            
            if relevant_analyses:
                avg_vehicles = np.mean([a.total_vehicles for a in relevant_analyses])
                confidence = min(0.9, len(relevant_analyses) * 0.1)
                
                patterns[day][hour] = {
                    'avg_vehicles': avg_vehicles,
                    'confidence': confidence,
                    'data_points': len(relevant_analyses)
                }
            else:
                day_avg = day_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 0
                patterns[day][hour] = {
                    'avg_vehicles': day_avg * get_hourly_pattern_factor(hour),
                    'confidence': 0.3,
                    'data_points': 0
                }
    
    return patterns

def has_hourly_data(analysis, target_hour):
    if analysis.video_file and analysis.video_file.video_start_time:
        try:
            video_hour = analysis.video_file.video_start_time.hour
            return abs(video_hour - target_hour) <= 2
        except:
            pass
    
    analysis_hour = analysis.analyzed_at.hour
    return abs(analysis_hour - target_hour) <= 2

def predict_hourly_traffic(hourly_patterns, day_of_week, hour, historical_analyses):
    day_pattern = hourly_patterns.get(day_of_week, {})
    hour_data = day_pattern.get(hour, {})
    
    if hour_data and hour_data.get('data_points', 0) >= 3:
        predicted_count = hour_data['avg_vehicles']
        confidence = hour_data['confidence']
    else:
        overall_avg = historical_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 50
        predicted_count = overall_avg * get_hourly_pattern_factor(hour)
        confidence = 0.4
    
    return round(predicted_count), confidence

def calculate_congestion_thresholds(hourly_patterns):
    all_volumes = []
    for day_data in hourly_patterns.values():
        for hour_data in day_data.values():
            all_volumes.append(hour_data.get('avg_vehicles', 0))
    
    if not all_volumes:
        return {'low': 30, 'medium': 60, 'high': 100, 'severe': 150}
    
    volumes = np.array(all_volumes)
    q25, q50, q75 = np.percentile(volumes, [25, 50, 75])
    
    return {
        'very_low': max(0, q25 - (q50 - q25)),
        'low': q25,
        'medium': q50,
        'high': q75,
        'severe': q75 + (q75 - q50)
    }

def determine_congestion_level(vehicle_count, thresholds):
    if vehicle_count >= thresholds['severe']:
        return 'severe'
    elif vehicle_count >= thresholds['high']:
        return 'high'
    elif vehicle_count >= thresholds['medium']:
        return 'medium'
    elif vehicle_count >= thresholds['low']:
        return 'low'
    else:
        return 'very_low'

def get_hourly_pattern_factor(hour):
    if 7 <= hour <= 9:
        return 1.8
    elif 16 <= hour <= 19:
        return 1.6
    elif 10 <= hour <= 15:
        return 1.2
    elif hour <= 5:
        return 0.3
    else:
        return 0.8

def get_traffic_predictions_for_date(date=None, location_id=None):
    if date is None:
        date = timezone.now().date() + timedelta(days=1)
    
    predictions = TrafficPrediction.objects.filter(prediction_date=date)
    
    if location_id:
        predictions = predictions.filter(location_id=location_id)
    
    return predictions.order_by('hour_of_day')

def get_peak_prediction_hours(date=None, location_id=None):
    predictions = get_traffic_predictions_for_date(date, location_id)
    
    if not predictions.exists():
        return []
    
    hourly_predictions = {}
    for pred in predictions:
        hourly_predictions[pred.hour_of_day] = pred.predicted_vehicle_count
    
    peak_hours = sorted(hourly_predictions.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return [
        {
            'hour': f"{hour:02d}:00",
            'predicted_vehicles': count,
            'congestion_level': next(p.predicted_congestion for p in predictions if p.hour_of_day == hour)
        }
        for hour, count in peak_hours
    ]

def auto_group_all_videos():
    from .models import VideoFile, LocationDateGroup, TrafficAnalysis
    
    ungrouped_videos = VideoFile.objects.filter(
        processing_status='completed',
        location_date_group__isnull=True
    ).select_related('traffic_analysis')
    
    grouped_count = 0
    errors = []
    
    for video in ungrouped_videos:
        try:
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.location:
                location = video.traffic_analysis.location
                
                if video.video_date:
                    group_date = video.video_date
                else:
                    group_date = video.traffic_analysis.analyzed_at.date()
                
                group, created = LocationDateGroup.objects.get_or_create(
                    location=location,
                    date=group_date
                )
                
                video.location_date_group = group
                video.save()
                
                grouped_count += 1
                print(f"✅ Auto-grouped: {video.filename} → {location.display_name} - {group_date}")
            else:
                errors.append(f"Video {video.filename} has no location assigned")
                
        except Exception as e:
            errors.append(f"Error grouping {video.filename}: {str(e)}")
    
    return {
        'grouped_count': grouped_count,
        'errors': errors,
        'remaining_ungrouped': VideoFile.objects.filter(
            processing_status='completed',
            location_date_group__isnull=True
        ).count()
    }

def get_location_groups_with_videos():
    from .models import LocationDateGroup
    from django.db.models import Prefetch
    
    groups = LocationDateGroup.objects.all().select_related('location').prefetch_related(
        Prefetch(
            'videos',
            queryset=VideoFile.objects.filter(processing_status='completed').order_by('video_start_time')
        )
    ).order_by('-date', 'location__display_name')
    
    result = []
    for group in groups:
        videos_data = []
        for video in group.videos.all():
            videos_data.append({
                'id': video.id,
                'filename': video.filename,
                'title': video.title,
                'start_time': video.video_start_time.strftime('%H:%M') if video.video_start_time else 'Unknown',
                'end_time': video.video_end_time.strftime('%H:%M') if video.video_end_time else 'Unknown',
                'duration': video.duration_seconds,
                'vehicle_count': video.traffic_analysis.total_vehicles if hasattr(video, 'traffic_analysis') else 0
            })
        
        result.append({
            'id': group.id,
            'location': {
                'id': group.location.id,
                'name': group.location.display_name
            },
            'date': group.date,
            'time_range': group.get_time_range(),
            'total_vehicles': group.get_total_vehicles(),
            'video_count': group.videos.count(),
            'videos': videos_data
        })
    
    return result

def get_enhanced_peak_hours_analysis(location_id='all', days_back=30, include_warnings=True):
    try:
        from .peak_hours_service import peak_hours_service
        result = peak_hours_service.get_peak_hours_analysis(
            location_id=location_id,
            days_back=days_back,
            include_warnings=include_warnings
        )
        return result
    except Exception as e:
        print(f"❌ Error in get_enhanced_peak_hours_analysis: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'peak_hours': []
        }

def get_location_peak_summary(location_id):
    try:
        from .peak_hours_service import peak_hours_service
        return peak_hours_service.get_location_summary(location_id)
    except Exception as e:
        print(f"❌ Error in get_location_peak_summary: {e}")
        return {
            'location_id': location_id,
            'has_data': False,
            'error': str(e)
        }

def get_peak_hour_trends(location_id='all', weeks=4):
    try:
        from .peak_hours_service import peak_hours_service
        return peak_hours_service.get_peak_hour_trends(
            location_id=location_id,
            weeks=weeks
        )
    except Exception as e:
        print(f"❌ Error in get_peak_hour_trends: {e}")
        return {
            'location_id': location_id,
            'weeks_analyzed': 0,
            'trends': [],
            'trend_direction': 'error'
        }

def get_group_aggregation(group_id):
    try:
        group = LocationDateGroup.objects.get(id=group_id)
        service = VideoAggregationService(group)
        return service.get_aggregation_summary()
    except LocationDateGroup.DoesNotExist:
        return {'error': 'Group not found'}
    except Exception as e:
        print(f"❌ Error in get_group_aggregation: {e}")
        return {'error': str(e)}

def get_group_timeline(group_id):
    try:
        group = LocationDateGroup.objects.get(id=group_id)
        service = VideoAggregationService(group)
        return service.generate_timeline_view()
    except LocationDateGroup.DoesNotExist:
        return {'error': 'Group not found'}
    except Exception as e:
        print(f"❌ Error in get_group_timeline: {e}")
        return {'error': str(e)}

def get_data_quality_report(location_id='all', days_back=30):
    try:
        cutoff_date = timezone.now().date() - timedelta(days=days_back)
        
        groups = LocationDateGroup.objects.filter(
            date__gte=cutoff_date
        ).select_related('location')
        
        if location_id != 'all':
            groups = groups.filter(location_id=location_id)
        
        quality_report = {
            'total_groups': groups.count(),
            'groups_with_issues': 0,
            'total_gaps': 0,
            'total_overlaps': 0,
            'average_confidence': 0,
            'issues_by_location': []
        }
        
        confidence_scores = []
        
        for group in groups:
            service = VideoAggregationService(group)
            weighted = service.weighted_aggregation()
            analysis = service.analyze_segments()
            
            confidence_scores.append(weighted['confidence_score'])
            
            if weighted['has_gaps'] or weighted['has_overlaps']:
                quality_report['groups_with_issues'] += 1
                quality_report['total_gaps'] += len(analysis.get('gaps', []))
                quality_report['total_overlaps'] += len(analysis.get('overlaps', []))
                
                quality_report['issues_by_location'].append({
                    'location': group.location.display_name,
                    'date': group.date.isoformat(),
                    'confidence': weighted['confidence_score'],
                    'gaps': len(analysis.get('gaps', [])),
                    'overlaps': len(analysis.get('overlaps', [])),
                    'warnings': weighted['warnings']
                })
        
        if confidence_scores:
            quality_report['average_confidence'] = round(
                sum(confidence_scores) / len(confidence_scores), 1
            )
        
        return quality_report
        
    except Exception as e:
        print(f"❌ Error in get_data_quality_report: {e}")
        return {'error': str(e)}

def migrate_to_enhanced_peak_hours():
    from .models import LocationDateGroup
    
    groups = LocationDateGroup.objects.all()
    updated = 0
    errors = 0
    
    print(f"🔄 Migrating {groups.count()} groups to enhanced peak hours...")
    
    for group in groups:
        try:
            service = VideoAggregationService(group)
            
            weighted = service.weighted_aggregation()
            peaks = service.peak_hour_analysis()
            
            print(f"  ✅ {group.location.display_name} - {group.date}: {weighted['total_vehicles']} vehicles, {weighted['confidence_score']}% confidence")
            updated += 1
            
        except Exception as e:
            print(f"  ❌ Error migrating {group.id}: {e}")
            errors += 1
    
    return {
        'total_groups': groups.count(),
        'updated': updated,
        'errors': errors
    }