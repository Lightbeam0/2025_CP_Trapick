# trapickapp/tasks.py
import os
import traceback
import logging
from celery import shared_task
import cv2
import numpy as np
import time as _time
from django.utils import timezone
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import VideoFile, TrafficAnalysis, Location, LocationDateGroup, DirectionalAnalysis

logger = logging.getLogger(__name__)


# ✅ HELPER: Convert NumPy types to native Python for JSON serialization
def convert_numpy_types(obj):
    """Recursively convert NumPy types to native Python types for JSON compatibility"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    return obj


def broadcast_progress_update(video_id, progress, message, status='processing', video_info=None, error_details=None):
    """
    Broadcast progress/completion messages to BOTH video-specific and general WebSocket groups.
    Non-critical: exceptions are caught and logged but never re-raised.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        base_payload = {
            'video_id': str(video_id),
            'progress': progress,
            'message': message,
        }

        if status == 'processing':
            progress_payload = {
                'type': 'progress_update',
                **base_payload,
                'status': 'processing'
            }
            async_to_sync(channel_layer.group_send)(f'video_progress_{video_id}', progress_payload)
            async_to_sync(channel_layer.group_send)('general_progress', progress_payload)
            logger.debug(f"📡 Broadcast progress update: {progress}% for video {video_id}")

        elif status == 'completed':
            completion_payload = {
                'type': 'processing_complete',
                **base_payload,
                'status': 'completed',
            }
            if video_info:
                completion_payload['video_info'] = video_info
            async_to_sync(channel_layer.group_send)(f'video_progress_{video_id}', completion_payload)
            async_to_sync(channel_layer.group_send)('general_progress', completion_payload)
            logger.info(f"✅ Broadcast completion for video {video_id}")

        elif status == 'failed':
            failure_payload = {
                'type': 'processing_failed',
                **base_payload,
                'status': 'failed',
            }
            if error_details:
                failure_payload['error_details'] = error_details
            async_to_sync(channel_layer.group_send)(f'video_progress_{video_id}', failure_payload)
            async_to_sync(channel_layer.group_send)('general_progress', failure_payload)
            logger.info(f"❌ Broadcast failure for video {video_id}")

    except Exception as e:
        # FIX 1: Never let broadcast failures kill processing
        logger.warning(f"⚠️ Failed to broadcast WebSocket update for video {video_id}: {e}")


# FIX 2: Add soft time limit and explicit task routing options
@shared_task(
    bind=True,
    # Retry once on unexpected failure, with 10-second delay
    max_retries=1,
    default_retry_delay=10,
    # Prevent zombie tasks: soft limit warns, hard limit kills
    soft_time_limit=3600,   # 1 hour soft limit  – raises SoftTimeLimitExceeded
    time_limit=3900,        # 65 min hard limit  – kills worker process
    acks_late=True,         # Acknowledge AFTER completion so crashes don't lose tasks
)
def process_video_task(self, video_id, location_id=None):
    from .progress import ProgressTracker
    # FIX 3: Import SoftTimeLimitExceeded for graceful handling
    try:
        from celery.exceptions import SoftTimeLimitExceeded
    except ImportError:
        SoftTimeLimitExceeded = Exception

    logger.info(f"🎬 Starting processing for video {video_id}")
    ProgressTracker.clear_progress(video_id)

    try:
        # FIX 4: Wrap the entire DB fetch in try/except with clear error
        try:
            video_obj = VideoFile.objects.get(id=video_id)
        except VideoFile.DoesNotExist:
            logger.error(f"❌ VideoFile {video_id} does not exist – aborting task.")
            return {'status': 'error', 'reason': 'video_not_found'}

        # ── Cleanup: Delete any existing partial/failed analysis ──────────────
        existing_analysis = TrafficAnalysis.objects.filter(video_file=video_obj)
        if existing_analysis.exists():
            logger.info(f"🗑️ Deleting existing analysis for video {video_id} before reprocessing")
            # FIX 5: Disconnect signals BEFORE deleting to avoid spurious re-grouping
            from django.db.models.signals import post_save
            from .models import auto_group_video_after_analysis, update_video_file_status
            post_save.disconnect(auto_group_video_after_analysis, sender=TrafficAnalysis)
            post_save.disconnect(update_video_file_status, sender=TrafficAnalysis)
            try:
                existing_analysis.delete()
            finally:
                # Always reconnect signals
                post_save.connect(auto_group_video_after_analysis, sender=TrafficAnalysis)
                post_save.connect(update_video_file_status, sender=TrafficAnalysis)

        # Reset processing status
        if video_obj.processing_status in ['processing', 'failed']:
            logger.info(f"🔄 Resetting stuck status '{video_obj.processing_status}' for video {video_id}")

        video_obj.processing_status = 'processing'
        video_obj.processing_progress = 0
        video_obj.processing_message = 'Starting...'
        video_obj.save(update_fields=['processing_status', 'processing_progress', 'processing_message'])

        # FIX 6: Clear stale group assignment unconditionally before reprocessing
        # (The old check `if not other_completed_in_group` caused groups to stick
        #  across reprocess attempts.)
        if video_obj.location_date_group:
            logger.info(f"🔄 Clearing group assignment for video {video_id} before reprocessing")
            video_obj.location_date_group = None
            video_obj.save(update_fields=['location_date_group'])

        progress_tracker = ProgressTracker(video_id)
        progress_tracker.begin_stage('initializing')

        # ── Resolve location ──────────────────────────────────────────────────
        location = None

        if location_id:
            try:
                location = Location.objects.get(id=location_id)
                logger.info(f"📍 Using provided location: {location.display_name}")
            except Location.DoesNotExist:
                logger.warning(f"⚠️ Provided location_id {location_id} not found")
                location_id = None

        if not location and hasattr(video_obj, 'location_date_group') and video_obj.location_date_group:
            location = video_obj.location_date_group.location
            logger.info(f"📍 Using location from existing group: {location.display_name}")

        if not location and hasattr(video_obj, 'location') and video_obj.location:
            location = video_obj.location
            logger.info(f"📍 Using location from video field: {location.display_name}")

        if not location:
            raise ValueError(
                f"Location is required for processing video {video_id}. "
                f"Please provide location_id or ensure video has location_date_group."
            )

        logger.info(f"✅ Location confirmed: {location.display_name} (ID: {location.id})")

        # ── Stage 2: Loading detector ─────────────────────────────────────────
        progress_tracker.begin_stage('loading_detector', f"({location.display_name})")
        logger.info(f"🔧 Loading detector for profile: {location.processing_profile.display_name}")

        processing_profile = location.processing_profile

        config_params = None
        for field_name in ['config_parameters', 'config_params', 'configuration', 'detection_config']:
            if hasattr(processing_profile, field_name):
                config_params = getattr(processing_profile, field_name, None)
                if config_params:
                    logger.info(f"⚙️ Found config in field: {field_name}")
                    break

        if not config_params:
            config_params = {}
            logger.info("ℹ️ No config parameters found, using defaults")
        else:
            logger.info(f"⚙️ Config parameters: {config_params}")

        detector = processing_profile.get_detector_instance()
        logger.info(f"✅ Loaded detector: {type(detector).__name__}")

        # ── Stage 3: Reading video metadata ───────────────────────────────────
        progress_tracker.begin_stage('reading_video')

        # FIX 7: Guard against missing or unreadable video file
        if not video_obj.file_path or not os.path.exists(video_obj.file_path.path):
            raise FileNotFoundError(
                f"Video file not found on disk: {getattr(video_obj.file_path, 'path', 'N/A')}"
            )

        cap = cv2.VideoCapture(video_obj.file_path.path)
        if not cap.isOpened():
            raise RuntimeError(f"OpenCV could not open video file: {video_obj.file_path.path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.release()

        # FIX 8: Sanity-check video metadata before proceeding
        if total_frames <= 0:
            raise RuntimeError(
                f"Video reports {total_frames} frames – file may be corrupt or unsupported."
            )

        video_obj.total_frames = total_frames
        video_obj.fps = fps
        video_obj.save(update_fields=['total_frames', 'fps'])

        logger.info(f"📹 Video info: {total_frames} frames, {fps:.2f} FPS")

        # ── Stage 4: Analyzing ────────────────────────────────────────────────
        progress_tracker.begin_stage('analyzing')

        _frame_times = []
        _last_broadcast_pct = -1  # FIX 9: Throttle WebSocket broadcasts

        def progress_callback_func(current_frame, total_frames_cb, message=""):
            nonlocal _last_broadcast_pct
            try:
                now = _time.time()
                _frame_times.append(now)
                if len(_frame_times) > 30:
                    _frame_times.pop(0)

                extra = ""
                if len(_frame_times) >= 2:
                    span = _frame_times[-1] - _frame_times[0]
                    if span > 0:
                        rolling_fps = (len(_frame_times) - 1) / span
                        extra = f"{rolling_fps:.1f} fps"

                progress_tracker.update_frame_progress(
                    current_frame,
                    total_frames_cb or total_frames,
                    extra_message=extra
                )

                total_cb = total_frames_cb or total_frames
                if total_cb > 0:
                    progress_percent = round((current_frame / total_cb) * 100, 1)
                    # FIX 9: Only broadcast on 5% boundaries or first/last frame
                    should_broadcast = (
                        int(progress_percent) % 5 == 0
                        or current_frame == 1
                        or current_frame >= total_cb
                    )
                    if should_broadcast and int(progress_percent) != _last_broadcast_pct:
                        _last_broadcast_pct = int(progress_percent)
                        broadcast_progress_update(
                            video_id=video_id,
                            progress=progress_percent,
                            message=f"{message} {extra}".strip() or f"Analyzing frames... {int(progress_percent)}%",
                            status='processing'
                        )

            except SoftTimeLimitExceeded:
                # Let it propagate so Celery can handle it gracefully
                raise
            except Exception as e:
                logger.warning(f"⚠️ Progress callback error (non-fatal): {e}")

        detector_kwargs = {'save_output': True}

        # ── ROI configuration ─────────────────────────────────────────────────
        roi_normalized = None
        if config_params and 'roi_normalized' in config_params:
            roi_normalized = config_params['roi_normalized']
            logger.info(f"📍 Using ROI from processing profile config: {roi_normalized}")
        elif hasattr(processing_profile, 'roi_config') and processing_profile.roi_config:
            roi_normalized = processing_profile.roi_config
            logger.info(f"📍 Using ROI from processing profile roi_config: {roi_normalized}")
        elif location.counting_config and 'roi_normalized' in location.counting_config:
            roi_normalized = location.counting_config['roi_normalized']
            logger.info(f"📍 Using ROI from location counting_config: {roi_normalized}")

        if roi_normalized:
            if isinstance(roi_normalized, list) and len(roi_normalized) >= 3:
                valid_roi = all(
                    isinstance(pt, list) and len(pt) == 2 and 0.0 <= pt[0] <= 1.0 and 0.0 <= pt[1] <= 1.0
                    for pt in roi_normalized
                )
                if valid_roi:
                    detector_kwargs['roi_normalized'] = roi_normalized
                    logger.info("✅ ROI validated and added to detector kwargs")
                else:
                    logger.warning("⚠️ ROI validation failed, will use full frame")
            else:
                logger.warning("⚠️ Invalid ROI format (need list with 3+ points), using full frame")

        # ── Main analysis with interface fallback ─────────────────────────────
        logger.info(f"🚀 Running analysis with {type(detector).__name__}...")
        report = None

        try:
            report = detector.analyze_video(
                video_obj.file_path.path,
                progress_callback=progress_callback_func,
                **detector_kwargs
            )
            logger.info("✅ Used standard interface successfully")

        except SoftTimeLimitExceeded:
            # FIX 10: Gracefully handle Celery time limit
            raise RuntimeError(
                f"Processing timed out after reaching the soft time limit for video {video_id}."
            )

        except TypeError as e:
            error_msg = str(e)
            
            # ✅ NEW: Handle Speed Comparison Error Specifically
            if "'<=' not supported between instances of 'NoneType' and 'float'" in error_msg:
                logger.error(f"❌ SPEED COMPARISON ERROR DETECTED: {error_msg}")
                logger.error("🛑 This indicates the congestion module or tracker is passing None speeds without checking.")
                logger.error("💡 FIX: Ensure ml/congestion_module.py and ml/enhanced_tracker.py have the latest None-handling updates.")
                raise TypeError(
                    "Speed comparison error: The detection module encountered a None speed value during comparison. "
                    "Please ensure 'ml/congestion_module.py' and 'ml/enhanced_tracker.py' are updated with the latest "
                    "None-handling fixes."
                ) from e

            logger.warning(f"⚠️ Standard interface failed: {error_msg}")

            if any(kw in error_msg for kw in ('progress_callback', 'roi_normalized', 'unexpected keyword argument')):
                logger.warning(f"⚠️ {type(detector).__name__} doesn't support all parameters. Trying fallbacks...")

                try:
                    report = detector.analyze_video(video_obj.file_path.path, save_output=True)
                    logger.info("✅ Used minimal interface successfully")
                except TypeError as minimal_error:
                    logger.warning(f"⚠️ Minimal interface failed: {minimal_error}")
                    try:
                        report = detector.analyze_video(video_obj.file_path.path)
                        logger.info("✅ Used bare-bones interface successfully")
                    except Exception as bare_error:
                        raise RuntimeError(
                            f"Detector {type(detector).__name__} is incompatible with all known interfaces. "
                            f"Standard: {e} | Minimal: {minimal_error} | Bare: {bare_error}"
                        )
                except Exception as fallback_error:
                    raise RuntimeError(f"Failed to run detector: {fallback_error}")
            else:
                # Re-raise if it wasn't a parameter issue and wasn't the specific speed error
                raise

        except Exception as general_error:
            logger.error(f"❌ Unexpected error during analysis: {general_error}")
            traceback.print_exc()
            raise

        if report is None:
            raise RuntimeError("Detector analysis completed but returned no report.")

        logger.info(f"✅ Analysis complete. Processing report...")
        logger.debug(f"📋 Report keys: {list(report.keys())}")

        # FIX 11: Convert BEFORE any DB writes
        report = convert_numpy_types(report)

        # ── Stage 5: Saving results ───────────────────────────────────────────
        progress_tracker.begin_stage('saving_results')

        analysis_data = report
        metrics_summary = {}
        frame_data = []
        congestion_events = {}

        if 'congestion_summary' in report:
            logger.info("📊 Detected CongestionTimeDetector report format")

            total_vehicles = report.get('vehicle_statistics', {}).get('total_vehicles_detected', 0)

            metrics_summary = {
                'model_used': 'CongestionTimeDetector (Full-Frame)',
                'detection_method': 'Full-frame congestion timing analysis',
                'monitoring_coverage': '100% screen area',
                'total_congestion_time': report['congestion_summary']['total_congestion_time_seconds'],
                'congestion_events': report['congestion_summary']['total_congestion_events'],
                'peak_vehicles': report['vehicle_statistics']['peak_vehicle_count'],
                'location_name': location.display_name,
                'location_id': location.id,
                'processing_profile': location.processing_profile.display_name if location.processing_profile else 'Default'
            }

            congestion_level = map_congestion_level(report['congestion_summary']['overall_congestion_level'])

            # FIX 5 (continued): Disconnect signals around DB write to prevent
            # the auto_group signal from running mid-task (we do grouping manually below)
            from django.db.models.signals import post_save
            from .models import auto_group_video_after_analysis, update_video_file_status
            post_save.disconnect(auto_group_video_after_analysis, sender=TrafficAnalysis)
            post_save.disconnect(update_video_file_status, sender=TrafficAnalysis)
            try:
                analysis, created = TrafficAnalysis.objects.update_or_create(
                    video_file=video_obj,
                    defaults=dict(
                        location=location,
                        total_vehicles=total_vehicles,
                        processing_time_seconds=report['metadata']['processing_time'],
                        car_count=0,
                        truck_count=0,
                        motorcycle_count=0,
                        bus_count=0,
                        bicycle_count=0,
                        other_count=0,
                        peak_traffic=report['vehicle_statistics'].get('peak_vehicle_count', 0),
                        average_traffic=report['vehicle_statistics'].get('average_vehicle_count', 0),
                        congestion_level=congestion_level,
                        traffic_pattern='stable',
                        analysis_data=analysis_data,
                        metrics_summary=convert_numpy_types(metrics_summary),
                        frame_data=frame_data,
                        congestion_events=convert_numpy_types(congestion_events)
                    )
                )
            finally:
                post_save.connect(auto_group_video_after_analysis, sender=TrafficAnalysis)
                post_save.connect(update_video_file_status, sender=TrafficAnalysis)

            logger.info(f"{'✅ Created' if created else '🔄 Updated'} CongestionTime analysis for video {video_id}")

        elif 'summary' in report:
            logger.info("📊 Detected standard detector report format")

            vehicle_breakdown = report['summary'].get('vehicle_breakdown', {})

            metrics_summary = {
                'model_used': report['metadata'].get('model_used', 'Universal Traffic Detector'),
                'tracked_classes': report.get('configuration', {}).get('vehicle_classes', ['car', 'motorcycle', 'bus', 'truck']),
                'detection_method': report['metadata'].get('detection_method', 'Standard detection'),
                'counting_mode': report.get('configuration', {}).get('counting_mode', 'unknown'),
                'location_name': location.display_name,
                'location_id': location.id,
                'processing_profile': location.processing_profile.display_name if location.processing_profile else 'Default'
            }

            congestion_level = map_congestion_level(report['metrics'].get('congestion_level', 'low'))
            traffic_pattern = map_traffic_pattern(report['metrics'].get('traffic_pattern', 'stable'))

            from django.db.models.signals import post_save
            from .models import auto_group_video_after_analysis, update_video_file_status
            post_save.disconnect(auto_group_video_after_analysis, sender=TrafficAnalysis)
            post_save.disconnect(update_video_file_status, sender=TrafficAnalysis)
            try:
                analysis, created = TrafficAnalysis.objects.update_or_create(
                    video_file=video_obj,
                    defaults=dict(
                        location=location,
                        total_vehicles=report['summary']['total_vehicles_counted'],
                        processing_time_seconds=report['metadata']['processing_time'],
                        car_count=vehicle_breakdown.get('car', 0),
                        truck_count=vehicle_breakdown.get('truck', 0),
                        motorcycle_count=vehicle_breakdown.get('motorcycle', 0),
                        bus_count=vehicle_breakdown.get('jeep', vehicle_breakdown.get('bus', 0)),
                        bicycle_count=vehicle_breakdown.get('tricycle', vehicle_breakdown.get('bicycle', 0)),
                        other_count=0,
                        peak_traffic=report['summary'].get('peak_traffic', 0),
                        average_traffic=report['summary'].get('average_traffic_density', 0),
                        congestion_level=congestion_level,
                        traffic_pattern=traffic_pattern,
                        analysis_data=analysis_data,
                        metrics_summary=convert_numpy_types(metrics_summary),
                        frame_data=frame_data,
                        congestion_events=convert_numpy_types(congestion_events)
                    )
                )
            finally:
                post_save.connect(auto_group_video_after_analysis, sender=TrafficAnalysis)
                post_save.connect(update_video_file_status, sender=TrafficAnalysis)

            logger.info(f"{'✅ Created' if created else '🔄 Updated'} standard analysis for video {video_id}")

        elif 'counting_results' in report:
            logger.info("📊 Detected directional detector report format (ENHANCED)")

            counting_results = report.get('counting_results', {})
            congestion_results = report.get('congestion_results', {})
            vehicle_breakdown = counting_results.get('vehicle_breakdown', {})
            metadata = report.get('metadata', {})

            processing_time = (
                metadata.get('processing_time_seconds') or
                metadata.get('processing_time') or
                0
            )
            duration = (
                metadata.get('duration_seconds') or
                metadata.get('video_duration') or
                metadata.get('duration') or
                0
            )
            total_frames_processed = (
                metadata.get('frames_processed') or
                metadata.get('total_frames') or
                0
            )

            congestion_score = congestion_results.get('congestion_score', 0)
            events_by_level = congestion_results.get('events_by_level', {})
            congestion_module_type = metadata.get('congestion_module', 'Standard')
            is_enhanced = 'Enhanced' in congestion_module_type or 'Multi-Factor' in congestion_module_type

            metrics_summary = {
                'model_used': f"Directional Detector - {metadata.get('direction', 'Unknown')}",
                'detector_type': metadata.get('direction', 'Unknown'),
                'counting_direction': metadata.get('direction', 'Unknown'),
                'tracked_classes': metadata.get('vehicle_classes', []),
                'detection_method': 'Directional counting with enhanced congestion detection',
                'congestion_module': congestion_module_type,
                'is_enhanced_congestion': is_enhanced,
                'congestion_score': congestion_score,
                'events_by_level': events_by_level,
                'location_name': location.display_name,
                'location_id': location.id,
                'processing_profile': location.processing_profile.display_name if location.processing_profile else 'Default',
                # ✅ NEW: Include feature flags and version for frontend
                'features_enabled': metadata.get('features_enabled', {}),
                'detector_version': metadata.get('version', 'v4.0'),
            }

            frame_data = report.get('raw_data', {}).get('frame_data', [])
            congestion_events = events_by_level

            # ✅ NEW: Extract enhanced metrics if available (backward compatible)
            enhanced_metrics = report.get('enhanced_metrics', {})
            lane_statistics = enhanced_metrics.get('lane_statistics', {})
            turning_movements = enhanced_metrics.get('turning_movements', {})
            stopped_vehicles_count = enhanced_metrics.get('stopped_vehicles', {}).get('active_stopped', 0)
            speed_metrics = enhanced_metrics.get('speed_results', {})
            congestion_enhanced = enhanced_metrics.get('congestion', {})
            detector_version = metadata.get('version', enhanced_metrics.get('detector_version', 'v4.0'))

            # ✅ ADD NEW: Extract ALL enhanced metrics for ML v4.2 Report
            # Tracker stats
            tracker_stats = enhanced_metrics.get('tracker_stats', {})
            
            # Congestion timeline
            congestion_timeline = [
                {
                    'frame': f.get('frame_number'),
                    'timestamp': f.get('timestamp'),
                    'score': f.get('congestion_score'),
                    'level': f.get('congestion_level')
                }
                for f in report.get('raw_data', {}).get('frame_data', [])
                if f.get('congestion_level') != 'none'
            ]
            
            # Features used
            features_used = enhanced_metrics.get('features_used', {})
            
            # Trajectory summary
            trajectory_summary = enhanced_metrics.get('trajectory_summary', {})

            # ✅ NEW: Extract directional details if available
            directional_details = enhanced_metrics.get('directional_details', {})

            from django.db.models.signals import post_save
            from .models import auto_group_video_after_analysis, update_video_file_status
            post_save.disconnect(auto_group_video_after_analysis, sender=TrafficAnalysis)
            post_save.disconnect(update_video_file_status, sender=TrafficAnalysis)
            try:
                analysis, created = TrafficAnalysis.objects.update_or_create(
                    video_file=video_obj,
                    defaults=dict(
                        location=location,
                        total_vehicles=counting_results.get('total_vehicles', 0),
                        processing_time_seconds=processing_time,
                        car_count=vehicle_breakdown.get('car', 0),
                        truck_count=vehicle_breakdown.get('truck', 0),
                        motorcycle_count=vehicle_breakdown.get('motorcycle', 0),
                        bus_count=vehicle_breakdown.get('jeep', 0),
                        bicycle_count=vehicle_breakdown.get('tricycle', 0),
                        other_count=0,
                        directional_count=counting_results.get('total_vehicles', 0),
                        directional_vehicles_per_minute=counting_results.get('vehicles_per_minute', 0),
                        congestion_events_count=congestion_results.get('total_events', 0),
                        total_congestion_time=congestion_results.get('total_congestion_time', 0),
                        congestion_level=map_congestion_level(congestion_results.get('final_congestion_level', 'none')),
                        duration_seconds=duration,
                        fps=metadata.get('fps', 30),
                        total_frames=total_frames_processed,
                        analysis_data=analysis_data,
                        metrics_summary=convert_numpy_types(metrics_summary),
                        frame_data=convert_numpy_types(frame_data),
                        congestion_events=convert_numpy_types(congestion_events),
                        # ✅ NEW: Enhanced fields (all nullable for backward compat)
                        avg_speed_kmh=speed_metrics.get('avg'),
                        p85_speed_kmh=speed_metrics.get('p85'),
                        max_speed_kmh=speed_metrics.get('max'),
                        lane_statistics=convert_numpy_types(lane_statistics),
                        turning_movements=convert_numpy_types(turning_movements),
                        stopped_vehicles_count=stopped_vehicles_count,
                        congestion_index=congestion_enhanced.get('index'),
                        queue_length_meters=congestion_enhanced.get('queue_length'),
                        incident_risk_score=congestion_enhanced.get('incident_risk'),
                        congestion_trend=congestion_enhanced.get('trend'),
                        detector_version=detector_version,
                        # ✅ ADD NEW: ML v4.2 Report Fields
                        tracker_stats=convert_numpy_types(tracker_stats),
                        congestion_timeline=convert_numpy_types(congestion_timeline),
                        trajectory_summary=convert_numpy_types(trajectory_summary),
                        features_used=convert_numpy_types(features_used),
                    )
                )
            finally:
                post_save.connect(auto_group_video_after_analysis, sender=TrafficAnalysis)
                post_save.connect(update_video_file_status, sender=TrafficAnalysis)

            logger.info(f"{'✅ Created' if created else '🔄 Updated'} directional analysis for video {video_id}")

            # ✅ NEW: Save enhanced directional details if available
            if directional_details:
                try:
                    DirectionalAnalysis.objects.update_or_create(
                        traffic_analysis=analysis,
                        defaults={
                            'direction_name': directional_details.get('direction_name', metadata.get('direction', '')),
                            'direction_angle': directional_details.get('direction_angle', 0),
                            'line_start_x': directional_details.get('line_start_x', 0),
                            'line_start_y': directional_details.get('line_start_y', 0),
                            'line_end_x': directional_details.get('line_end_x', 0),
                            'line_end_y': directional_details.get('line_end_y', 0),
                            'directional_car_count': directional_details.get('car_count', vehicle_breakdown.get('car', 0)),
                            'directional_truck_count': directional_details.get('truck_count', vehicle_breakdown.get('truck', 0)),
                            'directional_motorcycle_count': directional_details.get('motorcycle_count', vehicle_breakdown.get('motorcycle', 0)),
                            'directional_bus_count': directional_details.get('jeep_count', vehicle_breakdown.get('jeep', 0)),
                            'directional_bicycle_count': directional_details.get('tricycle_count', vehicle_breakdown.get('tricycle', 0)),
                            # ✅ NEW: Enhanced directional fields (JSON, nullable)
                            'lane_counts': convert_numpy_types(directional_details.get('lane_counts', {})),
                            'turning_counts': convert_numpy_types(directional_details.get('turning_counts', {})),
                            'lane_speeds': convert_numpy_types(directional_details.get('lane_speeds', {})),
                        }
                    )
                    logger.debug(f"📊 Saved enhanced directional details for analysis {analysis.id}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not save directional details (non-fatal): {e}")

            # ✅ NEW: Save frame-level enhanced data if available
            frame_analytics = enhanced_metrics.get('frame_analytics', [])
            if frame_analytics and hasattr(analysis, 'frame_analyses'):
                try:
                    from .models import FrameAnalysis
                    for frame_entry in frame_analytics:
                        FrameAnalysis.objects.update_or_create(
                            traffic_analysis=analysis,
                            frame_number=frame_entry.get('frame_number'),
                            defaults={
                                'timestamp_seconds': frame_entry.get('timestamp_seconds'),
                                'car_count': frame_entry.get('car_count', 0),
                                'truck_count': frame_entry.get('truck_count', 0),
                                'motorcycle_count': frame_entry.get('motorcycle_count', 0),
                                'bus_count': frame_entry.get('bus_count', 0),
                                'bicycle_count': frame_entry.get('bicycle_count', 0),
                                'total_vehicles': frame_entry.get('total_vehicles', 0),
                                'directional_count': frame_entry.get('directional_count', 0),
                                'congestion_level': frame_entry.get('congestion_level', 'none'),
                                'stationary_vehicles': frame_entry.get('stationary_vehicles', 0),
                                'detection_data': convert_numpy_types(frame_entry.get('detection_data', {})),
                                # ✅ NEW: Frame-level enhanced fields
                                'avg_speed_frame': frame_entry.get('avg_speed'),
                                'lane_assignments': convert_numpy_types(frame_entry.get('lane_assignments', {})),
                                'stopped_vehicles_frame': frame_entry.get('stopped_vehicles', 0),
                            }
                        )
                    logger.debug(f"📊 Saved {len(frame_analytics)} frame analytics entries")
                except Exception as e:
                    logger.warning(f"⚠️ Could not save frame analytics (non-fatal): {e}")

        else:
            logger.warning("⚠️ Unknown report format, creating basic analysis")

            metrics_summary = {
                'model_used': 'Unknown',
                'error': 'Unexpected report format',
                'location_name': location.display_name,
                'location_id': location.id
            }

            from django.db.models.signals import post_save
            from .models import auto_group_video_after_analysis, update_video_file_status
            post_save.disconnect(auto_group_video_after_analysis, sender=TrafficAnalysis)
            post_save.disconnect(update_video_file_status, sender=TrafficAnalysis)
            try:
                analysis, created = TrafficAnalysis.objects.update_or_create(
                    video_file=video_obj,
                    defaults=dict(
                        location=location,
                        total_vehicles=0,
                        processing_time_seconds=report.get('metadata', {}).get('processing_time', 0),
                        analysis_data=analysis_data,
                        metrics_summary=convert_numpy_types(metrics_summary),
                        frame_data=frame_data,
                        congestion_events=convert_numpy_types(congestion_events)
                    )
                )
            finally:
                post_save.connect(auto_group_video_after_analysis, sender=TrafficAnalysis)
                post_save.connect(update_video_file_status, sender=TrafficAnalysis)

            logger.info(f"{'✅ Created' if created else '🔄 Updated'} fallback analysis for video {video_id}")

        logger.info(
            f"💾 TrafficAnalysis saved: ID={analysis.id}, "
            f"Location={location.display_name}, Total Vehicles={analysis.total_vehicles}"
        )

        # ── Stage 6: Grouping (done explicitly here, not via signal) ─────────
        progress_tracker.begin_stage('grouping')

        group_date = video_obj.video_date or timezone.now().date()
        group, group_created = LocationDateGroup.objects.get_or_create(
            location=location,
            date=group_date
        )

        # FIX 12: Manually update VideoFile status and group in one save
        video_obj.location_date_group = group
        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()

        logger.info(f"📁 Video grouped: {location.display_name} - {group_date} (group_created={group_created})")

        # Update coverage metrics for the group
        try:
            coverage_metrics = group.calculate_coverage_metrics()
            logger.info(
                f"📊 Coverage metrics updated: {coverage_metrics['total_coverage_minutes']} minutes, "
                f"{coverage_metrics['continuity_score']}% continuous"
            )
            group.calculate_hourly_distribution()
            logger.info("📈 Hourly distribution calculated")
        except Exception as e:
            logger.warning(f"⚠️ Could not update coverage metrics (non-fatal): {e}")

        # Handle processed video path
        if report.get('output_video_path'):
            try:
                video_obj.processed_video_path = os.path.relpath(
                    report['output_video_path'],
                    settings.MEDIA_ROOT
                )
                logger.info(f"🎥 Processed video saved: {video_obj.processed_video_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not set processed video path (non-fatal): {e}")

        video_obj.save()

        # ── Stage 7: Finalizing ───────────────────────────────────────────────
        progress_tracker.begin_stage('finalizing')

        video_info = {
            'filename': video_obj.filename,
            'location_name': location.display_name,
            'location_id': str(location.id),
            'group_date': group.date.isoformat(),
            'group_id': str(group.id),
            'video_id': str(video_obj.id),
            'total_vehicles': analysis.total_vehicles,
            'model_used': analysis.metrics_summary.get('model_used', 'Unknown'),
            'processing_time': analysis.processing_time_seconds,
            'congestion_level': getattr(analysis, 'congestion_level', 'unknown'),
            'is_enhanced_congestion': analysis.metrics_summary.get('is_enhanced_congestion', False),
            'congestion_score': analysis.metrics_summary.get('congestion_score', 0)
        }

        progress_tracker.complete_processing(
            message="Processing completed successfully!",
            video_info=video_info
        )

        logger.info(f"✅✅✅ Video {video_id} processed successfully at {location.display_name}")
        return {'status': 'success', 'video_info': video_info}

    except SoftTimeLimitExceeded:
        # FIX 10: Graceful timeout handling
        _mark_failed(video_id, "Processing timed out (video may be too large)")
        raise  # Let Celery know the task exceeded its limit

    except Exception as exc:
        logger.error(f"❌ Processing failed for video {video_id}: {exc}", exc_info=True)
        traceback.print_exc()
        _mark_failed(video_id, str(exc))
        raise exc


def _mark_failed(video_id, error_message):
    """
    FIX 13: Extracted helper so failure marking never raises
    and is always attempted even when the main try/except fails.
    """
    try:
        video_obj = VideoFile.objects.get(id=video_id)
        video_obj.processing_status = 'failed'
        video_obj.processing_message = f"Error: {str(error_message)[:200]}"
        video_obj.save(update_fields=['processing_status', 'processing_message'])
    except Exception as e:
        logger.error(f"❌ Could not update video status to failed: {e}")

    try:
        from .progress import ProgressTracker
        tracker = ProgressTracker(video_id)
        tracker.fail_processing(
            message="Processing failed",
            error_details={'error_message': str(error_message)}
        )
    except Exception as e:
        logger.error(f"❌ Could not send failure notification: {e}")


def map_congestion_level(level_str):
    mapping = {
        'none': 'none',
        'light': 'low',
        'moderate': 'medium',
        'heavy': 'high',
        'severe': 'severe',
        'light traffic': 'low',
        'moderate congestion': 'medium',
        'high congestion': 'high',
        'severe congestion': 'severe',
        'very light': 'very_low',
    }
    normalized = level_str.strip().lower()
    if normalized in mapping:
        return mapping[normalized]
    for key, value in mapping.items():
        if normalized in key or key in normalized:
            return value
    return 'low'


def map_traffic_pattern(pattern_str):
    mapping = {
        'increasing': 'increasing',
        'decreasing': 'decreasing',
        'stable': 'stable',
        'fluctuating': 'fluctuating',
    }
    normalized = pattern_str.strip().lower()
    if normalized in mapping:
        return mapping[normalized]
    logger.warning(f"⚠️ Unknown traffic pattern: {pattern_str}, defaulting to 'stable'")
    return 'stable'


@shared_task
def bulk_group_videos():
    """Task to group all ungrouped completed videos"""
    try:
        from .data_services import auto_group_all_videos
        result = auto_group_all_videos()
        logger.info(f"Bulk grouping completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Bulk grouping failed: {e}")
        return {'error': str(e)}


@shared_task
def verify_video_grouping(video_id):
    """Verify and fix video grouping for a specific video"""
    try:
        video = VideoFile.objects.get(id=video_id)

        if video.processing_status != 'completed':
            return {'status': 'skipped', 'reason': 'Video not processed'}

        if not hasattr(video, 'traffic_analysis'):
            return {'status': 'skipped', 'reason': 'No traffic analysis'}

        analysis = video.traffic_analysis

        if not analysis.location:
            return {'status': 'skipped', 'reason': 'No location in analysis'}

        group_date = video.video_date if video.video_date else analysis.analyzed_at.date()

        correct_group, created = LocationDateGroup.objects.get_or_create(
            location=analysis.location,
            date=group_date
        )

        if video.location_date_group != correct_group:
            old_group = video.location_date_group
            video.location_date_group = correct_group
            video.save()
            logger.info(f"✅ Fixed grouping for video {video_id}: {old_group} -> {correct_group}")
            return {
                'status': 'fixed',
                'old_group': str(old_group.id) if old_group else None,
                'new_group': str(correct_group.id),
                'location': analysis.location.display_name,
                'date': group_date.isoformat()
            }
        else:
            return {
                'status': 'already_correct',
                'group': str(correct_group.id),
                'location': analysis.location.display_name,
                'date': group_date.isoformat()
            }

    except Exception as e:
        logger.error(f"❌ Verify grouping failed for {video_id}: {e}")
        return {'status': 'error', 'error': str(e)}