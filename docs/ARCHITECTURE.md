# Breakout Radar v3 — architecture

## Product navigation

The interface has exactly four primary sections:

| Section | Responsibility |
|---|---|
| Discovery | Query configured identity sources, merge matching identities into candidate groups, and let A&R reviewers accept or dismiss each group. |
| Analyse | View source identities, source-specific observation history and linked evidence; save a structured artistic review. |
| Recommendations | Rank accepted artists using discovery coverage and artistic quality, and record Pursue / Meet / Watch / Hold decisions. |
| Settings | Enable sources, configure credentials, edit discovery seeds, set emerging-artist guardrails and tune scoring weights. |

## Runtime components

```text
React 18 + Vite
  four-section workspace
  api.js  ───────────────►  FastAPI /api/*
                              main.py
                                ├── source_catalog.py
                                ├── integrations.py
                                ├── providers.py (16 existing catalogue adapters)
                                ├── scoring.py
                                ├── secrets.py (Fernet encryption)
                                └── SQLAlchemy models
                                      └── SQLite / PostgreSQL

Optional scheduled process:
  python -m app.worker
       └── run_discovery() ───► same source adapters / database
```

The worker is separate from Uvicorn. The API startup does not launch a scheduler, so adding API processes does not silently start duplicate discovery loops. Run one worker until distributed locking is introduced.

## Source layer

The source registry is data-driven and lists 73 providers. It distinguishes:
- identity-search adapters that can be called by Discovery,
- evidence-enrichment adapters that collect press/community/media references,
- entries requiring credentials or approved OAuth scopes,
- partner/licensed/research-only entries,
- manual feed/link entries, and
- client-only integrations.

A source marked Ready has an implemented adapter and locally complete required fields. It does not mean the remote service has accepted a request. Provider errors are stored in the run result rather than replaced with fake sample records.

Each provider result is normalized into an identity shape with a provider ID, external ID, source URL, optional profile metadata and optional source-returned metrics. The source identifier and the original source URL are retained.

## Discovery lifecycle

1. Read enabled source IDs, encrypted credentials and saved discovery settings.
2. Filter out sources that are disabled, missing credentials, restricted to research/partner/licensed access, or not identity-search adapters.
3. Bound the source/query fan-out and reserve any quota-limited calls before starting concurrent I/O.
4. Query official provider endpoints with a concurrency ceiling of three.
5. Normalize provider results and group names using a conservative normalized-name key. Provider identifiers are not collapsed or discarded.
6. Save candidates by unique (source ID, external ID). Candidate groups expose their source count and corroboration requirement.
7. A human accepts or dismisses the candidate group.
8. Accepting a group creates one canonical artist and separate provider identity records.
9. Future discovery scans recognise accepted identities and append new metric observations to the artist history instead of recreating duplicate candidates.

Name matching is a candidate grouping heuristic, not definitive identity verification. A&R reviewers can inspect the underlying source links before accepting.

## Data model

| Table | Purpose |
|---|---|
| radar_artists | Canonical artist profile and current decision tier |
| radar_artist_identities | One identity per provider/external ID, linked to a canonical artist |
| radar_candidates | Pending/reviewed discovery identities |
| radar_observations | Immutable source-scoped metric observations with timestamps |
| radar_evidence | Linked press, community and media records |
| radar_artistic_reviews | Reviewer, track reference, rubric scores, strengths, risks and notes |
| radar_decisions | Decision history and rationale |
| radar_source_configuration | Enabled providers and encrypted provider credentials |
| radar_source_daily_usage | Durable daily quota reservations |
| radar_settings | Discovery, threshold and scoring configuration |
| radar_discovery_runs | Provider/query run history |
| radar_alerts | Workspace alerts |

Observation values are never added across providers. A number from Deezer is recorded as Deezer data; it is not treated as the artist's global streaming audience.

## Scoring and decisions

Discovery uses source-specific momentum only when two observations exist and the configured minimum history has elapsed. Other discovery components include independent-source breadth, release activity, live activity, search interest and catalogue headroom. Missing dimensions are omitted and reduce coverage/confidence.

Artistic review is separate and reviewer-attributed. Recommendation thresholds are configurable. An artist without a completed artistic review stays on Hold regardless of discovery score. All scores are ranking indices, not predicted probabilities.

See [scoring-method.md](scoring-method.md).

## API surface

- `GET /api/health`, `GET /api/dashboard`
- `GET/PUT /api/sources`
- `GET/PUT /api/settings`
- `POST /api/discovery/run`, `GET /api/discovery/candidates`
- `POST /api/discovery/candidates/{id}/review`
- `GET/POST /api/artists`, `GET /api/artists/{id}`
- `POST /api/artists/{id}/collect-evidence`
- `POST /api/artists/{id}/reviews`, `POST /api/artists/{id}/decisions`
- `GET /api/recommendations`, `GET /api/runs`, `GET /api/alerts`

## Security and operations

- Provider secrets are encrypted using Fernet. The key is supplied through `PROVIDER_SECRETS_KEY` and must be backed up independently from the database.
- The API has no user authentication or workspace isolation yet. It binds to loopback by default; do not expose it to an untrusted network.
- YouTube `search.list` calls have a persistent budget (80/day by default) using the Pacific-time quota reset boundary.
- Manual provider fan-out is capped by `MAX_PROVIDER_CALLS_PER_SEARCH`.
- The optional worker must be started separately. Use one worker until a distributed lock is configured.
- SQLAlchemy `create_all()` creates missing v3 tables but does not migrate existing tables. Add Alembic migrations before production schema changes.
