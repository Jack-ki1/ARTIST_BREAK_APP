.PHONY: dev test lint migrate

PYTHON ?= python3
NODE ?= npm

dev:
	@echo "Starting backend and frontend in development mode..."
	(cd backend && $(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) & \
	(cd frontend && $(NODE) run dev)

test:
	@echo "Running backend and frontend tests..."
	(cd backend && $(PYTHON) -m pytest)
	(cd frontend && $(NODE) test)

lint:
	@command -v pre-commit >/dev/null 2>&1 || { echo "pre-commit is required; install it with python -m pip install pre-commit"; exit 127; }
	pre-commit run --all-files
migrate:
	@echo "Database migrations are managed in backend/ via Alembic when configured."
	@echo "No automatic migration step is defined in this repo yet."
