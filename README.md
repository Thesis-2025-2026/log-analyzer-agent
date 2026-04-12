# Log Analyzer Agent

**Overview**
- Multi-agent system for intelligent log analysis with distributed deployment support.
- Uses LLM-powered agents (Main Agent + Internal Knowledge Agent) for error reasoning and resolution.
- Supports both local single-service mode and distributed multi-service deployment.

## Documentation Status

For implementation-aligned documentation, use:

- `docs/LATEST_AGENT_SYSTEM_OVERVIEW.md`
- `docs/LATEST_DISTRIBUTED_DEPLOYMENT.md`
- `docs/DOCS_GAP_CHECKLIST.md` (verified stale vs current gaps)

## Project Structure

```
├── agent_system/          # Agent logic, tools, prompts, model factory
│   ├── agents/            # Main Agent and Internal Knowledge Agent
│   ├── tools/             # Health check, internal knowledge, cross-service tools
│   └── prompts/           # Agent system prompts
├── agent_api/             # Flask service for agent interaction
├── proxy_service/         # Service discovery proxy/dispatcher
├── web/                   # Frontend UI (Tailwind CSS)
├── infra/                 # Database init scripts and seeds
├── config/                # Service-specific environment configs
├── docker-compose.yml     # Single-service local development
└── docker-compose.distributed.yml  # Multi-service distributed deployment
```

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API key (for embeddings and LLM)

## Environment Variables

Create `.env` from `.exampleEnv`:

```bash
# Required for distributed deployment
OPENAI_API_KEY=sk-your-key-here

# For local Ollama usage
MODEL_PLATFORM=OLLAMA
MODEL_NAME=llama3.2:3b-instruct
OPENAI_BASE_URL=http://localhost:11434/v1
TEMPERATURE=0.1
```

---

## Quick Start: Local Development

### 1. Start Infrastructure
```bash
make up  # Starts Redis, Postgres, Ollama
```

### 2. Setup Server
```bash
make server  # Install deps, build Tailwind CSS
```

### 3. Run API
```bash
make start  # Flask server at http://localhost:8000
```

### Test
```bash
curl -X POST http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"{\"level\":\"error\",\"service\":\"orders\",\"message\":\"DB timeout\"}"}'
```

---

## Distributed Deployment

The distributed architecture deploys isolated agent clusters per service, with a central proxy for service discovery.

### Architecture

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Payment Service │  │  Order Service  │  │   Service C     │
│  Agent Cluster  │  │  Agent Cluster  │  │  Agent Cluster  │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Proxy/Dispatcher │
                    │ (Service Registry)│
                    └───────────────────┘
```

Each service cluster contains:
- **Main Agent** - Error reasoning, cross-service coordination
- **Internal Knowledge Agent** - RAG-based local knowledge search
- **PostgreSQL** - Historical logs storage
- **Qdrant** - Vector database for error-fix patterns

### 1. Start Distributed Services

```bash
# Ensure OPENAI_API_KEY is set in .env
docker-compose -f docker-compose.distributed.yml up -d
```

This starts:
| Service | Port | Description |
|---------|------|-------------|
| Proxy | 8000 | Service discovery & registry |
| Payment API | 8001 | Payment service agent |
| Payment Postgres | 5433 | Payment logs database |
| Payment Qdrant | 6333 | Payment knowledge base |
| Order API | 8002 | Order service agent |
| Order Postgres | 5434 | Order logs database |
| Order Qdrant | 6334 | Order knowledge base |
| Auth API | 8003 | Auth service agent |
| Auth Postgres | 5435 | Auth logs database |
| Auth Qdrant | 6335 | Auth knowledge base |
| Deployments API | 8004 | Deployments service agent |
| Deployments Postgres | 5436 | Deployments logs database |
| Deployments Qdrant | 6336 | Deployments knowledge base |
| IdP API | 8005 | IdP service agent |
| IdP Postgres | 5437 | IdP logs database |
| IdP Qdrant | 6337 | IdP knowledge base |

### 2. Verify Services

```bash
# Check proxy health
curl http://localhost:8000/health

# List registered services
curl http://localhost:8000/services

# Check individual services
curl http://localhost:8001/health  # payment-service
curl http://localhost:8002/health  # order-service
```

### 3. Seed Demo Data

PostgreSQL seeds are automatically loaded on container start. To seed Qdrant vector databases:

```bash
# Option 1: Run the seed script
./infra/seed_all.sh

# Option 2: Manual Qdrant seeding
python infra/seed_qdrant.py \
  --payment-url http://localhost:6333 \
  --order-url http://localhost:6334 \
  --collection log_fixes
```

**Seeded Data:**

| Database | Payment | Order |
|----------|---------|-------|
| PostgreSQL | 10 payment logs, 2 reports | 11 order logs, 2 reports |
| Qdrant | 5 error-fix pairs | 5 error-fix pairs |

### 4. Test Cross-Service Analysis

Run the test notebook:
```bash
jupyter notebook test_distributed_system.ipynb
```

Or test via API:
```bash
curl -X POST http://localhost:8001/api/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Analyze: javax.persistence.PersistenceException - Connection pool exhausted. Orders ORD-10055, ORD-10056 stuck in PENDING_PAYMENT."
  }'
```

The Main Agent will:
1. Search local internal knowledge (PostgreSQL + Qdrant)
2. Discover other services via the proxy
3. Query order-service for downstream impact
4. Generate comprehensive cross-service analysis

### 5. Cleanup

```bash
# Stop services
docker-compose -f docker-compose.distributed.yml down

# Stop and remove all data
docker-compose -f docker-compose.distributed.yml down -v
```

---

## API Endpoints

### Proxy Service (port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Proxy health status |
| `/services` | GET | List all registered services |
| `/discover?capability=X` | GET | Find services by capability |
| `/register` | POST | Register a new service |
| `/services/{name}/heartbeat` | POST | Service heartbeat |

### Agent Service (ports 8001, 8002)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/query` | POST | Analyze log with Main Agent |
| `/api/service-info` | GET | Service metadata |
| `/api/discover-services` | GET | Discover other services |
| `/api/query-service/{name}` | POST | Query specific service |

---

## Key Features

### Environment Isolation
- Each service cluster operates independently
- Service-specific dependencies and configurations
- No conflicts between services

### Data Privacy & Compliance
- Teams maintain control over their service's data
- No sensitive data sharing across boundaries
- Meets corporate data governance requirements

### Fault Tolerance
- Failure in one service doesn't affect others
- Independent scaling per service
- Each service can be updated independently

---

## Troubleshooting

### Services not registering with proxy
Check logs: `docker-compose -f docker-compose.distributed.yml logs service-payment-api`

### Qdrant collection not found
Run the seed script: `./infra/seed_all.sh`

### OPENAI_API_KEY error
Ensure `.env` contains `OPENAI_API_KEY=sk-...`

### Connection refused to databases
Wait for containers to be healthy: `docker-compose -f docker-compose.distributed.yml ps`

---

## Recommended Models

| Model | Use Case |
|-------|----------|
| `gpt-4o-mini` | Fast, cost-effective (default for distributed) |
| `gpt-4o` | Best quality analysis |
| `llama3.2:3b-instruct` | Local Ollama, quick testing |
| `llama3.1:8b-instruct-q4_K_M` | Local Ollama, better quality |

---

## Documentation

- [Latest Agent System Overview](docs/LATEST_AGENT_SYSTEM_OVERVIEW.md) - Current architecture, API contract, and tracing model
- [Latest Distributed Deployment Guide](docs/LATEST_DISTRIBUTED_DEPLOYMENT.md) - Current multi-service topology, channels, and operations
- [Docs Gap Checklist](docs/DOCS_GAP_CHECKLIST.md) - Verified mismatches and maintenance baseline
- [Legacy Agent System Overview](docs/AGENT_SYSTEM_OVERVIEW.md) - Historical reference
- [Legacy Distributed Deployment Guide](docs/DISTRIBUTED_DEPLOYMENT.md) - Historical reference
- [Test Notebook](test_distributed_system.ipynb) - Interactive testing scenarios
