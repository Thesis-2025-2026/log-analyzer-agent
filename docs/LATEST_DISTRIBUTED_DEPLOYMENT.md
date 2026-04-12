# Latest Distributed Deployment Guide

This guide reflects the current distributed deployment layout in `docker-compose.distributed.yml`.

## Topology

- 1 shared Redis instance
- 1 proxy service (`proxy`) for registry/discovery
- 1 proxy trace database (`proxy-trace-postgres`)
- 5 service clusters:
  - payment
  - order
  - auth
  - deployments
  - idp

Each service cluster includes:

- API container (`service-*-api`)
- Postgres container (`service-*-postgres`)
- Qdrant container (`service-*-qdrant`)
- Detector worker (`service-*-detector`)
- Anomaly consumer (`service-*-consumer`)

## Data and Control Paths

### Control plane

- APIs register with proxy.
- Proxy provides discovery (`/discover`) and service metadata (`/services/{name}`).

### Data plane (streaming)

1. Logs arrive to Redis service-specific channels (for example `logs:auth`).
2. Detector subscribes to `LOGS_CHANNEL` and applies filters.
3. Flagged records are published to `ANOM_CHANNEL` and anomaly queue.
4. Consumer reads anomalies and invokes local API `POST /api/query`.

### Data plane (request/response)

- Service APIs can call other services through proxy-discovered addresses using `POST /api/query-service/{service_name}`.

### Tracing plane

- All services can emit distributed trace events to proxy:
  - `/traces/init`
  - `/traces/events`
  - `/traces/{trace_id}`
- Proxy persists trace data in `proxy-trace-postgres`.

## Quick Start

```bash
docker compose -f docker-compose.distributed.yml up -d
docker compose -f docker-compose.distributed.yml ps
```

## Service Ports

- Proxy: `8000`
- Payment API: `8001`
- Order API: `8002`
- Auth API: `8003`
- Deployments API: `8004`
- IdP API: `8005`

## Verification Commands

```bash
# Proxy health and registered services
curl http://localhost:8000/health
curl http://localhost:8000/services

# Service health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health

# Trace API probe
curl http://localhost:8000/traces/nonexistent-trace-id
```

## Important Runtime Endpoints

### Proxy service

- `GET /health`
- `POST /register`
- `GET /services`
- `GET /services/{service_name}`
- `POST /services/{service_name}/heartbeat`
- `DELETE /services/{service_name}`
- `GET /discover?capability=...`
- `POST /cleanup`
- `GET /services/{service_name}/queue`
- `GET /services/{service_name}/reports`
- `GET /services/{service_name}/reports/count`
- `POST /traces/init`
- `POST /traces/events`
- `PATCH /traces/events/{entry_id}`
- `GET /traces/{trace_id}`

### Agent API service

- `GET /health`
- `GET /api/service-info`
- `POST /api/query`
- `POST /api/query-service/{service_name}`
- `GET /api/discover-services`
- `GET /api/reports`
- `GET /api/reports/count`
- `GET /api/reports/{id}`
- `DELETE /api/reports/{id}`
- `POST /api/reports/{id}/memory`
- `GET /api/reports/{id}/events`

## Environment Contract (Distributed Mode)

- Required global:
  - `OPENAI_API_KEY` (if using OpenAI-backed model/provider)
- Shared infra:
  - `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- Service identity:
  - `SERVICE_NAME`, `SERVICE_URL`, `SERVICE_CAPABILITIES`
- Service storage:
  - `DATABASE_URL`, `QDRANT_URL`, `QDRANT_COLLECTION`
- Proxy:
  - `PROXY_URL`, `PROXY_ENABLED`, `HEARTBEAT_INTERVAL`
- Streaming channels:
  - `LOGS_CHANNEL`, `ANOM_CHANNEL`

## Thesis Context

This deployment is suitable for thesis evaluation when you need:

- **Service isolation experiments**: independent DB/vector stores per service.
- **Cross-service diagnosis experiments**: compare local-only vs federated analysis.
- **Pipeline latency experiments**: detector/anomaly/API stages as separate timing points.
- **Trace-based explainability**: reconstruct decision flow with proxy trace data.

### Threats to validity

- Synthetic workloads may not capture real production entropy.
- Service health and registration churn can affect cross-service completeness.
- Queue/channel configuration mismatches can silently reduce anomaly coverage.
