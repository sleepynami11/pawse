"""Real human recordings through POST /voice/transcriptions with the real Gemini key.

Opt-in (spends quota): PAWSE_LIVE_SPEECH=1, GEMINI_API_KEY, PAWSE_RECORDINGS_DIR. Recordings never go
in git. Results are written to test-results/speech-api.json for docs/VALIDATION.md.
"""
import base64
import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from audio_fixtures import silence
from pawse.app import app
from pawse.voice import inspect_wav
from speech_metrics import LANGUAGES, MIN_PER_LANGUAGE, TARGETS, error_rate, in_native_script, live_speech_enabled, load_manifest

pytestmark = pytest.mark.skipif(bool(live_speech_enabled()), reason=live_speech_enabled() or "")
RESULTS = Path(__file__).resolve().parents[2] / "test-results" / "speech-api.json"
results = []


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def transcribe(client, data: bytes, language: str) -> str:
    r = client.post("/api/v1/voice/transcriptions", json={
        "audio": {"data": base64.b64encode(data).decode()}, "language": language, "share_with_gemini": True})
    assert r.status_code == 200, r.text
    return r.json()["text"]


def test_recordings_cover_all_four_languages_and_are_valid_wavs():
    entries = load_manifest()
    counts = Counter(e["language"] for e in entries)
    assert all(counts[lang] >= MIN_PER_LANGUAGE for lang in LANGUAGES), f"recordings per language: {dict(counts)}"
    for e in entries:
        inspect_wav(base64.b64encode(e["path"].read_bytes()).decode())


@pytest.mark.parametrize("entry", load_manifest(), ids=lambda e: e["file"])
def test_real_recording_is_transcribed_in_its_own_language_within_target(client, entry):
    text = transcribe(client, entry["path"].read_bytes(), entry["language"])
    rate = error_rate(entry["language"], entry["reference"], text)
    results.append({"file": entry["file"], "language": entry["language"], "speaker": entry.get("speaker"),
                    "error_rate": round(rate, 3), "transcript": text})
    assert in_native_script(entry["language"], text), f"not in {entry['language']} script: {text!r}"
    assert rate <= TARGETS[entry["language"]], f"error rate {rate:.2f} > {TARGETS[entry['language']]}: {text!r}"


@pytest.mark.xfail(strict=True, reason="2026-10-10: gemini-3-flash-preview invents a greeting for 2 s of silence in "
                   "all four languages (#25). Remove this marker once the transcription route stops it.")
@pytest.mark.parametrize("language", LANGUAGES)
def test_silence_is_not_turned_into_invented_speech(client, language):
    assert transcribe(client, silence(2), language).strip() == ""
