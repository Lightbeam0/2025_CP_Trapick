import requests
import time
import json

def test_with_progress_monitoring():
    """Test upload with detailed progress monitoring"""
    url = "http://127.0.0.1:8000/upload/video/"
    
    # Use a SMALL test video for quick testing
    video_path = "test_short.mp4"  # Make sure this is a short video (5-30 seconds)
    
    files = {'video': open(video_path, 'rb')}
    data = {
        'title': 'Progress Test',
        'location_id': '1',
        'video_date': '2024-01-15'
    }
    
    print("🚀 Starting upload with progress monitoring...")
    
    try:
        response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            upload_id = result['upload_id']
            print(f"✅ Upload successful! ID: {upload_id}")
            
            # Monitor progress
            print("🔍 Monitoring progress...")
            progress_url = f"http://127.0.0.1:8000/progress/{upload_id}/"
            
            for i in range(60):  # Monitor for up to 10 minutes
                try:
                    progress_response = requests.get(progress_url)
                    if progress_response.status_code == 200:
                        progress_data = progress_response.json()
                        progress = progress_data.get('progress', 0)
                        message = progress_data.get('message', '')
                        
                        print(f"🔄 [{i:02d}] Progress: {progress}% - {message}")
                        
                        if progress == 100:
                            print("🎉 Processing completed successfully!")
                            break
                        elif progress == 0 and "failed" in message.lower():
                            print("❌ Processing failed!")
                            break
                            
                    else:
                        print(f"❌ Error fetching progress: {progress_response.status_code}")
                        
                except Exception as e:
                    print(f"❌ Progress check error: {e}")
                
                time.sleep(10)  # Check every 10 seconds
            
            # Check final results
            print("\n📊 Checking final results...")
            analysis_url = f"http://127.0.0.1:8000/analysis/{upload_id}/"
            analysis_response = requests.get(analysis_url)
            
            if analysis_response.status_code == 200:
                analysis_data = analysis_response.json()
                print("✅ Analysis completed!")
                print(f"   - Status: {analysis_data.get('status')}")
                if analysis_data.get('analysis'):
                    print(f"   - Total vehicles: {analysis_data['analysis'].get('total_vehicles')}")
            else:
                print(f"❌ Analysis not ready: {analysis_response.status_code}")
                
        else:
            print(f"❌ Upload failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        files['video'].close()

if __name__ == "__main__":
    test_with_progress_monitoring()