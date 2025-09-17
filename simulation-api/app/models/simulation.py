"""
Pydantic models for simulation API responses
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class VehiclePosition(BaseModel):
    """Vehicle position data"""
    vehicle_id: str
    route_id: Optional[str] = None
    line_name: Optional[str] = None
    transport_type: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: datetime
    delay_minutes: int = 0
    status: str = "active"
    direction: Optional[str] = None


class TimeRangeResponse(BaseModel):
    """Available time range for simulation data"""
    start_time: datetime
    end_time: datetime
    total_duration_hours: float
    total_records: int
    transport_types_available: List[str]


class VehiclePositionsResponse(BaseModel):
    """Response for vehicle positions at a specific time"""
    timestamp: datetime
    time_window_seconds: int
    vehicles: List[VehiclePosition]
    total_vehicles: int
    transport_type_counts: Dict[str, int]


class SimulationChunkResponse(BaseModel):
    """Chunked simulation data for efficient client-side playback"""
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    vehicles: List[VehiclePosition]
    total_vehicles: int
    frame_count: int
    recommended_frame_rate: int = 30


class RouteInfo(BaseModel):
    """Route information"""
    route_id: str
    line_name: str
    transport_type: str
    description: Optional[str] = None
    color: str
    geometry_available: bool = False
    vehicle_count_24h: int = 0


class StopInfo(BaseModel):
    """Stop information"""
    stop_id: str
    stop_name: str
    latitude: float
    longitude: float
    is_tracked: bool
    transport_types: List[str]


class RouteGeometry(BaseModel):
    """Route geometry data"""
    route_id: str
    line_name: str
    transport_type: str
    geometry: Dict[str, Any]  # GeoJSON FeatureCollection
    stops: List[Dict[str, Any]]  # Stop information along route


class SimulationStats(BaseModel):
    """Real-time simulation statistics"""
    active_vehicles: int
    average_delay_minutes: float
    transport_type_distribution: Dict[str, int]
    geographic_bounds: Dict[str, float]
    last_updated: datetime