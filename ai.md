# Assisted rebuild record

This file records the repository audit and the hardening work in the
`rebuild/production-hardening` branch. It contains no provider credentials,
encryption keys, or local database content.

## Verified baseline

- The application is a React/Vite frontend and Python/FastAPI backend.
- The live application code is under `frontend/` and `backend/`; `apps/`,
  `packages/`, and `infra/` are future-layout placeholders.
- It supports artist catalogue search, provider configuration, a local artist
  identity directory, a scheduled discovery queue, and human review.
- It does not yet implement historical audience analytics, artistic scoring,
  validated breakout prediction, or automated recommendations.
- The backend API has no caller authentication and must remain on loopback or
  behind a trusted access-controlled network.

## Rebuild changes completed and CI-verified

- Raised the supported frontend runtime to Node 24.15+ and upgraded GitHub
  Actions to Node 24-compatible action releases.
- Added a persistent per-Pacific-day request ledger for YouTube search.list calls.
  The default budget is 80 to leave headroom below the standard 100-call
  allocation; operators can configure the budget for their approved project.
- Added bounded retries with Retry-After support for transient provider errors.
- Corrected provider status handling for an explicitly empty provider selection.
- Corrected TheAudioDB source links to use artist identity URLs rather than
  artwork URLs, and stopped treating Ticketmaster event counts as identity
  disambiguation.
- Consolidated multi-region and multi-genre discovery into one API request,
  deduplicated provider results, and imposed request fan-out limits.
- Added a per-cycle scheduler cap, credential-readiness checks, and small
  scheduling jitter.
- Added regression tests for quota enforcement, transient retries, batching,
  and deduplication.
- Updated CI to package the tested source and production frontend into a
  downloadable `ARTIST_BREAK_APP.zip` artifact after the test jobs pass.

## Remaining production work (not included in this rebuild)

- Add Alembic migrations and deployment-safe schema upgrades.
- Operate scheduled collection in a separate durable worker with distributed
  locking and provider-wide rate coordination.
- Add authenticated users, roles, workspace isolation, and audit history before
  any internet-facing deployment.
- Verify every external adapter with current approved credentials, quotas,
  terms, retention, and attribution requirements.
- Add a canonical cross-provider artist identity/identifier model.
- Build time-stamped audience observations only from authorised sources.
- Add structured artistic reviews and evidence references before building
  predictive models.
- Evaluate audio models only against audio the project has permission to
  process and licences compatible with the intended deployment.

## Verification

GitHub Actions run `41801165096` completed successfully on the rebuild branch:

- Backend: 23 tests passed, with no pytest deprecation warnings.
- Frontend: 8 tests passed.
- Vite 8.3.5 production build completed successfully.
- Release packaging job rebuilt the production frontend, assembled the source
  archive, passed `unzip -t`, and uploaded artifact `13306734941`.
- The downloaded project ZIP was independently checked: 68 archive entries,
  valid ZIP integrity, includes frontend production assets, and contains no
  `.env`, local databases, `node_modules`, or virtual environments.

The branch is available in pull request #1. The main branch has not been
modified or merged.
