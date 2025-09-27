# check_analysis_results.py
import requests
import json

def check_latest_analysis():
    print("=== CHECKING LATEST VIDEO ANALYSIS ===")
    
    # First, get the list of videos to find the latest one
    response = requests.get('http://127.0.0.1:8000/api/videos/')
    videos = response.json()
    
    if videos:
        latest_video = videos[0]  # Most recent video
        video_id = latest_video['id']
        print(f"Latest video: {latest_video['filename']}")
        print(f"Status: {latest_video['processing_status']}")
        
        # Get the analysis results
        analysis_response = requests.get(f'http://127.0.0.1:8000/api/analysis/{video_id}/')
        analysis_data = analysis_response.json()
        
        print("\n📊 ANALYSIS RESULTS:")
        print(f"Status: {analysis_data.get('status')}")
        
        if analysis_data.get('status') == 'completed':
            analysis = analysis_data.get('analysis', {})
            print(f"✅ Total vehicles detected: {analysis.get('total_vehicles', 0)}")
            print(f"🚗 Vehicle breakdown: {json.dumps(analysis.get('vehicle_breakdown', {}), indent=2)}")
            print(f"⏱️ Processing time: {analysis.get('processing_time', 0):.2f} seconds")
            print(f"🚦 Congestion level: {analysis.get('congestion_level', 'Unknown')}")
            print(f"📈 Traffic pattern: {analysis.get('traffic_pattern', 'Unknown')}")
            
            # Additional metrics from the detailed analysis
            video_info = analysis_data.get('video_info', {})
            print(f"🎥 Video duration: {video_info.get('duration', 'Unknown')} seconds")
            print(f"📅 Analyzed at: {analysis.get('analyzed_at', 'Unknown')}")
            
        else:
            print(f"Analysis status: {analysis_data.get('message', 'Unknown')}")
    else:
        print("No videos found in database")

if __name__ == "__main__":
    check_latest_analysis()