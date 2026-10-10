"""Opt-in smoke checks of this project's Gemini access, using only synthetic input.

Never prints credentials or upstream response bodies. Not a quality/latency benchmark.
"""
import argparse
import asyncio
import base64
import io
import json
import os
import wave
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


async def probe(output):
    load_dotenv(ROOT / '.env')
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        raise SystemExit('GEMINI_API_KEY is not configured')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'scope': 'This development project only; synthetic inputs. Availability can change.', 'checks': [], 'gradium': 'not_configured' if not os.getenv('GRADIUM_API_KEY') else 'configured_not_probed'}
    async with httpx.AsyncClient(headers={'x-goog-api-key': key}, timeout=45) as client:
        r = await client.get('https://generativelanguage.googleapis.com/v1beta/models', params={'pageSize': 1000})
        if r.status_code != 200:
            raise SystemExit('Model listing failed (HTTP ' + str(r.status_code) + ')')
        models = r.json().get('models', [])
        report['listed_models'] = [{'name': m['name'].removeprefix('models/'), 'methods': m.get('supportedGenerationMethods', [])} for m in models]
        preferred = list(dict.fromkeys([os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview'), 'gemini-2.5-flash', 'gemini-3.1-pro-preview']))
        async def check(model, kind, body, method='generateContent'):
            try:
                response = await client.post('https://generativelanguage.googleapis.com/v1beta/models/' + quote(model, safe='') + ':' + method, json=body)
                valid = False
                if response.status_code == 200:
                    data = response.json()
                    if method == 'embedContent':
                        valid = bool(data.get('embedding', {}).get('values'))
                    else:
                        parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                        valid = any(p.get('text') and not p.get('thought') for p in parts)
                report['checks'].append({'model': model, 'modality': kind, 'method': method, 'http_status': response.status_code, 'usable_response': valid})
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
                report['checks'].append({'model': model, 'modality': kind, 'method': method, 'usable_response': False, 'error': 'transport_or_schema_failure'})
        for model in preferred:
            await check(model, 'text', {'contents': [{'parts': [{'text': 'Reply only: OK'}]}], 'generationConfig': {'maxOutputTokens': 128}})
        chosen = os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview')
        wav = io.BytesIO()
        with wave.open(wav, 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000); f.writeframes(b'\0' * 32000)
        await check(chosen, 'audio_input_silent_wav', {'contents': [{'parts': [{'text': 'Describe whether this clip contains intelligible speech in one short sentence.'}, {'inlineData': {'mimeType': 'audio/wav', 'data': base64.b64encode(wav.getvalue()).decode()}}]}], 'generationConfig': {'maxOutputTokens': 256}})
        # Synthetic 1x1 PNG. Tests accepted image input, not medical image quality.
        png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII='
        await check(chosen, 'image_input_synthetic_png', {'contents': [{'parts': [{'text': 'This is a tiny synthetic image. Reply only: image received.'}, {'inlineData': {'mimeType': 'image/png', 'data': png}}]}], 'generationConfig': {'maxOutputTokens': 256}})
        embedding = next((m['name'].removeprefix('models/') for m in models if 'embedContent' in m.get('supportedGenerationMethods', []) and 'gemini-embedding' in m['name']), None)
        if embedding:
            await check(embedding, 'embedding', {'content': {'parts': [{'text': 'Fictional cat insurance deductible.'}]}}, 'embedContent')
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'listed_models'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / 'docs/model-access-check.json'))
    asyncio.run(probe(parser.parse_args().output))
