# Roadmap

The app now has a working React/Vite frontend, Python/FastAPI backend, persistent artist-identity API, and live MusicBrainz catalog search. It intentionally starts with no saved artists and has no audience metrics or scoring model.

1. Set a real `MUSICBRAINZ_CONTACT` value before deployment and monitor upstream availability and rate-limit behavior.
2. Assess Spotify and YouTube API eligibility, permissions, credentials, quotas, retention terms, and attribution before adding provider adapters.
3. Implement any approved adapter with provenance, permissions, rate limits, freshness, and deletion support.
4. Add database migrations, backups, and production observability.
5. Choose an identity provider and enforce user/role access before deploying beyond localhost.
6. Only consider a scoring or ML model after obtaining authorized, representative, labeled historical outcomes and defining independent validation criteria.
