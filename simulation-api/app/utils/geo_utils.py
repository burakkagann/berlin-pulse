"""
Geographic calculation utilities for simulation API
"""

import math
from typing import Tuple, List, Dict, Any


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    
    return c * r


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the bearing between two points
    Returns bearing in degrees (0-360)
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlon = lon2 - lon1
    
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360
    
    return bearing


def interpolate_position(
    lat1: float, lon1: float, lat2: float, lon2: float, 
    progress: float
) -> Tuple[float, float]:
    """
    Interpolate position between two points
    progress: 0.0 to 1.0 (0 = first point, 1 = second point)
    """
    lat = lat1 + (lat2 - lat1) * progress
    lon = lon1 + (lon2 - lon1) * progress
    return lat, lon


def get_bounding_box(coordinates: List[Tuple[float, float]], padding: float = 0.01) -> Dict[str, float]:
    """
    Get bounding box for a list of coordinates
    padding: additional padding in degrees
    """
    if not coordinates:
        # Default to Berlin bounds
        return {
            "min_lat": 52.3,
            "max_lat": 52.7,
            "min_lng": 13.0,
            "max_lng": 13.8
        }
    
    lats = [coord[0] for coord in coordinates]
    lngs = [coord[1] for coord in coordinates]
    
    return {
        "min_lat": min(lats) - padding,
        "max_lat": max(lats) + padding,
        "min_lng": min(lngs) - padding,
        "max_lng": max(lngs) + padding
    }


def is_within_berlin_bounds(lat: float, lon: float) -> bool:
    """
    Check if coordinates are within Berlin metropolitan area
    """
    # Berlin bounding box (approximate)
    berlin_bounds = {
        "min_lat": 52.3,
        "max_lat": 52.7,
        "min_lng": 13.0,
        "max_lng": 13.8
    }
    
    return (
        berlin_bounds["min_lat"] <= lat <= berlin_bounds["max_lat"] and
        berlin_bounds["min_lng"] <= lon <= berlin_bounds["max_lng"]
    )


def calculate_speed_kmh(
    lat1: float, lon1: float, time1,
    lat2: float, lon2: float, time2
) -> float:
    """
    Calculate speed in km/h between two positions and timestamps
    """
    distance_m = calculate_distance(lat1, lon1, lat2, lon2)
    time_diff_s = (time2 - time1).total_seconds()
    
    if time_diff_s <= 0:
        return 0.0
    
    speed_ms = distance_m / time_diff_s
    speed_kmh = speed_ms * 3.6
    
    return speed_kmh


def create_geojson_point(lat: float, lon: float, properties: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a GeoJSON Point feature"""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": properties or {}
    }


def create_geojson_linestring(coordinates: List[Tuple[float, float]], properties: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a GeoJSON LineString feature"""
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in coordinates]
        },
        "properties": properties or {}
    }