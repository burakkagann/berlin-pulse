"""
Database connection and operations module for Berlin Transport data collection.
"""

import asyncio
import asyncpg
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool initialized")
            
            # Test connection
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.info("Database connection test successful")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def insert_vehicle_position(self, vehicle_data: Dict[str, Any]) -> bool:
        """Insert vehicle position data into database"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO vehicle_positions (
                        timestamp, vehicle_id, route_id, line_name, transport_type,
                        latitude, longitude, direction, delay_minutes, status, raw_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """, 
                    vehicle_data['timestamp'],
                    vehicle_data['vehicle_id'],
                    vehicle_data.get('route_id'),
                    vehicle_data.get('line_name'),
                    vehicle_data['transport_type'],
                    vehicle_data['latitude'],
                    vehicle_data['longitude'],
                    vehicle_data.get('direction'),
                    vehicle_data.get('delay_minutes', 0),
                    vehicle_data.get('status', 'active'),
                    json.dumps(vehicle_data.get('raw_data', {}))
                )
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert vehicle position: {e}")
            return False
    
    async def insert_departure_event(self, departure_data: Dict[str, Any]) -> bool:
        """Insert departure event data into database"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO departure_events (
                        timestamp, stop_id, stop_name, route_id, line_name, transport_type,
                        direction, scheduled_time, actual_time, delay_minutes, status,
                        platform, trip_id, raw_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                    departure_data['timestamp'],
                    departure_data['stop_id'],
                    departure_data['stop_name'],
                    departure_data.get('route_id'),
                    departure_data.get('line_name'),
                    departure_data['transport_type'],
                    departure_data.get('direction'),
                    departure_data['scheduled_time'],
                    departure_data.get('actual_time'),
                    departure_data.get('delay_minutes', 0),
                    departure_data.get('status', 'on_time'),
                    departure_data.get('platform'),
                    departure_data.get('trip_id'),
                    json.dumps(departure_data.get('raw_data', {}))
                )
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert departure event: {e}")
            return False
    
    async def insert_route_geometry(self, route_data: Dict[str, Any]) -> bool:
        """Insert route geometry data into database"""
        try:
            async with self.pool.acquire() as conn:
                # Check if route geometry already exists
                existing = await conn.fetchrow("""
                    SELECT id FROM route_geometry 
                    WHERE route_id = $1 AND transport_type = $2 AND direction = $3
                """, route_data['route_id'], route_data['transport_type'], route_data.get('direction'))
                
                if existing:
                    # Update existing geometry
                    await conn.execute("""
                        UPDATE route_geometry 
                        SET geometry_geojson = $1, stops_data = $2, trip_id = $3, updated_at = NOW()
                        WHERE id = $4
                    """,
                        json.dumps(route_data['geometry_geojson']),
                        json.dumps(route_data.get('stops_data', [])),
                        route_data.get('trip_id'),
                        existing['id']
                    )
                else:
                    # Insert new geometry
                    await conn.execute("""
                        INSERT INTO route_geometry (
                            route_id, line_name, transport_type, direction, trip_id,
                            geometry_geojson, stops_data
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                        route_data['route_id'],
                        route_data['line_name'],
                        route_data['transport_type'],
                        route_data.get('direction'),
                        route_data.get('trip_id'),
                        json.dumps(route_data['geometry_geojson']),
                        json.dumps(route_data.get('stops_data', []))
                    )
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert route geometry: {e}")
            return False
    
    async def update_collection_status(self, collector_name: str, status: str, 
                                     records_collected: int = 0, error_message: str = None):
        """Update collection status for monitoring"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO collection_status (collector_name, status, records_collected, error_message, last_run_at, last_success_at)
                    VALUES ($1, $2::VARCHAR, $3, $4, NOW(), CASE WHEN $2::VARCHAR = 'running' THEN NOW() ELSE NULL END)
                    ON CONFLICT (collector_name) DO UPDATE SET
                        status = EXCLUDED.status,
                        records_collected = collection_status.records_collected + EXCLUDED.records_collected,
                        error_message = EXCLUDED.error_message,
                        last_run_at = EXCLUDED.last_run_at,
                        last_success_at = CASE WHEN EXCLUDED.status = 'running' THEN NOW() ELSE collection_status.last_success_at END,
                        updated_at = NOW()
                """, collector_name, status, records_collected, error_message)
                
        except Exception as e:
            logger.error(f"Failed to update collection status: {e}")
    
    async def get_tracked_stops(self) -> List[Dict[str, Any]]:
        """Get list of tracked stops for departure monitoring"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT stop_id, stop_name, latitude, longitude
                    FROM stops_reference 
                    WHERE is_tracked = TRUE
                """)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get tracked stops: {e}")
            return []
    
    async def cleanup_old_data(self, days_to_keep: int = 7):
        """Clean up old data to maintain rolling window"""
        try:
            async with self.pool.acquire() as conn:
                # Delete old vehicle positions
                vehicle_deleted = await conn.execute("""
                    DELETE FROM vehicle_positions 
                    WHERE timestamp < NOW() - INTERVAL '%s days'
                """ % days_to_keep)
                
                # Delete old departure events
                departure_deleted = await conn.execute("""
                    DELETE FROM departure_events 
                    WHERE timestamp < NOW() - INTERVAL '%s days'
                """ % days_to_keep)
                
                logger.info(f"Cleaned up old data: {vehicle_deleted} vehicle positions, {departure_deleted} departure events")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")


# Global database manager instance
db_manager = None

async def get_db_manager():
    """Get or create database manager instance"""
    global db_manager
    if db_manager is None:
        database_url = os.getenv('DATABASE_URL', 'postgresql://transport_user:transport_pass@localhost:5432/berlin_transport')
        db_manager = DatabaseManager(database_url)
        await db_manager.initialize()
    return db_manager

async def close_db_manager():
    """Close database manager"""
    global db_manager
    if db_manager:
        await db_manager.close()
        db_manager = None