"""Breakout Radar v3 — evidence-first A&R intelligence API."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import unicodedata
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from statistics import mean
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal, create_database_tables, engine, get_db
from app.integrations import collect_artist_evidence, search_identity_source
from app.models import (
    Artist, ArtistCandidate, ArtistDecision, ArtistIdentity, ArtistObservation,
    ArtisticReview, AppAlert, DiscoveryRun, RadarSettings, SourceConfiguration,
    SourceDailyUsage, SourceEvidence, utc_now,
)
from app.schemas import (
    ArtistCreate, CandidateReview, DecisionCreate, DiscoveryRunRequest,
    HealthResponse, ReviewCreate, SettingsWrite, SourceSettingsWrite,
)
from app.scoring import (
    DEFAULT_SETTINGS, artistic_overall, discovery_index, explain_discovery,
    recommendation, source_momentum,
)
from app.secrets import decrypt_credentials, encrypt_credentials
from app.source_catalog import (
    EVIDENCE_IMPLEMENTED_IDS, EXTRA_IMPLEMENTED_IDS, IMPLEMENTED_IDS,
    LEGACY_PROVIDER_IDS, source_catalog, source_ids, source_summary,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
APP_VERSION = "3.0.0"
DEFAULT_SOURCES = ["musicbrainz", "deezer", "wikidata", "wikipedia", "itunes", "bluesky", "gdelt"]
IDENTITY_SOURCE_IDS = IMPLEMENTED_IDS - EVIDENCE_IMPLEMENTED_IDS
EVIDENCE_SOURCE_IDS = EVIDENCE_IMPLEMENTED_IDS
YOUTUBE_QUOTA_ZONE = ZoneInfo("America/Los_Angeles")
SEEDS = [
    "Kenyan emerging artists", "East African new music", "Bongo Flava",
    "Kenyan hip hop", "Ugandan alternative music", "Rwandan music",
    "Ghanaian Afrobeats", "Nigerian alternative music", "African R&B",
    "Zambian music", "Ethiopian new music", "African amapiano",
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database_tables()
    yield


app = FastAPI(
    title="Breakout Radar — A&R Intelligence",
    description="Artist discovery, evidence analysis, artistic evaluation and A&R recommendations.",
    version=APP_VERSION,
    lifespan=lifespan,
)

origins = [
    item.strip() for item in os.getenv(
        "CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    ).split(",") if item.strip()
]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _normalise_name(value: str) -> str:
    clean = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", clean.casefold()).strip()


def _source_config(db: Session) -> tuple[set[str], dict[str, str]]:
    row = db.get(SourceConfiguration, 1)
    if row is None:
        return set(DEFAULT_SOURCES), {}
    return set(row.enabled_source_ids or []), decrypt_credentials(row.encrypted_credentials)


def _settings(db: Session) -> dict:
    row = db.get(RadarSettings, 1)
    stored = row.config if row and isinstance(row.config, dict) else {}
    merged = {**DEFAULT_SETTINGS, **stored}
    for key in ("discovery_weights", "artistic_weights", "tier_rules", "emerging_limits"):
        merged[key] = {**DEFAULT_SETTINGS[key], **(stored.get(key) or {})}
    return merged


def _save_settings(db: Session, config: dict) -> dict:
    merged = {**DEFAULT_SETTINGS, **config}
    for key in ("discovery_weights", "artistic_weights", "tier_rules", "emerging_limits"):
        merged[key] = {**DEFAULT_SETTINGS[key], **(config.get(key) or {})}
    # Keep the controls bounded. Unknown keys are dropped rather than persisted.
    allowed = set(DEFAULT_SETTINGS)
    merged = {key: value for key, value in merged.items() if key in allowed}
    row = db.get(RadarSettings, 1)
    if row is None:
        row = RadarSettings(id=1, config=merged)
        db.add(row)
    else:
        row.config = merged
    db.commit()
    return merged


def _daily_source_budget(source_id: str) -> int | None:
    if source_id == "youtube":
        try:
            return max(0, int(os.getenv("YOUTUBE_SEARCH_DAILY_BUDGET", "80")))
        except ValueError:
            logger.warning("Invalid YOUTUBE_SEARCH_DAILY_BUDGET; using 80")
            return 80
    return None


def _claim_source_request(db: Session, source_id: str, now: datetime | None = None) -> bool:
    """Reserve a source request before upstream I/O. Failed requests still count.

    YouTube quota buckets follow Google's midnight-Pacific reset, with DST handled
    by zoneinfo. Other sources currently have no application-level daily cap.
    """
    budget = _daily_source_budget(source_id)
    if budget is None:
        return True
    current = now or _now()
    quota_date = current.astimezone(YOUTUBE_QUOTA_ZONE).date().isoformat()
    row = db.scalar(select(SourceDailyUsage).where(
        SourceDailyUsage.source_id == source_id,
        SourceDailyUsage.quota_date == quota_date,
    ).with_for_update())
    if row is None:
        row = SourceDailyUsage(source_id=source_id, quota_date=quota_date, request_count=0)
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return False
    if row.request_count >= budget:
        return False
    row.request_count += 1
    db.commit()
    return True


def _candidate_group(rows: list[ArtistCandidate]) -> list[dict]:
    grouped: dict[str, list[ArtistCandidate]] = defaultdict(list)
    for row in rows:
        grouped[row.normalized_name].append(row)
    result = []
    for key, entries in grouped.items():
        entries.sort(key=lambda x: (x.discovery_score or 0, x.last_seen_at), reverse=True)
        lead = entries[0]
        providers = sorted({entry.source_id for entry in entries})
        # Breadth is a transparent source corroboration signal, not an audience score.
        score = round(min(100, (lead.discovery_score or 0) + max(0, len(providers) - 1) * 7), 1)
        result.append({
            "group_key": key,
            "name": lead.name,
            "country": next((x.country for x in entries if x.country), None),
            "city": next((x.city for x in entries if x.city), None),
            "genres": list(dict.fromkeys(tag for x in entries for tag in (x.genres or [])))[:8],
            "bio": lead.bio,
            "image_url": lead.image_url,
            "source_url": lead.source_url,
            "source_ids": providers,
            "source_count": len(providers),
            "candidate_ids": [x.id for x in entries],
            "discovery_score": score,
            "confidence": round(min(100, len(providers) * 12.5), 1),
            "signal_summary": list(dict.fromkeys(signal for x in entries for signal in (x.signal_summary or [])))[:8],
            "first_seen_at": _iso(min(x.first_seen_at for x in entries)),
            "last_seen_at": _iso(max(x.last_seen_at for x in entries)),
        })
    return sorted(result, key=lambda x: (x["discovery_score"], x["source_count"], x["last_seen_at"]), reverse=True)


def _artist_dict(artist: Artist, *, identities: list | None = None, observations: list | None = None,
                 evidence: list | None = None, reviews: list | None = None, decisions: list | None = None) -> dict:
    return {
        "id": artist.id, "name": artist.name, "stage_name": artist.stage_name,
        "country": artist.country, "city": artist.city, "region": artist.region,
        "genres": artist.genres or [], "bio": artist.bio, "image_url": artist.image_url,
        "website_url": artist.website_url, "primary_source": artist.primary_source,
        "primary_source_url": artist.primary_source_url, "stage": artist.stage,
        "review_status": artist.review_status, "discovery_score": artist.discovery_score,
        "discovery_confidence": artist.discovery_confidence, "artistic_score": artist.artistic_score,
        "combined_score": artist.combined_score, "recommendation_tier": artist.recommendation_tier,
        "excluded_reason": artist.excluded_reason,
        "first_seen_at": _iso(artist.first_seen_at), "last_seen_at": _iso(artist.last_seen_at),
        "created_at": _iso(artist.created_at), "updated_at": _iso(artist.updated_at),
        "identities": identities or [], "observations": observations or [],
        "evidence": evidence or [], "reviews": reviews or [], "decisions": decisions or [],
    }


def _recompute_artist(db: Session, artist: Artist, settings: dict) -> None:
    identities = db.scalars(select(ArtistIdentity).where(ArtistIdentity.artist_id == artist.id)).all()
    observations = db.scalars(
        select(ArtistObservation).where(ArtistObservation.artist_id == artist.id)
        .order_by(ArtistObservation.observed_at)
    ).all()
    serialised = [
        {"source_id": item.source_id, "metric": item.metric, "value": item.value, "observed_at": _iso(item.observed_at)}
        for item in observations
    ]
    series: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in serialised:
        series[(row["source_id"], row["metric"])].append(row)
    growths = []
    for (_source, metric), points in series.items():
        if metric in {"followers", "fans", "subscribers"}:
            momentum = source_momentum(points, metric, float(settings.get("min_observation_days", 7)))
            if momentum is not None:
                growths.append(momentum)
    features = {
        "momentum": round(sum(growths) / len(growths), 1) if growths else None,
        "independent_source_count": len({identity.source_id for identity in identities}),
        "release_activity": None,
        "live_activity": None,
        "search_interest": None,
        "catalogue_headroom": None,
    }
    releases = [float(row.value) for row in observations if row.metric in {"releases_12m", "albums"}]
    events = [float(row.value) for row in observations if row.metric in {"events_12m", "live_events"}]
    if releases:
        features["release_activity"] = min(100, max(0, mean(releases) * 12))
    if events:
        features["live_activity"] = min(100, max(0, mean(events) * 10))
    scored = discovery_index(features, settings.get("discovery_weights"))
    artist.discovery_score = scored["score"]
    artist.discovery_confidence = scored["confidence"]
    artist.recommendation_tier = recommendation(artist.discovery_score, artist.artistic_score, settings)["tier"]
    artist.combined_score = recommendation(artist.discovery_score, artist.artistic_score, settings)["score"]
    artist.updated_at = _now()


def _metric_observations(db: Session, artist_id: str, source_id: str, metrics: dict, source_url: str | None) -> int:
    count = 0
    for key, value in (metrics or {}).items():
        if not isinstance(value, (int, float)) or value < 0:
            continue
        metric = key.strip().lower().replace(" ", "_")[:80]
        if metric not in {"followers", "fans", "subscribers", "views", "releases_12m", "albums", "events_12m", "live_events", "tracks"}:
            continue
        db.add(ArtistObservation(
            artist_id=artist_id, source_id=source_id, metric=metric,
            value=float(value), unit="count", scope=source_id,
            source_url=source_url, confidence=1.0, context={"source_metric": key},
        ))
        count += 1
    return count


@app.get("/api/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    enabled, credentials = _source_config(db)
    return HealthResponse(
        status="ok", database="connected", version=APP_VERSION,
        authentication="disabled — loopback only",
        source_count=len(source_catalog(enabled, credentials)),
    )


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    enabled, credentials = _source_config(db)
    settings = _settings(db)
    artists = db.scalars(select(Artist)).all()
    pending = db.scalar(select(func.count()).select_from(ArtistCandidate).where(ArtistCandidate.status == "pending")) or 0
    reviews = db.scalar(select(func.count()).select_from(ArtisticReview)) or 0
    decisions = db.scalar(select(func.count()).select_from(ArtistDecision)) or 0
    runs = db.scalars(select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).limit(8)).all()
    source_rows = source_catalog(enabled, credentials)
    ready = sum(1 for item in source_rows if item["status"] == "ready")
    tiers = defaultdict(int)
    for artist in artists:
        tiers[artist.recommendation_tier or "hold"] += 1
    return {
        "overview": {
            "artists_tracked": len(artists), "pending_candidates": pending,
            "artistic_reviews": reviews, "a_and_r_decisions": decisions,
            "sources_total": len(source_rows), "sources_ready": ready,
            "emerging_artists": sum(1 for artist in artists if artist.stage == "emerging"),
        },
        "recommendation_tiers": dict(tiers),
        "recent_runs": [
            {"id": run.id, "kind": run.kind, "status": run.status,
             "started_at": _iso(run.started_at), "finished_at": _iso(run.finished_at),
             "candidates_found": run.candidates_found, "artists_added": run.artists_added,
             "source_results": run.source_results, "error": run.error}
            for run in runs
        ],
        "source_summary": source_summary(enabled, credentials),
        "settings": {"region_focus": settings.get("region_focus"), "auto_discovery_enabled": settings.get("auto_discovery_enabled")},
    }


@app.get("/api/sources")
def get_sources(db: Session = Depends(get_db)) -> dict:
    enabled, credentials = _source_config(db)
    rows = source_catalog(enabled, credentials)
    return {"items": rows, "summary": source_summary(enabled, credentials)}


@app.put("/api/sources")
def update_sources(payload: SourceSettingsWrite, db: Session = Depends(get_db)) -> dict:
    allowed = source_ids()
    enabled = list(dict.fromkeys(payload.enabled_source_ids))
    unknown = sorted(set(enabled) - allowed)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown sources: {', '.join(unknown)}")
    current = db.get(SourceConfiguration, 1)
    credentials = decrypt_credentials(current.encrypted_credentials if current else None)
    for source_id, values in payload.credential_updates.items():
        row = next((item for item in source_catalog({source_id}, credentials) if item["id"] == source_id), None)
        if row is None:
            raise HTTPException(status_code=422, detail=f"Unknown source: {source_id}")
        allowed_fields = {field["key"] for field in row["fields"]}
        unexpected = sorted(set(values) - allowed_fields)
        if unexpected:
            raise HTTPException(status_code=422, detail=f"Unknown {source_id} credential fields: {', '.join(unexpected)}")
        for key, value in values.items():
            if value.strip():
                credentials[f"{source_id}.{key}"] = value.strip()
    for key in payload.clear_credentials:
        if "." not in key:
            raise HTTPException(status_code=422, detail="Credential keys must use source_id.field_name")
        source_id, field = key.split(".", 1)
        row = next((item for item in source_catalog({source_id}, credentials) if item["id"] == source_id), None)
        if row is None or field not in {item["key"] for item in row["fields"]}:
            raise HTTPException(status_code=422, detail=f"Unknown credential field: {key}")
        credentials.pop(key, None)
    if current is None:
        current = SourceConfiguration(id=1)
        db.add(current)
    current.enabled_source_ids = enabled
    current.encrypted_credentials = encrypt_credentials(credentials) if credentials else None
    db.commit()
    return {"items": source_catalog(set(enabled), credentials), "summary": source_summary(set(enabled), credentials)}


@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)) -> dict:
    return {"config": _settings(db)}


@app.put("/api/settings")
def update_settings(payload: SettingsWrite, db: Session = Depends(get_db)) -> dict:
    config = payload.config
    if "artistic_share" in config and not 0 <= float(config["artistic_share"]) <= 100:
        raise HTTPException(status_code=422, detail="artistic_share must be between 0 and 100")
    if "max_artists_per_run" in config and not 1 <= int(config["max_artists_per_run"]) <= 250:
        raise HTTPException(status_code=422, detail="max_artists_per_run must be between 1 and 250")
    saved = _save_settings(db, config)
    return {"config": saved}


@app.get("/api/artists")
def list_artists(
    q: str | None = Query(default=None, max_length=160),
    country: str | None = Query(default=None, max_length=80),
    stage: str | None = Query(default=None, max_length=30),
    tier: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    query = select(Artist)
    if q:
        query = query.where(Artist.name.ilike(f"%{q.strip()}%"))
    if country:
        query = query.where(Artist.country.ilike(f"%{country.strip()}%"))
    if stage:
        query = query.where(Artist.stage == stage)
    if tier:
        query = query.where(Artist.recommendation_tier == tier)
    total_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(total_query) or 0
    rows = db.scalars(query.order_by(Artist.combined_score.desc().nullslast(), Artist.discovery_score.desc()).limit(limit).offset(offset)).all()
    return {"items": [_artist_dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@app.post("/api/artists", status_code=201)
def create_artist(payload: ArtistCreate, db: Session = Depends(get_db)) -> dict:
    name = payload.name.strip()
    normalized = _normalise_name(name)
    existing = db.scalar(select(Artist).where(Artist.normalized_name == normalized))
    if existing:
        raise HTTPException(status_code=409, detail="An artist with this normalized name already exists")
    artist = Artist(
        name=name, normalized_name=normalized, country=payload.country, city=payload.city,
        region=payload.region, genres=payload.genres, bio=payload.bio,
        website_url=payload.website_url, primary_source="manual",
        primary_source_url=payload.primary_source_url, stage="emerging",
    )
    db.add(artist)
    db.commit()
    db.refresh(artist)
    return _artist_dict(artist)


@app.get("/api/artists/{artist_id}")
def get_artist(artist_id: str, db: Session = Depends(get_db)) -> dict:
    artist = db.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    identities = db.scalars(select(ArtistIdentity).where(ArtistIdentity.artist_id == artist_id).order_by(ArtistIdentity.source_id)).all()
    observations = db.scalars(select(ArtistObservation).where(ArtistObservation.artist_id == artist_id).order_by(ArtistObservation.observed_at.desc()).limit(500)).all()
    evidence = db.scalars(select(SourceEvidence).where(SourceEvidence.artist_id == artist_id).order_by(SourceEvidence.published_at.desc().nullslast(), SourceEvidence.collected_at.desc()).limit(100)).all()
    reviews = db.scalars(select(ArtisticReview).where(ArtisticReview.artist_id == artist_id).order_by(ArtisticReview.created_at.desc())).all()
    decisions = db.scalars(select(ArtistDecision).where(ArtistDecision.artist_id == artist_id).order_by(ArtistDecision.created_at.desc())).all()
    return _artist_dict(
        artist,
        identities=[{"id": x.id, "source_id": x.source_id, "external_id": x.external_id, "source_url": x.source_url, "verified": x.verified, "match_confidence": x.match_confidence} for x in identities],
        observations=[{"id": x.id, "source_id": x.source_id, "metric": x.metric, "value": x.value, "unit": x.unit, "scope": x.scope, "observed_at": _iso(x.observed_at), "source_url": x.source_url, "confidence": x.confidence, "context": x.context} for x in observations],
        evidence=[{"id": x.id, "source_id": x.source_id, "evidence_type": x.evidence_type, "title": x.title, "summary": x.summary, "url": x.url, "published_at": _iso(x.published_at), "collected_at": _iso(x.collected_at), "context": x.context} for x in evidence],
        reviews=[{"id": x.id, "reviewer": x.reviewer, "track_title": x.track_title, "track_url": x.track_url, "scores": x.scores, "overall": x.overall, "verdict": x.verdict, "notes": x.notes, "strengths": x.strengths, "risks": x.risks, "is_ai_assisted": x.is_ai_assisted, "created_at": _iso(x.created_at)} for x in reviews],
        decisions=[{"id": x.id, "decision": x.decision, "note": x.note, "owner": x.owner, "created_at": _iso(x.created_at)} for x in decisions],
    )


@app.post("/api/artists/{artist_id}/reviews", status_code=201)
def add_artistic_review(artist_id: str, payload: ReviewCreate, db: Session = Depends(get_db)) -> dict:
    artist = db.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    settings = _settings(db)
    overall = artistic_overall(payload.scores, settings.get("artistic_weights"))
    if overall is None:
        raise HTTPException(status_code=422, detail="At least one artistic score is required")
    review = ArtisticReview(
        artist_id=artist_id, reviewer=payload.reviewer.strip(), track_title=payload.track_title,
        track_url=payload.track_url, scores=payload.scores, overall=overall,
        verdict=payload.verdict, notes=payload.notes, strengths=payload.strengths,
        risks=payload.risks, evidence=payload.evidence, is_ai_assisted=False,
    )
    db.add(review)
    artist.artistic_score = overall
    artist.review_status = "reviewed"
    scored = recommendation(artist.discovery_score, overall, settings)
    artist.combined_score = scored["score"]
    artist.recommendation_tier = scored["tier"]
    db.commit()
    db.refresh(review)
    return {"id": review.id, "overall": overall, "tier": scored["tier"], "scores": payload.scores, "created_at": _iso(review.created_at)}


@app.post("/api/artists/{artist_id}/decisions", status_code=201)
def add_decision(artist_id: str, payload: DecisionCreate, db: Session = Depends(get_db)) -> dict:
    artist = db.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    row = ArtistDecision(artist_id=artist_id, decision=payload.decision, note=payload.note, owner=payload.owner)
    db.add(row)
    if payload.decision in {"pursue", "meet", "watch", "hold", "signed", "passed"}:
        artist.stage = {"pursue": "shortlist", "meet": "meeting", "watch": "watchlist", "hold": "emerging", "signed": "signed", "passed": "passed"}[payload.decision]
    db.commit()
    db.refresh(row)
    return {"id": row.id, "decision": row.decision, "owner": row.owner, "created_at": _iso(row.created_at)}


@app.get("/api/discovery/candidates")
def list_candidates(
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(select(ArtistCandidate).where(ArtistCandidate.status == "pending").order_by(ArtistCandidate.discovery_score.desc(), ArtistCandidate.last_seen_at.desc()).limit(1500)).all()
    grouped = _candidate_group(rows)
    minimum_sources = max(1, int(_settings(db).get("min_sources_for_candidate", 2)))
    for item in grouped:
        item["corroborated"] = item["source_count"] >= minimum_sources
        item["corroboration_requirement"] = minimum_sources
    if q:
        grouped = [x for x in grouped if q.casefold() in x["name"].casefold()]
    return {"items": grouped[:limit], "total": len(grouped), "sources_scanned": sorted({x.source_id for x in rows})}


@app.post("/api/discovery/run", response_model=DiscoveryRunResponse)
async def run_discovery(payload: DiscoveryRunRequest, db: Session = Depends(get_db)) -> dict:
    enabled, credentials = _source_config(db)
    settings = _settings(db)
    available = {
        row["id"] for row in source_catalog(enabled, credentials)
        if row["status"] == "ready" and row["id"] in IDENTITY_SOURCE_IDS
    }
    requested = list(dict.fromkeys(payload.source_ids or sorted(available)))
    requested = [source_id for source_id in requested if source_id in available]
    maximum = min(15, int(settings.get("max_sources_per_run", 12)))
    requested = requested[:maximum]
    if not requested:
        raise HTTPException(
            status_code=422,
            detail="No ready identity-search sources are enabled. Configure at least one public source or add the required API credentials in Settings.",
        )

    seeds = [payload.query.strip()] if payload.query and payload.query.strip() else list(settings.get("discovery_seeds", SEEDS))[:2]
    if not seeds:
        seeds = SEEDS[:2]
    run = DiscoveryRun(kind="manual" if payload.query else "discovery", status="running",
                       query=payload.query, sources_attempted=requested)
    db.add(run)
    db.commit()
    db.refresh(run)

    semaphore = asyncio.Semaphore(3)
    source_results: dict[str, Any] = {}

    async def query_one(source_id: str, term: str) -> tuple[str, str, list[dict]]:
        async with semaphore:
            row = next(x for x in source_catalog(enabled, credentials) if x["id"] == source_id)
            source_credentials = {
                key.removeprefix(source_id + "."): value
                for key, value in credentials.items() if key.startswith(source_id + ".")
            }
            results = await search_identity_source(
                source_id, term, source_credentials, limit=payload.limit,
                country=payload.country, genre=payload.genre,
            )
            return source_id, term, results

    estimated_requests = len(requested) * len(seeds)
    max_requests = max(1, int(os.getenv("MAX_PROVIDER_CALLS_PER_SEARCH", "100")))
    if estimated_requests > max_requests:
        db.delete(run)
        db.commit()
        raise HTTPException(
            status_code=422,
            detail=f"Search would start {estimated_requests} upstream requests; maximum is {max_requests}. Reduce selected sources or discovery seeds.",
        )
    tasks = []
    for source_id in requested:
        for term in seeds:
            if not _claim_source_request(db, source_id):
                if source_results.get(source_id, {}).get("status") == "success":
                    source_results[source_id]["quota_exhausted"] = True
                else:
                    source_results[source_id] = {
                        "status": "quota_exhausted",
                        "error": "Daily YouTube search budget exhausted; quota resets at midnight Pacific Time."
                    }
                continue
            tasks.append(query_one(source_id, term))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    unique_groups: set[str] = set()
    candidates_written = 0
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Discovery source request failed: %s", result)
            continue
        source_id, term, items = result
        if source_results.get(source_id, {}).get("status") != "success":
            source_results[source_id] = {"status": "success", "queries": [], "results": 0}
        source_results[source_id]["queries"].append(term)
        source_results[source_id]["results"] += len(items)
        for item in items:
            name = (item.get("name") or "").strip()
            external_id = str(item.get("external_id") or "").strip()
            source_url = item.get("source_url") or ""
            if not name or not external_id or not source_url.startswith(("http://", "https://")):
                continue
            normalized = _normalise_name(name)
            if not normalized:
                continue
            excluded = [_normalise_name(value) for value in settings.get("exclude_names", []) if value]
            if any(term and (normalized == term or normalized.startswith(term + " ")) for term in excluded):
                continue
            limits = settings.get("emerging_limits", DEFAULT_SETTINGS["emerging_limits"])
            source_metrics = item.get("metrics") or {}
            try:
                if float(source_metrics.get("fans") or 0) > float(limits.get("max_known_follower_count", 500000)):
                    continue
                if float(source_metrics.get("albums") or 0) > float(limits.get("max_catalog_releases", 35)):
                    continue
            except (TypeError, ValueError):
                logger.warning("Invalid emerging-artist guardrail values; source-specific filters skipped")

            # Once an A&R reviewer has accepted a cross-source identity, future
            # scans append a new source-scoped observation instead of recreating
            # it as a fresh candidate.
            linked_identity = db.scalar(select(ArtistIdentity).where(
                ArtistIdentity.source_id == source_id,
                ArtistIdentity.external_id == external_id,
            ))
            if linked_identity is not None:
                linked_identity.last_seen_at = _now()
                linked_identity.source_url = source_url
                linked_identity.raw_metadata = {
                    "bio": item.get("bio"),
                    "metrics": item.get("metrics") or {},
                    "context": item.get("context") or {},
                    "last_query": term,
                }
                linked_artist = db.get(Artist, linked_identity.artist_id)
                if linked_artist is not None:
                    linked_artist.last_seen_at = _now()
                    _metric_observations(db, linked_artist.id, source_id, item.get("metrics") or {}, source_url)
                    _recompute_artist(db, linked_artist, settings)
                continue

            existing = db.scalar(select(ArtistCandidate).where(
                ArtistCandidate.source_id == source_id, ArtistCandidate.external_id == external_id,
            ))
            metrics = item.get("metrics") or {}
            raw_metadata = {
                "bio": item.get("bio"), "metrics": metrics,
                "context": item.get("context") or {}, "query": term,
            }
            if existing:
                existing.name = name
                existing.normalized_name = normalized
                existing.country = item.get("country") or existing.country
                existing.genres = list(dict.fromkeys((existing.genres or []) + (item.get("genres") or [])))[:12]
                existing.bio = item.get("bio") or existing.bio
                existing.image_url = item.get("image_url") or existing.image_url
                existing.source_url = source_url
                existing.raw_metadata = raw_metadata
                existing.last_seen_at = _now()
            else:
                existing = ArtistCandidate(
                    source_id=source_id, external_id=external_id, normalized_name=normalized,
                    name=name, country=item.get("country"), city=item.get("city"),
                    genres=item.get("genres") or [], bio=item.get("bio"),
                    image_url=item.get("image_url"), source_url=source_url,
                    raw_metadata=raw_metadata, discovery_score=0, discovery_confidence=12.5,
                    signal_summary=[f"Found on {source_id}", f"Matched discovery query: {term}"],
                )
                db.add(existing)
            unique_groups.add(normalized)
            candidates_written += 1
            if metrics:
                source_results[source_id]["metrics_returned"] = True

    db.flush()
    # Recalculate per-candidate source breadth without combining platform follower counts.
    pending_rows = db.scalars(select(ArtistCandidate).where(
        ArtistCandidate.status == "pending",
        ArtistCandidate.normalized_name.in_(list(unique_groups) or ["__no_candidates__"]),
    )).all()
    by_name: dict[str, set[str]] = defaultdict(set)
    for row in pending_rows:
        by_name[row.normalized_name].add(row.source_id)
    for row in pending_rows:
        breadth = len(by_name[row.normalized_name])
        row.discovery_score = round(min(100, 20 + breadth * 12.5), 1)
        row.discovery_confidence = round(min(100, breadth * 12.5), 1)
        row.signal_summary = [
            f"Confirmed by {breadth} independent source(s)",
            "No cross-platform audience total has been inferred",
        ]

    for source_id in requested:
        if source_id not in source_results:
            source_results[source_id] = {"status": "error", "error": "No response was returned"}
    run.source_results = source_results
    run.candidates_found = len(unique_groups)
    run.status = "completed" if any(item.get("status") == "success" for item in source_results.values()) else "partial"
    run.finished_at = _now()
    db.commit()
    return {
        "run_id": run.id, "status": run.status, "sources_attempted": requested,
        "source_results": source_results, "candidates_found": len(unique_groups),
        "artists_added": 0, "error": None,
    }


@app.post("/api/discovery/candidates/{candidate_id}/review")
def review_candidate(candidate_id: str, payload: CandidateReview, db: Session = Depends(get_db)) -> dict:
    candidate = db.get(ArtistCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    related = db.scalars(select(ArtistCandidate).where(
        ArtistCandidate.normalized_name == candidate.normalized_name,
        ArtistCandidate.status == "pending",
    )).all()
    artist = db.scalar(select(Artist).where(Artist.normalized_name == candidate.normalized_name))
    if payload.action == "accept":
        if artist is None:
            artist = Artist(
                name=candidate.name, normalized_name=candidate.normalized_name,
                country=candidate.country, city=candidate.city, genres=candidate.genres or [],
                bio=candidate.bio, image_url=candidate.image_url, primary_source=candidate.source_id,
                primary_source_url=candidate.source_url, stage="emerging", review_status="unreviewed",
                discovery_score=candidate.discovery_score, discovery_confidence=candidate.discovery_confidence,
            )
            db.add(artist)
            db.flush()
        linked = 0
        for item in related:
            existing_identity = db.scalar(select(ArtistIdentity).where(
                ArtistIdentity.source_id == item.source_id, ArtistIdentity.external_id == item.external_id,
            ))
            if not existing_identity:
                db.add(ArtistIdentity(
                    artist_id=artist.id, source_id=item.source_id, external_id=item.external_id,
                    source_url=item.source_url, source_name=item.name,
                    match_confidence=1.0 if item.normalized_name == artist.normalized_name else 0.7,
                    verified=False, raw_metadata=item.raw_metadata or {},
                ))
                metrics = (item.raw_metadata or {}).get("metrics", {})
                _metric_observations(db, artist.id, item.source_id, metrics, item.source_url)
                linked += 1
            item.status = "accepted"
            item.matched_artist_id = artist.id
            item.reviewed_at = _now()
            item.review_note = payload.note
        _recompute_artist(db, artist, _settings(db))
    else:
        linked = 0
        for item in related:
            item.status = "dismissed"
            item.reviewed_at = _now()
            item.review_note = payload.note
    db.commit()
    return {"action": payload.action, "linked_sources": linked, "artist_id": artist.id if payload.action == "accept" else None}


@app.post("/api/artists/{artist_id}/collect-evidence")
async def collect_evidence(artist_id: str, db: Session = Depends(get_db)) -> dict:
    artist = db.get(Artist, artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    enabled, credentials = _source_config(db)
    ready = {row["id"] for row in source_catalog(enabled, credentials) if row["status"] == "ready"}
    selected = sorted(EVIDENCE_SOURCE_IDS & ready)
    if not selected:
        raise HTTPException(status_code=422, detail="Enable and configure at least one evidence source in Settings")
    results = {}
    for source_id in selected:
        source_credentials = {
            key.removeprefix(source_id + "."): value
            for key, value in credentials.items() if key.startswith(source_id + ".")
        }
        try:
            items = await collect_artist_evidence(source_id, artist.name, source_credentials)
        except Exception as exc:
            results[source_id] = {"status": "error", "error": str(exc)}
            continue
        saved = 0
        for item in items:
            if not item.get("url"):
                continue
            dupe = db.scalar(select(SourceEvidence).where(
                SourceEvidence.artist_id == artist.id,
                SourceEvidence.source_id == source_id,
                SourceEvidence.url == item["url"],
            ))
            if dupe:
                continue
            published = item.get("published_at")
            published_dt = None
            if isinstance(published, str):
                try:
                    published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError:
                    published_dt = None
            elif isinstance(published, (int, float)):
                published_dt = datetime.fromtimestamp(published, tz=timezone.utc)
            db.add(SourceEvidence(
                artist_id=artist.id, source_id=source_id,
                evidence_type=item.get("evidence_type", "article"),
                title=(item.get("title") or artist.name)[:300],
                summary=item.get("summary"), url=item["url"],
                published_at=published_dt, context=item.get("context") or {},
            ))
            saved += 1
        results[source_id] = {"status": "success", "saved": saved}
    db.commit()
    return {"artist_id": artist.id, "sources": results, "evidence_saved": sum(x.get("saved", 0) for x in results.values())}


@app.get("/api/recommendations")
def get_recommendations(db: Session = Depends(get_db)) -> dict:
    settings = _settings(db)
    artists = db.scalars(select(Artist).order_by(Artist.discovery_score.desc())).all()
    result = []
    for artist in artists:
        scored = recommendation(artist.discovery_score, artist.artistic_score, settings)
        result.append({
            **_artist_dict(artist),
            "recommendation": scored,
            "decision_count": db.scalar(select(func.count()).select_from(ArtistDecision).where(ArtistDecision.artist_id == artist.id)) or 0,
        })
    result.sort(key=lambda item: (item["recommendation"]["score"], item["discovery_confidence"]), reverse=True)
    return {"items": result, "total": len(result)}


@app.get("/api/runs")
def get_runs(limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).limit(limit)).all()
    return {"items": [
        {"id": row.id, "kind": row.kind, "status": row.status, "query": row.query,
         "started_at": _iso(row.started_at), "finished_at": _iso(row.finished_at),
         "sources_attempted": row.sources_attempted, "source_results": row.source_results,
         "candidates_found": row.candidates_found, "artists_added": row.artists_added, "error": row.error}
        for row in rows
    ]}


@app.get("/api/alerts")
def get_alerts(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(AppAlert).order_by(AppAlert.created_at.desc()).limit(limit)).all()
    return {"items": [
        {"id": x.id, "artist_id": x.artist_id, "kind": x.kind, "title": x.title,
         "body": x.body, "read": x.read, "created_at": _iso(x.created_at)}
        for x in rows
    ]}


@app.patch("/api/alerts/{alert_id}/read")
def mark_alert_read(alert_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(AppAlert, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    row.read = True
    db.commit()
    return {"ok": True}


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(_request, exc: SQLAlchemyError):
    logger.exception("Database operation failed", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Database operation failed"})
