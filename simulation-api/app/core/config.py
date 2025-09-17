"""
Configuration management for simulation API
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://transport_user:transport_pass@postgres:5432/berlin_transport"
    )
    
    # API Settings
    PORT: int = int(os.getenv("PORT", "8081"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "*"  # Allow all origins for development
    ]
    
    # Simulation Settings
    DEFAULT_TIME_WINDOW_SECONDS: int = 30
    MAX_CHUNK_DURATION_MINUTES: int = 60
    DEFAULT_CHUNK_DURATION_MINUTES: int = 10
    MAX_VEHICLES_PER_REQUEST: int = 10000
    
    # Performance
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    QUERY_TIMEOUT_SECONDS: int = 30
    
    class Config:
        env_file = ".env"


settings = Settings()