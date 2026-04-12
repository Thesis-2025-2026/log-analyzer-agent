# Documentation Gap Checklist (Verified)

This checklist records verified mismatches between documentation and the current implementation, and it is intended as a maintenance baseline for thesis writing.

## Verified on

- Date: 2026-04-06
- Scope:
  - `docs/AGENT_SYSTEM_OVERVIEW.md`
  - `docs/DISTRIBUTED_DEPLOYMENT.md`
  - `README.md`

## Gaps Found

### 1) Distributed topology drift

- Docs mostly describe a 2-service setup (payment + order).
- Runtime compose defines 5 service clusters:
  - `payment-service`
  - `order-service`
  - `auth-service`
  - `deployments-service`
  - `idp-service`
- Each cluster also includes detector and anomaly-consumer workers in distributed mode.

Reference:
- `docker-compose.distributed.yml`

### 2) Missing detector/anomaly pipeline

- Existing docs under-describe the Redis-driven ingestion path:
  - detector subscribes to `LOGS_CHANNEL`
  - detector archives logs and publishes anomalies
  - consumer subscribes to anomaly channel and invokes `/api/query`

References:
- `detector/detector.py`
- `agent_system/connect_to_detector.py`

### 3) Tracing model not fully documented

- System supports distributed tracing with proxy-backed trace persistence:
  - `/traces/init`
  - `/traces/events`
  - `/traces/{trace_id}`
  - detail endpoints for agent/tool/http calls
- Existing docs do not clearly explain trace DB and proxy trace APIs.

References:
- `proxy_service/trace_api.py`
- `agent_system/core/tracing.py`
- `docker-compose.distributed.yml` (`proxy-trace-postgres`)

### 4) API behavior drift in query/report endpoints

- `POST /api/query` supports and defaults behavior for:
  - `trace_id`
  - `parent_event_id`
  - `persist_report` (defaults to `true`)
  - `response_mode` (defaults to `"user"`)
- Docs do not fully cover trace/report endpoints:
  - `GET /api/reports/count`
  - `POST /api/reports/{id}/memory`
  - `DELETE /api/reports/{id}`
  - `GET /api/reports/{id}/events`
  - `GET /api/traces/...`

Reference:
- `agent_api/app.py`

### 5) Framework label mismatch

- `README.md` labels `agent_api` as FastAPI in project structure.
- Runtime `agent_api` is Flask.

Reference:
- `agent_api/app.py`

## Resulting action

- New "latest" docs are added to represent the current architecture and runtime behavior:
  - `docs/LATEST_AGENT_SYSTEM_OVERVIEW.md`
  - `docs/LATEST_DISTRIBUTED_DEPLOYMENT.md`
- Existing legacy docs are retained for historical context but explicitly marked as legacy.
