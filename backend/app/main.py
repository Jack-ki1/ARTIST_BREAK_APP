import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal, create_database_tables, engine, get_db
from app.models import Artist, DiscoveryCandidate, DiscoveryConfiguration, ProviderConfiguration
from app.providers import (
    PROVIDER_CATALOG,
    expand_area_filter,
    provider_status,
    search_enabled_providers,
    search_provider,
)
from app.scheduler import DISCOVERY_INTERVAL_SECONDS, run_discovery_scheduler
from app.secrets import decrypt_credentials, encrypt_credentials
from app.schemas import (
    ArtistCreate,
    ArtistPage,
    ArtistRead,
    ArtistUpdate,
    DiscoveryPage,
    DiscoveryQueueItemRead,
    DiscoveryQueuePage,
    DiscoveryQueueReview,
    DiscoverySettingsRead,
    DiscoverySettingsWrite,
    HealthRead,
    ProviderRead,
    ProviderSettingsWrite,
)


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _report_scheduler_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exception = task.exception()
    if exception is not None:
        logger.error(
            "Background discovery scheduler stopped unexpectedly",
            exc_info=(type(exception), exception, exception.__traceback__),
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database_tables()
    wakeup = asyncio.Event()
    app.state.discovery_wakeup = wakeup
    scheduler_task = asyncio.create_task(
        run_discovery_scheduler(SessionLocal, search_provider, wakeup),
        name="provider-discovery-scheduler",
    )
    scheduler_task.add_done_callback(_report_scheduler_failure)
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Breakout Radar API",
    description=(
        "Artist identity records, scheduled multi-provider discovery, and a human-reviewed "
        "candidate queue. No audience measurements or rankings are configured."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _settings_response(configuration: DiscoveryConfiguration | None) -> DiscoverySettingsRead:
    return DiscoverySettingsRead(
        areas=configuration.areas if configuration else [],
        genres=configuration.genres if configuration else [],
        result_limit=configuration.result_limit if configuration else 10,
        enabled=configuration.enabled if configuration else True,
        updated_at=configuration.updated_at if configuration else None,
        interval_seconds=DISCOVERY_INTERVAL_SECONDS,
    )


allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=HealthRead)
def health(db: Session = Depends(get_db)) -> HealthRead:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc

    provider_configuration = db.get(ProviderConfiguration, 1)
    enabled_provider_ids = (
        provider_configuration.enabled_provider_ids
        if provider_configuration else ["musicbrainz"]
    )
    try:
        credentials = decrypt_credentials(
            provider_configuration.encrypted_credentials
            if provider_configuration else None
        )
    except RuntimeError as exc:
        logger.exception("Could not read configured provider credentials")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    available_provider_ids = [
        provider["id"]
        for provider in provider_status(enabled_provider_ids, credentials)
        if provider["enabled"] and provider["configured"]
    ]
    return HealthRead(
        status="ok",
        database="connected",
        authentication="disabled",
        configured_data_providers=available_provider_ids,
    )


@app.get("/api/providers", response_model=list[ProviderRead])
def list_providers(db: Session = Depends(get_db)) -> list[ProviderRead]:
    configuration = db.get(ProviderConfiguration, 1)
    enabled_provider_ids = (
        configuration.enabled_provider_ids if configuration else ["musicbrainz"]
    )
    try:
        credentials = decrypt_credentials(
            configuration.encrypted_credentials if configuration else None
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return [
        ProviderRead(**provider)
        for provider in provider_status(enabled_provider_ids, credentials)
    ]


@app.put("/api/providers")
def update_providers(
    payload: ProviderSettingsWrite,
    db: Session = Depends(get_db),
) -> list[ProviderRead]:
    specs = {provider["id"]: provider for provider in PROVIDER_CATALOG}
    enabled_ids = list(dict.fromkeys(payload.enabled_provider_ids))
    unknown_ids = sorted(set(enabled_ids) - specs.keys())
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown provider IDs: {', '.join(unknown_ids)}",
        )

    configuration = db.get(ProviderConfiguration, 1)
    credentials: dict[str, str] = {}
    if configuration is not None and configuration.encrypted_credentials:
        try:
            credentials = decrypt_credentials(configuration.encrypted_credentials)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    for provider_id, values in payload.credential_updates.items():
        if provider_id not in specs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown provider ID: {provider_id}",
            )
        allowed_fields = {field["key"] for field in specs[provider_id]["fields"]}
        unknown_fields = sorted(set(values) - allowed_fields)
        if unknown_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown credential fields for {provider_id}: {', '.join(unknown_fields)}",
            )
        for key, value in values.items():
            credential_key = f"{provider_id}.{key}"
            if value.strip():
                credentials[credential_key] = value.strip()

    for credential_key in payload.clear_credentials:
        if "." not in credential_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Credential keys must use provider_id.field_name",
            )
        provider_id, field_name = credential_key.split(".", 1)
        if (
            provider_id not in specs
            or field_name not in {field["key"] for field in specs[provider_id]["fields"]}
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unknown credential field: {credential_key}",
            )
        credentials.pop(credential_key, None)

    if configuration is None:
        configuration = ProviderConfiguration(id=1)
        db.add(configuration)
    configuration.enabled_provider_ids = enabled_ids
    if credentials:
        try:
            configuration.encrypted_credentials = encrypt_credentials(credentials)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
    else:
        configuration.encrypted_credentials = None
    db.commit()
    db.refresh(configuration)
    return [
        ProviderRead(**provider)
        for provider in provider_status(enabled_ids, credentials)
    ]


@app.get("/api/discovery/settings", response_model=DiscoverySettingsRead)
def get_discovery_settings(db: Session = Depends(get_db)) -> DiscoverySettingsRead:
    return _settings_response(db.get(DiscoveryConfiguration, 1))


@app.put("/api/discovery/settings", response_model=DiscoverySettingsRead)
def update_discovery_settings(
    payload: DiscoverySettingsWrite,
    db: Session = Depends(get_db),
) -> DiscoverySettingsRead:
    configuration = db.get(DiscoveryConfiguration, 1)
    if configuration is None:
        configuration = DiscoveryConfiguration(id=1)
        db.add(configuration)

    configuration.areas = payload.areas
    configuration.genres = payload.genres
    configuration.result_limit = payload.result_limit
    configuration.enabled = payload.enabled
    db.commit()
    db.refresh(configuration)

    wakeup = getattr(app.state, "discovery_wakeup", None)
    if wakeup is not None:
        wakeup.set()
    return _settings_response(configuration)


@app.get("/api/discovery/search", response_model=DiscoveryPage)
async def discover_artists(
    query: str | None = Query(default=None, min_length=1, max_length=120),
    area: list[str] = Query(default=[]),
    genre: list[str] = Query(default=[]),
    limit: int = Query(default=10, ge=1, le=25),
    offset: int = Query(default=0, ge=0, le=1000),
    db: Session = Depends(get_db),
) -> DiscoveryPage:
    query_text = query.strip() if query else None
    areas = list(dict.fromkeys(value.strip() for value in area if value.strip()))
    genres = list(dict.fromkeys(value.strip() for value in genre if value.strip()))
    if not any((query_text, areas, genres)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Enter an artist, region, or genre to search the enabled providers",
        )

    area_filters = areas or [None]
    genre_filters = genres or [None]
    if len(area_filters) * len(genre_filters) > 25:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A search can include at most 25 region/genre combinations",
        )

    try:
        configuration = db.get(ProviderConfiguration, 1)
        enabled_provider_ids = (
            configuration.enabled_provider_ids if configuration else ["musicbrainz"]
        )
        credentials = decrypt_credentials(
            configuration.encrypted_credentials if configuration else None
        )
        configured_providers = provider_status(enabled_provider_ids, credentials)
        ready_provider_count = sum(
            1 for item in configured_providers
            if item["enabled"] and item["configured"]
        )
        estimated_calls = (
            sum(len(expand_area_filter(area_value)) for area_value in area_filters)
            * len(genre_filters)
            * ready_provider_count
        )
        try:
            max_provider_calls = max(
                1, int(os.getenv("MAX_PROVIDER_CALLS_PER_SEARCH", "100"))
            )
        except ValueError:
            max_provider_calls = 100
        if estimated_calls > max_provider_calls:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"This filter/provider combination would make about {estimated_calls} "
                    "upstream requests. Reduce regions, genres, or enabled providers; "
                    f"the per-search safety limit is {max_provider_calls}."
                ),
            )

        search_filters = {
            "query": query_text,
            "area": areas[0] if len(areas) == 1 else None,
            "genre": genres[0] if len(genres) == 1 else None,
            "limit": limit,
            "offset": offset,
        }
        if len(areas) > 1:
            search_filters["areas"] = areas
        if len(genres) > 1:
            search_filters["genres"] = genres
        if "youtube" in enabled_provider_ids:
            search_filters["quota_session_factory"] = SessionLocal
        result = await search_enabled_providers(
            enabled_provider_ids,
            credentials,
            **search_filters,
        )
    except RuntimeError as exc:
        logger.exception("Could not run configured discovery providers")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return DiscoveryPage(**result)


@app.get("/api/discovery/queue", response_model=DiscoveryQueuePage)
def get_discovery_queue(
    status_filter: str = Query(default="pending", alias="status", pattern="^(pending|accepted|dismissed|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DiscoveryQueuePage:
    query = select(DiscoveryCandidate)
    count_query = select(func.count()).select_from(DiscoveryCandidate)
    if status_filter != "all":
        query = query.where(DiscoveryCandidate.status == status_filter)
        count_query = count_query.where(DiscoveryCandidate.status == status_filter)
    total = db.scalar(count_query) or 0
    items = db.scalars(
        query.order_by(DiscoveryCandidate.last_seen_at.desc(), DiscoveryCandidate.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return DiscoveryQueuePage(items=items, total=total, limit=limit, offset=offset)


@app.patch("/api/discovery/queue/{candidate_id}", response_model=DiscoveryQueueItemRead)
def review_discovery_candidate(
    candidate_id: str,
    payload: DiscoveryQueueReview,
    db: Session = Depends(get_db),
) -> DiscoveryCandidate:
    candidate = db.get(DiscoveryCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery candidate not found")
    if candidate.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Discovery candidate has already been reviewed",
        )

    if payload.status == "accepted":
        artist = db.scalar(
            select(Artist).where(
                Artist.source_name == candidate.provider_id,
                Artist.source_url == candidate.source_url,
            )
        )
        if artist is None:
            db.add(
                Artist(
                    name=candidate.name,
                    country=candidate.country,
                    city=candidate.area,
                    genre=", ".join(candidate.tags[:3]) or None,
                    source_name=candidate.provider_id,
                    source_url=candidate.source_url,
                )
            )
    candidate.status = payload.status
    db.commit()
    db.refresh(candidate)
    return candidate


@app.get("/api/artists", response_model=ArtistPage)
def list_artists(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ArtistPage:
    total = db.scalar(select(func.count()).select_from(Artist)) or 0
    items = db.scalars(
        select(Artist)
        .order_by(func.lower(Artist.name), Artist.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return ArtistPage(items=items, total=total, limit=limit, offset=offset)


@app.post("/api/artists", response_model=ArtistRead, status_code=status.HTTP_201_CREATED)
def create_artist(payload: ArtistCreate, db: Session = Depends(get_db)) -> Artist:
    artist = Artist(**payload.model_dump())
    db.add(artist)
    db.commit()
    db.refresh(artist)
    return artist


@app.get("/api/artists/{artist_id}", response_model=ArtistRead)
def get_artist(artist_id: str, db: Session = Depends(get_db)) -> Artist:
    artist = db.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")
    return artist


@app.patch("/api/artists/{artist_id}", response_model=ArtistRead)
def update_artist(
    artist_id: str,
    payload: ArtistUpdate,
    db: Session = Depends(get_db),
) -> Artist:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    artist = db.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")
    for field, value in updates.items():
        setattr(artist, field, value)
    db.commit()
    db.refresh(artist)
    return artist


@app.delete("/api/artists/{artist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artist(artist_id: str, db: Session = Depends(get_db)) -> Response:
    artist = db.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")
    db.delete(artist)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
