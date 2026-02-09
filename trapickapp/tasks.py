# trapickapp/tasks.py - UPDATED for Enhanced Congestion Detection
import os
import traceback
import logging
from celery import shared_task
import cv2
from django.utils import timezone
from django.conf import settings

from .models import VideoFile, TrafficAnalysis, Location, LocationDateGroup
from .progress import ProgressTracker

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_video_task(self, video_id, location_id=None):
    logger.info(f"🎬 Starting processing for video {video_id}")

    # CRITICAL: Clear any old stuck progress
    ProgressTracker.clear_progress(video_id)

    try:
        video_obj = VideoFile.objects.get(id=video_id)
        
        # Get location with processing profile
        location = None
        
        # Priority 1: Use provided location_id if available
        if location_id:
            try:
                location = Location.objects.get(id=location_id)
                logger.info(f"📍 Using provided location: {location.display_name}")
            except Location.DoesNotExist:
                logger.warning(f"⚠️ Provided location_id {location_id} not found")
                location_id = None
        
        # Priority 2: Try to get location from video's existing group
        if not location and hasattr(video_obj, 'location_date_group') and video_obj.location_date_group:
            location = video_obj.location_date_group.location
            logger.info(f"📍 Using location from existing group: {location.display_name}")
        
        # Priority 3: Check if video has a location field directly
        if not location and hasattr(video_obj, 'location') and video_obj.location:
            location = video_obj.location
            logger.info(f"📍 Using location from video field: {location.display_name}")
        
        # Final fallback: Raise error if no location found
        if not location:
            raise ValueError(
                f"Location is required for processing video {video_id}. "
                f"Please provide location_id or ensure video has location_date_group."
            )
        
        logger.info(f"✅ Location confirmed: {location.display_name} (ID: {location.id})")

        video_obj.processing_status = 'processing'
        video_obj.save(update_fields=['processing_status'])

        # Initialize fresh tracker
        progress_tracker = ProgressTracker(video_id)
        progress_tracker.set_progress(5, f"Initializing for {location.display_name}...")

        # Get detector from location's processing profile
        logger.info(f"🔧 Loading detector for profile: {location.processing_profile.display_name}")
        
        processing_profile = location.processing_profile
        
        # Get config parameters - try multiple field names
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

        # Define progress callback function
        def progress_callback_func(current_frame, total_frames, message=""):
            """Progress callback wrapper for detector"""
            try:
                progress_percent = int((current_frame / total_frames) * 90) + 5
                progress_tracker.set_progress(
                    progress_percent, 
                    f"{message} ({current_frame}/{total_frames})"
                )
            except Exception as e:
                logger.warning(f"⚠️ Progress callback error: {e}")

        # Build kwargs for detector
        detector_kwargs = {
            'save_output': True
        }

        # Add ROI if available in config
        roi_normalized = None
        
        # Try multiple sources for ROI configuration
        if config_params and 'roi_normalized' in config_params:
            roi_normalized = config_params['roi_normalized']
            logger.info(f"📍 Using ROI from processing profile config: {roi_normalized}")
        elif hasattr(processing_profile, 'roi_config') and processing_profile.roi_config:
            roi_normalized = processing_profile.roi_config
            logger.info(f"📍 Using ROI from processing profile roi_config: {roi_normalized}")
        elif location.counting_config and 'roi_normalized' in location.counting_config:
            roi_normalized = location.counting_config['roi_normalized']
            logger.info(f"📍 Using ROI from location counting_config: {roi_normalized}")
        
        # Validate and add ROI to kwargs
        if roi_normalized:
            if isinstance(roi_normalized, list) and len(roi_normalized) >= 3:
                valid_roi = True
                for point in roi_normalized:
                    if not isinstance(point, list) or len(point) != 2:
                        logger.warning(f"⚠️ Invalid ROI point format: {point}")
                        valid_roi = False
                        break
                    x, y = point
                    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                        logger.warning(f"⚠️ ROI point out of range [0.0, 1.0]: {point}")
                        valid_roi = False
                        break
                
                if valid_roi:
                    detector_kwargs['roi_normalized'] = roi_normalized
                    logger.info(f"✅ ROI validated and added to detector kwargs")
                else:
                    logger.warning(f"⚠️ ROI validation failed, will use full frame")
            else:
                logger.warning(f"⚠️ Invalid ROI format (need list with 3+ points), using full frame")
        else:
            logger.info("ℹ️ No ROI configured, congestion will be detected in full frame")

        # MAIN ANALYSIS - with graceful fallback for different detectors
        logger.info(f"🚀 Running analysis with {type(detector).__name__}...")
        
        report = None

        try:
            # ATTEMPT 1: Try with progress_callback and all kwargs
            logger.info("📡 Attempting standard detector interface with progress_callback...")
            report = detector.analyze_video(
                video_obj.file_path.path,
                progress_callback=progress_callback_func,
                **detector_kwargs
            )
            logger.info("✅ Used standard interface successfully")
            
        except TypeError as e:
            # ATTEMPT 2: Handle detectors with old signatures
            error_msg = str(e)
            logger.warning(f"⚠️ Standard interface failed: {error_msg}")
            
            if 'progress_callback' in error_msg or 'roi_normalized' in error_msg or 'unexpected keyword argument' in error_msg:
                logger.warning(
                    f"⚠️ {type(detector).__name__} doesn't support all parameters. "
                    f"Trying fallback interfaces..."
                )
                
                try:
                    # ATTEMPT 3: Try with just save_output
                    logger.info("📡 Attempting minimal detector interface (save_output only)...")
                    report = detector.analyze_video(
                        video_obj.file_path.path,
                        save_output=True
                    )
                    logger.info("✅ Used minimal interface successfully")
                    
                except TypeError as minimal_error:
                    # ATTEMPT 4: Try with absolutely no extra parameters
                    logger.warning(f"⚠️ Minimal interface failed: {minimal_error}")
                    logger.info("📡 Attempting bare-bones detector interface (video path only)...")
                    
                    try:
                        report = detector.analyze_video(video_obj.file_path.path)
                        logger.info("✅ Used bare-bones interface successfully")
                        
                    except Exception as bare_error:
                        logger.error(f"❌ All detector interfaces failed")
                        logger.error(f"   Standard error: {e}")
                        logger.error(f"   Minimal error: {minimal_error}")
                        logger.error(f"   Bare error: {bare_error}")
                        raise RuntimeError(
                            f"Detector {type(detector).__name__} is incompatible with all known interfaces."
                        )
                        
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback failed with unexpected error: {fallback_error}")
                    raise RuntimeError(f"Failed to run detector: {fallback_error}")
            else:
                logger.error(f"❌ Unexpected TypeError during analysis: {e}")
                raise
                
        except Exception as general_error:
            logger.error(f"❌ Unexpected error during analysis: {general_error}")
            import traceback
            traceback.print_exc()
            raise

        # Verify we got a report
        if report is None:
            raise RuntimeError("Detector analysis completed but returned no report.")

        logger.info(f"✅ Analysis complete. Processing report...")
        logger.info(f"📋 Report keys: {list(report.keys())}")
        
        # ✅ ENHANCED: Handle new report format with enhanced congestion data
        if 'congestion_summary' in report:
            # CongestionTimeDetector format
            logger.info("📊 Detected CongestionTimeDetector report format")
            
            total_vehicles = report.get('vehicle_statistics', {}).get('total_vehicles_detected', 0)
            
            analysis = TrafficAnalysis.objects.create(
                video_file=video_obj,
                location=location,
                total_vehicles=total_vehicles,
                processing_time_seconds=report['metadata']['processing_time'],
                car_count=0, truck_count=0, motorcycle_count=0,
                bus_count=0, bicycle_count=0, other_count=0,
                peak_traffic=report['vehicle_statistics'].get('peak_vehicle_count', 0),
                average_traffic=report['vehicle_statistics'].get('average_vehicle_count', 0),
                congestion_level=map_congestion_level(report['congestion_summary']['overall_congestion_level']),
                traffic_pattern='stable',
                analysis_data=report,
                metrics_summary={
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
            )

        elif 'summary' in report:
            # Standard detector format
            logger.info("📊 Detected standard detector report format")
            
            vehicle_breakdown = report['summary'].get('vehicle_breakdown', {})
            
            analysis = TrafficAnalysis.objects.create(
                video_file=video_obj,
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
                congestion_level=map_congestion_level(report['metrics'].get('congestion_level', 'low')),
                traffic_pattern=map_traffic_pattern(report['metrics'].get('traffic_pattern', 'stable')),
                analysis_data=report,
                metrics_summary={
                    'model_used': report['metadata'].get('model_used', 'Universal Traffic Detector'),
                    'tracked_classes': report.get('configuration', {}).get('vehicle_classes', ['car', 'motorcycle', 'bus', 'truck']),
                    'detection_method': report['metadata'].get('detection_method', 'Standard detection'),
                    'counting_mode': report.get('configuration', {}).get('counting_mode', 'unknown'),
                    'location_name': location.display_name,
                    'location_id': location.id,
                    'processing_profile': location.processing_profile.display_name if location.processing_profile else 'Default'
                }
            )

        elif 'counting_results' in report:
            # ✅ ENHANCED: BaseDirectionalDetector format with new congestion features
            logger.info("📊 Detected directional detector report format (ENHANCED)")
            
            counting_results = report.get('counting_results', {})
            congestion_results = report.get('congestion_results', {})
            vehicle_breakdown = counting_results.get('vehicle_breakdown', {})
            metadata = report.get('metadata', {})
            
            # ✅ Handle multiple possible key names for processing time
            processing_time = (
                metadata.get('processing_time_seconds') or 
                metadata.get('processing_time') or 
                0
            )
            
            # ✅ Handle multiple possible key names for duration
            duration = (
                metadata.get('duration_seconds') or
                metadata.get('video_duration') or
                metadata.get('duration') or
                0
            )
            
            # ✅ Handle multiple possible key names for frames
            total_frames_processed = (
                metadata.get('frames_processed') or
                metadata.get('total_frames') or
                0
            )
            
            # ✅ NEW: Extract enhanced congestion metrics
            congestion_score = congestion_results.get('congestion_score', 0)
            events_by_level = congestion_results.get('events_by_level', {})
            
            # ✅ NEW: Check if enhanced congestion module was used
            congestion_module_type = metadata.get('congestion_module', 'Standard')
            is_enhanced = 'Enhanced' in congestion_module_type or 'Multi-Factor' in congestion_module_type
            
            logger.info(f"🚦 Congestion module: {congestion_module_type} (Enhanced: {is_enhanced})")
            if is_enhanced:
                logger.info(f"✨ Enhanced congestion score: {congestion_score}")
                logger.info(f"📊 Events by level: {events_by_level}")
            
            analysis = TrafficAnalysis.objects.create(
                video_file=video_obj,
                location=location,
                total_vehicles=counting_results.get('total_vehicles', 0),
                processing_time_seconds=processing_time,
                
                # Vehicle types
                car_count=vehicle_breakdown.get('car', 0),
                truck_count=vehicle_breakdown.get('truck', 0),
                motorcycle_count=vehicle_breakdown.get('motorcycle', 0),
                bus_count=vehicle_breakdown.get('bus', 0),
                bicycle_count=vehicle_breakdown.get('bicycle', 0),
                other_count=0,
                
                # Directional counting
                directional_count=counting_results.get('total_vehicles', 0),
                directional_vehicles_per_minute=counting_results.get('vehicles_per_minute', 0),
                
                # ✅ ENHANCED: Congestion data with new metrics
                congestion_events_count=congestion_results.get('total_events', 0),
                total_congestion_time=congestion_results.get('total_congestion_time', 0),
                congestion_level=map_congestion_level(congestion_results.get('final_congestion_level', 'none')),
                
                # Video properties
                duration_seconds=duration,
                fps=metadata.get('fps', 30),
                total_frames=total_frames_processed,
                
                # ✅ ENHANCED: Store full report with new congestion data
                analysis_data=report,
                metrics_summary={
                    'model_used': f"Directional Detector - {metadata.get('direction', 'Unknown')}",
                    'detector_type': metadata.get('direction', 'Unknown'),
                    'counting_direction': metadata.get('direction', 'Unknown'),
                    'tracked_classes': metadata.get('vehicle_classes', []),
                    'detection_method': 'Directional counting with enhanced congestion detection',
                    'congestion_module': congestion_module_type,  # ✅ NEW
                    'is_enhanced_congestion': is_enhanced,  # ✅ NEW
                    'congestion_score': congestion_score,  # ✅ NEW
                    'events_by_level': events_by_level,  # ✅ NEW
                    'location_name': location.display_name,
                    'location_id': location.id,
                    'processing_profile': location.processing_profile.display_name if location.processing_profile else 'Default'
                },
                frame_data=report.get('raw_data', {}).get('frame_data', []),
                congestion_events=events_by_level  # ✅ Store enhanced events
            )
            
            logger.info(f"✅ Created enhanced analysis with congestion score: {congestion_score}")

        else:
            # Unknown report format
            logger.warning("⚠️ Unknown report format, creating basic analysis")
            
            analysis = TrafficAnalysis.objects.create(
                video_file=video_obj,
                location=location,
                total_vehicles=0,
                processing_time_seconds=report.get('metadata', {}).get('processing_time', 0),
                analysis_data=report,
                metrics_summary={
                    'model_used': 'Unknown', 
                    'error': 'Unexpected report format',
                    'location_name': location.display_name,
                    'location_id': location.id
                }
            )

        logger.info(f"💾 TrafficAnalysis created: ID={analysis.id}, Location={location.display_name}, Total Vehicles={analysis.total_vehicles}")

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
            'location_id': str(location.id),
            'group_date': group.date.isoformat(),
            'group_id': str(group.id),
            'video_id': str(video_obj.id),
            'total_vehicles': analysis.total_vehicles,
            'model_used': analysis.metrics_summary.get('model_used', 'Unknown'),
            'processing_time': analysis.processing_time_seconds,
            'congestion_level': getattr(analysis, 'congestion_level', 'unknown'),
            # ✅ NEW: Add enhanced congestion info if available
            'is_enhanced_congestion': analysis.metrics_summary.get('is_enhanced_congestion', False),
            'congestion_score': analysis.metrics_summary.get('congestion_score', 0)
        }

        progress_tracker.set_progress(100, "Complete!")
        progress_tracker.complete_processing(
            message="Processing completed successfully!",
            video_info=video_info
        )

        logger.info(f"✅✅✅ Video {video_id} processed successfully at {location.display_name}")
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
    """Map congestion levels to database choices - ENHANCED"""
    mapping = {
        'Light Traffic': 'low',
        'Moderate Congestion': 'medium',
        'High Congestion': 'high',
        'Severe Congestion': 'severe',
        'Very Light': 'very_low',
        'low': 'low',
        'medium': 'medium',
        'high': 'high',
        'severe': 'severe',
        'very_low': 'very_low',
        'none': 'none',
        'light': 'low',
        'moderate': 'medium',
        'heavy': 'high'
    }
    
    normalized = level_str.strip().lower()
    for key, value in mapping.items():
        if key.lower() == normalized or normalized in key.lower():
            return value
    
    logger.warning(f"⚠️ Unknown congestion level: {level_str}, defaulting to 'low'")
    return 'low'


def map_traffic_pattern(pattern_str):
    """Map traffic patterns to database choices"""
    mapping = {
        'Increasing': 'increasing',
        'Decreasing': 'decreasing',
        'Stable': 'stable',
        'Fluctuating': 'fluctuating',
        'increasing': 'increasing',
        'decreasing': 'decreasing',
        'stable': 'stable',
        'fluctuating': 'fluctuating'
    }
    
    normalized = pattern_str.strip().lower()
    for key, value in mapping.items():
        if key.lower() == normalized:
            return value
    
    logger.warning(f"⚠️ Unknown traffic pattern: {pattern_str}, defaulting to 'stable'")
    return 'stable'


@shared_task
def bulk_group_videos():
    """Task to group all ungrouped completed videos"""
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