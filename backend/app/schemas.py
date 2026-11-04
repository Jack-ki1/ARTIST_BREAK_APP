"""API request and response contracts for the v3 intelligence workspace."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscoveryRunRequest(StrictModel):
    query: str | None = Field(default=None, max_length=180)
    country: str | None = Field(default=None, max_length=80)
    genre: str | None = Field(default=None, max_length=80)
    source_ids: list[str] | None = Field(default=None, max_length=25)
    limit: int = Field(default=15, ge=1, le=50)


class SourceSettingsWrite(StrictModel):
    enabled_source_ids: list[str] = Field(default_factory=list, max_length=69)
    credential_updates: dict[str, dict[str, str]] = Field(default_factory=dict)
    clear_credentials: list[str] = Field(default_factory=list)


class SettingsWrite(StrictModel):
    config: dict[str, Any]


class ArtistCreate(StrictModel):
    name: str = Field(min_length=1, max_length=180)
    country: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=100)
    genres: list[str] = Field(default_factory=list, max_length=20)
    bio: str | None = Field(default=None, max_length=4000)
    website_url: str | None = Field(default=None, max_length=2048)
    primary_source_url: str | None = Field(default=None, max_length=2048)


class ReviewCreate(StrictModel):
    reviewer: str = Field(default="A&R Team", min_length=1, max_length=120)
    track_title: str | None = Field(default=None, max_length=240)
    track_url: str | None = Field(default=None, max_length=2048)
    scores: dict[str, float]
    verdict: Literal["standout", "strong", "promising", "developing", "pass"] = "promising"
    notes: str | None = Field(default=None, max_length=6000)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    risks: list[str] = Field(default_factory=list, max_length=20)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=30)

    @field_validator("scores")
    @classmethod
    def validate_scores(cls, value: dict[str, float]) -> dict[str, float]:
        allowed = {"songwriting", "vocals", "melody", "production", "originality", "performance", "identity"}
        if not value or set(value) - allowed:
            raise ValueError("Scores must include at least one supported artistic dimension")
        if any(not 0 <= float(score) <= 10 for score in value.values()):
            raise ValueError("Artistic scores must be between 0 and 10")
        return {key: round(float(score), 1) for key, score in value.items()}

    @field_validator("track_url")
    @classmethod
    def validate_track_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Track URL must use HTTP or HTTPS")
        return value


class DecisionCreate(StrictModel):
    decision: Literal["pursue", "meet", "watch", "hold", "signed", "passed"]
    owner: str = Field(default="A&R Team", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=6000)


class CandidateReview(StrictModel):
    action: Literal["accept", "dismiss"]
    note: str | None = Field(default=None, max_length=2000)


class ArtistPage(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class DiscoveryCandidates(BaseModel):
    items: list[dict[str, Any]]
    total: int
    sources_scanned: list[str] = Field(default_factory=list)
    last_run: dict[str, Any] | None = None


class DiscoveryRunResponse(BaseModel):
    run_id: str
    status: str
    sources_attempted: list[str]
    source_results: dict[str, Any]
    candidates_found: int
    artists_added: int
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    authentication: str
    source_count: int
