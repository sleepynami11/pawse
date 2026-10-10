import json
import httpx
import pytest
from fastapi.testclient import TestClient
from pawse.app import app
from pawse import live, voice
from pawse.models import Clinic

REAL_CLIENT = httpx.AsyncClient


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for key in ['GEMINI_API_KEY', 'GEMINI_LIVE_MODEL', 'GOOGLE_PLACES_API_KEY', 'MAPIFY_BASE_URL']:
        monkeypatch.delenv(key, raising=False)
    live.minted.clear(); live.tool_active.clear(); live.session_clinics.clear()


def upstream(monkeypatch, handler):
    fake = lambda *a, **kw: REAL_CLIENT(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(live.httpx, 'AsyncClient', fake)
    monkeypatch.setattr(voice.httpx, 'AsyncClient', fake)


def call(c, name, args, **extra):
    return c.post('/api/v1/live/tool-calls', json={'id': 'fc1', 'name': name, 'args': args, 'share_with_gemini': True} | extra)


def test_token_requires_consent_and_key():
    with TestClient(app) as c:
        assert c.post('/api/v1/live/tokens', json={}).status_code == 422
        assert c.post('/api/v1/live/tokens', json={'share_with_gemini': False}).status_code == 422
        assert c.post('/api/v1/live/tokens', json={'share_with_gemini': True}).status_code == 503


def test_token_is_single_use_short_lived_and_locked_to_server_setup(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'private-gemini-key')
    seen = {}
    def handler(req):
        assert str(req.url) == live.TOKEN_URL and req.headers['x-goog-api-key'] == 'private-gemini-key'
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={'name': 'auth_tokens/ephemeral'})
    upstream(monkeypatch, handler)
    with TestClient(app) as c:
        r = c.post('/api/v1/live/tokens', json={'share_with_gemini': True, 'language': 'zh'})
    assert r.status_code == 201 and 'private-gemini-key' not in r.text
    body = r.json()
    assert body['token'] == 'auth_tokens/ephemeral' and body['model'] == 'gemini-3.8-live' and body['api_version'] == 'v1alpha'
    assert seen['uses'] == 1 and seen['expireTime'].endswith('Z') and seen['newSessionExpireTime'] < seen['expireTime']
    setup = seen['bidiGenerateContentSetup']
    assert setup['model'] == 'models/gemini-3.8-live'
    assert setup['generationConfig'] == {'responseModalities': ['AUDIO']}
    assert 'Mandarin Chinese' in setup['systemInstruction']['parts'][0]['text']
    tools = setup['tools'][0]['functionDeclarations']
    assert [t['name'] for t in tools] == body['tools'] and all(t['behavior'] == 'NON_BLOCKING' for t in tools)
    assert 'inputAudioTranscription' in setup and 'outputAudioTranscription' in setup


def test_token_upstream_failure_is_safe_and_minting_is_rate_limited(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'k')
    upstream(monkeypatch, lambda req: httpx.Response(429, text='upstream-private-detail'))
    with TestClient(app) as c:
        r = c.post('/api/v1/live/tokens', json={'share_with_gemini': True})
        assert r.status_code == 502 and 'upstream-private-detail' not in r.text
        for _ in range(live.TOKENS_PER_WINDOW - 1):
            c.post('/api/v1/live/tokens', json={'share_with_gemini': True})
        assert c.post('/api/v1/live/tokens', json={'share_with_gemini': True}).status_code == 429


def test_tool_call_envelope_requires_consent_and_known_tool():
    with TestClient(app) as c:
        assert call(c, 'search_policy', {'question': 'x'}, share_with_gemini=False).status_code == 422
        assert call(c, 'delete_everything', {}).status_code == 422


def test_search_policy_returns_cited_demo_evidence_never_approval():
    with TestClient(app) as c:
        r = call(c, 'search_policy', {'question': 'What is the deductible?'}, context={'insurance': {'company': 'Example Insurer'}})
    body = r.json()
    assert r.status_code == 200 and body['id'] == 'fc1'
    assert body['response']['insurance_approval'] == 'not_obtained' and body['response']['evidence']
    assert body['ui']['synthetic'] is True


def test_invalid_arguments_go_back_to_the_model():
    with TestClient(app) as c:
        r = call(c, 'assess_and_find_vets', {'concern': '', 'warning_signs': ['made_up']})
    assert r.status_code == 200 and r.json()['response'] == {'error': 'invalid_arguments'}


def test_assess_keeps_warning_signs_and_explains_missing_clinic_search():
    # No Gemini key: deterministic warning-sign guidance still answers.
    with TestClient(app) as c:
        r = call(c, 'assess_and_find_vets', {'concern': 'She is not breathing well', 'warning_signs': ['breathing_difficulty']})
    response = r.json()['response']
    assert response['urgency'] == 'emergency' and response['clinics'] == []
    assert response['clinic_search'] != 'complete' and 'location' in response['clinic_search_detail']


def test_open_clinic_call_needs_a_clinic_from_this_session_and_app_confirmation():
    clinic = Clinic(id='c1', name='Tierklinik Test', phone='+41 44 000 00 00', call_url='tel:+41440000000',
                    source='google_places', retrieved_at='2026-10-10T00:00:00Z')
    with TestClient(app) as a, TestClient(app) as b:
        a.get('/api/v1/voice/status'); b.get('/api/v1/voice/status')
        live.session_clinics[a.cookies.get('pawse_session')] = {'c1': clinic}
        assert call(b, 'open_clinic_call', {'clinic_id': 'c1'}).json()['response']['error'] == 'unknown_clinic'
        body = call(a, 'open_clinic_call', {'clinic_id': 'c1'}).json()
    assert body['response']['status'] == 'awaiting_owner_confirmation'
    assert body['ui'] == {'action': 'confirm_call', 'clinic_name': 'Tierklinik Test', 'phone': '+41 44 000 00 00', 'call_url': 'tel:+41440000000'}


def test_script_tool_reuses_reviewed_script_contract_and_reports_failures(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'k')
    upstream(monkeypatch, lambda req: httpx.Response(200, json={'candidates': [{'content': {'parts': [
        {'text': json.dumps({'lines': [{'german': 'Unsere Katze hinkt.', 'subtitle': 'Our cat is limping.'}]})}]}}]}))
    with TestClient(app) as c:
        body = call(c, 'draft_vet_call_script', {'message': 'Mimi is limping', 'recipient': 'vet'}).json()
        assert body['response']['status'] == 'draft_not_sent' and body['ui']['lines'][0]['german'] == voice.DISCLOSURE
        upstream(monkeypatch, lambda req: httpx.Response(500, text='upstream-private-detail'))
        failed = call(c, 'draft_vet_call_script', {'message': 'Mimi is limping'})
    assert failed.status_code == 200 and failed.json()['response']['error'] == 'tool_unavailable'
    assert 'upstream-private-detail' not in failed.text


def test_tool_concurrency_is_bounded_per_session():
    with TestClient(app) as c:
        c.get('/api/v1/voice/status')
        live.tool_active[c.cookies.get('pawse_session')] = 3
        assert call(c, 'search_policy', {'question': 'deductible'}).status_code == 429


def test_status_reports_live_model(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'k'); monkeypatch.setenv('GEMINI_LIVE_MODEL', 'gemini-3.8-live-extended-thinking')
    with TestClient(app) as c:
        status = c.get('/api/v1/voice/status').json()
    assert status['live_configured'] is True and status['live_model'] == 'gemini-3.8-live-extended-thinking'


def test_policy_requires_owner_profile_and_does_not_match_partial_demo_name():
    with TestClient(app) as c:
        missing = call(c, 'search_policy', {'question': 'deductible'})
        assert missing.json()['response']['status'] == 'needs_insurance_profile'
        for company in ['Pet', 'Demo insurer unrelated']:
            result = call(c, 'search_policy', {'question': 'deductible'}, context={'insurance': {'company': company}})
            assert result.json()['response']['matches_owner_policy'] is False
