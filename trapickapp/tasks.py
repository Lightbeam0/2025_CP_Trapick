# trapickapp/tasks.py
import os
import tempfile
import subprocess
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import VideoFile, AnalysisSession, TrafficAnalysis, Location
from .progress import ProgressTracker # Assuming this can work with Celery's state updates
from ml.detector_factory import DetectorFactory
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True) 
def process_video_task(self, video_id, location_id=None, session_id=None):
    """
    Celery task to process a single video file.
    """
    logger.info(f"Starting Celery task for video {video_id}")
    progress_tracker = ProgressTracker(video_id)

    try:
        video_obj = VideoFile.objects.get(id=video_id)
        video_obj.processing_status = 'processing'
        video_obj.save()

        progress_tracker.set_progress(5, f"Loading detector...")

        # --- 1. Determine Location and Load Detector ---
        location = None
        if location_id:
            location = Location.objects.get(id=location_id)
        elif session_id and video_obj.analysis_session:
            location = video_obj.analysis_session.location
        elif video_obj.analysis_session:
            location = video_obj.analysis_session.location # Fallback if session exists

        if not location:
            raise ValueError(f"Location not found for video {video_id} (location_id: {location_id}, session_id: {session_id})")

        detector = DetectorFactory.get_detector(location.processing_profile)
        logger.info(f"Detector loaded for video {video_id}: {type(detector).__name__}")

        progress_tracker.set_progress(10, f"Starting analysis with {type(detector).__name__}...")

        # --- 2. Process Video using the Detector ---
        # The detector's analyze_video method should accept progress_tracker
        report = detector.analyze_video(
            video_obj.file_path.path,
            progress_tracker=progress_tracker,
            save_output=True # Ensure the detector saves the output video
        )

        progress_tracker.set_progress(95, "Saving analysis results...")

        # --- 3. Save Analysis Results ---
        analysis = TrafficAnalysis.objects.create(
            video_file=video_obj, # Always link to the specific video file
            # analysis_session_id=session_id, # Link to session if applicable (handled via video_file link if session exists)
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
                'detector_class': type(detector).__name__
            }
        )

        # --- 4. Update Processed Video Path ---
        # Handle the path returned by the detector robustly
        if 'output_video_path' in report and report['output_video_path']:
            absolute_output_path = report['output_video_path']
            logger.info(f"Detector returned absolute path: {absolute_output_path}")

            # Normalize paths for comparison
            media_root_normalized = os.path.normpath(settings.MEDIA_ROOT)
            absolute_output_path_normalized = os.path.normpath(absolute_output_path)

            # Check if the path is inside MEDIA_ROOT
            if absolute_output_path_normalized.startswith(media_root_normalized + os.sep):
                # Calculate the relative path correctly
                relative_path = os.path.relpath(absolute_output_path_normalized, media_root_normalized)
                # Ensure forward slashes for Django compatibility
                relative_path = relative_path.replace(os.sep, '/')
                logger.info(f"Calculated relative path: {relative_path}")
            else:
                logger.warning(f"Output path {absolute_output_path} is not within MEDIA_ROOT {settings.MEDIA_ROOT}")
                # Heuristic: If it starts with 'media/' or 'media\', assume it's meant to be relative to MEDIA_ROOT
                if absolute_output_path.startswith('media/') or absolute_output_path.startswith('media\\'):
                     # Strip the leading 'media/' or 'media\' part and normalize separators
                    relative_path = os.path.normpath(absolute_output_path[6:]) # Remove 'media/' (or 'media\')
                     # Ensure it's using forward slashes for Django
                    relative_path = relative_path.replace(os.sep, '/')
                    logger.info(f"Adjusted relative path from detector output: {relative_path}")
                else:
                     # Fallback: Use the path as-is (might cause issues, but avoids crash)
                     # Or raise an error if the path structure is unexpected
                    logger.error(f"Unexpected output path format: {absolute_output_path}. Cannot determine relative path.")
                    # Option 1: Raise Error
                    # raise ValueError(f"Detector output path '{absolute_output_path}' is outside MEDIA_ROOT and doesn't start with 'media/'. Cannot save.")
                    # Option 2: Use as-is (NOT RECOMMENDED, might not work with Django storage)
                    relative_path = absolute_output_path
                    logger.warning(f"Falling back to using path as-is: {relative_path}")

            # --- CORRECT WAY TO SAVE THE PATH ---
            # Assign the relative path string directly to the field
            video_obj.processed_video_path = relative_path # e.g., 'processed_videos/filename.mp4'
            # Save the VideoFile model instance to persist the change
            video_obj.save()
            logger.info(f"Saved processed video path to database: {relative_path}")
        else:
            logger.warning(f"No output_video_path in report for video {video_id}")

        # --- 5. Update Video Status ---
        video_obj.processing_status = 'completed'
        video_obj.processed = True
        video_obj.processed_at = timezone.now()
        video_obj.save()

        progress_tracker.set_progress(100, f"{type(detector).__name__} completed successfully!")
        progress_tracker.complete_processing("Video analysis completed!")

        logger.info(f"Celery task completed for video {video_id}")
        return f"Video {video_id} processed successfully"

    except Exception as exc:
        # Handle errors
        logger.error(f"Celery task failed for video {video_id}: {exc}")
        try:
            video_obj = VideoFile.objects.get(id=video_id)
            video_obj.processing_status = 'failed'
            video_obj.save()
        except VideoFile.DoesNotExist:
            logger.error(f"VideoFile {video_id} not found to update status after error.")

        # Update Celery task state
        self.update_state(
            state='FAILURE',
            meta={'exc_type': type(exc).__name__, 'exc_message': str(exc)}
        )
        raise exc # Celery will handle this

@shared_task(bind=True)
def process_session_task(self, session_id):
    """FAST: Process session videos in parallel"""
    from .models import AnalysisSession, VideoFile
    from .progress import ProgressTracker
    
    session = AnalysisSession.objects.get(id=session_id)
    session.status = 'processing'
    session.save()

    progress_tracker = ProgressTracker(session_id)
    progress_tracker.set_progress(5, "Starting parallel video processing...")

    # Get all videos that need processing
    video_files = session.video_files.filter(processing_status__in=['uploaded', 'pending'])
    
    if not video_files.exists():
        progress_tracker.set_progress(100, "No videos to process")
        session.status = 'completed'
        session.save()
        return "No videos to process"

    print(f"🚀 Starting parallel processing for {video_files.count()} videos in session {session_id}")

    # Start ALL videos in parallel
    task_ids = []
    for video in video_files:
        # Use your existing process_video_task but run them in parallel
        task = process_video_task.delay(video.id, session_id=session_id)
        task_ids.append(task.id)
        # Immediately update video status
        video.processing_status = 'processing'
        video.save()
        print(f"✅ Started video {video.id} with task {task.id}")

    # Store task IDs (we'll use a simple approach for now)
    session.metadata = session.metadata or {}  # Use existing metadata field
    session.metadata['celery_task_ids'] = task_ids
    session.save()

    progress_tracker.set_progress(10, f"Started {len(task_ids)} videos in parallel...")

    # Start monitoring
    monitor_session_completion.delay(session_id, task_ids)
    
    return f"Started {len(task_ids)} videos in parallel for session {session_id}"

@shared_task
def monitor_session_completion(session_id, task_ids):
    """Simple monitor to check when all videos are done"""
    from celery.result import AsyncResult
    from .models import AnalysisSession
    from .progress import ProgressTracker
    
    try:
        session = AnalysisSession.objects.get(id=session_id)
        progress_tracker = ProgressTracker(session_id)
        
        # Check completion status
        completed = 0
        failed = 0
        
        for task_id in task_ids:
            task = AsyncResult(task_id)
            if task.ready():
                if task.successful():
                    completed += 1
                else:
                    failed += 1

        total_completed = completed + failed
        progress = (total_completed / len(task_ids)) * 100
        
        status_message = f"Processed {completed}/{len(task_ids)} videos"
        if failed > 0:
            status_message += f" ({failed} failed)"
            
        progress_tracker.set_progress(progress, status_message)
        
        if total_completed == len(task_ids):
            # All tasks are done (success or failure)
            if completed > 0:  # Only create analysis if we have some successful videos
                create_simple_session_analysis(session_id)
                session.status = 'completed'
                progress_tracker.complete_processing(f"Session completed! {completed} videos processed successfully")
            else:
                session.status = 'failed'
                progress_tracker.set_progress(100, "All videos failed to process")
                
            session.save()
        else:
            # Check again in 10 seconds
            monitor_session_completion.apply_async((session_id, task_ids), countdown=10)
            
    except Exception as e:
        print(f"Error in monitor_session_completion: {e}")
        # Try again in 30 seconds if there's an error
        monitor_session_completion.apply_async((session_id, task_ids), countdown=30)

@shared_task
def create_simple_session_analysis(session_id):
    """Simple aggregation - no complex logic"""
    from .models import AnalysisSession, TrafficAnalysis
    
    session = AnalysisSession.objects.get(id=session_id)
    
    # Get all analyses from session videos
    analyses = TrafficAnalysis.objects.filter(video_file__analysis_session=session)
    
    if not analyses.exists():
        print(f"No analyses found for session {session_id}")
        return
    
    # Simple sums - much faster than your current complex aggregation
    total_vehicles = sum(a.total_vehicles for a in analyses)
    total_processing_time = sum(a.processing_time_seconds for a in analyses)
    
    # Create the session-level analysis
    TrafficAnalysis.objects.create(
        analysis_session=session,
        location=session.location,
        total_vehicles=total_vehicles,
        processing_time_seconds=total_processing_time,
        car_count=sum(a.car_count for a in analyses),
        truck_count=sum(a.truck_count for a in analyses),
        motorcycle_count=sum(a.motorcycle_count for a in analyses),
        bus_count=sum(a.bus_count for a in analyses),
        bicycle_count=sum(a.bicycle_count for a in analyses),
        other_count=sum(a.other_count for a in analyses),
        congestion_level=calculate_simple_congestion(total_vehicles, len(analyses)),
        analysis_data={
            'summary': {
                'total_vehicles': total_vehicles,
                'videos_processed': len(analyses),
                'average_vehicles_per_video': total_vehicles / len(analyses) if analyses else 0
            }
        }
    )
    print(f"✅ Created simple session analysis for {session_id}")

def calculate_simple_congestion(total_vehicles, video_count):
    """Simple congestion calculation"""
    avg_per_video = total_vehicles / video_count if video_count else 0
    if avg_per_video > 100: return 'high'
    if avg_per_video > 50: return 'medium'
    return 'low'