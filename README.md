# Log Analyzer Agent

**Overview**
- Flask micro-API that wraps an LLM-powered log analysis agent and a simple Tailwind UI.
- Uses Ollama locally via the OpenAI-compatible endpoint for model inference.

**Project Structure**
- `agent_system/` — agent logic, tools, prompts, and model factory.
- `agent_api/` — Flask API and static file server.
- `web/` — frontend (index and reports pages) and Tailwind sources.
- `infra/`, `docker-compose.yml` — Redis, Postgres, and Ollama services.
- `Makefile` — convenience targets for infra, setup, and running.

Key files:
- agent_api/app.py:1 — Flask app factory, routes, and static serving.
- agent_api/__main__.py:1 — dev entrypoint (`python -m agent_api`).
- web/src/input.css:1 — Tailwind source (compiled to `web/assets/styles.css`).
- agent_system/__main__.py:1 — CLI agent entry (optional terminal usage).

**Prerequisites**
- Python 3.11+
- Node.js 18+ and npm
- Docker (for Ollama via compose) or native Ollama

**Environment Variables**
Create `.env` (you can start from `.exampleEnv`) and set at least:
- `MODEL_PLATFORM=OLLAMA`
- `MODEL_NAME=llama3.2:3b-instruct` (fast test) or `llama3.1:8b-instruct-q4_K_M`
- `OPENAI_BASE_URL=http://localhost:11434/v1`
- `OPENAI_API_KEY=ollama` (any non-empty string)
- `TEMPERATURE=0.1`

Defaults for the above are also baked into settings (see agent_system/config/settings.py:1), but a `.env` keeps things explicit.

**Bring Up Infra (Docker)**
- `make up`
  - Starts Redis (`6379`), Postgres (`5433`), and Ollama (`11434`).
  - `docker-compose.yml` includes a one-time init to pull `${MODEL_NAME}`.
- Verify Ollama is reachable: `curl -s http://localhost:11434/api/version`

**One-Time Server Setup**
- `make server`
  - Installs Python deps (`requirements.txt`).
  - Installs Node dev deps (`tailwindcss`, `postcss`, `autoprefixer`).
  - Builds Tailwind CSS to `web/assets/styles.css`.

**Run the API + UI**
- `make start`
  - Runs the Flask server at `http://localhost:8000` and serves the UI.
- Pages
  - `GET /` → chat UI (web/index.html:1)
  - `GET /reports` → reports mock (web/reports.html:1)
- API endpoints
  - `POST /api/query` — analyze a log, body: `{ "query": string, "agent": "log_analysis" }`
  - `GET /api/reports` — placeholder list (TODO)
  - `GET /api/reports/:id` — placeholder detail (TODO)
  - `GET /health` — liveness

Quick test:
```
curl -s -X POST http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"{\"level\":\"error\",\"service\":\"orders\",\"message\":\"DB timeout\"}"}'
```

**Optional: CLI Agent**
- `make agent` — runs the terminal-based agent (agent_system) if you prefer CLI.

**Recommended Models (Ollama)**
- Small and quick: `llama3.2:3b-instruct`
- Balanced quantized: `llama3.1:8b-instruct-q4_K_M`

Note: Smaller models may be less reliable at tool invocation; the API’s guard logic retries with explicit tool-call instructions.
