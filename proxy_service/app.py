"""
FastAPI application for the Proxy/Dispatcher service.
Provides service registration, discovery, and health monitoring.
"""
from contextlib import asynccontextmanager
from datetime import datetime
import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import redis
import requests

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

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Service Registry</title>
    <style>
      :root {
        color-scheme: light;
      }
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #f3f4f6;
        color: #111827;
      }
      .page {
        max-width: 980px;
        margin: 0 auto;
        padding: 28px 20px 40px;
      }
      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 16px;
      }
      .title {
        font-size: 18px;
        font-weight: 600;
        margin: 0;
      }
      .subtitle {
        margin: 4px 0 0;
        font-size: 13px;
        color: #6b7280;
      }
      .actions {
        display: flex;
        gap: 8px;
      }
      button {
        border: 1px solid #d1d5db;
        background: #fff;
        padding: 8px 12px;
        border-radius: 10px;
        font-size: 12px;
        cursor: pointer;
      }
      button:hover {
        background: #f9fafb;
      }
      .card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
      }
      .grid {
        display: grid;
        gap: 12px;
      }
      .svc {
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 14px;
        display: grid;
        gap: 8px;
      }
      .svc-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      .btn {
        border: 1px solid #d1d5db;
        background: #fff;
        padding: 6px 12px;
        border-radius: 10px;
        font-size: 12px;
        color: #111827;
        text-decoration: none;
      }
      .btn:hover {
        background: #f9fafb;
      }
      .svc-name {
        font-weight: 600;
        font-size: 14px;
      }
      .section {
        margin-top: 6px;
        display: grid;
        gap: 6px;
      }
      .section-title {
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #6b7280;
        font-weight: 600;
      }
      .metrics {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }
      .metric {
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        border-radius: 12px;
        padding: 10px 12px;
      }
      .metric-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #6b7280;
        font-weight: 600;
      }
      .metric-value {
        margin-top: 4px;
        font-size: 18px;
        font-weight: 600;
        color: #111827;
      }
      .links {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .links a {
        font-size: 12px;
        color: #2563eb;
        text-decoration: none;
      }
      .links a:hover {
        text-decoration: underline;
      }
      .empty {
        text-align: center;
        font-size: 13px;
        color: #6b7280;
        padding: 30px 0;
      }
      .footer {
        margin-top: 18px;
        font-size: 11px;
        color: #6b7280;
      }
    </style>
  </head>
  <body>
    <div class="page">
      <div class="header">
        <div>
          <h1 class="title">Service Registry</h1>
          <p class="subtitle">Proxy at port 8000 • live service list</p>
        </div>
        <div class="actions">
          <button id="refreshBtn">Refresh</button>
        </div>
      </div>

      <div class="card">
        <div id="services" class="grid"></div>
        <div id="emptyState" class="empty" style="display:none;">No services registered yet.</div>
      </div>

      <div class="footer">
        Tip: Host URLs assume default ports (8001-8005). Adjust if your compose ports differ.
      </div>
    </div>

    <script>
      const HOST_PORT_MAP = {
        "payment-service": 8001,
        "order-service": 8002,
        "auth-service": 8003,
        "deployments-service": 8004,
        "idp-service": 8005
      };

      const servicesEl = document.getElementById("services");
      const emptyEl = document.getElementById("emptyState");
      const refreshBtn = document.getElementById("refreshBtn");

      const escapeHtml = (value) => String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");

      const serviceKey = (name) => String(name || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");

      const setMetric = (targetId, value, fallback) => {
        const el = document.getElementById(targetId);
        if (!el) return;
        el.textContent = value !== null && value !== undefined ? value : fallback;
      };

      const loadQueueCount = async (serviceName, targetId) => {
        try {
          const res = await fetch(`/services/${encodeURIComponent(serviceName)}/queue?limit=1`);
          if (!res.ok) throw new Error("queue fetch failed");
          const data = await res.json();
          setMetric(targetId, data.count ?? 0, "0");
        } catch (err) {
          setMetric(targetId, "—", "—");
        }
      };

      const loadReportCount = async (serviceName, targetId) => {
        try {
          const res = await fetch(`/services/${encodeURIComponent(serviceName)}/reports/count`);
          if (!res.ok) throw new Error("reports count failed");
          const data = await res.json();
          setMetric(targetId, data.count ?? 0, "0");
        } catch (err) {
          setMetric(targetId, "—", "—");
        }
      };

      const render = (services) => {
        servicesEl.innerHTML = "";
        if (!services.length) {
          emptyEl.style.display = "block";
          return;
        }
        emptyEl.style.display = "none";

        services.forEach((svc) => {
          const hostPort = HOST_PORT_MAP[svc.name];
          const hostUrl = hostPort ? `http://localhost:${hostPort}` : null;
          const uiUrl = hostUrl ? `${hostUrl}` : null;
          const key = serviceKey(svc.name);

          const item = document.createElement("div");
          item.className = "svc";
          item.innerHTML = `
            <div class="svc-head">
              <div class="svc-name">${svc.name}</div>
              ${uiUrl ? `<a class="btn" href="${uiUrl}" target="_blank">Open UI</a>` : ""}
            </div>
            <div class="section">
              <div class="section-title">Activity</div>
              <div class="metrics">
                <div class="metric">
                  <div class="metric-label">Queued</div>
                  <div class="metric-value" id="queue-${key}">—</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Reports</div>
                  <div class="metric-value" id="reports-${key}">—</div>
                </div>
              </div>
            </div>
          `;
          servicesEl.appendChild(item);
          loadQueueCount(svc.name, `queue-${key}`);
          loadReportCount(svc.name, `reports-${key}`);
        });
      };

      const loadServices = async () => {
        try {
          const res = await fetch("/services");
          const data = await res.json();
          render(data.services || []);
        } catch (err) {
          servicesEl.innerHTML = "<div class='empty'>Failed to load services.</div>";
        }
      };

      refreshBtn.addEventListener("click", loadServices);
      loadServices();
      setInterval(loadServices, 15000);
    </script>
  </body>
</html>
"""


def _queue_key_for_service(service_name: str) -> str:
    if service_name.endswith("-service"):
        slug = service_name[:-8]
    else:
        slug = service_name
    return f"anomalies:{slug}:queue"


def _service_url(service_name: str) -> str:
    service_info = registry.get_service(service_name)
    if not service_info:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found"
        )
    return service_info.url


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


@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def index():
    """Minimal service registry UI."""
    return HTMLResponse(INDEX_HTML)


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
    "/services/{service_name}/reports",
    tags=["UI"]
)
async def get_service_reports(
    service_name: str,
    limit: int = Query(5, ge=1, le=50),
    offset: int = Query(0, ge=0, le=1000),
):
    service_url = _service_url(service_name)
    try:
        resp = requests.get(
            f"{service_url}/api/reports",
            params={"limit": limit, "offset": offset},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach {service_name}: {exc}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    try:
        return resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from {service_name}")


@app.get(
    "/services/{service_name}/reports/count",
    tags=["UI"]
)
async def get_service_reports_count(service_name: str):
    service_url = _service_url(service_name)
    try:
        resp = requests.get(f"{service_url}/api/reports/count", timeout=5)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach {service_name}: {exc}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    try:
        return resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from {service_name}")


@app.get(
    "/services/{service_name}/queue",
    tags=["UI"]
)
async def get_service_queue(
    service_name: str,
    limit: int = Query(5, ge=1, le=50),
):
    _service_url(service_name)
    queue_key = _queue_key_for_service(service_name)
    try:
        raw_items = redis_client.lrange(queue_key, 0, limit - 1)
        count = redis_client.llen(queue_key)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")

    items = []
    for raw in raw_items:
        try:
            items.append(json.loads(raw))
        except Exception:
            items.append({"raw": raw})
    return {"items": items, "count": count}


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
