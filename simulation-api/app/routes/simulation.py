"""
Simulation data endpoints
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from ..models.simulation import (
    TimeRangeResponse, VehiclePositionsResponse, SimulationChunkResponse,
    VehiclePosition, SimulationStats
)
from ..services.simulation_service import SimulationService
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def get_simulation_service() -> SimulationService:
    """Dependency to get simulation service instance"""
    return SimulationService()


@router.get("/simulation/time-range", response_model=TimeRangeResponse)
async def get_available_time_range(
    service: SimulationService = Depends(get_simulation_service)
):
    """Get the available time range for simulation data"""
    try:
        return await service.get_time_range()
    except Exception as e:
        logger.error(f"Failed to get time range: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve time range")


@router.get("/simulation/vehicles", response_model=VehiclePositionsResponse)
async def get_vehicles_at_time(
    timestamp: datetime,
    time_window_seconds: int = Query(
        default=settings.DEFAULT_TIME_WINDOW_SECONDS,
        ge=1,
        le=300,
        description="Time window in seconds around the target timestamp"
    ),
    transport_types: List[str] = Query(
        default=["suburban", "subway", "tram", "bus", "ring", "regional", "ferry"],
        description="Transport types to include"
    ),
    routes: Optional[List[str]] = Query(
        default=None,
        description="Specific route IDs to filter (optional)"
    ),
    service: SimulationService = Depends(get_simulation_service)
):
    """Get all vehicle positions within a time window"""
    try:
        return await service.get_vehicles_at_time(
            timestamp=timestamp,
            time_window_seconds=time_window_seconds,
            transport_types=transport_types,
            routes=routes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get vehicles at time {timestamp}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve vehicle positions")


@router.get("/simulation/data-chunk", response_model=SimulationChunkResponse)
async def get_simulation_chunk(
    start_time: datetime,
    duration_minutes: int = Query(
        default=settings.DEFAULT_CHUNK_DURATION_MINUTES,
        ge=1,
        le=settings.MAX_CHUNK_DURATION_MINUTES,
        description="Duration of the simulation chunk in minutes"
    ),
    transport_types: List[str] = Query(
        default=["suburban", "subway", "tram", "bus", "ring", "regional", "ferry"],
        description="Transport types to include"
    ),
    routes: Optional[List[str]] = Query(
        default=None,
        description="Specific route IDs to filter (optional)"
    ),
    frame_interval_seconds: int = Query(
        default=30,
        ge=5,
        le=120,
        description="Interval between animation frames in seconds"
    ),
    service: SimulationService = Depends(get_simulation_service)
):
    """Get a chunk of simulation data for efficient client-side playback"""
    try:
        return await service.get_simulation_chunk(
            start_time=start_time,
            duration_minutes=duration_minutes,
            transport_types=transport_types,
            routes=routes,
            frame_interval_seconds=frame_interval_seconds
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get simulation chunk starting {start_time}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve simulation chunk")


@router.get("/simulation/stats", response_model=SimulationStats)
async def get_simulation_stats(
    timestamp: Optional[datetime] = Query(
        default=None,
        description="Timestamp for stats calculation (defaults to latest available)"
    ),
    service: SimulationService = Depends(get_simulation_service)
):
    """Get real-time simulation statistics"""
    try:
        return await service.get_simulation_stats(timestamp)
    except Exception as e:
        logger.error(f"Failed to get simulation stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve simulation statistics")


@router.get("/simulation/time-series")
async def get_time_series_data(
    start_time: datetime,
    end_time: datetime,
    interval_minutes: int = Query(
        default=60,
        ge=5,
        le=1440,
        description="Aggregation interval in minutes"
    ),
    transport_types: List[str] = Query(
        default=["suburban", "subway", "tram", "bus", "ring", "regional", "ferry"],
        description="Transport types to include"
    ),
    service: SimulationService = Depends(get_simulation_service)
):
    """Get time series data for charts and analytics"""
    try:
        # Validate time range
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        
        duration_hours = (end_time - start_time).total_seconds() / 3600
        if duration_hours > 168:  # 1 week max
            raise ValueError("Time range cannot exceed 1 week")
        
        return await service.get_time_series_data(
            start_time=start_time,
            end_time=end_time,
            interval_minutes=interval_minutes,
            transport_types=transport_types
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get time series data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve time series data")