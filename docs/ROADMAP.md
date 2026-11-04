# Product roadmap

## Implemented in v3 rebuild

- New four-section A&R workspace: Discovery, Analyse, Recommendations and Settings.
- 73-entry configurable source directory with explicit access states and source documentation links.
- 22 identity-search adapter paths and four evidence-enrichment adapters.
- Bounded concurrent discovery and per-run request fan-out guardrail.
- Source-identity candidate grouping and human accept/dismiss workflow.
- Canonical artist records and separate source identity identifiers.
- Source-scoped time-series observations that append on subsequent scans.
- GDELT, Reddit, Flickr and Openverse evidence collection.
- Structured human artistic review and reviewer-linked decision history.
- Transparent discovery/artistic scoring, confidence coverage and recommendation tiers.
- Fernet-encrypted provider credentials.
- Persistent YouTube daily quota ledger aligned to midnight Pacific Time.
- Optional scheduled discovery worker.
- React/Vite production frontend, backend tests, frontend tests and ZIP packaging workflow.

## Next production priorities

1. Add caller authentication, user/team workspaces, role-based access, audit log and CSRF/session policy before any public deployment.
2. Add Alembic migrations, explicit rollback paths and database backup/restore tests.
3. Add distributed worker leases/locks and shared provider rate limits before running multiple worker instances.
4. Add provider contract tests and scheduled health checks with real approved credentials for every adapter.
5. Add source-specific retention/deletion jobs and provenance/consent controls for user-generated data.
6. Add owner-authorised channel analytics only where the artist or their team explicitly grants access.
7. Evaluate an audio ingestion and analysis pipeline only after track upload/URL rights, consent, supported model capabilities and compatible licensing are established.
8. Train and validate a breakout model only after sufficient authorised historical outcomes exist. Use time-based splits, calibration, leakage checks and cohort-level performance reporting.
9. Add production observability, alerting, rate-limit dashboards and provider outage reporting.

## Deliberately not claimed

- 73 live data connections. The directory includes partner, licensed, research-only, manual and client-only options; only implemented adapters with complete credentials can be queried.
- Universal access to competitor social analytics or private streaming dashboards.
- AI music-listening scores.
- A statistically validated probability of breakout success.
