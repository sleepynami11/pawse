"""Bounded public-data collection. Offline handoff only; no live API routes."""
import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import Field

from .models import Clinic, Location, phone_uri
from .providers import distance

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ZURICH = Location(lat=47.3769, lng=8.5417)
MAX_BYTES = 2_000_000


class CrawlError(ValueError):
    """Safe failure without publishing upstream content."""


class CrawledClinic(Clinic):
    # This is a staging schema, NOT an expansion of the live Clinic source enum.
    source: Literal["openstreetmap"] = "openstreetmap"
    source_url: str
    record_sha256: str
    opening_hours_raw: str | None = None
    emergency_raw: str | None = None
    field_tags: dict[str, str] = Field(default_factory=dict)
    verification: Literal["community_listing_unverified"] = "community_listing_unverified"
    license: Literal["ODbL-1.0"] = "ODbL-1.0"


def query_for(radius_km: int) -> str:
    if isinstance(radius_km, bool) or not isinstance(radius_km, int) or not 1 <= radius_km <= 20:
        raise CrawlError("Radius must be an integer from 1 to 20 km.")
    return f'[out:json][timeout:15];nwr["amenity"="veterinary"](around:{radius_km * 1000},{ZURICH.lat},{ZURICH.lng});out center tags;'


def website_url(value):
    if not value:
        return None
    try:
        url = urlsplit(value)
        if url.scheme in {"http", "https"} and url.hostname and url.username is None and url.password is None:
            return value
    except ValueError:
        pass
    return None


def normalize(element: dict, retrieved_at: str) -> CrawledClinic | None:
    if not isinstance(element, dict):
        return None
    tags = element.get("tags")
    if not isinstance(tags, dict) or tags.get("amenity") != "veterinary":
        return None
    kind, ident = element.get("type"), element.get("id")
    if kind not in {"node", "way", "relation"} or type(ident) is not int or ident <= 0:
        return None
    name = tags.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    coords = element if kind == "node" else element.get("center")
    try:
        location = Location(lat=coords["lat"], lng=coords["lon"])
    except (ValueError, TypeError, KeyError):
        return None
    fields = {"name": "name", "location": "coordinates" if kind == "node" else "center"}

    def tag(field, *keys):
        for key in keys:
            value = tags.get(key)
            if isinstance(value, str) and value.strip():
                fields[field] = key
                return value.strip()
        return None

    raw_phone = tag("phone", "contact:phone", "phone")
    phone = re.sub(r"[\s().-]", "", raw_phone or "")
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if re.fullmatch(r"0\d{9}", phone):
        phone = "+41" + phone[1:]
    call_url = phone_uri(phone)
    if not call_url:
        phone = None
        fields.pop("phone", None)
    address = ", ".join(filter(None, [
        " ".join(filter(None, [tag("street", "addr:street"), tag("housenumber", "addr:housenumber")])),
        " ".join(filter(None, [tag("postcode", "addr:postcode"), tag("city", "addr:city")]))]))
    source_url = f"https://www.openstreetmap.org/{kind}/{ident}"
    return CrawledClinic(
        id=f"osm:{kind}:{ident}", name=name.strip(), address=address, phone=phone,
        call_url=call_url, location=location, distance_km=distance(ZURICH, location),
        website=website_url(tag("website", "contact:website", "website")), maps_url=source_url,
        open_now=None, rating=None, services=[], emergency_service="unknown",
        opening_hours_raw=tag("opening_hours_raw", "opening_hours"),
        emergency_raw=tag("emergency_raw", "emergency"),
        retrieved_at=retrieved_at, source_url=source_url, field_tags=fields,
        record_sha256=hashlib.sha256(json.dumps(element, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        availability_note="Community listing; call to verify contact, hours, services and appointments.")


def dataset(raw: bytes, radius_km: int, retrieved_at: str) -> dict:
    query = query_for(radius_km)
    if len(raw) > MAX_BYTES:
        raise CrawlError("Overpass response exceeds the 2 MB limit.")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise CrawlError("Overpass returned invalid JSON.") from None
    if not isinstance(payload, dict) or payload.get("remark") or not isinstance(payload.get("elements"), list):
        raise CrawlError("Overpass returned an incomplete or unsupported response.")
    unique = {}
    rejected, duplicates = 0, 0
    for element in payload["elements"]:
        row = normalize(element, retrieved_at)
        if row is None or row.distance_km > radius_km:
            rejected += 1
        elif row.id in unique:
            duplicates += 1
        else:
            unique[row.id] = row.model_dump()
    records = sorted(unique.values(), key=lambda row: (row["distance_km"], row["id"]))
    return {"schema_version": "pawse-crawled-clinic-v1", "manifest": {
        "source": "openstreetmap", "endpoint": OVERPASS_URL, "query": query,
        "center": ZURICH.model_dump(), "radius_km": radius_km, "retrieved_at": retrieved_at,
        "response_sha256": hashlib.sha256(raw).hexdigest(), "license": "ODbL-1.0",
        "attribution": "© OpenStreetMap contributors", "license_url": "https://www.openstreetmap.org/copyright",
        "input_count": len(payload["elements"]), "record_count": len(records),
        "rejected_count": rejected, "duplicate_id_count": duplicates,
        "coverage": "Partial community directory; not all clinics or verified current availability.",
        "refresh_policy": "Manual; reuse the snapshot, normally refresh no more than daily."},
        "clinics": records, "source_elements": payload["elements"]}


async def collect(radius_km=10, *, transport=None):
    query = query_for(radius_km)
    try:
        async with asyncio.timeout(30):
            async with httpx.AsyncClient(transport=transport, follow_redirects=False, timeout=20) as client:
                async with client.stream("POST", OVERPASS_URL, data={"data": query}, headers={
                    "User-Agent": "PawseClinicResearch/0.1 (+https://github.com/yyyuanfish/pawse)"}) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > MAX_BYTES:
                            raise CrawlError("Overpass response exceeds the 2 MB limit.")
        return dataset(bytes(raw), radius_km, datetime.now(timezone.utc).isoformat())
    except (httpx.HTTPError, TimeoutError):
        raise CrawlError("Overpass is unavailable or rate-limited. Keep the previous snapshot and retry later.") from None
