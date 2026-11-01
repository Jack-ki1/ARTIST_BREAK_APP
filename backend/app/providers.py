import asyncio
import logging
import os
import time
from typing import Any
from urllib.parse import quote

import httpx


logger = logging.getLogger(__name__)
MUSICBRAINZ_API = "https://musicbrainz.org/ws/2/artist"
_request_lock = asyncio.Lock()
_last_request_at = 0.0


def _lucene_phrase(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


async def search_musicbrainz(
    *,
    query: str | None,
    area: str | None,
    genre: str | None,
    limit: int,
    offset: int = 0,
) -> dict[str, Any]:
    clauses = []
    if query:
        clauses.append(f"artist:{_lucene_phrase(query)}")
    if area:
        clauses.append(f"area:{_lucene_phrase(area)}")
    if genre:
        clauses.append(f"tag:{_lucene_phrase(genre)}")
    if not clauses:
        raise ValueError("Provide an artist name, area, or genre to search")

    global _last_request_at
    async with _request_lock:
        wait_seconds = 1.05 - (time.monotonic() - _last_request_at)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
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
                _last_request_at = time.monotonic()
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("MusicBrainz search timed out")
            raise RuntimeError("MusicBrainz did not respond in time") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("MusicBrainz returned HTTP %s", exc.response.status_code)
            raise RuntimeError(
                f"MusicBrainz search failed (HTTP {exc.response.status_code})"
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("MusicBrainz request failed: %s", exc)
            raise RuntimeError("Could not reach MusicBrainz") from exc
        except ValueError as exc:
            logger.warning("MusicBrainz returned invalid JSON")
            raise RuntimeError("MusicBrainz returned an invalid response") from exc

    items = []
    for artist in payload.get("artists", []):
        mbid = artist.get("id")
        name = artist.get("name")
        if not mbid or not name:
            continue
        tags = artist.get("tags") or []
        area_data = artist.get("area") or artist.get("begin-area") or {}
        items.append(
            {
                "id": mbid,
                "name": name,
                "country": artist.get("country"),
                "area": area_data.get("name"),
                "type": artist.get("type"),
                "disambiguation": artist.get("disambiguation") or None,
                "tags": [tag["name"] for tag in tags if tag.get("name")][:8],
                "source_url": f"https://musicbrainz.org/artist/{quote(mbid, safe='')}",
            }
        )

    return {"items": items, "count": payload.get("count", len(items)), "offset": offset}


def provider_status() -> list[dict[str, str | bool]]:
    return [
        {
            "id": "musicbrainz",
            "name": "MusicBrainz",
            "status": "available",
            "configured": True,
            "description": "Open artist catalog; search results are metadata, not popularity or growth metrics.",
            "url": "https://musicbrainz.org/",
        },
        {
            "id": "spotify",
            "name": "Spotify",
            "status": "not_configured",
            "configured": False,
            "description": "Not integrated. Requires an approved Spotify developer application and credentials.",
            "url": "https://developer.spotify.com/documentation/web-api",
        },
        {
            "id": "youtube",
            "name": "YouTube",
            "status": "not_configured",
            "configured": False,
            "description": "Not integrated. Requires a YouTube Data API key and quota review.",
            "url": "https://developers.google.com/youtube/v3",
        },
    ]
