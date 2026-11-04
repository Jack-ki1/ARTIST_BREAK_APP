# Data sources, adapters and access policy

Breakout Radar contains **73 distinct source entries**. The settings directory is not a promise that all 73 are connected or that each provider permits arbitrary competitor analytics.

## Adapter coverage

### Identity search — 22 adapter paths

The 16 existing catalogue adapters are:

- MusicBrainz
- Wikidata
- Deezer
- Spotify Web API
- YouTube Data API
- Apple Music API
- Last.fm
- Discogs
- Google Knowledge Graph
- TheAudioDB
- Jamendo
- Audius
- Ticketmaster Discovery
- SoundCloud
- Musixmatch
- Genius

The six additional identity-search adapters are:

- Wikipedia
- iTunes Search API
- Bluesky / AT Protocol
- Mastodon
- setlist.fm
- Twitch Helix

These are official API integrations. They still require working provider access, and credentialed sources require the user's own approved credentials.

### Evidence enrichment — 4 adapter paths

- GDELT Project — news/press article metadata and source links.
- Reddit Data API — query-specific community evidence with OAuth.
- Flickr — public image references plus licence metadata.
- Openverse — openly licensed media search and licence attribution.

Evidence is stored as links, titles, short summaries and source context. It is not converted into a global audience count or presented as an official artist metric.

## Full 73-entry directory

| Category | Sources |
|---|---|
| Music metadata | MusicBrainz, Wikidata, Wikipedia, Discogs, Google Knowledge Graph, TheAudioDB, Musixmatch, Genius, Wikidata SPARQL, MusicBrainz Tags & Genres |
| Streaming and catalogue | Deezer, Spotify Web API, Apple Music API, iTunes Search API, Last.fm, Jamendo, Audius, SoundCloud, Apple Music Feed, Spotify Charts, Apple Music Charts, Amazon Music, TIDAL, Qobuz, Pandora AMP, Anghami, Boomplay, Mdundo, Shazam Charts |
| Social and community | Bluesky / AT Protocol, Mastodon, Reddit Data API, TikTok Display API, TikTok Research API, Instagram Graph API, Threads API, Facebook Pages Graph API, X API, Pinterest API v5, Tumblr API v2, LinkedIn Community Management |
| Video and creator | YouTube Data API, Twitch Helix, Vimeo, YouTube Analytics API |
| Live and events | Ticketmaster Discovery, setlist.fm, Songkick API, Bandsintown for Artists |
| Press and media | GDELT Project, Google Alerts RSS, Music press RSS feeds, Naija music press feeds, OkayAfrica, Afropunk |
| Media and identity | Wikimedia Commons, Flickr, Openverse |
| Listening and demand signals | ListenBrainz, Google Trends API, Wikimedia Pageviews |
| Commercial / industry data | Chartmetric, Soundcharts, Songstats, Viberate, Luminate, Mediabase, Radio monitoring partners, SoundExchange, DDEX / distributor feeds |
| Audio intelligence | ShazamKit |

The exact provider metadata, documentation links, required credential fields and access notes are in `backend/app/source_data.py` and `backend/app/source_data_extra.py`.

## What each status means

| Status | Meaning |
|---|---|
| Ready | The app has the relevant adapter and required local credential fields are present. Remote access is not guaranteed until a request succeeds. |
| Needs credentials | A search adapter exists, but required API credentials are missing. |
| Disabled | The operator has not enabled the source. |
| Approval required | The API product/scopes require app review or explicit approval. |
| Artist authorisation | The API is for an artist or team that authorises access to their own account. |
| Research only | The service restricts access to eligible research users/organisations. |
| Licensed access | A commercial data licence or subscription is required. |
| Partner access | Access is limited to a partner or approved developer programme. |
| Manual setup | The operator configures a permitted feed or reviewed source URL. |
| Client only | This requires an app/device-side SDK implementation, not a backend search request. |

## Important provider-specific boundaries

- **Spotify:** the integration is limited to catalogue identity metadata. Do not use Spotify Content to train AI/ML models or derive listenership metrics from Spotify Content or the Spotify Service. Spotify developer access and scopes change; verify current account eligibility.
- **YouTube:** public channel/video search uses the Data API. Channel Analytics requires OAuth and the channel owner's explicit authorisation. The app reserves `search.list` calls in a persistent budget of 80 per Pacific-time day by default.
- **TikTok:** the Display API is for approved app products/scopes and creator-authorised data. The Research API is available only to qualified researchers and eligible organisations/regions; it is not treated as a commercial analytics source.
- **Instagram, Threads and Facebook Pages:** use approved Meta permissions and account/page authorisation. Private account insights are not obtained from public search.
- **X, Pinterest and LinkedIn:** availability is governed by current developer tiers, product approval, scopes and commercial policies. LinkedIn's community-management product is restricted and is not a public people-search endpoint.
- **Bandsintown:** API use is tied to an artist/team that authorises the integration. Do not use artist-specific keys to analyse unrelated artists.
- **Songkick:** listed as a partner/legacy option; new API access may be restricted. It is not marked as an active search adapter.
- **Google Trends:** access is limited/early-access. No unofficial scraping fallback is used.
- **Chartmetric, Soundcharts, Songstats, Viberate, Luminate, Mediabase and radio-monitoring data:** require commercial or partner licensing.
- **Flickr, Openverse and Wikimedia:** preserve individual work-level attribution and licence information. Publicly viewable media is not automatically licensed for commercial reuse.
- **RSS, chart URLs and artist profile links:** must be supplied from a feed/source the operator is permitted to ingest. Manual entries are not silently scraped.

## Credential storage and operating guidance

1. Configure a Fernet key in `backend/.env` using `PROVIDER_SECRETS_KEY`.
2. Enable a source in Settings and supply only the credentials it requests.
3. Save the source configuration. Credentials are encrypted in the backend database and are never returned to the browser.
4. A Ready status means required fields are present; run a discovery scan to confirm that the remote provider accepts the request.
5. Disable a provider when credentials expire or access is withdrawn. Honour provider retention/deletion rules.

Do not put provider keys in `frontend/`, source control, screenshots or issue comments. The application API is currently unauthenticated and should remain on loopback or behind trusted access control.

## Data collected

Identity metadata includes source ID, external ID, source URL, name and optional profile metadata. Numeric observations are stored with source ID, metric name, scope, timestamp and source URL. Press/community/media records are stored as evidence references. Provider values are not blended into one cross-platform audience total.

Source readiness is a configuration signal, not a live health check. Provider-specific quotas, current access terms, data retention, attribution and commercial rights must be verified before production use.
