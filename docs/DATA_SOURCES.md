# Data sources and permissions

## Integrated artist search

The backend can search these sources through the provider settings:

- MusicBrainz, Wikidata, and Deezer
- Spotify, YouTube Data API, Apple Music, Last.fm, Discogs, Google Knowledge Graph
- TheAudioDB, Jamendo, Audius, Ticketmaster Discovery, SoundCloud, Musixmatch, and Genius

Each adapter returns provider-attributed artist identity metadata. Sources differ in coverage, authentication, rate limits, approval requirements, commercial-use terms, and response quality. A provider marked ready only means the required credentials are present; it does not guarantee that the provider will accept a request.

Enter credentials in **Settings → Data providers**. Credentials are encrypted by the backend with `PROVIDER_SECRETS_KEY`. Do not put credentials in frontend code or browser storage. Review the current provider documentation and terms before enabling an integration for ongoing or commercial use.

MusicBrainz, Wikidata, and Deezer do not require credentials for the implemented search paths. MusicBrainz requests are serialized and limited to about one request per second; configure a maintainer-owned `MUSICBRAINZ_CONTACT` URL or email. Other providers require the relevant API key, application credentials, or access token; Audius requires an application name.

The application reserves YouTube `search.list` requests in a persistent UTC-day ledger. The default budget is 80 calls per day, leaving headroom below the standard 100-call daily allocation; override it only after verifying the quota assigned to the configured Google Cloud project. The manual API also rejects requests estimated to exceed 100 upstream calls, and scheduled discovery defaults to 100 provider calls per cycle. These safeguards cover the documented YouTube search quota and unbounded fan-out; they do not automatically enforce undocumented or account-specific quotas for every other integration.

## Scheduled and manual discovery

Manual search sends all selected regions and genres in one backend request, deduplicates results by provider identity, and reports provider-specific errors. Searches are limited to 25 region/genre combinations and a configurable estimate of 100 upstream calls. Scheduled discovery runs approximately every 15 minutes while the backend is running, skips providers without configured credentials, and stops at its per-cycle request budget. With no region/genre filters configured, the scheduler intentionally skips the cycle. The **East Africa** shortcut searches Burundi, Comoros, Djibouti, Eritrea, Ethiopia, Kenya, Madagascar, Malawi, Mauritius, Mozambique, Rwanda, Seychelles, Somalia, South Sudan, Tanzania, Uganda, Zambia, and Zimbabwe. **Central Africa** searches Angola, Cameroon, the Central African Republic, Chad, Congo, the Democratic Republic of the Congo, Equatorial Guinea, Gabon, and Sao Tome and Principe. These country-level searches use sovereign states; territories are excluded. New scheduled results enter a review queue; they are not added to the artist directory until accepted.

## Data integrity

- Catalog presence does not indicate that an artist is emerging, popular, or worth signing.
- No artist images, follower counts, scores, audience growth, or recommendation data are fabricated.
- Search results preserve provider identity and source links.
- Provider outages, missing credentials, and invalid responses are reported rather than replaced with sample results.
- This local workspace does not authenticate API callers; keep it bound to localhost and do not expose it to untrusted networks.
