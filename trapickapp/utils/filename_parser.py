# trapickapp/utils/filename_parser.py
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CCTVFilenameParser:
    """
    Parses CCTV video filenames in format: D11_20250903122635.mp4
    Extracts: camera_id, date, time, and full datetime
    """
    
    # Regex pattern for: D11_20250903122635.mp4
    PATTERN = r'^([A-Za-z0-9]+)_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\.mp4$'
    
    @classmethod
    def parse_filename(cls, filename):
        """
        Parse CCTV filename and extract metadata
        Returns: dict with camera_id, date, time, datetime or None if invalid
        """
        try:
            match = re.match(cls.PATTERN, filename)
            if not match:
                logger.warning(f"Filename pattern not recognized: {filename}")
                return None
            
            # Extract components
            camera_id = match.group(1)  # D11
            year = int(match.group(2))  # 2025
            month = int(match.group(3)) # 09
            day = int(match.group(4))   # 03
            hour = int(match.group(5))  # 12
            minute = int(match.group(6)) # 26
            second = int(match.group(7)) # 35
            
            # Create datetime object
            video_datetime = datetime(year, month, day, hour, minute, second)
            
            return {
                'camera_id': camera_id,
                'date': video_datetime.date(),
                'time': video_datetime.time(),
                'datetime': video_datetime,
                'year': year,
                'month': month,
                'day': day,
                'hour': hour,
                'minute': minute,
                'second': second,
                'filename': filename
            }
            
        except Exception as e:
            logger.error(f"Error parsing filename {filename}: {e}")
            return None
    
    @classmethod
    def is_cctv_filename(cls, filename):
        """Check if filename matches CCTV pattern"""
        return re.match(cls.PATTERN, filename) is not None
    
    @classmethod
    def extract_camera_location(cls, camera_id):
        """
        Map camera IDs to locations
        You can expand this mapping based on your camera setup
        """
        camera_mapping = {
            'D11': 'Baliwasan Main Road',
            'D12': 'Baliwasan Side Road', 
            'D13': 'San Roque Intersection',
            # Add more cameras as needed
        }
        return camera_mapping.get(camera_id, f'Camera {camera_id}')
    
    @classmethod
    def validate_datetime(cls, parsed_data):
        """Validate that the extracted datetime is reasonable"""
        if not parsed_data:
            return False
            
        video_date = parsed_data['date']
        video_time = parsed_data['time']
        
        # Check if date is not in the future
        from django.utils import timezone
        if video_date > timezone.now().date():
            logger.warning(f"Video date is in the future: {video_date}")
            return False
            
        # Check if time is within reasonable bounds (0-23 hours)
        if not (0 <= video_time.hour <= 23):
            logger.warning(f"Invalid hour in video time: {video_time.hour}")
            return False
            
        return True

# Helper functions for easy use
def parse_video_filename(filename):
    """Convenience function to parse a single filename"""
    return CCTVFilenameParser.parse_filename(filename)

def extract_metadata_from_filename(filename):
    """
    Extract and validate metadata from filename
    Returns clean metadata dict or None if invalid
    """
    parsed = parse_video_filename(filename)
    if parsed and CCTVFilenameParser.validate_datetime(parsed):
        return parsed
    return None