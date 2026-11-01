# Breakout Radar

Breakout Radar is the place where a scouting team turns measured, sourced signals into human-reviewed signing decisions.

The product is built around one principle: a signal is only valuable if it is provable, time-stamped, and explainable. This repository keeps the product honest by separating catalog lookups from recommendation claims and by making every evidence source explicit.

## North star

- Every number has a provenance row: source, timestamp, licence, and raw reference
- Every score remains explainable before it is presented as a recommendation
- Humans decide; the system prepares evidence and accelerates review

## Current repo layout

```text
backend/    FastAPI app, SQLAlchemy models, provider integrations, API tests
frontend/   React + Vite client, API layer, UI and component tests
docs/       Architecture, data-source, and product notes
```

This project already includes a working catalog search and directory workflow, and the next step is to evolve it from a metadata browser into an evidence-backed scouting workspace. The rebuild keeps the catalog search, but adds a scoring and review layer that is explicitly sourced and reviewable.

## Product direction

The working wedge is a human-in-the-loop scouting workspace with:

- a command-bar search for artist, region, and genre
- a reviewable artist page with signal timelines and evidence drawers
- a pipeline board for discovery through review
- structured scoring rubrics and reviewer notes
- weekly digest views and alert thresholds

This extends beyond the current placeholder dashboards and keeps the product useful without inventing audience data.

## Quick start

### Backend

Requires Python 3.10+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `http://127.0.0.1:8000/api/health`
Interactive docs: `http://127.0.0.1:8000/docs`

### Frontend

Requires Node 20.19+.

```bash
cd frontend
npm ci
npm run dev
```

The Vite app runs at `http://127.0.0.1:5173` and proxies `/api` to the backend on port 8000.

### Repo tasks

```bash
make dev
make test
make lint
make migrate
```

## Security and ops notes

- Authentication is not enabled in the current local demo flow; the API must remain local-only during development.
- Keep provider and sign-in access behind real authorization before exposing the service publicly.
- PostgreSQL is supported via `DATABASE_URL`; SQLite remains the default for local development.
- Production deployments need real auth, migrations, retention rules, and monitoring.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution workflow and standards.

## Security

See [SECURITY.md](./SECURITY.md) for reporting vulnerabilities and the supported disclosure process.

## License

This project is licensed under the [MIT License](./LICENSE).
