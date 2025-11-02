# trapickapp/tasks.py - SIMPLIFIED FOR IMMEDIATE PROCESSING
import os
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import VideoFile, TrafficAnalysis, Location
from .progress import ProgressTracker
from ml.detector_factory import DetectorFactory
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True) 
def process_video_task(self, video_id, location_id=None):
    """
    Celery task to process a single video file immediately after upload.
    """
    logger.info(f"Starting immediate processing for video {video_id}")
    progress_tracker = ProgressTracker(video_id)

    try:
        video_obj = VideoFile.objects.get(id=video_id)
        video_obj.processing_status = 'processing'
        video_obj.save()

        progress_tracker.set_progress(5, "Loading detector...")

        # Get location
        if not location_id:
            raise ValueError(f"Location ID required for video {video_id}")

        location = Location.objects.get(id=location_id)
        detector = DetectorFactory.get_detector(location.processing_profile)
        logger.info(f"Detector loaded for video {video_id}: {type(detector).__name__}")

        progress_tracker.set_progress(10, f"Starting analysis with {type(detector).__name__}...")

        # Process video using the detector
        report = detector.analyze_video(
            video_obj.file_path.path,
            progress_tracker=progress_tracker,
            save_output=True
        )

        progress_tracker.set_progress(95, "Saving analysis results...")

        # Save analysis results
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
            analysis_data=report,
            metrics_summary={
                'processing_profile': location.processing_profile.name,
                'location_name': location.display_name,
                'detector_type': location.processing_profile.display_name,
            }
        )

        # Update processed video path
        if 'output_video_path' in report and report['output_video_path']:
            absolute_output_path = report['output_video_path']
            # Handle path conversion (same as before)
            media_root_normalized = os.path.normpath(settings.MEDIA_ROOT)
            absolute_output_path_normalized = os.path.normpath(absolute_output_path)
            
            if absolute_output_path_normalized.startswith(media_root_normalized + os.sep):
                relative_path = os.path.relpath(absolute_output_path_normalized, media_root_normalized)
                relative_path = relative_path.replace(os.sep, '/')
                video_obj.processed_video_path = relative_path
            else:
                # Fallback handling
                if absolute_output_path.startswith('media/') or absolute_output_path.startswith('media\\'):
                    relative_path = os.path.normpath(absolute_output_path[6:])
                    relative_path = relative_path.replace(os.sep, '/')
                    video_obj.processed_video_path = relative_path
                else:
                    video_obj.processed_video_path = absolute_output_path

        # Update video status
        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()
        video_obj.save()

        progress_tracker.set_progress(100, f"{type(detector).__name__} completed successfully!")
        progress_tracker.complete_processing("Video analysis completed!")

        logger.info(f"Video processing completed for {video_id}")
        return f"Video {video_id} processed successfully"

    except Exception as exc:
        logger.error(f"Video processing failed for {video_id}: {exc}")
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'failed'
            video_obj.save()
        except VideoFile.DoesNotExist:
            logger.error(f"VideoFile {video_id} not found to update status after error.")

        self.update_state(
            state='FAILURE',
            meta={'exc_type': type(exc).__name__, 'exc_message': str(exc)}
        )
        raise exc