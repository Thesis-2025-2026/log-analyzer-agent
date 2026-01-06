# Agent System Overview

This document provides a comprehensive overview of the Log Analyzer Agent System architecture, components, and workflows.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Types](#agent-types)
3. [Tools](#tools)
4. [Workflows](#workflows)
5. [Data Flow](#data-flow)
6. [Configuration](#configuration)
7. [Extending the System](#extending-the-system)

---

## Architecture Overview

The Log Analyzer Agent System is a multi-agent architecture designed for intelligent log analysis in distributed microservice environments. It uses LLM-powered agents with specialized tools to analyze errors, retrieve historical context, and coordinate across services.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Agent System                                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Main Agent                                │   │
│  │  • Orchestration & Decision Making                              │   │
│  │  • Error Severity Assessment                                    │   │
│  │  • Cross-Service Coordination                                   │   │
│  │  • Final Report Generation                                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                │                                        │
│                    ┌───────────┼───────────┐                           │
│                    ▼           ▼           ▼                           │
│  ┌──────────────────┐ ┌──────────────┐ ┌─────────────────────────┐    │
│  │ Health Check     │ │  Internal    │ │   Cross-Service         │    │
│  │ Tool             │ │  Knowledge   │ │   Tools                 │    │
│  │                  │ │  Tool        │ │                         │    │
│  │ • Service ping   │ │      │       │ │ • discover_services     │    │
│  │ • Status check   │ │      ▼       │ │ • get_service_report    │    │
│  └──────────────────┘ │ ┌──────────┐ │ │ • gather_cross_service  │    │
│                       │ │ Internal │ │ │         _reports        │    │
│                       │ │Knowledge │ │ └─────────────────────────┘    │
│                       │ │  Agent   │ │              │                  │
│                       │ └──────────┘ │              ▼                  │
│                       │      │       │    ┌─────────────────┐          │
│                       │   ┌──┴──┐    │    │     Proxy       │          │
│                       │   ▼     ▼    │    │   (Dispatcher)  │          │
│                       │ ┌───┐ ┌───┐  │    └─────────────────┘          │
│                       │ │SQL│ │RAG│  │              │                  │
│                       │ │ DB│ │ DB│  │              ▼                  │
│                       │ └───┘ └───┘  │    ┌─────────────────┐          │
│                       └──────────────┘    │  Other Service  │          │
│                                           │     Agents      │          │
│                                           └─────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Each agent has a single, well-defined responsibility
2. **Tool-Based Capabilities**: Agents extend functionality through composable tools
3. **Hierarchical Coordination**: Main Agent orchestrates, specialized agents execute
4. **Distributed-First**: Built for multi-service environments with service discovery
5. **Knowledge-Augmented**: RAG-enhanced analysis with historical context

---

## Agent Types

### 1. Main Agent

The Main Agent is the primary orchestrator responsible for comprehensive log analysis and decision-making.

**File**: `agent_system/agents/main_agent/agent.py`

#### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Orchestration** | Coordinates the analysis workflow and delegates to specialized tools |
| **Severity Assessment** | Evaluates error severity on a 0-10 scale with justification |
| **Impact Analysis** | Identifies immediate impact and potential cascading effects |
| **Cross-Service Analysis** | Discovers and queries other services for holistic view |
| **Report Generation** | Synthesizes all information into actionable reports |

#### Available Tools

```python
tools = [
    # Local analysis
    FunctionTool(check_service_health),      # Ping services for health status
    FunctionTool(query_internal_knowledge),   # Query Internal Knowledge Agent
    
    # Cross-service (distributed)
    FunctionTool(discover_services),          # Find services via proxy
    FunctionTool(get_service_report),         # Query specific service
]
```

#### Severity Levels

| Level | Score | Criteria |
|-------|-------|----------|
| **CRITICAL** | 7-10 | System-wide failures, data loss, security breaches, complete outages |
| **HIGH** | 5-7 | Major functionality broken, significant user impact |
| **MEDIUM** | 4-5 | Partial functionality affected, moderate impact |
| **LOW** | 0-3 | Minor issues, warnings, non-critical errors |

#### Workflow Strategy

```
1. Parse and understand the log data
2. Extract key information (error level, service, message, timestamp)
3. Query internal knowledge for historical context
4. Discover available services in the ecosystem
5. If multi-service impact suspected:
   - Query related services for their reports
   - Correlate findings across services
6. Check service health when needed
7. Assess severity based on all gathered information
8. Generate comprehensive report with recommendations
```

---

### 2. Internal Knowledge Agent

The Internal Knowledge Agent specializes in retrieving historical context and known fixes from local databases.

**File**: `agent_system/agents/internal_knowledge/agent.py`

#### Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **SQL Database Queries** | Retrieve historical logs matching error patterns |
| **RAG Search** | Find similar past errors and their fixes via vector search |
| **Pattern Identification** | Identify trends and recurring issues |
| **Context Synthesis** | Compile historical data into actionable context |

#### Available Tools

```python
tools = [
    FunctionTool(query_logs_sql),           # Read-only SQL queries
    FunctionTool(query_logs_by_time_range), # Start/end timestamp window
    FunctionTool(search_fixes_for_error),   # RAG vector search
    FunctionTool(search_reports_for_context), # Report RAG (advisory)
    FunctionTool(get_current_time),         # Current UTC timestamp
]
```

#### Query Strategy

The Internal Knowledge Agent receives a free-form query from the Main Agent and
decides which tools to use (SQL logs, time-range logs, RAG fixes, or report RAG).

---

## Tools

### Local Analysis Tools

#### 1. Health Check Tool

**File**: `agent_system/tools/health_check_tool.py`

Pings services to determine their health status.

```python
def check_service_health(service_url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Check if a service is alive by pinging health endpoints.
    
    Returns:
        {
            "status": "alive" | "dead" | "unknown",
            "response_time_ms": 42,
            "status_code": 200,
            "endpoint": "http://service:8000/health"
        }
    """
```

**Health Check Sequence**:
1. Try `/health` endpoint
2. Try `/healthz` endpoint
3. Try `/ping` endpoint
4. Try base URL
5. Fall back to socket connection test

---

#### 2. Database Tool

**File**: `agent_system/tools/db_tool.py`

Queries PostgreSQL for historical log data.

```python
def query_logs_sql(
    sql: str,
    limit: int = 100
) -> Dict[str, Any]:
    """Run a read-only SELECT/WITH query against logs."""

def query_logs_by_time_range(
    start_ts: str,
    end_ts: str,
    limit: int = 100
) -> Dict[str, Any]:
    """Return up to 100 logs between start/end timestamps."""
```

**Database Schema**:
```sql
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT now(),
    level VARCHAR(20) NOT NULL,
    raw JSONB NOT NULL
);
```

---

#### 3. RAG Tool

**File**: `agent_system/tools/rag_tool.py`

Vector database search for similar errors and their fixes.

```python
def search_fixes_for_error(
    error_log: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Search vector database for fixes related to an error.
    
    Returns:
        [
            {
                "content": "Fix description...",
                "score": 0.89,
                "metadata": {"severity": "HIGH", "service": "payment"}
            }
        ]
    """

def add_fix_to_knowledge_base(
    error_log: str,
    fix_description: str,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """Store new error-fix pairs in the knowledge base."""
```

**Vector Database Configuration**:
- **Database**: Qdrant
- **Embedding Model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Distance Metric**: Cosine similarity
- **Collection**: `log_fixes`

---

#### 4. Internal Knowledge Tool

**File**: `agent_system/tools/internal_knowledge_tool.py`

Bridges the Main Agent to the Internal Knowledge Agent.

```python
def query_internal_knowledge(
    query: str
) -> str:
    """
    Query the Internal Knowledge Agent for specific internal knowledge needs.
    
    Internally creates an Internal Knowledge Agent instance and
    executes the query, returning synthesized results.
    """
```

---

### Cross-Service Tools

#### 1. Discover Services

**File**: `agent_system/tools/cross_service_tool.py`

```python
def discover_services(capability: Optional[str] = None) -> str:
    """
    Query the proxy for registered services.
    
    Args:
        capability: Optional filter (e.g., "payment", "order")
    
    Returns:
        "Found 3 service(s):
         - payment-service: capabilities=[payment, billing], status=healthy
         - order-service: capabilities=[order, fulfillment], status=healthy
         - inventory-service: capabilities=[inventory], status=healthy"
    """
```

---

#### 2. Get Service Report

```python
def get_service_report(service_name: str, query: str) -> str:
    """
    Get analysis from a specific service's agent.
    
    Process:
    1. Look up service URL from proxy
    2. Verify service is healthy
    3. POST query to service's /api/query endpoint
    4. Return formatted report
    
    Returns:
        "[Report from order-service]
         Service: order-service
         Capabilities: order, fulfillment
         ----------------------------------------
         Analysis: Found 5 orders stuck in PENDING_PAYMENT..."
    """
```

---

## Workflows

### Single-Service Analysis

```
User Request
     │
     ▼
┌─────────────────────┐
│     Main Agent      │
│  (parse log data)   │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐  ┌─────────────┐
│ Health  │  │  Internal   │
│  Check  │  │  Knowledge  │
│  Tool   │  │    Tool     │
└────┬────┘  └──────┬──────┘
     │              │
     │         ┌────┴────┐
     │         ▼         ▼
     │    ┌────────┐ ┌────────┐
     │    │  SQL   │ │  RAG   │
     │    │   DB   │ │   DB   │
     │    └────────┘ └────────┘
     │         │         │
     └────┬────┴─────────┘
          ▼
┌─────────────────────┐
│     Main Agent      │
│ (synthesize report) │
└──────────┬──────────┘
           │
           ▼
    Final Analysis Report
```

### Cross-Service Analysis

```
User Request (complex multi-service error)
     │
     ▼
┌─────────────────────┐
│     Main Agent      │
│  (parse log data)   │
└──────────┬──────────┘
           │
     ┌─────┼─────────────────┐
     ▼     ▼                 ▼
┌───────┐ ┌──────────┐ ┌───────────────┐
│Health │ │ Internal │ │   Discover    │
│ Check │ │Knowledge │ │   Services    │
└───────┘ └──────────┘ └───────┬───────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       Proxy         │
                    │  (Service Registry) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Service  │    │ Service  │    │ Service  │
        │    A     │    │    B     │    │    C     │
        │  Agent   │    │  Agent   │    │  Agent   │
        └────┬─────┘    └────┬─────┘    └────┬─────┘
             │               │               │
             └───────────────┼───────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │     Main Agent      │
                  │  (aggregate reports │
                  │   & synthesize)     │
                  └──────────┬──────────┘
                             │
                             ▼
               Comprehensive Cross-Service Report
```

---

## Data Flow

### Log Analysis Request Flow

```
1. API receives POST /api/query with log data
   │
2. analyze_log_with_main_agent() called
   │
3. Main Agent created with tools
   │
4. Main Agent parses log, decides on actions:
   │
   ├──► query_internal_knowledge()
   │    └──► Internal Knowledge Agent
   │         ├──► query_logs_sql() → PostgreSQL
   │         └──► search_fixes_for_error() → Qdrant
   │
   ├──► check_service_health()
   │    └──► HTTP/Socket ping to service
   │
   └──► discover_services()
        └──► GET /discover → Proxy
             └──► get_service_report()
                  └──► POST /api/query → Remote Service Agents
   │
5. Main Agent synthesizes all information
   │
6. Formatted report returned to API
```

### Data Sources

| Source | Type | Purpose |
|--------|------|---------|
| **PostgreSQL** | Relational | Historical logs, structured queries |
| **Qdrant** | Vector DB | RAG search for similar errors/fixes |
| **Proxy Registry** | In-Memory | Service discovery and health tracking |
| **Remote Services** | API | Cross-service context and reports |

---

## Configuration

### Environment Variables

```bash
# Model Configuration
MODEL_PLATFORM=OPENAI              # OPENAI, OLLAMA, etc.
MODEL_NAME=gpt-4o-mini             # Model identifier
OPENAI_API_KEY=sk-...              # API key
OPENAI_BASE_URL=https://api.openai.com/v1
TEMPERATURE=0.1                    # Response temperature

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=logs_db
POSTGRES_USER=logs_user
POSTGRES_PASSWORD=logs_pass

# Vector Database Configuration
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=log_fixes
QDRANT_TIMEOUT=30.0
EMBEDDING_DIM=1536

# Cross-Service Configuration
PROXY_URL=http://localhost:8000
CROSS_SERVICE_TIMEOUT=240
```

### Model Factory

**File**: `agent_system/core/model_factory.py`

```python
def create_model(tool_choice="required"):
    """
    Create an LLM model instance using CAMEL-AI ModelFactory.
    
    Supports:
    - OpenAI (GPT-4, GPT-4o-mini, etc.)
    - Ollama (local LLMs)
    - Other CAMEL-AI supported platforms
    """
```

---

## Extending the System

### Adding a New Tool

1. **Create the tool function** in `agent_system/tools/`:

```python
# agent_system/tools/my_new_tool.py
def my_new_tool(param1: str, param2: int = 10) -> str:
    """
    Tool description for the LLM.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)
    
    Returns:
        Description of return value
    """
    # Implementation
    return result
```

2. **Register with an agent**:

```python
# In agent.py
from agent_system.tools.my_new_tool import my_new_tool

tools = [
    # ... existing tools
    FunctionTool(my_new_tool),
]
```

3. **Update the system prompt** to describe when to use the tool.

### Adding a New Agent

1. **Create agent directory**: `agent_system/agents/my_agent/`

2. **Create agent file**:

```python
# agent_system/agents/my_agent/agent.py
from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from agent_system.core.model_factory import create_model

def make_my_agent() -> ChatAgent:
    model = create_model()
    system_prompt = "You are a specialized agent for..."
    
    tools = [
        FunctionTool(tool1),
        FunctionTool(tool2),
    ]
    
    return ChatAgent(
        system_message=system_prompt,
        model=model,
        tools=tools,
    )
```

3. **Create prompt file**: `agent_system/prompts/my_agent.py`

4. **Integrate with Main Agent** if needed (as a tool).

### Adding a New Data Source

1. **Create a tool** that interfaces with the data source
2. **Register the tool** with the appropriate agent
3. **Update prompts** to describe the new capability

---

## Best Practices

### Prompt Engineering

- Be specific about when to use each tool
- Provide clear examples in system prompts
- Define expected output formats
- Include error handling guidance

### Tool Design

- Keep tools focused (single responsibility)
- Provide comprehensive docstrings (used by LLM)
- Handle errors gracefully with informative messages
- Use appropriate timeouts for external calls

### Performance

- Use parallel queries when possible (ThreadPoolExecutor)
- Cache expensive resources (vector retriever)
- Set appropriate timeouts for all network calls
- Limit result sets to prevent token overflow

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Empty agent response | Token limit or parsing error | Check log data size, increase max_retries |
| RAG search fails | Qdrant connection issues | Verify QDRANT_URL, check network |
| Cross-service timeout | Remote service slow/down | Increase CROSS_SERVICE_TIMEOUT |
| Health check fails | Service down or wrong URL | Verify service URL and port |

### Debugging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agent_system")
logger.setLevel(logging.DEBUG)
```

---

## References

- [CAMEL-AI Documentation](https://docs.camel-ai.org/)
- [Qdrant Vector Database](https://qdrant.tech/documentation/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
