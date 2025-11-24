# trapickapp/progress.py
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import cache
import time
import json

logger = logging.getLogger(__name__)

# In-memory progress store (as fallback to cache)
progress_store = {}

def get_all_active_progress():
    """Get all active video progress from cache and memory"""
    all_progress = {}
    
    # Get from Django cache (works with both LocMemCache and RedisCache)
    try:
        # Try to get all keys with pattern (works with Redis backend)
        cache_keys = cache.keys('video_progress_*') if hasattr(cache, 'keys') else []
        for key in cache_keys:
            video_id = key.replace('video_progress_', '')
            progress_data = cache.get(key)
            if progress_data and isinstance(progress_data, dict):
                # Check if data is recent (within 10 minutes)
                if time.time() - progress_data.get('timestamp', 0) <= 600:
                    all_progress[video_id] = progress_data
    except Exception as e:
        logger.warning(f"Could not get cache keys: {e}")
    
    # Also check memory store for recent data
    for video_id, data in list(progress_store.items()):
        if time.time() - data.get('timestamp', 0) <= 600:
            all_progress[video_id] = data
        else:
            # Clean up old data
            del progress_store[video_id]
    
    logger.info(f"📊 Retrieved progress for {len(all_progress)} active videos")
    return all_progress


class ProgressTracker:
    """Handles progress tracking and WebSocket broadcasting for video processing"""
    
    def __init__(self, video_id):
        self.video_id = str(video_id)
        self.channel_layer = None
        self.async_to_sync = None
        logger.info(f"🎯 ProgressTracker initialized for video {self.video_id}")
    
    def _get_channel_layer(self):
        """Lazy load channel layer to avoid import issues"""
        if self.channel_layer is None:
            try:
                self.channel_layer = get_channel_layer()
                self.async_to_sync = async_to_sync
                if self.channel_layer:
                    logger.info(f"✅ Channel layer loaded for video {self.video_id}")
                else:
                    logger.warning(f"⚠️ Channel layer is None for video {self.video_id}")
            except Exception as e:
                logger.error(f"❌ Error getting channel layer: {e}")
                self.channel_layer = None
                self.async_to_sync = None
        return self.channel_layer
    
    def _store_progress(self, progress, message, status='processing', video_info=None, error_details=None):
        """Store progress data in cache and memory"""
        data = {
            'progress': max(0, min(100, progress)),
            'message': message,
            'status': status,
            'timestamp': time.time(),
            'video_id': self.video_id
        }
        
        # Add optional data
        if video_info:
            data['video_info'] = video_info
            logger.info(f"📋 Storing video_info: {video_info}")
        
        if error_details:
            data['error_details'] = error_details
            logger.info(f"📋 Storing error_details: {error_details}")
        
        # Store in Django cache
        cache_key = f'video_progress_{self.video_id}'
        try:
            cache.set(cache_key, data, timeout=3600)  # 1 hour
            logger.info(f"💾 Stored progress in cache: {cache_key}")
        except Exception as e:
            logger.error(f"❌ Error storing in cache: {e}")
        
        # Also store in memory as fallback
        progress_store[self.video_id] = data
        
        return data
    
    def set_progress(self, progress, message="Processing..."):
        """Update and broadcast progress"""
        try:
            # Store progress
            data = self._store_progress(progress, message, status='processing')
            
            # Broadcast to WebSocket clients
            self._broadcast_to_channels('progress_update', {
                'progress': data['progress'],
                'message': data['message'],
                'video_id': self.video_id
            })
            
            logger.info(f"📊 Progress updated: {self.video_id} - {progress}% - {message}")
            
        except Exception as e:
            logger.error(f"❌ Error setting progress for {self.video_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def complete_processing(self, message="Processing completed!", video_info=None):
        """
        Signal that processing is complete and send video info to frontend
        
        Args:
            message: Success message to display
            video_info: Dictionary containing video details for the modal
                {
                    'filename': str,
                    'location_name': str,
                    'group_date': str,
                    'group_id': str,
                    'video_id': str,
                    'total_vehicles': int
                }
        """
        try:
            # Store completion state
            data = self._store_progress(100, message, status='completed', video_info=video_info)
            
            # Prepare completion message for WebSocket
            completion_data = {
                'video_id': self.video_id,
                'message': message,
                'progress': 100,
                'status': 'completed'
            }
            
            # CRITICAL: Include video_info at root level for React
            if video_info:
                completion_data['video_info'] = video_info
                logger.info(f"📋 Including video_info in completion broadcast: {video_info}")
            else:
                logger.warning(f"⚠️ No video_info provided for completion of {self.video_id}")
            
            # Broadcast completion to WebSocket clients
            self._broadcast_to_channels('processing_complete', completion_data)
            
            logger.info(f"🎉 Processing completed for {self.video_id}")
            logger.info(f"🎯 PROGRESS TRACKER: Sent completion with data: {completion_data}")
            
            # Clean up after 10 seconds
            import threading
            def cleanup():
                time.sleep(10)
                try:
                    cache_key = f'video_progress_{self.video_id}'
                    cache.delete(cache_key)
                    if self.video_id in progress_store:
                        del progress_store[self.video_id]
                    logger.info(f"🧹 Cleaned up progress data for {self.video_id}")
                except Exception as e:
                    logger.error(f"❌ Error cleaning up progress for {self.video_id}: {e}")
            
            cleanup_thread = threading.Thread(target=cleanup, daemon=True)
            cleanup_thread.start()
            
        except Exception as e:
            logger.error(f"❌ Error completing processing for {self.video_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def fail_processing(self, message="Processing failed!", error_details=None):
        """
        Signal that processing has failed
        
        Args:
            message: Error message to display
            error_details: Dictionary containing error information
        """
        try:
            # Store failure state
            data = self._store_progress(0, message, status='failed', error_details=error_details)
            
            # Prepare failure message for WebSocket
            failure_data = {
                'video_id': self.video_id,
                'message': message,
                'progress': 0,
                'status': 'failed'
            }
            
            # Include error details if provided
            if error_details:
                failure_data['error_details'] = error_details
                logger.info(f"📋 Including error_details in failure broadcast: {error_details}")
            
            # Broadcast failure to WebSocket clients
            self._broadcast_to_channels('processing_failed', failure_data)
            
            logger.error(f"❌ Processing failed for {self.video_id}: {message}")
            
            # Clean up after 30 seconds
            import threading
            def cleanup():
                time.sleep(30)
                try:
                    cache_key = f'video_progress_{self.video_id}'
                    cache.delete(cache_key)
                    if self.video_id in progress_store:
                        del progress_store[self.video_id]
                    logger.info(f"🧹 Cleaned up failed progress data for {self.video_id}")
                except Exception as e:
                    logger.error(f"❌ Error cleaning up failed progress for {self.video_id}: {e}")
            
            cleanup_thread = threading.Thread(target=cleanup, daemon=True)
            cleanup_thread.start()
            
        except Exception as e:
            logger.error(f"❌ Error setting failure status for {self.video_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def _broadcast_to_channels(self, event_type, data):
        """
        Broadcast message to both specific video channel and general progress channel
        
        Args:
            event_type: Type of event (progress_update, processing_complete, processing_failed)
            data: Data to send (must include video_id)
        """
        try:
            channel_layer = self._get_channel_layer()
            
            if not channel_layer or not self.async_to_sync:
                logger.warning(f"⚠️ Channel layer not available, skipping broadcast for {event_type}")
                return
            
            # Prepare message for channel layer
            message = {
                'type': event_type,  # This determines which consumer method is called
                **data  # Spread all data into the message
            }
            
            logger.info(f"📡 Broadcasting {event_type} for video {self.video_id}")
            logger.info(f"📡 Message content: {json.dumps(message, default=str)}")
            
            # Send to specific video progress channel
            video_channel = f'video_progress_{self.video_id}'
            try:
                self.async_to_sync(channel_layer.group_send)(
                    video_channel,
                    message
                )
                logger.info(f"✅ Sent to video channel: {video_channel}")
            except Exception as e:
                logger.error(f"❌ Error sending to video channel {video_channel}: {e}")
            
            # Send to general progress channel (for sidebar)
            try:
                self.async_to_sync(channel_layer.group_send)(
                    'general_progress',
                    message
                )
                logger.info(f"✅ Sent to general_progress channel")
            except Exception as e:
                logger.error(f"❌ Error sending to general_progress channel: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting to channels: {e}")
            import traceback
            traceback.print_exc()
    
    def get_current_progress(self):
        """Get current progress from cache or memory"""
        # Try cache first
        cache_key = f'video_progress_{self.video_id}'
        progress_data = cache.get(cache_key)
        
        if progress_data and isinstance(progress_data, dict):
            # Check if data is recent
            if time.time() - progress_data.get('timestamp', 0) <= 600:
                return progress_data
        
        # Fallback to memory store
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
        
        # Clear from cache
        cache_key = f'video_progress_{video_id}'
        cache.delete(cache_key)
        
        # Clear from memory
        if video_id in progress_store:
            del progress_store[video_id]
        
        logger.info(f"🧹 Cleared progress data for video {video_id}")
    
    @classmethod
    def clear_all_progress(cls):
        """Clear all progress data"""
        # Clear cache (if keys() is supported)
        try:
            cache_keys = cache.keys('video_progress_*') if hasattr(cache, 'keys') else []
            for key in cache_keys:
                cache.delete(key)
        except Exception as e:
            logger.warning(f"Could not clear cache keys: {e}")
        
        # Clear memory
        progress_store.clear()
        
        logger.info("🧹 Cleared all progress data")


def debug_video_info_flow(video_id, video_info, stage):
    """Debug function to track video_info through the pipeline"""
    logger.info(f"🔍 {stage} - Video ID: {video_id}")
    logger.info(f"🔍 {stage} - Video Info Type: {type(video_info)}")
    
    if video_info:
        logger.info(f"🔍 {stage} - Video Info Keys: {list(video_info.keys())}")
        logger.info(f"🔍 {stage} - Video Info: {video_info}")
        
        # Ensure video_info has the expected structure
        expected_keys = ['filename', 'location_name', 'group_date', 'total_vehicles', 'group_id']
        for key in expected_keys:
            if key in video_info:
                logger.info(f"   ✅ {key}: {video_info[key]}")
            else:
                logger.warning(f"   ❌ {key}: MISSING")
    else:
        logger.warning(f"🔍 {stage} - Video Info: None")