IMAGE ?= aibox/framework-template
TAG ?= latest
PORT ?= 8010
VENV ?= .venv
PYTHON_BIN ?= $(shell command -v python3.12 2>/dev/null || command -v python3.11 2>/dev/null || command -v python3.10 2>/dev/null)
UV ?= $(shell command -v uv 2>/dev/null)
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip
CHAT_ARGS ?=

.PHONY: check-python venv install reinstall clean-venv run dev test build up down log

check-python:
	@test -n "$(PYTHON_BIN)" || (echo "Python 3.10+ is required. Install python3.10+ or run: make install PYTHON_BIN=/path/to/python3.11" && exit 1)
	@$(PYTHON_BIN) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else "Python 3.10+ is required")'

venv: check-python
	@if [ -x "$(PYTHON)" ] && ! $(PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then \
		echo "Removing incompatible $(VENV)"; \
		rm -rf "$(VENV)"; \
	fi
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "Creating $(VENV) with $(PYTHON_BIN)"; \
		if [ -n "$(UV)" ]; then \
			$(UV) venv --python "$(PYTHON_BIN)" "$(VENV)"; \
		else \
			$(PYTHON_BIN) -m venv "$(VENV)"; \
		fi; \
	fi
	@$(PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else "Virtualenv Python 3.10+ is required")'

install: venv
	@if [ -n "$(UV)" ]; then \
		$(UV) pip install --python "$(PYTHON)" -r requirements/requirements.txt; \
	else \
		$(PIP) install --upgrade pip setuptools wheel; \
		$(PIP) install -r requirements/requirements.txt; \
	fi

reinstall: clean-venv install

clean-venv:
	rm -rf "$(VENV)"

run: venv
	$(PYTHON) main.py

dev: venv
	$(PYTHON) -m app.cli chat $(CHAT_ARGS)

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
