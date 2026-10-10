import asyncio
import base64
import io
import json
import wave
import httpx
import pytest
from fastapi.testclient import TestClient
from pawse.app import app
from pawse import voice
from pawse.demo import costs


def wav(seconds=12, rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate)
        f.writeframes(b'\0\0' * int(seconds * rate))
    return stream.getvalue()


def audio(seconds=12):
    return {'data': base64.b64encode(wav(seconds)).decode()}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for key in ['GEMINI_API_KEY', 'GRADIUM_API_KEY', 'GRADIUM_VOICE_ID_DE', 'GRADIUM_STANDARD_VOICE_ID_DE']:
        monkeypatch.delenv(key, raising=False)
    voice.voices.clear(); voice.voice_active.clear(); voice.disclosed_calls.clear()


def upstream(monkeypatch, handler):
    factory = httpx.AsyncClient
    monkeypatch.setattr(voice.httpx, 'AsyncClient', lambda *a, **kw: factory(transport=httpx.MockTransport(handler)))


def test_voice_validation_requires_ownership_consent_supported_sample_and_duration():
    with TestClient(app) as c:
        base = {'audio': audio(), 'sample_language': 'en', 'own_voice_consent': True, 'share_with_gradium': True}
        for change in [{'own_voice_consent': False}, {'share_with_gradium': False}, {'sample_language': 'zh'}, {'audio': audio(2)}]:
            assert c.post('/api/v1/voice/clone', json=base | change).status_code == 422
        bad = c.post('/api/v1/voice/clone', json=base | {'audio': {'data': 'PRIVATE_RECORDING' * 10}})
        assert bad.status_code == 422 and 'PRIVATE_RECORDING' not in bad.text
        assert c.post('/api/v1/voice/clone', json=base).status_code == 503
    assert not voice.voice_active


def test_truncated_wav_rejected():
    raw = wav()[:-200]
    with pytest.raises(ValueError):
        voice.Audio(data=base64.b64encode(raw).decode())


def test_clone_localize_preview_approve_speak_delete_and_session_isolation(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'private-test-key')
    seen = []
    def handler(req):
        assert req.headers['x-api-key'] == 'private-test-key'
        path = req.url.path; seen.append((req.method, path))
        if req.method == 'DELETE':
            return httpx.Response(204)
        if path.endswith('/voices/'):
            assert b'name="language"\r\n\r\nen' in req.content
            assert b'RIFF' in req.content
            return httpx.Response(201, json={'uid': 'source123'})
        if path.endswith('/localize'):
            assert json.loads(req.content) == {'src_voice': 'source123', 'target_language': 'de', 'n_samples': 1}
            return httpx.Response(201, json={'embeddings': [{'embedding_id': 'vox_emb_test', 'ready': False}]})
        if path.endswith('/embeddings'):
            assert req.url.params['embedding_id'] == 'vox_emb_test'
            return httpx.Response(200, json={'embeddings': [{'embedding_id': 'vox_emb_test', 'ready': True}]})
        if path.endswith('/from-embedding'):
            assert json.loads(req.content)['voxium_embedding_id'] == 'vox_emb_test'
            return httpx.Response(201, json={'uid': 'german123'})
        if path.endswith('/tts'):
            data = json.loads(req.content)
            assert data['only_audio'] is True and data['output_format'] == 'wav'
            assert data['text'].startswith(voice.DISCLOSURE)
            assert data['voice_id'] in ['vox_emb_test', 'german123']
            if data['voice_id'].startswith('vox_emb_'): assert len(data['text']) <= 300
            return httpx.Response(200, content=wav(1), headers={'content-type': 'audio/wav'})
        raise AssertionError(path)
    upstream(monkeypatch, handler)
    consent = {'share_with_gradium': True}
    with TestClient(app) as a, TestClient(app) as b:
        a.get('/api/v1/voice/status'); b.get('/api/v1/voice/status')
        r = a.post('/api/v1/voice/clone', json=consent | {'audio': audio(), 'sample_language': 'en', 'own_voice_consent': True})
        assert r.status_code == 201 and r.json()['source_id'] == 'source123'
        assert b.get('/api/v1/voice/status').json()['source_id'] is None
        assert b.post('/api/v1/voice/localizations', json=consent).status_code == 409
        assert a.post('/api/v1/voice/speech', json=consent | {'text': 'Hallo'}).status_code == 409
        assert a.post('/api/v1/voice/localizations', json=consent).status_code == 202
        assert a.post('/api/v1/voice/preview', json=consent).status_code == 409
        assert a.get('/api/v1/voice/localizations/current').json()['candidate_ready'] is True
        save = consent | {'listened_to_preview': True}
        assert a.post('/api/v1/voice/localizations/current/save', json=save).status_code == 409
        assert a.post('/api/v1/voice/preview', json=consent).content[:4] == b'RIFF'
        assert a.post('/api/v1/voice/localizations/current/save', json=save).status_code == 201
        r = a.post('/api/v1/voice/speech', json=consent | {'text': 'Hallo'})
        assert r.status_code == 200 and r.headers['content-type'] == 'audio/wav'
        assert 'private-test-key' not in r.text
        assert a.delete('/api/v1/voice/profile').status_code == 204
        assert not a.get('/api/v1/voice/status').json()['my_voice_ready']
    assert ('DELETE', '/api/voices/source123') in seen
    assert ('DELETE', '/api/voices/german123') in seen
    assert not voice.voices and not voice.voice_active


def test_delete_retries_partial_failure_without_losing_ids(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    failed = False
    def handler(req):
        nonlocal failed
        if req.url.path.endswith('/german123') and not failed:
            failed = True
            return httpx.Response(503, text='upstream-private-error')
        return httpx.Response(404)  # Already removed is a successful deletion.
    upstream(monkeypatch, handler)
    with TestClient(app) as c:
        c.get('/api/v1/voice/status')
        owner = c.cookies.get('pawse_session')
        voice.voices[owner] = {'source_id': 'source123', 'german_id': 'german123', 'candidate_id': 'vox_emb_test'}
        r = c.delete('/api/v1/voice/profile')
        assert r.status_code == 502 and 'upstream-private-error' not in r.text
        assert voice.voices[owner]['german_id'] == 'german123'
        assert 'candidate_id' not in voice.voices[owner]
        assert c.delete('/api/v1/voice/profile').status_code == 204


def test_transcription_and_translation_keep_multilingual_contract(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'gemini-test')
    def handler(req):
        body = json.loads(req.content)
        parts = body['contents'][0]['parts']
        if 'inlineData' in parts[0]:
            assert parts[0]['inlineData']['mimeType'] == 'audio/wav'
            data = {'text': '我的猫在跳下来后跛行。'}
        else:
            assert parts[0]['text'] == '我的猫在跳下来后跛行。'
            data = {'lines': [{'german': 'Meine Katze hinkt nach einem Sprung.', 'subtitle': '我的猫在跳下来后跛行。'}]}
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(data)}]}}]})
    upstream(monkeypatch, handler)
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/transcriptions', json={'audio': audio(1), 'language': 'zh', 'share_with_gemini': True})
        assert r.status_code == 200 and r.json()['text'].startswith('我的猫')
        r = c.post('/api/v1/voice/scripts', json={'message': r.json()['text'], 'input_language': 'zh', 'subtitle_language': 'zh', 'share_with_gemini': True})
        assert r.status_code == 200
        data = r.json()
        assert data['status'] == 'draft_not_sent' and data['target_language'] == 'de'
        assert data['lines'][0]['german'] == voice.DISCLOSURE
        assert 'AI' in data['lines'][0]['subtitle']
        assert c.post('/api/v1/voice/scripts', json={'message': 'Hi', 'share_with_gemini': False}).status_code == 422


def test_script_rejects_oversized_model_response(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    upstream(monkeypatch, lambda req: httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps({'lines': [{'german': 'Hallo', 'subtitle': 'Hello'}] * 6})}]}}]}))
    with TestClient(app) as c:
        assert c.post('/api/v1/voice/scripts', json={'message': 'Hi', 'share_with_gemini': True}).status_code == 502


def test_standard_voice_is_explicit_and_disclosed(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    def handler(req):
        data = json.loads(req.content)
        assert data['voice_id'] == 'p6Uutkyi3j2iNAUu'
        assert data['text'].startswith(voice.DISCLOSURE)
        return httpx.Response(200, content=wav(1))
    upstream(monkeypatch, handler)
    with TestClient(app) as c:
        assert c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'voice': 'standard', 'share_with_gradium': True}).status_code == 200
        assert c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'share_with_gradium': True}).status_code == 409


def test_provider_errors_do_not_leak_credentials_or_audio(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'private-test-key')
    upstream(monkeypatch, lambda req: httpx.Response(401, text='private-test-key raw recording'))
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'voice': 'standard', 'share_with_gradium': True})
        assert r.status_code == 502 and 'private-test-key' not in r.text
    assert not voice.voice_active


def test_voice_concurrency_bound_and_cleanup():
    async def run():
        async with voice.operation('owner'):
            with pytest.raises(Exception) as exc:
                async with voice.operation('owner'): pass
            assert exc.value.status_code == 429
        assert not voice.voice_active
    asyncio.run(run())


def test_mimi_costs_and_status_are_explicitly_synthetic():
    assert costs()['reimbursed'] == 240
    assert costs()['clinic'] == 385 and costs()['home'] == 510
    with TestClient(app) as c:
        d = c.get('/api/v1/demo/mimi').json()
        assert d['synthetic'] and len(d['steps']) == 6
        assert d['calendar']['source'] == 'synthetic'
        assert 'No appointments' in d['notice']


def test_malformed_gemini_parts_return_safe_error(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test')
    upstream(monkeypatch, lambda req: httpx.Response(200, json={'candidates': [{'content': {'parts': [None]}}]}))
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/scripts', json={'message': 'Hi', 'share_with_gemini': True})
        assert r.status_code == 502


@pytest.mark.parametrize('body', [b'RIFFxxxxWAVE', wav(1)[:-20], b'{"error":"private"}'])
def test_invalid_upstream_audio_never_returns_playable_success(monkeypatch, body):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    upstream(monkeypatch, lambda req: httpx.Response(200, content=body))
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'voice': 'standard', 'share_with_gradium': True})
        assert r.status_code == 502 and 'private' not in r.text


def streamed_wav(seconds=1):
    """Gradium streams TTS, so its WAV header carries 0xFFFFFFFF placeholder sizes instead of real ones."""
    raw = bytearray(wav(seconds))
    raw[4:8] = raw[40:44] = b'\xff\xff\xff\xff'
    return bytes(raw)


def test_streamed_upstream_wav_is_returned_with_real_sizes(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    upstream(monkeypatch, lambda req: httpx.Response(200, content=streamed_wav(1)))
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'voice': 'standard', 'share_with_gradium': True})
    assert r.status_code == 200 and r.headers['content-type'] == 'audio/wav'
    with wave.open(io.BytesIO(r.content)) as f:
        assert f.getnframes() == 16000 and len(f.readframes(f.getnframes())) == 32000


@pytest.mark.parametrize('body', [streamed_wav(0), streamed_wav(1)[:45]])
def test_streamed_upstream_wav_without_whole_frames_is_rejected(monkeypatch, body):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    upstream(monkeypatch, lambda req: httpx.Response(200, content=body))
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'voice': 'standard', 'share_with_gradium': True})
    assert r.status_code == 502


def test_upstream_download_stops_at_bound(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    chunks_read = []
    class Chunks(httpx.AsyncByteStream):
        async def __aiter__(self):
            for i in range(100):
                chunks_read.append(i)
                yield b'x' * 65536
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=Chunks()))) as client:
            with pytest.raises(Exception) as exc:
                await voice.gradium(client, 'GET', '/test', max_bytes=100_000)
            assert exc.value.status_code == 502
    asyncio.run(check())
    assert len(chunks_read) == 2


def test_agent_run_result_uses_same_private_cache():
    with TestClient(app) as a, TestClient(app) as b:
        run = a.post('/api/v1/agents/runs', json={'care': {'query': 'Mimi has a checkup question'}})
        assert run.status_code == 201
        id_ = run.json()['care']['request_id']
        assert a.get('/api/v1/care/requests/' + id_).status_code == 200
        assert b.get('/api/v1/care/requests/' + id_).status_code == 404
        assert a.delete('/api/v1/care/requests/' + id_).status_code == 204


def test_chunked_body_limit_is_enforced_without_content_length():
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/scripts', content=iter([b' ' * 3_000_000, b' ' * 1_500_001]), headers={'Content-Type': 'application/json'})
        assert r.status_code == 413


def test_call_lines_disclose_once_per_server_issued_call_id(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    spoken = []
    def handler(req):
        spoken.append(json.loads(req.content)['text'])
        return httpx.Response(200, content=wav(1))
    upstream(monkeypatch, handler)
    line = {'voice': 'standard', 'share_with_gradium': True}
    with TestClient(app) as c, TestClient(app) as other:
        first = c.post('/api/v1/voice/speech', json=line | {'text': 'Meine Katze hinkt.'})
        assert first.status_code == 200
        call_id = first.headers['x-pawse-call-id']
        assert spoken[-1] == voice.DISCLOSURE + ' Meine Katze hinkt.'
        # Later lines of the same call are spoken as is, with the same id.
        second = c.post('/api/v1/voice/speech', json=line | {'text': 'Ist das gedeckt?', 'call_id': call_id})
        assert second.status_code == 200 and second.headers['x-pawse-call-id'] == call_id
        assert spoken[-1] == 'Ist das gedeckt?'
        # An unknown id, or one issued to another session, still gets the disclosure and a fresh id.
        for client in (c, other):
            r = client.post('/api/v1/voice/speech', json=line | {'text': 'Hallo', 'call_id': 'x' * 24})
            assert r.status_code == 200 and spoken[-1].startswith(voice.DISCLOSURE)
            assert r.headers['x-pawse-call-id'] != 'x' * 24
        r = other.post('/api/v1/voice/speech', json=line | {'text': 'Hallo', 'call_id': call_id})
        assert spoken[-1].startswith(voice.DISCLOSURE) and r.headers['x-pawse-call-id'] != call_id
        # No id at all: disclosed, and a text that already starts with it is not doubled.
        c.post('/api/v1/voice/speech', json=line | {'text': voice.DISCLOSURE + ' Hallo'})
        assert spoken[-1] == voice.DISCLOSURE + ' Hallo'
        # Consent is still required on every line.
        assert c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'voice': 'standard', 'call_id': call_id}).status_code == 422
        assert c.post('/api/v1/voice/speech', json=line | {'text': 'Hallo', 'call_id': call_id, 'share_with_gradium': False}).status_code == 422


def test_failed_first_line_does_not_count_as_disclosed(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    upstream(monkeypatch, lambda req: httpx.Response(500, text='down'))
    with TestClient(app) as c:
        r = c.post('/api/v1/voice/speech', json={'text': 'Hallo', 'voice': 'standard', 'share_with_gradium': True})
        assert r.status_code == 502 and 'x-pawse-call-id' not in r.headers
    assert not any(voice.disclosed_calls.values())


def test_call_ids_expire_and_are_bounded(monkeypatch):
    monkeypatch.setenv('GRADIUM_API_KEY', 'test')
    spoken = []
    def handler(req):
        spoken.append(json.loads(req.content)['text'])
        return httpx.Response(200, content=wav(1))
    upstream(monkeypatch, handler)
    line = {'voice': 'standard', 'share_with_gradium': True}
    with TestClient(app) as c:
        call_id = c.post('/api/v1/voice/speech', json=line | {'text': 'Hallo'}).headers['x-pawse-call-id']
        for calls in voice.disclosed_calls.values():
            calls[call_id] = 0  # expired
        c.post('/api/v1/voice/speech', json=line | {'text': 'Weiter', 'call_id': call_id})
        assert spoken[-1].startswith(voice.DISCLOSURE)
        for _ in range(voice.MAX_CALLS_PER_OWNER + 5):
            c.post('/api/v1/voice/speech', json=line | {'text': 'Hallo'})
        assert all(len(calls) <= voice.MAX_CALLS_PER_OWNER for calls in voice.disclosed_calls.values())
