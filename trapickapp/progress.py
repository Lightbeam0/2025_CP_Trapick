# trapickapp/progress.py
import json
import os
import time
import redis

try:
    redis_client = redis.Redis(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=int(os.environ.get('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
    print("✅ Redis connected for progress tracking")
except:
    REDIS_AVAILABLE = False
    print("⚠️ Redis not available, using in-memory progress store")

# Fallback in-memory storage
progress_store = {}

def get_all_active_progress():
    """Get all active video progress for sidebar display"""
    active_progress = {}

    if REDIS_AVAILABLE:
        try:
            # Get all progress keys matching the pattern
            keys = redis_client.keys('video_progress_*')
            for key in keys:
                data = redis_client.get(key)
                if data:
                    progress_data = json.loads(data)
                    # Only include recent progress (last 10 minutes)
                    if time.time() - progress_data['timestamp'] <= 600:
                        video_id = progress_data['video_id']
                        active_progress[video_id] = progress_data
        except Exception as e:
            print(f"Error getting Redis progress: {e}")

    # Add in-memory progress data
    for video_id, data in progress_store.items():
        if time.time() - data['timestamp'] <= 600:
            active_progress[video_id] = data

    return active_progress

class ProgressTracker:
    def __init__(self, video_id):
        self.video_id = str(video_id)
        self.channel_layer = None
        self.room_group_name = f'video_progress_{self.video_id}'
        self.general_group_name = 'general_progress'

    def _get_channel_layer(self):
        """Lazy load channel layer to avoid import issues"""
        if self.channel_layer is None:
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                self.channel_layer = get_channel_layer()
                self.async_to_sync = async_to_sync
            except Exception as e:
                print(f"❌ Error getting channel layer: {e}")
                # Create a mock channel layer that won't crash
                self.channel_layer = type('MockChannelLayer', (), {})()
                self.async_to_sync = lambda func: func
        return self.channel_layer

    def _store_progress(self, progress, message):
        """Store progress data persistently"""
        data = {
            'progress': max(0, min(100, progress)),
            'message': message,
            'timestamp': time.time(),
            'video_id': self.video_id
        }

        # Try Redis first, fallback to memory
        if REDIS_AVAILABLE:
            try:
                redis_client.setex(
                    f'video_progress_{self.video_id}',
                    3600,  # 1 hour expiry
                    json.dumps(data)
                )
            except Exception as e:
                print(f"Redis store error: {e}")
                progress_store[self.video_id] = data
        else:
            progress_store[self.video_id] = data

        return data

    def _get_progress(self):
        """Retrieve progress data"""
        if REDIS_AVAILABLE:
            try:
                data = redis_client.get(f'video_progress_{self.video_id}')
                if data:
                    return json.loads(data)
            except Exception as e:
                print(f"Redis get error: {e}")

        return progress_store.get(self.video_id)

    def _broadcast_to_groups(self, message_type, data):
        """Broadcast to both video-specific and general progress groups"""
        try:
            # Ensure video_id is in the data payload if not already present
            if 'video_id' not in data:
                data['video_id'] = self.video_id

            print(f"📢 Broadcasting {message_type} for {self.video_id}: {data}")

            # Get channel layer (lazy load)
            channel_layer = self._get_channel_layer()
            
            # Only try to broadcast if we have a real channel layer
            if hasattr(channel_layer, 'group_send'):
                # Broadcast to Video-Specific Group
                try:
                    self.async_to_sync(channel_layer.group_send)(
                        self.room_group_name,
                        {
                            'type': message_type,
                            **data
                        }
                    )
                    print(f"✅ Sent {message_type} to specific video group: {self.room_group_name}")
                except Exception as e:
                    print(f"❌ Error sending to video-specific group {self.room_group_name}: {e}")

                # Broadcast to General Progress Group
                try:
                    self.async_to_sync(channel_layer.group_send)(
                        self.general_group_name,
                        {
                            'type': message_type,
                            **data
                        }
                    )
                    print(f"✅ Sent {message_type} to general progress group: {self.general_group_name}")
                except Exception as e:
                    print(f"❌ Error sending to general progress group {self.general_group_name}: {e}")

            print(f"✅ Progress broadcast: {message_type} for {self.video_id}")

        except Exception as e:
            print(f"❌ WebSocket broadcast error: {e}")
            import traceback
            traceback.print_exc()

    def set_progress(self, progress, message=""):
        """Set progress percentage and message with WebSocket broadcast"""
        data = self._store_progress(progress, message)

        # Broadcast progress update with proper structure
        self._broadcast_to_groups('progress_update', {
            'progress': data['progress'],
            'message': data['message'],
        })

        print(f"Progress updated for {self.video_id}: {progress}% - {message}")

    def complete_processing(self, message="Processing completed!", video_info=None):
        """Notify that processing is complete - ENHANCED VERSION"""
        # Set final progress
        self.set_progress(100, message)

        # Prepare data for completion message including video info for the modal
        completion_data = {
            'message': message,
            'status': 'completed',
            'video_info': video_info or {}  # Make sure this is included
        }

        print(f"🎯 SENDING COMPLETION DATA WITH VIDEO_INFO: {completion_data}")

        # Send completion message separately
        self._broadcast_to_groups('processing_complete', completion_data)

        print(f"✅ Processing complete: {message}")

    def fail_processing(self, error_message="Processing failed!", error_details=None):
        """Notify that processing failed - ENHANCED VERSION"""
        # Set progress to 0 on failure
        self.set_progress(0, error_message)

        # Prepare data for failure message including error details
        failure_data = {
            'message': error_message,
            'status': 'failed',
            'error_details': error_details or {}
        }

        # Send failure message separately
        self._broadcast_to_groups('processing_failed', failure_data)

        print(f"❌ Processing failed: {error_message}")

    def get_progress(self):
        """Get current progress"""
        data = self._get_progress()
        if data:
            # Check if data is older than 10 minutes (600 seconds)
            if time.time() - data['timestamp'] > 600:
                return None
            return data
        return None

    def clear_progress(self):
        """Clear progress data"""
        if REDIS_AVAILABLE:
            try:
                redis_client.delete(f'video_progress_{self.video_id}')
            except:
                pass
        progress_store.pop(self.video_id, None)