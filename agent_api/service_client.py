"""
Client for communicating with the Proxy/Dispatcher service.
"""
import logging
import requests
from typing import Optional, List, Dict, Any

from agent_api.config import service_config

logger = logging.getLogger(__name__)


class ProxyClient:
    """
    Client for interacting with the Proxy/Dispatcher service.
    
    Provides methods for:
    - Service registration
    - Heartbeat sending
    - Service discovery
    - Cross-service communication
    """
    
    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url or service_config.PROXY_URL
        self._timeout = 10  # seconds
    
    @property
    def is_configured(self) -> bool:
        """Check if proxy URL is configured."""
        return bool(self.proxy_url) and service_config.PROXY_ENABLED
    
    def register(
        self,
        name: str = None,
        url: str = None,
        capabilities: List[str] = None,
        version: str = None,
        description: str = None
    ) -> bool:
        """
        Register this service with the proxy.
        
        Args:
            name: Service name (default: from config)
            url: Service URL (default: from config)
            capabilities: List of capabilities (default: from config)
            version: Service version (default: from config)
            description: Service description (default: from config)
            
        Returns:
            True if registration succeeded, False otherwise
        """
        if not self.is_configured:
            logger.warning("Proxy not configured, skipping registration")
            return False
        
        registration_data = {
            "name": name or service_config.SERVICE_NAME,
            "url": url or service_config.SERVICE_URL,
            "capabilities": capabilities or service_config.capabilities,
            "version": version or service_config.SERVICE_VERSION,
            "description": description or service_config.SERVICE_DESCRIPTION,
        }
        
        try:
            response = requests.post(
                f"{self.proxy_url}/register",
                json=registration_data,
                timeout=self._timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully registered with proxy: {registration_data['name']}")
                return True
            else:
                logger.error(f"Registration failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to proxy for registration: {e}")
            return False
    
    def unregister(self, service_name: str = None) -> bool:
        """
        Unregister this service from the proxy.
        
        Args:
            service_name: Service name (default: from config)
            
        Returns:
            True if unregistration succeeded, False otherwise
        """
        if not self.is_configured:
            return False
        
        name = service_name or service_config.SERVICE_NAME
        
        try:
            response = requests.delete(
                f"{self.proxy_url}/services/{name}",
                timeout=self._timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully unregistered from proxy: {name}")
                return True
            else:
                logger.warning(f"Unregistration failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to unregister from proxy: {e}")
            return False
    
    def heartbeat(self, service_name: str = None) -> bool:
        """
        Send a heartbeat to the proxy.
        
        Args:
            service_name: Service name (default: from config)
            
        Returns:
            True if heartbeat succeeded, False otherwise
        """
        if not self.is_configured:
            return False
        
        name = service_name or service_config.SERVICE_NAME
        
        try:
            response = requests.post(
                f"{self.proxy_url}/services/{name}/heartbeat",
                timeout=self._timeout
            )
            
            if response.status_code == 200:
                logger.debug(f"Heartbeat sent successfully: {name}")
                return True
            elif response.status_code == 404:
                # Service not found, try to re-register
                logger.warning(f"Service not found in proxy, attempting re-registration")
                return self.register()
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False
    
    def discover_services(self, capability: str = None) -> List[Dict[str, Any]]:
        """
        Discover available services from the proxy.
        
        Args:
            capability: Optional capability filter
            
        Returns:
            List of service information dictionaries
        """
        if not self.is_configured:
            logger.warning("Proxy not configured, cannot discover services")
            return []
        
        try:
            params = {}
            if capability:
                params["capability"] = capability
            
            response = requests.get(
                f"{self.proxy_url}/discover",
                params=params,
                timeout=self._timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("services", [])
            else:
                logger.error(f"Service discovery failed: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to discover services: {e}")
            return []
    
    def get_service(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific service.
        
        Args:
            service_name: Name of the service to look up
            
        Returns:
            Service information dict or None if not found
        """
        if not self.is_configured:
            return None
        
        try:
            response = requests.get(
                f"{self.proxy_url}/services/{service_name}",
                timeout=self._timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get service info: {e}")
            return None
    
    def list_all_services(self, healthy_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all registered services.
        
        Args:
            healthy_only: If True, only return healthy services
            
        Returns:
            List of service information dictionaries
        """
        if not self.is_configured:
            return []
        
        try:
            response = requests.get(
                f"{self.proxy_url}/services",
                params={"healthy_only": healthy_only},
                timeout=self._timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("services", [])
            else:
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list services: {e}")
            return []
    
    def query_service(
        self,
        service_name: str,
        query: str,
        timeout: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Query another service's agent for analysis.
        
        Args:
            service_name: Name of the target service
            query: The query/log data to analyze
            timeout: Request timeout in seconds
            
        Returns:
            Response from the target service or None on failure
        """
        # First, discover the service URL
        service_info = self.get_service(service_name)
        if not service_info:
            logger.error(f"Service not found: {service_name}")
            return None
        
        service_url = service_info.get("url")
        if not service_url:
            logger.error(f"Service URL not available: {service_name}")
            return None
        
        # Query the service directly
        try:
            response = requests.post(
                f"{service_url}/api/query",
                json={"query": query},
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Service query failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to query service {service_name}: {e}")
            return None


# Global proxy client instance
proxy_client = ProxyClient()

