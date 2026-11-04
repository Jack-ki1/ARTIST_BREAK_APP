# Breakout Radar v3.1.1

## Release focus

This revision aligns the Settings experience with the supplied product reference and makes the background collector observable.

### Settings and workspace UX

- Light workspace palette with a white content canvas, navy typography and blue-violet interaction accents.
- Fixed workspace navigation rail and persistent search header.
- Provider configuration displayed as responsive three-column cards on desktop, with source status, access notes, official documentation and expandable credential fields.
- Worker status is passed explicitly into Settings so its online state and heartbeat render correctly.
- Global search submits directly into Discovery; `Ctrl/⌘ + K` focuses the search field.

### Autonomous collection

- A separately run worker performs scheduled discovery and evidence refresh while the process is running.
- Discovery seeds rotate across cycles when the configured provider-call budget prevents processing every seed in one cycle.
- Worker heartbeat and the latest scan times are exposed through `/api/automation/status`.
- YouTube public channel statistics are stored as provider-attributed observations.
- MusicBrainz requests are paced rather than sent in bursts.

### Operational boundaries

The source directory is a catalogue, not a claim that every listed provider is a live connection. Active adapters are distinguished from entries requiring credentials, approval, licensing, artist authorisation, partnership or manual setup. Scores rank observed evidence and do not represent a validated probability of commercial success. Artistic judgement remains an A&R responsibility. The included Compose stack is a local/self-hosted deployment, not a managed cloud service.
