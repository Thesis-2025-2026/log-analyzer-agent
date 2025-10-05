# Log Analyzer Agent

Project structure
- `agent/agent.py`: main agent entry (LangChain + Ollama).
- `agent/tools/`: tool functions used by the agent (e.g., `logParser.py`).

Docker compose
- Starts Redis (`6379`), Postgres (`5433`), and Ollama (`11434`).
- Includes an init step to pull the model; containers are ephemeral.

Setup
- Create `.env` and paste the contents of `exampleEnv`.
- Run `make up` to start services and prepare the model.
- Use `make agent` to talk to the agent in the terminal.
