"""Approved API adapters beyond the legacy provider catalogue.

No HTML scraping or login-cookie harvesting is used. Platform metrics are only
collected when the official endpoint returns them for the authorised account.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.providers import search_provider as legacy_search

logger = logging.getLogger(__name__)
USER_AGENT = "BreakoutRadar/2.0 (+https://github.com/Jack-ki1/ARTIST_BREAK_APP)"
LEGACY_IDS = {
    "musicbrainz", "wikidata", "deezer", "spotify", "youtube", "apple_music",
    "lastfm", "discogs", "knowledge_graph", "theaudiodb", "jamendo", "audius",
    "ticketmaster", "soundcloud", "musixmatch", "genius",
}
_extra_token_cache: dict[str, tuple[str, float]] = {}


def _norm(source_id: str, external_id: str, name: str, url: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "provider_id": source_id,
        "external_id": str(external_id),
        "name": str(name).strip(),
        "source_url": url,
        "country": kwargs.get("country"),
        "city": kwargs.get("city"),
        "genres": [x for x in kwargs.get("genres", []) if isinstance(x, str)][:12],
        "bio": kwargs.get("bio"),
        "image_url": kwargs.get("image_url"),
        "metrics": kwargs.get("metrics", {}),
        "context": kwargs.get("context", {}),
    }


async def _json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                retry = response.headers.get("Retry-After", "")
                try:
                    delay = min(8.0, max(0.0, float(retry)))
                except ValueError:
                    delay = 0.5 * (2 ** attempt)
                import asyncio
                await asyncio.sleep(delay)
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Upstream returned a non-object JSON payload")
            return payload
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in {401, 403}:
                raise RuntimeError(f"Source denied access (HTTP {code}); check credentials, permissions or account approval") from exc
            raise RuntimeError(f"Source returned HTTP {code}") from exc
        except (httpx.RequestError, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                import asyncio
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("Source did not return a valid response after retries") from last_error


async def _reddit_token(client: httpx.AsyncClient, credentials: dict[str, str]) -> str:
    cache_key = credentials.get("client_id", "") + ":" + credentials.get("client_secret", "")
    cached = _extra_token_cache.get("reddit:" + cache_key)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    auth = base64.b64encode(
        f"{credentials['client_id']}:{credentials['client_secret']}".encode()
    ).decode()
    response = await client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        headers={
            "Authorization": f"Basic {auth}",
            "User-Agent": USER_AGENT + " contact=repository-issues",
        },
    )
    if not response.is_success:
        raise RuntimeError(f"Reddit OAuth failed (HTTP {response.status_code}); use an approved OAuth app")
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Reddit did not return an OAuth access token")
    _extra_token_cache["reddit:" + cache_key] = (token, time.monotonic() + max(60, int(payload.get("expires_in", 3600)) - 60))
    return token


async def search_identity_source(
    source_id: str,
    query: str,
    credentials: dict[str, str],
    *,
    limit: int = 20,
    country: str | None = None,
    genre: str | None = None,
) -> list[dict[str, Any]]:
    term = " ".join(x for x in (query, genre, country) if x).strip()
    if not term:
        return []
    if source_id in LEGACY_IDS:
        raw = await legacy_search(
            source_id, query=query or None, area=country, genre=genre,
            limit=min(limit, 25), offset=0, credentials=credentials,
        )
        mapped = []
        for item in raw:
            mapped.append(_norm(
                source_id,
                item.get("external_id") or item.get("id"),
                item["name"], item["source_url"],
                country=item.get("country") or country,
                genres=item.get("tags", []),
                bio=item.get("disambiguation"),
                metrics=item.get("metrics", {}),
                context=item.get("raw_metadata", {}),
            ))
        return mapped

    timeout = httpx.Timeout(18, connect=8)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if source_id == "itunes":
            payload = await _json(
                client, "https://itunes.apple.com/search",
                params={"term": term, "entity": "musicArtist", "limit": min(limit, 50)},
            )
            return [
                _norm("itunes", item["artistId"], item.get("artistName") or item.get("collectionName", term),
                      item.get("artistViewUrl") or f"https://music.apple.com/search?term={quote(term)}",
                      context={"result_count": item.get("artistId") and 1 or 0})
                for item in payload.get("results", [])
                if item.get("artistId") and item.get("artistName")
            ]

        if source_id == "wikipedia":
            payload = await _json(
                client, "https://en.wikipedia.org/w/rest.php/v1/search/page",
                params={"q": term, "limit": min(limit, 20)},
            )
            return [
                _norm("wikipedia", item.get("key") or item.get("title"), item.get("title", term),
                      "https://en.wikipedia.org/wiki/" + quote((item.get("key") or item.get("title", "")).replace(" ", "_")),
                      bio=item.get("description"),
                      image_url=(item.get("thumbnail") or {}).get("url"))
                for item in payload.get("pages", [])
                if item.get("key") or item.get("title")
            ]

        if source_id == "bluesky":
            payload = await _json(
                client, "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors",
                params={"q": term, "limit": min(limit, 100)},
            )
            return [
                _norm("bluesky", item.get("did") or item.get("handle"), item.get("displayName") or item.get("handle"),
                      "https://bsky.app/profile/" + item.get("handle", ""),
                      bio=item.get("description"), image_url=item.get("avatar"),
                      metrics={"followers": item.get("followersCount")} if item.get("followersCount") is not None else {})
                for item in payload.get("actors", [])
                if item.get("handle")
            ]

        if source_id == "mastodon":
            instance = credentials.get("instance_url", "https://mastodon.social").strip().rstrip("/")
            parsed = urlparse(instance)
            if parsed.scheme not in {"https"} or not parsed.netloc:
                raise ValueError("Mastodon instance URL must be an HTTPS origin")
            headers_local = dict(headers)
            if credentials.get("access_token"):
                headers_local["Authorization"] = f"Bearer {credentials['access_token']}"
            payload = await _json(
                client, instance + "/api/v2/search",
                params={"q": term, "type": "accounts", "limit": min(limit, 20)},
                headers=headers_local,
            )
            return [
                _norm("mastodon", item.get("id") or item.get("acct"), item.get("display_name") or item.get("acct"),
                      item.get("url") or instance, bio=item.get("note"),
                      image_url=item.get("avatar"),
                      metrics={"followers": item.get("followers_count")} if item.get("followers_count") is not None else {})
                for item in payload.get("accounts", [])
                if item.get("id") and (item.get("display_name") or item.get("acct"))
            ]

        if source_id == "setlistfm":
            payload = await _json(
                client, "https://api.setlist.fm/rest/1.0/search/artists",
                params={"artistName": term, "p": 1},
                headers={**headers, "x-api-key": credentials["api_key"], "Accept": "application/json"},
            )
            return [
                _norm("setlistfm", item.get("mbid") or item.get("name"), item.get("name", term),
                      item.get("url") or "https://www.setlist.fm/search?query=" + quote(term),
                      country=(item.get("country") or {}).get("name"))
                for item in payload.get("artist", [])
                if item.get("name")
            ]

        if source_id == "twitch":
            token = _extra_token_cache.get("twitch:" + credentials.get("client_id", ""))
            if token and token[1] > time.monotonic():
                bearer = token[0]
            else:
                response = await client.post(
                    "https://id.twitch.tv/oauth2/token",
                    data={"client_id": credentials["client_id"], "client_secret": credentials["client_secret"], "grant_type": "client_credentials"},
                )
                response.raise_for_status()
                obj = response.json()
                bearer = obj["access_token"]
                _extra_token_cache["twitch:" + credentials["client_id"]] = (bearer, time.monotonic() + max(60, int(obj.get("expires_in", 3600)) - 60))
            payload = await _json(
                client, "https://api.twitch.tv/helix/search/channels",
                params={"query": term, "first": min(limit, 100)},
                headers={"Client-Id": credentials["client_id"], "Authorization": f"Bearer {bearer}"},
            )
            return [
                _norm("twitch", item["id"], item["display_name"], "https://twitch.tv/" + item["broadcaster_login"],
                      bio=item.get("title"), metrics={"views": item.get("view_count")} if item.get("view_count") is not None else {})
                for item in payload.get("data", []) if item.get("id") and item.get("display_name")
            ]

        raise RuntimeError(
            f"{source_id} is listed in the source directory but does not have a live search adapter. "
            "The source's access requirements and official documentation are shown in Settings."
        )


async def collect_artist_evidence(
    source_id: str,
    artist_name: str,
    credentials: dict[str, str],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Fetch source-linked evidence; these results are not promoted to audience metrics."""
    timeout = httpx.Timeout(18, connect=8)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if source_id == "gdelt":
            payload = await _json(
                client, "https://api.gdeltproject.org/api/v2/doc/doc",
                params={"query": f'"{artist_name}"', "mode": "ArtList", "format": "json", "maxrecords": min(limit, 25), "sort": "HybridRel"},
            )
            return [
                {"source_id": "gdelt", "evidence_type": "press", "title": item.get("title", artist_name),
                 "summary": item.get("seendate"), "url": item.get("url"),
                 "published_at": item.get("seendate"), "context": {"domain": item.get("domain"), "language": item.get("language")}}
                for item in payload.get("articles", []) if item.get("url")
            ]

        if source_id == "reddit":
            token = await _reddit_token(client, credentials)
            payload = await _json(
                client, "https://oauth.reddit.com/search",
                params={"q": f'"{artist_name}"', "sort": "new", "limit": min(limit, 25), "type": "link"},
                headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
            )
            children = payload.get("data", {}).get("children", [])
            return [
                {"source_id": "reddit", "evidence_type": "community", "title": item.get("title", artist_name),
                 "summary": (item.get("selftext") or "")[:500],
                 "url": "https://www.reddit.com" + item.get("permalink", ""),
                 "published_at": item.get("created_utc"), "context": {"subreddit": item.get("subreddit"), "score": item.get("score"), "num_comments": item.get("num_comments")}}
                for child in children if isinstance(child, dict)
                for item in [child.get("data", {})] if item.get("permalink")
            ]

        if source_id == "flickr":
            payload = await _json(
                client, "https://www.flickr.com/services/rest/",
                params={"method": "flickr.photos.search", "api_key": credentials["api_key"],
                        "text": artist_name, "format": "json", "nojsoncallback": 1, "per_page": min(limit, 25),
                        "media": "photos", "content_type": 1},
                headers=headers,
            )
            return [
                {"source_id": "flickr", "evidence_type": "image", "title": item.get("title") or artist_name,
                 "summary": "Public Flickr image result; inspect licence before reuse.",
                 "url": f"https://www.flickr.com/photos/{item.get('owner')}/{item.get('id')}/",
                 "published_at": None,
                 "context": {"photo_id": item.get("id"), "owner": item.get("owner"), "license_id": item.get("license")}}
                for item in payload.get("photos", {}).get("photo", []) if item.get("id") and item.get("owner")
            ]

        if source_id == "openverse":
            payload = await _json(
                client, "https://api.openverse.org/v1/images/",
                params={"q": artist_name, "page_size": min(limit, 20)},
                headers=headers,
            )
            return [
                {"source_id": "openverse", "evidence_type": "image", "title": item.get("title") or artist_name,
                 "summary": item.get("creator"), "url": item.get("foreign_landing_url") or item.get("url"),
                 "published_at": None, "context": {"license": item.get("license"), "license_url": item.get("license_url"), "creator": item.get("creator")}}
                for item in payload.get("results", []) if item.get("foreign_landing_url") or item.get("url")
            ]
    raise RuntimeError(f"{source_id} is not an evidence adapter or is not configured")
