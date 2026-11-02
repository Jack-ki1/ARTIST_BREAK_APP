# Roadmap

The app has a working React/Vite frontend, Python/FastAPI backend, persistent artist-identity API, 16 provider search adapters, and a scheduled candidate review queue. It intentionally starts with no saved artists and has no audience metrics or scoring model.

1. Verify account eligibility, credentials, quotas, retention terms, and attribution separately for every enabled provider.
2. Add provider-aware scheduler quotas and shared rate limiting before scaling filter combinations or backend workers.
3. Add database migrations, backups, and production observability.
4. Implement authentication and role-based access before deploying beyond localhost.
5. Only consider a scoring or ML model after obtaining authorized, representative, labeled historical outcomes and defining independent validation criteria.
