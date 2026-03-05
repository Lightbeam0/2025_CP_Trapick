# trapickapp/utils/time_slot_validator.py
"""
Utility for time slot conflict detection and video duration extraction.
Used during video upload to:
  1. Auto-detect video duration → compute end_time from start_time
  2. Check for overlapping time slots in the same location+date group
"""

import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Duration detection
# ─────────────────────────────────────────────────────────────────────────────

def get_video_duration_seconds(file_obj):
    """
    Extract duration (in seconds) from an uploaded video file object.

    Tries cv2 first (fast, no disk write needed if the file is seekable),
    then falls back to a temp-file approach with moviepy if cv2 fails.

    Args:
        file_obj: Django InMemoryUploadedFile or TemporaryUploadedFile

    Returns:
        Duration in seconds, or None if detection failed.
    """
    # ── Attempt 1: OpenCV (preferred — no extra deps) ─────────────────────
    try:
        import cv2
        import tempfile

        suffix = os.path.splitext(getattr(file_obj, 'name', '.mp4'))[1] or '.mp4'
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp_path = tmp.name
                file_obj.seek(0)
                # Only read up to 50 MB to detect duration — avoids blocking on huge files
                chunk = file_obj.read(50 * 1024 * 1024)
                tmp.write(chunk)
                file_obj.seek(0)

            cap = cv2.VideoCapture(tmp_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                cap.release()
                if fps and fps > 0 and frame_count and frame_count > 0:
                    duration = frame_count / fps
                    logger.info(f"🎬 cv2 detected duration: {duration:.1f}s")
                    return round(duration, 2)
            else:
                cap.release()
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        logger.warning(f"cv2 duration detection failed (non-fatal): {e}")

    return None


def compute_end_time(start_time, duration_seconds: float):
    """
    Given a start time (datetime.time) and a duration in seconds,
    return the computed end time (datetime.time).

    Handles wrap-around midnight gracefully.

    Args:
        start_time: datetime.time object
        duration_seconds: video length in seconds

    Returns:
        datetime.time
    """
    dummy_date = datetime(2000, 1, 1,
                          start_time.hour,
                          start_time.minute,
                          start_time.second)
    end_dt = dummy_date + timedelta(seconds=duration_seconds)
    return end_dt.time()


# ─────────────────────────────────────────────────────────────────────────────
# Conflict / overlap detection
# ─────────────────────────────────────────────────────────────────────────────

def time_to_minutes(t) -> int:
    """Convert a datetime.time to minutes since midnight."""
    return t.hour * 60 + t.minute + round(t.second / 60)


def _ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """Return True if two [start, end) ranges overlap by more than 1 minute."""
    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)
    return (overlap_end - overlap_start) > 1


def check_time_slot_conflict(
    location_id,
    video_date,
    start_time,
    end_time,
    exclude_video_id=None,
):
    """
    Check whether a proposed [start_time, end_time] slot conflicts with any
    existing completed or processing video for the same location and date.

    Args:
        location_id:      int or str — Location PK
        video_date:       datetime.date
        start_time:       datetime.time — proposed start
        end_time:         datetime.time — proposed end
        exclude_video_id: (optional) UUID str — skip this video (for re-uploads)

    Returns:
        dict with keys:
            has_conflict   bool
            conflicts      list[dict]   — conflicting video details
            message        str          — human-readable summary
    """
    from trapickapp.models import VideoFile

    # Only check completed / processing / uploaded videos; skip failed/pending
    qs = VideoFile.objects.filter(
        location_date_group__location_id=location_id,
        video_date=video_date,
        video_start_time__isnull=False,
        video_end_time__isnull=False,
        processing_status__in=['uploaded', 'processing', 'completed'],
    ).select_related('location_date_group__location')

    if exclude_video_id:
        qs = qs.exclude(id=exclude_video_id)

    proposed_start = time_to_minutes(start_time)
    proposed_end   = time_to_minutes(end_time)

    # Handle midnight wrap-around for the proposed slot
    if proposed_end < proposed_start:
        proposed_end += 24 * 60

    conflicts = []

    for existing in qs:
        ex_start = time_to_minutes(existing.video_start_time)
        ex_end   = time_to_minutes(existing.video_end_time)

        if ex_end < ex_start:          # overnight recording
            ex_end += 24 * 60

        if _ranges_overlap(proposed_start, proposed_end, ex_start, ex_end):
            # Calculate overlap details
            overlap_start_min = max(proposed_start, ex_start)
            overlap_end_min   = min(proposed_end,   ex_end)
            overlap_minutes   = overlap_end_min - overlap_start_min

            conflicts.append({
                'video_id':   str(existing.id),
                'filename':   existing.filename,
                'title':      existing.title or existing.filename,
                'start_time': existing.video_start_time.strftime('%H:%M'),
                'end_time':   existing.video_end_time.strftime('%H:%M'),
                'status':     existing.processing_status,
                'overlap_minutes': round(overlap_minutes, 1),
                'overlap_range': (
                    f"{overlap_start_min // 60:02d}:{overlap_start_min % 60:02d}"
                    f" – "
                    f"{overlap_end_min // 60:02d}:{overlap_end_min % 60:02d}"
                ),
            })

    if conflicts:
        names = ', '.join(f'"{c["filename"]}"' for c in conflicts[:3])
        suffix = f' and {len(conflicts) - 3} more' if len(conflicts) > 3 else ''
        message = (
            f"Time slot {start_time.strftime('%H:%M')}–{end_time.strftime('%H:%M')} "
            f"overlaps with existing video(s): {names}{suffix}."
        )
    else:
        message = "No conflicts detected."

    return {
        'has_conflict': bool(conflicts),
        'conflicts':    conflicts,
        'message':      message,
    }


def find_next_available_slot(location_id, video_date, duration_seconds: float):
    """
    Scan existing videos for the given location+date and return the earliest
    available start time that has no conflicts for the given duration.

    Starts from 00:00 and walks forward in 1-minute increments.

    Args:
        location_id:      int or str
        video_date:       datetime.date
        duration_seconds: float

    Returns:
        dict with keys:
            found          bool
            start_time     datetime.time | None
            end_time       datetime.time | None
            message        str
    """
    from trapickapp.models import VideoFile
    from datetime import time as dtime

    qs = VideoFile.objects.filter(
        location_date_group__location_id=location_id,
        video_date=video_date,
        video_start_time__isnull=False,
        video_end_time__isnull=False,
        processing_status__in=['uploaded', 'processing', 'completed'],
    )

    # Build list of occupied ranges in minutes
    occupied = []
    for v in qs:
        s = time_to_minutes(v.video_start_time)
        e = time_to_minutes(v.video_end_time)
        if e < s:
            e += 24 * 60
        occupied.append((s, e))

    occupied.sort()

    duration_minutes = int(duration_seconds / 60) + (1 if duration_seconds % 60 else 0)
    total_day_minutes = 24 * 60

    # Walk through every minute of the day
    candidate = 0
    while candidate + duration_minutes <= total_day_minutes:
        slot_end = candidate + duration_minutes

        conflict = any(
            _ranges_overlap(candidate, slot_end, s, e)
            for s, e in occupied
        )

        if not conflict:
            start_h, start_m = divmod(candidate, 60)
            end_h,   end_m   = divmod(slot_end, 60)
            start_time = dtime(start_h % 24, start_m)
            end_time   = dtime(end_h   % 24, end_m)
            return {
                'found':      True,
                'start_time': start_time,
                'end_time':   end_time,
                'message':    (
                    f"Next available slot: "
                    f"{start_time.strftime('%H:%M')} – {end_time.strftime('%H:%M')}"
                ),
            }

        # Jump past the next occupied block's end to avoid re-scanning
        blocking = [e for s, e in occupied if _ranges_overlap(candidate, slot_end, s, e)]
        candidate = max(blocking) if blocking else candidate + 1

    return {
        'found':      False,
        'start_time': None,
        'end_time':   None,
        'message':    'No available slot found for the full day.',
    }