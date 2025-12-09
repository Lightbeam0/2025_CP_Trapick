# trapickapp/tasks.py
import os
import traceback
import logging
from celery import shared_task
import cv2
from django.utils import timezone
from django.conf import settings

from .models import VideoFile, TrafficAnalysis, Location, LocationDateGroup
from .progress import ProgressTracker
from ml.detector_factory import DetectorFactory

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_video_task(self, video_id, location_id=None):
    logger.info(f"🎬 Starting processing for video {video_id}")

    # CRITICAL: Clear any old stuck progress
    ProgressTracker.clear_progress(video_id)

    try:
        video_obj = VideoFile.objects.get(id=video_id)
        location = Location.objects.get(id=location_id)

        video_obj.processing_status = 'processing'
        video_obj.save(update_fields=['processing_status'])

        # Initialize fresh tracker
        progress_tracker = ProgressTracker(video_id)
        progress_tracker.set_progress(5, "Initializing detector...")

        # Get detector
        logger.info(f"🔧 Loading detector for profile: {location.processing_profile.display_name}")
        detector = DetectorFactory.get_detector(location.processing_profile)
        progress_tracker.set_progress(10, f"Loaded {type(detector).__name__}...")

        # Get video info
        cap = cv2.VideoCapture(video_obj.file_path.path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.release()

        video_obj.total_frames = total_frames
        video_obj.fps = fps
        video_obj.save(update_fields=['total_frames', 'fps'])

        logger.info(f"📹 Video info: {total_frames} frames, {fps:.2f} FPS")

        # Universal progress callback
        def progress_callback(*args):
            try:
                # Handle different detector formats
                if len(args) >= 2 and isinstance(args[0], (int, float)) and isinstance(args[1], (int, float)):
                    progress_percent = int(args[0])
                    message = args[2] if len(args) > 2 else f"Progress: {progress_percent}%"
                    progress_percent = max(10, min(88, progress_percent))
                    
                    video_obj.update_progress(progress_percent, message)
                    progress_tracker.set_progress(progress_percent, message)
                    return
                
                elif len(args) >= 2:
                    frame_number = int(args[0])
                    total_frames = int(args[1])
                    message = args[2] if len(args) > 2 else f"Processing frame {frame_number}/{total_frames}"
                    
                    if total_frames <= 0:
                        return
                    
                    progress = min(88, 10 + int((frame_number / total_frames) * 78))
                    video_obj.update_progress(progress, message)
                    progress_tracker.set_progress(progress, message)
                    return
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Invalid progress callback args: {args}, error: {e}")
                return

        progress_tracker.set_progress(15, "Starting analysis...")

        # Build kwargs for detector
        detector_kwargs = {
            'save_output': True
        }

        # Add ROI if location has it defined
        if hasattr(location, 'roi_normalized') and location.roi_normalized:
            detector_kwargs['roi_normalized'] = location.roi_normalized
            logger.info(f"📍 Using ROI from location: {location.roi_normalized}")

        # MAIN ANALYSIS - with graceful fallback for different detectors
        logger.info(f"🚀 Running analysis with {type(detector).__name__}...")

        try:
            # Try with progress_callback (new standard interface)
            report = detector.analyze_video(
                video_obj.file_path.path,
                progress_callback=progress_callback,
                **detector_kwargs
            )
        except TypeError as e:
            # Handle detectors with old signatures
            if 'progress_callback' in str(e) or 'roi_normalized' in str(e):
                logger.warning(
                    f"⚠️ {type(detector).__name__} has old signature. "
                    f"Using fallback call..."
                )
                
                # Fallback: try minimal call
                try:
                    report = detector.analyze_video(
                        video_obj.file_path.path,
                        save_output=True
                    )
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback also failed: {fallback_error}")
                    raise
            else:
                # Different error, re-raise it
                raise

        logger.info(f"✅ Analysis complete. Processing report...")
        logger.info(f"📋 Report keys: {list(report.keys())}")
        progress_tracker.set_progress(90, "Saving results...")

        # FIXED: Handle different report formats from different detectors
        try:
            # Extract vehicle breakdown based on detector type
            if 'congestion_summary' in report:
                # This is CongestionTimeDetector format
                logger.info("📊 Detected CongestionTimeDetector report format")
                
                # For congestion detector, we need to extract vehicle counts differently
                # Since it doesn't provide per-class counts in the same way, we'll use totals
                total_vehicles = report.get('vehicle_statistics', {}).get('total_vehicles_detected', 0)
                
                # Create analysis with congestion-focused data
                analysis = TrafficAnalysis.objects.create(
                    video_file=video_obj,
                    location=location,
                    total_vehicles=total_vehicles,
                    processing_time_seconds=report['metadata']['processing_time'],
                    
                    # Use default counts for congestion detector
                    car_count=0,
                    truck_count=0,
                    motorcycle_count=0,
                    bus_count=0,
                    bicycle_count=0,
                    other_count=0,
                    
                    # Traffic metrics from congestion analysis
                    peak_traffic=report.get('vehicle_statistics', {}).get('peak_vehicle_count', 0),
                    average_traffic=report.get('vehicle_statistics', {}).get('average_vehicle_count', 0),
                    congestion_level=map_congestion_level(report['congestion_summary']['overall_congestion_level']),
                    traffic_pattern='stable',  # Default for congestion detector
                    
                    # Store full report for reference
                    analysis_data=report,
                    metrics_summary={
                        'model_used': 'CongestionTimeDetector (Full-Frame)',
                        'detection_method': 'Full-frame congestion timing analysis',
                        'monitoring_coverage': '100% screen area',
                        'total_congestion_time': report['congestion_summary']['total_congestion_time_seconds'],
                        'congestion_events': report['congestion_summary']['total_congestion_events'],
                        'peak_vehicles': report['vehicle_statistics']['peak_vehicle_count']
                    }
                )

            elif 'summary' in report:
                # This is standard detector format (BaliwasanYJunctionDetector, etc.)
                logger.info("📊 Detected standard detector report format")
                
                vehicle_breakdown = report['summary'].get('vehicle_breakdown', {})
                
                analysis = TrafficAnalysis.objects.create(
                    video_file=video_obj,
                    location=location,
                    total_vehicles=report['summary']['total_vehicles_counted'],
                    processing_time_seconds=report['metadata']['processing_time'],
                    
                    # COLLISION4 MODEL VEHICLE TYPES
                    car_count=vehicle_breakdown.get('car', 0),
                    truck_count=vehicle_breakdown.get('truck', 0),
                    motorcycle_count=vehicle_breakdown.get('motorcycle', 0),
                    bus_count=vehicle_breakdown.get('jeep', 0),  # Map jeep to bus_count
                    bicycle_count=vehicle_breakdown.get('tricycle', 0),  # Map tricycle to bicycle_count
                    other_count=0,
                    
                    # Traffic metrics
                    peak_traffic=report['summary'].get('peak_traffic', 0),
                    average_traffic=report['summary'].get('average_traffic_density', 0),
                    congestion_level=map_congestion_level(report['metrics'].get('congestion_level', 'low')),
                    traffic_pattern=map_traffic_pattern(report['metrics'].get('traffic_pattern', 'stable')),
                    
                    # Store full report for reference
                    analysis_data=report,
                    metrics_summary={
                        'model_used': report['metadata'].get('model_used', 'collision4_model (YOLOv8s)'),
                        'tracked_classes': ['car', 'jeep', 'motorcycle', 'tricycle', 'truck'],
                        'excluded_classes': ['VehicleCrash', 'person'],
                        'model_architecture': 'YOLOv8s',
                        'confidence_threshold': 0.4,
                        'iou_threshold': 0.7
                    }
                )

            else:
                # Unknown report format - create basic analysis
                logger.warning("⚠️ Unknown report format, creating basic analysis")
                
                analysis = TrafficAnalysis.objects.create(
                    video_file=video_obj,
                    location=location,
                    total_vehicles=0,
                    processing_time_seconds=report.get('metadata', {}).get('processing_time', 0),
                    analysis_data=report,
                    metrics_summary={'model_used': 'Unknown', 'error': 'Unexpected report format'}
                )

        except KeyError as e:
            logger.error(f"❌ KeyError processing report: {e}")
            logger.error(f"📋 Available report keys: {list(report.keys())}")
            raise

        logger.info(f"💾 TrafficAnalysis created: ID={analysis.id}, Total Vehicles={analysis.total_vehicles}")

        # Auto-grouping by location and date
        group_date = video_obj.video_date or timezone.now().date()
        group, group_created = LocationDateGroup.objects.get_or_create(
            location=location, 
            date=group_date
        )
        video_obj.location_date_group = group
        
        logger.info(f"📁 Video grouped: {location.display_name} - {group_date} (created={group_created})")

        # Handle processed video path
        if report.get('output_video_path'):
            try:
                video_obj.processed_video_path = os.path.relpath(
                    report['output_video_path'],
                    settings.MEDIA_ROOT
                )
                logger.info(f"🎥 Processed video saved: {video_obj.processed_video_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not set processed video path: {e}")

        # Final video status update
        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()
        video_obj.save()

        # FINAL: Send 100% completion + modal info
        video_info = {
            'filename': video_obj.filename,
            'location_name': location.display_name,
            'group_date': group.date.isoformat(),
            'group_id': str(group.id),
            'video_id': str(video_obj.id),
            'total_vehicles': analysis.total_vehicles,
            'model_used': analysis.metrics_summary.get('model_used', 'Unknown'),
            'processing_time': analysis.processing_time_seconds
        }

        progress_tracker.set_progress(100, "Complete!")
        progress_tracker.complete_processing(
            message="Processing completed successfully!",
            video_info=video_info
        )

        logger.info(f"✅✅✅ Video {video_id} processed successfully")
        logger.info(f"📋 Final video info: {video_info}")
        
        return {'status': 'success', 'video_info': video_info}

    except Exception as exc:
        logger.error(f"❌ Processing failed for video {video_id}: {exc}", exc_info=True)
        traceback.print_exc()

        try:
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'failed'
            video_obj.processing_message = f"Error: {str(exc)[:200]}"
            video_obj.save(update_fields=['processing_status', 'processing_message'])
        except Exception as e:
            logger.error(f"❌ Could not update video status to failed: {e}")

        try:
            tracker = ProgressTracker(video_id)
            tracker.fail_processing(
                message="Processing failed",
                error_details={'error_message': str(exc)}
            )
        except Exception as e:
            logger.error(f"❌ Could not send failure notification: {e}")

        raise exc


def map_congestion_level(level_str):
    """
    Map collision4_model congestion levels to database choices
    collision4_model uses: 'Light Traffic', 'Moderate Congestion', 'High Congestion'
    Database uses: 'very_low', 'low', 'medium', 'high', 'severe'
    """
    mapping = {
        'Light Traffic': 'low',
        'Moderate Congestion': 'medium',
        'High Congestion': 'high',
        'Severe Congestion': 'severe',
        'Very Light': 'very_low',
        # Fallbacks
        'low': 'low',
        'medium': 'medium',
        'high': 'high',
        'severe': 'severe',
        'very_low': 'very_low'
    }
    
    normalized = level_str.strip().lower()
    for key, value in mapping.items():
        if key.lower() == normalized or normalized in key.lower():
            return value
    
    # Default fallback
    logger.warning(f"⚠️ Unknown congestion level: {level_str}, defaulting to 'low'")
    return 'low'


def map_traffic_pattern(pattern_str):
    """
    Map collision4_model traffic patterns to database choices
    collision4_model uses: 'Increasing', 'Decreasing', 'Stable'
    Database uses: 'increasing', 'decreasing', 'stable', 'fluctuating'
    """
    mapping = {
        'Increasing': 'increasing',
        'Decreasing': 'decreasing',
        'Stable': 'stable',
        'Fluctuating': 'fluctuating',
        # Direct mappings
        'increasing': 'increasing',
        'decreasing': 'decreasing',
        'stable': 'stable',
        'fluctuating': 'fluctuating'
    }
    
    normalized = pattern_str.strip().lower()
    for key, value in mapping.items():
        if key.lower() == normalized:
            return value
    
    # Default fallback
    logger.warning(f"⚠️ Unknown traffic pattern: {pattern_str}, defaulting to 'stable'")
    return 'stable'


@shared_task
def bulk_group_videos():
    """
    Task to group all ungrouped completed videos
    Useful for fixing existing data
    """
    try:
        from .services import auto_group_all_videos
        result = auto_group_all_videos()
        logger.info(f"Bulk grouping completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Bulk grouping failed: {e}")
        return {'error': str(e)}


@shared_task
def verify_video_grouping(video_id):
    """
    Verify and fix video grouping for a specific video
    """
    try:
        video = VideoFile.objects.get(id=video_id)
        
        if video.processing_status != 'completed':
            return {'status': 'skipped', 'reason': 'Video not processed'}
        
        if not hasattr(video, 'traffic_analysis'):
            return {'status': 'skipped', 'reason': 'No traffic analysis'}
        
        analysis = video.traffic_analysis
        
        if not analysis.location:
            return {'status': 'skipped', 'reason': 'No location in analysis'}
        
        # Determine correct group
        if video.video_date:
            group_date = video.video_date
        else:
            group_date = analysis.analyzed_at.date()
        
        correct_group, created = LocationDateGroup.objects.get_or_create(
            location=analysis.location,
            date=group_date
        )
        
        # Check if video is in correct group
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