from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ProviderRead(BaseModel):
    id: str
    name: str
    status: str
    configured: bool
    description: str
    url: str
