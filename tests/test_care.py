import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from pawse.app import app, records, active
from pawse.models import CareRequest, Clinic, Location, Photo, phone_uri
from pawse.providers import normalize_mapify, fallback_assessment, assess, google_clinics, mapify_clinics, rank_clinics, ProviderError
from pawse import service


@pytest.fixture(autouse=True)
def no_live_credentials(monkeypatch):
    for key in ['GEMINI_API_KEY','GOOGLE_PLACES_API_KEY','MAPIFY_BASE_URL','LEGACY_AGENT_BASE_URL','LEGACY_AGENT_USER_ID','LEGACY_AGENT_CAT_IDS']:
        monkeypatch.delenv(key, raising=False)
    records.clear(); active.clear()


def payload(**updates):
    return {'query':'My cat is not eating normally', **updates}


def test_phone_never_creates_arbitrary_scheme():
    assert phone_uri('+41 44 123 45 67') == 'tel:+41441234567'
    assert phone_uri('javascript:alert(1)') is None
    assert phone_uri('+41;1234567') is None
    assert phone_uri('0441234567') is None


def test_photo_rejects_fake_image_and_mime():
    import base64
    with pytest.raises(ValueError):
        Photo(mime_type='image/png', data=base64.b64encode(b'<script>alert(1)</script>').decode())


def test_no_downgrade_for_reported_warning():
    req=CareRequest(**payload(red_flags=['breathing_difficulty']))
    assert fallback_assessment(req).urgency=='emergency'


def test_unknown_not_open_and_non_vet_filtered():
    origin=Location(lat=47.37,lng=8.54)
    assert normalize_mapify({'place_id':'salon','name':'Hair Salon'}, {}, origin) is None
    clinic=normalize_mapify({'place_id':'vet','name':'Zurich Animal Hospital','status':'open_now'}, {}, origin)
    assert clinic.open_now is None
    assert clinic.phone is None
    assert clinic.emergency_service=='unknown'


def test_nearest_with_reported_open_before_closed():
    base={'source':'google_places','retrieved_at':'2026-10-10','name':'Vet'}
    a=Clinic(id='closed',distance_km=.1,open_now=False,**base)
    b=Clinic(id='open',distance_km=2,open_now=True,**base)
    assert rank_clinics([a,b])[0].id=='open'


def test_no_configuration_returns_honest_partial_result_and_call():
    with TestClient(app) as c:
        r=c.post('/api/v1/care/requests',json=payload(insurance={'company':'My insurer','phone':'+41 44 123 45 67'}))
        assert r.status_code==201
        d=r.json();assert d['status']=='partial'
        assert d['clinics']==[]
        assert d['assessment']['urgency']=='unknown'
        assert d['insurance']['coverage']=='unconfirmed'
        assert d['insurance']['call_url']=='tel:+41441234567'
        assert c.get('/api/v1/care/requests/'+d['request_id']).status_code==200
        assert c.delete('/api/v1/care/requests/'+d['request_id']).status_code==204
        assert c.get('/api/v1/care/requests/'+d['request_id']).status_code==404


def test_sessions_do_not_share_results():
    with TestClient(app) as a, TestClient(app) as b:
        id_=a.post('/api/v1/care/requests',json=payload()).json()['request_id']
        assert b.get('/api/v1/care/requests/'+id_).status_code==404


def test_sse_returns_safety_before_search_and_final():
    with TestClient(app) as c:
        r=c.post('/api/v1/care/requests?stream=true',json=payload(red_flags=['unable_to_urinate']))
        events=[json.loads(line[6:]) for line in r.text.splitlines() if line.startswith('data: ')]
        assert events[1]['type']=='safety'
        assert events[1]['assessment']['urgency']=='emergency'
        assert events[-1]['type']=='result'
        assert events[-1]['assessment']['urgency']=='emergency'
        assert active==set()


def test_bad_location_rejected_without_echoing_photo():
    with TestClient(app) as c:
        r=c.post('/api/v1/care/requests',json=payload(location={'lat':100,'lng':8},photo={'mime_type':'image/png','data':'PRIVATE_INVALID_DATA'}))
        assert r.status_code==422
        assert 'PRIVATE_INVALID_DATA' not in r.text


def test_cross_origin_post_rejected():
    with TestClient(app) as c:
        assert c.post('/api/v1/care/requests',json=payload(),headers={'origin':'https://example.com'}).status_code==403


def test_catalog_complete_and_legacy_disabled():
    with TestClient(app) as c:
        d=c.get('/api/v1/capabilities').json()
        assert len(d['legacy_intents'])==25
        assert len(d['legacy_tools'])==14
        assert len(d['analysis_types'])==10
        assert c.post('/api/v1/agent/requests',json={'mode':'chat','cat_id':1,'message':'hello'}).status_code==503


@pytest.mark.asyncio
async def test_ai_consent_prevents_network(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    def handler(r):raise AssertionError('No request allowed')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError,match='consent'):
            await assess(CareRequest(**payload()),client)


@pytest.mark.asyncio
async def test_gemini_cannot_downgrade_red_flags(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    def handler(r):
        body=json.loads(r.content)
        assert 'insurance' not in body['contents'][0]['parts'][0]['text']
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps({'urgency':'contact_vet','summary':'Call your vet','questions':[],'services_to_ask_about':[]})}]}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await assess(CareRequest(**payload(share_with_ai=True,red_flags=['collapse'])),client)
        assert result.urgency=='emergency'


@pytest.mark.asyncio
async def test_google_places_normalization(monkeypatch):
    monkeypatch.setenv('GOOGLE_PLACES_API_KEY','test-only')
    def handler(r):
        assert json.loads(r.content)['includedTypes']==['veterinary_care']
        return httpx.Response(200,json={'places':[{'id':'123','displayName':{'text':'Animal Clinic'},'location':{'latitude':47.37,'longitude':8.54},'internationalPhoneNumber':'+41441234567'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await google_clinics(CareRequest(**payload(location={'lat':47.37,'lng':8.54})),client)
        assert result[0].call_url=='tel:+41441234567'
        assert result[0].open_now is None
        assert result[0].distance_km==0


@pytest.mark.asyncio
async def test_mapify_actual_contract(monkeypatch):
    monkeypatch.setenv('MAPIFY_BASE_URL','https://mapify.example')
    def handler(r):
        if r.method=='POST':
            assert r.url.path=='/api/requests/'
            assert r.url.params['stream']=='false'
            body=json.loads(r.content)
            assert body['query'].startswith('Veterinary')
            assert 'PRIVATE_CONCERN' not in str(body)
            return httpx.Response(200,json={'results':[{'place_id':'vet-1','name':'Tierarzt Test'},{'place_id':'salon','name':'Salon'}]})
        if r.url.path.endswith('salon'):
            return httpx.Response(200,json={'detail':{'place':{'name':'Salon'}}})
        return httpx.Response(200,json={'detail':{'place':{'name':'Tierarzt Test','location':{'lat':47.37,'lng':8.54},'phone':'+41441234567','status':'open_now'}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result=await mapify_clinics(CareRequest(query='PRIVATE_CONCERN',location=Location(lat=47.37,lng=8.54)),client)
        assert len(result)==1
        assert result[0].open_now is None
        assert result[0].call_url=='tel:+41441234567'


@pytest.mark.asyncio
async def test_parallel_partial_provider_failure(monkeypatch):
    async def fail(req,client):raise ProviderError('unavailable')
    async def succeed(req,client):return []
    monkeypatch.setattr(service,'assess',fail);monkeypatch.setattr(service,'discover',succeed)
    events=[e async for e in service.care_events(CareRequest(**payload()))]
    assert events[-1]['providers']=={'assessment':'unavailable','clinics':'complete'}
    assert events[-1]['status']=='partial'


@pytest.mark.asyncio
async def test_deadline_cancels_slow_providers(monkeypatch):
    cancelled=[]
    async def slow(req,client):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
    monkeypatch.setattr(service,'CARE_DEADLINE_SECONDS',.5)  # clock starts before httpx client setup (~50 ms)
    monkeypatch.setattr(service,'assess',slow);monkeypatch.setattr(service,'discover',slow)
    events=[e async for e in service.care_events(CareRequest(**payload()))]
    assert len(cancelled)==2
    assert events[-1]['providers']=={'assessment':'timeout','clinics':'timeout'}
    assert 'deadline_reached' in events[-1]['warnings']


def test_legacy_cat_scope_is_enforced(monkeypatch):
    monkeypatch.setenv('LEGACY_AGENT_BASE_URL','http://localhost:8000')
    monkeypatch.setenv('LEGACY_AGENT_USER_ID','1')
    monkeypatch.setenv('LEGACY_AGENT_CAT_IDS','2')
    with TestClient(app) as c:
        assert c.post('/api/v1/agent/requests',json={'cat_id':3,'message':'hello'}).status_code==403


def test_result_schema_is_documented():
    schema=app.openapi()
    assert 'CareResult' in schema['components']['schemas']
    assert 'Clinic' in schema['components']['schemas']


@pytest.mark.asyncio
async def test_legacy_bridge_preserves_named_sse_and_server_user(monkeypatch):
    from pawse import legacy
    monkeypatch.setenv('LEGACY_AGENT_BASE_URL','http://legacy.test')
    monkeypatch.setenv('LEGACY_AGENT_USER_ID','7')
    monkeypatch.setenv('LEGACY_AGENT_CAT_IDS','2')
    from pawse.models import LegacyRequest
    def handler(r):
        if r.url.path=='/chat':
            assert json.loads(r.content)['user_id']==7
            assert json.loads(r.content)['cat_id']==2
            return httpx.Response(200,json={'stream_id':'abc'})
        assert r.url.path=='/chat/stream/abc'
        return httpx.Response(200,text='event: result\ndata: {"response":"synthetic cat result"}\n\n')
    original=httpx.AsyncClient
    monkeypatch.setattr(legacy.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    events=[e async for e in legacy.legacy_events(LegacyRequest(cat_id=2,message='activity'))]
    assert events==[{'type':'legacy','event':'result','data':{'response':'synthetic cat result'}}]


def test_capabilities_expose_model_ids_and_clinic_providers_without_keys(monkeypatch, tmp_path):
    monkeypatch.setenv('PAWSE_CLINIC_SNAPSHOT', str(tmp_path / 'missing.json'))
    for k in ('GEMINI_MODEL','GEMINI_CARE_MODEL','GEMINI_VOICE_MODEL','GEMINI_LIVE_MODEL','GOOGLE_PLACES_API_KEY','MAPIFY_BASE_URL'):
        monkeypatch.delenv(k,raising=False)
    monkeypatch.setenv('GEMINI_API_KEY','secret-key-value')
    monkeypatch.setenv('GEMINI_CARE_MODEL','care-x')
    monkeypatch.setenv('GOOGLE_PLACES_API_KEY','places-secret')
    with TestClient(app) as c:
        r=c.get('/api/v1/capabilities')
        d=r.json()
    assert d['models']=={'care':'care-x','voice':'gemini-3-flash-preview','live':'gemini-3.8-live'}
    assert d['clinic_providers']==['google_places', 'gemini_maps']
    assert {f['id']:f['status'] for f in d['new_features']}['nearby_clinics']=='configured'
    assert 'secret-key-value' not in r.text and 'places-secret' not in r.text
