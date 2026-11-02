import asyncio
import hashlib
import logging
import os
import time
from typing import Any
from urllib.parse import quote

import httpx


logger = logging.getLogger(__name__)
MUSICBRAINZ_API = "https://musicbrainz.org/ws/2/artist"
_musicbrainz_lock = asyncio.Lock()
_last_musicbrainz_request_at = 0.0
_spotify_tokens: dict[str, tuple[str, float]] = {}
_soundcloud_tokens: dict[str, tuple[str, float]] = {}
REGIONAL_AREA_COUNTRIES = {
    "east africa": [
        "Burundi",
        "Comoros",
        "Djibouti",
        "Eritrea",
        "Ethiopia",
        "Kenya",
        "Madagascar",
        "Malawi",
        "Mauritius",
        "Mozambique",
        "Rwanda",
        "Seychelles",
        "Somalia",
        "South Sudan",
        "Tanzania",
        "Uganda",
        "Zambia",
        "Zimbabwe",
    ],
    "central africa": [
        "Angola",
        "Cameroon",
        "Central African Republic",
        "Chad",
        "Congo",
        "Democratic Republic of the Congo",
        "Equatorial Guinea",
        "Gabon",
        "Sao Tome and Principe",
    ],
}
PROVIDER_CATALOG: list[dict[str, Any]] = [
    {
        "id": "musicbrainz",
        "name": "MusicBrainz",
        "url": "https://musicbrainz.org/",
        "description": "Open artist catalog and identity matching. Does not provide popularity or growth metrics.",
        "fields": [],
        "access_note": "No API key. Requests are limited to one per second.",
    },
    {
        "id": "wikidata",
        "name": "Wikidata",
        "url": "https://www.wikidata.org/wiki/Wikidata:Data_access",
        "description": "Open structured artist identities and cross-provider identifiers.",
        "fields": [],
        "access_note": "No API key. Community coverage varies for emerging artists.",
    },
    {
        "id": "deezer",
        "name": "Deezer",
        "url": "https://developers.deezer.com/api",
        "description": "Artist and catalog search across Deezer.",
        "fields": [],
        "access_note": "No API key in the legacy search API; developer onboarding and commercial terms must be verified.",
    },
    {
        "id": "spotify",
        "name": "Spotify",
        "url": "https://developer.spotify.com/documentation/web-api",
        "description": "Search artist records in the Spotify catalog.",
        "fields": [
            {"key": "client_id", "label": "Client ID", "secret": False},
            {"key": "client_secret", "label": "Client secret", "secret": True},
        ],
        "access_note": "Requires a Spotify developer application. New-app access and commercial-use limits apply.",
    },
    {
        "id": "youtube",
        "name": "YouTube Data API",
        "url": "https://developers.google.com/youtube/v3",
        "description": "Search public music channels by artist name, region, or genre keywords.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True}],
        "access_note": "Requires a Google Cloud API key; search calls consume quota.",
    },
    {
        "id": "apple_music",
        "name": "Apple Music",
        "url": "https://developer.apple.com/documentation/applemusicapi",
        "description": "Search artists in the Apple Music catalog.",
        "fields": [
            {"key": "developer_token", "label": "Developer token (JWT)", "secret": True},
            {"key": "storefront", "label": "Storefront (optional, e.g. us)", "secret": False, "optional": True},
        ],
        "access_note": "Requires a valid Apple Music developer token. Catalog results depend on storefront.",
    },
    {
        "id": "lastfm",
        "name": "Last.fm",
        "url": "https://www.last.fm/api",
        "description": "Artist search and community-derived tags and similarity data.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True}],
        "access_note": "Requires a Last.fm API key. Commercial use requires provider approval.",
    },
    {
        "id": "discogs",
        "name": "Discogs",
        "url": "https://api.discogs.com/",
        "description": "Search artists and enrich identities with release and label context.",
        "fields": [{"key": "token", "label": "Personal access token", "secret": True}],
        "access_note": "Requires a Discogs token. API terms restrict reuse of some fields and images.",
    },
    {
        "id": "knowledge_graph",
        "name": "Google Knowledge Graph",
        "url": "https://developers.google.com/knowledge-graph",
        "description": "Resolve notable music artists to canonical knowledge-graph entities.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True}],
        "access_note": "Requires a Google API key; notability-ranked results may omit emerging artists.",
    },
    {
        "id": "theaudiodb",
        "name": "TheAudioDB",
        "url": "https://www.theaudiodb.com/free_music_api",
        "description": "Artist catalog and related metadata search.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True}],
        "access_note": "Requires a TheAudioDB API key. Check subscription and commercial reuse terms.",
    },
    {
        "id": "jamendo",
        "name": "Jamendo",
        "url": "https://developer.jamendo.com/v3.0/docs",
        "description": "Independent-music artist catalog and community discovery.",
        "fields": [{"key": "client_id", "label": "Client ID", "secret": True}],
        "access_note": "Requires a Jamendo client ID. API access does not grant recording-use rights.",
    },
    {
        "id": "audius",
        "name": "Audius",
        "url": "https://docs.audius.co/api",
        "description": "Search artist profiles in the Audius creator-uploaded catalog.",
        "fields": [{"key": "app_name", "label": "Application name", "secret": False}],
        "access_note": "Requires an application name; catalog coverage is specific to Audius.",
    },
    {
        "id": "ticketmaster",
        "name": "Ticketmaster Discovery",
        "url": "https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/",
        "description": "Find music artists and attractions with event activity.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True}],
        "access_note": "Requires a Ticketmaster API key; event coverage is market-dependent.",
    },
    {
        "id": "soundcloud",
        "name": "SoundCloud",
        "url": "https://developers.soundcloud.com/docs/api/guide",
        "description": "Search SoundCloud artist profiles and creator-uploaded music.",
        "fields": [
            {"key": "client_id", "label": "Client ID", "secret": True},
            {"key": "client_secret", "label": "Client secret", "secret": True},
        ],
        "access_note": "Requires an approved SoundCloud application and current API access.",
    },
    {
        "id": "musixmatch",
        "name": "Musixmatch",
        "url": "https://docs.musixmatch.com/api-reference/lyrics-catalog/lyrics-catalog-overview",
        "description": "Search artist records in the Musixmatch music catalog.",
        "fields": [{"key": "api_key", "label": "API key", "secret": True}],
        "access_note": "Requires an API key; lyric display is not included and requires separate rights.",
    },
    {
        "id": "genius",
        "name": "Genius",
        "url": "https://docs.genius.com/",
        "description": "Search music-related knowledge and song artists.",
        "fields": [{"key": "access_token", "label": "Access token", "secret": True}],
        "access_note": "Requires an access token; commercial API use requires a separate license.",
    },
]


def _lucene_phrase(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _normalize(
    provider_id: str,
    external_id: str,
    name: str,
    source_url: str,
    *,
    country: str | None = None,
    area: str | None = None,
    artist_type: str | None = None,
    disambiguation: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{provider_id}:{external_id}",
        "external_id": external_id,
        "provider_id": provider_id,
        "name": name,
        "country": country,
        "area": area,
        "type": artist_type,
        "disambiguation": disambiguation,
        "tags": [tag for tag in (tags or []) if isinstance(tag, str) and tag][:8],
        "source_url": source_url,
    }


def _artist_search_term(query: str | None, area: str | None, genre: str | None) -> str:
    return " ".join(value for value in (query, genre, area) if value).strip()


def expand_area_filter(area: str | None) -> list[str | None]:
    if area is None:
        return [None]
    return REGIONAL_AREA_COUNTRIES.get(area.strip().casefold(), [area])


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError("The provider did not respond in time") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Provider request returned HTTP %s", exc.response.status_code)
        raise RuntimeError(f"Provider search failed (HTTP {exc.response.status_code})") from exc
    except httpx.RequestError as exc:
        logger.warning("Provider request failed: %s", exc)
        raise RuntimeError("Could not reach the provider") from exc
    except ValueError as exc:
        raise RuntimeError("Provider returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Provider returned an unexpected response")
    return payload


async def _search_musicbrainz(
    client: httpx.AsyncClient,
    *,
    query: str | None,
    area: str | None,
    genre: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    clauses = []
    if query:
        clauses.append(f"artist:{_lucene_phrase(query)}")
    if area:
        clauses.append(f"area:{_lucene_phrase(area)}")
    if genre:
        clauses.append(f"tag:{_lucene_phrase(genre)}")
    global _last_musicbrainz_request_at
    async with _musicbrainz_lock:
        wait_seconds = 1.05 - (time.monotonic() - _last_musicbrainz_request_at)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        payload = await _get_json(
            client,
            MUSICBRAINZ_API,
            params={
                "query": " AND ".join(clauses),
                "fmt": "json",
                "limit": limit,
                "offset": offset,
            },
            headers={
                "User-Agent": (
                    "BreakoutRadar/1.0 "
                    f"({os.getenv('MUSICBRAINZ_CONTACT', 'http://localhost:5173')})"
                ),
                "Accept": "application/json",
            },
        )
        _last_musicbrainz_request_at = time.monotonic()
    items = []
    for artist in payload.get("artists", []):
        artist_id, name = artist.get("id"), artist.get("name")
        if not artist_id or not name:
            continue
        location = artist.get("area") or artist.get("begin-area") or {}
        items.append(_normalize(
            "musicbrainz", artist_id, name,
            f"https://musicbrainz.org/artist/{quote(artist_id, safe='')}",
            country=artist.get("country"),
            area=location.get("name"),
            artist_type=artist.get("type"),
            disambiguation=artist.get("disambiguation") or None,
            tags=[tag["name"] for tag in artist.get("tags", []) if tag.get("name")],
        ))
    return items


async def _spotify_token(client: httpx.AsyncClient, credentials: dict[str, str]) -> str:
    cache_key = hashlib.sha256(
        f"{credentials.get('client_id', '')}:{credentials.get('client_secret', '')}".encode()
    ).hexdigest()
    cached = _spotify_tokens.get(cache_key)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    try:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(credentials["client_id"], credentials["client_secret"]),
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("Spotify client-credentials authentication failed")
        raise RuntimeError("Spotify authentication failed; check the saved app credentials") from exc
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Spotify did not return an access token")
    _spotify_tokens[cache_key] = (
        token,
        time.monotonic() + max(int(payload.get("expires_in", 3600)) - 60, 60),
    )
    return token


async def _soundcloud_token(client: httpx.AsyncClient, credentials: dict[str, str]) -> str:
    cache_key = hashlib.sha256(
        f"{credentials.get('client_id', '')}:{credentials.get('client_secret', '')}".encode()
    ).hexdigest()
    cached = _soundcloud_tokens.get(cache_key)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    try:
        response = await client.post(
            "https://secure.soundcloud.com/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": credentials["client_id"],
                "client_secret": credentials["client_secret"],
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("SoundCloud client-credentials authentication failed")
        raise RuntimeError("SoundCloud authentication failed; check the saved app credentials") from exc
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("SoundCloud did not return an access token")
    _soundcloud_tokens[cache_key] = (
        token,
        time.monotonic() + max(int(payload.get("expires_in", 3600)) - 60, 60),
    )
    return token


async def search_provider(
    provider_id: str,
    *,
    query: str | None,
    area: str | None,
    genre: str | None,
    limit: int,
    offset: int = 0,
    credentials: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    credentials = credentials or {}
    term = _artist_search_term(query, area, genre)
    if not term:
        raise ValueError("Provide an artist name, area, or genre to search")
    if provider_id not in {provider["id"] for provider in PROVIDER_CATALOG}:
        raise ValueError(f"Unsupported provider: {provider_id}")

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        if provider_id == "musicbrainz":
            return await _search_musicbrainz(
                client, query=query, area=area, genre=genre, limit=limit, offset=offset
            )
        if provider_id == "deezer":
            payload = await _get_json(
                client, "https://api.deezer.com/search/artist",
                params={"q": term, "limit": limit, "index": offset},
            )
            return [
                _normalize("deezer", str(item["id"]), item["name"], item["link"],
                           country=item.get("country"), tags=[])
                for item in payload.get("data", []) if item.get("id") and item.get("name")
            ]
        if provider_id == "wikidata":
            payload = await _get_json(
                client, "https://www.wikidata.org/w/api.php",
                params={"action": "wbsearchentities", "search": term, "language": "en",
                        "format": "json", "type": "item", "limit": limit, "continue": offset},
                headers={"User-Agent": "BreakoutRadar/1.0 (https://github.com/Jack-ki1/ARTIST_BREAK_APP)"},
            )
            return [
                _normalize("wikidata", item["id"], item["label"],
                           f"https://www.wikidata.org/wiki/{item['id']}",
                           disambiguation=item.get("description"))
                for item in payload.get("search", []) if item.get("id") and item.get("label")
            ]
        if provider_id == "spotify":
            token = await _spotify_token(client, credentials)
            payload = await _get_json(
                client, "https://api.spotify.com/v1/search",
                params={"q": term, "type": "artist", "limit": min(limit, 10), "offset": offset},
                headers={"Authorization": f"Bearer {token}"},
            )
            artists = payload.get("artists", {}).get("items", [])
            return [
                _normalize("spotify", item["id"], item["name"],
                           item.get("external_urls", {}).get("spotify", f"https://open.spotify.com/artist/{item['id']}"),
                           tags=item.get("genres", []))
                for item in artists if item.get("id") and item.get("name")
            ]
        if provider_id == "youtube":
            payload = await _get_json(
                client, "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "type": "channel", "q": term, "maxResults": min(limit, 50),
                        "key": credentials["api_key"]},
            )
            return [
                _normalize("youtube", item["id"]["channelId"], item["snippet"]["channelTitle"],
                           f"https://www.youtube.com/channel/{item['id']['channelId']}")
                for item in payload.get("items", [])
                if item.get("id", {}).get("channelId") and item.get("snippet", {}).get("channelTitle")
            ]
        if provider_id == "apple_music":
            storefront = credentials.get("storefront", "us")
            payload = await _get_json(
                client, f"https://api.music.apple.com/v1/catalog/{quote(storefront, safe='')}/search",
                params={"term": term, "types": "artists", "limit": min(limit, 25), "offset": offset},
                headers={"Authorization": f"Bearer {credentials['developer_token']}"},
            )
            return [
                _normalize("apple_music", item["id"], item["attributes"]["name"],
                           item["attributes"].get("url", f"https://music.apple.com/{storefront}/artist/{item['id']}"),
                           tags=item["attributes"].get("genreNames", []))
                for item in payload.get("results", {}).get("artists", {}).get("data", [])
                if item.get("id") and item.get("attributes", {}).get("name")
            ]
        if provider_id == "lastfm":
            payload = await _get_json(
                client, "https://ws.audioscrobbler.com/2.0/",
                params={"method": "artist.search", "artist": term, "api_key": credentials["api_key"],
                        "format": "json", "limit": limit, "page": offset // max(limit, 1) + 1},
            )
            artists = payload.get("results", {}).get("artistmatches", {}).get("artist", [])
            return [
                _normalize("lastfm", str(item.get("mbid") or item["name"]), item["name"],
                           item.get("url", f"https://www.last.fm/music/{quote(item['name'])}"))
                for item in artists if item.get("name")
            ]
        if provider_id == "discogs":
            payload = await _get_json(
                client, "https://api.discogs.com/database/search",
                params={"q": term, "type": "artist", "per_page": limit, "page": offset // max(limit, 1) + 1},
                headers={"Authorization": f"Discogs token={credentials['token']}",
                         "User-Agent": "BreakoutRadar/1.0"},
            )
            return [
                _normalize("discogs", str(item["id"]), item["title"],
                           f"https://www.discogs.com/artist/{item['id']}")
                for item in payload.get("results", []) if item.get("id") and item.get("title")
            ]
        if provider_id == "knowledge_graph":
            payload = await _get_json(
                client, "https://kgsearch.googleapis.com/v1/entities:search",
                params={"query": term, "key": credentials["api_key"], "limit": limit,
                        "types": ["MusicGroup", "Person"]},
            )
            return [
                _normalize("knowledge_graph", item["result"]["@id"].rsplit("/", 1)[-1],
                           item["result"]["name"], item["result"].get("url", item["result"]["@id"]),
                           disambiguation=item["result"].get("description"))
                for item in payload.get("itemListElement", [])
                if item.get("result", {}).get("@id") and item.get("result", {}).get("name")
            ]
        if provider_id == "theaudiodb":
            payload = await _get_json(
                client, f"https://www.theaudiodb.com/api/v1/json/{quote(credentials['api_key'], safe='')}/search.php",
                params={"s": term},
            )
            return [
                _normalize("theaudiodb", item["idArtist"], item["strArtist"],
                           item.get("strArtistFanart") or f"https://www.theaudiodb.com/artist/{item['idArtist']}",
                           country=item.get("strCountry"), tags=[item.get("strGenre", "")])
                for item in payload.get("artists") or [] if item.get("idArtist") and item.get("strArtist")
            ][:limit]
        if provider_id == "jamendo":
            payload = await _get_json(
                client, "https://api.jamendo.com/v3.0/artists/",
                params={"client_id": credentials["client_id"], "format": "json",
                        "namesearch": term, "limit": limit, "offset": offset},
            )
            return [
                _normalize("jamendo", str(item["id"]), item["name"],
                           item.get("shareurl", f"https://www.jamendo.com/artist/{item['id']}"),
                           country=item.get("location"))
                for item in payload.get("results", []) if item.get("id") and item.get("name")
            ]
        if provider_id == "audius":
            payload = await _get_json(
                client, "https://api.audius.co/v1/users/search",
                params={"query": term, "app_name": credentials.get("app_name", "breakout-radar"),
                        "limit": limit, "offset": offset},
            )
            return [
                _normalize("audius", item["id"], item["name"],
                           f"https://audius.co/{item.get('handle') or item['id']}",
                           disambiguation=item.get("bio"))
                for item in payload.get("data", []) if item.get("id") and item.get("name")
            ]
        if provider_id == "ticketmaster":
            payload = await _get_json(
                client, "https://app.ticketmaster.com/discovery/v2/attractions.json",
                params={"keyword": term, "classificationName": "music", "apikey": credentials["api_key"],
                        "size": limit, "page": offset // max(limit, 1)},
            )
            return [
                _normalize("ticketmaster", item["id"], item["name"],
                           item.get("url", f"https://www.ticketmaster.com/artist/{item['id']}"),
                           disambiguation=(
                               f"{(item.get('upcomingEvents') or {}).get('_total')} upcoming events"
                               if (item.get("upcomingEvents") or {}).get("_total") is not None
                               else None
                           ))
                for item in payload.get("_embedded", {}).get("attractions", [])
                if item.get("id") and item.get("name")
            ]
        if provider_id == "soundcloud":
            token = await _soundcloud_token(client, credentials)
            payload = await _get_json(
                client, "https://api.soundcloud.com/users",
                params={"q": term, "limit": limit, "offset": offset},
                headers={"Authorization": f"OAuth {token}"},
            )
            return [
                _normalize("soundcloud", str(item["id"]), item["username"],
                           item.get("permalink_url", f"https://soundcloud.com/{item.get('permalink', '')}"),
                           disambiguation=item.get("description"))
                for item in payload.get("collection", payload.get("data", []))
                if item.get("id") and item.get("username")
            ]
        if provider_id == "musixmatch":
            payload = await _get_json(
                client, "https://api.musixmatch.com/ws/1.1/artist.search",
                params={"q_artist": term, "apikey": credentials["api_key"], "page_size": limit,
                        "page": offset // max(limit, 1) + 1, "format": "json"},
            )
            artists = payload.get("message", {}).get("body", {}).get("artist_list", [])
            return [
                _normalize("musixmatch", str(item["artist"]["artist_id"]), item["artist"]["artist_name"],
                           f"https://www.musixmatch.com/artist/{item['artist']['artist_id']}")
                for item in artists if item.get("artist", {}).get("artist_id") and item["artist"].get("artist_name")
            ]
        if provider_id == "genius":
            payload = await _get_json(
                client, "https://api.genius.com/search",
                params={"q": term, "per_page": limit, "page": offset // max(limit, 1) + 1},
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            artists: dict[str, dict[str, Any]] = {}
            for hit in payload.get("response", {}).get("hits", []):
                artist = hit.get("result", {}).get("primary_artist", {})
                if artist.get("id") and artist.get("name"):
                    artists[str(artist["id"])] = artist
            return [
                _normalize("genius", artist_id, artist["name"], artist.get("url", "https://genius.com"))
                for artist_id, artist in artists.items()
            ]
    raise ValueError(f"Unsupported provider: {provider_id}")


def provider_status(
    enabled_provider_ids: list[str] | None = None,
    credentials: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    enabled_provider_ids = enabled_provider_ids or ["musicbrainz"]
    credentials = credentials or {}
    statuses = []
    for provider in PROVIDER_CATALOG:
        provider_id = provider["id"]
        provider_credentials = {
            field["key"]: credentials[f"{provider_id}.{field['key']}"]
            for field in provider["fields"]
            if f"{provider_id}.{field['key']}" in credentials
        }
        missing = [
            field["key"] for field in provider["fields"]
            if field["key"] not in provider_credentials and not field.get("optional", False)
        ]
        enabled = provider_id in enabled_provider_ids
        configured = not missing
        if provider_id in {"musicbrainz", "wikidata", "deezer"}:
            configured = True
        if enabled and configured:
            state = "available"
        elif enabled:
            state = "needs_credentials"
        else:
            state = "disabled"
        statuses.append({
            "id": provider_id,
            "name": provider["name"],
            "status": state,
            "configured": configured,
            "enabled": enabled,
            "description": provider["description"],
            "url": provider["url"],
            "access_note": provider["access_note"],
            "fields": provider["fields"],
            "configured_fields": [
                field["key"] for field in provider["fields"]
                if field["key"] in provider_credentials
            ],
        })
    return statuses


async def search_enabled_providers(
    enabled_provider_ids: list[str],
    credentials: dict[str, str],
    *,
    query: str | None,
    area: str | None,
    genre: str | None,
    limit: int,
    offset: int = 0,
) -> dict[str, Any]:
    statuses = {provider["id"]: provider for provider in provider_status(enabled_provider_ids, credentials)}
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for provider_id in enabled_provider_ids:
        status = statuses[provider_id]
        if not status["configured"]:
            missing = [
                field["key"] for field in status["fields"]
                if field["key"] not in credentials and not field.get("optional", False)
            ]
            errors.append(f"{status['name']}: missing credentials ({', '.join(missing)})")
            continue
        provider_credentials = {
            field["key"]: credentials[f"{provider_id}.{field['key']}"]
            for field in status["fields"]
            if f"{provider_id}.{field['key']}" in credentials
        }
        for provider_area in expand_area_filter(area):
            try:
                items.extend(await search_provider(
                    provider_id,
                    query=query,
                    area=provider_area,
                    genre=genre,
                    limit=limit,
                    offset=offset,
                    credentials=provider_credentials,
                ))
            except (RuntimeError, ValueError, KeyError) as exc:
                logger.warning(
                    "Search failed for provider %s in area %r: %s",
                    provider_id,
                    provider_area,
                    exc,
                )
                errors.append(f"{status['name']} ({provider_area or 'any area'}): {exc}")
    return {"items": items, "count": len(items), "offset": offset, "errors": errors}
