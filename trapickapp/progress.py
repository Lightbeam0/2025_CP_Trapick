import logging
import time
import json
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Global progress store (works in both modes)
progress_store = {}

def get_all_active_progress():
    """Get all active video progress from cache and memory"""
    all_progress = {}
    
    # Get from Django cache
    try:
        cache_keys = cache.keys('video_progress_*') if hasattr(cache, 'keys') else []
        for key in cache_keys:
            video_id = key.replace('video_progress_', '')
            progress_data = cache.get(key)
            if progress_data and isinstance(progress_data, dict):
                if time.time() - progress_data.get('timestamp', 0) <= 600:
                    all_progress[video_id] = progress_data
    except Exception as e:
        logger.warning(f"Could not get cache keys: {e}")
    
    # Also check memory store
    for video_id, data in list(progress_store.items()):
        if time.time() - data.get('timestamp', 0) <= 600:
            all_progress[video_id] = data
        else:
            del progress_store[video_id]
    
    logger.info(f"📊 Retrieved progress for {len(all_progress)} active videos")
    return all_progress

class ProgressTracker:
    """Handles progress tracking - WebSocket broadcasting only in local mode"""
    
    def __init__(self, video_id):
        self.video_id = str(video_id)
        logger.info(f"🎯 ProgressTracker initialized for video {self.video_id}")
    
    def _store_progress(self, progress, message, status='processing', video_info=None, error_details=None):
        """Store progress data in cache and memory"""
        data = {
            'progress': max(0, min(100, progress)),
            'message': message,
            'status': status,
            'timestamp': time.time(),
            'video_id': self.video_id
        }
        
        if video_info:
            data['video_info'] = video_info
        if error_details:
            data['error_details'] = error_details
        
        # Store in Django cache
        cache_key = f'video_progress_{self.video_id}'
        try:
            cache.set(cache_key, data, timeout=3600)
        except Exception as e:
            logger.error(f"❌ Error storing in cache: {e}")
        
        # Also store in memory as fallback
        progress_store[self.video_id] = data
        return data
    
    def _broadcast_to_channels(self, event_type, data):
        """Broadcast to WebSocket channels - ONLY in local mode"""
        if settings.IS_CLOUD_DEPLOYMENT:
            # Skip WebSocket broadcasting in cloud mode
            logger.debug(f"☁️ Skipping WebSocket broadcast in cloud mode: {event_type}")
            return
        
        try:
            # LAZY IMPORT - only import when needed and in local mode
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning(f"⚠️ Channel layer is None for video {self.video_id}")
                return
            
            message = {
                'type': event_type,
                **data
            }
            
            logger.info(f"📡 Broadcasting {event_type} for video {self.video_id}")
            
            # Send to specific video channel
            video_channel = f'video_progress_{self.video_id}'
            async_to_sync(channel_layer.group_send)(video_channel, message)
            logger.info(f"✅ Sent to video channel: {video_channel}")
            
            # Send to general progress channel
            async_to_sync(channel_layer.group_send)('general_progress', message)
            logger.info(f"✅ Sent to general_progress channel")
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting to channels: {e}")
    
    def set_progress(self, progress, message="Processing..."):
        """Update and optionally broadcast progress"""
        try:
            data = self._store_progress(progress, message, status='processing')
            self._broadcast_to_channels('progress_update', {
                'progress': data['progress'],
                'message': data['message'],
                'video_id': self.video_id
            })
            logger.info(f"📊 Progress updated: {self.video_id} - {progress}% - {message}")
        except Exception as e:
            logger.error(f"❌ Error setting progress for {self.video_id}: {e}")
    
    def complete_processing(self, message="Processing completed!", video_info=None):
        """Signal completion and broadcast if in local mode"""
        try:
            data = self._store_progress(100, message, status='completed', video_info=video_info)
            
            completion_data = {
                'video_id': self.video_id,
                'message': message,
                'progress': 100,
                'status': 'completed'
            }
            if video_info:
                completion_data['video_info'] = video_info
            
            self._broadcast_to_channels('processing_complete', completion_data)
            logger.info(f"🎉 Processing completed for {self.video_id}")
            
            # Clean up after 10 seconds
            import threading
            def cleanup():
                time.sleep(10)
                cache_key = f'video_progress_{self.video_id}'
                cache.delete(cache_key)
                if self.video_id in progress_store:
                    del progress_store[self.video_id]
                logger.info(f"🧹 Cleaned up progress data for {self.video_id}")
            
            cleanup_thread = threading.Thread(target=cleanup, daemon=True)
            cleanup_thread.start()
            
        except Exception as e:
            logger.error(f"❌ Error completing processing for {self.video_id}: {e}")
    
    def fail_processing(self, message="Processing failed!", error_details=None):
        """Signal failure and broadcast if in local mode"""
        try:
            data = self._store_progress(0, message, status='failed', error_details=error_details)
            
            failure_data = {
                'video_id': self.video_id,
                'message': message,
                'progress': 0,
                'status': 'failed'
            }
            if error_details:
                failure_data['error_details'] = error_details
            
            self._broadcast_to_channels('processing_failed', failure_data)
            logger.error(f"❌ Processing failed for {self.video_id}: {message}")
            
            # Clean up after 30 seconds
            import threading
            def cleanup():
                time.sleep(30)
                cache_key = f'video_progress_{self.video_id}'
                cache.delete(cache_key)
                if self.video_id in progress_store:
                    del progress_store[self.video_id]
                logger.info(f"🧹 Cleaned up failed progress data for {self.video_id}")
            
            cleanup_thread = threading.Thread(target=cleanup, daemon=True)
            cleanup_thread.start()
            
        except Exception as e:
            logger.error(f"❌ Error setting failure status for {self.video_id}: {e}")
    
    def get_current_progress(self):
        """Get current progress from cache or memory"""
        cache_key = f'video_progress_{self.video_id}'
        progress_data = cache.get(cache_key)
        
        if progress_data and isinstance(progress_data, dict):
            if time.time() - progress_data.get('timestamp', 0) <= 600:
                return progress_data
        
        data = progress_store.get(self.video_id)
        if data and time.time() - data.get('timestamp', 0) <= 600:
            return data
        
        return {
            'progress': 0,
            'message': 'No progress data available',
            'status': 'unknown'
        }
    
    @classmethod
    def clear_progress(cls, video_id):
        """Clear progress data for a specific video"""
        video_id = str(video_id)
        cache_key = f'video_progress_{video_id}'
        cache.delete(cache_key)
        if video_id in progress_store:
            del progress_store[video_id]
        logger.info(f"🧹 Cleared progress data for video {video_id}")
    
    @classmethod
    def clear_all_progress(cls):
        """Clear all progress data"""
        try:
            cache_keys = cache.keys('video_progress_*') if hasattr(cache, 'keys') else []
            for key in cache_keys:
                cache.delete(key)
        except Exception as e:
            logger.warning(f"Could not clear cache keys: {e}")
        progress_store.clear()
        logger.info("🧹 Cleared all progress data")

# Remove the VideoProgressAPI class from here - it should be in api_views.py