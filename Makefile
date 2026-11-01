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
	@echo "Running lint checks..."
	(cd backend && $(PYTHON) -m ruff check . || true)
	(cd frontend && $(NODE) exec eslint . || true)

migrate:
	@echo "Database migrations are managed in backend/ via Alembic when configured."
	@echo "No automatic migration step is defined in this repo yet."
