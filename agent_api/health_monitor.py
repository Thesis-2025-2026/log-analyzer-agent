"""
Health monitoring and heartbeat management for the Agent API service.
"""
import asyncio
import logging
import threading
from typing import Optional

from agent_api.config import service_config
from agent_api.service_client import proxy_client

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Manages service health monitoring and heartbeat sending.
    
    Runs a background task that periodically sends heartbeats to the proxy
    to indicate that this service is still alive.
    """
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
        self._interval = service_config.HEARTBEAT_INTERVAL_SECONDS
    
    async def start_async(self):
        """Start the heartbeat task asynchronously."""
        if self._running:
            logger.warning("Health monitor already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Health monitor started (interval: {self._interval}s)")
    
    def start_threaded(self):
        """Start the heartbeat task in a background thread."""
        if self._running:
            logger.warning("Health monitor already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop_sync, daemon=True)
        self._thread.start()
        logger.info(f"Health monitor started in thread (interval: {self._interval}s)")
    
    async def stop_async(self):
        """Stop the heartbeat task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor stopped")
    
    def stop(self):
        """Stop the heartbeat task (sync version)."""
        self._running = False
        logger.info("Health monitor stopped")
    
    async def _heartbeat_loop(self):
        """Async loop that sends periodic heartbeats."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if self._running:
                    self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    def _heartbeat_loop_sync(self):
        """Sync loop that sends periodic heartbeats (for threaded mode)."""
        import time
        while self._running:
            try:
                time.sleep(self._interval)
                if self._running:
                    self._send_heartbeat()
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    def _send_heartbeat(self):
        """Send a single heartbeat to the proxy."""
        try:
            success = proxy_client.heartbeat()
            if not success:
                logger.warning("Failed to send heartbeat")
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")


# Global health monitor instance
health_monitor = HealthMonitor()


def register_with_proxy(max_retries: int = 3) -> bool:
    """
    Register this service with the proxy.
    
    Args:
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if registration succeeded, False otherwise
    """
    if not proxy_client.is_configured:
        logger.info("Proxy not configured, skipping registration")
        return False
    
    import time
    retry_interval = service_config.REGISTRATION_RETRY_SECONDS
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"Attempting to register with proxy (attempt {attempt}/{max_retries})")
        
        if proxy_client.register():
            return True
        
        if attempt < max_retries:
            logger.info(f"Registration failed, retrying in {retry_interval}s...")
            time.sleep(retry_interval)
    
    logger.error(f"Failed to register with proxy after {max_retries} attempts")
    return False


def unregister_from_proxy() -> bool:
    """
    Unregister this service from the proxy.
    
    Returns:
        True if unregistration succeeded, False otherwise
    """
    if not proxy_client.is_configured:
        return False
    
    return proxy_client.unregister()

