# Latest Agent System Overview

This document is the current, implementation-aligned overview of the Log Analyzer Agent System.

## System Purpose

The system analyzes operational logs with LLM-powered agents, augments findings with internal historical context, and supports cross-service reasoning in a distributed deployment.

## Core Runtime Components

- `agent_api` (Flask): primary API, report management, and web UI serving.
- `agent_system` (CAMEL-based): Main Agent workflow + Internal Knowledge Agent + tools.
- `proxy_service` (FastAPI): service registry/discovery and distributed trace ingestion.
- `detector`: Redis subscriber that filters logs and emits anomalies.
- `connect_to_detector`: anomaly consumer that forwards anomalies to `POST /api/query`.

## Main Analysis Flow

1. Request arrives at `POST /api/query`.
2. API establishes trace context (`trace_id`, parent event context).
3. Main Agent workflow runs:
   - local understanding and synthesis
   - optional internal knowledge lookup (SQL + RAG)
   - optional cross-service querying through proxy
4. Report may be persisted (`persist_report=true` by default).
5. Trace/report references are returned.

## API Contract (Current)

### Main query endpoint

- `POST /api/query`
  - request fields:
    - `query` (required string)
    - `trace_id` (optional, auto-generated if missing)
    - `parent_event_id` (optional)
    - `visited_services` (optional list)
    - `persist_report` (optional bool, default `true`)
    - `response_mode` (optional string, default `"user"`)
  - response fields include:
    - `reply`
    - `agent` (`main_agent`)
    - `duration_ms`
    - `trace_id`
    - `report_id` (nullable)

### Cross-service endpoint

- `POST /api/query-service/{service_name}`
  - used for service-to-service calls via proxy metadata.

### Report and trace endpoints

- `GET /api/reports`
- `GET /api/reports/count`
- `GET /api/reports/{id}`
- `DELETE /api/reports/{id}`
- `POST /api/reports/{id}/memory`
- `GET /api/reports/{id}/events`
- `GET /api/traces/agent-calls/{id}`
- `GET /api/traces/tool-calls/{id}`
- `GET /api/traces/http-calls/{id}`

## Tools and Coordination

Main Agent tools include:

- `query_internal_knowledge`: delegates to Internal Knowledge Agent.
- `check_service_health`: runtime service liveness checks.
- `discover_services`: proxy discovery for healthy services/capabilities.
- `get_service_report`: remote service query with cycle prevention.

## Detector Pipeline

Detector-based path is active in distributed mode:

1. `detector.detector` subscribes to `LOGS_CHANNEL`.
2. Every log is archived to Postgres.
3. Matching anomalies are pushed to `ANOM_CHANNEL` and queue.
4. `agent_system.connect_to_detector` consumes anomalies and submits to `POST /api/query`.

## Distributed Tracing

Tracing is emitted from agent runtime to proxy endpoints:

- `POST /traces/init`
- `POST /traces/events`
- `PATCH /traces/events/{entry_id}`
- `GET /traces/{trace_id}`

Trace events include agent calls, tool calls, and HTTP calls for cross-service observability.

## Configuration Highlights

- Query behavior:
  - `CROSS_SERVICE_TIMEOUT`
  - `AGENT_RATE_LIMIT_BASE_SLEEP_SECONDS`
  - `AGENT_RATE_LIMIT_MAX_SLEEP_SECONDS`
- Proxy integration:
  - `PROXY_URL`
  - `PROXY_ENABLED`
- Detector/streaming:
  - `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
  - `LOGS_CHANNEL`, `ANOM_CHANNEL`

## Thesis Context

For thesis writing, this component provides:

- **Agentic reasoning model**: single-orchestrator (Main Agent) with tool delegation.
- **Knowledge augmentation**: SQL + vector retrieval fusion inside incident analysis.
- **Cross-service dependency reasoning**: service discovery + remote report calls.
- **Observability artifact**: trace graph over agent/tool/http operations.
- **Operational mode comparison**: direct API path vs detector-driven asynchronous path.

### Validity Notes

- LLM output quality and latency depend on selected model/backend.
- Distributed trace completeness depends on proxy availability and trace emission success.
- Cross-service analysis quality depends on registration health and timeout settings.
