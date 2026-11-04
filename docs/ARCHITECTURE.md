# Architecture

```text
Workspace                          Python FastAPI
  React + Vite                      app/main.py (API routes)
  src/api.js ── HTTP /api/* ─────►  app/providers.py (multi-provider search adapters)
                                    app/quotas.py (persistent daily provider budgets)
  Settings                          app/secrets.py (encrypted provider credentials)
  src/App.jsx                       app/scheduler.py (15-minute discovery loop)
                                    app/schemas.py (Pydantic models)
                                    app/models.py (artists, settings, review queue)
                                    app/database.py (SQLite/PostgreSQL)
```

## Stored record

An artist row contains only an identity explicitly entered by an operator or saved from a provider, plus optional provenance:

- UUID, name, optional country/city/genre
- optional source name and URL supplied by the operator
- creation and update timestamps

An artist row contains only an identity explicitly entered by an operator or accepted from the review queue, plus optional provenance. Scheduled catalog matches are stored in a separate review queue with provider ID, external ID, observed timestamps, and search filters. Repeated matches update the existing queue record rather than creating duplicate artists. Accepting a candidate creates an identity row; dismissing it leaves it out of the directory.

There are no metric, score, recommendation, or audience-history tables. The API rejects unrecognized identity fields so audience figures cannot accidentally be persisted through the identity endpoint.

## Runtime and trust boundaries

- The frontend makes provider requests only through the backend API. Spotify and YouTube links are external human-verification links, not API integrations.
- SQLite is the local default, configured via `DATABASE_URL`; PostgreSQL is supported with its SQLAlchemy driver.
- Backend startup creates tables for local development. Production needs formal migrations before schema changes.
- Discovery settings are persisted in the database. While the API process is running, its scheduler searches each configured region/genre combination every 15 minutes; the browser is not required to remain open.
- Provider selections are stored in the database. Provider credentials are encrypted with Fernet using `PROVIDER_SECRETS_KEY`; that key must be backed up separately from the database.
- Provider status distinguishes enabled/disabled from credential readiness. Search calls return provider-specific errors rather than claiming success for unconfigured integrations.
- The scheduler enforces a per-cycle upstream request ceiling and skips providers that lack required credentials.
- YouTube search.list requests reserve a durable daily quota entry in `provider_daily_usage` before transmission; failed requests are counted conservatively.
- The in-process scheduler and MusicBrainz rate limiter assume one backend worker. Multi-worker deployment requires a dedicated scheduler and shared rate limiting.
- Authentication is not configured. The API binds to loopback by default and must not be exposed publicly.
- `GET /api/health` discloses the authentication mode and configured provider list; `GET /api/providers` describes implemented and unavailable integrations.
- MusicBrainz requests include a configurable maintainer contact and are serialized at the provider's one-request-per-second limit.
