"""
Vehicle position tracking module using BVG transport.rest API radar endpoint.
Collects real-time vehicle positions across Berlin in geographic sectors.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json
from database import get_db_manager

logger = logging.getLogger(__name__)

class VehicleTracker:
    def __init__(self, api_base_url: str = "https://v6.bvg.transport.rest"):
        self.api_base_url = api_base_url
        self.session = None
        self.db_manager = None
        
        # Berlin sectors for efficient radar coverage
        self.berlin_sectors = [
            # Central Berlin
            {
                "name": "central", 
                "north": 52.55, "south": 52.48, 
                "west": 13.35, "east": 13.45
            },
            # Eastern Berlin
            {
                "name": "east", 
                "north": 52.55, "south": 52.48, 
                "west": 13.45, "east": 13.55
            },
            # Western Berlin
            {
                "name": "west", 
                "north": 52.55, "south": 52.48, 
                "west": 13.25, "east": 13.35
            },
            # Northern Berlin
            {
                "name": "north", 
                "north": 52.60, "south": 52.55, 
                "west": 13.30, "east": 13.50
            },
            # Southern Berlin
            {
                "name": "south", 
                "north": 52.48, "south": 52.42, 
                "west": 13.30, "east": 13.50
            },
            # Northeast Berlin
            {
                "name": "northeast", 
                "north": 52.60, "south": 52.55, 
                "west": 13.50, "east": 13.70
            },
            # Southeast Berlin
            {
                "name": "southeast", 
                "north": 52.48, "south": 52.42, 
                "west": 13.50, "east": 13.70
            },
            # Northwest Berlin
            {
                "name": "northwest", 
                "north": 52.60, "south": 52.55, 
                "west": 13.10, "east": 13.30
            },
            # Southwest Berlin
            {
                "name": "southwest", 
                "north": 52.48, "south": 52.40, 
                "west": 13.10, "east": 13.30
            }
        ]
        
        self.max_results_per_sector = 100
        self.request_timeout = 30
        self.retry_attempts = 3
        self.retry_delay = 5
        
        # Transport type mapping
        self.transport_type_mapping = {
            'suburban': 'suburban',  # S-Bahn
            'subway': 'subway',      # U-Bahn
            'tram': 'tram',          # Tram
            'bus': 'bus',            # Bus
            'ferry': 'ferry',        # Ferry
            'express': 'express',    # Express trains
            'regional': 'regional'   # Regional trains
        }
    
    async def initialize(self):
        """Initialize the vehicle tracker"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            headers={
                'User-Agent': 'Berlin-Transport-Timemachine/1.0'
            }
        )
        self.db_manager = await get_db_manager()
        logger.info("VehicleTracker initialized")
    
    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        logger.info("VehicleTracker closed")
    
    async def collect_vehicles_in_sector(self, sector: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect all vehicles in a geographic sector using /radar endpoint"""
        params = {
            'north': sector['north'],
            'south': sector['south'],
            'west': sector['west'],
            'east': sector['east'],
            'results': self.max_results_per_sector
        }
        
        url = f"{self.api_base_url}/radar"
        
        for attempt in range(self.retry_attempts):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        movements_count = len(data.get('movements', []))
                        logger.info(f"API returned {movements_count} movements for {sector['name']} sector")
                        vehicles = self.process_radar_response(data, sector['name'])
                        logger.info(f"Successfully processed {len(vehicles)} vehicles from {sector['name']} sector")
                        return vehicles
                    elif response.status == 429:
                        # Rate limit hit
                        logger.warning(f"Rate limit hit for sector {sector['name']}, attempt {attempt + 1}")
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        logger.warning(f"API returned status {response.status} for sector {sector['name']}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout collecting vehicles from {sector['name']}, attempt {attempt + 1}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Error collecting vehicles from {sector['name']}: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        # All attempts failed
        logger.error(f"Failed to collect vehicles from {sector['name']} after {self.retry_attempts} attempts")
        return []
    
    def process_radar_response(self, data: Dict, sector_name: str) -> List[Dict[str, Any]]:
        """Process radar API response and extract vehicle data"""
        vehicles = []
        current_time = datetime.now(timezone.utc)
        
        # Extract movements from the API response
        movements = data.get('movements', [])
        logger.debug(f"Processing {len(movements)} movements from {sector_name} sector")
        
        for item in movements:
            try:
                vehicle = self.extract_vehicle_data(item, current_time, sector_name)
                if vehicle:
                    vehicles.append(vehicle)
            except Exception as e:
                logger.debug(f"Error processing vehicle item: {e}")
                continue
        
        return vehicles
    
    def extract_vehicle_data(self, item: Dict, timestamp: datetime, sector_name: str) -> Optional[Dict[str, Any]]:
        """Extract relevant vehicle data from radar response item"""
        try:
            # Extract location
            location = item.get('location', {})
            if not location:
                return None
            
            latitude = location.get('latitude')
            longitude = location.get('longitude')
            
            if latitude is None or longitude is None:
                return None
            
            # Extract line information
            line = item.get('line', {})
            trip = item.get('trip', {})
            
            # Determine transport type
            transport_type = self.determine_transport_type(line, trip)
            if not transport_type:
                return None
            
            # Generate vehicle ID (might be tripId or other identifier)
            vehicle_id = (
                trip.get('id') or 
                item.get('tripId') or 
                f"{line.get('name', 'unknown')}_{latitude}_{longitude}_{int(timestamp.timestamp())}"
            )
            
            # Extract route and line information
            route_id = line.get('id', '').lower()
            line_name = line.get('name', '')
            direction = trip.get('direction') or item.get('direction')
            
            # Calculate delay if available
            delay_minutes = self.calculate_delay(item)
            
            # Determine status
            status = self.determine_vehicle_status(item, delay_minutes)
            
            vehicle_data = {
                'timestamp': timestamp,
                'vehicle_id': vehicle_id,
                'route_id': route_id if route_id else None,
                'line_name': line_name if line_name else None,
                'transport_type': transport_type,
                'latitude': float(latitude),
                'longitude': float(longitude),
                'direction': direction,
                'delay_minutes': delay_minutes,
                'status': status,
                'raw_data': {
                    'sector': sector_name,
                    'original_item': item
                }
            }
            
            return vehicle_data
            
        except Exception as e:
            logger.debug(f"Error extracting vehicle data: {e}")
            return None
    
    def determine_transport_type(self, line: Dict, trip: Dict) -> Optional[str]:
        """Determine transport type from line and trip data with Berlin-specific patterns"""
        import re
        
        line_name = line.get('name', '').upper().strip()
        mode = line.get('mode', '').lower()
        product = line.get('product', '').lower()
        
        # Berlin-specific line pattern recognition (PRIORITY)
        if line_name:
            # U-Bahn lines (U1, U2, U3, U4, U5, U6, U7, U8, U9)
            if re.match(r'^U[1-9]$', line_name):
                return 'subway'
            
            # Ring Bahn (S41 clockwise, S42 counter-clockwise)
            if line_name in ['S41', 'S42']:
                return 'ring'
            
            # S-Bahn lines (S1, S2, S3, S5, S7, S8, S9, S25, S26, S45, S46, S47, S75, S85)
            if re.match(r'^S[1-9]$|^S[2-8][0-9]$', line_name):
                return 'suburban'
            
            # MetroTram lines (M1, M2, M4, M5, M6, M8, M10, M13, M17, etc.)
            if re.match(r'^M[1-9][0-9]?$', line_name):
                return 'tram'
            
            # Regular Tram lines (12, 16, 18, 21, 27, 37, 50, 60, 61, 62, 63, 67, 68)
            if re.match(r'^[1-6][0-9]?$|^[7-9][0-9]?$', line_name) and len(line_name) <= 2:
                # Check if it's likely a tram (not a high-numbered bus)
                if any(tram_num in line_name for tram_num in ['12', '16', '18', '21', '27', '37', '50', '60', '61', '62', '63', '67', '68']):
                    return 'tram'
            
            # Express Bus lines (X7, X9, X10, X11, X21, X36, X49, X54, X76, X83)
            if re.match(r'^X[1-9][0-9]?$', line_name):
                return 'bus'
            
            # Night Bus lines (N1, N2, N3, N5, N6, N7, N8, N9, N10, etc.)
            if re.match(r'^N[1-9][0-9]?$', line_name):
                return 'bus'
            
            # Regional Express (RE1, RE2, RE7, RE8, etc.)
            if re.match(r'^RE[1-9][0-9]?$', line_name):
                return 'regional'
            
            # Regional Bahn (RB10, RB14, RB20, etc.)
            if re.match(r'^RB[1-9][0-9]?$', line_name):
                return 'regional'
            
            # General bus patterns (catch remaining bus routes)
            if any(pattern in line_name for pattern in ['BUS']) or re.match(r'^[1-9][0-9][0-9]+$', line_name):
                return 'bus'
        
        # Fallback to API mode/product mapping (secondary priority)
        api_mapping = {
            'suburban': 'suburban',
            'subway': 'subway', 
            'tram': 'tram',
            'bus': 'bus',
            'ferry': 'ferry',
            'express': 'regional',
            'regional': 'regional'
        }
        
        # Check mode first, then product
        if mode in api_mapping:
            return api_mapping[mode]
        if product in api_mapping:
            return api_mapping[product]
        
        # Final fallback based on line name patterns
        if line_name:
            if 'TRAM' in line_name or 'STR' in line_name:
                return 'tram'
            elif any(x in line_name for x in ['BAHN', 'TRAIN']):
                return 'suburban'
        
        # Ultimate fallback
        return 'bus'
    
    def calculate_delay(self, item: Dict) -> int:
        """Calculate delay in minutes from vehicle data"""
        # This is complex as radar endpoint doesn't always provide delay info
        # We'll need to enhance this based on actual API response structure
        delay = item.get('delay', 0)
        
        if isinstance(delay, (int, float)):
            return int(delay / 60) if delay > 0 else 0  # Convert seconds to minutes
        
        return 0
    
    def determine_vehicle_status(self, item: Dict, delay_minutes: int) -> str:
        """Determine vehicle status based on available data"""
        # Check if explicitly cancelled
        if item.get('cancelled', False):
            return 'cancelled'
        
        # Determine status based on delay
        if delay_minutes > 10:
            return 'delayed'
        elif delay_minutes > 5:
            return 'delayed'
        else:
            return 'active'
    
    async def collect_all_vehicles(self) -> int:
        """Collect vehicles from all sectors"""
        await self.db_manager.update_collection_status('vehicle_tracker', 'running')
        
        total_vehicles = 0
        
        try:
            # Create tasks for all sectors to collect in parallel
            tasks = [
                self.collect_vehicles_in_sector(sector) 
                for sector in self.berlin_sectors
            ]
            
            # Execute all sector collections in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error collecting from sector {self.berlin_sectors[i]['name']}: {result}")
                    continue
                
                vehicles = result
                
                # Store vehicles in database
                for vehicle in vehicles:
                    success = await self.db_manager.insert_vehicle_position(vehicle)
                    if success:
                        total_vehicles += 1
            
            await self.db_manager.update_collection_status('vehicle_tracker', 'idle', total_vehicles)
            logger.info(f"Successfully collected {total_vehicles} vehicle positions")
            
        except Exception as e:
            logger.error(f"Error in collect_all_vehicles: {e}")
            await self.db_manager.update_collection_status('vehicle_tracker', 'error', 0, str(e))
        
        return total_vehicles
    
    async def run_continuous_collection(self, interval_seconds: int = 30):
        """Run continuous vehicle collection"""
        logger.info(f"Starting continuous vehicle collection with {interval_seconds}s interval")
        
        while True:
            try:
                start_time = datetime.now()
                total_collected = await self.collect_all_vehicles()
                end_time = datetime.now()
                
                collection_time = (end_time - start_time).total_seconds()
                logger.info(f"Collection cycle completed: {total_collected} vehicles in {collection_time:.1f}s")
                
                # Wait for next collection
                sleep_time = max(0, interval_seconds - collection_time)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("Vehicle collection stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous collection: {e}")
                await asyncio.sleep(interval_seconds)


# Test function
async def test_vehicle_tracker():
    """Test the vehicle tracker functionality"""
    tracker = VehicleTracker()
    await tracker.initialize()
    
    try:
        # Test single collection
        total_vehicles = await tracker.collect_all_vehicles()
        print(f"Test completed: collected {total_vehicles} vehicles")
        
    finally:
        await tracker.close()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    asyncio.run(test_vehicle_tracker())