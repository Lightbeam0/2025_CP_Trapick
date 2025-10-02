# trapickapp/progress.py
import json
import os
import time
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Simple in-memory progress storage for development
progress_store = {}

class ProgressTracker:
    def __init__(self, video_id):
        self.video_id = str(video_id)
        self.channel_layer = get_channel_layer()
        self.room_group_name = f'video_progress_{self.video_id}'
    
    def set_progress(self, progress, message=""):
        """Set progress percentage and message with WebSocket broadcast"""
        data = {
            'progress': max(0, min(100, progress)),
            'message': message,
            'timestamp': time.time()
        }
        
        progress_store[self.video_id] = data
        
        # Broadcast progress update via WebSocket
        try:
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'progress_update',
                    'progress': data['progress'],
                    'message': data['message']
                }
            )
            print(f"✓ Progress broadcast: {data['progress']}% - {message}")
        except Exception as e:
            print(f"WebSocket error: {e}")
            # Fallback: store in progress_store for HTTP polling
            progress_store[self.video_id] = data
        
        print(f"Progress updated for {self.video_id}: {progress}% - {message}")
    
    def complete_processing(self, message="Processing completed!"):
        """Notify that processing is complete"""
        try:
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'processing_complete',
                    'video_id': self.video_id,
                    'message': message
                }
            )
            print(f"✓ Processing complete broadcast: {message}")
        except Exception as e:
            print(f"WebSocket completion error: {e}")
    
    def get_progress(self):
        """Get current progress"""
        data = progress_store.get(self.video_id)
        if data:
            # Check if data is older than 10 minutes
            if time.time() - data['timestamp'] > 600:
                return None
            return data
        return None
    
    def clear_progress(self):
        """Clear progress data"""
        progress_store.pop(self.video_id, None)