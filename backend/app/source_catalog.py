"""Runtime metadata for 73 configurable data sources."""
from __future__ import annotations

from typing import Any

from app.source_data import CORE
from app.source_data_extra import EXTRA

LEGACY_PROVIDER_IDS = {
    "musicbrainz", "wikidata", "deezer", "spotify", "youtube", "apple_music",
    "lastfm", "discogs", "knowledge_graph", "theaudiodb", "jamendo", "audius",
    "ticketmaster", "soundcloud", "musixmatch", "genius",
}
EXTRA_IMPLEMENTED_IDS = {
    "wikipedia", "itunes", "bluesky", "mastodon", "setlistfm", "twitch",
}
EVIDENCE_IMPLEMENTED_IDS = {"gdelt", "reddit", "flickr", "openverse"}
IMPLEMENTED_IDS = LEGACY_PROVIDER_IDS | EXTRA_IMPLEMENTED_IDS | EVIDENCE_IMPLEMENTED_IDS
_ROWS = CORE + EXTRA


def source_ids() -> set[str]:
    return {row[0] for row in _ROWS}


def source_row(source_id: str) -> tuple[Any, ...] | None:
    return next((row for row in _ROWS if row[0] == source_id), None)


def source_catalog(enabled: set[str] | None = None, credentials: dict[str, str] | None = None) -> list[dict[str, Any]]:
    enabled = enabled or set()
    credentials = credentials or {}
    result = []
    for row in _ROWS:
        source_id, name, category, access, docs, description, fields, note = row
        missing = [key for key, _label, _secret in fields if not credentials.get(f"{source_id}.{key}")]
        supported = source_id in IMPLEMENTED_IDS
        capability = "identity_search" if source_id in (LEGACY_PROVIDER_IDS | EXTRA_IMPLEMENTED_IDS) else ("evidence_enrichment" if source_id in EVIDENCE_IMPLEMENTED_IDS else "catalogue_only")
        if source_id not in enabled:
            state = "disabled"
        elif not supported:
            state = {
                "research": "research_only",
                "licensed": "licensed_access",
                "partner": "partner_access",
                "artist": "artist_authorisation",
                "oauth": "approval_required",
                "client": "client_only",
                "manual": "manual_setup",
            }.get(access, "not_implemented")
        elif missing:
            state = "needs_credentials"
        else:
            state = "ready"
        result.append({
            "id": source_id, "name": name, "category": category,
            "access": access, "docs_url": docs, "description": description,
            "fields": [
                {"key": key, "label": label, "secret": secret,
                 "configured": bool(credentials.get(f"{source_id}.{key}"))}
                for key, label, secret in fields
            ],
            "missing_fields": missing, "enabled": source_id in enabled,
            "implemented": supported, "capability": capability,
            "connected": state == "ready",
            "status": state, "access_note": note,
        })
    return result


def configured_source_ids(enabled: set[str], credentials: dict[str, str]) -> list[str]:
    return [
        row["id"] for row in source_catalog(enabled, credentials)
        if row["status"] == "ready"
    ]


def source_summary(enabled: set[str], credentials: dict[str, str]) -> dict[str, int]:
    summary: dict[str, int] = {"total": len(_ROWS), "enabled": len(enabled)}
    for row in source_catalog(enabled, credentials):
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    return summary
