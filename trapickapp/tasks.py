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
    logger.info(f"Starting processing for video {video_id}")

    # CRITICAL: Clear any old stuck progress (this fixes "stuck at 5%" forever)
    ProgressTracker.clear_progress(video_id)

    try:
        video_obj = VideoFile.objects.get(id=video_id)
        location = Location.objects.get(id=location_id)

        video_obj.processing_status = 'processing'
        video_obj.save(update_fields=['processing_status'])

        # Initialize fresh tracker
        progress_tracker = ProgressTracker(video_id)
        progress_tracker.set_progress(5, "Initializing...")

        # Get detector
        detector = DetectorFactory.get_detector(location.processing_profile)
        progress_tracker.set_progress(10, "Loading detector...")

        # Get video info
        cap = cv2.VideoCapture(video_obj.file_path.path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.release()

        video_obj.total_frames = total_frames
        video_obj.fps = fps
        video_obj.save(update_fields=['total_frames', 'fps'])

        # FIXED PROGRESS CALLBACK
        def progress_callback(frame_number, total_frames, message=""):
            
            # Case 1: total_frames is actually a message string
            if isinstance(total_frames, str) and ("Analyzing" in total_frames or "frame" in total_frames.lower()):
                actual_progress = frame_number  # First arg is the progress percentage
                actual_message = total_frames    # Second arg is the message
                
                # Ensure progress is in valid range
                try:
                    actual_progress = int(actual_progress)
                    actual_progress = max(10, min(88, actual_progress))  # Clamp between 10-88%
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ Invalid progress value: {frame_number}")
                    return
                
                video_obj.update_progress(actual_progress, actual_message)
                progress_tracker.set_progress(actual_progress, actual_message)
                return
            
            # Case 2: Normal call with frame numbers
            try:
                frame_number = int(frame_number)
                total_frames = int(total_frames)
            except (ValueError, TypeError):
                logger.warning(f"⚠️ Invalid frame numbers: {frame_number}/{total_frames}")
                return
            
            if total_frames <= 0:
                return
            
            # Calculate progress: 10% → 88% based on frame progress
            progress = min(88, 10 + int((frame_number / total_frames) * 78))
            msg = message or f"Processing frame {frame_number}/{total_frames}"
            
            video_obj.update_progress(progress, msg)
            progress_tracker.set_progress(progress, msg)

        progress_tracker.set_progress(15, "Starting analysis...")

        # MAIN ANALYSIS
        report = detector.analyze_video(
            video_obj.file_path.path,
            progress_callback=progress_callback,
            save_output=True
        )

        progress_tracker.set_progress(90, "Saving results...")

        # Create analysis
        analysis = TrafficAnalysis.objects.create(
            video_file=video_obj,
            location=location,
            total_vehicles=report['summary']['total_vehicles_counted'],
            processing_time_seconds=report['metadata']['processing_time'],
            car_count=report['summary']['vehicle_breakdown'].get('car', 0),
            truck_count=report['summary']['vehicle_breakdown'].get('truck', 0),
            motorcycle_count=report['summary']['vehicle_breakdown'].get('motorcycle', 0),
            bus_count=report['summary']['vehicle_breakdown'].get('bus', 0),
            bicycle_count=report['summary']['vehicle_breakdown'].get('bicycle', 0),
            peak_traffic=report['summary'].get('peak_traffic', 0),
            average_traffic=report['summary'].get('average_traffic_density', 0),
            congestion_level=report['metrics']['congestion_level'],
            traffic_pattern=report['metrics']['traffic_pattern'],
            analysis_data=report
        )

        # Grouping
        group_date = video_obj.video_date or timezone.now().date()
        group, _ = LocationDateGroup.objects.get_or_create(location=location, date=group_date)
        video_obj.location_date_group = group

        # Final video updates
        if report.get('output_video_path'):
            try:
                video_obj.processed_video_path = os.path.relpath(
                    report['output_video_path'],
                    settings.MEDIA_ROOT
                )
            except Exception as e:
                logger.warning(f"⚠️ Could not set processed video path: {e}")

        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()
        video_obj.save()

        # FINAL: Send 100% + modal info
        video_info = {
            'filename': video_obj.filename,
            'location_name': location.display_name,
            'group_date': group.date.isoformat(),
            'group_id': str(group.id),
            'video_id': str(video_obj.id),
            'total_vehicles': analysis.total_vehicles
        }

        progress_tracker.set_progress(100, "Complete!")
        progress_tracker.complete_processing(
            message="Processing completed successfully!",
            video_info=video_info
        )

        logger.info(f"✅ Video {video_id} processed successfully")
        logger.info(f"📋 Video info for modal: {video_info}")
        
        return {'status': 'success', 'video_info': video_info}

    except Exception as exc:
        logger.error(f"❌ Processing failed for video {video_id}: {exc}", exc_info=True)
        traceback.print_exc()

        try:
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'failed'
            video_obj.save(update_fields=['processing_status'])
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