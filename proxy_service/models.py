"""
Data models for the Proxy/Dispatcher service.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ServiceStatus(str, Enum):
    """Status of a registered service."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceRegistration(BaseModel):
    """Request model for service registration."""
    name: str = Field(..., description="Unique service identifier")
    url: str = Field(..., description="Base URL of the service API")
    capabilities: List[str] = Field(default_factory=list, description="List of service capabilities")
    version: Optional[str] = Field(default="1.0.0", description="Service version")
    description: Optional[str] = Field(default=None, description="Service description")


class ServiceInfo(BaseModel):
    """Complete information about a registered service."""
    name: str
    url: str
    capabilities: List[str]
    version: str
    description: Optional[str]
    status: ServiceStatus
    registered_at: datetime
    last_heartbeat: datetime
    heartbeat_count: int = 0


class ServiceListResponse(BaseModel):
    """Response model for listing services."""
    services: List[ServiceInfo]
    count: int


class ServiceDiscoveryResponse(BaseModel):
    """Response model for service discovery by capability."""
    capability: Optional[str]
    services: List[ServiceInfo]
    count: int


class HeartbeatResponse(BaseModel):
    """Response model for heartbeat acknowledgment."""
    service_name: str
    status: ServiceStatus
    last_heartbeat: datetime
    message: str = "Heartbeat received"


class RegistrationResponse(BaseModel):
    """Response model for service registration."""
    success: bool
    service_name: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str = "proxy"
    registered_services: int
    healthy_services: int
    timestamp: datetime

