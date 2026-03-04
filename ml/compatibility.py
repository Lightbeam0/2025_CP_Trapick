# ml/compatibility.py
"""
Backward compatibility layer for existing backend services.

Applied fixes (review session):
  - FIX-CP1: TaskCompatibility.__exit__ now restores enhanced features if they
              were active before __enter__ was called. The original left features
              permanently disabled after the context manager exited, meaning
              all subsequent Celery tasks on the same detector would silently
              run in basic mode.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportCompatibility:
    """Ensures reports maintain backward compatibility"""

    @staticmethod
    def to_v1_compatible(report_v2):
        """Convert v2 report to v1 format for legacy services."""
        v1_report = {
            'metadata': report_v2.get('metadata', {}).copy(),
            'counting_results': report_v2.get('counting_results', {}).copy(),
            'congestion_results': report_v2.get('congestion_results', {}).copy(),
            'raw_data': report_v2.get('raw_data', {}).copy(),
        }

        v1_report['metadata'].pop('report_version', None)
        v1_report['metadata'].pop('features', None)

        cong = v1_report['congestion_results']
        if 'flow_rate_vehicles_per_min' in cong:
            for field in ['flow_rate_vehicles_per_min', 'density_vehicles_per_km',
                         'queue_length_meters', 'congestion_index']:
                cong.pop(field, None)

        if 'frame_data' in v1_report['raw_data']:
            v1_frames = []
            for frame in v1_report['raw_data']['frame_data']:
                v1_frame = {
                    'frame_number': frame.get('frame_number'),
                    'timestamp': frame.get('timestamp'),
                    'total_vehicles': frame.get('vehicle_count_full_frame', frame.get('total_vehicles', 0)),
                    'vehicle_breakdown': frame.get('vehicle_breakdown', {}),
                }
                v1_frames.append(v1_frame)
            v1_report['raw_data']['frame_data'] = v1_frames

        return v1_report

    @staticmethod
    def to_v2_with_fallback(report, api_version='v1'):
        """Return appropriate format based on API version."""
        is_v2 = report.get('metadata', {}).get('report_version') == '2.0'

        if api_version == 'v1' and is_v2:
            return ReportCompatibility.to_v1_compatible(report)
        elif api_version == 'v2' and not is_v2:
            report['metadata']['report_version'] = '2.0'
            report['enhanced_metrics'] = {}
            return report
        else:
            return report


class TaskCompatibility:
    """
    Ensures Celery tasks remain compatible.

    FIX-CP1: __exit__ now properly restores enhanced features if they were
    active before __enter__ was called. The original implementation never
    restored state, permanently disabling enhanced features on the shared
    detector instance for all subsequent tasks in the same worker process.
    """

    def __init__(self, detector):
        self.detector = detector
        self._was_enhanced = False

    def __enter__(self):
        """Temporarily disable enhanced features for a task."""
        # FIX-CP1: Record current state so __exit__ can restore it
        if hasattr(self.detector, 'congestion_module'):
            cm = self.detector.congestion_module
            self._was_enhanced = getattr(cm, '_feature_level', 'basic') == 'enhanced'
        else:
            self._was_enhanced = False

        if hasattr(self.detector, 'enable_enhanced_metrics'):
            self.detector.enable_enhanced_metrics(False)

        if (hasattr(self.detector, 'congestion_module') and
                hasattr(self.detector.congestion_module, 'enable_enhanced_features')):
            self.detector.congestion_module.enable_enhanced_features(False)

        return self.detector

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        FIX-CP1: Restore enhanced features if they were active before __enter__.
        Previously this was a no-op comment, leaving the detector permanently
        in basic mode for all subsequent Celery tasks on this worker.
        """
        if self._was_enhanced:
            if hasattr(self.detector, 'enable_enhanced_metrics'):
                self.detector.enable_enhanced_metrics(True)

            if (hasattr(self.detector, 'congestion_module') and
                    hasattr(self.detector.congestion_module, 'enable_enhanced_features')):
                self.detector.congestion_module.enable_enhanced_features(True)

        # Don't suppress exceptions
        return False


class ModelCompatibility:
    """Ensures Django model compatibility"""

    @staticmethod
    def prepare_for_model_save(report, model_fields):
        """Prepare report data for Django model save."""
        compatible_data = {}
        flattened = {}

        for key in ['total_vehicles', 'vehicles_per_minute', 'traffic_level']:
            if key in report.get('counting_results', {}):
                flattened[key] = report['counting_results'][key]

        for key in ['total_events', 'total_congestion_time', 'final_congestion_level']:
            if key in report.get('congestion_results', {}):
                flattened[key] = report['congestion_results'][key]

        for key in ['video_duration', 'processing_time', 'fps']:
            if key in report.get('metadata', {}):
                flattened[key] = report['metadata'][key]

        for field in model_fields:
            if field in flattened:
                compatible_data[field] = flattened[field]
            elif field == 'raw_results':
                compatible_data[field] = report

        return compatible_data