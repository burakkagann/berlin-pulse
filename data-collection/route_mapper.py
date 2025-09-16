"""
Route geometry mapping module for Berlin transport routes.
Discovers and stores route geometry using journey planning and trip data with polylines.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import json
from urllib.parse import quote
from database import get_db_manager

logger = logging.getLogger(__name__)

class RouteMapper:
    def __init__(self, api_base_url: str = "https://v6.bvg.transport.rest"):
        self.api_base_url = api_base_url
        self.session = None
        self.db_manager = None
        
        # Expanded target routes configuration with better error handling
        self.target_routes = {
            # S-Bahn routes - Major lines with known working stops
            "s7": {
                "name": "S7", 
                "type": "suburban", 
                "description": "S7 Line: Ahrensfelde ↔ Potsdam Hbf",
                "endpoints": ["900100003", "900100002"]  # Alexanderplatz to Berlin Hauptbahnhof
            },
            "s5": {
                "name": "S5", 
                "type": "suburban", 
                "description": "S5 Line: Strausberg Nord ↔ Spandau", 
                "endpoints": ["900100001", "900100003"]  # Friedrichstr to Alexanderplatz
            },
            "s1": {
                "name": "S1", 
                "type": "suburban", 
                "description": "S1 Line: Oranienburg ↔ Wannsee",
                "endpoints": ["900100002", "900100004"]  # Berlin Hauptbahnhof to Potsdamer Platz
            },
            "s3": {
                "name": "S3", 
                "type": "suburban", 
                "description": "S3 Line: Erkner ↔ Spandau",
                "endpoints": ["900120005", "900100003"]  # Ostbahnhof to Alexanderplatz
            },
            
            # Ring Bahn - Important circular line
            "s41": {
                "name": "S41", 
                "type": "ring", 
                "description": "S41 Ring: Clockwise circle",
                "endpoints": ["900058102", "900245025"]  # Gesundbrunnen to Warschauer Str
            },
            "s42": {
                "name": "S42", 
                "type": "ring", 
                "description": "S42 Ring: Counter-clockwise circle",
                "endpoints": ["900245025", "900058102"]  # Warschauer Str to Gesundbrunnen
            },
            
            # U-Bahn routes - Major subway lines
            "u6": {
                "name": "U6", 
                "type": "subway", 
                "description": "U6 Line: Alt-Tegel ↔ Alt-Mariendorf",
                "endpoints": ["900100001", "900100004"]  # Friedrichstr to Potsdamer Platz
            },
            "u2": {
                "name": "U2", 
                "type": "subway", 
                "description": "U2 Line: Pankow ↔ Ruhleben",
                "endpoints": ["900100004", "900003201"]  # Potsdamer Platz to Zoologischer Garten
            },
            
            # Tram routes - Sample tram lines
            "m1": {
                "name": "M1", 
                "type": "tram", 
                "description": "M1 MetroTram: Rosenthal Nord ↔ Am Kupfergraben",
                "endpoints": ["900100001", "900100003"]  # Using major stops for discovery
            },
            "12": {
                "name": "12", 
                "type": "tram", 
                "description": "Tram 12: Am Kupfergraben ↔ Pasedagplatz",
                "endpoints": ["900100003", "900100002"]  # Using major stops for discovery
            },
            
            # Bus routes - Sample major bus lines
            "100": {
                "name": "100", 
                "type": "bus", 
                "description": "Bus 100: Alexanderplatz ↔ Zoologischer Garten (Tourist bus)",
                "endpoints": ["900100003", "900003201"]  # Alexanderplatz to Zoo
            },
            "200": {
                "name": "200", 
                "type": "bus", 
                "description": "Bus 200: Prenzlauer Berg ↔ Potsdamer Platz",
                "endpoints": ["900100003", "900100004"]  # Using major stops
            }
        }
        
        self.request_timeout = 30
        self.retry_attempts = 3
        self.retry_delay = 5
    
    async def initialize(self):
        """Initialize the route mapper"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            headers={
                'User-Agent': 'Berlin-Transport-Timemachine/1.0'
            }
        )
        self.db_manager = await get_db_manager()
        logger.info("RouteMapper initialized")
    
    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        logger.info("RouteMapper closed")
    
    async def find_route_journey(self, route_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a representative journey for the route"""
        from_stop = route_config['endpoints'][0]
        to_stop = route_config['endpoints'][1]
        
        params = {
            'from': from_stop,
            'to': to_stop,
            'results': 5,  # Get multiple options
            'stopovers': 'true'  # Include intermediate stops
        }
        
        url = f"{self.api_base_url}/journeys"
        
        for attempt in range(self.retry_attempts):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        journeys = data.get('journeys', [])
                        
                        # Find journey with matching line
                        for journey in journeys:
                            matching_leg = self.find_matching_leg(journey, route_config)
                            if matching_leg:
                                logger.debug(f"Found matching journey for {route_config['name']}")
                                return matching_leg
                        
                        logger.warning(f"No matching journey found for {route_config['name']}")
                        return None
                        
                    elif response.status == 429:
                        logger.warning(f"Rate limit hit for route {route_config['name']}")
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        logger.warning(f"API returned status {response.status} for route {route_config['name']}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout finding journey for {route_config['name']}, attempt {attempt + 1}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Error finding journey for {route_config['name']}: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        logger.error(f"Failed to find journey for {route_config['name']} after {self.retry_attempts} attempts")
        return None
    
    def find_matching_leg(self, journey: Dict, route_config: Dict) -> Optional[Dict]:
        """Find the journey leg that matches our target route"""
        legs = journey.get('legs', [])
        
        for leg in legs:
            line = leg.get('line', {})
            if not line:
                continue
            
            line_name = line.get('name', '').upper()
            route_name = route_config['name'].upper()
            
            # Check if this leg matches our target route
            if line_name == route_name:
                return leg
        
        return None
    
    async def fetch_trip_geometry(self, trip_id: str) -> Optional[Dict[str, Any]]:
        """Fetch trip details with polyline geometry"""
        if not trip_id:
            return None
        
        # URL encode the trip_id
        encoded_trip_id = quote(trip_id, safe='')
        url = f"{self.api_base_url}/trips/{encoded_trip_id}"
        
        params = {
            'polyline': 'true',  # Request polyline geometry
            'stopovers': 'true'  # Include all stops
        }
        
        for attempt in range(self.retry_attempts):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        trip_data = data.get('trip', data)  # Some responses wrap in 'trip' key
                        
                        polyline = trip_data.get('polyline')
                        if polyline:
                            logger.debug(f"Successfully fetched geometry for trip {trip_id}")
                            return {
                                'polyline': polyline,
                                'stopovers': trip_data.get('stopovers', []),
                                'trip_data': trip_data
                            }
                        else:
                            logger.warning(f"No polyline data in trip {trip_id}")
                            return None
                        
                    elif response.status == 429:
                        logger.warning(f"Rate limit hit for trip {trip_id}")
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    elif response.status == 404:
                        logger.warning(f"Trip {trip_id} not found")
                        return None
                    else:
                        logger.warning(f"API returned status {response.status} for trip {trip_id}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching trip {trip_id}, attempt {attempt + 1}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Error fetching trip {trip_id}: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        logger.error(f"Failed to fetch trip {trip_id} after {self.retry_attempts} attempts")
        return None
    
    def process_trip_geometry(self, trip_data: Dict, route_config: Dict) -> Optional[Dict[str, Any]]:
        """Process trip geometry data into our format"""
        try:
            polyline = trip_data.get('polyline')
            stopovers = trip_data.get('stopovers', [])
            
            if not polyline:
                return None
            
            # Extract stops data
            stops_data = []
            for stopover in stopovers:
                stop = stopover.get('stop', {})
                location = stop.get('location', {})
                
                if location.get('latitude') and location.get('longitude'):
                    stop_info = {
                        'stop_id': stop.get('id'),
                        'stop_name': stop.get('name'),
                        'latitude': location['latitude'],
                        'longitude': location['longitude'],
                        'arrival': stopover.get('arrival'),
                        'departure': stopover.get('departure')
                    }
                    stops_data.append(stop_info)
            
            route_data = {
                'route_id': route_config['name'].lower(),
                'line_name': route_config['name'],
                'transport_type': route_config['type'],
                'direction': trip_data.get('trip_data', {}).get('direction'),
                'trip_id': trip_data.get('trip_data', {}).get('id'),
                'geometry_geojson': polyline,  # This should be GeoJSON from API
                'stops_data': stops_data
            }
            
            return route_data
            
        except Exception as e:
            logger.error(f"Error processing trip geometry: {e}")
            return None
    
    async def discover_route_geometry(self, route_config: Dict[str, Any]) -> bool:
        """Discover and store route geometry using journey planning"""
        logger.info(f"Discovering geometry for route {route_config['name']}")
        
        try:
            # Find representative journey for the route
            journey_leg = await self.find_route_journey(route_config)
            if not journey_leg:
                logger.warning(f"No journey found for route {route_config['name']}")
                return False
            
            # Extract trip ID from journey leg
            trip_id = journey_leg.get('tripId')
            if not trip_id:
                logger.warning(f"No trip ID found for route {route_config['name']}")
                return False
            
            # Fetch trip details with polyline geometry
            trip_geometry = await self.fetch_trip_geometry(trip_id)
            if not trip_geometry:
                logger.warning(f"No geometry data for route {route_config['name']}")
                return False
            
            # Process geometry data
            route_data = self.process_trip_geometry(trip_geometry, route_config)
            if not route_data:
                logger.warning(f"Failed to process geometry for route {route_config['name']}")
                return False
            
            # Store in database
            success = await self.db_manager.insert_route_geometry(route_data)
            if success:
                logger.info(f"Successfully stored geometry for route {route_config['name']}")
                return True
            else:
                logger.error(f"Failed to store geometry for route {route_config['name']}")
                return False
                
        except Exception as e:
            logger.error(f"Error discovering geometry for route {route_config['name']}: {e}")
            return False
    
    async def discover_all_route_geometries(self) -> int:
        """Discover and store geometry for all target routes with enhanced error handling"""
        try:
            await self.db_manager.update_collection_status('route_mapper', 'running')
        except Exception as e:
            logger.error(f"Failed to update collection status to running: {e}")
        
        successful_routes = 0
        failed_routes = []
        
        try:
            for route_id, route_config in self.target_routes.items():
                logger.info(f"Processing route {route_config['name']} ({route_config['description']})")
                
                try:
                    success = await self.discover_route_geometry(route_config)
                    if success:
                        successful_routes += 1
                        logger.info(f"✓ Successfully processed {route_config['name']}")
                    else:
                        failed_routes.append(route_config['name'])
                        logger.warning(f"✗ Failed to process {route_config['name']}")
                except Exception as route_error:
                    failed_routes.append(route_config['name'])
                    logger.error(f"✗ Error processing {route_config['name']}: {route_error}")
                
                # Small delay between routes to respect rate limits
                await asyncio.sleep(2)
            
            # Update status with detailed results
            status_message = f"Completed: {successful_routes}/{len(self.target_routes)} routes successful"
            if failed_routes:
                status_message += f". Failed: {', '.join(failed_routes[:3])}" + ("..." if len(failed_routes) > 3 else "")
            
            try:
                if successful_routes > 0:
                    await self.db_manager.update_collection_status('route_mapper', 'idle', successful_routes, status_message)
                else:
                    await self.db_manager.update_collection_status('route_mapper', 'warning', 0, f"No routes discovered. {status_message}")
            except Exception as e:
                logger.error(f"Failed to update final collection status: {e}")
            
            logger.info(f"Route geometry discovery completed: {status_message}")
            
        except Exception as e:
            error_message = f"Critical error in route discovery: {str(e)}"
            logger.error(error_message)
            try:
                await self.db_manager.update_collection_status('route_mapper', 'error', successful_routes, error_message)
            except Exception as status_error:
                logger.error(f"Failed to update error status: {status_error}")
        
        return successful_routes
    
    async def update_route_geometries(self) -> int:
        """Update existing route geometries (for periodic refresh)"""
        logger.info("Updating existing route geometries")
        return await self.discover_all_route_geometries()
    
    async def discover_route_by_name(self, route_name: str) -> bool:
        """Discover geometry for a specific route by name"""
        route_name_lower = route_name.lower()
        
        if route_name_lower in self.target_routes:
            route_config = self.target_routes[route_name_lower]
            return await self.discover_route_geometry(route_config)
        else:
            logger.error(f"Route {route_name} not found in target routes")
            return False
    
    async def validate_stored_geometries(self) -> Dict[str, bool]:
        """Validate that all target routes have geometry stored"""
        try:
            async with self.db_manager.pool.acquire() as conn:
                # Get all stored route geometries
                rows = await conn.fetch("""
                    SELECT DISTINCT route_id, line_name, transport_type 
                    FROM route_geometry
                """)
                
                stored_routes = {row['route_id'] for row in rows}
                
                validation_results = {}
                for route_id, route_config in self.target_routes.items():
                    validation_results[route_id] = route_id in stored_routes
                
                missing_routes = [route_id for route_id, stored in validation_results.items() if not stored]
                if missing_routes:
                    logger.warning(f"Missing geometry for routes: {missing_routes}")
                else:
                    logger.info("All target routes have geometry stored")
                
                return validation_results
                
        except Exception as e:
            logger.error(f"Error validating stored geometries: {e}")
            return {}


# Test function
async def test_route_mapper():
    """Test the route mapper functionality"""
    mapper = RouteMapper()
    await mapper.initialize()
    
    try:
        # Test discovery of all routes
        total_routes = await mapper.discover_all_route_geometries()
        print(f"Test completed: discovered {total_routes} route geometries")
        
        # Validate results
        validation = await mapper.validate_stored_geometries()
        print(f"Validation results: {validation}")
        
    finally:
        await mapper.close()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    asyncio.run(test_route_mapper())