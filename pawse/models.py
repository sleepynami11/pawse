"""Validated frontend contract. Unknown evidence is represented explicitly."""
import base64
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Location(Model):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Photo(Model):
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(max_length=4_200_000, repr=False)

    @model_validator(mode="after")
    def valid_image(self):
        try:
            raw = base64.b64decode(self.data, validate=True)
        except ValueError as exc:
            raise ValueError("Photo must be base64 encoded") from exc
        valid = {"image/jpeg": raw.startswith(b"\xff\xd8\xff"),
                 "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
                 "image/webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"}
        if not valid[self.mime_type] or not 12 <= len(raw) <= 3_000_000:
            raise ValueError("Use a JPEG, PNG or WebP image up to 3 MB")
        return self


def phone_uri(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[\s().-]", "", value)
    return "tel:" + cleaned if re.fullmatch(r"\+[1-9]\d{6,14}", cleaned) else None


class InsuranceProfile(Model):
    """What the owner told Pawse about their policy. Never proof of cover."""
    company: str = Field(min_length=1, max_length=100)
    plan: str | None = Field(default=None, max_length=120)


class Insurance(Model):
    company: str = Field(min_length=1, max_length=100)
    phone: str = Field(max_length=40)
    plan: str | None = Field(default=None, max_length=120)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value):
        if not phone_uri(value):
            raise ValueError("Use an international phone number, such as +41...")
        return value


RedFlag = Literal["breathing_difficulty", "collapse", "seizure", "unable_to_urinate", "suspected_poisoning", "major_trauma"]


class CareRequest(Model):
    query: str = Field(default="", max_length=4000)
    cat_name: str = Field(default="My cat", min_length=1, max_length=80)
    location: Location | None = None
    radius_km: float = Field(default=10, ge=0.5, le=50)
    language: str = Field(default="en", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    red_flags: list[RedFlag] = Field(default_factory=list, max_length=6)
    photo: Photo | None = None
    insurance: Insurance | None = None
    share_with_ai: bool = False
    share_location: bool = False

    @model_validator(mode="after")
    def meaningful(self):
        if not (self.query or self.photo or self.red_flags):
            raise ValueError("Describe your concern, attach a photo, or select a warning sign")
        return self


class Assessment(Model):
    urgency: Literal["emergency", "contact_vet", "unknown"] = "unknown"
    summary: str = Field(max_length=1800)
    questions: list[str] = Field(default_factory=list, max_length=5)
    services_to_ask_about: list[str] = Field(default_factory=list, max_length=6)
    source: Literal["reported_warning_signs", "gemini", "fallback"] = "fallback"
    disclaimer: str = "This is care navigation, not a diagnosis. A photo cannot rule out an emergency."


class Clinic(Model):
    id: str
    name: str
    address: str = ""
    phone: str | None = None
    call_url: str | None = None
    maps_url: str | None = None
    website: str | None = None
    location: Location | None = None
    distance_km: float | None = None
    rating: float | None = None
    open_now: bool | None = None
    emergency_service: Literal["unknown", "provider_reported"] = "unknown"
    services: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    opening_hours: list[str] = Field(default_factory=list, max_length=14)
    source: Literal["google_places", "gemini_maps", "mapify", "openstreetmap"]
    retrieved_at: str
    availability_note: str = "Call to confirm opening hours, services, and whether the clinic can see your cat."


class ClinicSearchRequest(Model):
    """Clinic lookup on its own: only coordinates leave the server, never symptoms."""
    location: Location
    radius_km: float = Field(default=10, ge=0.5, le=50)
    language: str = Field(default="en", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    share_location: bool = False


class ClinicSearchResult(Model):
    status: Literal["complete", "unavailable"]
    clinics: list[Clinic]
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int
    search_url: str
    completeness: str


ANALYSIS_TYPES = ("daily_summary", "weekly_report", "monthly_report", "health_prediction", "trend_analysis", "behavior_pattern", "vet_recommendation", "comparison", "multi_cat_comparison", "anomaly_detection")


class LegacyRequest(Model):
    mode: Literal["chat", "analysis"] = "chat"
    cat_id: int = Field(gt=0)
    message: str = Field(default="", max_length=4000)
    analysis_type: str | None = None
    time_range: Literal["24h", "7d", "30d"] = "24h"

    @model_validator(mode="after")
    def valid_operation(self):
        if self.mode == "chat" and not self.message:
            raise ValueError("A message is required")
        if self.mode == "analysis" and self.analysis_type not in ANALYSIS_TYPES:
            raise ValueError("Unsupported analysis type")
        return self


class InsuranceResult(Model):
    company: str
    phone: str
    plan: str | None = None
    call_url: str
    source: Literal["user_provided"]
    coverage: Literal["unconfirmed"]
    questions: list[str]
    note: str


class CareResult(Model):
    type: Literal["result"] = "result"
    request_id: str
    status: Literal["complete", "partial"]
    assessment: Assessment
    clinics: list[Clinic]
    insurance: InsuranceResult | None = None
    handoff: str
    warnings: list[str]
    providers: dict[str, str]
    elapsed_ms: int
    target_seconds: int
    search_url: str
    completeness: str
