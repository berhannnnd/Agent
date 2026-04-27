IMAGE ?= agents
TAG ?= latest
PORT ?= 8010
VENV ?= .venv
PYTHON_BIN ?= $(shell command -v python3.12 2>/dev/null || command -v python3.11 2>/dev/null || command -v python3.10 2>/dev/null)
UV ?= $(shell command -v uv 2>/dev/null)
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip

.PHONY: check-python venv setup run cli dev-web stop test build up down log

check-python:
	@test -n "$(PYTHON_BIN)" || (echo "Python 3.10+ is required." && exit 1)
	@$(PYTHON_BIN) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'

venv: check-python
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "Creating $(VENV) with $(PYTHON_BIN)"; \
		if [ -n "$(UV)" ]; then $(UV) venv --python "$(PYTHON_BIN)" "$(VENV)"; \
		else $(PYTHON_BIN) -m venv "$(VENV)"; fi; \
	fi
	@$(PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'

setup: venv
	$(PIP) install -e .
	cd web && npm install

run: venv
	$(PYTHON) main.py

cli: venv
	$(PYTHON) -m app.cli chat

dev-web: venv
	@echo "Starting backend..."
	@$(PYTHON) main.py & BACKEND_PID=$$!; \
	trap "kill $$BACKEND_PID 2>/dev/null" EXIT; \
	cd web && npm run dev

stop:
	-pkill -f "main:app" 2>/dev/null || true

test: venv
	$(PYTHON) -m pytest tests -q

build:
	docker build -f deploy/Dockerfile -t $(IMAGE):$(TAG) .

up:
	IMAGE=$(IMAGE) TAG=$(TAG) PORT=$(PORT) docker compose -f deploy/docker-compose.yml up -d

down:
	IMAGE=$(IMAGE) TAG=$(TAG) PORT=$(PORT) docker compose -f deploy/docker-compose.yml down

log:
	IMAGE=$(IMAGE) TAG=$(TAG) PORT=$(PORT) docker compose -f deploy/docker-compose.yml logs -f --tail 200
