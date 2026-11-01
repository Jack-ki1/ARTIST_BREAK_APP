# Architecture

```text
Public home / demo sign-in / app    Python FastAPI
  React + Vite                      app/main.py (API routes)
  src/api.js ── HTTP /api/* ─────►  app/providers.py (MusicBrainz client)
  src/App.jsx                       app/schemas.py (Pydantic models)
                                    app/models.py (SQLAlchemy records)
                                    app/database.py (SQLite/PostgreSQL)
```

## Stored record

An artist row contains only an identity explicitly entered by an operator or saved from a provider, plus optional provenance:

- UUID, name, optional country/city/genre
- optional source name and URL supplied by the operator
- creation and update timestamps

There are no metric, score, recommendation, sample, seed, or provider tables. The API rejects unrecognized request fields so audience figures cannot accidentally be persisted through the identity endpoint. Discovery queries MusicBrainz live; results are only copied into the local identity table after an explicit user action and include provider provenance.

## Runtime and trust boundaries

- The frontend makes provider requests only through the backend API. Spotify and YouTube links are external human-verification links, not API integrations.
- SQLite is the local default, configured via `DATABASE_URL`; PostgreSQL is supported with its SQLAlchemy driver.
- Backend startup creates tables for local development. Production needs formal migrations before schema changes.
- Authentication is disabled in this demo. The API binds to loopback by default and must not be exposed publicly.
- `GET /api/health` discloses the authentication mode and configured provider list; `GET /api/providers` describes implemented and unavailable integrations.
- MusicBrainz requests include a configurable maintainer contact and are serialized at the provider's one-request-per-second limit.
- Demo sign-in is client-side navigation only. It does not authenticate or authorize API requests.
