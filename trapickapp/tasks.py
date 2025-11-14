# trapickapp/tasks.py
import os
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import VideoFile, TrafficAnalysis, Location, LocationDateGroup
from .progress import ProgressTracker
from ml.detector_factory import DetectorFactory
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_video_task(self, video_id, location_id=None):
    logger.info(f"🎬 Starting immediate processing for video {video_id}")
    
    try:
        # Initialize progress tracker with debug logging
        progress_tracker = ProgressTracker(video_id)
        logger.info(f"🔍 Progress tracker created for video {video_id}")
        
        # Test immediate progress update
        progress_tracker.set_progress(5, "Initializing video processing...")
        logger.info("🔍 Initial progress update sent (5%)")
        
        video_obj = VideoFile.objects.get(id=video_id)
        video_obj.processing_status = 'processing'
        video_obj.save()

        if not location_id:
            raise ValueError(f"❌ Location ID required for video {video_id}")

        location = Location.objects.get(id=location_id)

        progress_tracker.set_progress(10, "Loading detector...")
        logger.info("🔍 Progress update sent (10%)")

        detector = DetectorFactory.get_detector(location.processing_profile)
        logger.info(f"🔧 Detector loaded for video {video_id}: {type(detector).__name__}")

        progress_tracker.set_progress(15, f"Starting analysis with {type(detector).__name__}...")
        logger.info("🔍 Progress update sent (15%)")

        # Simulate some processing to test progress
        import time
        time.sleep(2)  # Simulate 2 seconds of work
        progress_tracker.set_progress(25, "Processing video frames...")
        logger.info("🔍 Progress update sent (25%)")

        # Continue with actual processing
        report = detector.analyze_video(
            video_obj.file_path.path,
            progress_tracker=progress_tracker,
            save_output=True
        )

        progress_tracker.set_progress(80, "Saving analysis results...")
        logger.info("🔍 Progress update sent (80%)")

        TrafficAnalysis.objects.create(
            video_file=video_obj,
            location=location,
            total_vehicles=report['summary']['total_vehicles_counted'],
            processing_time_seconds=report['metadata']['processing_time'],
            car_count=report['summary']['vehicle_breakdown'].get('car', 0),
            truck_count=report['summary']['vehicle_breakdown'].get('truck', 0),
            motorcycle_count=report['summary']['vehicle_breakdown'].get('motorcycle', 0),
            bus_count=report['summary']['vehicle_breakdown'].get('bus', 0),
            bicycle_count=report['summary']['vehicle_breakdown'].get('bicycle', 0),
            peak_traffic=report['summary']['peak_traffic'],
            average_traffic=report['summary']['average_traffic_density'],
            congestion_level=report['metrics']['congestion_level'],
            traffic_pattern=report['metrics']['traffic_pattern'],
            analysis_data=report,
            metrics_summary={
                'processing_profile': location.processing_profile.name,
                'location_name': location.display_name,
                'detector_type': location.processing_profile.display_name,
            }
        )

        progress_tracker.set_progress(85, "Assigning to location-date group...")
        logger.info("🔍 Progress update sent (85%)")

        # Determine the date for grouping
        if video_obj.video_date:
            group_date = video_obj.video_date
        else:
            group_date = timezone.now().date() # Fallback to analysis date if no video_date

        group, created = LocationDateGroup.objects.get_or_create(
            location=location,
            date=group_date
        )

        video_obj.location_date_group = group
        logger.info(f"✅ Video {video_id} assigned to group {group.id} ({location.display_name} - {group_date})")

        if created:
            logger.info(f"🆕 Created new group: {location.display_name} - {group_date}")

        # Update processed video path if available
        if 'output_video_path' in report and report['output_video_path']:
            try:
                absolute_output_path = report['output_video_path']
                media_root_normalized = os.path.normpath(settings.MEDIA_ROOT)
                absolute_output_path_normalized = os.path.normpath(absolute_output_path)

                if absolute_output_path_normalized.startswith(media_root_normalized + os.sep):
                    relative_path = os.path.relpath(absolute_output_path_normalized, media_root_normalized)
                    relative_path = relative_path.replace(os.sep, '/')
                    video_obj.processed_video_path = relative_path
                    logger.info(f"📁 Processed video path set: {relative_path}")
                else:
                    if absolute_output_path.startswith('media/') or absolute_output_path.startswith('media\\'):
                        relative_path = os.path.normpath(absolute_output_path[6:])
                        relative_path = relative_path.replace(os.sep, '/')
                        video_obj.processed_video_path = relative_path
                    else:
                        video_obj.processed_video_path = absolute_output_path
            except Exception as path_error:
                logger.error(f"❌ Error setting processed video path: {path_error}")

        # Final video status update
        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()

        # Prepare update_fields, including start/end time if they were set during upload
        update_fields = ['processing_status', 'processed', 'processed_at', 'location_date_group']
        if video_obj.video_start_time is not None:
            update_fields.append('video_start_time')
        if video_obj.video_end_time is not None:
            update_fields.append('video_end_time')

        video_obj.save(update_fields=update_fields)

        progress_tracker.set_progress(95, "Finalizing...")
        logger.info("🔍 Progress update sent (95%)")

        if video_obj.location_date_group:
            logger.info(f"✅ CONFIRMED: Video {video_id} is in group {video_obj.location_date_group.id}")
        else:
            logger.error(f"❌ CRITICAL ERROR: Video {video_id} has no group after grouping step!")
            raise Exception(f"Video {video_id} not properly grouped after grouping step")

        progress_tracker.set_progress(100, f"{type(detector).__name__} completed successfully!")
        progress_tracker.complete_processing("Video analysis completed and grouped!")
        logger.info("🔍 Final progress update sent (100%)")

        logger.info(f"🎉 Video processing completed for {video_id}")

        return {
            'status': 'success',
            'message': f'Video {video_id} processed and grouped successfully',
            'video_id': str(video_id),
            'group_id': str(video_obj.location_date_group.id) if video_obj.location_date_group else None,
            'location': location.display_name,
            'total_vehicles': report['summary']['total_vehicles_counted']
        }

    except VideoFile.DoesNotExist:
        error_msg = f"VideoFile {video_id} not found"
        logger.error(error_msg)
        # Make sure to update progress on failure
        try:
            progress_tracker.fail_processing(f"Video not found: {error_msg}")
        except:
            pass
        self.update_state(
            state='FAILURE',
            meta={'exc_type': 'VideoFile.DoesNotExist', 'exc_message': error_msg}
        )
        raise ValueError(error_msg)

    except Location.DoesNotExist:
        error_msg = f"Location {location_id} not found"
        logger.error(error_msg)
        # Make sure to update progress on failure
        try:
            progress_tracker.fail_processing(f"Location not found: {error_msg}")
        except:
            pass
        self.update_state(
            state='FAILURE',
            meta={'exc_type': 'Location.DoesNotExist', 'exc_message': error_msg}
        )
        raise ValueError(error_msg)

    except Exception as exc:
        logger.error(f"❌ Video processing failed for {video_id}: {str(exc)}")
        import traceback
        traceback.print_exc()

        # Make sure to update progress on failure
        try:
            progress_tracker.fail_processing(f"Processing failed: {str(exc)}")
            logger.info("🔍 Failure progress update sent")
        except Exception as progress_error:
            logger.error(f"Failed to send progress failure: {progress_error}")

        try:
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'failed'
            video_obj.save(update_fields=['processing_status'])
            logger.info(f"📝 Updated video {video_id} status to 'failed'")
        except VideoFile.DoesNotExist:
            logger.error(f"VideoFile {video_id} not found to update status after error.")
        except Exception as save_error:
            logger.error(f"Failed to update video status after error: {save_error}")

        self.update_state(
            state='FAILURE',
            meta={'exc_type': type(exc).__name__, 'exc_message': str(exc)}
        )
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