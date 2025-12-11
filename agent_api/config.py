"""
Configuration for the Agent API service.
"""
import os
from typing import List, Optional


class ServiceConfig:
    """Configuration settings for the agent service."""
    
    # Service identity
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "default-service")
    SERVICE_URL: str = os.getenv("SERVICE_URL", "http://localhost:8000")
    SERVICE_VERSION: str = os.getenv("SERVICE_VERSION", "1.0.0")
    SERVICE_DESCRIPTION: str = os.getenv("SERVICE_DESCRIPTION", "Agent Analysis Service")
    
    # Service capabilities (comma-separated in env)
    @property
    def capabilities(self) -> List[str]:
        caps = os.getenv("SERVICE_CAPABILITIES", "log-analysis")
        return [c.strip() for c in caps.split(",") if c.strip()]
    
    # Proxy settings
    PROXY_URL: Optional[str] = os.getenv("PROXY_URL", None)
    PROXY_ENABLED: bool = os.getenv("PROXY_ENABLED", "true").lower() == "true"
    
    # Heartbeat settings
    HEARTBEAT_INTERVAL_SECONDS: int = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
    REGISTRATION_RETRY_SECONDS: int = int(os.getenv("REGISTRATION_RETRY", "10"))
    
    # Database settings (service-specific)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/logs_db"
    )
    
    # Qdrant settings (service-specific)
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "log_fixes")
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


service_config = ServiceConfig()

