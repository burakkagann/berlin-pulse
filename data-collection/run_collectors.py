"""
Main orchestrator for running all data collection services.
Coordinates vehicle tracking, departure monitoring, and route geometry collection.
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime
from typing import List, Any

from vehicle_tracker import VehicleTracker
from departure_tracker import DepartureTracker
from route_mapper import RouteMapper
from database import get_db_manager, close_db_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/collectors.log') if os.path.exists('/app/logs') else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)

class DataCollectionOrchestrator:
    def __init__(self):
        self.vehicle_tracker = None
        self.departure_tracker = None
        self.route_mapper = None
        self.db_manager = None
        
        self.running = False
        self.tasks = []
        
        # Configuration from environment
        self.vehicle_collection_interval = int(os.getenv('VEHICLE_COLLECTION_INTERVAL', '30'))
        self.departure_collection_interval = int(os.getenv('DEPARTURE_COLLECTION_INTERVAL', '60'))
        self.route_discovery_interval = int(os.getenv('ROUTE_DISCOVERY_INTERVAL', '3600'))  # 1 hour
        self.cleanup_interval = int(os.getenv('CLEANUP_INTERVAL', '86400'))  # 24 hours
        self.data_retention_days = int(os.getenv('DATA_RETENTION_DAYS', '7'))
        
    async def initialize(self):
        """Initialize all collectors and database"""
        logger.info("Initializing data collection orchestrator")
        
        try:
            # Initialize database manager
            self.db_manager = await get_db_manager()
            
            # Initialize collectors
            api_base_url = os.getenv('API_BASE_URL', 'https://v6.bvg.transport.rest')
            
            self.vehicle_tracker = VehicleTracker(api_base_url)
            await self.vehicle_tracker.initialize()
            
            self.departure_tracker = DepartureTracker(api_base_url)
            await self.departure_tracker.initialize()
            
            self.route_mapper = RouteMapper(api_base_url)
            await self.route_mapper.initialize()
            
            logger.info("All collectors initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize collectors: {e}")
            raise
    
    async def close(self):
        """Clean up all resources"""
        logger.info("Shutting down data collection orchestrator")
        
        # Cancel all running tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close collectors
        if self.vehicle_tracker:
            await self.vehicle_tracker.close()
        if self.departure_tracker:
            await self.departure_tracker.close()
        if self.route_mapper:
            await self.route_mapper.close()
        
        # Close database
        await close_db_manager()
        
        logger.info("Orchestrator shutdown complete")
    
    async def discover_initial_routes(self):
        """Run initial route geometry discovery"""
        logger.info("Starting initial route geometry discovery")
        
        try:
            total_routes = await self.route_mapper.discover_all_route_geometries()
            logger.info(f"Initial route discovery completed: {total_routes} routes discovered")
            
            # Validate results
            validation = await self.route_mapper.validate_stored_geometries()
            successful = sum(1 for success in validation.values() if success)
            total = len(validation)
            
            if successful == total:
                logger.info("All target routes successfully discovered")
            else:
                logger.warning(f"Route discovery incomplete: {successful}/{total} routes successful")
                
        except Exception as e:
            logger.error(f"Error in initial route discovery: {e}")
    
    async def run_periodic_cleanup(self):
        """Run periodic data cleanup to maintain rolling window"""
        logger.info(f"Starting periodic cleanup with {self.cleanup_interval}s interval")
        
        while self.running:
            try:
                logger.info("Running data cleanup")
                await self.db_manager.cleanup_old_data(self.data_retention_days)
                logger.info(f"Data cleanup completed, keeping {self.data_retention_days} days of data")
                
            except Exception as e:
                logger.error(f"Error in data cleanup: {e}")
            
            # Wait for next cleanup
            await asyncio.sleep(self.cleanup_interval)
    
    async def run_periodic_route_updates(self):
        """Run periodic route geometry updates"""
        logger.info(f"Starting periodic route updates with {self.route_discovery_interval}s interval")
        
        while self.running:
            try:
                await asyncio.sleep(self.route_discovery_interval)  # Wait first
                
                if self.running:
                    logger.info("Running route geometry update")
                    updated_routes = await self.route_mapper.update_route_geometries()
                    logger.info(f"Route update completed: {updated_routes} routes updated")
                
            except Exception as e:
                logger.error(f"Error in route updates: {e}")
    
    async def monitor_collection_health(self):
        """Monitor the health of data collection processes"""
        logger.info("Starting collection health monitoring")
        
        while self.running:
            try:
                # Check collection status in database
                async with self.db_manager.pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT collector_name, status, last_success_at, error_message,
                               records_collected, updated_at
                        FROM collection_status
                        ORDER BY collector_name
                    """)
                    
                    current_time = datetime.now()
                    
                    for row in rows:
                        collector_name = row['collector_name']
                        status = row['status']
                        last_success = row['last_success_at']
                        error_message = row['error_message']
                        
                        if last_success:
                            time_since_success = (current_time - last_success.replace(tzinfo=None)).total_seconds()
                            
                            # Alert if no success in the last 10 minutes
                            if time_since_success > 600:
                                logger.warning(f"Collector {collector_name} hasn't succeeded in {time_since_success:.0f}s")
                        
                        if status == 'error' and error_message:
                            logger.error(f"Collector {collector_name} in error state: {error_message}")
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
            
            # Check every 5 minutes
            await asyncio.sleep(300)
    
    async def start_collection(self):
        """Start all data collection processes"""
        logger.info("Starting continuous data collection")
        
        self.running = True
        
        # Create tasks for continuous collection
        tasks = [
            asyncio.create_task(self.vehicle_tracker.run_continuous_collection(self.vehicle_collection_interval)),
            asyncio.create_task(self.departure_tracker.run_continuous_collection(self.departure_collection_interval)),
            asyncio.create_task(self.run_periodic_cleanup()),
            asyncio.create_task(self.run_periodic_route_updates()),
            asyncio.create_task(self.monitor_collection_health())
        ]
        
        self.tasks = tasks
        
        logger.info("All collection processes started")
        
        try:
            # Wait for all tasks to complete (they should run indefinitely)
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in collection processes: {e}")
        finally:
            self.running = False
    
    def setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.running = False
            
            # Create shutdown task
            loop = asyncio.get_event_loop()
            loop.create_task(self.close())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main entry point"""
    orchestrator = DataCollectionOrchestrator()
    
    try:
        # Initialize everything
        await orchestrator.initialize()
        
        # Setup signal handlers for graceful shutdown
        orchestrator.setup_signal_handlers()
        
        # Run initial route discovery
        await orchestrator.discover_initial_routes()
        
        # Start continuous collection
        logger.info("=== Berlin Transport Data Collection Started ===")
        await orchestrator.start_collection()
        
    except KeyboardInterrupt:
        logger.info("Data collection stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in data collection: {e}")
        sys.exit(1)
    finally:
        await orchestrator.close()

if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('/app/logs', exist_ok=True)
    
    # Run the orchestrator
    asyncio.run(main())