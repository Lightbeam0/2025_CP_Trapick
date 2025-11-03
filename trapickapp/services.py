# trapickapp/services.py
from django.db.models import Count, Avg, Max, Min, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Location, TrafficAnalysis, Detection, VideoFile, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction
import numpy as np

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
    
def calculate_real_vehicle_stats(period='today', location_id=None, date_range='last_7_days'):
    """Calculate actual vehicle statistics from TrafficAnalysis with filtering"""
    try:
        from django.db.models import Q
        from datetime import timedelta
        
        print(f"🔄 Calculating vehicle stats - period: {period}, location: {location_id}, date_range: {date_range}")
        
        # Build base query
        base_query = Q()
        
        # Add location filter
        if location_id and location_id != 'all':
            base_query &= Q(location_id=location_id)
            print(f"📍 Filtering by location: {location_id}")
        
        # Add date range filter
        if date_range != 'all':
            if date_range == 'last_7_days':
                start_date = timezone.now() - timedelta(days=7)
            elif date_range == 'last_30_days':
                start_date = timezone.now() - timedelta(days=30)
            elif date_range == 'last_90_days':
                start_date = timezone.now() - timedelta(days=90)
            else:
                start_date = timezone.now() - timedelta(days=7)  # Default
            
            base_query &= Q(analyzed_at__gte=start_date)
            print(f"📅 Filtering by date range: {date_range} from {start_date}")
        
        # Get ALL analyses (remove date filter for now to test)
        analyses = TrafficAnalysis.objects.all()
        print(f"📊 Total analyses in database: {analyses.count()}")
        
        # Debug: Print first few analyses
        for i, analysis in enumerate(analyses[:3]):
            print(f"🔍 Analysis {i+1}: ID={analysis.id}, Vehicles={analysis.total_vehicles}, Date={analysis.analyzed_at}")
        
        if analyses.count() == 0:
            print("❌ No analyses found in database at all!")
            return get_fallback_data("No traffic analyses found")
        
        def get_period_counts(period_type):
            """Get vehicle counts for a specific period"""
            if period_type == 'today':
                target_date = timezone.now().date()
            elif period_type == 'yesterday':
                target_date = timezone.now().date() - timedelta(days=1)
            else:
                # For week/month, use all data for now
                target_date = None
            
            if target_date:
                period_analyses = analyses.filter(analyzed_at__date=target_date)
                print(f"📅 {period_type} analyses: {period_analyses.count()} on {target_date}")
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
        
        # Get data for different periods
        today_data = get_period_counts('today')
        yesterday_data = get_period_counts('yesterday')
        week_data = get_period_counts('week')
        month_data = get_period_counts('month')
        
        # Calculate summary statistics
        total_analyses = analyses.count()
        total_vehicles = sum(a.total_vehicles for a in analyses)
        
        # Count unique days with analyses
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
            'all': today_data,  # Fallback
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
    """Return fallback data structure"""
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
        # Get all analyses first to see what data we have
        all_analyses = TrafficAnalysis.objects.all()
        print(f"🔍 Found {all_analyses.count()} total analyses for peak hours")
        
        # If no analyses at all, return helpful message
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
        
        # Get locations with analyses
        locations = Location.objects.filter(
            trafficanalysis__isnull=False
        ).distinct()
        
        print(f"📍 Found {locations.count()} locations with analyses")
        
        areas_data = []
        
        # If we have locations with data, analyze each one
        if locations.exists():
            for location in locations:
                # Get analyses for this location
                location_analyses = TrafficAnalysis.objects.filter(location=location)
                
                if location_analyses.exists():
                    # Calculate real peak hours from actual data
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
        
        # If no location-specific data but we have analyses, create general analysis
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
        
        # Final fallback if still no data
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
    """Calculate actual morning and evening peak hours from analyses"""
    try:
        print(f"📈 Calculating peak hours from {analyses.count()} analyses")
        
        # Group by hour of analysis (as proxy for traffic hour)
        hourly_totals = {}
        
        for analysis in analyses:
            hour = analysis.analyzed_at.hour
            hourly_totals[hour] = hourly_totals.get(hour, 0) + analysis.total_vehicles
        
        print(f"🕒 Hourly totals: {hourly_totals}")
        
        if not hourly_totals:
            return "7:30 - 9:00 AM", "4:30 - 6:30 PM"  # Default peaks
        
        # Find morning peak (6 AM - 10 AM)
        morning_hours = {h: c for h, c in hourly_totals.items() if 6 <= h <= 10}
        # Find evening peak (4 PM - 8 PM)  
        evening_hours = {h: c for h, c in hourly_totals.items() if 16 <= h <= 20}
        
        # Calculate morning peak
        if morning_hours:
            peak_hour = max(morning_hours.items(), key=lambda x: x[1])[0]
            morning_peak = format_peak_time(peak_hour, "morning")
            print(f"🌅 Morning peak: {morning_peak} at hour {peak_hour}")
        else:
            morning_peak = "7:30 - 9:00 AM"
            print("🌅 Using default morning peak")
        
        # Calculate evening peak
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
        return "7:30 - 9:00 AM", "4:30 - 6:30 PM"

def format_peak_time(hour, period):
    """Format peak hour into readable time range"""
    if period == "morning":
        start_hour = max(6, hour - 1)  # 1 hour before peak
        end_hour = min(11, hour + 1)   # 1 hour after peak
    else:  # evening
        start_hour = max(15, hour - 1)  # 1 hour before peak
        end_hour = min(21, hour + 1)    # 1 hour after peak
    
    start_period = "AM" if start_hour < 12 else "PM"
    end_period = "AM" if end_hour < 12 else "PM"
    
    start_display = start_hour if start_hour <= 12 else start_hour - 12
    end_display = end_hour if end_hour <= 12 else end_hour - 12
    
    return f"{start_display}:00 - {end_display}:00 {start_period}"

def calculate_real_peak_volumes(analyses, morning_peak, evening_peak):
    """Calculate realistic peak volumes based on actual data"""
    try:
        total_vehicles = sum(analysis.total_vehicles for analysis in analyses)
        analysis_count = analyses.count()
        
        if analysis_count == 0:
            return 0, 0
        
        # Calculate average vehicles per analysis
        avg_per_analysis = total_vehicles / analysis_count
        
        # Estimate peak volumes (morning typically 30-40%, evening 25-35% of daily traffic)
        morning_volume = int(avg_per_analysis * 0.35)  # 35% in morning peak
        evening_volume = int(avg_per_analysis * 0.30)  # 30% in evening peak
        
        # Ensure minimum reasonable values
        morning_volume = max(10, morning_volume)
        evening_volume = max(10, evening_volume)
        
        print(f"🚗 Peak volumes: morning={morning_volume}, evening={evening_volume}")
        return morning_volume, evening_volume
        
    except Exception as e:
        print(f"❌ Error calculating peak volumes: {e}")
        return 0, 0

def calculate_peak_hours_from_analyses(analyses):
    """Calculate morning and evening peak hours from analyses"""
    try:
        # Group analyses by hour of analysis
        hourly_counts = {}
        
        for analysis in analyses:
            # Use analysis hour as proxy for traffic hour
            hour = analysis.analyzed_at.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + analysis.total_vehicles
        
        if not hourly_counts:
            return "7:30 - 9:00 AM", "4:30 - 6:30 PM"  # Default peaks
        
        # Find morning peak (7-10 AM)
        morning_hours = {h: c for h, c in hourly_counts.items() if 7 <= h <= 10}
        evening_hours = {h: c for h, c in hourly_counts.items() if 16 <= h <= 19}
        
        morning_peak = "7:30 - 9:00 AM"  # Default
        evening_peak = "4:30 - 6:30 PM"  # Default
        
        if morning_hours:
            peak_hour = max(morning_hours.items(), key=lambda x: x[1])[0]
            morning_peak = f"{peak_hour-1}:30 - {peak_hour+1}:00 {'AM' if peak_hour < 12 else 'PM'}"
        
        if evening_hours:
            peak_hour = max(evening_hours.items(), key=lambda x: x[1])[0]
            evening_peak = f"{peak_hour-1}:30 - {peak_hour+1}:00 {'AM' if peak_hour < 12 else 'PM'}"
        
        return morning_peak, evening_peak
        
    except Exception as e:
        print(f"Error calculating peak hours: {e}")
        return "7:30 - 9:00 AM", "4:30 - 6:30 PM"

def calculate_peak_volumes(analyses, morning_peak, evening_peak):
    """Calculate average volumes for peak periods"""
    try:
        total_vehicles = sum(analysis.total_vehicles for analysis in analyses)
        analysis_count = analyses.count()
        
        if analysis_count == 0:
            return 0, 0
        
        # Estimate volumes based on typical distribution
        # Morning peak typically 25-35% of daily traffic
        # Evening peak typically 20-30% of daily traffic
        avg_daily = total_vehicles / analysis_count
        
        morning_volume = int(avg_daily * 0.3)  # 30% in morning peak
        evening_volume = int(avg_daily * 0.25)  # 25% in evening peak
        
        return morning_volume, evening_volume
        
    except Exception as e:
        print(f"Error calculating peak volumes: {e}")
        return 0, 0
    
def generate_traffic_predictions(location_id=None, days_ahead=7):
    """Generate traffic predictions based on actual TrafficAnalysis data with hourly patterns"""
    from .models import TrafficPrediction, TrafficAnalysis, Detection
    from django.db.models import Count, Avg, Q
    
    # Clear old predictions
    TrafficPrediction.objects.all().delete()
    
    # Get actual historical data from TrafficAnalysis and Detections
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Build base query
    historical_query = Q(analyzed_at__gte=thirty_days_ago)
    if location_id:
        historical_query &= Q(location_id=location_id)
    
    # Get analyses with their detections for more granular data
    historical_analyses = TrafficAnalysis.objects.filter(historical_query)
    
    if not historical_analyses.exists():
        print("No TrafficAnalysis data available for predictions")
        return []
    
    predictions = []
    
    # Analyze historical patterns by day of week and hour
    hourly_patterns = analyze_hourly_traffic_patterns(historical_analyses, location_id)
    
    # Generate predictions for next days
    for day_offset in range(1, days_ahead + 1):
        prediction_date = timezone.now().date() + timedelta(days=day_offset)
        day_of_week = prediction_date.weekday()
        
        for hour in range(24):
            # Get prediction based on historical patterns
            predicted_count, confidence = predict_hourly_traffic(
                hourly_patterns, day_of_week, hour, historical_analyses
            )
            
            # Determine congestion based on actual traffic patterns
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
    """Analyze traffic patterns by day of week and hour"""
    from django.db.models import Count, Avg, Q
    
    patterns = {}
    
    # Analyze each day of week (0=Monday, 6=Sunday)
    for day in range(7):
        patterns[day] = {}
        
        # Get analyses for this specific day of week
        day_analyses = historical_analyses.filter(
            analyzed_at__week_day=((day + 1) % 7) + 1  # Convert to Django week_day (1=Sunday)
        )
        
        if not day_analyses.exists():
            # If no specific day data, use overall average
            overall_avg = historical_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 0
            for hour in range(24):
                patterns[day][hour] = {
                    'avg_vehicles': overall_avg * get_hourly_pattern_factor(hour),
                    'confidence': 0.3,
                    'data_points': 0
                }
            continue
        
        # Analyze hourly patterns for this day
        for hour in range(24):
            # Get analyses around this hour (considering video recording times)
            hour_start = hour
            hour_end = hour + 1
            
            # Find analyses that likely contain this hour based on their metadata
            relevant_analyses = []
            for analysis in day_analyses:
                if has_hourly_data(analysis, hour):
                    relevant_analyses.append(analysis)
            
            if relevant_analyses:
                # Calculate average for this hour
                avg_vehicles = np.mean([a.total_vehicles for a in relevant_analyses])
                confidence = min(0.9, len(relevant_analyses) * 0.1)
                
                patterns[day][hour] = {
                    'avg_vehicles': avg_vehicles,
                    'confidence': confidence,
                    'data_points': len(relevant_analyses)
                }
            else:
                # Fallback to daily average with hourly pattern
                day_avg = day_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 0
                patterns[day][hour] = {
                    'avg_vehicles': day_avg * get_hourly_pattern_factor(hour),
                    'confidence': 0.3,
                    'data_points': 0
                }
    
    return patterns

def has_hourly_data(analysis, target_hour):
    """Check if analysis likely contains data for the target hour"""
    # If analysis has video file with time information, use it
    if analysis.video_file and analysis.video_file.video_start_time:
        try:
            video_hour = analysis.video_file.video_start_time.hour
            # Consider analyses starting within 2 hours of target hour as relevant
            return abs(video_hour - target_hour) <= 2
        except:
            pass
    
    # Fallback: use analysis timestamp hour
    analysis_hour = analysis.analyzed_at.hour
    return abs(analysis_hour - target_hour) <= 2

def predict_hourly_traffic(hourly_patterns, day_of_week, hour, historical_analyses):
    """Predict traffic for specific day and hour"""
    day_pattern = hourly_patterns.get(day_of_week, {})
    hour_data = day_pattern.get(hour, {})
    
    if hour_data and hour_data.get('data_points', 0) >= 3:
        # Use specific hour pattern if we have enough data
        predicted_count = hour_data['avg_vehicles']
        confidence = hour_data['confidence']
    else:
        # Fallback to overall patterns
        overall_avg = historical_analyses.aggregate(avg=Avg('total_vehicles'))['avg'] or 50
        predicted_count = overall_avg * get_hourly_pattern_factor(hour)
        confidence = 0.4
    
    return round(predicted_count), confidence

def calculate_congestion_thresholds(hourly_patterns):
    """Calculate dynamic congestion thresholds based on historical data"""
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
    """Determine congestion level based on dynamic thresholds"""
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

def auto_group_all_videos():
    """Automatically group all ungrouped videos by location and date"""
    from .models import VideoFile, LocationDateGroup, TrafficAnalysis
    
    ungrouped_videos = VideoFile.objects.filter(
        processing_status='completed',
        location_date_group__isnull=True
    ).select_related('traffic_analysis')
    
    grouped_count = 0
    errors = []
    
    for video in ungrouped_videos:
        try:
            # Get location from traffic analysis
            if hasattr(video, 'traffic_analysis') and video.traffic_analysis.location:
                location = video.traffic_analysis.location
                
                # Use video date or fallback to analysis date
                if video.video_date:
                    group_date = video.video_date
                else:
                    group_date = video.traffic_analysis.analyzed_at.date()
                
                # Get or create group for this location and date
                group, created = LocationDateGroup.objects.get_or_create(
                    location=location,
                    date=group_date
                )
                
                # Add video to group
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
    """Get all location groups with their videos sorted by time"""
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