"""
Time manipulation utilities for simulation API
"""

from datetime import datetime, timedelta
from typing import List, Tuple
import pytz


def generate_time_intervals(
    start_time: datetime,
    end_time: datetime,
    interval_seconds: int
) -> List[datetime]:
    """Generate time intervals between start and end time"""
    intervals = []
    current = start_time
    
    while current <= end_time:
        intervals.append(current)
        current += timedelta(seconds=interval_seconds)
    
    return intervals


def round_to_interval(timestamp: datetime, interval_seconds: int) -> datetime:
    """Round timestamp to nearest interval"""
    seconds_since_epoch = timestamp.timestamp()
    rounded_seconds = round(seconds_since_epoch / interval_seconds) * interval_seconds
    return datetime.fromtimestamp(rounded_seconds, tz=timestamp.tzinfo)


def get_berlin_timezone() -> pytz.BaseTzInfo:
    """Get Berlin timezone"""
    return pytz.timezone('Europe/Berlin')


def convert_to_berlin_time(utc_time: datetime) -> datetime:
    """Convert UTC time to Berlin time"""
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)
    
    berlin_tz = get_berlin_timezone()
    return utc_time.astimezone(berlin_tz)


def get_time_range_chunks(
    start_time: datetime,
    end_time: datetime,
    chunk_duration_minutes: int = 60
) -> List[Tuple[datetime, datetime]]:
    """Split time range into smaller chunks for processing"""
    chunks = []
    current_start = start_time
    chunk_delta = timedelta(minutes=chunk_duration_minutes)
    
    while current_start < end_time:
        current_end = min(current_start + chunk_delta, end_time)
        chunks.append((current_start, current_end))
        current_start = current_end
    
    return chunks


def calculate_time_progress(
    current_time: datetime,
    start_time: datetime,
    end_time: datetime
) -> float:
    """Calculate progress as percentage between start and end time"""
    if current_time <= start_time:
        return 0.0
    elif current_time >= end_time:
        return 1.0
    else:
        total_duration = (end_time - start_time).total_seconds()
        elapsed_duration = (current_time - start_time).total_seconds()
        return elapsed_duration / total_duration


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"