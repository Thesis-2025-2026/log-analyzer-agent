# Log Analyzer Agent

Project structure
- `agent/agent.py`: main agent entry (local Ollama via OpenAI-compatible API).
- `agent/tools/`: tool functions used by the agent (e.g., `log_parser.py`).

Docker compose
- Starts Redis (`6379`), Postgres (`5433`), and Ollama (`11434`).
- Includes an init step to pull the model; containers are ephemeral.

Setup
- Create `.env` and paste the contents of `.exampleEnv`.
- Ensure env for local model:
  - `OPENAI_BASE_URL=http://localhost:11434/v1`
  - `OPENAI_API_KEY=ollama` (any non-empty string)
  - `MODEL_NAME=phi3:mini` (or your chosen Ollama model)
- Run `make up` to start services and prepare the model.
- Use `make agent` to talk to the agent in the terminal.
