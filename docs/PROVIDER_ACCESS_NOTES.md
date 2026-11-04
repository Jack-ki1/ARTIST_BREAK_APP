# Provider access notes (verified 4 November 2026)

This is an operational reference for the providers most likely to be mistaken for unrestricted data feeds. Provider status in the application describes the adapter and local configuration; it does not grant a platform permission or guarantee the next request will succeed.

## Spotify Web API

Spotify's February 2026 Development Mode changes materially affect this use case:

- The app owner must have Spotify Premium.
- A Development Mode app is limited to five authorised Spotify users.
- Development Mode is intended for individual learning, experimentation and personal projects, not as the foundation for a commercial A&R service.
- The February 2026 change also limits the endpoint surface for Development Mode apps. Spotify's migration guide distinguishes these restrictions from Extended Quota Mode.

For commercial A&R operations, obtain the required Spotify access/partnership approval before relying on this adapter. The code searches the catalogue; it does not infer listener counts, stream counts or artist-owned analytics.

Official references:
- https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security
- https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
- https://developer.spotify.com/documentation/web-api/concepts/quota-modes

## YouTube Data API

Google's current default quota includes 100 `search.list` calls per day. A search call costs one unit, and the daily search bucket resets at midnight Pacific Time. Additional pages consume additional calls. The project uses a conservative configurable budget of 80 search calls per day by default so it does not plan against the whole default allowance.

Keep the budget aligned with the quota actually assigned to the Google Cloud project. Requests for more quota may require a compliance audit.

Official references:
- https://developers.google.com/youtube/data/determine_quota_cost
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits

## TikTok Research Tools

TikTok's Research Tools are not a general-purpose commercial artist-discovery API. Access is for approved independent research, with eligibility requirements around eligible regions and organisations, non-commercial/public-interest purpose, a research proposal and data-security commitments. TikTok's published eligibility list does not currently include Kenya; its FAQ explicitly says creators, advertisers and commercial users are not eligible for Research Tools access.

For that reason, the TikTok Research API entry remains a research-only directory item. Do not enable it for Breakout Radar's commercial A&R workflow unless TikTok confirms a separate, applicable product and grants access under its terms. A normal TikTok developer account alone does not grant Research Tools access.

Official references:
- https://developers.tiktok.com/products/research-api/
- https://developers.tiktok.com/docs/en/about-research-api
- https://developers.tiktok.com/docs/en/research-api-faq

## Reddit Data API

Reddit states that commercial use of its developer tools and services requires prior permission; its published guidance says commercial use of Reddit data to power or enhance a product requires permission and a contract. Research access is separately governed. Do not run the Reddit enrichment adapter for commercial product use without Reddit's permission and the applicable agreement. Reddit content must not be used for model training without explicit consent.

Official reference:
- https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data

## Operational rule

A provider may appear in the 73-entry catalogue while being disabled, awaiting credentials, restricted to research, dependent on an approved app, or requiring a commercial agreement. The application must not equate directory presence, a saved API key, or a locally displayed `Ready` status with permission to use all data for all purposes. Confirm the current provider terms before enabling each source in a deployed commercial environment.
