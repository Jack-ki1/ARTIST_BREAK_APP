# Data sources

This project intentionally starts with catalog and identity sources that are traceable and permissioned. The current implementation surfaces MusicBrainz metadata, while the long-term architecture is designed to support provider-specific evidence sources with explicit provenance.

## Current scope

- MusicBrainz: catalog metadata and artist identity lookup
- External search destinations: Spotify and YouTube are not data providers in the current implementation

## North-star rules

- No audience or popularity metric without a source, timestamp, and licence
- No recommendation without explainable scoring inputs
- No fabricated or inferred "breakout" rows without supporting evidence
