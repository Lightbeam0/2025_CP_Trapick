# trapickapp/services.py
from django.db.models import Count, Avg, Max, Min, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from .models import TrafficAnalysis, Detection, VideoFile, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction

def calculate_real_weekly_data():
    """Calculate actual weekly vehicle counts from TrafficAnalysis"""
    try:
        one_week_ago = timezone.now() - timedelta(days=7)
        
        # Get analyses from last 7 days
        recent_analyses = TrafficAnalysis.objects.filter(analyzed_at__gte=one_week_ago)
        
        if not recent_analyses.exists():
            print("No recent analyses found for weekly data")
            return [0, 0, 0, 0, 0, 0, 0]  # Return zeros for frontend
        
        # Group by day and sum vehicles
        daily_data = []
        for i in range(7):
            day = one_week_ago + timedelta(days=i)
            day_analyses = recent_analyses.filter(analyzed_at__date=day)
            total_vehicles = sum(analysis.total_vehicles for analysis in day_analyses)
            daily_data.append(total_vehicles)
        
        print(f"Weekly data calculated: {daily_data}")
        return daily_data
        
    except Exception as e:
        print(f"Error calculating weekly data: {e}")
        return [0, 0, 0, 0, 0, 0, 0]

def calculate_real_vehicle_stats():
    """Calculate actual vehicle statistics from Detection model"""
    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        def get_daily_counts(date):
            """Get vehicle counts for a specific date"""
            try:
                # Try to get from TrafficAnalysis first (more reliable)
                analyses = TrafficAnalysis.objects.filter(analyzed_at__date=date)
                if analyses.exists():
                    return {
                        'cars': sum(a.car_count for a in analyses),
                        'trucks': sum(a.truck_count for a in analyses),
                        'buses': sum(a.bus_count for a in analyses),
                        'motorcycles': sum(a.motorcycle_count for a in analyses),
                        'bicycles': sum(a.bicycle_count for a in analyses),
                        'others': sum(a.other_count for a in analyses)
                    }
                
                # Fallback to Detection model
                detections = Detection.objects.filter(timestamp__date=date)
                return {
                    'cars': detections.filter(vehicle_type__name='car').count(),
                    'trucks': detections.filter(vehicle_type__name='truck').count(),
                    'buses': detections.filter(vehicle_type__name='bus').count(),
                    'motorcycles': detections.filter(vehicle_type__name='motorcycle').count(),
                    'bicycles': detections.filter(vehicle_type__name='bicycle').count(),
                    'others': detections.filter(vehicle_type__name='other').count()
                }
            except Exception as e:
                print(f"Error getting daily counts for {date}: {e}")
                return {'cars': 0, 'trucks': 0, 'buses': 0, 'motorcycles': 0, 'bicycles': 0, 'others': 0}
        
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
    """Calculate real congestion data from TrafficAnalysis"""
    # Get recent analyses with locations
    recent_analyses = TrafficAnalysis.objects.filter(
        location__isnull=False
    ).select_related('location').order_by('-analyzed_at')[:10]
    
    if not recent_analyses.exists():
        return []  # Return empty instead of fake data
    
    congestion_data = []
    
    for analysis in recent_analyses:
        # Calculate vehicles per hour
        video_duration_hours = analysis.video_file.duration_seconds / 3600 if analysis.video_file.duration_seconds else 1
        vehicles_per_hour = analysis.total_vehicles / video_duration_hours if video_duration_hours > 0 else 0
        
        # Determine congestion level based on vehicles per hour
        if vehicles_per_hour > 2000:
            congestion_level = 'High'
        elif vehicles_per_hour > 1000:
            congestion_level = 'Medium'
        else:
            congestion_level = 'Low'
        
        # Determine trend
        if analysis.traffic_pattern == 'increasing':
            trend = 'increasing'
        elif analysis.traffic_pattern == 'decreasing':
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        congestion_data.append({
            'road': f"{analysis.location.display_name} Road",
            'area': analysis.location.display_name,
            'time': analysis.analyzed_at.strftime('%I:%M %p'),
            'congestion_level': congestion_level,
            'vehicles_per_hour': int(vehicles_per_hour),
            'trend': trend
        })
    
    return congestion_data

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
    total_detections = Detection.objects.count()
    
    # Recent activity (last 24 hours)
    one_day_ago = timezone.now() - timedelta(hours=24)
    recent_analyses = TrafficAnalysis.objects.filter(analyzed_at__gte=one_day_ago)
    recent_detections = Detection.objects.filter(timestamp__gte=one_day_ago)
    
    return {
        'total_videos': total_videos,
        'processed_videos': processed_videos,
        'total_analyses': total_analyses,
        'total_detections': total_detections,
        'recent_analyses_count': recent_analyses.count(),
        'recent_detections_count': recent_detections.count(),
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
    """Analyze peak traffic hours across all data - SQLite compatible"""
    # Get all detections
    detections = Detection.objects.all()
    
    # Manual grouping by hour for SQLite compatibility
    hourly_counts = {}
    hourly_confidence = {}
    
    for detection in detections:
        hour = detection.timestamp.hour
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        hourly_confidence[hour] = hourly_confidence.get(hour, []) + [detection.confidence]
    
    # Find peak hour
    if hourly_counts:
        peak_hour = max(hourly_counts.items(), key=lambda x: x[1])
        hour = peak_hour[0]
        count = peak_hour[1]
        avg_confidence = sum(hourly_confidence[hour]) / len(hourly_confidence[hour]) if hour in hourly_confidence else 0
        
        return {
            'peak_hour': f"{hour:02d}:00",
            'peak_hour_count': count,
            'average_confidence': float(avg_confidence)
        }
    
    return {
        'peak_hour': '08:00',
        'peak_hour_count': 0,
        'average_confidence': 0
    }

def generate_traffic_predictions(location_id=None, days_ahead=7):
    """Generate traffic predictions based on historical data"""
    from .models import TrafficPrediction, Detection, Location
    
    # Clear old predictions
    TrafficPrediction.objects.all().delete()
    
    # Get historical data (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    historical_data = Detection.objects.filter(timestamp__gte=thirty_days_ago)
    
    if location_id:
        historical_data = historical_data.filter(location_id=location_id)
        location = Location.objects.get(id=location_id)
    else:
        location = None
    
    if not historical_data.exists():
        print("No historical data available for predictions")
        return []
    
    predictions = []
    
    # Generate predictions for next 7 days
    for day_offset in range(days_ahead):
        prediction_date = timezone.now().date() + timedelta(days=day_offset)
        day_of_week = prediction_date.weekday()  # 0=Monday, 6=Sunday
        
        for hour in range(6, 22):  # 6 AM to 10 PM
            # Simple prediction algorithm (can be enhanced with ML later)
            predicted_count = predict_hourly_traffic(historical_data, day_of_week, hour)
            confidence_score = calculate_confidence(historical_data, day_of_week, hour)
            
            # Determine congestion level
            if predicted_count > 150:
                predicted_congestion = 'severe'
            elif predicted_count > 100:
                predicted_congestion = 'high'
            elif predicted_count > 50:
                predicted_congestion = 'medium'
            elif predicted_count > 20:
                predicted_congestion = 'low'
            else:
                predicted_congestion = 'very_low'
            
            # Create prediction record
            prediction = TrafficPrediction.objects.create(
                location=location,
                prediction_date=prediction_date,
                day_of_week=day_of_week,
                hour_of_day=hour,
                predicted_vehicle_count=predicted_count,
                predicted_congestion=predicted_congestion,
                confidence_score=confidence_score,
                confidence_interval_lower=max(0, predicted_count * 0.7),
                confidence_interval_upper=predicted_count * 1.3,
                model_version="v1.0"
            )
            
            predictions.append(prediction)
    
    print(f"Generated {len(predictions)} traffic predictions")
    return predictions

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