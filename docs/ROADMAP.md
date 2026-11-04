# Roadmap

The app has a working React/Vite frontend, Python/FastAPI backend, persistent artist-identity API, 16 provider search adapters, a scheduled candidate review queue, bounded provider request fan-out, and a persistent YouTube search quota ledger. It intentionally starts with no saved artists and has no audience metrics or scoring model.

## Completed hardening

- Upgrade the frontend toolchain and CI runner to a compatible Node 24 runtime.
- Add a persistent UTC-day YouTube `search.list` request budget with a default of 80.
- Bound manual and scheduled provider fan-out and skip providers without credentials.
- Retry transient provider transport failures and HTTP 429/5xx responses with bounded backoff.
- Batch multi-region/genre discovery in one browser-to-API request and deduplicate provider identities.

## Next priorities

1. Verify account eligibility, credentials, quotas, retention terms, and attribution separately for every enabled provider.
2. Move the scheduler into a separately operated worker and introduce shared rate limiting before running multiple API workers.
3. Add Alembic migrations, backup/restore procedures, and production observability.
4. Implement authentication, workspace isolation, and role-based access before deploying beyond localhost.
5. Build permissioned historical audience observations and artistic-review records before attempting predictive modelling.
6. Only consider a scoring or ML model after obtaining authorised, representative, labelled historical outcomes and defining independent validation criteria.
