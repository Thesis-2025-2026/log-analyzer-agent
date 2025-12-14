"""
Configuration for the Proxy/Dispatcher service.
"""
import os
from typing import Optional


class ProxyConfig:
    """Configuration settings for the proxy service."""
    
    # Server settings
    HOST: str = os.getenv("PROXY_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PROXY_PORT", "8000"))
    
    # Service registry settings
    HEARTBEAT_INTERVAL_SECONDS: int = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
    SERVICE_TIMEOUT_SECONDS: int = int(os.getenv("SERVICE_TIMEOUT", "90"))
    
    # Health check settings
    HEALTH_CHECK_ENABLED: bool = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


config = ProxyConfig()

