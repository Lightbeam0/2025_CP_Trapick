# trapickapp/tasks.py
import os
from celery import shared_task
import cv2
from django.conf import settings
from django.utils import timezone
from .models import VideoFile, TrafficAnalysis, Location, LocationDateGroup
from .progress import ProgressTracker
from ml.detector_factory import DetectorFactory
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_video_task(self, video_id, location_id=None):
    logger.info(f"🎬 Starting processing for video {video_id}")

    try:
        # Get video and location objects
        video_obj = VideoFile.objects.get(id=video_id)
        location = Location.objects.get(id=location_id)

        # Update status and initial progress
        video_obj.processing_status = 'processing'
        video_obj.save(update_fields=['processing_status'])

        # --- CRITICAL: Initialize ProgressTracker ---
        progress_tracker = ProgressTracker(video_id)
        progress_tracker.set_progress(5, "Initializing video processing...")

        # Get detector
        detector = DetectorFactory.get_detector(location.processing_profile)

        video_obj.update_progress(10, "Loading detector and video...") # Update DB too, if needed
        progress_tracker.set_progress(10, "Loading detector and video...") # Also broadcast

        # Get video info
        cap = cv2.VideoCapture(video_obj.file_path.path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        logger.info(f"📊 Video info: {total_frames} frames, {fps:.1f} FPS")

        # Store video info
        video_obj.total_frames = total_frames
        video_obj.fps = fps
        video_obj.save(update_fields=['total_frames', 'fps'])

        # Process video with progress callback
        def progress_callback(frame_number, total_frames, message=""):
            # Calculate progress based on frame number
            # Ensure progress doesn't exceed 80% until saving results
            calculated_progress = min(80, 20 + int((frame_number / total_frames) * 60))
            # Update database for polling (optional, but good for fallback)
            video_obj.update_progress(calculated_progress, message)
            # --- CRITICAL: Use ProgressTracker to broadcast ---
            progress_tracker.set_progress(calculated_progress, message)
            logger.info(f"📈 Progress: {calculated_progress}% - {message}")

        # Call detector with progress callback
        report = detector.analyze_video(
            video_obj.file_path.path,
            progress_callback=progress_callback,
            save_output=True
        )

        # Update progress before saving analysis
        progress_tracker.set_progress(85, "Saving analysis results...")
        video_obj.update_progress(85, "Saving analysis results...")

        # Create analysis record
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
            peak_traffic=report['summary']['peak_traffic'],
            average_traffic=report['summary']['average_traffic_density'],
            congestion_level=report['metrics']['congestion_level'],
            traffic_pattern=report['metrics']['traffic_pattern'],
            analysis_data=report
        )

        progress_tracker.set_progress(90, "Assigning to location-date group...")
        video_obj.update_progress(90, "Assigning to location-date group...")

        # Grouping logic
        if video_obj.video_date:
            group_date = video_obj.video_date
        else:
            group_date = timezone.now().date()

        group, created = LocationDateGroup.objects.get_or_create(
            location=location,
            date=group_date
        )

        video_obj.location_date_group = group
        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()

        # Update processed video path if available
        if 'output_video_path' in report and report['output_video_path']:
            try:
                video_obj.processed_video_path = report['output_video_path']
            except Exception as path_error:
                logger.error(f"❌ Error setting processed video path: {path_error}")

        video_obj.save()

        # --- ENHANCEMENT: Gather info for the modal ---
        video_info_for_modal = {
            'filename': video_obj.filename,
            'location_name': location.display_name,
            'group_date': group.date.isoformat(), # Use isoformat for consistency
            'group_id': str(group.id), # String ID for URL construction
            'video_id': str(video_obj.id), # String ID for URL construction
            'total_vehicles': analysis.total_vehicles
        }

        print(f"🎯 TASK: About to send completion with video_info: {video_info_for_modal}")

        # --- CRITICAL: Use ProgressTracker to signal completion WITH INFO ---
        progress_tracker.complete_processing("Processing completed successfully!", video_info=video_info_for_modal)

        print(f"🎯 TASK: Completion message sent for video {video_id}")

        logger.info(f"🎉 Video processing completed for {video_id}")

        return {
            'status': 'success',
            'message': f'Video {video_id} processed successfully',
            'video_id': str(video_id),
            'total_vehicles': report['summary']['total_vehicles_counted'],
            'video_info': video_info_for_modal # Include info for potential frontend use
        }

    except Exception as exc:
        logger.error(f"❌ Video processing failed for {video_id}: {str(exc)}")
        import traceback
        traceback.print_exc()

        # --- ENHANCEMENT: Gather error details for the modal ---
        error_details_for_modal = {
            'error_message': str(exc),
            'traceback': traceback.format_exc() # Be careful with exposing full tracebacks in production
        }

        # Update progress on failure using ProgressTracker WITH DETAILS
        try:
            progress_tracker = ProgressTracker(video_id)
            progress_tracker.fail_processing(f"Processing failed: {str(exc)}", error_details=error_details_for_modal)
        except Exception as tracker_error:
            logger.error(f"❌ Error updating progress via tracker on failure: {tracker_error}")

        # Update video status to failed
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'failed'
            video_obj.save()
        except VideoFile.DoesNotExist:
            logger.error(f"❌ Video object {video_id} not found to update status on failure.")

        # Re-raise the exception to mark the task as failed
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