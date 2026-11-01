# Breakout Radar

Breakout Radar is a React/Vite frontend with a separately run Python/FastAPI backend. It searches the live MusicBrainz artist catalog and stores artist identities an operator chooses to save.

**It starts with no saved artists.** Discovery results come from MusicBrainz and are labeled with their source; the application does not invent artist profiles or audience measurements. Spotify and YouTube are external search destinations, not integrated data providers.

The public homepage leads to a local demo sign-in and then the app. The demo sign-in creates only a browser session marker; it is not authentication. The API remains unauthenticated. Do not expose it to the public internet or enter confidential data.

## Project layout

```text
frontend/   React + Vite UI and frontend tests
backend/    FastAPI service, Pydantic request/response models, SQLAlchemy persistence, API tests
docs/       Architecture and live-data integration notes
```

## Workspace sections

- **Discovery** manages the operator-entered artist directory and shows the actual provider and measurement status.
- **Live catalog search** calls the Python backend, which searches MusicBrainz by artist/keyword, configured region, or genre. Results can be opened at MusicBrainz and saved to the local directory with provenance.
- **Analyze** explains which evidence is unavailable; it does not display placeholder charts or inferred metrics.
- **Recommend** stays empty until authorized evidence and a validated recommendation model exist.
- **Settings** controls saved discovery region, genre, result count, and optional auto-search when Discovery opens. It also reports backend/database status and provider availability.

The artist search filters records loaded from the API, and the directory can load additional records when needed. Empty states describe missing data rather than filling the dashboard with sample artists or invented results. Discovery auto-search runs at most once per app entry and respects MusicBrainz's request limits.

## Run the backend

Requires Python 3.10+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install -r requirements.txt
cp .env.example .env               # optional; SQLite defaults to backend/data/breakout_radar.db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If the project folder is moved and a command reports a `bad interpreter` path, recreate the virtual environment from `backend/` because virtual environments contain absolute paths:

```bash
deactivate  # if the old environment is active
python3 -m venv --clear .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

API health: `http://127.0.0.1:8000/api/health`  
Interactive API docs: `http://127.0.0.1:8000/docs`

SQLite is created on first startup. For PostgreSQL, set `DATABASE_URL` to a SQLAlchemy URL such as `postgresql://user:password@localhost:5432/breakout_radar`; the PostgreSQL driver is included.

Before deployment, set `MUSICBRAINZ_CONTACT` to a real maintainer email or contact URL. MusicBrainz requires a meaningful User-Agent and limits clients to one request per second. Local development defaults to the frontend's localhost URL.

## Run the frontend separately

Requires Node 20.19+.

```bash
cd frontend
npm ci
npm run dev
```

Vite runs at `http://127.0.0.1:5173` and proxies `/api` requests to the Python service on port 8000. Set `API_PROXY_TARGET` to use a different backend URL. Build and test the client from `frontend/`:

```bash
npm test
npm run build
```

Run backend tests separately from `backend/`:

```bash
python -m pytest
```

## API capabilities

- `GET /api/health` reports database connectivity, demo authentication status, and the configured MusicBrainz catalog.
- `GET /api/providers` lists MusicBrainz availability and clearly marks Spotify/YouTube as not integrated.
- `GET /api/discovery/search?query=...&area=...&genre=...&limit=10` retrieves current artist metadata from MusicBrainz. At least one filter is required.
- `GET /api/artists?limit=50&offset=0` lists persisted identities.
- `POST /api/artists` adds an operator-submitted or explicitly saved provider identity and source URL.
- `GET`, `PATCH`, and `DELETE /api/artists/{id}` manage a single identity record.

The API rejects unknown fields such as audience counts or scores. A MusicBrainz search never saves a record automatically; the operator must choose **Add to directory**. Results are catalog matches, not a discovery ranking or claim of artist potential.

## Current limitations

- Authentication is disabled and clearly marked. API access is not protected; keep the service bound to localhost.
- MusicBrainz provides identity/catalog metadata only; this search does not provide audience growth or popularity evidence.
- Spotify and YouTube adapters are not implemented. Spotify requires an approved application and credentials; YouTube Data API requires an API key and quota. Review provider terms before adding either integration.
- The sign-in flow is a UI-only demo, not authentication. API access is unprotected.
- Database tables are created automatically for local development; production deployment needs migrations, real authentication/authorization, backups, and operational monitoring.
# ARTIST_BREAK_APP
