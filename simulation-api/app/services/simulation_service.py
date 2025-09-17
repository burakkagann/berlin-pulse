"""
Simulation service - Business logic for simulation data processing
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from ..core.database import database
from ..models.simulation import (
    TimeRangeResponse, VehiclePositionsResponse, SimulationChunkResponse,
    VehiclePosition, SimulationStats
)

logger = logging.getLogger(__name__)


class SimulationService:
    """Service for handling simulation data operations"""
    
    async def get_time_range(self) -> TimeRangeResponse:
        """Get available time range for simulation data"""
        query = """
        SELECT 
            MIN(timestamp) as start_time,
            MAX(timestamp) as end_time,
            COUNT(*) as total_records,
            COUNT(DISTINCT transport_type) as transport_type_count,
            array_agg(DISTINCT transport_type ORDER BY transport_type) as transport_types
        FROM vehicle_positions
        """
        
        result = await database.execute_single(query)
        
        if not result or not result["start_time"]:
            raise ValueError("No simulation data available")
        
        duration_hours = (result["end_time"] - result["start_time"]).total_seconds() / 3600
        
        return TimeRangeResponse(
            start_time=result["start_time"],
            end_time=result["end_time"],
            total_duration_hours=round(duration_hours, 2),
            total_records=result["total_records"],
            transport_types_available=result["transport_types"]
        )
    
    async def get_vehicles_at_time(
        self,
        timestamp: datetime,
        time_window_seconds: int = 30,
        transport_types: List[str] = None,
        routes: Optional[List[str]] = None
    ) -> VehiclePositionsResponse:
        """Get vehicle positions within a time window"""
        
        # Default transport types
        if not transport_types:
            transport_types = ["suburban", "subway", "tram", "bus", "ring", "regional", "ferry"]
        
        # Build dynamic query conditions
        conditions = ["transport_type = ANY($3)"]
        params = [
            timestamp - timedelta(seconds=time_window_seconds),
            timestamp + timedelta(seconds=time_window_seconds),
            transport_types
        ]
        
        if routes:
            conditions.append("route_id = ANY($4)")
            params.append(routes)
        
        query = f"""
        WITH latest_positions AS (
            SELECT DISTINCT ON (vehicle_id) 
                vehicle_id, route_id, line_name, transport_type,
                latitude, longitude, timestamp, delay_minutes, 
                status, direction
            FROM vehicle_positions 
            WHERE timestamp BETWEEN $1 AND $2
            AND {' AND '.join(conditions)}
            ORDER BY vehicle_id, timestamp DESC
        )
        SELECT 
            vehicle_id, route_id, line_name, transport_type,
            latitude, longitude, timestamp, delay_minutes,
            status, direction
        FROM latest_positions
        ORDER BY transport_type, line_name, vehicle_id
        """
        
        vehicles_data = await database.execute_query(query, *params)
        
        vehicles = [
            VehiclePosition(
                vehicle_id=row["vehicle_id"],
                route_id=row["route_id"],
                line_name=row["line_name"],
                transport_type=row["transport_type"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                timestamp=row["timestamp"],
                delay_minutes=row["delay_minutes"] or 0,
                status=row["status"] or "active",
                direction=row["direction"]
            )
            for row in vehicles_data
        ]
        
        # Calculate transport type counts
        transport_counts = {}
        for vehicle in vehicles:
            transport_counts[vehicle.transport_type] = transport_counts.get(vehicle.transport_type, 0) + 1
        
        return VehiclePositionsResponse(
            timestamp=timestamp,
            time_window_seconds=time_window_seconds,
            vehicles=vehicles,
            total_vehicles=len(vehicles),
            transport_type_counts=transport_counts
        )
    
    async def get_simulation_chunk(
        self,
        start_time: datetime,
        duration_minutes: int = 10,
        transport_types: List[str] = None,
        routes: Optional[List[str]] = None,
        frame_interval_seconds: int = 30
    ) -> SimulationChunkResponse:
        """Get chunked simulation data for efficient playback"""
        
        if not transport_types:
            transport_types = ["suburban", "subway", "tram", "bus", "ring", "regional", "ferry"]
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Build dynamic query conditions
        conditions = ["transport_type = ANY($3)"]
        params = [start_time, end_time, transport_types]
        
        if routes:
            conditions.append("route_id = ANY($4)")
            params.append(routes)
        
        # Query to get vehicles with time-based sampling
        query = f"""
        WITH time_frames AS (
            SELECT generate_series($1, $2, interval '{frame_interval_seconds} seconds') as frame_time
        ),
        vehicle_samples AS (
            SELECT 
                tf.frame_time,
                DISTINCT ON (vp.vehicle_id, tf.frame_time) 
                vp.vehicle_id, vp.route_id, vp.line_name, vp.transport_type,
                vp.latitude, vp.longitude, vp.timestamp, vp.delay_minutes,
                vp.status, vp.direction
            FROM time_frames tf
            LEFT JOIN vehicle_positions vp ON 
                vp.timestamp BETWEEN tf.frame_time - interval '{frame_interval_seconds/2} seconds' 
                                 AND tf.frame_time + interval '{frame_interval_seconds/2} seconds'
            WHERE vp.vehicle_id IS NOT NULL 
            AND {' AND '.join(conditions)}
            ORDER BY vp.vehicle_id, tf.frame_time, vp.timestamp DESC
        )
        SELECT 
            frame_time, vehicle_id, route_id, line_name, transport_type,
            latitude, longitude, timestamp, delay_minutes, status, direction
        FROM vehicle_samples
        ORDER BY frame_time, transport_type, line_name, vehicle_id
        """
        
        chunk_data = await database.execute_query(query, *params)
        
        # Process into vehicle positions
        vehicles = [
            VehiclePosition(
                vehicle_id=row["vehicle_id"],
                route_id=row["route_id"],
                line_name=row["line_name"],
                transport_type=row["transport_type"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                timestamp=row["timestamp"],
                delay_minutes=row["delay_minutes"] or 0,
                status=row["status"] or "active",
                direction=row["direction"]
            )
            for row in chunk_data
        ]
        
        # Calculate frame count
        duration_seconds = duration_minutes * 60
        frame_count = max(1, duration_seconds // frame_interval_seconds)
        
        return SimulationChunkResponse(
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            vehicles=vehicles,
            total_vehicles=len(vehicles),
            frame_count=frame_count,
            recommended_frame_rate=30
        )
    
    async def get_simulation_stats(self, timestamp: Optional[datetime] = None) -> SimulationStats:
        """Get real-time simulation statistics"""
        
        if not timestamp:
            # Get latest timestamp
            latest_query = "SELECT MAX(timestamp) as latest FROM vehicle_positions"
            latest_result = await database.execute_single(latest_query)
            timestamp = latest_result["latest"]
        
        # Get stats for the specified time (within 5 minutes)
        time_window = timedelta(minutes=5)
        start_time = timestamp - time_window
        end_time = timestamp + time_window
        
        stats_query = """
        SELECT 
            COUNT(DISTINCT vehicle_id) as active_vehicles,
            AVG(CASE WHEN delay_minutes > 0 THEN delay_minutes ELSE NULL END) as avg_delay,
            json_object_agg(transport_type, vehicle_count) as transport_distribution,
            MIN(latitude) as min_lat, MAX(latitude) as max_lat,
            MIN(longitude) as min_lng, MAX(longitude) as max_lng
        FROM (
            SELECT DISTINCT ON (vehicle_id) 
                vehicle_id, transport_type, delay_minutes, latitude, longitude
            FROM vehicle_positions 
            WHERE timestamp BETWEEN $1 AND $2
            ORDER BY vehicle_id, timestamp DESC
        ) latest_vehicles
        CROSS JOIN LATERAL (
            SELECT COUNT(*) as vehicle_count 
            FROM vehicle_positions 
            WHERE transport_type = latest_vehicles.transport_type 
            AND timestamp BETWEEN $1 AND $2
        ) counts
        """
        
        result = await database.execute_single(stats_query, start_time, end_time)
        
        return SimulationStats(
            active_vehicles=result["active_vehicles"] or 0,
            average_delay_minutes=round(float(result["avg_delay"] or 0), 1),
            transport_type_distribution=result["transport_distribution"] or {},
            geographic_bounds={
                "min_lat": float(result["min_lat"] or 0),
                "max_lat": float(result["max_lat"] or 0),
                "min_lng": float(result["min_lng"] or 0),
                "max_lng": float(result["max_lng"] or 0)
            },
            last_updated=timestamp
        )
    
    async def get_time_series_data(
        self,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 60,
        transport_types: List[str] = None
    ) -> Dict[str, Any]:
        """Get time series data for analytics"""
        
        if not transport_types:
            transport_types = ["suburban", "subway", "tram", "bus", "ring", "regional", "ferry"]
        
        query = """
        WITH time_series AS (
            SELECT 
                date_trunc('hour', timestamp) + 
                (EXTRACT(minute FROM timestamp)::int / $4) * interval '1 minute' * $4 as time_bucket,
                transport_type,
                COUNT(DISTINCT vehicle_id) as vehicle_count,
                AVG(delay_minutes) as avg_delay,
                COUNT(*) as position_count
            FROM vehicle_positions 
            WHERE timestamp BETWEEN $1 AND $2
            AND transport_type = ANY($3)
            GROUP BY time_bucket, transport_type
            ORDER BY time_bucket, transport_type
        )
        SELECT 
            time_bucket,
            json_object_agg(transport_type, json_build_object(
                'vehicle_count', vehicle_count,
                'avg_delay', ROUND(avg_delay::numeric, 1),
                'position_count', position_count
            )) as data
        FROM time_series
        GROUP BY time_bucket
        ORDER BY time_bucket
        """
        
        results = await database.execute_query(query, start_time, end_time, transport_types, interval_minutes)
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "interval_minutes": interval_minutes,
            "data_points": [
                {
                    "timestamp": row["time_bucket"],
                    "metrics": row["data"]
                }
                for row in results
            ]
        }