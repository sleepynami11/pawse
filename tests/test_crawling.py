import asyncio
import json

import httpx
import pytest

from pawse.crawling import CrawlError, collect, dataset, normalize, query_for

STAMP = "2026-10-10T12:00:00+00:00"


def clinic(**tags):
    return {"type": "node", "id": 12, "lat": 47.3769, "lon": 8.5417,
            "tags": {"amenity": "veterinary", "name": "Synthetic Clinic", **tags}}


def test_normalizes_contact_and_preserves_unverified_hours():
    row = normalize(clinic(phone="044 123 45 67", opening_hours="24/7", emergency="yes"), STAMP)
    assert row.phone == "+41441234567"
    assert row.call_url == "tel:+41441234567"
    assert row.open_now is None and row.emergency_service == "unknown"
    assert row.opening_hours_raw == "24/7" and row.emergency_raw == "yes"
    assert row.services == [] and row.rating is None
    assert row.source_url.endswith("/node/12") and len(row.record_sha256) == 64
    assert row.field_tags["phone"] == "phone"


def test_ways_missing_data_and_unsafe_website():
    item = clinic(website="javascript:alert(1)")
    item.update(type="way", center={"lat": item.pop("lat"), "lon": item.pop("lon")})
    row = normalize(item, STAMP)
    assert row.id == "osm:way:12"
    assert row.phone is None and row.website is None and row.open_now is None
    assert row.field_tags["location"] == "center"
    assert normalize(clinic(name=""), STAMP) is None
    assert normalize(clinic(amenity="pharmacy"), STAMP) is None
    assert normalize({"type": "node", "id": True, "tags": clinic()["tags"]}, STAMP) is None


def test_deduplication_provenance_and_partial_result_rejection():
    raw = json.dumps({"elements": [clinic(), clinic(), {"type": "bad"}]}).encode()
    result = dataset(raw, 10, STAMP)
    assert len(result["clinics"]) == 1
    assert result["manifest"]["duplicate_id_count"] == 1
    assert result["manifest"]["rejected_count"] == 1
    assert result["manifest"]["license"] == "ODbL-1.0"
    assert result["source_elements"][0] == clinic()
    with pytest.raises(CrawlError):
        dataset(b'{"remark":"runtime timeout","elements":[]}', 10, STAMP)


@pytest.mark.parametrize("radius", [0, 21, True, "10", 1.5])
def test_query_is_bounded(radius):
    with pytest.raises(CrawlError):
        query_for(radius)


def test_collection_uses_fixed_public_source_and_safe_failures():
    def handler(request):
        assert request.url.host == "overpass-api.de"
        assert request.method == "POST"
        assert b"veterinary" in request.content
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"elements": [clinic()]})
    result = asyncio.run(collect(transport=httpx.MockTransport(handler)))
    assert result["manifest"]["record_count"] == 1
    failed = httpx.MockTransport(lambda req: httpx.Response(429, text="private upstream diagnostic"))
    with pytest.raises(CrawlError, match="rate-limited") as exc:
        asyncio.run(collect(transport=failed))
    assert "diagnostic" not in str(exc.value)


def test_malformed_urls_coordinates_and_size_bounds():
    assert normalize(clinic(website="https://[bad"), STAMP).website is None
    assert normalize(clinic(website="https://user:password@example.org"), STAMP).website is None
    item = clinic()
    item["lat"] = 500
    assert normalize(item, STAMP) is None
    with pytest.raises(CrawlError, match="2 MB"):
        dataset(b" " * 2_000_001, 10, STAMP)
