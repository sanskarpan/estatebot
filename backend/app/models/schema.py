"""Canonical application models shared by scraping, storage, and the API."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceSite(str, Enum):
    darglobal = "darglobal"
    wasalt = "wasalt"


class RecordType(str, Enum):
    project = "project"
    sale_listing = "sale_listing"
    rent_listing = "rent_listing"
    plan = "plan"
    auction = "auction"


class PropertyCategory(str, Enum):
    apartment = "apartment"
    villa = "villa"
    hotel_room = "hotel_room"
    land = "land"
    commercial = "commercial"
    other = "other"


class DescriptionLang(str, Enum):
    en = "en"
    ar = "ar"
    mixed = "mixed"
    unknown = "unknown"


class ListingType(str, Enum):
    sale = "sale"
    rent = "rent"


class RentPeriod(str, Enum):
    monthly = "monthly"
    yearly = "yearly"


class Listing(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_site: SourceSite
    source_id: str = Field(min_length=1)
    source_url: str
    record_type: RecordType
    name: str = Field(min_length=1)
    description: str | None = None
    description_lang: DescriptionLang = DescriptionLang.en
    developer_name: str | None = None
    brand_partner: str | None = None
    property_category: PropertyCategory | None = None
    status: str | None = None
    location_country: str | None = None
    location_city: str | None = None
    location_city_raw: str | None = None
    location_area: str | None = None
    masterplan_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    price_display_text: str | None = None
    listing_type: ListingType | None = None
    rent_period: RentPeriod | None = None
    area_sqm_min: float | None = None
    area_sqm_max: float | None = None
    bedrooms: str | None = None
    bedrooms_min: int | None = None
    bedrooms_max: int | None = None
    bathrooms: int | None = None
    unit_types_raw: str | None = None
    unit_types_normalized: list[str] = Field(default_factory=list)
    amenities: list[str] = Field(default_factory=list)
    expected_completion_date: date | None = None
    expected_completion_raw: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    brochure_url: str | None = None
    related_source_ids: list[str] = Field(default_factory=list)
    posted_or_updated_date: date | None = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    raw_snapshot_path: str | None = None

    @field_validator("name", "source_id", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        if value is None:
            return value
        value = str(value).strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("source_url", "brochure_url", mode="before")
    @classmethod
    def validate_urls(cls, value: Any) -> Any:
        if value is None:
            return value
        parsed = urlparse(str(value))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute http(s) URL")
        return str(value)

    @field_validator("price_amount", "area_sqm_min", "area_sqm_max", mode="before")
    @classmethod
    def coerce_positive_numbers(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return float(value)

    @model_validator(mode="after")
    def validate_business_rules(self) -> "Listing":
        if self.price_amount is not None and self.price_amount <= 0:
            raise ValueError("price_amount must be greater than zero")
        if self.area_sqm_min is not None and self.area_sqm_min <= 0:
            raise ValueError("area_sqm_min must be greater than zero")
        if self.area_sqm_max is not None and self.area_sqm_max <= 0:
            raise ValueError("area_sqm_max must be greater than zero")
        if self.area_sqm_min is not None and self.area_sqm_max is not None and self.area_sqm_min > self.area_sqm_max:
            raise ValueError("area_sqm_min cannot exceed area_sqm_max")
        if self.bedrooms_min is not None and self.bedrooms_min < 0:
            raise ValueError("bedrooms_min cannot be negative")
        if self.bedrooms_max is not None and self.bedrooms_max < 0:
            raise ValueError("bedrooms_max cannot be negative")
        if self.bedrooms_min is not None and self.bedrooms_max is not None and self.bedrooms_min > self.bedrooms_max:
            raise ValueError("bedrooms_min cannot exceed bedrooms_max")
        if self.bathrooms is not None and self.bathrooms < 0:
            raise ValueError("bathrooms cannot be negative")
        if self.source_site == SourceSite.darglobal and "darglobal.co.uk" not in urlparse(self.source_url).netloc:
            raise ValueError("DarGlobal source_url must be on darglobal.co.uk")
        if self.source_site == SourceSite.wasalt and not ({"wasalt.sa", "wasalt.com"} & set(_host_parts(urlparse(self.source_url).netloc))):
            raise ValueError("Wasalt source_url must be on wasalt.sa or wasalt.com")
        if self.record_type == RecordType.sale_listing and self.listing_type not in (None, ListingType.sale):
            raise ValueError("sale_listing must have sale listing_type")
        if self.record_type == RecordType.rent_listing and self.listing_type not in (None, ListingType.rent):
            raise ValueError("rent_listing must have rent listing_type")
        return self


def _host_parts(host: str) -> list[str]:
    return [host, host.removeprefix("www.")]


class ContentDocument(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_site: SourceSite
    source_id: str = Field(min_length=1)
    source_url: str
    content_type: str
    title: str = Field(min_length=1)
    publish_date: date | None = None
    body_text: str = Field(min_length=1)
    related_source_ids: list[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    @field_validator("title", "body_text", "source_id", mode="before")
    @classmethod
    def trim_document_text(cls, value: Any) -> Any:
        if value is None:
            return value
        value = str(value).strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("source_url")
    @classmethod
    def validate_document_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute http(s) URL")
        return value


class Citation(BaseModel):
    source_id: str
    source_site: SourceSite
    source_url: str
    name: str
    record_type: str | None = None
    location: str | None = None
    property_category: str | None = None
    price: str | None = None
    bedrooms: str | None = None
    image_url: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=160)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    model_used: str | None = None
    retrieval_mode: str
    grounded: bool
    response_time_ms: int
    degraded: bool = False
