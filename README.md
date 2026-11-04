# Breakout Radar — A&R Intelligence

Breakout Radar is an Africa-first artist discovery and A&R research workspace. It is built around four primary sections:

1. **Discovery** — search configured catalogues and public sources, group source identities, and review emerging-artist candidates.
2. **Analyse** — inspect source-attributed observations and linked evidence, then complete a structured artistic review.
3. **Recommendations** — combine discovery evidence with artistic judgement and record explicit A&R decisions.
4. **Settings** — configure 73 data-source entries, credentials, discovery seeds, guardrails and scoring weights.

The UI borrows the dark, high-contrast, chart-led design language of the pixel-perfect-replica demo. Its data model and operating workflows are a new implementation for this repository.

## What is implemented

### Discovery and source integration

- 73 distinct source entries in the settings directory.
- 22 identity-search adapters: the 16 existing catalogue integrations plus Wikipedia, iTunes Search, Bluesky, Mastodon, setlist.fm and Twitch Helix.
- 4 evidence-enrichment adapters: GDELT, Reddit, Flickr and Openverse.
- The remaining entries are explicitly classified as requiring app approval, OAuth scopes, artist authorisation, partner access, commercial licensing, research eligibility, manual feed configuration or a client-side implementation.
- Concurrent discovery is bounded, uses per-source credentials, and reports identity records as candidates rather than silently promoting them to the artist directory.
- Cross-source artist grouping uses a normalized-name key and retains provider identifiers separately.
- Accepted identities are rechecked on later scans. New metric observations are appended with provider, metric, scope, timestamp and source URL.

**A catalogue entry is not a claim that its provider is connected.** A source displays Ready when the application has an implemented adapter and its locally required credentials are present. This is not a live credential-validation guarantee. Sources with restricted access are not called by discovery just because they appear in the directory.

### Analysis and decision support

- Historical metric observations remain source-specific; Deezer fans, YouTube channel values and any other provider values are not summed into a synthetic global audience count.
- Growth calculations require at least the configured observation history (seven days by default).
- Source coverage and missing dimensions affect confidence.
- Press/community/media items are stored as evidence links with source and context.
- The artistic rubric captures songwriting, vocals, melody, production, originality, performance and artist identity.
- Artistic reviews record reviewer, notes, track reference, strengths, risks and evidence references.
- Recommendations use configurable weighted discovery/artistic scores. Without a completed artistic review, an artist remains on Hold.
- Scores are ranking indices, not probabilities of commercial success.

### Credentials and quota management

- Provider credentials are encrypted at rest using Fernet.
- YouTube search requests are reserved against a persistent daily budget (80 by default) using Google's midnight-Pacific reset day, including daylight-saving changes.
- A manual discovery run has an estimated upstream-call ceiling (MAX_PROVIDER_CALLS_PER_SEARCH, default 100).
- Scheduled discovery is opt-in and runs through a separate worker process.
- API and worker should be run as one worker each against the same database until distributed locking is configured.

## Architecture

- **Frontend:** React 18 + Vite 8.
- **API:** FastAPI + Pydantic 2.
- **Persistence:** SQLAlchemy 2 with SQLite by default; PostgreSQL is supported by the configured driver.
- **Source layer:** curated registry, official API adapters, source-specific credentials and evidence collectors.
- **Worker:** optional process using the same discovery use case; it is not started by every API server.
- **Scoring:** deterministic Python functions with configurable weights and explicit missing-data handling.

New v3 tables use the radar_* namespace and do not drop the previous app's tables. create_all() creates missing tables; it does not migrate existing tables. Introduce Alembic migrations before making schema changes to an existing production database.

## Requirements

- Python 3.11+ (CI uses Python 3.13).
- Node.js 24.15+ and npm.
- Internet access for the external sources you choose to enable.
- A Fernet key if you intend to save credentialed integrations.

## Local setup

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

On macOS/Linux, use `cp .env.example .env` instead of `copy`.

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the result into PROVIDER_SECRETS_KEY in backend/.env. Preserve this key securely; credentials cannot be decrypted without the same key.

Start the API from the backend/ directory:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation is at http://127.0.0.1:8000/docs.

### 2. Frontend

In a separate terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173.

### 3. Optional scheduled discovery worker

Enable Scheduled discovery in Settings, then start one worker in a separate terminal:

```bash
cd backend
# Activate the same backend virtual environment first.
python -m app.worker
```

The worker reads the configured source selection and discovery seeds and runs on the saved interval. Leave it off for manual-only operation. Do not run multiple copies with SQLite or without distributed locking.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| DATABASE_URL | sqlite:///./data/breakout_radar.db | SQLAlchemy database URL |
| CORS_ORIGINS | Vite localhost origins | Allowed browser origins |
| LOG_LEVEL | INFO | Python log level |
| MUSICBRAINZ_CONTACT | repository issue URL | Maintainer contact in MusicBrainz User-Agent |
| PROVIDER_SECRETS_KEY | unset | Fernet key for encrypted credentials |
| YOUTUBE_SEARCH_DAILY_BUDGET | 80 | YouTube search.list request budget per Pacific-time day |
| MAX_PROVIDER_CALLS_PER_SEARCH | 100 | Estimated upstream requests permitted by one discovery run |

backend/.env.example is the template. Do not commit .env or share provider credentials.

## Tests and build

```bash
# Backend
cd backend
python -m pytest

# Frontend
cd ../frontend
npm ci
npm test
npm run build
```

GitHub Actions runs backend tests, frontend tests, a production build and ZIP integrity validation. A downloadable ARTIST_BREAK_APP.zip artifact is published only after all three CI jobs pass. The archive includes source and production frontend assets; it excludes .env, databases, virtual environments and node_modules.

## Operational and data-governance limits

- The API does not currently implement user authentication or workspace isolation. It binds to loopback by default. Do not expose it publicly.
- Source readiness is based on adapter and credential configuration, not a remote health check.
- Many platform APIs do not permit arbitrary competitor analytics. YouTube Analytics requires channel-owner OAuth; Meta insights require authorised professional accounts; TikTok Display requires approved scopes and creator authorisation; LinkedIn products are restricted.
- TikTok Research API and Meta Content Library are research-only/eligibility-gated entries, not commercial integrations.
- Spotify content must not be used to derive listenership metrics or train models. Spotify catalogue metadata is retained only as catalogue identity data.
- Chartmetric, Soundcharts, Songstats, Viberate, Luminate, Mediabase and similar feeds require commercial contracts.
- Google Trends API access is limited; no unofficial scraping fallback is used.
- Manual RSS/chart/artist-URL entries require operator rights and review.
- Audio understanding and AI-generated listening reviews are not claimed as live. The current artistic rubric is a human review workflow.

See docs/DATA_SOURCES.md, docs/ARCHITECTURE.md and docs/scoring-method.md.

## Product scope still to build

The current rebuild establishes the source registry, working API adapters, historical source observations, a human artistic review workflow and transparent decisions. Before a public multi-user deployment, the remaining work is authentication, workspace isolation, Alembic migrations, distributed worker locking, deeper provider contract tests, audio ingestion/consent, and a validated predictive model trained on authorised historical outcomes.
