# Data sources and permissions

## Integrated: MusicBrainz

The backend's live Discovery search queries the MusicBrainz artist catalog and returns artist identity metadata, area, type, tags, and a source link. Results are not popularity rankings or breakout predictions. A result is stored locally only after the user chooses **Add to directory**, with the MusicBrainz artist page stored as provenance.

The API requires no key, but MusicBrainz asks clients to send a meaningful `User-Agent` and make no more than one request per second. The backend serializes and throttles application requests. Set `MUSICBRAINZ_CONTACT` to a real maintainer contact URL or email before public deployment; local development defaults to `http://localhost:5173`.

Official references:

- [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)
- [MusicBrainz API rate limiting](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting)

## Not integrated: Spotify and YouTube

The candidate panel provides clearly labeled outbound Spotify and YouTube search links for human verification. The application does not call either provider's API or report their audience/play counts.

- Spotify integration needs an approved Spotify developer application and server-side credentials. See [Spotify Search API](https://developer.spotify.com/documentation/web-api/reference/search).
- YouTube Data API needs a server-side API key and quota management. Search calls consume quota and can return channels, videos, or playlists rather than verified artist identities. See [YouTube Search API](https://developers.google.com/youtube/v3/docs/search/list).

Do not put provider secrets in frontend code or browser storage. Before integrating another API, verify account authorization, current terms, commercial eligibility, quotas, retention, caching, deletion, and attribution requirements.

## Data integrity

- MusicBrainz catalog presence does not mean an artist is emerging, popular, or worth signing.
- No artist images, follower counts, scores, audience growth, or recommendation data are fabricated.
- External records are not persisted until a user explicitly saves an identity.
- Provider outages and invalid responses are shown as errors rather than sample results.
- The demo login is presentation-only; it does not provide authorization or change the backend's unauthenticated status.
