"""
Service Registry for tracking registered services.
Thread-safe implementation with automatic health monitoring.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from proxy_service.models import ServiceInfo, ServiceRegistration, ServiceStatus
from proxy_service.config import config

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Thread-safe service registry for managing service registrations.
    
    Features:
    - Register and unregister services
    - Track service health via heartbeats
    - Automatic status updates based on heartbeat timeout
    - Service discovery by name or capability
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceInfo] = {}
        self._lock = threading.RLock()
        self._timeout_seconds = config.SERVICE_TIMEOUT_SECONDS
    
    def register(self, registration: ServiceRegistration) -> ServiceInfo:
        """
        Register a new service or update existing registration.
        
        Args:
            registration: Service registration details
            
        Returns:
            ServiceInfo object for the registered service
        """
        with self._lock:
            now = datetime.utcnow()
            
            if registration.name in self._services:
                # Update existing registration
                existing = self._services[registration.name]
                service_info = ServiceInfo(
                    name=registration.name,
                    url=registration.url,
                    capabilities=registration.capabilities,
                    version=registration.version or "1.0.0",
                    description=registration.description,
                    status=ServiceStatus.HEALTHY,
                    registered_at=existing.registered_at,
                    last_heartbeat=now,
                    heartbeat_count=existing.heartbeat_count + 1
                )
                logger.info(f"Updated service registration: {registration.name}")
            else:
                # New registration
                service_info = ServiceInfo(
                    name=registration.name,
                    url=registration.url,
                    capabilities=registration.capabilities,
                    version=registration.version or "1.0.0",
                    description=registration.description,
                    status=ServiceStatus.HEALTHY,
                    registered_at=now,
                    last_heartbeat=now,
                    heartbeat_count=1
                )
                logger.info(f"New service registered: {registration.name} at {registration.url}")
            
            self._services[registration.name] = service_info
            return service_info
    
    def unregister(self, service_name: str) -> bool:
        """
        Unregister a service.
        
        Args:
            service_name: Name of the service to unregister
            
        Returns:
            True if service was unregistered, False if not found
        """
        with self._lock:
            if service_name in self._services:
                del self._services[service_name]
                logger.info(f"Service unregistered: {service_name}")
                return True
            return False
    
    def heartbeat(self, service_name: str) -> Optional[ServiceInfo]:
        """
        Record a heartbeat for a service.
        
        Args:
            service_name: Name of the service sending heartbeat
            
        Returns:
            Updated ServiceInfo or None if service not found
        """
        with self._lock:
            if service_name not in self._services:
                return None
            
            service = self._services[service_name]
            updated = ServiceInfo(
                name=service.name,
                url=service.url,
                capabilities=service.capabilities,
                version=service.version,
                description=service.description,
                status=ServiceStatus.HEALTHY,
                registered_at=service.registered_at,
                last_heartbeat=datetime.utcnow(),
                heartbeat_count=service.heartbeat_count + 1
            )
            self._services[service_name] = updated
            logger.debug(f"Heartbeat received from: {service_name}")
            return updated
    
    def get_service(self, service_name: str) -> Optional[ServiceInfo]:
        """
        Get information about a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            ServiceInfo or None if not found
        """
        with self._lock:
            service = self._services.get(service_name)
            if service:
                return self._update_service_status(service)
            return None
    
    def list_services(self) -> List[ServiceInfo]:
        """
        List all registered services with updated status.
        
        Returns:
            List of all registered services
        """
        with self._lock:
            return [self._update_service_status(s) for s in self._services.values()]
    
    def discover_by_capability(self, capability: str) -> List[ServiceInfo]:
        """
        Find services that have a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of services with the requested capability
        """
        with self._lock:
            matching = []
            for service in self._services.values():
                if capability.lower() in [c.lower() for c in service.capabilities]:
                    matching.append(self._update_service_status(service))
            return matching
    
    def get_healthy_services(self) -> List[ServiceInfo]:
        """
        Get all services that are currently healthy.
        
        Returns:
            List of healthy services
        """
        with self._lock:
            healthy = []
            for service in self._services.values():
                updated = self._update_service_status(service)
                if updated.status == ServiceStatus.HEALTHY:
                    healthy.append(updated)
            return healthy
    
    def _update_service_status(self, service: ServiceInfo) -> ServiceInfo:
        """
        Update service status based on last heartbeat time.
        
        Args:
            service: Service to check
            
        Returns:
            ServiceInfo with updated status
        """
        now = datetime.utcnow()
        time_since_heartbeat = now - service.last_heartbeat
        
        if time_since_heartbeat > timedelta(seconds=self._timeout_seconds):
            status = ServiceStatus.UNHEALTHY
        else:
            status = ServiceStatus.HEALTHY
        
        if status != service.status:
            # Update the stored service status
            updated = ServiceInfo(
                name=service.name,
                url=service.url,
                capabilities=service.capabilities,
                version=service.version,
                description=service.description,
                status=status,
                registered_at=service.registered_at,
                last_heartbeat=service.last_heartbeat,
                heartbeat_count=service.heartbeat_count
            )
            self._services[service.name] = updated
            return updated
        
        return service
    
    def cleanup_unhealthy_services(self) -> List[str]:
        """
        Remove services that have been unhealthy for too long.
        
        Returns:
            List of removed service names
        """
        with self._lock:
            removed = []
            now = datetime.utcnow()
            
            for name, service in list(self._services.items()):
                time_since_heartbeat = now - service.last_heartbeat
                # Remove if no heartbeat for 3x the timeout period
                if time_since_heartbeat > timedelta(seconds=self._timeout_seconds * 3):
                    del self._services[name]
                    removed.append(name)
                    logger.warning(f"Service removed due to timeout: {name}")
            
            return removed
    
    @property
    def service_count(self) -> int:
        """Get total number of registered services."""
        with self._lock:
            return len(self._services)
    
    @property
    def healthy_count(self) -> int:
        """Get number of healthy services."""
        return len(self.get_healthy_services())


# Global registry instance
registry = ServiceRegistry()

