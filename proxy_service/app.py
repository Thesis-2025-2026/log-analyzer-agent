"""
FastAPI application for the Proxy/Dispatcher service.
Provides service registration, discovery, and health monitoring.
"""
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from proxy_service.config import config
from proxy_service.registry import registry
from proxy_service.models import (
    ServiceRegistration,
    ServiceInfo,
    ServiceListResponse,
    ServiceDiscoveryResponse,
    HeartbeatResponse,
    RegistrationResponse,
    ErrorResponse,
    HealthResponse,
    ServiceStatus,
)
from proxy_service.trace_api import router as trace_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Proxy/Dispatcher service starting...")
    logger.info(f"Service timeout: {config.SERVICE_TIMEOUT_SECONDS}s")
    logger.info(f"Heartbeat interval: {config.HEARTBEAT_INTERVAL_SECONDS}s")
    yield
    logger.info("Proxy/Dispatcher service shutting down...")


app = FastAPI(
    title="Proxy/Dispatcher Service",
    description="Service discovery and registration for distributed agent clusters",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(trace_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Check proxy service health and get registry statistics.
    """
    return HealthResponse(
        status="healthy",
        service="proxy",
        registered_services=registry.service_count,
        healthy_services=registry.healthy_count,
        timestamp=datetime.utcnow()
    )


@app.post(
    "/register",
    response_model=RegistrationResponse,
    responses={400: {"model": ErrorResponse}},
    tags=["Registration"]
)
async def register_service(registration: ServiceRegistration):
    """
    Register a new service with the proxy.
    
    If a service with the same name already exists, it will be updated.
    """
    try:
        service_info = registry.register(registration)
        return RegistrationResponse(
            success=True,
            service_name=service_info.name,
            message=f"Service '{service_info.name}' registered successfully"
        )
    except Exception as e:
        logger.error(f"Failed to register service: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete(
    "/services/{service_name}",
    response_model=RegistrationResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["Registration"]
)
async def unregister_service(service_name: str):
    """
    Unregister a service from the proxy.
    """
    if registry.unregister(service_name):
        return RegistrationResponse(
            success=True,
            service_name=service_name,
            message=f"Service '{service_name}' unregistered successfully"
        )
    raise HTTPException(
        status_code=404,
        detail=f"Service '{service_name}' not found"
    )


@app.post(
    "/services/{service_name}/heartbeat",
    response_model=HeartbeatResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["Health"]
)
async def service_heartbeat(service_name: str):
    """
    Record a heartbeat from a service.
    
    Services should send heartbeats periodically to indicate they are still alive.
    """
    service_info = registry.heartbeat(service_name)
    if service_info:
        return HeartbeatResponse(
            service_name=service_name,
            status=service_info.status,
            last_heartbeat=service_info.last_heartbeat,
            message="Heartbeat received"
        )
    raise HTTPException(
        status_code=404,
        detail=f"Service '{service_name}' not found. Please register first."
    )


@app.get(
    "/services",
    response_model=ServiceListResponse,
    tags=["Discovery"]
)
async def list_services(
    healthy_only: bool = Query(False, description="Only return healthy services")
):
    """
    List all registered services.
    
    Optionally filter to only return healthy services.
    """
    if healthy_only:
        services = registry.get_healthy_services()
    else:
        services = registry.list_services()
    
    return ServiceListResponse(
        services=services,
        count=len(services)
    )


@app.get(
    "/services/{service_name}",
    response_model=ServiceInfo,
    responses={404: {"model": ErrorResponse}},
    tags=["Discovery"]
)
async def get_service(service_name: str):
    """
    Get detailed information about a specific service.
    """
    service_info = registry.get_service(service_name)
    if service_info:
        return service_info
    raise HTTPException(
        status_code=404,
        detail=f"Service '{service_name}' not found"
    )


@app.get(
    "/discover",
    response_model=ServiceDiscoveryResponse,
    tags=["Discovery"]
)
async def discover_services(
    capability: Optional[str] = Query(None, description="Filter by capability")
):
    """
    Discover services, optionally filtering by capability.
    
    If no capability is specified, returns all healthy services.
    """
    if capability:
        services = registry.discover_by_capability(capability)
    else:
        services = registry.get_healthy_services()
    
    return ServiceDiscoveryResponse(
        capability=capability,
        services=services,
        count=len(services)
    )


@app.post("/cleanup", tags=["Maintenance"])
async def cleanup_services():
    """
    Remove services that have been unhealthy for too long.
    
    This endpoint can be called periodically to clean up stale registrations.
    """
    removed = registry.cleanup_unhealthy_services()
    return {
        "removed_services": removed,
        "count": len(removed),
        "message": f"Removed {len(removed)} stale service(s)"
    }


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app."""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "proxy_service.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=True
    )
