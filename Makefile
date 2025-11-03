PROJECT ?= $(notdir $(CURDIR))

SERVER_API := $(shell docker version --format '{{.Server.APIVersion}}' 2>/dev/null)
API := $(if $(SERVER_API),$(SERVER_API),1.43)

DOCKER = DOCKER_API_VERSION=$(API) docker
DC     = DOCKER_API_VERSION$(and $(API),=$(API)) docker compose -p $(PROJECT)
PY     = python

# Read MODEL_NAME / OLLAMA_HOST from .env if present, else use sane defaults
MODEL_NAME_FILE := $(shell awk -F= '/^MODEL_NAME=/{print $$2}' .env 2>/dev/null)
MODEL_NAME ?= $(if $(MODEL_NAME_FILE),$(MODEL_NAME_FILE),llama3.1:8b-instruct-q4_K_M)

OLLAMA_HOST_FILE := $(shell awk -F= '/^OPENAI_BASE_URL=/{print $$2}' .env 2>/dev/null)
# .env uses OPENAI_BASE_URL with /v1; the daemon is at the same host without /v1
OLLAMA_HOST ?= $(if $(OLLAMA_HOST_FILE),$(subst /v1,,$(OLLAMA_HOST_FILE)),http://localhost:11434)

# Python module to run (package with __main__.py)
PYMODULE ?= agent_system

.PHONY: up _clean docker agent down clean _wait_ollama _pull_model _wait_model server start build-ui watch-ui api

up:
	@echo "🔧 Using Docker API $(API)"
	@echo "🚀 Starting docker services (detached)…"
	@$(DC) up -d --build

_clean:
	@echo "🧹 Cleaning project '$(PROJECT)'…"
	@$(DC) down -v --remove-orphans || true
	@$(DOCKER) rm -fv $$($(DOCKER) ps -aq --filter "label=com.docker.compose.project=$(PROJECT)") 2>/dev/null || true
	@$(DOCKER) network rm $$($(DOCKER) network ls -q --filter "label=com.docker.compose.project=$(PROJECT)") 2>/dev/null || true
	@$(DOCKER) volume rm $$($(DOCKER) volume ls -q --filter "label=com.docker.compose.project=$(PROJECT)") 2>/dev/null || true
	@$(DOCKER) network rm $(PROJECT)_default 2>/dev/null || true

_wait_ollama:
	@echo "⏳ Waiting for Ollama at $(OLLAMA_HOST)…"
	@i=0; \
	until curl -sf "$(OLLAMA_HOST)/api/version" >/dev/null 2>&1; do \
	  i=$$((i+1)); \
	  if [ $$i -gt 120 ]; then echo "❌ Ollama daemon did not respond"; exit 1; fi; \
	  sleep 1; \
	done
	@echo "✅ Ollama is up."

_pull_model:
	@echo "⬇️  Pulling model '$(MODEL_NAME)' inside the container…"
	@$(DC) exec -T ollama sh -lc "ollama show '$(MODEL_NAME)' >/dev/null 2>&1 || ollama pull '$(MODEL_NAME)'" \
	  || (echo '❌ Failed to pull $(MODEL_NAME)'; exit 1)
	@echo "✅ Pull finished (or already present)."

_wait_model:
	@echo "⏳ Verifying model '$(MODEL_NAME)' is available…"
	@i=0; \
	while true; do \
	  if $(DC) exec -T ollama sh -lc "ollama show '$(MODEL_NAME)' >/dev/null 2>&1"; then \
	    echo "✅ Model '$(MODEL_NAME)' ready."; break; \
	  fi; \
	  i=$$((i+1)); \
	  if [ $$i -gt 300 ]; then echo "❌ Model '$(MODEL_NAME)' not available"; exit 1; fi; \
	  sleep 2; \
	done

docker:
	@$(DC) up -d --build

agent:
	@$(PY) -m $(PYMODULE)

api:
	@$(PY) -m agent_api

server:
	@echo "📦 Installing Python dependencies…"
	@$(PY) -m pip install -r requirements.txt
	@echo "📦 Installing Node dependencies…"
	@npm install
	@echo "🎨 Building Tailwind CSS…"
	@mkdir -p web/assets
	@npm run build:css
	@echo "✅ Server setup complete. Run 'make start' to launch."

start:
	@$(PY) -m agent_api

build-ui:
	@npx tailwindcss -i web/src/input.css -o web/assets/styles.css --minify

watch-ui:
	@npx tailwindcss -i web/src/input.css -o web/assets/styles.css --watch

down:
	@$(DC) down || true

clean:
	@$(MAKE) _clean
