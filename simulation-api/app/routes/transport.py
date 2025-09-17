"""
Transport information endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
import logging

from ..models.simulation import RouteInfo, StopInfo, RouteGeometry
from ..services.transport_service import TransportService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_transport_service() -> TransportService:
    """Dependency to get transport service instance"""
    return TransportService()


@router.get("/routes", response_model=List[RouteInfo])
async def get_available_routes(
    service: TransportService = Depends(get_transport_service)
):
    """Get information about all tracked routes"""
    try:
        return await service.get_available_routes()
    except Exception as e:
        logger.error(f"Failed to get available routes: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve route information")


@router.get("/routes/{route_id}/geometry", response_model=RouteGeometry)
async def get_route_geometry(
    route_id: str,
    service: TransportService = Depends(get_transport_service)
):
    """Get route geometry for map visualization"""
    try:
        geometry = await service.get_route_geometry(route_id)
        if not geometry:
            raise HTTPException(status_code=404, detail=f"Route geometry not found for {route_id}")
        return geometry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get route geometry for {route_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve route geometry")


@router.get("/stops", response_model=List[StopInfo])
async def get_tracked_stops(
    tracked_only: bool = True,
    service: TransportService = Depends(get_transport_service)
):
    """Get information about tracked stops"""
    try:
        return await service.get_stops(tracked_only=tracked_only)
    except Exception as e:
        logger.error(f"Failed to get stops: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stop information")


@router.get("/transport-types")
async def get_transport_types(
    service: TransportService = Depends(get_transport_service)
):
    """Get available transport types with their configurations"""
    try:
        return await service.get_transport_types()
    except Exception as e:
        logger.error(f"Failed to get transport types: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transport types")