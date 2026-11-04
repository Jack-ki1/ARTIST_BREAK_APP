from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DiscoveryConfiguration(Base):
    __tablename__ = "discovery_configuration"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    areas: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    genres: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    result_limit: Mapped[int] = mapped_column(default=10, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ProviderConfiguration(Base):
    __tablename__ = "provider_configuration"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled_provider_ids: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["musicbrainz"], nullable=False)
    encrypted_credentials: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ProviderDailyUsage(Base):
    """Persistent per-provider daily request ledger for quota-limited APIs."""

    __tablename__ = "provider_daily_usage"

    provider_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    usage_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    request_count: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class DiscoveryCandidate(Base):
    __tablename__ = "discovery_candidates"
    __table_args__ = (
        UniqueConstraint("provider_id", "external_id", name="uq_candidate_provider_external"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    provider_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    artist_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    disambiguation: Mapped[str | None] = mapped_column(String(240), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_query_area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_query_genre: Mapped[str | None] = mapped_column(String(120), nullable=True)
