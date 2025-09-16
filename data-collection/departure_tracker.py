"""
Departure and arrival events tracking module for major Berlin transport stops.
Monitors real-time departure/arrival information including delays and cancellations.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from dateutil import parser as date_parser
from typing import List, Dict, Any, Optional
import json
from database import get_db_manager

logger = logging.getLogger(__name__)

class DepartureTracker:
    def __init__(self, api_base_url: str = "https://v6.bvg.transport.rest"):
        self.api_base_url = api_base_url
        self.session = None
        self.db_manager = None
        
        # Configuration
        self.duration_minutes = 60  # Look ahead 60 minutes
        self.max_departures = 100   # Max departures per stop
        self.request_timeout = 30
        self.retry_attempts = 3
        self.retry_delay = 5
        
        # Transport type mapping (same as vehicle tracker)
        self.transport_type_mapping = {
            'suburban': 'suburban',
            'subway': 'subway', 
            'tram': 'tram',
            'bus': 'bus',
            'ferry': 'ferry',
            'express': 'express',
            'regional': 'regional'
        }
    
    async def initialize(self):
        """Initialize the departure tracker"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            headers={
                'User-Agent': 'Berlin-Transport-Timemachine/1.0'
            }
        )
        self.db_manager = await get_db_manager()
        logger.info("DepartureTracker initialized")
    
    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
        logger.info("DepartureTracker closed")
    
    async def collect_departures_for_stop(self, stop_id: str, stop_name: str) -> List[Dict[str, Any]]:
        """Collect departure/arrival data for a specific stop"""
        params = {
            'duration': self.duration_minutes,
            'results': self.max_departures,
        }
        
        url = f"{self.api_base_url}/stops/{stop_id}/departures"
        
        for attempt in range(self.retry_attempts):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        departures = self.process_departures_response(data, stop_id, stop_name)
                        logger.debug(f"Collected {len(departures)} departures from {stop_name}")
                        return departures
                    elif response.status == 429:
                        # Rate limit hit
                        logger.warning(f"Rate limit hit for stop {stop_name}, attempt {attempt + 1}")
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    elif response.status == 404:
                        logger.warning(f"Stop {stop_id} ({stop_name}) not found")
                        return []
                    else:
                        logger.warning(f"API returned status {response.status} for stop {stop_name}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout collecting departures from {stop_name}, attempt {attempt + 1}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Error collecting departures from {stop_name}: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        # All attempts failed
        logger.error(f"Failed to collect departures from {stop_name} after {self.retry_attempts} attempts")
        return []
    
    def process_departures_response(self, data: List[Dict], stop_id: str, stop_name: str) -> List[Dict[str, Any]]:
        """Process departures API response and extract departure data"""
        departures = []
        current_time = datetime.now(timezone.utc)
        
        for item in data:
            try:
                departure = self.extract_departure_data(item, stop_id, stop_name, current_time)
                if departure:
                    departures.append(departure)
            except Exception as e:
                logger.debug(f"Error processing departure item: {e}")
                continue
        
        return departures
    
    def extract_departure_data(self, item: Dict, stop_id: str, stop_name: str, 
                             timestamp: datetime) -> Optional[Dict[str, Any]]:
        """Extract relevant departure data from API response item"""
        try:
            # Extract line information
            line = item.get('line', {})
            if not line:
                return None
            
            # Determine transport type
            transport_type = self.determine_transport_type(line)
            if not transport_type:
                return None
            
            # Extract timing information
            scheduled_time = self.parse_datetime(item.get('plannedWhen'))
            actual_time = self.parse_datetime(item.get('when'))
            
            if not scheduled_time:
                return None
            
            # Calculate delay
            delay_minutes = item.get('delay', 0)
            if isinstance(delay_minutes, (int, float)):
                delay_minutes = int(delay_minutes / 60) if delay_minutes > 0 else 0
            else:
                delay_minutes = 0
            
            # If no explicit delay, calculate from times
            if delay_minutes == 0 and actual_time and scheduled_time:
                delay_seconds = (actual_time - scheduled_time).total_seconds()
                delay_minutes = max(0, int(delay_seconds / 60))
            
            # Determine status
            status = self.determine_departure_status(item, delay_minutes)
            
            # Extract other information
            route_id = line.get('id', '').lower()
            line_name = line.get('name', '')
            direction = item.get('direction', '')
            platform = item.get('platform') or item.get('plannedPlatform')
            trip_id = item.get('tripId')
            
            departure_data = {
                'timestamp': timestamp,
                'stop_id': stop_id,
                'stop_name': stop_name,
                'route_id': route_id if route_id else None,
                'line_name': line_name if line_name else None,
                'transport_type': transport_type,
                'direction': direction,
                'scheduled_time': scheduled_time,
                'actual_time': actual_time,
                'delay_minutes': delay_minutes,
                'status': status,
                'platform': platform,
                'trip_id': trip_id,
                'raw_data': {
                    'original_item': item
                }
            }
            
            return departure_data
            
        except Exception as e:
            logger.debug(f"Error extracting departure data: {e}")
            return None
    
    def determine_transport_type(self, line: Dict) -> Optional[str]:
        """Determine transport type from line data with Berlin-specific patterns"""
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
    
    def parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from API response"""
        if not datetime_str:
            return None
        
        try:
            # Use dateutil parser for robust datetime parsing
            dt = date_parser.parse(datetime_str)
            
            # Ensure timezone aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            return dt
            
        except Exception as e:
            logger.debug(f"Error parsing datetime '{datetime_str}': {e}")
            return None
    
    def determine_departure_status(self, item: Dict, delay_minutes: int) -> str:
        """Determine departure status based on available data"""
        # Check if explicitly cancelled
        if item.get('cancelled', False):
            return 'cancelled'
        
        # Check for explicit status fields
        if 'realtimeDataUpdatedAt' in item or 'when' in item:
            # Real-time data available
            if delay_minutes > 5:
                return 'delayed'
            else:
                return 'on_time'
        
        # No real-time data, assume on time
        return 'on_time'
    
    async def collect_all_departures(self) -> int:
        """Collect departures from all tracked stops"""
        await self.db_manager.update_collection_status('departure_tracker', 'running')
        
        total_departures = 0
        
        try:
            # Get tracked stops
            tracked_stops = await self.db_manager.get_tracked_stops()
            
            if not tracked_stops:
                logger.warning("No tracked stops found in database")
                return 0
            
            # Create tasks for all stops to collect in parallel
            tasks = [
                self.collect_departures_for_stop(stop['stop_id'], stop['stop_name'])
                for stop in tracked_stops
            ]
            
            # Execute all stop collections in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error collecting from stop {tracked_stops[i]['stop_name']}: {result}")
                    continue
                
                departures = result
                
                # Store departures in database
                for departure in departures:
                    success = await self.db_manager.insert_departure_event(departure)
                    if success:
                        total_departures += 1
            
            await self.db_manager.update_collection_status('departure_tracker', 'idle', total_departures)
            logger.info(f"Successfully collected {total_departures} departure events")
            
        except Exception as e:
            logger.error(f"Error in collect_all_departures: {e}")
            await self.db_manager.update_collection_status('departure_tracker', 'error', 0, str(e))
        
        return total_departures
    
    async def run_continuous_collection(self, interval_seconds: int = 60):
        """Run continuous departure collection"""
        logger.info(f"Starting continuous departure collection with {interval_seconds}s interval")
        
        while True:
            try:
                start_time = datetime.now()
                total_collected = await self.collect_all_departures()
                end_time = datetime.now()
                
                collection_time = (end_time - start_time).total_seconds()
                logger.info(f"Departure collection cycle completed: {total_collected} events in {collection_time:.1f}s")
                
                # Wait for next collection
                sleep_time = max(0, interval_seconds - collection_time)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("Departure collection stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous departure collection: {e}")
                await asyncio.sleep(interval_seconds)


# Test function
async def test_departure_tracker():
    """Test the departure tracker functionality"""
    tracker = DepartureTracker()
    await tracker.initialize()
    
    try:
        # Test single collection
        total_departures = await tracker.collect_all_departures()
        print(f"Test completed: collected {total_departures} departure events")
        
        # Test single stop
        departures = await tracker.collect_departures_for_stop("900100003", "S+U Alexanderplatz")
        print(f"Alexanderplatz test: {len(departures)} departures")
        
    finally:
        await tracker.close()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    asyncio.run(test_departure_tracker())