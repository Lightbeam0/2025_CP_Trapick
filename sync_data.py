#!/usr/bin/env python
# sync_data.py - Simple sync script for original system
import requests
import json
import logging
from datetime import datetime, timedelta
import os
import sys

# Setup Django
sys.path.append(os.getcwd())  # Add current directory to path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')

import django
django.setup()

from trapickapp.models import Location, VideoFile, TrafficAnalysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_location(location_id, deployed_url, api_key):
    """Sync data for one location from yesterday"""
    try:
        # Get yesterday's date
        yesterday = datetime.now().date() - timedelta(days=1)
        
        # Get location
        location = Location.objects.get(id=location_id)
        logger.info(f"Syncing {location.display_name} for {yesterday}")
        
        # Get all videos for this location from yesterday
        videos = VideoFile.objects.filter(
            traffic_analysis__location=location,
            video_date=yesterday,
            processing_status='completed'
        ).select_related('traffic_analysis')
        
        if not videos.exists():
            logger.info(f"No videos found for {yesterday}")
            return False
        
        # Prepare data
        analyses = []
        for video in videos:
            if hasattr(video, 'traffic_analysis'):
                analysis = video.traffic_analysis
                
                analyses.append({
                    'time_interval': f"{video.video_start_time.strftime('%H:%M') if video.video_start_time else '00:00'}-{video.video_end_time.strftime('%H:%M') if video.video_end_time else '23:59'}",
                    'vehicle_count': analysis.total_vehicles,
                    'congestion_level': analysis.congestion_level,
                    'avg_speed': analysis.avg_speed,
                    'vehicle_breakdown': {
                        'car': analysis.car_count,
                        'truck': analysis.truck_count,
                        'motorcycle': analysis.motorcycle_count,
                        'bus': analysis.bus_count,
                        'bicycle': analysis.bicycle_count,
                        'other': analysis.other_count
                    }
                })
        
        # Prepare sync data
        sync_data = {
            'location_id': location.id,
            'location_name': location.display_name,
            'date': yesterday.isoformat(),
            'analyses': analyses
        }
        
        # Send to deployed system
        headers = {
            'X-Sync-API-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            f"{deployed_url.rstrip('/')}/api/sync-data/",
            json=sync_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info(f"✓ Successfully synced {len(analyses)} videos")
            return True
        else:
            logger.error(f"✗ Failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


def sync_all_locations(deployed_url, api_key):
    """Sync all locations with recent data"""
    # Get all locations
    locations = Location.objects.all()
    
    success = 0
    failed = 0
    
    for location in locations:
        if sync_location(location.id, deployed_url, api_key):
            success += 1
        else:
            failed += 1
    
    logger.info(f"Sync complete: {success} succeeded, {failed} failed")
    return success, failed


if __name__ == "__main__":
    # CONFIGURE THESE VALUES
    DEPLOYED_URL = "http://localhost:8001"  # Change to your deployed URL
    API_KEY = "test-key"  # Change to your actual API key
    
    print("=" * 50)
    print("Trapick Data Sync Tool")
    print("=" * 50)
    print(f"Target: {DEPLOYED_URL}")
    
    # Simple menu
    print("\nOptions:")
    print("1. Sync all locations (yesterday's data)")
    print("2. Sync specific location")
    print("3. Test connection")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        print("Syncing all locations...")
        sync_all_locations(DEPLOYED_URL, API_KEY)
        
    elif choice == "2":
        # Show available locations
        locations = Location.objects.all()
        print("\nAvailable locations:")
        for loc in locations:
            print(f"  {loc.id}: {loc.display_name}")
        
        loc_id = input("\nEnter location ID: ").strip()
        if loc_id:
            sync_location(int(loc_id), DEPLOYED_URL, API_KEY)
            
    elif choice == "3":
        # Test connection
        try:
            response = requests.get(f"{DEPLOYED_URL.rstrip('/')}/api/sync-health/", timeout=10)
            if response.status_code == 200:
                print("✓ Connection successful")
            else:
                print(f"✗ Connection failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Cannot connect: {e}")
    
    print("\nDone!")