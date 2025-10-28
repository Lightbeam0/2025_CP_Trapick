import os
import django
import json
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

from trapickapp.models import *

def export_analysis_data():
    """Export only viewable data for cloud deployment"""
    
    export_data = {
        'timestamp': datetime.now().isoformat(),
        'traffic_analyses': [],
        'locations': [],
        'processing_profiles': [],
        'predictions': [],
        'hourly_summaries': [],
        'daily_summaries': []
    }
    
    # Export Traffic Analyses (without video file data)
    for analysis in TrafficAnalysis.objects.all():
        export_data['traffic_analyses'].append({
            'id': str(analysis.id),
            'total_vehicles': analysis.total_vehicles,
            'processing_time_seconds': analysis.processing_time_seconds,
            'analyzed_at': analysis.analyzed_at.isoformat(),
            'car_count': analysis.car_count,
            'truck_count': analysis.truck_count,
            'motorcycle_count': analysis.motorcycle_count,
            'bus_count': analysis.bus_count,
            'bicycle_count': analysis.bicycle_count,
            'other_count': analysis.other_count,
            'peak_traffic': analysis.peak_traffic,
            'average_traffic': analysis.average_traffic,
            'congestion_level': analysis.congestion_level,
            'traffic_pattern': analysis.traffic_pattern,
            'location_id': analysis.location.id if analysis.location else None,
            'analysis_session_id': str(analysis.analysis_session.id) if analysis.analysis_session else None
        })
    
    # Export Locations
    for location in Location.objects.all():
        export_data['locations'].append({
            'id': location.id,
            'name': location.name,
            'display_name': location.display_name,
            'description': location.description,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'processing_profile_id': location.processing_profile.id if location.processing_profile else None
        })
    
    # Export Processing Profiles
    for profile in ProcessingProfile.objects.all():
        export_data['processing_profiles'].append({
            'id': profile.id,
            'name': profile.name,
            'display_name': profile.display_name,
            'description': profile.description,
            'detector_class': profile.detector_class,
            'road_type': profile.road_type,
            'active': profile.active
        })
    
    # Save to JSON file
    with open('exported_data.json', 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"✅ Exported {len(export_data['traffic_analyses'])} analyses to exported_data.json")

if __name__ == '__main__':
    export_analysis_data()