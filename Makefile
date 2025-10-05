PROJECT ?= $(notdir $(CURDIR))

SERVER_API := $(shell docker version --format '{{.Server.APIVersion}}' 2>/dev/null)
API := $(if $(SERVER_API),$(SERVER_API),1.43)

DOCKER = DOCKER_API_VERSION=$(API) docker
DC     = DOCKER_API_VERSION$(and $(API),=$(API)) docker compose -p $(PROJECT)
PY     = python

MODEL_NAME ?= phi3:mini
OLLAMA_HOST ?= http://localhost:11434

.PHONY: up _clean docker agent down clean hardclean _wait_ollama _pull_model _wait_model

up:
	@echo "🔧 Using Docker API $(API)"
	@$(MAKE) _clean
	@echo "🚀 Starting docker services (detached)…"
	@$(DC) up -d --build
	@$(MAKE) _wait_ollama
	@$(MAKE) _pull_model
	@$(MAKE) _wait_model
	@echo "🤖 Launching agent…"
	@$(PY) -m agent

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
	@echo "⬇️  Ensuring model '$(MODEL_NAME)' is present…"
	@$(DC) exec -T ollama ollama pull $(MODEL_NAME) >/dev/null 2>&1 || \
	  $(DC) run --rm -e OLLAMA_HOST=$(OLLAMA_HOST) ollama-init >/dev/null 2>&1 || true
	@echo "✅ Pull initiated or model already present."

_wait_model:
	@echo "⏳ Waiting for model '$(MODEL_NAME)' to be available…"
	@i=0; \
	until curl -s "$(OLLAMA_HOST)/api/tags" | grep -q "\"name\":\"$(MODEL_NAME)\""; do \
	  i=$$((i+1)); \
	  if [ $$i -gt 300 ]; then echo "❌ Model '$(MODEL_NAME)' not available"; exit 1; fi; \
	  sleep 2; \
	done
	@echo "✅ Model '$(MODEL_NAME)' ready."

docker:
	@$(DC) up -d --build

agent:
	@$(PY) -m agent

down:
	@$(DC) down || true

clean:
	@$(MAKE) _clean
