# trapickapp/peak_hours_api.py
"""
API endpoints for peak hour traffic analysis.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import logging

from .peak_hours_service import peak_hours_service
from .models import Location

logger = logging.getLogger(__name__)


class PeakHoursAnalysisAPI(APIView):
    """
    API endpoint for getting peak hour traffic analysis.
    
    GET parameters:
    - location_id: Optional location ID (default: 'all')
    - days_back: Number of days to look back (default: 30)
    """
    
    def get(self, request):
        try:
            # Get query parameters
            location_id = request.GET.get('location_id', 'all')
            days_back = int(request.GET.get('days_back', 30))
            
            # Validate location if provided
            if location_id != 'all':
                try:
                    location = Location.objects.get(id=location_id)
                    location_name = location.display_name
                except Location.DoesNotExist:
                    return Response({
                        'error': f'Location with ID {location_id} not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                location_name = 'All Locations'
            
            logger.info(f"PeakHoursAnalysisAPI called for location: {location_id}, days: {days_back}")
            
            # Get peak hours analysis
            peak_data = peak_hours_service.get_peak_hours_analysis(
                location_id=location_id,
                days_back=days_back
            )
            
            # Get summary statistics
            summary = peak_hours_service.get_peak_hour_statistics(location_id)
            
            # Prepare response
            response_data = {
                'success': True,
                'location': {
                    'id': location_id,
                    'name': location_name
                },
                'days_back': days_back,
                'analysis_date': timezone.now().isoformat(),
                'peak_hours': peak_data,
                'summary': summary
            }
            
            return Response(response_data)
            
        except ValueError as e:
            logger.error(f"Invalid days_back parameter: {e}")
            return Response({
                'error': 'Invalid days_back parameter. Must be an integer.'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in PeakHoursAnalysisAPI: {e}", exc_info=True)
            return Response({
                'error': f'Failed to get peak hours analysis: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PeakHoursDetailAPI(APIView):
    """
    API endpoint for getting detailed peak hour analysis for a specific day.
    
    GET parameters:
    - location_id: Optional location ID (default: 'all')
    - day: Day name (Monday, Tuesday, etc.)
    """
    
    def get(self, request):
        try:
            location_id = request.GET.get('location_id', 'all')
            day = request.GET.get('day')
            
            if not day:
                return Response({
                    'error': 'Day parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate day
            valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            if day not in valid_days:
                return Response({
                    'error': f'Invalid day. Must be one of: {", ".join(valid_days)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"PeakHoursDetailAPI called for location: {location_id}, day: {day}")
            
            # Get detailed analysis
            detailed_data = peak_hours_service.get_detailed_peak_analysis(
                location_id=location_id,
                day=day
            )
            
            if not detailed_data:
                return Response({
                    'error': f'No data found for {day}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'success': True,
                'day': day,
                'data': detailed_data
            })
            
        except Exception as e:
            logger.error(f"Error in PeakHoursDetailAPI: {e}", exc_info=True)
            return Response({
                'error': f'Failed to get detailed peak hours: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PeakHoursRefreshCacheAPI(APIView):
    """
    API endpoint to refresh the peak hours cache.
    """
    
    def post(self, request):
        try:
            location_id = request.data.get('location_id', 'all')
            
            # Clear cache for this location
            cache_key = f"{location_id}_30"
            if cache_key in peak_hours_service.peak_cache:
                del peak_hours_service.peak_cache[cache_key]
                if cache_key in peak_hours_service.cache_expiry:
                    del peak_hours_service.cache_expiry[cache_key]
            
            logger.info(f"Cleared peak hours cache for {location_id}")
            
            # Recalculate
            peak_data = peak_hours_service.get_peak_hours_analysis(
                location_id=location_id,
                days_back=30
            )
            
            return Response({
                'success': True,
                'message': f'Peak hours cache refreshed for {location_id}',
                'data': peak_data
            })
            
        except Exception as e:
            logger.error(f"Error refreshing cache: {e}", exc_info=True)
            return Response({
                'error': f'Failed to refresh cache: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)