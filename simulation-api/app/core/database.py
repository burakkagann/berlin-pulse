"""
Database connection management for simulation API
"""

import asyncpg
import logging
from typing import Optional
from .config import settings

logger = logging.getLogger(__name__)


class Database:
    """Async database connection manager"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=1,
                max_size=settings.DATABASE_POOL_SIZE,
                max_inactive_connection_lifetime=300,
                command_timeout=settings.QUERY_TIMEOUT_SECONDS
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def execute_query(self, query: str, *args):
        """Execute a query and return results"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            try:
                return await connection.fetch(query, *args)
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                logger.error(f"Query: {query}")
                logger.error(f"Args: {args}")
                raise
    
    async def execute_single(self, query: str, *args):
        """Execute a query and return single result"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            try:
                return await connection.fetchrow(query, *args)
            except Exception as e:
                logger.error(f"Single query execution failed: {e}")
                raise


# Global database instance
database = Database()