"""
Transport service - Business logic for transport information
"""

from typing import List, Optional, Dict, Any
import logging
import json

from ..core.database import database
from ..models.simulation import RouteInfo, StopInfo, RouteGeometry

logger = logging.getLogger(__name__)


class TransportService:
    """Service for handling transport information operations"""
    
    # Transport type color mapping
    TRANSPORT_COLORS = {
        'suburban': '#0066cc',    # S-Bahn blue
        'subway': '#003d82',      # U-Bahn dark blue
        'ring': '#ff6b35',        # Ring line orange
        'tram': '#00a86b',        # Tram green
        'bus': '#dc2626',         # Bus red
        'ferry': '#8b5cf6',       # Ferry purple
        'regional': '#ff8c00',    # Regional orange
        'express': '#dc143c'      # Express red
    }
    
    async def get_available_routes(self) -> List[RouteInfo]:
        """Get information about all tracked routes"""
        
        # Query to get route information with vehicle counts
        query = """
        WITH route_stats AS (
            SELECT 
                COALESCE(route_id, line_name) as route_key,
                line_name,
                transport_type,
                COUNT(DISTINCT vehicle_id) as vehicle_count_24h,
                COUNT(*) as total_positions
            FROM vehicle_positions 
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
            AND line_name IS NOT NULL
            GROUP BY COALESCE(route_id, line_name), line_name, transport_type
        ),
        route_geometry_availability AS (
            SELECT 
                COALESCE(route_id, line_name) as route_key,
                bool_or(geometry_geojson IS NOT NULL) as has_geometry
            FROM route_geometry
            GROUP BY COALESCE(route_id, line_name)
        )
        SELECT 
            rs.route_key as route_id,
            rs.line_name,
            rs.transport_type,
            rs.vehicle_count_24h,
            COALESCE(rga.has_geometry, false) as geometry_available
        FROM route_stats rs
        LEFT JOIN route_geometry_availability rga ON rs.route_key = rga.route_key
        WHERE rs.vehicle_count_24h > 10  -- Only include routes with significant activity
        ORDER BY rs.transport_type, rs.line_name
        """
        
        results = await database.execute_query(query)
        
        routes = []
        for row in results:
            # Generate route description
            description = self._generate_route_description(row["line_name"], row["transport_type"])
            
            route_info = RouteInfo(
                route_id=row["route_id"],
                line_name=row["line_name"],
                transport_type=row["transport_type"],
                description=description,
                color=self.TRANSPORT_COLORS.get(row["transport_type"], "#666666"),
                geometry_available=row["geometry_available"],
                vehicle_count_24h=row["vehicle_count_24h"]
            )
            routes.append(route_info)
        
        return routes
    
    async def get_route_geometry(self, route_id: str) -> Optional[RouteGeometry]:
        """Get route geometry for map visualization"""
        
        query = """
        SELECT 
            route_id, line_name, transport_type, 
            geometry_geojson, stops_data
        FROM route_geometry 
        WHERE route_id = $1 OR line_name = $1
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        result = await database.execute_single(query, route_id)
        
        if not result:
            return None
        
        # Process stops data
        stops = []
        if result["stops_data"]:
            try:
                stops_raw = result["stops_data"] if isinstance(result["stops_data"], list) else json.loads(result["stops_data"])
                stops = [
                    {
                        "stop_id": stop.get("id", ""),
                        "stop_name": stop.get("name", ""),
                        "latitude": stop.get("latitude", 0),
                        "longitude": stop.get("longitude", 0),
                        "type": "station"
                    }
                    for stop in stops_raw
                ]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse stops data for route {route_id}: {e}")
                stops = []
        
        return RouteGeometry(
            route_id=result["route_id"],
            line_name=result["line_name"],
            transport_type=result["transport_type"],
            geometry=result["geometry_geojson"],
            stops=stops
        )
    
    async def get_stops(self, tracked_only: bool = True) -> List[StopInfo]:
        """Get information about stops"""
        
        conditions = []
        params = []
        
        if tracked_only:
            conditions.append("is_tracked = true")
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        WITH stop_transport_types AS (
            SELECT 
                sr.stop_id,
                array_agg(DISTINCT vp.transport_type) as transport_types
            FROM stops_reference sr
            LEFT JOIN departure_events vp ON sr.stop_id = vp.stop_id
            {where_clause}
            GROUP BY sr.stop_id
        )
        SELECT 
            sr.stop_id, sr.stop_name, sr.latitude, sr.longitude, 
            sr.is_tracked, 
            COALESCE(stt.transport_types, ARRAY[]::text[]) as transport_types
        FROM stops_reference sr
        LEFT JOIN stop_transport_types stt ON sr.stop_id = stt.stop_id
        {where_clause}
        ORDER BY sr.is_tracked DESC, sr.stop_name
        """
        
        results = await database.execute_query(query, *params)
        
        stops = [
            StopInfo(
                stop_id=row["stop_id"],
                stop_name=row["stop_name"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                is_tracked=row["is_tracked"],
                transport_types=row["transport_types"] or []
            )
            for row in results
        ]
        
        return stops
    
    async def get_transport_types(self) -> Dict[str, Any]:
        """Get available transport types with their configurations"""
        
        query = """
        SELECT 
            transport_type,
            COUNT(DISTINCT vehicle_id) as unique_vehicles,
            COUNT(*) as total_positions,
            array_agg(DISTINCT line_name ORDER BY line_name) as lines
        FROM vehicle_positions 
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        GROUP BY transport_type
        ORDER BY unique_vehicles DESC
        """
        
        results = await database.execute_query(query)
        
        transport_types = {}
        for row in results:
            transport_type = row["transport_type"]
            transport_types[transport_type] = {
                "name": transport_type.title(),
                "color": self.TRANSPORT_COLORS.get(transport_type, "#666666"),
                "unique_vehicles": row["unique_vehicles"],
                "total_positions": row["total_positions"],
                "lines": row["lines"][:20] if row["lines"] else [],  # Limit to first 20 lines
                "description": self._get_transport_description(transport_type)
            }
        
        return {
            "transport_types": transport_types,
            "color_mapping": self.TRANSPORT_COLORS
        }
    
    def _generate_route_description(self, line_name: str, transport_type: str) -> str:
        """Generate route description based on line name and type"""
        
        # Special cases for well-known routes
        special_routes = {
            "S41": "Ring Line (Clockwise)",
            "S42": "Ring Line (Counter-clockwise)",
            "U1": "Warschauer Str. ↔ Uhlandstr.",
            "U2": "Pankow ↔ Ruhleben",
            "U3": "Nollendorfplatz ↔ Krumme Lanke",
            "U4": "Nollendorfplatz ↔ Innsbrucker Platz",
            "U5": "Hauptbahnhof ↔ Hönow",
            "U6": "Alt-Tegel ↔ Alt-Mariendorf",
            "U7": "Rathaus Spandau ↔ Rudow",
            "U8": "Wittenau ↔ Hermannstr.",
            "U9": "Rathaus Steglitz ↔ Osloer Str."
        }
        
        if line_name in special_routes:
            return special_routes[line_name]
        
        # Generate description based on transport type
        if transport_type == "suburban":
            return f"S-Bahn Line {line_name}"
        elif transport_type == "subway":
            return f"U-Bahn Line {line_name}"
        elif transport_type == "tram":
            if line_name.startswith("M"):
                return f"MetroTram Line {line_name}"
            else:
                return f"Tram Line {line_name}"
        elif transport_type == "bus":
            if line_name.startswith("X"):
                return f"Express Bus {line_name}"
            elif line_name.startswith("N"):
                return f"Night Bus {line_name}"
            else:
                return f"Bus Line {line_name}"
        elif transport_type == "ring":
            return f"Ring Line {line_name}"
        elif transport_type == "regional":
            return f"Regional Train {line_name}"
        elif transport_type == "ferry":
            return f"Ferry Line {line_name}"
        else:
            return f"{transport_type.title()} {line_name}"
    
    def _get_transport_description(self, transport_type: str) -> str:
        """Get description for transport type"""
        
        descriptions = {
            "suburban": "S-Bahn rapid transit system",
            "subway": "U-Bahn underground metro system",
            "ring": "S-Bahn ring line (S41/S42)",
            "tram": "Tram and MetroTram network",
            "bus": "Bus network including express and night services",
            "ferry": "Ferry services across waterways",
            "regional": "Regional train connections",
            "express": "Express bus services"
        }
        
        return descriptions.get(transport_type, f"{transport_type.title()} transport")