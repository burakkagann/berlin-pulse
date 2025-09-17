"""
Health check endpoints
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import asyncpg

from ..core.database import database

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "simulation-api"
    }


@router.get("/health/database")
async def database_health():
    """Database connectivity health check"""
    try:
        result = await database.execute_single("SELECT 1 as status, NOW() as timestamp")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": result["timestamp"]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")


@router.get("/health/data")
async def data_health():
    """Data availability health check"""
    try:
        # Check recent data availability
        query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT transport_type) as transport_types,
            MIN(timestamp) as earliest_data,
            MAX(timestamp) as latest_data,
            COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_records
        FROM vehicle_positions
        """
        
        result = await database.execute_single(query)
        
        is_healthy = (
            result["total_records"] > 0 and 
            result["transport_types"] >= 4 and
            result["recent_records"] > 0
        )
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "data_summary": {
                "total_records": result["total_records"],
                "transport_types": result["transport_types"],
                "earliest_data": result["earliest_data"],
                "latest_data": result["latest_data"],
                "recent_records": result["recent_records"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Data health check failed: {str(e)}")