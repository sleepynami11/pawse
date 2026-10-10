from pawse.providers import parse_maps_place


def test_maps_listing_requires_grounding_and_keeps_hours_unknown():
    assert parse_maps_place({'text': 'Invented clinic'}) is None
    clinic = parse_maps_place({'maps': {'placeId': 'test', 'title': 'Example Tierarzt - Google Maps',
        'uri': 'https://maps.google.com/', 'text': '* **Address:** Example Street\n* **Phone:** +41445550123\n* **Opening Hours:**\n  * Monday: 09:00–17:00'}})
    assert clinic.phone == '+41445550123'
    assert clinic.source == 'gemini_maps'
    assert clinic.open_now is None
    assert clinic.opening_hours == ['Monday: 09:00–17:00']


import json

import httpx
import pytest
from fastapi.testclient import TestClient

from pawse.app import app
from pawse.models import CareRequest, Clinic, Location
from pawse.providers import ProviderError, discover, gemini_maps_clinics, merge_clinics, rank_clinics


def place(pid, title, text):
    return {'maps': {'placeId': pid, 'title': title + ' - Google Maps', 'uri': f'https://maps.google.com/?cid={pid}', 'text': text}}


VET = place('vet1', 'Kleintierpraxis Test', '* **Address:** Teststrasse 1, 8000 Zürich\n* **Rating:** 4.8 (10 reviews)\n'
            '* **Phone:** +41 44 111 22 33\n* **Website:** https://vet.example/')
SHOP = place('shop', 'QUALIPET Center', '* **Address:** Somewhere\n* **Description:** Pet food and toys')
REVIEW = {'maps': {'placeId': 'vet1', 'title': 'Review of Kleintierpraxis Test - Google Maps', 'uri': 'https://maps.google.com/r', 'text': 'Great vet'}}


def maps_reply(*chunks):
    return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': 'model text with +41 00 000 00 00'}]},
                                                     'groundingMetadata': {'groundingChunks': list(chunks)}}]})


def request(**extra):
    return CareRequest(query='PRIVATE_SYMPTOM', location=Location(lat=47.37, lng=8.54), share_location=True, **extra)


@pytest.fixture
def no_providers(monkeypatch, tmp_path):
    for key in ('GEMINI_API_KEY', 'GOOGLE_PLACES_API_KEY', 'MAPIFY_BASE_URL'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('PAWSE_CLINIC_SNAPSHOT', str(tmp_path / 'snapshot.json'))
    return tmp_path / 'snapshot.json'


@pytest.mark.asyncio
async def test_maps_adapter_sends_only_location_and_keeps_grounded_vets(no_providers, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    bodies = []
    def handler(r):
        bodies.append(json.loads(r.content))
        return maps_reply(VET, SHOP, REVIEW)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await gemini_maps_clinics(request(), client)
    assert len(bodies) == 2 and all(b['tools'] == [{'googleMaps': {}}] for b in bodies)
    assert bodies[0]['toolConfig']['retrievalConfig']['latLng'] == {'latitude': 47.37, 'longitude': 8.54}
    assert 'PRIVATE_SYMPTOM' not in json.dumps(bodies)
    assert [c.id for c in result] == ['gmaps:vet1']
    clinic = result[0]
    assert clinic.call_url == 'tel:+41441112233' and clinic.rating == 4.8 and clinic.website == 'https://vet.example/'
    assert clinic.distance_km is None and clinic.open_now is None


@pytest.mark.asyncio
async def test_maps_adapter_failure_is_a_safe_provider_error(no_providers, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as client:
        with pytest.raises(ProviderError, match='gemini_maps_unavailable'):
            await gemini_maps_clinics(request(), client)


@pytest.mark.asyncio
async def test_discover_falls_back_from_places_to_maps_grounding(no_providers, monkeypatch):
    monkeypatch.setenv('GOOGLE_PLACES_API_KEY', 'blocked-key')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only')
    def handler(r):
        return httpx.Response(403) if r.url.host == 'places.googleapis.com' else maps_reply(VET)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await discover(request(), client)
    assert [c.source for c in result] == ['gemini_maps']


def osm_row(ident, name, phone, lat, lng, **extra):
    return {'id': f'osm:node:{ident}', 'name': name, 'address': '', 'phone': phone, 'call_url': 'tel:' + phone if phone else None,
            'location': {'lat': lat, 'lng': lng}, 'distance_km': 0, 'source': 'openstreetmap', 'retrieved_at': '2026-10-10T12:33:03Z',
            'maps_url': f'https://www.openstreetmap.org/node/{ident}', 'opening_hours_raw': extra.get('hours'),
            'record_sha256': 'x', 'license': 'ODbL-1.0'}


@pytest.mark.asyncio
async def test_snapshot_is_offline_fallback_within_radius(no_providers):
    no_providers.write_text(json.dumps({'clinics': [osm_row(1, 'Near Vet', '+41441112233', 47.371, 8.541, hours='Mo-Fr 08:00-18:00'),
                                                    osm_row(2, 'Far Vet', None, 47.9, 8.9)]}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as client:
        result = await discover(request(radius_km=5), client)
    assert [c.name for c in result] == ['Near Vet']
    assert result[0].source == 'openstreetmap' and result[0].opening_hours == ['Mo-Fr 08:00-18:00'] and result[0].distance_km < 1


@pytest.mark.asyncio
async def test_without_any_provider_or_snapshot_search_reports_not_configured(no_providers):
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderError, match='clinic_provider_not_configured'):
            await discover(request(), client)


def test_merge_keeps_provider_records_unmodified_and_drops_duplicate_snapshot_rows():
    maps = Clinic(id='gmaps:1', name='Kleintierpraxis Test GmbH', phone='+41 44 111 22 33', source='gemini_maps', retrieved_at='t')
    near = Clinic(id='osm:1', name='Kleintierpraxis Test', phone='+41441112233', location=Location(lat=47.37, lng=8.54),
                  distance_km=0.4, source='openstreetmap', retrieved_at='t')
    other = Clinic(id='osm:2', name='Other Vet', location=Location(lat=47.38, lng=8.55), distance_km=0.1, source='openstreetmap', retrieved_at='t')
    merged = merge_clinics([maps], [near, other], radius_km=10)
    assert [c.id for c in merged] == ['gmaps:1', 'osm:2']
    assert merged[0].location is None and merged[0].distance_km is None
    # Google Maps results stay one block ahead of the snapshot, even when a snapshot row is closer.
    assert [c.id for c in rank_clinics(merged)] == ['gmaps:1', 'osm:2']


def tool(c, name, args, **context):
    return c.post('/api/v1/live/tool-calls', json={'id': 'fc1', 'name': name, 'args': args, 'share_with_gemini': True, 'context': context}).json()


def test_live_saves_owner_insurance_for_the_session_and_reuses_it():
    with TestClient(app) as c:
        assert tool(c, 'search_policy', {'question': 'deductible'})['response']['status'] == 'needs_insurance_profile'
        saved = tool(c, 'set_insurance_profile', {'company': 'Example Insurer', 'plan': 'Accident only'})
        assert saved['ui'] == {'action': 'save_insurance_profile', 'company': 'Example Insurer', 'plan': 'Accident only'}
        answer = tool(c, 'search_policy', {'question': 'deductible'})['response']
        assert answer['owner_insurer'] == 'Example Insurer' and answer['matches_owner_policy'] is False
        assert answer['insurance_approval'] == 'not_obtained' and 'not from the owner' in answer['note']
        demo = tool(c, 'search_policy', {'question': 'deductible'}, insurance={'company': 'Pawse Demo Pet Insurance (fictional)'})
        assert demo['response']['matches_owner_policy'] is True and 'note' not in demo['response']
