"""Recorded audio in the React app: the REST voice fallback and the own-voice enrollment recorder.

The fake microphone loops 2.5 s of speech-like sound and 2.5 s of silence, so voice-activity detection
sees a turn start and end. Uploaded WAVs are also checked with the server's own validator.
"""
import re

from playwright.sync_api import Page, expect

from audio_fixtures import read_wav
from e2e_helpers import DENY_MIC, MIC_RELEASED, TRACK_SPY, wait_for
from pawse.voice import inspect_wav

REST = "/app/?live=1&voice=rest"


def start_rest_call(page: Page):
    page.route("**/api/v1/agents/runs", lambda r: r.fulfill(status=503, json={"detail": "Gemini is not configured."}))
    page.goto(REST)
    page.locator(".start-btn").click()
    page.get_by_role("button", name="Agree and start").click()
    page.locator("nav.call-controls button").first.click()  # microphone on


def test_rest_fallback_sends_one_audible_mono_wav_per_spoken_turn(page: Page, transcriptions):
    start_rest_call(page)
    wait_for(page, lambda: transcriptions, seconds=25, what="a transcription request after a spoken turn")
    body = transcriptions[0]
    assert body["language"] == "en" and body["share_with_gemini"] is True
    channels, width, rate, seconds, rms = read_wav(body["audio"]["data"])
    assert (channels, width, rate) == (1, 2, 16000)
    assert 2 <= seconds <= 8, f"turn of {seconds:.1f}s: expected the 2.5 s utterance plus the silence that ended it"
    assert rms > 0.02, "the uploaded turn is silent: the capture path lost the microphone signal"
    inspect_wav(body["audio"]["data"])
    expect(page.locator(".cap-user")).to_contain_text("Mimi is limping")


def test_rest_fallback_sends_the_chosen_language(page: Page, transcriptions):
    page.goto(REST)
    page.get_by_role("button", name="中文").click()  # remembered for the next load
    start_rest_call(page)
    wait_for(page, lambda: transcriptions, seconds=25, what="a transcription request")
    assert transcriptions[0]["language"] == "zh"


def test_rest_fallback_with_denied_microphone_is_explained(page: Page, transcriptions):
    page.add_init_script(DENY_MIC)
    start_rest_call(page)
    expect(page.locator(".cap-error")).to_contain_text("Couldn't open the microphone")
    expect(page.get_by_role("textbox")).to_be_enabled()
    assert transcriptions == []


def open_own_voice(page: Page):
    page.goto("/app/")
    page.get_by_role("button", name="Record my voice · emergency rehearsal").click()
    expect(page.get_by_role("heading", name="My voice · emergency rehearsal")).to_be_visible()


def test_own_voice_recording_plays_back_locally_and_sends_nothing(page: Page):
    seconds = 11  # enrollment needs 10-30 s
    page.add_init_script(TRACK_SPY)
    uploads = []
    page.on("request", lambda r: r.method == "POST" and "/api/v1/voice/" in r.url and uploads.append(r.url))
    open_own_voice(page)
    page.get_by_role("button", name="Record my voice", exact=True).click()
    page.wait_for_timeout(seconds * 1000)
    page.get_by_role("button", name="Stop recording").click()
    player = page.locator("audio[controls]").first
    expect(player).to_have_attribute("src", re.compile(r"^blob:"))
    duration = player.evaluate("""a => new Promise(ok => a.readyState >= 1 && isFinite(a.duration) ? ok(a.duration)
                                   : a.addEventListener("loadedmetadata", () => ok(a.duration), { once: true }))""")
    assert seconds - 1.5 <= duration <= seconds + 1.5
    expect(page.get_by_role("alert")).to_have_count(0)
    page.wait_for_function(MIC_RELEASED)
    expect(page.get_by_role("button", name="Clone and preview in German")).to_be_disabled()  # no consent, no Gradium key
    assert uploads == [], "recording alone must not upload audio"


def test_own_voice_rejects_a_recording_under_ten_seconds(page: Page):
    open_own_voice(page)
    page.get_by_role("button", name="Record my voice", exact=True).click()
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="Stop recording").click()
    expect(page.get_by_role("alert")).to_contain_text("10")
    expect(page.locator("audio[controls]")).to_have_count(0)


def test_own_voice_with_denied_microphone_is_explained(page: Page):
    page.add_init_script(DENY_MIC)
    open_own_voice(page)
    page.get_by_role("button", name="Record my voice", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Microphone unavailable")
    expect(page.get_by_role("button", name="Record my voice", exact=True)).to_be_enabled()
