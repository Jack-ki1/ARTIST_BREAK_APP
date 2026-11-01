import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import create_database_tables, engine, get_db
from app.models import Artist
from app.providers import provider_status, search_musicbrainz
from app.schemas import (
    ArtistCreate,
    ArtistPage,
    ArtistRead,
    ArtistUpdate,
    DiscoveryPage,
    HealthRead,
    ProviderRead,
)


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database_tables()
    yield


app = FastAPI(
    title="Breakout Radar API",
    description=(
        "Artist identity records and live MusicBrainz catalog search. No audience "
        "measurements, rankings, or authentication are configured."
    ),
    version="1.0.0",
    lifespan=lifespan,
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
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=HealthRead)
def health() -> HealthRead:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc

    return HealthRead(
        status="ok",
        database="connected",
        authentication="disabled-demo-mode",
        configured_data_providers=["musicbrainz"],
    )


@app.get("/api/providers", response_model=list[ProviderRead])
def list_providers() -> list[ProviderRead]:
    return [ProviderRead(**provider) for provider in provider_status()]


@app.get("/api/discovery/search", response_model=DiscoveryPage)
async def discover_artists(
    query: str | None = Query(default=None, min_length=1, max_length=120),
    area: str | None = Query(default=None, min_length=1, max_length=120),
    genre: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=10, ge=1, le=25),
    offset: int = Query(default=0, ge=0, le=1000),
) -> DiscoveryPage:
    filters = {
        "query": query.strip() if query else None,
        "area": area.strip() if area else None,
        "genre": genre.strip() if genre else None,
        "limit": limit,
        "offset": offset,
    }
    if not any((filters["query"], filters["area"], filters["genre"])):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter an artist, region, or genre to search MusicBrainz",
        )
    try:
        result = await search_musicbrainz(**filters)
    except RuntimeError as exc:
        logger.warning("Artist discovery provider unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return DiscoveryPage(**result)


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
