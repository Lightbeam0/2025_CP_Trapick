import logging
import time
import json
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Global progress store (works in both modes)
progress_store = {}

# Processing stage definitions with weights for accurate progress calculation
PROCESSING_STAGES = {
    'initializing':     {'start': 0,  'end': 5,  'label': 'Initializing...'},
    'loading_detector': {'start': 5,  'end': 12, 'label': 'Loading detector...'},
    'reading_video':    {'start': 12, 'end': 18, 'label': 'Reading video metadata...'},
    'analyzing':        {'start': 18, 'end': 88, 'label': 'Analyzing video...'},
    'saving_results':   {'start': 88, 'end': 94, 'label': 'Saving results...'},
    'grouping':         {'start': 94, 'end': 97, 'label': 'Organizing data...'},
    'finalizing':       {'start': 97, 'end': 100, 'label': 'Finalizing...'},
}


def get_all_active_progress():
    """Get all active video progress from cache and memory"""
    all_progress = {}

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

    for video_id, data in list(progress_store.items()):
        if time.time() - data.get('timestamp', 0) <= 600:
            all_progress[video_id] = data
        else:
            del progress_store[video_id]

    logger.info(f"📊 Retrieved progress for {len(all_progress)} active videos")
    return all_progress


class ProgressTracker:
    """Handles progress tracking with smooth, accurate stage-based updates"""

    # Minimum ms between updates to avoid flooding
    MIN_UPDATE_INTERVAL = 0.25  # 250ms

    def __init__(self, video_id):
        self.video_id = str(video_id)
        self._last_update_time = 0
        self._last_broadcast_progress = -1
        self._current_stage = None
        logger.info(f"🎯 ProgressTracker initialized for video {self.video_id}")

    # ------------------------------------------------------------------
    # Stage-based helpers
    # ------------------------------------------------------------------

    def begin_stage(self, stage_name, detail=None):
        """Enter a named processing stage and immediately report its start progress."""
        stage = PROCESSING_STAGES.get(stage_name)
        if not stage:
            logger.warning(f"Unknown stage: {stage_name}")
            return
        self._current_stage = stage_name
        message = stage['label']
        if detail:
            message = f"{stage['label']} {detail}"
        self.set_progress(stage['start'], message, force=True)

    def update_frame_progress(self, current_frame, total_frames, extra_message=""):
        """
        Called from the detector's progress callback.
        Maps frame position to the 'analyzing' stage range and throttles updates.
        """
        if total_frames <= 0:
            return

        stage = PROCESSING_STAGES['analyzing']
        stage_range = stage['end'] - stage['start']

        # Smooth fractional progress within the analyzing stage
        fraction = current_frame / total_frames
        progress = stage['start'] + fraction * stage_range

        # Build a descriptive message
        pct_done = int(fraction * 100)
        fps_hint = extra_message if extra_message else ""
        message = f"Analyzing frames... {pct_done}%"
        if fps_hint:
            message += f" · {fps_hint}"

        self.set_progress(progress, message)

    # ------------------------------------------------------------------
    # Core storage / broadcast
    # ------------------------------------------------------------------

    def _store_progress(self, progress, message, status='processing',
                        video_info=None, error_details=None):
        """Persist progress to cache and in-memory store."""
        data = {
            'progress': max(0, min(100, round(progress, 1))),
            'message': message,
            'status': status,
            'timestamp': time.time(),
            'video_id': self.video_id,
            'stage': self._current_stage,
        }
        if video_info:
            data['video_info'] = video_info
        if error_details:
            data['error_details'] = error_details

        cache_key = f'video_progress_{self.video_id}'
        try:
            cache.set(cache_key, data, timeout=3600)
        except Exception as e:
            logger.error(f"❌ Error storing in cache: {e}")

        progress_store[self.video_id] = data
        return data

    def _should_broadcast(self, progress):
        """
        Throttle broadcasts: skip if the last update was too recent
        OR if the progress delta is negligible (< 0.5 pp).
        Always broadcast at 0, 100, or on status changes.
        """
        now = time.time()
        elapsed = now - self._last_update_time
        delta = abs(progress - self._last_broadcast_progress)

        if progress in (0, 100):
            return True
        if elapsed < self.MIN_UPDATE_INTERVAL:
            return False
        if delta < 0.5:
            return False
        return True

    def _broadcast_to_channels(self, event_type, data):
        """Broadcast to WebSocket channels — only in local mode."""
        if settings.IS_CLOUD_DEPLOYMENT:
            logger.debug(f"☁️ Skipping WebSocket broadcast in cloud mode: {event_type}")
            return

        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning(f"⚠️ Channel layer is None for video {self.video_id}")
                return

            message = {'type': event_type, **data}

            video_channel = f'video_progress_{self.video_id}'
            async_to_sync(channel_layer.group_send)(video_channel, message)
            async_to_sync(channel_layer.group_send)('general_progress', message)

        except Exception as e:
            logger.error(f"❌ Error broadcasting to channels: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_progress(self, progress, message="Processing...", force=False):
        """
        Update progress.  Pass force=True to bypass throttling
        (e.g. at stage boundaries).
        """
        try:
            clamped = max(0.0, min(100.0, float(progress)))

            if not force and not self._should_broadcast(clamped):
                # Still update the store so polling clients see fresh data,
                # but skip the WebSocket push.
                self._store_progress(clamped, message)
                return

            data = self._store_progress(clamped, message, status='processing')

            self._broadcast_to_channels('progress_update', {
                'progress': data['progress'],
                'message': data['message'],
                'video_id': self.video_id,
                'stage': self._current_stage,
            })

            self._last_update_time = time.time()
            self._last_broadcast_progress = clamped

            logger.info(f"📊 Progress: {self.video_id} – {clamped:.1f}% – {message}")
        except Exception as e:
            logger.error(f"❌ Error setting progress for {self.video_id}: {e}")

    def complete_processing(self, message="Processing completed!", video_info=None):
        """Signal completion."""
        try:
            self._current_stage = 'finalizing'
            data = self._store_progress(100, message, status='completed',
                                        video_info=video_info)

            completion_data = {
                'video_id': self.video_id,
                'message': message,
                'progress': 100,
                'status': 'completed',
            }
            if video_info:
                completion_data['video_info'] = video_info

            self._broadcast_to_channels('processing_complete', completion_data)
            logger.info(f"🎉 Processing completed for {self.video_id}")

            import threading
            def cleanup():
                time.sleep(10)
                cache.delete(f'video_progress_{self.video_id}')
                progress_store.pop(self.video_id, None)
                logger.info(f"🧹 Cleaned up progress for {self.video_id}")

            threading.Thread(target=cleanup, daemon=True).start()

        except Exception as e:
            logger.error(f"❌ Error completing processing for {self.video_id}: {e}")

    def fail_processing(self, message="Processing failed!", error_details=None):
        """Signal failure."""
        try:
            data = self._store_progress(0, message, status='failed',
                                        error_details=error_details)

            failure_data = {
                'video_id': self.video_id,
                'message': message,
                'progress': 0,
                'status': 'failed',
            }
            if error_details:
                failure_data['error_details'] = error_details

            self._broadcast_to_channels('processing_failed', failure_data)
            logger.error(f"❌ Processing failed for {self.video_id}: {message}")

            import threading
            def cleanup():
                time.sleep(30)
                cache.delete(f'video_progress_{self.video_id}')
                progress_store.pop(self.video_id, None)

            threading.Thread(target=cleanup, daemon=True).start()

        except Exception as e:
            logger.error(f"❌ Error setting failure for {self.video_id}: {e}")

    def get_current_progress(self):
        """Retrieve latest progress from cache or memory."""
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
            'status': 'unknown',
        }

    @classmethod
    def clear_progress(cls, video_id):
        video_id = str(video_id)
        cache.delete(f'video_progress_{video_id}')
        progress_store.pop(video_id, None)
        logger.info(f"🧹 Cleared progress for video {video_id}")

    @classmethod
    def clear_all_progress(cls):
        try:
            cache_keys = cache.keys('video_progress_*') if hasattr(cache, 'keys') else []
            for key in cache_keys:
                cache.delete(key)
        except Exception as e:
            logger.warning(f"Could not clear cache keys: {e}")
        progress_store.clear()
        logger.info("🧹 Cleared all progress data")