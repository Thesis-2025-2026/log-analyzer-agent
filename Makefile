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

.PHONY: up _clean docker agent down clean _wait_ollama _pull_model _wait_model server start build-ui watch-ui api migrate \
        detector all tail test

up:
	@echo "🔧 Using Docker API $(API)"
	@echo "🚀 Starting docker services (detached)…"
	@$(DC) up -d --build
	@$(MAKE) _wait_ollama
	@$(MAKE) _pull_model
	@$(MAKE) _wait_model
	@echo "✅ Infra and model ready: $(MODEL_NAME)"

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

## Apply DB migrations (re-run init SQL safely)
migrate:
	@$(DC) exec -T postgres sh -lc "psql -U $$POSTGRES_USER -d $$POSTGRES_DB -f /docker-entrypoint-initdb.d/init_db.sql"

## Initialize PostgreSQL with sample data
init-postgres-sample:
	@echo "📊 Inserting sample data into PostgreSQL..."
	@$(DC) cp infra/init_sample_data.sql postgres:/tmp/init_sample_data.sql
	@$(DC) exec -T postgres sh -lc "psql -U $$POSTGRES_USER -d $$POSTGRES_DB -f /tmp/init_sample_data.sql"
	@echo "✅ PostgreSQL sample data inserted"

## Initialize Qdrant with sample data
init-qdrant-sample:
	@echo "📊 Inserting sample data into Qdrant..."
	@$(PY) init_qdrant_sample_data.py
	@echo "✅ Qdrant sample data inserted"

## Initialize both databases with sample data
init-sample-data: init-postgres-sample init-qdrant-sample
	@echo "✅ All sample data initialized"

## Fix Qdrant collection configuration (recreates with correct vector config)
fix-qdrant-collection:
	@echo "🔧 Fixing Qdrant collection configuration..."
	@$(PY) fix_qdrant_collection.py

build-ui:
	@npx tailwindcss -i web/src/input.css -o web/assets/styles.css --minify

watch-ui:
	@npx tailwindcss -i web/src/input.css -o web/assets/styles.css --watch

## Fully rebuild distributed stack with no cached layers or persisted volumes
# Usage: make rebuild-distributed-fresh [PRUNE_IMAGES=1]
# - Stops and removes distributed containers + volumes
# - Prunes builder cache (and images if PRUNE_IMAGES=1)
# - Rebuilds images without cache (with --pull)
# - Brings the stack back up with forced recreation
rebuild-distributed-fresh:
	@echo "🛑 Stopping distributed stack and wiping volumes…"
	@$(DC) -f docker-compose.distributed.yml down -v --remove-orphans
	@echo "🧹 Pruning builder cache…"
	@$(DOCKER) builder prune -af
	@if [ "$(PRUNE_IMAGES)" = "1" ]; then \
		echo "🧹 Pruning unused images…"; \
		$(DOCKER) image prune -af; \
	fi
	@echo "🔨 Rebuilding images (no cache, pull latest bases)…"
	@$(DC) -f docker-compose.distributed.yml build --no-cache --pull
	@echo "🚀 Starting distributed stack (force recreate)…"
	@$(DC) -f docker-compose.distributed.yml up -d --force-recreate
	@echo "🌱 Seeding Qdrant knowledge bases…"
	@./infra/seed_all.sh
	@echo "✅ Distributed stack rebuilt fresh."

down:
	@$(DC) down || true

clean:
	@$(MAKE) _clean

test:
	@$(PY) -m pytest


detector:
	@echo "🚀 Starting detector + agent consumer (Ctrl-C to stop)…"
	@set -e; \
	  $(PY) -m detector.detector & D1=$$!; \
#	  $(PY) -m agent_system.connect_to_detector & D2=$$!; \
	  wait $$D1

all:
	@echo "🚀 Starting detector + agent consumer + API (Ctrl-C to stop)…"
	@set -e; \
	  $(PY) -m detector.detector & D1=$$!; \
	  $(PY) -m agent_system.connect_to_detector & D2=$$!; \
	  $(PY) -m agent_api & D3=$$!; \
	  wait $$D1 $$D2 $$D3

tail:
	@$(PY) scripts/tail_pubsub.py
