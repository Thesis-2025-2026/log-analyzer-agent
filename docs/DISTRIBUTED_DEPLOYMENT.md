# Distributed Agent System Deployment Guide

This document describes how to deploy and use the distributed agent system with multiple service clusters and a central proxy/dispatcher for service discovery.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Distributed Architecture                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│                      ┌─────────────────────┐                          │
│                      │  Proxy/Dispatcher   │                          │
│                      │  (Service Registry) │                          │
│                      │    Port: 8000       │                          │
│                      └──────────┬──────────┘                          │
│                                 │                                      │
│               ┌─────────────────┼─────────────────┐                   │
│               │                 │                 │                   │
│    ┌──────────▼──────────┐     │     ┌──────────▼──────────┐        │
│    │   Service A Cluster │     │     │   Service B Cluster │        │
│    │   (payment-service) │     │     │   (order-service)   │        │
│    │     Port: 8001      │     │     │     Port: 8002      │        │
│    ├─────────────────────┤     │     ├─────────────────────┤        │
│    │  - Main Agent       │     │     │  - Main Agent       │        │
│    │  - Internal KB      │     │     │  - Internal KB      │        │
│    │  - PostgreSQL       │     │     │  - PostgreSQL       │        │
│    │  - Qdrant           │     │     │  - Qdrant           │        │
│    └─────────────────────┘     │     └─────────────────────┘        │
│                                 │                                      │
└─────────────────────────────────┴──────────────────────────────────────┘
```

## Key Benefits

### Environment Isolation
- Each service cluster operates in its own isolated environment
- Service-specific dependencies and configurations remain separate
- Prevents conflicts between different service requirements

### Data Privacy & Corporate Compliance
- Critical for corporate environments with strict data governance
- Teams can maintain control over their service's data
- No need to share sensitive information across team boundaries
- Meets compliance requirements for data isolation

### Robust Deployment
- Failure in one service cluster doesn't affect others
- Independent scaling based on service-specific load
- Each service can be updated or maintained independently

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- OpenAI API key (or other LLM provider configured)

### 1. Configure Environment

Create a `.env` file in the project root with your API keys:

```bash
# Create .env file
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

### 2. Start the Distributed System

```bash
# Start all services
docker-compose -f docker-compose.distributed.yml up -d

# Check status
docker-compose -f docker-compose.distributed.yml ps
```

### 3. Verify Services

```bash
# Check proxy health
curl http://localhost:8000/health

# Check Service A health
curl http://localhost:8001/health

# Check Service B health
curl http://localhost:8002/health

# List registered services
curl http://localhost:8000/services
```

### 4. Run Tests

Open and run the test notebook:
```bash
jupyter notebook test_distributed_system.ipynb
```

## Service Endpoints

### Proxy Service (Port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check and registry stats |
| `/register` | POST | Register a service |
| `/services` | GET | List all registered services |
| `/services/{name}` | GET | Get specific service details |
| `/services/{name}` | DELETE | Unregister a service |
| `/services/{name}/heartbeat` | POST | Send heartbeat |
| `/discover` | GET | Discover services (optional: ?capability=X) |
| `/cleanup` | POST | Remove stale services |

### Agent Service (Ports 8001, 8002)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health and info |
| `/api/service-info` | GET | Detailed service information |
| `/api/query` | POST | Submit log for analysis |
| `/api/discover-services` | GET | Discover other services via proxy |
| `/api/query-service/{name}` | POST | Query another service's agent |
| `/api/reports` | GET | List analysis reports |
| `/api/reports/{id}` | GET | Get specific report |

## Cross-Service Communication Flow

```
1. Service A receives error log for analysis
2. Service A's Main Agent analyzes locally
3. Main Agent calls discover_services() → Proxy returns available services
4. Main Agent identifies relevant services (e.g., order-service)
5. Main Agent calls get_service_report("order-service", error_context)
   → Proxy provides order-service URL
   → Direct request to order-service
   → order-service's Main Agent analyzes from its perspective
   → Returns report to Service A
6. Service A synthesizes all information:
   - Local analysis
   - Internal knowledge (historical context)
   - Cross-service reports
7. Final comprehensive report generated
```

## Configuration

### Service A Configuration (`config/service-a.env`)

```env
SERVICE_NAME=payment-service
SERVICE_URL=http://service-a-api:8000
SERVICE_CAPABILITIES=payment,billing,transaction,financial
PROXY_URL=http://proxy:8000
DATABASE_URL=postgresql://logs_user:logs_pass@service-a-postgres:5432/service_a_logs
QDRANT_URL=http://service-a-qdrant:6333
```

### Service B Configuration (`config/service-b.env`)

```env
SERVICE_NAME=order-service
SERVICE_URL=http://service-b-api:8000
SERVICE_CAPABILITIES=order,fulfillment,inventory,shipping
PROXY_URL=http://proxy:8000
DATABASE_URL=postgresql://logs_user:logs_pass@service-b-postgres:5432/service_b_logs
QDRANT_URL=http://service-b-qdrant:6333
```

## Main Agent Tools

The Main Agent has access to these tools for comprehensive analysis:

### Local Analysis Tools
- **check_service_health**: Ping services to verify health
- **query_internal_knowledge**: Query local database and RAG for historical context

### Cross-Service Tools
- **discover_services**: Query proxy for available services
- **get_service_report**: Get analysis from a specific service
- **gather_cross_service_reports**: Collect reports from multiple services

## Adding New Services

To add a new service (e.g., inventory-service):

1. **Create configuration file:**
```bash
# config/service-c.env
SERVICE_NAME=inventory-service
SERVICE_URL=http://service-c-api:8000
SERVICE_CAPABILITIES=inventory,stock,warehouse
PROXY_URL=http://proxy:8000
DATABASE_URL=postgresql://logs_user:logs_pass@service-c-postgres:5432/service_c_logs
QDRANT_URL=http://service-c-qdrant:6333
```

2. **Add to docker-compose.distributed.yml:**
```yaml
  service-c-postgres:
    image: postgres:15
    container_name: service-c-postgres
    environment:
      POSTGRES_USER: logs_user
      POSTGRES_PASSWORD: logs_pass
      POSTGRES_DB: service_c_logs
    volumes:
      - service-c-pg-data:/var/lib/postgresql/data
      - ./infra/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql:ro
    networks:
      - agent-network

  service-c-qdrant:
    image: qdrant/qdrant:latest
    container_name: service-c-qdrant
    volumes:
      - service-c-qdrant-data:/qdrant/storage
    networks:
      - agent-network

  service-c-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: service-c-api
    ports:
      - "8003:8000"
    env_file:
      - ./config/service-c.env
    depends_on:
      - proxy
      - service-c-postgres
      - service-c-qdrant
    networks:
      - agent-network

volumes:
  service-c-pg-data:
  service-c-qdrant-data:
```

3. **Restart the system:**
```bash
docker-compose -f docker-compose.distributed.yml up -d
```

## Scaling

### Horizontal Scaling (More Service Instances)

To run multiple instances of the same service type:

```bash
docker-compose -f docker-compose.distributed.yml up -d --scale service-a-api=3
```

### Vertical Scaling (More Resources)

Modify resource limits in docker-compose.distributed.yml:

```yaml
service-a-api:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
```

## Monitoring

### View Logs

```bash
# All services
docker-compose -f docker-compose.distributed.yml logs -f

# Specific service
docker-compose -f docker-compose.distributed.yml logs -f proxy
docker-compose -f docker-compose.distributed.yml logs -f service-a-api
docker-compose -f docker-compose.distributed.yml logs -f service-b-api
```

### Check Service Status

```bash
# Via proxy
curl http://localhost:8000/services | jq

# Check specific service
curl http://localhost:8000/services/payment-service | jq
```

## Troubleshooting

### Service Not Registering

1. Check if proxy is running:
```bash
curl http://localhost:8000/health
```

2. Check service logs:
```bash
docker-compose -f docker-compose.distributed.yml logs service-a-api
```

3. Verify PROXY_URL in service config:
```bash
docker exec service-a-api env | grep PROXY
```

### Cross-Service Communication Failing

1. Verify both services are registered:
```bash
curl http://localhost:8000/services
```

2. Check network connectivity:
```bash
docker exec service-a-api curl http://service-b-api:8000/health
```

3. Check service health status:
```bash
curl http://localhost:8000/services/order-service | jq '.status'
```

### Database Connection Issues

1. Check database is running:
```bash
docker-compose -f docker-compose.distributed.yml ps | grep postgres
```

2. Verify connection from service:
```bash
docker exec service-a-api python -c "
from agent_api.config import service_config
print(service_config.DATABASE_URL)
"
```

## Cleanup

### Stop Services

```bash
docker-compose -f docker-compose.distributed.yml down
```

### Stop and Remove Data

```bash
docker-compose -f docker-compose.distributed.yml down -v
```

### Remove All Docker Resources

```bash
docker-compose -f docker-compose.distributed.yml down -v --rmi all
```

## File Structure

```
log-analyzer-agent/
├── proxy_service/
│   ├── __init__.py
│   ├── app.py              # FastAPI proxy application
│   ├── models.py           # Pydantic models
│   ├── registry.py         # Service registry logic
│   ├── config.py           # Configuration
│   ├── requirements.txt    # Dependencies
│   └── Dockerfile          # Container definition
├── agent_api/
│   ├── app.py              # Flask API with registration
│   ├── config.py           # Service configuration
│   ├── service_client.py   # Proxy client
│   └── health_monitor.py   # Heartbeat management
├── agent_system/
│   ├── agents/
│   │   ├── main_agent/     # Main Agent with cross-service tools
│   │   └── internal_knowledge/
│   └── tools/
│       └── cross_service_tool.py  # Cross-service communication
├── config/
│   ├── service-a.env       # Service A configuration
│   ├── service-b.env       # Service B configuration
│   └── proxy.env           # Proxy configuration
├── docker-compose.distributed.yml
├── Dockerfile
└── test_distributed_system.ipynb
```

## API Examples

### Register a Service

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-service",
    "url": "http://localhost:9000",
    "capabilities": ["testing", "demo"],
    "version": "1.0.0"
  }'
```

### Query Service for Analysis

```bash
curl -X POST http://localhost:8001/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2025-01-14 10:00:00 [ERROR] Payment timeout"
  }'
```

### Discover Services by Capability

```bash
curl "http://localhost:8000/discover?capability=payment"
```

### Query Another Service

```bash
curl -X POST http://localhost:8001/api/query-service/order-service \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Check for related order issues with payment timeout"
  }'
```

