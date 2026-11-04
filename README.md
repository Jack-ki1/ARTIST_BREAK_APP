# Breakout Radar

Breakout Radar is a local-first artist discovery and identity-review workspace.
It lets an operator search supported music and knowledge catalogs, inspect
provider-attributed artist records, maintain a small artist directory, and
review new identities collected by a scheduled background search.

The application is intentionally conservative about what catalog data means.
A catalog match confirms only that a provider returned an identity record. It
does not establish that an artist is emerging, popular, growing, or suitable
for signing.

> **Current deployment boundary:** the API has no caller authentication.
> Keep it on loopback or behind a trusted, access-controlled network.
> Provider credentials must not be entered from an untrusted browser session.

## Contents

- [Project status](#project-status)
- [What works today](#what-works-today)
- [What is not implemented](#what-is-not-implemented)
- [Technology](#technology)
- [Repository map](#repository-map)
- [Application architecture](#application-architecture)
- [Runtime request and data flows](#runtime-request-and-data-flows)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Run and stop the services](#run-and-stop-the-services)
- [Artist provider catalog](#artist-provider-catalog)
- [Provider setup and readiness](#provider-setup-and-readiness)
- [Provider selection guidelines](#provider-selection-guidelines)
- [Discovery behavior](#discovery-behavior)
- [Regional search shortcuts](#regional-search-shortcuts)
- [Manual catalog search](#manual-catalog-search)
- [Scheduled discovery](#scheduled-discovery)
- [Review queue](#review-queue)
- [Artist directory](#artist-directory)
- [HTTP API reference](#http-api-reference)
- [Data model](#data-model)
- [Validation and response conventions](#validation-and-response-conventions)
- [Credential protection](#credential-protection)
- [Database and persistence](#database-and-persistence)
- [Frontend guide](#frontend-guide)
- [Backend guide](#backend-guide)
- [Environment variable reference](#environment-variable-reference)
- [Testing](#testing)
- [Build and CI](#build-and-ci)
- [Common operational issues](#common-operational-issues)
- [Known limitations](#known-limitations)
- [Privacy, permissions, and source terms](#privacy-permissions-and-source-terms)
- [Documentation map](#documentation-map)
- [Contribution workflow](#contribution-workflow)
- [Security reporting](#security-reporting)
- [License](#license)

## Project status

The functional application currently lives in the `backend/` and `frontend/`
directories. The `apps/`, `packages/`, and `infra/` directories are architectural
placeholders for a possible future monorepo organization. They do not currently
contain a second implementation of the API, web app, worker, or contracts.

The running application provides:

1. A React workspace served by Vite during development.
2. A FastAPI HTTP API for artists, discovery, providers, and service health.
3. A SQLAlchemy persistence layer using SQLite by default.
4. Sixteen provider adapters with common response normalization.
5. A 15-minute scheduler running inside the API process.
6. A human-review queue between scheduled matches and saved artist records.

The current database intentionally contains identity and configuration data,
not audience analytics. Empty analysis, signal, and recommendation areas in the
interface are explanatory placeholders, not computed product features.

## What works today

### Artist discovery

- Search enabled provider catalogs by artist text, region, or genre.
- Configure multiple comma-separated regions and genres in Settings.
- Receive normalized identity data with provider IDs and source URLs.
- Expand the supported East Africa and Central Africa shortcuts into
  country-level MusicBrainz searches.
- See provider-specific errors when a provider is missing credentials or
  rejects a request.

### Scheduled collection

- Enable or pause the recurring discovery scheduler in Settings.
- Set a result limit and a list of region and/or genre filters.
- Search each configured region/genre combination every 15 minutes while the
  backend process remains up.
- Store newly observed identities in a review queue.
- Deduplicate queue items by provider ID and the provider's external ID.
- Accept or dismiss pending items through the application.

The browser does not need to remain open for the scheduler to run. The backend
does need to remain running. Scheduled searches are skipped if both region and
genre filters are empty, if scheduled discovery is disabled, or if no provider
is enabled.

### Artist identity directory

- Add an artist manually with optional place, genre, and source information.
- Accept a queued catalog candidate into the directory.
- List, paginate, retrieve, update, and delete artist records.
- Preserve the provider name and source URL when an operator accepts a result.

### Provider administration

- Enable or disable each implemented provider.
- View whether a provider is enabled and whether its required fields are
  configured.
- Submit, replace, or remove provider credential fields in Settings.
- Encrypt saved provider credentials in the backend database.
- Keep saved credential values out of provider status responses.

## What is not implemented

The following items must not be inferred from the current interface or catalog
results:

- Authentication, user accounts, roles, or workspace isolation.
- Popularity, followers, streams, audience composition, or growth metrics.
- Audio feature extraction, audio quality measurement, or listening-session
  annotations.
- Artist potential scores, recommendations, or automated sign/no-sign
  decisions.
- A production-ready signal ingestion pipeline.
- A separate worker process or deployment orchestration.
- Database schema migrations.
- Provider quota planning across all scheduled filter combinations.
- Exhaustive live verification of every provider adapter.

The Analyze and Recommend sections explain which evidence would be required
before those features can make reliable claims. They do not currently calculate
scores or produce recommendations.

## Technology

| Layer | Technology | Current responsibility |
|---|---|---|
| Browser UI | React 18 | Workspace screens and user interactions |
| Frontend build/dev server | Vite | Bundling, local web server, and API proxy |
| Browser tests | Vitest and jsdom | UI/API behavior checks without a real browser |
| API | FastAPI | HTTP routes, validation, and OpenAPI docs |
| ASGI server | Uvicorn | Backend process and development reload |
| Validation | Pydantic | API request and response schemas |
| ORM | SQLAlchemy 2 | Models, sessions, and queries |
| Local database | SQLite | Default persistent store |
| Optional database | PostgreSQL | Supported using the psycopg driver |
| HTTP client | HTTPX | Async requests to external providers |
| Secret storage | cryptography / Fernet | Encryption of provider credentials at rest |
| Environment loading | python-dotenv | Loads `backend/.env` when the database module imports |

## Repository map

This tree lists the project's application, test, configuration, and
documentation files. Generated build output, installed packages, virtual
environments, and local database files are omitted.

```text
.
├── .editorconfig
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── .pre-commit-config.yaml
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── README.md
├── SECURITY.md
├── ai.md
├── apps/
│   ├── README.md
│   ├── api/
│   │   └── README.md
│   ├── web/
│   │   └── README.md
│   └── worker/
│       └── README.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── providers.py
│   │   ├── quotas.py
│   │   ├── scheduler.py
│   │   ├── schemas.py
│   │   └── secrets.py
│   └── tests/
│       └── test_api.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_SOURCES.md
│   ├── ROADMAP.md
│   ├── data-sources.md
│   ├── scoring-method.md
│   └── adr/
│       └── README.md
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── main.jsx
│   │   └── styles.css
│   └── tests/
│       ├── app.test.jsx
│       └── setup.js
├── infra/
│   └── README.md
└── packages/
    └── contracts/
        └── README.md
```

### Root-level files

| File | Purpose |
|---|---|
| `.editorconfig` | Shared indentation, line endings, and whitespace defaults |
| `.gitignore` | Excludes local environments, secrets, generated assets, and data |
| `.pre-commit-config.yaml` | Optional whitespace, format, lint, and secret checks |
| `CONTRIBUTING.md` | Contribution workflow and basic project conventions |
| `LICENSE` | MIT license terms |
| `Makefile` | Convenience targets for development, tests, lint, and migration notes |
| `README.md` | Main product, setup, architecture, API, and operations guide |
| `SECURITY.md` | Vulnerability reporting and deployment security reminders |
| `ai.md` | Summary of changes and operational findings from the assisted work |

### Backend files

| File | Purpose |
|---|---|
| `backend/.env.example` | Example environment variables; copy to ignored `backend/.env` |
| `backend/requirements.txt` | Python runtime and test dependencies |
| `backend/app/__init__.py` | Marks `app` as a Python package |
| `backend/app/database.py` | Loads database settings, builds SQLAlchemy engine/sessions, and creates tables |
| `backend/app/main.py` | FastAPI app, lifecycle, CORS, routes, persistence actions, and error mapping |
| `backend/app/models.py` | SQLAlchemy tables for artists, settings, credentials, and discovery candidates |
| `backend/app/providers.py` | Provider catalog, request adapters, normalization, regional expansion, readiness, and aggregation |
| `backend/app/quotas.py` | Persistent daily request-budget reservations for quota-limited integrations |
| `backend/app/scheduler.py` | Periodic multi-provider searches and queue persistence |
| `backend/app/schemas.py` | Pydantic request/response validation and field limits |
| `backend/app/secrets.py` | Fernet key validation and credential encryption/decryption |
| `backend/tests/test_api.py` | API, scheduler, provider settings, and identity behavior tests |

### Frontend files

| File | Purpose |
|---|---|
| `frontend/package.json` | Frontend dependencies, scripts, and supported Node version |
| `frontend/package-lock.json` | Reproducible npm dependency resolution |
| `frontend/index.html` | Browser document shell, metadata, and React root element |
| `frontend/vite.config.js` | Vite React plugin, development API proxy, and Vitest settings |
| `frontend/src/main.jsx` | Creates the React root and imports the app and styles |
| `frontend/src/App.jsx` | Workspace state, discovery UX, settings, queue, directory, and empty modules |
| `frontend/src/api.js` | Fetch wrapper and typed-by-convention API functions |
| `frontend/src/styles.css` | Application styling and responsive layouts |
| `frontend/tests/app.test.jsx` | UI flows, settings, search, and error-display tests |
| `frontend/tests/setup.js` | Vitest/jsdom test environment initialization |

### Documentation and scaffolding

| Path | Purpose and implementation status |
|---|---|
| `docs/ARCHITECTURE.md` | Data model and runtime trust boundaries |
| `docs/DATA_SOURCES.md` | Current provider capabilities, terms reminders, and search prerequisites |
| `docs/ROADMAP.md` | Known implementation and production-readiness gaps |
| `docs/data-sources.md` | Compatibility note linking to the current source guide |
| `docs/scoring-method.md` | Principles for a future explainable human-reviewed rubric |
| `docs/adr/README.md` | Placeholder instructions for architecture decision records |
| `apps/README.md` | Description of the intended future app/package layout |
| `apps/api/README.md` | Placeholder for a future API app; live API remains in `backend/` |
| `apps/web/README.md` | Placeholder for a future web app; live UI remains in `frontend/` |
| `apps/worker/README.md` | Placeholder for a future worker; scheduler currently runs in API process |
| `packages/contracts/README.md` | Placeholder for shared schemas and generated clients |
| `infra/README.md` | Placeholder for deployment and infrastructure configuration |

## Application architecture

```text
Browser
  React workspace (frontend/src/App.jsx)
    API helper (frontend/src/api.js)
      GET/POST/PUT/PATCH/DELETE /api/*
        FastAPI routes (backend/app/main.py)
          Pydantic schemas (backend/app/schemas.py)
          Provider adapters (backend/app/providers.py)
          SQLAlchemy models (backend/app/models.py)
            Database engine and sessions (backend/app/database.py)

Backend process lifecycle
  FastAPI lifespan
    creates missing tables
    starts one asynchronous discovery scheduler task
      queries enabled providers
      persists new/updated candidates
    cancels scheduler task at shutdown
```

### API process lifecycle

1. Importing `app.main` imports the configured SQLAlchemy engine.
2. `backend/app/database.py` loads `backend/.env` if present.
3. When FastAPI starts, its lifespan hook creates any missing model tables.
4. The lifespan hook starts one in-process scheduler task.
5. On shutdown, the task is cancelled and awaited.
6. Uvicorn exits after application shutdown completes.

`Base.metadata.create_all()` creates missing tables but does not migrate changed
schemas. Existing installations may need a migration or a deliberate local
database recreation when the model schema changes.

### Trust boundaries

- Browser API calls are proxied to the local backend during Vite development.
- External provider calls originate in the backend, not browser JavaScript.
- Provider credentials are encrypted before being written to the database.
- Provider readiness responses expose configured field names, never secret
  values.
- The API does not authenticate or authorize callers.
- An enabled API provider may return catalog metadata only; it does not prove a
  license to reuse that metadata for every purpose.

## Runtime request and data flows

### Manual search

1. The operator enters an artist, area, or genre in Discovery.
2. The browser requests `/api/discovery/search` with the selected filters.
3. FastAPI loads the enabled provider IDs and decrypts saved credentials.
4. The provider aggregator checks whether each enabled source has required
   credentials.
5. Each configured source is queried and normalized into the shared
   `DiscoveryArtist` shape.
6. Successful items and provider-specific errors are returned.
7. Manual search results remain transient until the operator explicitly adds
   one to the directory.

Manual search does not create review queue records. The scheduled job is the
path that writes catalog matches to the review queue.

### Scheduled search

1. The scheduler checks that recurring discovery is enabled.
2. It loads saved areas, genres, result limit, enabled providers, and secrets.
3. It expands configured East Africa / Central Africa shortcuts into countries.
4. It makes one provider call per provider/filter combination.
5. For each match, it looks up the `(provider_id, external_id)` identity.
6. New matches are inserted; known matches have their metadata and last-seen
   fields updated.
7. A human accepts or dismisses candidates from the queue.

### Candidate acceptance

1. The UI sends a `PATCH` with status `accepted`.
2. The API verifies that the candidate exists and is still pending.
3. The API checks whether an artist with the same provider and source URL is
   already present.
4. If absent, it creates an artist identity from candidate name, country, area,
   tags, provider ID, and source URL.
5. The candidate status is committed as `accepted`.

The directory is not an automatically generated dump of search results.
Acceptance is explicit.

## Requirements

### Backend

- Python 3.10 or later is the documented minimum.
- `pip` for installing dependencies.
- Network access to the selected external provider APIs.

The CI workflow tests the backend with Python 3.13.

### Frontend

- Node.js 24.15 or later (matches the locked Vite/Vitest/jsdom toolchain).
- npm (the lockfile should be used with `npm ci`).

### Optional services

- PostgreSQL can be selected using `DATABASE_URL`.
- A credential-encryption key is needed if provider API credentials are saved.
- No external queue service is required; the scheduler is in-process.

## Quick start

Run the backend and frontend in separate terminals for the clearest development
logs and lifecycle control.

### 1. Create backend environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PowerShell activation:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Configure backend environment

```bash
cp .env.example .env
```

Generate a Fernet encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the generated value after `PROVIDER_SECRETS_KEY=` in `backend/.env`.
Treat the value as a long-lived secret. Do not commit the `.env` file.

### 3. Start the API

From the `backend/` directory, with its Python environment active:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The first successful startup creates the configured database tables.

### 4. Start the web app

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`.

### 5. Confirm the API

```bash
curl http://127.0.0.1:8000/api/health
```

Interactive API documentation is available at
`http://127.0.0.1:8000/docs`; the OpenAPI schema is at
`http://127.0.0.1:8000/openapi.json`.

## Configuration

The backend reads `backend/.env` when `app.database` imports. The file is
ignored by Git. Values can also be supplied through the process environment.

### Configuration sequence

1. Start the backend once to create the database schema.
2. Configure `PROVIDER_SECRETS_KEY` before saving credentialed providers.
3. Open **Settings → Data providers** and select sources.
4. Supply each enabled provider's required credentials.
5. Open **Settings → Search preferences**.
6. Enter one or more areas or genres.
7. Confirm recurring discovery is enabled and save.
8. Leave the backend process running for recurring searches.

### Provider credential storage behavior

- An empty credential input leaves an existing saved value unchanged.
- A non-empty input replaces the saved value for that field.
- The explicit remove checkbox clears a saved value.
- Credentials are only returned as a list of configured field names.
- `PROVIDER_SECRETS_KEY` must remain identical to decrypt existing saved data.

## Run and stop the services

### Individual processes

Backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Stop either development server with `Ctrl+C` in its terminal.
Stopping Uvicorn also stops the in-process scheduler. Restarting Uvicorn starts
the scheduler again.

### Make targets

From the repository root:

```bash
make dev
make test
make lint
make migrate
```

The `dev` target starts backend and frontend processes together. `test` runs
backend and frontend tests. The `lint` target invokes Ruff and ESLint commands,
but currently allows failures with `|| true`, so its exit status is not a
reliable quality gate. The `migrate` target is informational: no Alembic
migration is configured.

## Artist provider catalog

Provider adapters are listed in `backend/app/providers.py`. Settings shows the
provider name, readiness status, description, required credential inputs, and
a link to the provider's own documentation.

| Provider | Required configuration | Catalog/search behavior | Important caveat |
|---|---|---|---|
| MusicBrainz | None | Artist identities, areas, tags, disambiguation | Community catalog; requests throttled to about one per second |
| Wikidata | None | Entity label and description search | Sparse coverage for emerging/local acts |
| Deezer | None for implemented search | Artist catalog search | API availability and terms may change |
| Spotify | Client ID and client secret | Artist catalog search | Developer access and commercial-use limits apply |
| YouTube Data API | API key | Channel search | Search quota may be consumed quickly |
| Apple Music | Developer token; optional storefront | Storefront-specific artist catalog | Results depend on storefront and token access |
| Last.fm | API key | Artist search | Commercial access requires provider approval |
| Discogs | Personal access token | Artist/release catalog search | Terms restrict reuse of some fields and images |
| Google Knowledge Graph | API key | Knowledge-graph entity lookup | Notability ranking can omit emerging artists |
| TheAudioDB | API key | Artist catalog lookup | Check tier, subscription, and commercial terms |
| Jamendo | Client ID | Independent-music artist catalog | API access does not confer recording-use rights |
| Audius | Application name | Creator profile search | Catalog is specific to Audius |
| Ticketmaster Discovery | API key | Music attraction/event lookup | Market and event coverage varies |
| SoundCloud | Client ID and client secret | User/creator profile search | Requires an approved app and current API access |
| Musixmatch | API key | Artist catalog search | Lyrics are not included; lyric display needs separate rights |
| Genius | Access token | Song search, deduplicated primary artists | Commercial API use requires a separate license |

### Provider implementation is not provider approval

The UI's **Ready** status means that required input fields have been saved. It
does not validate credentials with the provider and does not guarantee that
the endpoint, account, quota, or terms will permit a particular request.

An adapter can fail later with an HTTP status, timeout, invalid response, or
provider-specific error. The application reports search errors rather than
substituting sample results.

### Metadata coverage is not uniform

The shared response shape contains identity-oriented fields. Some providers
return rich areas and tags, while others return only a name and canonical
source URL. Empty optional fields are expected and do not imply a failed
request.

Provider results are not automatically reconciled across services. The same
artist may appear as several candidates because each provider's ID namespace is
different. The queue's duplicate key is provider plus external ID, not a
global artist identity match.

## Provider setup and readiness

### No-key provider setup

MusicBrainz, Wikidata, and Deezer do not require credentials for the
implemented request paths. Enable them in Settings and save the provider
selection.

MusicBrainz asks clients to identify themselves and limits request frequency.
The example value points to this repository's issue tracker. Replace it with a
maintainer-owned contact URL or email before public deployment.

### Credentialed provider setup

For each provider:

1. Follow its official developer onboarding process.
2. Confirm that the API product and account permit your intended use.
3. Create or obtain the required API key, application credentials, or token.
4. Enable the provider in Settings.
5. Enter the required fields and save.
6. Trigger a manual search with a term likely to exist in that catalog.
7. Check the result and any provider-specific error.

### Spotify credentials

Provide the application's client ID and client secret. The backend exchanges
these for a client-credentials access token and caches that token in process
until shortly before expiry.

### SoundCloud credentials

Provide the client ID and client secret. The backend uses the client
credentials flow and caches the access token in process. Access requires an
approved application and can change with SoundCloud API policy.

### Apple Music credentials

Provide a valid developer token. The optional storefront field defaults to
`us` when not configured. Storefront choice affects catalog availability.

### Other credential fields

YouTube, Last.fm, Discogs, Knowledge Graph, TheAudioDB, Jamendo, Ticketmaster,
Musixmatch, and Genius take the field shown in Settings. Audius takes an
application name and uses a public catalog endpoint.

## Provider selection guidelines

Provider selection is a trade-off among coverage, access, licensing, request
limits, geographic availability, and maintenance.

### Starting with public/keyless catalogs

Enable MusicBrainz, Wikidata, and Deezer to compare identity coverage without
first requesting credentials. These sources do not share identical search
semantics or metadata coverage.

### Enabling key-based sources

Add a key-based integration only after:

- Confirming account approval and API product availability.
- Reviewing the current terms and intended use.
- Checking quota and rate-limit requirements.
- Deciding how to handle data freshness, retention, and deletion.
- Confirming the provider can be accessed from the deployment environment.

### Keep scheduled load bounded

The current scheduler runs every configured provider across every expanded
region/genre combination. Large lists can create many upstream calls. YouTube
search quota is a particular concern, and the application currently does not
implement provider-specific daily quota accounting.

Start with a small number of filters and providers. The settings schema allows
up to ten raw areas and ten raw genres, and rejects more than one hundred
unexpanded combinations. Regional shortcuts expand to more calls than the
unexpanded combination count indicates.

## Discovery behavior

### Search filters

At least one search term must be present for a manual query:

- `query`: artist name or keyword
- `area`: country, region, or supported region shortcut
- `genre`: genre or scene text

The frontend can combine a typed artist query with saved areas and genres. It
requests each area/genre pair separately and merges results by provider-scoped
candidate ID.

### Result limits

- The API accepts `limit` values from 1 through 25.
- The scheduled settings result limit defaults to 10.
- Settings enforce a maximum of 25.
- A provider may impose a lower maximum.
- Offset support and offset interpretation vary among provider APIs.

### Source provenance

Each normalized result includes:

- `provider_id`: this application's provider identifier
- `external_id`: provider-native identity
- `source_url`: canonical provider URL when available
- `name`: normalized artist/act name
- optional country, area, type, description, and tags

The result's `id` is namespaced by provider to avoid collisions between
different provider ID formats.

## Regional search shortcuts

The scheduler and manual search expand two named area shortcuts into
country-level MusicBrainz area searches:

### East Africa

- Burundi
- Comoros
- Djibouti
- Eritrea
- Ethiopia
- Kenya
- Madagascar
- Malawi
- Mauritius
- Mozambique
- Rwanda
- Seychelles
- Somalia
- South Sudan
- Tanzania
- Uganda
- Zambia
- Zimbabwe

### Central Africa

- Angola
- Cameroon
- Central African Republic
- Chad
- Congo
- Democratic Republic of the Congo
- Equatorial Guinea
- Gabon
- Sao Tome and Principe

This list uses country-level names; territories are excluded. The regional
shortcut currently expands before provider invocation, so region expansion is
applied to enabled providers, not only to MusicBrainz. Other providers may
interpret a country string differently or ignore area filters. Use specific
country names if a provider does not support a regional expansion as expected.

These are operational shortcuts defined in the application, not claims that
all organizations use the same definition of either region.

## Manual catalog search

Manual search is initiated from Discovery and does not require the scheduler to
be enabled. It requires a non-empty query, area, or genre. Provider errors are
returned alongside any successful items.

If a result appears, use its provider link to verify the identity. Select
**Add to directory** only when the identity and source are appropriate for the
workspace. The manual search itself does not persist the result.

If search returns no items:

1. Confirm at least one provider is enabled.
2. Confirm the enabled provider is marked Ready in Settings.
3. Try a full artist name or a shorter query.
4. Remove filters that may be too restrictive.
5. Check the displayed provider errors.
6. Verify the provider's official endpoint, account access, and quota.

An empty result is a valid outcome; the application does not fabricate a
candidate to make the screen look populated.

## Scheduled discovery

### Requirements for collection

All of the following must be true:

1. The backend process is running.
2. The discovery setting is enabled.
3. At least one area or one genre is configured.
4. At least one provider is enabled.
5. The provider is configured and reachable.

If there are no areas but one or more genres, the scheduler searches each genre
without an area filter. If there are areas but no genres, it searches each area
without a genre filter. If both lists are empty, the cycle logs a skip and
returns without making a provider request.

### Cadence

The scheduler interval is 900 seconds (15 minutes). A scheduler cycle starts
immediately when the API starts, then waits for the remaining interval after
the cycle completes. Updating discovery settings wakes the scheduler so it
does not need to wait for the full interval before using the new settings.

### Process and worker limitations

- The scheduler is tied to one Uvicorn application process.
- Use one backend worker with the current configuration.
- Running multiple workers would start duplicate scheduler tasks.
- A process restart interrupts an in-progress cycle.
- A stopped backend does not perform background work.
- There is no separate worker deployment or shared distributed lock.

### Queue update rules

The scheduler processes one search pair and provider at a time. A new
provider-scoped external ID is inserted as pending. If the ID already exists,
the candidate fields and `last_seen_at` are updated.

The duplicate check is enforced by application lookup and a database unique
constraint on `(provider_id, external_id)`. Database races or provider data
inconsistencies can still surface as logged errors; the scheduler does not
silently convert unexpected exceptions into success.

## Review queue

Queue statuses are:

| Status | Meaning |
|---|---|
| `pending` | Waiting for operator review |
| `accepted` | Operator approved its identity for the directory |
| `dismissed` | Operator rejected it for current intake |

The default queue endpoint returns pending candidates. Request
`status=accepted`, `status=dismissed`, or `status=all` to inspect other states.

Acceptance creates an identity row if a matching provider/source URL is not
already present. Dismissal only changes the candidate status. A candidate can
only be reviewed once; an already reviewed item returns a conflict response.

The queue is provider-specific. A matching performer from another provider is
not guaranteed to be recognized as the same person or act.

## Artist directory

The artist directory is a local identity list. Each record contains:

- Generated UUID.
- Required artist/act name.
- Optional country, city, and genre.
- Optional source name and URL.
- Created and updated timestamps.

The API rejects unknown fields such as arbitrary score or audience fields.
Directory writes are intentional operator actions, either through the manual
artist form or queue acceptance.

The current UI supports listing, filtering the loaded page, adding a record,
and deleting a record. The API supports single-record retrieval and patching
even when those operations are not exposed as direct workspace controls.

## HTTP API reference

All routes are prefixed with `/api`. FastAPI's `/docs` and `/openapi.json` are
outside that prefix.

### Health

#### `GET /api/health`

Checks that a database connection can execute `SELECT 1`. Returns:

- `status`: application health marker (`ok` on success).
- `database`: database status (`connected` on success).
- `authentication`: currently `disabled`.
- `configured_data_providers`: IDs that are both enabled and have required
  credential fields.

This endpoint does not test each provider's network health or validate API
credentials against provider servers.

### Provider settings

#### `GET /api/providers`

Returns the catalog of 16 provider definitions with status, enabled flag,
required credential field metadata, documentation URL, access note, and names
of fields known to be configured. Secret values are never returned.

#### `PUT /api/providers`

Replaces the enabled provider list and applies credential updates/removals.
Request shape:

```json
{
  "enabled_provider_ids": ["musicbrainz", "spotify"],
  "credential_updates": {
    "spotify": {
      "client_id": "your-client-id",
      "client_secret": "your-client-secret"
    }
  },
  "clear_credentials": []
}
```

`enabled_provider_ids` is limited to 16 known IDs. Unknown provider IDs and
unknown credential field names are rejected. Blank submitted values do not
overwrite saved values. Credential updates require a valid
`PROVIDER_SECRETS_KEY`.

### Discovery settings

#### `GET /api/discovery/settings`

Returns configured area filters, genre filters, result limit, enabled flag,
last update time, and the interval in seconds.

#### `PUT /api/discovery/settings`

Stores:

```json
{
  "areas": ["East Africa"],
  "genres": ["Afrobeats"],
  "result_limit": 10,
  "enabled": true
}
```

The API accepts up to ten unique, non-blank values in each list. It accepts no
more than 100 combinations before regional expansion. The result limit ranges
from 1 through 25. Saving settings wakes the running scheduler.

### Manual discovery

#### `GET /api/discovery/search`

Query parameters:

| Parameter | Type | Default | Bounds |
|---|---|---:|---|
| `query` | string | none | 1–120 characters when supplied |
| `area` | string | none | 1–120 characters when supplied |
| `genre` | string | none | 1–120 characters when supplied |
| `limit` | integer | 10 | 1–25 |
| `offset` | integer | 0 | 0–1000 |

At least one of query, area, or genre is required. Response:

```json
{
  "items": [],
  "count": 0,
  "offset": 0,
  "errors": []
}
```

Successful results from multiple enabled providers are combined. Each provider
error is returned in `errors`; one provider failure does not erase successful
results from other providers.

### Discovery queue

#### `GET /api/discovery/queue`

Query parameters:

| Parameter | Type | Default | Bounds |
|---|---|---:|---|
| `status` | string | `pending` | `pending`, `accepted`, `dismissed`, `all` |
| `limit` | integer | 50 | 1–200 |
| `offset` | integer | 0 | 0 or greater |

Returns `items`, `total`, `limit`, and `offset`. Items are ordered by most
recently observed, then name.

#### `PATCH /api/discovery/queue/{candidate_id}`

Accepts one review status:

```json
{
  "status": "accepted"
}
```

Allowed values are `accepted` and `dismissed`. Unknown candidate IDs return
404; already reviewed candidates return 409.

### Artist records

#### `GET /api/artists`

Returns a page of artist records ordered by lowercase name, then ID.
Parameters:

| Parameter | Type | Default | Bounds |
|---|---|---:|---|
| `limit` | integer | 50 | 1–100 |
| `offset` | integer | 0 | 0 or greater |

#### `POST /api/artists`

Creates an artist record and returns 201. `name` is required. Optional fields
are `country`, `city`, `genre`, `source_name`, and `source_url`.

#### `GET /api/artists/{artist_id}`

Returns one artist record or 404 when it does not exist.

#### `PATCH /api/artists/{artist_id}`

Updates supplied identity fields. An empty patch returns 400. Unknown fields
and blank names are rejected.

#### `DELETE /api/artists/{artist_id}`

Deletes one artist record and returns 204. Missing IDs return 404.

## Data model

### `artists`

Stores explicit identity records. The source URL is optional for manually
entered records. Source metadata does not make the record an audience
measurement.

### `discovery_configuration`

Stores singleton ID 1 with:

- JSON array of areas.
- JSON array of genres.
- Result limit.
- Enabled flag.
- Updated timestamp.

When no row exists, API responses use defaults. The scheduler exits until a
configuration row exists; save settings through the Settings API to create it.

### `provider_configuration`

Stores singleton ID 1 with:

- JSON array of enabled provider IDs.
- Encrypted credential JSON blob.
- Updated timestamp.

If no row exists, the code defaults provider selection to MusicBrainz.

### `discovery_candidates`

Stores normalized provider results awaiting or completing human review:

- Provider ID and provider external ID.
- Name and optional country/area/type/disambiguation.
- Tags and source URL.
- Review status.
- First seen and last seen timestamps.
- Last searched area and genre.

A unique constraint prevents duplicate `(provider_id, external_id)` pairs.

### What the schema deliberately omits

There are no database tables for:

- Followers, streams, or view counts.
- Time-series audience growth.
- Audio measurements.
- Model training labels.
- Recommendation scores.
- Signing decisions or reviewer accounts.

See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for additional model and
trust-boundary notes.

## Validation and response conventions

- API bodies use Pydantic schemas.
- Most write schemas reject unexpected fields.
- Artist name and optional text fields are trimmed.
- Artist source URLs must be absolute HTTP or HTTPS URLs.
- Artist names cannot be blank.
- Search and pagination parameters are range-limited.
- Filter strings are stripped and deduplicated while preserving order.
- External provider errors are reported as readable provider-specific text.
- Credentials do not appear in API responses.

The UI displays backend and provider errors rather than filling the application
with synthetic example records.

## Credential protection

Provider credentials are encrypted using Fernet in `backend/app/secrets.py`.
The key is supplied through `PROVIDER_SECRETS_KEY`; it is not generated
automatically by the application.

### Key handling

- Generate a Fernet key using the command in [Quick start](#quick-start).
- Store it in `backend/.env` for local work.
- Back it up separately from the database.
- Keep it stable across API restarts and database restores.
- Restrict filesystem and environment access to trusted operators.
- Do not paste the key or provider credentials into source code, issues, or
  public logs.

If the key is lost or replaced, previously stored credential blobs cannot be
decrypted. Restoring the database without restoring its matching key will make
credential-dependent providers unusable until credentials are re-entered.

### Encryption is not caller authentication

The backend API does not authenticate callers. Encryption at rest protects
credential values in the database, but it does not prevent an unauthorized
network client from invoking API endpoints or submitting new credentials.
Bind the service to localhost and do not expose it directly to the internet.

## Database and persistence

### SQLite default

The default database path is:

```text
backend/data/breakout_radar.db
```

The data directory is created as needed and ignored by Git. Back it up if
artist records, queue history, settings, or credentials must be preserved.

### PostgreSQL

Set `DATABASE_URL` to a PostgreSQL connection string. A plain
`postgresql://` URL is rewritten to use the psycopg SQLAlchemy dialect.
Installations use the psycopg binary extra listed in
`backend/requirements.txt`.

### Schema evolution

The application currently calls `Base.metadata.create_all()` at startup. This
creates new tables; it is not a migration framework and does not reliably
transform existing schemas. Before production schema changes, introduce
Alembic revisions and a migration deployment procedure.

## Frontend guide

### App component

`frontend/src/App.jsx` owns the current workspace experience:

- Four main sections: Discovery, Analyze, Recommend, and Settings.
- API status and artist-directory loading.
- Provider selection and credential update/removal forms.
- Discovery preference forms and local browser preference compatibility.
- Manual search and result aggregation across configured filters.
- Candidate queue polling and review actions.
- Artist add/delete actions and client-side filtering of the loaded page.
- Explanatory empty states for features without authorized evidence.

The UI opens directly to the workspace. It does not show a sign-in screen.
Authentication is not implemented by this frontend or backend.

### API module

`frontend/src/api.js` centralizes:

- Fetch calls under `/api`.
- JSON request headers for bodies.
- Error conversion for non-2xx responses.
- Helpers for health, providers, discovery settings, discovery search,
  candidate review, and artist records.

The helper throws on failed requests. It does not provide hardcoded fallback
records.

### Styling

`frontend/src/styles.css` contains layout and responsive styles for the
sidebar, panels, metrics, tables, candidate cards, forms, and empty states.
Mobile breakpoints adjust the navigation, forms, and candidate cards.

### Development proxy

Vite runs on port 5173 and proxies `/api` to
`http://127.0.0.1:8000`. Set `API_PROXY_TARGET` to override the backend proxy
target when necessary.

## Backend guide

### `main.py`

This module:

- Creates the FastAPI application and defines its lifespan.
- Sets CORS origins from `CORS_ORIGINS`.
- Starts and stops the scheduler task.
- Exposes health and provider configuration routes.
- Persists discovery settings.
- Runs manual multi-provider search.
- Lists and reviews queue candidates.
- Creates, reads, updates, lists, and deletes artist identities.
- Converts database/provider failures to API errors and logs failures.

### `providers.py`

This module:

- Defines provider metadata used by the API and Settings UI.
- Maps provider-specific inputs and responses into the common artist shape.
- Enforces the MusicBrainz request interval with an in-process lock.
- Caches Spotify and SoundCloud tokens in process.
- Expands named region shortcuts into country filters.
- Determines whether required credentials have been configured.
- Aggregates successful results and provider errors.

Provider adapters share transport/error helpers but keep endpoint-specific
response parsing. Changing one adapter should include a focused mock test of
its expected response shape.

### `scheduler.py`

This module:

- Defines the 15-minute interval.
- Reads persisted search settings and provider credentials.
- Skips collection when disabled or without search filters/providers.
- Generates the area/genre search matrix.
- Calls each selected provider.
- Inserts new candidates or refreshes known candidate records.
- Logs provider failures and cycle summaries.
- Waits for either a settings-change wakeup or the next interval.

The scheduler uses a single application process and its own database sessions.

### `schemas.py`

This module is the API contract for:

- Artist create/update/read/page requests and responses.
- Health status.
- Normalized provider search results.
- Provider status and provider settings writes.
- Discovery settings and queue pages.
- Candidate review status.

Update the schemas and tests when request or response fields change.

### `models.py` and `database.py`

Models define persistent artist, provider, discovery, and queue data. The
database module constructs the engine and session factory, and provides a
FastAPI dependency that scopes a session to a request.

### `secrets.py`

This module validates the configured Fernet key, encrypts serialized
credentials, decrypts them for backend use, and reports invalid keys or
corrupted encrypted data explicitly.

## Environment variable reference

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite file in `backend/data/` | SQLAlchemy database connection |
| `CORS_ORIGINS` | localhost Vite origins | Comma-separated browser origins accepted by the API |
| `LOG_LEVEL` | `INFO` | Python logging level passed to `logging.basicConfig` |
| `MUSICBRAINZ_CONTACT` | Repository issue tracker example | Contact hint included in the MusicBrainz User-Agent; replace with a maintained contact |
| `YOUTUBE_SEARCH_DAILY_BUDGET` | `80` | Persistent YouTube search.list request budget per UTC day |
| `MAX_PROVIDER_CALLS_PER_SEARCH` | `100` | Maximum estimated upstream calls accepted by one manual search |
| `MAX_SCHEDULED_PROVIDER_CALLS_PER_CYCLE` | `100` | Maximum provider calls in one scheduled discovery cycle |
| `PROVIDER_SECRETS_KEY` | unset | Fernet key required to store/decrypt provider credentials |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Vite proxy target for `/api` |

`API_PROXY_TARGET` is read by Vite, not by the Python backend. Provider keys
are stored through the Settings API rather than a separate environment
variable for each provider.

## Testing

### Backend

From the repository root:

```bash
cd backend
python -m pytest
```

The test client uses an in-memory SQLite database. Tests cover:

- Health status.
- Provider readiness and credential encryption.
- Rejection of unknown providers and fields.
- Missing credential reporting.
- Regional filter expansion.
- OAuth bearer-header construction for selected adapters.
- Manual-search normalization contract.
- Discovery settings persistence and validation.
- Scheduled filter combination processing.
- Queue insertion, deduplication, and review.
- Artist create, update, delete, validation, and pagination.

The current backend tests mock most provider HTTP responses. The suite does
not substitute for validating every upstream service with real approved
credentials.

### Frontend

From the repository root:

```bash
cd frontend
npm test
```

The Vitest/jsdom tests cover:

- Workspace rendering and section navigation.
- Search result display and explicit artist saving.
- Discovery settings persistence.
- Provider selection and credential submission.
- API failure visibility.

### Frontend production build

```bash
cd frontend
npm run build
```

### Root convenience command

```bash
make test
```

The backend test runner must be available as `python3` by default, or override
the Make variable:

```bash
make test PYTHON=/path/to/python
```

## Build and CI

`.github/workflows/ci.yml` runs two independent jobs:

1. Install Python dependencies and execute backend pytest on Python 3.13.
2. Install Node 24.15 dependencies with `npm ci`, run Vitest, and build the
   frontend.
3. When both test jobs pass, assemble the source plus production frontend and
   publish `ARTIST_BREAK_APP.zip` as a workflow artifact.

The pre-commit configuration includes whitespace and YAML/JSON checks, Ruff,
ESLint, Prettier, and Gitleaks. Install `pre-commit` and run `make lint` to
execute the configured hooks. The lint target fails when pre-commit is missing
or when a hook reports an error; it does not suppress failed checks.

## Common operational issues

### API logs show startup, then shutdown

`Uvicorn running` followed by `Application startup complete` indicates startup
succeeded. If the process then logs `Shutting down`, the server received a
shutdown request, commonly from `Ctrl+C` or terminal closure. Activating a
virtual environment in another shell does not restart a stopped process.

Start Uvicorn again from `backend/` and keep that terminal open.

### `GET /api/health` works but the queue stays empty

Health verifies database reachability, not that scheduled discovery can find
results. Check:

1. The recurring discovery checkbox is enabled.
2. At least one area or genre is saved.
3. At least one provider is enabled.
4. The provider is configured and reaches its upstream service.
5. The scheduler process remains running.
6. Backend logs for skipped cycles or provider errors.

Health's configured provider list does not verify credentials against upstream
services. A provider with valid-looking saved fields can still reject requests.

### Regional phrase returns no results

MusicBrainz area search expects recognized area names. The exact strings
`East Africa` and `Central Africa` are expanded by this application. Other
regional names may not be recognized by a provider. Try a country name or
inspect a provider's area vocabulary.

### No providers are ready

Open Settings and inspect each provider. Enable a provider that is either
keyless or has all required credentials. Save changes. Missing credentials
produce explicit errors for manual search; the scheduler logs the failed
provider search.

### Credential save reports a key error

Set a valid Fernet key in `backend/.env` before saving credentials. Generate
one with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Restart the backend after changing environment values. Do not rotate a key
unless the existing encrypted credentials have been migrated or are no longer
needed.

### Credentials cannot be decrypted

The encryption key does not match the key used to save the database values, or
the encrypted data is malformed. Restore the original key from a secure backup.
If it is unavailable, the affected credentials must be cleared or replaced.

### The UI says the API is unavailable

Confirm that:

- Uvicorn is running on port 8000.
- Vite is running on port 5173.
- The Vite proxy target points to the actual API URL.
- CORS and local firewall settings allow the request path.
- `/api/health` returns HTTP 200.

### Virtual environment has a stale interpreter path

Python virtual environments may contain launch scripts with an absolute path
from the machine that created them. If a checked-in or moved `.venv` is stale,
create a new local environment and reinstall `backend/requirements.txt`.
Virtual environments should not be shared or committed.

### Provider search returns an HTTP error

An HTTP error can indicate an invalid key, blocked API product, changed
provider endpoint, missing account permission, exhausted quota, or a provider
outage. Use the provider's official diagnostics and developer dashboard.
Avoid repeatedly retrying quota-limited requests.

## Known limitations

### Provider API lifecycle

Provider APIs can change, require review, or disappear. The integration list
does not mean all endpoints have been tested with production credentials.
Check official references in Settings and
[docs/DATA_SOURCES.md](./docs/DATA_SOURCES.md).

### Quotas and scheduler fan-out

The scheduler now maintains a persistent daily request ledger for YouTube
search.list calls, with a conservative default budget of 80 per UTC day. Manual
searches are capped at an estimated 100 upstream calls, and scheduled cycles
default to 100 provider requests. These controls prevent unbounded fan-out, but
they are not a substitute for verifying each provider's own quota, contract,
and commercial-use terms. The scheduler and MusicBrainz rate limiter remain
single-process components; multi-worker deployment still needs a dedicated
worker and distributed rate coordination.

### Catalog identity matching

Providers may represent group members, solo artists, stage names, or
collaborations differently. The app does not infer a cross-provider canonical
identity. Human verification remains necessary.

### Search ranking and meaning

Search ordering comes from upstream providers and is not an artist score. The
app does not claim that result order is comparable across providers.

### Database migrations

No Alembic migration is configured. `make migrate` documents this fact but
does not run a migration.

### Security and multi-user operation

No API authentication, authorization, CSRF protection, tenant model, or
multi-user audit trail is implemented. Do not expose this service as a
multi-user or internet-facing product without addressing those boundaries.

### Monitoring

The scheduler logs cycle outcomes and provider errors, but the project has no
metrics endpoint, alerting integration, durable job history, or operations
dashboard.

### Placeholder product modules

Analyze and Recommend are evidence-first explanatory screens, not implemented
analytics engines. The ROADMAP describes further work.

## Privacy, permissions, and source terms

Provider credentials are sensitive. Catalog records may also be subject to
provider-specific restrictions, attribution requirements, retention rules, or
commercial-use terms.

Before using a provider in a business workflow:

1. Read the current official terms and API documentation.
2. Confirm account and application eligibility.
3. Confirm commercial-use and redistribution rights.
4. Review API quota, caching, deletion, and attribution rules.
5. Keep only the data the workflow is allowed to retain.
6. Document operator approval and any relevant license where required.

The application does not grant recording, publishing, synchronization, image,
lyrics, or other music rights. API access and content-use rights are distinct.

Do not treat the absence of an API key as permission to scrape a provider.
Only the documented adapters and approved API methods should be used.

## Documentation map

- This README is the central developer/operator guide.
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) describes the runtime,
  persistence, and trust boundaries.
- [docs/DATA_SOURCES.md](./docs/DATA_SOURCES.md) describes providers,
  credentials, regional shortcuts, and source caveats.
- [docs/ROADMAP.md](./docs/ROADMAP.md) tracks known next steps.
- [docs/scoring-method.md](./docs/scoring-method.md) records principles for a
  future explainable rubric; no scoring implementation is implied.
- [CONTRIBUTING.md](./CONTRIBUTING.md) explains the contribution workflow.
- [SECURITY.md](./SECURITY.md) explains vulnerability reporting.
- [ai.md](./ai.md) summarizes the implementation and debugging work recorded
  in this repository.

## Contribution workflow

1. Create a focused branch.
2. Follow the patterns already used in the relevant frontend or backend area.
3. Update tests for behavior changes.
4. Update this guide and other affected documentation.
5. Run the smallest relevant test set, then the broader suite when appropriate.
6. Include behavior changes, test results, and operational caveats in the pull
   request.

When adding an external source, include provenance, permission review, error
handling, rate-limit behavior, credential treatment, response normalization,
and tests with representative provider payloads.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the repository workflow.

## Security reporting

Do not publish secrets, provider tokens, Fernet keys, or private credentials in
issues or pull requests. Report suspected security issues privately using the
process in [SECURITY.md](./SECURITY.md).

## License

Breakout Radar is distributed under the MIT license. See [LICENSE](./LICENSE)
for the complete license text.
