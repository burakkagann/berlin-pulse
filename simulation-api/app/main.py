"""
Berlin Transport Simulation API
FastAPI application for serving historical transport simulation data
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from .core.config import settings
from .core.database import database
from .routes import simulation, transport, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    await database.connect()
    yield
    # Shutdown
    await database.disconnect()


app = FastAPI(
    title="Berlin Transport Simulation API",
    description="API for historical Berlin transport data simulation and visualization",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(simulation.router, prefix="/api/v1", tags=["simulation"])
app.include_router(transport.router, prefix="/api/v1", tags=["transport"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Berlin Transport Simulation API",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs"
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )