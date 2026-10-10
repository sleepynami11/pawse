"""One real recording per language spoken into the React app's live call, through real Gemini Live.

This is the whole owner path (recording → AudioWorklet 16 kHz PCM → Gemini Live input transcription → caption)
with human speech. Opt-in like test_real_recordings_api.py (PAWSE_LIVE_SPEECH=1); also needs PAWSE_E2E=1.
"""
import os
import time
import wave

import pytest

from e2e_helpers import serve
from speech_metrics import LANGUAGES, TARGETS, error_rate, in_native_script, live_speech_enabled, load_manifest

pytestmark = pytest.mark.skipif(bool(live_speech_enabled()), reason=live_speech_enabled() or "")
FIRST = {e["language"]: e for e in reversed(load_manifest())}  # first recording of each language
# Chromium's fake capture file starts at browser launch, so a short recording would be over before the
# owner turns the mic on. Instead the recording starts the moment the app opens the microphone, over a
# faint noise floor like a real mic (pure digital silence never ends a Live turn); the app's own
# AudioWorklet/PCM path is unchanged.
RECORDING_AS_MIC = """
navigator.mediaDevices.getUserMedia = async () => {
  const ctx = new AudioContext();
  const buffer = await ctx.decodeAudioData(await (await fetch("/__e2e/recording.wav")).arrayBuffer());
  const source = ctx.createBufferSource(), sink = ctx.createMediaStreamDestination();
  source.buffer = buffer; source.connect(sink); source.start(ctx.currentTime + 0.5);
  const noise = ctx.createBuffer(1, ctx.sampleRate * 60, ctx.sampleRate), samples = noise.getChannelData(0);
  for (let i = 0; i < samples.length; i++) samples[i] = (Math.random() * 2 - 1) * 0.003;
  const floor = ctx.createBufferSource(); floor.buffer = noise; floor.connect(sink); floor.start();
  return sink.stream;
};
"""
CHIP = {"en": "EN", "zh": "中文", "de": "DE", "hi": "हिन्दी"}


@pytest.fixture(scope="module")
def live_app():
    proc, url = serve(dict(os.environ))  # keeps GEMINI_API_KEY
    yield url
    proc.terminate()
    proc.wait(10)


def settled_caption(page, seconds):
    """The owner caption once it has stopped changing for 3 s (Gemini streams it in pieces)."""
    end, last, since = time.monotonic() + seconds, "", time.monotonic()
    while time.monotonic() < end:
        text = page.locator(".cap-user").first.text_content() if page.locator(".cap-user").count() else ""
        if text != last:
            last, since = text, time.monotonic()
        elif text and time.monotonic() - since > 3:
            return text
        page.wait_for_timeout(250)
    return last


@pytest.mark.parametrize("language", LANGUAGES)
def test_spoken_message_survives_the_live_call(browser_type, live_app, language):
    entry = FIRST.get(language)
    assert entry, f"no {language} recording in the manifest"
    with wave.open(str(entry["path"])) as f:
        seconds = f.getnframes() / f.getframerate()
    browser = browser_type.launch(args=["--autoplay-policy=no-user-gesture-required"])
    try:
        page = browser.new_page(base_url=live_app, viewport={"width": 1440, "height": 900})
        page.route("**/__e2e/recording.wav", lambda r: r.fulfill(body=entry["path"].read_bytes(), content_type="audio/wav"))
        page.add_init_script(RECORDING_AS_MIC)
        page.goto("/app/?live=1")
        page.get_by_role("button", name=CHIP[language], exact=True).click()
        page.locator(".start-btn").click()
        page.get_by_role("button", name="Agree and start").click()
        page.locator(".cap-ai").wait_for(timeout=30_000)  # Pawse greeted: the session is live
        page.locator("nav.call-controls button").first.click()  # mic on: the recording starts playing now
        text = settled_caption(page, seconds + 30)
    finally:
        browser.close()
    rate = error_rate(language, entry["reference"], text)
    assert in_native_script(language, text), f"not in {language} script: {text!r}"
    assert rate <= TARGETS[language], f"{entry['file']}: error rate {rate:.2f} > {TARGETS[language]}: {text!r}"
