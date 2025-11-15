"""
Health Check Tool for pinging associated services to determine which are alive or dead.
"""
import requests
from typing import Dict, Any
import socket
from urllib.parse import urlparse


def check_service_health(service_url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Check if a service is alive by pinging its health endpoint or base URL.
    
    This tool attempts to connect to a service and determine its health status.
    It tries both HTTP health endpoints and basic connectivity checks.
    
    Args:
        service_url: The URL of the service to check (e.g., 'http://localhost:8000' or 'http://api.example.com/health')
        timeout: Connection timeout in seconds (default: 5)
    
    Returns:
        A dictionary containing:
        - status: 'alive', 'dead', or 'unknown'
        - response_time_ms: Response time in milliseconds (if available)
        - status_code: HTTP status code (if HTTP request succeeded)
        - error: Error message (if check failed)
    """
    try:
        # Parse URL
        parsed = urlparse(service_url)
        if not parsed.scheme:
            service_url = f"http://{service_url}"
            parsed = urlparse(service_url)
        
        # Try health endpoint first
        health_endpoints = [
            f"{service_url}/health",
            f"{service_url}/healthz",
            f"{service_url}/ping",
            service_url  # Fallback to base URL
        ]
        
        for endpoint in health_endpoints:
            try:
                import time
                start_time = time.time()
                response = requests.get(endpoint, timeout=timeout, allow_redirects=True)
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code < 500:
                    return {
                        "status": "alive",
                        "response_time_ms": response_time_ms,
                        "status_code": response.status_code,
                        "endpoint": endpoint
                    }
            except requests.exceptions.RequestException:
                continue
        
        # If HTTP failed, try basic socket connection
        host = parsed.hostname or parsed.path.split('/')[0]
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return {
                    "status": "alive",
                    "note": "Port is open but HTTP health check failed",
                    "host": host,
                    "port": port
                }
        except Exception:
            pass
        
        return {
            "status": "dead",
            "error": "Service did not respond to health checks or connection attempts"
        }
    
    except Exception as e:
        return {
            "status": "unknown",
            "error": f"Health check failed: {str(e)}"
        }

