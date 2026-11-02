from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ShortText = Annotated[str, Field(min_length=1, max_length=120)]
OptionalText = Annotated[str | None, Field(max_length=120)]


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class ArtistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ShortText
    country: OptionalText = None
    city: OptionalText = None
    genre: OptionalText = None
    source_name: OptionalText = None
    source_url: Annotated[str | None, Field(max_length=2048)] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Artist name cannot be blank")
        return value

    @field_validator("country", "city", "genre", "source_name")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        return clean_optional_text(value)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        value = clean_optional_text(value)
        if value is not None:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Source URL must be an absolute HTTP or HTTPS URL")
        return value


class ArtistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ShortText | None = None
    country: OptionalText = None
    city: OptionalText = None
    genre: OptionalText = None
    source_name: OptionalText = None
    source_url: Annotated[str | None, Field(max_length=2048)] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Artist name cannot be blank")
        return value

    @field_validator("country", "city", "genre", "source_name")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        return clean_optional_text(value)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        value = clean_optional_text(value)
        if value is not None:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Source URL must be an absolute HTTP or HTTPS URL")
        return value


class ArtistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    country: str | None
    city: str | None
    genre: str | None
    source_name: str | None
    source_url: str | None
    created_at: datetime
    updated_at: datetime


class ArtistPage(BaseModel):
    items: list[ArtistRead]
    total: int
    limit: int
    offset: int


class HealthRead(BaseModel):
    status: str
    database: str
    authentication: str
    configured_data_providers: list[str]


class DiscoveryArtist(BaseModel):
    id: str
    external_id: str
    provider_id: str
    name: str
    country: str | None
    area: str | None
    type: str | None
    disambiguation: str | None
    tags: list[str]
    source_url: str


class DiscoveryPage(BaseModel):
    items: list[DiscoveryArtist]
    count: int
    offset: int
    errors: list[str] = Field(default_factory=list)


class ProviderRead(BaseModel):
    id: str
    name: str
    status: str
    configured: bool
    enabled: bool
    description: str
    url: str
    access_note: str
    fields: list[dict[str, str | bool]]
    configured_fields: list[str]


class ProviderSettingsWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled_provider_ids: list[str] = Field(max_length=16)
    credential_updates: dict[str, dict[str, Annotated[str, Field(max_length=8192)]]] = Field(
        default_factory=dict,
        max_length=16,
    )
    clear_credentials: list[Annotated[str, Field(max_length=120)]] = Field(
        default_factory=list,
        max_length=128,
    )


class DiscoverySettingsWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    areas: list[ShortText] = Field(default_factory=list, max_length=10)
    genres: list[ShortText] = Field(default_factory=list, max_length=10)
    result_limit: int = Field(default=10, ge=1, le=25)
    enabled: bool = True

    @field_validator("areas", "genres")
    @classmethod
    def clean_filter_values(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def limit_filter_combinations(self) -> "DiscoverySettingsWrite":
        if self.areas and self.genres and len(self.areas) * len(self.genres) > 100:
            raise ValueError("Configure no more than 100 region/genre combinations")
        return self


class DiscoverySettingsRead(DiscoverySettingsWrite):
    updated_at: datetime | None = None
    interval_seconds: int


class DiscoveryQueueItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_id: str
    external_id: str
    name: str
    country: str | None
    area: str | None
    artist_type: str | None
    disambiguation: str | None
    tags: list[str]
    source_url: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    last_query_area: str | None
    last_query_genre: str | None


class DiscoveryQueuePage(BaseModel):
    items: list[DiscoveryQueueItemRead]
    total: int
    limit: int
    offset: int


class DiscoveryQueueReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(accepted|dismissed)$")
