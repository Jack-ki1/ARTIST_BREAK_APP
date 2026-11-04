"""Persistent A&R intelligence models. New table names preserve legacy local data."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Artist(Base):
    __tablename__ = "radar_artists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    stage_name: Mapped[str | None] = mapped_column(String(180))
    country: Mapped[str | None] = mapped_column(String(80), index=True)
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(100))
    genres: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    website_url: Mapped[str | None] = mapped_column(String(2048))
    primary_source: Mapped[str | None] = mapped_column(String(80))
    primary_source_url: Mapped[str | None] = mapped_column(String(2048))
    stage: Mapped[str] = mapped_column(String(30), default="emerging", nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(30), default="unreviewed", nullable=False, index=True)
    discovery_score: Mapped[float | None] = mapped_column(Float)
    discovery_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    artistic_score: Mapped[float | None] = mapped_column(Float)
    combined_score: Mapped[float | None] = mapped_column(Float)
    recommendation_tier: Mapped[str] = mapped_column(String(30), default="hold", nullable=False, index=True)
    excluded_reason: Mapped[str | None] = mapped_column(String(240))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ArtistIdentity(Base):
    __tablename__ = "radar_artist_identities"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_radar_source_identity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    artist_id: Mapped[str] = mapped_column(ForeignKey("radar_artists.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(180))
    match_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ArtistObservation(Base):
    __tablename__ = "radar_observations"
    __table_args__ = (
        Index("ix_radar_obs_artist_metric_time", "artist_id", "metric", "observed_at"),
        Index("ix_radar_obs_source_time", "source_id", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    artist_id: Mapped[str] = mapped_column(ForeignKey("radar_artists.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False)
    metric: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="count", nullable=False)
    scope: Mapped[str] = mapped_column(String(60), default="platform", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    evidence_id: Mapped[str | None] = mapped_column(String(36))
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SourceEvidence(Base):
    __tablename__ = "radar_evidence"
    __table_args__ = (Index("ix_radar_evidence_artist_published", "artist_id", "published_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    artist_id: Mapped[str] = mapped_column(ForeignKey("radar_artists.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(50), default="catalogue", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    sentiment: Mapped[float | None] = mapped_column(Float)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ArtistCandidate(Base):
    __tablename__ = "radar_candidates"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_radar_candidate_source"),
        Index("ix_radar_candidate_status_score", "status", "discovery_score"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(80))
    city: Mapped[str | None] = mapped_column(String(120))
    genres: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    discovery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    discovery_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    signal_summary: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, index=True)
    matched_artist_id: Mapped[str | None] = mapped_column(ForeignKey("radar_artists.id", ondelete="SET NULL"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class ArtisticReview(Base):
    __tablename__ = "radar_artistic_reviews"
    __table_args__ = (Index("ix_radar_review_artist_created", "artist_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    artist_id: Mapped[str] = mapped_column(ForeignKey("radar_artists.id", ondelete="CASCADE"), index=True)
    reviewer: Mapped[str] = mapped_column(String(120), default="A&R Team", nullable=False)
    track_title: Mapped[str | None] = mapped_column(String(240))
    track_url: Mapped[str | None] = mapped_column(String(2048))
    scores: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), default="watch", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risks: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120))
    is_ai_assisted: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ArtistDecision(Base):
    __tablename__ = "radar_decisions"
    __table_args__ = (Index("ix_radar_decision_artist_created", "artist_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    artist_id: Mapped[str] = mapped_column(ForeignKey("radar_artists.id", ondelete="CASCADE"), index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(120), default="A&R Team", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SourceDailyUsage(Base):
    """Daily per-source request ledger; YouTube uses Google's Pacific reset day."""

    __tablename__ = "radar_source_daily_usage"
    __table_args__ = (UniqueConstraint("source_id", "quota_date", name="uq_radar_source_quota_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    quota_date: Mapped[str] = mapped_column(String(10), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class SourceConfiguration(Base):
    __tablename__ = "radar_source_configuration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled_source_ids: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["musicbrainz", "wikidata", "deezer", "wikipedia", "itunes", "bluesky", "gdelt"], nullable=False)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class RadarSettings(Base):
    __tablename__ = "radar_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DiscoveryRun(Base):
    __tablename__ = "radar_discovery_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="running", nullable=False, index=True)
    query: Mapped[str | None] = mapped_column(String(240))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sources_attempted: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    candidates_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    artists_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class AppAlert(Base):
    __tablename__ = "radar_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    artist_id: Mapped[str | None] = mapped_column(ForeignKey("radar_artists.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class WorkerHeartbeat(Base):
    __tablename__ = "radar_worker_heartbeat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    state: Mapped[str] = mapped_column(String(32), default="starting", nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
