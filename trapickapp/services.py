# trapickapp/services.py
from django.db.models import Count, Avg, Max, Min, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Location, TrafficAnalysis, Detection, VideoFile, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction

def calculate_real_weekly_data():
    """Calculate weekly vehicle counts from all available data"""
    try:
        # Get ALL traffic analyses (including session analyses)
        analyses = TrafficAnalysis.objects.all()
        
        if not analyses.exists():
            print("No traffic analyses found at all")
            return [0, 0, 0, 0, 0, 0, 0]
        
        # Initialize daily counts (Monday=0 to Sunday=6)
        daily_counts = [0, 0, 0, 0, 0, 0, 0]
        total_analyses = 0
        
        for analysis in analyses:
            # Try to get date from different sources in priority order:
            date_to_use = None
            
            # 1. First try video file date
            if analysis.video_file and analysis.video_file.video_date:
                date_to_use = analysis.video_file.video_date
            # 2. Then try session start date
            elif analysis.analysis_session and analysis.analysis_session.start_datetime:
                date_to_use = analysis.analysis_session.start_datetime.date()
            # 3. Finally use analysis date
            else:
                date_to_use = analysis.analyzed_at.date()
            
            # Calculate day of week and add to counts
            day_of_week = date_to_use.weekday()
            daily_counts[day_of_week] += analysis.total_vehicles
            total_analyses += 1
        
        print(f"Processed {total_analyses} analyses for weekly data: {daily_counts}")
        return daily_counts
        
    except Exception as e:
        print(f"Error calculating weekly data: {e}")
        return [0, 0, 0, 0, 0, 0, 0]
    
def calculate_real_vehicle_stats():
    """Calculate actual vehicle statistics from TrafficAnalysis"""
    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        def get_daily_counts(date):
            """Get vehicle counts for a specific date from TrafficAnalysis"""
            analyses = TrafficAnalysis.objects.filter(analyzed_at__date=date)
            
            return {
                'cars': sum(a.car_count for a in analyses),
                'trucks': sum(a.truck_count for a in analyses),
                'buses': sum(a.bus_count for a in analyses),
                'motorcycles': sum(a.motorcycle_count for a in analyses),
                'bicycles': sum(a.bicycle_count for a in analyses),
                'others': sum(a.other_count for a in analyses)
            }
        
        today_data = get_daily_counts(today)
        yesterday_data = get_daily_counts(yesterday)
        
        return {
            'today': today_data,
            'yesterday': yesterday_data
        }
        
    except Exception as e:
        print(f"Error calculating vehicle stats: {e}")
        return {
            'today': {'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0},
            'yesterday': {'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0}
        }
        
def calculate_real_congestion_data():
    """Calculate real congestion data from recent TrafficAnalysis"""
    try:
        # Get recent analyses with locations
        recent_analyses = TrafficAnalysis.objects.filter(
            location__isnull=False
        ).select_related('location').order_by('-analyzed_at')[:10]
        
        congestion_data = []
        
        for analysis in recent_analyses:
            # Calculate vehicles per hour
            video_duration_hours = analysis.video_file.duration_seconds / 3600 if analysis.video_file and analysis.video_file.duration_seconds else 1
            vehicles_per_hour = analysis.total_vehicles / video_duration_hours if video_duration_hours > 0 else 0
            
            # Use actual congestion level from analysis
            congestion_level = analysis.congestion_level.capitalize()
            
            # Determine trend from traffic pattern
            trend = 'stable'
            if analysis.traffic_pattern == 'increasing':
                trend = 'increasing'
            elif analysis.traffic_pattern == 'decreasing':
                trend = 'decreasing'
            
            congestion_data.append({
                'road': f"{analysis.location.display_name} Road",
                'area': analysis.location.display_name,
                'time': analysis.analyzed_at.strftime('%I:%M %p'),
                'congestion_level': congestion_level,
                'vehicles_per_hour': int(vehicles_per_hour),
                'trend': trend
            })
        
        return congestion_data
        
    except Exception as e:
        print(f"Error calculating congestion data: {e}")
        return []
    
def calculate_hourly_traffic_summary():
    """Calculate hourly traffic patterns for today - SQLite compatible"""
    today = timezone.now().date()
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    today_end = today_start + timedelta(days=1)
    
    # Get all detections for today
    detections = Detection.objects.filter(timestamp__range=(today_start, today_end))
    
    # Manual grouping by hour for SQLite compatibility
    hourly_counts = {}
    for detection in detections:
        hour = detection.timestamp.hour
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
    
    # Convert to format expected by frontend
    hourly_summary = {f"{hour:02d}:00": count for hour, count in sorted(hourly_counts.items())}
    
    return hourly_summary

def get_system_overview_stats():
    """Get real system overview statistics"""
    total_videos = VideoFile.objects.count()
    processed_videos = VideoFile.objects.filter(processed=True).count()
    total_analyses = TrafficAnalysis.objects.count()
    
    # Recent activity (last 24 hours)
    one_day_ago = timezone.now() - timedelta(hours=24)
    recent_analyses = TrafficAnalysis.objects.filter(analyzed_at__gte=one_day_ago)
    
    # Calculate congested roads (analyses with high congestion)
    congested_roads = TrafficAnalysis.objects.filter(
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

def get_vehicle_type_distribution():
    """Get distribution of vehicle types across all detections"""
    distribution = (
        Detection.objects
        .values('vehicle_type__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    return {item['vehicle_type__name']: item['count'] for item in distribution}

def get_peak_hours_analysis():
    """Get peak hours analysis for each location from TrafficAnalysis data"""
    try:
        # Get all locations with analyses
        locations = Location.objects.filter(
            traffic_analysis__isnull=False
        ).distinct()
        
        areas_data = []
        
        for location in locations:
            # Get analyses for this location
            location_analyses = TrafficAnalysis.objects.filter(location=location)
            
            if not location_analyses.exists():
                continue
            
            # Calculate average vehicles per analysis for this location
            total_vehicles = sum(analysis.total_vehicles for analysis in location_analyses)
            avg_vehicles = total_vehicles / location_analyses.count()
            
            # Use typical peak patterns (you can enhance this with actual Detection data later)
            morning_peak = "7:30 - 9:00 AM"
            evening_peak = "4:30 - 6:30 PM"
            
            # Estimate volumes based on average traffic
            morning_volume = int(avg_vehicles * 0.4)  # 40% in morning peak
            evening_volume = int(avg_vehicles * 0.35)  # 35% in evening peak
            
            areas_data.append({
                'name': location.display_name,
                'morning_peak': morning_peak,
                'evening_peak': evening_peak,
                'morning_volume': morning_volume,
                'evening_volume': evening_volume,
                'total_analysis_vehicles': total_vehicles
            })
        
        # If no location data, return empty
        if not areas_data:
            return [
                {
                    'name': 'No data available',
                    'morning_peak': 'N/A',
                    'evening_peak': 'N/A',
                    'morning_volume': 0,
                    'evening_volume': 0,
                    'total_analysis_vehicles': 0
                }
            ]
        
        return areas_data
        
    except Exception as e:
        print(f"Error getting peak hours analysis: {e}")
        return []
    
def generate_traffic_predictions(location_id=None, days_ahead=7):
    """Generate traffic predictions based on actual TrafficAnalysis data"""
    from .models import TrafficPrediction, TrafficAnalysis
    from django.db.models import Avg
    
    # Clear old predictions
    TrafficPrediction.objects.all().delete()
    
    # Get actual historical data from TrafficAnalysis (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    historical_data = TrafficAnalysis.objects.filter(analyzed_at__gte=thirty_days_ago)
    
    if location_id:
        historical_data = historical_data.filter(location_id=location_id)
        location = Location.objects.get(id=location_id)
    else:
        location = None
    
    if not historical_data.exists():
        print("No TrafficAnalysis data available for predictions")
        return []
    
    predictions = []
    
    # Generate predictions for next days
    for day_offset in range(1, days_ahead + 1):
        prediction_date = timezone.now().date() + timedelta(days=day_offset)
        day_of_week = prediction_date.weekday()
        
        for hour in range(24):
            # Use actual TrafficAnalysis data for predictions
            predicted_count = predict_from_traffic_analysis(historical_data, day_of_week, hour)
            confidence_score = calculate_analysis_confidence(historical_data, day_of_week, hour)
            
            # Determine congestion based on actual traffic patterns
            if predicted_count > 200:
                predicted_congestion = 'severe'
            elif predicted_count > 150:
                predicted_congestion = 'high'
            elif predicted_count > 100:
                predicted_congestion = 'medium'
            elif predicted_count > 50:
                predicted_congestion = 'low'
            else:
                predicted_congestion = 'very_low'
            
            prediction = TrafficPrediction.objects.create(
                location=location,
                prediction_date=prediction_date,
                day_of_week=day_of_week,
                hour_of_day=hour,
                predicted_vehicle_count=predicted_count,
                predicted_congestion=predicted_congestion,
                confidence_score=confidence_score,
                confidence_interval_lower=max(0, predicted_count * 0.8),
                confidence_interval_upper=predicted_count * 1.2,
                model_version="v2.0-traffic-analysis"
            )
            
            predictions.append(prediction)
    
    print(f"Generated {len(predictions)} predictions from TrafficAnalysis data")
    return predictions

def predict_from_traffic_analysis(historical_data, day_of_week, hour):
    """Predict based on TrafficAnalysis historical data"""
    # Get analyses for same day of week
    same_day_analyses = historical_data.filter(
        analyzed_at__week_day=day_of_week + 1  # Django: 1=Sunday, 7=Saturday
    )
    
    if same_day_analyses.exists():
        avg_vehicles = same_day_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 0
        # Apply hourly pattern
        hourly_factor = get_hourly_traffic_factor(hour)
        return int(avg_vehicles * hourly_factor)
    
    # Fallback to overall average
    overall_avg = historical_data.aggregate(avg=Avg('total_vehicles'))['avg'] or 50
    hourly_factor = get_hourly_traffic_factor(hour)
    return int(overall_avg * hourly_factor)

def get_hourly_traffic_factor(hour):
    """Get traffic pattern factor based on hour"""
    # Morning peak: 7-9 AM
    if 7 <= hour <= 9:
        return 1.8
    # Evening peak: 4-7 PM  
    elif 16 <= hour <= 19:
        return 1.6
    # Mid-day: 10 AM - 3 PM
    elif 10 <= hour <= 15:
        return 1.2
    # Late night: 12 AM - 5 AM
    elif hour <= 5:
        return 0.3
    # Other hours
    else:
        return 0.8

def calculate_analysis_confidence(historical_data, day_of_week, hour):
    """Calculate confidence based on TrafficAnalysis data availability"""
    same_day_count = historical_data.filter(
        analyzed_at__week_day=day_of_week + 1
    ).count()
    
    total_count = historical_data.count()
    
    if total_count == 0:
        return 0.3
    
    data_coverage = min(1.0, same_day_count / 4)
    base_confidence = 0.3 + (data_coverage * 0.6)
    
    return min(0.9, base_confidence)

def predict_from_historical_data(historical_analyses, day_of_week, hour):
    """Predict traffic based on actual historical analysis data"""
    # Get analyses for same day of week
    same_day_analyses = historical_analyses.filter(
        analyzed_at__week_day=day_of_week + 1  # Django uses 1=Sunday, 7=Saturday
    )
    
    if same_day_analyses.exists():
        # Use average of same day analyses
        avg_vehicles = same_day_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 0
        
        # Apply hourly pattern (morning/evening peaks)
        hourly_factor = get_hourly_pattern_factor(hour)
        return int(avg_vehicles * hourly_factor)
    
    # Fallback: overall average
    overall_avg = historical_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 50
    hourly_factor = get_hourly_pattern_factor(hour)
    return int(overall_avg * hourly_factor)

def get_hourly_pattern_factor(hour):
    """Get traffic pattern factor based on hour of day"""
    # Morning peak: 7-9 AM
    if 7 <= hour <= 9:
        return 1.8
    # Evening peak: 4-7 PM
    elif 16 <= hour <= 19:
        return 1.6
    # Mid-day: 10 AM - 3 PM
    elif 10 <= hour <= 15:
        return 1.2
    # Late night: 12 AM - 5 AM
    elif hour <= 5:
        return 0.3
    # Other hours
    else:
        return 0.8

def calculate_prediction_confidence(historical_analyses, day_of_week, hour):
    """Calculate confidence score based on data availability"""
    # Count analyses for this day of week
    same_day_count = historical_analyses.filter(
        analyzed_at__week_day=day_of_week + 1
    ).count()
    
    total_count = historical_analyses.count()
    
    if total_count == 0:
        return 0.3
    
    # Base confidence on data availability and consistency
    data_coverage = min(1.0, same_day_count / 4)  # At least 4 samples for good confidence
    base_confidence = 0.3 + (data_coverage * 0.6)
    
    return min(0.9, base_confidence)

def predict_hourly_traffic(historical_data, day_of_week, hour):
    """Simple prediction algorithm based on historical patterns"""
    # Filter historical data for same day of week and hour
    similar_data = [
        det for det in historical_data 
        if det.timestamp.weekday() == day_of_week and det.timestamp.hour == hour
    ]
    
    if not similar_data:
        # Fallback: average of all data for that hour
        similar_data = [det for det in historical_data if det.timestamp.hour == hour]
    
    if not similar_data:
        # Default patterns based on common traffic flows
        if 7 <= hour <= 9:  # Morning rush hour
            return 120
        elif 16 <= hour <= 18:  # Evening rush hour
            return 110
        elif 10 <= hour <= 15:  # Mid-day
            return 80
        else:  # Early morning/late evening
            return 30
    
    # Calculate average count for this time slot
    hourly_counts = {}
    for detection in similar_data:
        hour_key = f"{detection.timestamp.date()}_{hour}"
        hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1
    
    if hourly_counts:
        average_count = sum(hourly_counts.values()) / len(hourly_counts)
        return int(average_count)
    
    return 50  # Fallback default

def calculate_confidence(historical_data, day_of_week, hour):
    """Calculate confidence score for predictions (0.0 to 1.0)"""
    # Count how much historical data we have for this time slot
    similar_data = [
        det for det in historical_data 
        if det.timestamp.weekday() == day_of_week and det.timestamp.hour == hour
    ]
    
    if not similar_data:
        return 0.3  # Low confidence for no historical data
    
    # More data = higher confidence
    data_points = len(similar_data)
    if data_points > 100:
        return 0.9
    elif data_points > 50:
        return 0.7
    elif data_points > 20:
        return 0.5
    else:
        return 0.4

def get_traffic_predictions_for_date(date=None, location_id=None):
    """Get predictions for a specific date (default: tomorrow)"""
    if date is None:
        date = timezone.now().date() + timedelta(days=1)
    
    predictions = TrafficPrediction.objects.filter(prediction_date=date)
    
    if location_id:
        predictions = predictions.filter(location_id=location_id)
    
    return predictions.order_by('hour_of_day')

def get_peak_prediction_hours(date=None, location_id=None):
    """Get peak traffic hours from predictions"""
    predictions = get_traffic_predictions_for_date(date, location_id)
    
    if not predictions.exists():
        return []
    
    # Find hours with highest predicted traffic
    hourly_predictions = {}
    for pred in predictions:
        hourly_predictions[pred.hour_of_day] = pred.predicted_vehicle_count
    
    # Get top 3 peak hours
    peak_hours = sorted(hourly_predictions.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return [
        {
            'hour': f"{hour:02d}:00",
            'predicted_vehicles': count,
            'congestion_level': next(p.predicted_congestion for p in predictions if p.hour_of_day == hour)
        }
        for hour, count in peak_hours
    ]