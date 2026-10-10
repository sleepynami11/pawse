"""The React app's Gemini Live conversation (/app/?live=1), with a real browser mic and audio stack.

Chromium's fake microphone plays a speech-like WAV; the Live WebSocket is answered by FakeLive in the
real wire format; /live/tokens and /live/tool-calls are mocked. Everything else is the shipped build.
"""
import base64
import re
import time

import httpx
from playwright.sync_api import Page, expect

from audio_fixtures import pcm16, pcm16_rms
from e2e_helpers import DENY_MIC, MIC_RELEASED, TRACK_SPY, FakeLive, wait_for

LIVE = "/app/?live=1"
CLINIC_UI = {"action": "confirm_call", "clinic_name": "Tierarztpraxis Seefeld", "phone": "+41 44 000 00 00",
             "call_url": "tel:+41440000000"}


def open_call(page: Page, live: FakeLive, language_chip="EN"):
    page.goto(LIVE)
    page.get_by_role("button", name=language_chip, exact=True).click()
    page.locator(".start-btn").click()
    page.get_by_role("button", name="Agree and start").click()
    wait_for(page, lambda: live.frames("setup"), what="Live setup message")
    wait_for(page, lambda: any("text" in f for f in live.frames("realtimeInput")), what="greeting request")


def mic_button(page: Page):
    return page.locator("nav.call-controls button").first


def turn_mic_on(page: Page, live: FakeLive):
    mic_button(page).click()
    expect(mic_button(page)).to_have_attribute("aria-pressed", "false")  # pressed = muted
    wait_for(page, lambda: len(live.audio_frames()) >= 5, what="mic audio frames")


def test_nothing_reaches_gemini_before_consent(page: Page):
    live = FakeLive(page)
    page.goto(LIVE)
    page.locator(".start-btn").click()
    expect(page.get_by_role("button", name="Agree and start")).to_be_visible()
    page.wait_for_timeout(500)
    assert live.token_requests == [] and live.socket is None


def test_session_uses_the_ephemeral_token_and_chosen_language(page: Page):
    live = FakeLive(page)
    open_call(page, live, language_chip="DE")
    assert live.token_requests == [{"language": "de", "share_with_gemini": True}]
    assert "Constrained?access_token=auth_tokens/e2e-test" in live.url and "key=" not in live.url


def test_mic_stays_off_until_the_owner_turns_it_on(page: Page):
    page.add_init_script(TRACK_SPY)
    live = FakeLive(page)
    open_call(page, live)
    page.wait_for_timeout(1000)
    assert live.audio_frames() == []
    assert page.evaluate("window.__micTracks.length") == 0


def test_microphone_streams_audible_16_khz_pcm_in_real_time(page: Page):
    live = FakeLive(page)
    open_call(page, live)
    began = time.monotonic()
    turn_mic_on(page, live)
    page.wait_for_timeout(3000)
    elapsed = time.monotonic() - began
    audio = live.audio_frames()
    assert {a["mimeType"] for a in audio} == {"audio/pcm;rate=16000"}
    raw = b"".join(base64.b64decode(a["data"]) for a in audio)
    streamed = len(raw) / 2 / 16000
    assert 0.5 * elapsed <= streamed <= 1.2 * elapsed, f"{streamed:.1f}s of audio in {elapsed:.1f}s: wrong sample rate?"
    assert pcm16_rms(base64.b64encode(raw).decode()) > 0.02, "mic frames are silent"


def test_muting_ends_the_audio_stream(page: Page):
    live = FakeLive(page)
    open_call(page, live)
    turn_mic_on(page, live)
    mic_button(page).click()
    wait_for(page, lambda: any(f.get("audioStreamEnd") for f in live.frames("realtimeInput")), what="audioStreamEnd")
    page.wait_for_timeout(300)
    count = len(live.audio_frames())
    page.wait_for_timeout(1000)
    assert len(live.audio_frames()) == count, "audio kept streaming after mute"


def test_transcripts_render_as_text(page: Page):
    live = FakeLive(page)
    open_call(page, live)
    live.push({"serverContent": {"inputTranscription": {"text": "My cat Mimi is limping "}}})
    live.push({"serverContent": {"inputTranscription": {"text": "<img src=x onerror=\"window.__xss=1\">after a jump"}}})
    live.push({"serverContent": {"outputTranscription": {"text": "Is she putting weight on the leg?"}}})
    expect(page.locator(".cap-user")).to_contain_text("My cat Mimi is limping <img src=x")
    expect(page.locator(".cap-ai")).to_contain_text("putting weight on the leg")
    assert page.locator(".captions img").count() == 0
    assert page.evaluate("window.__xss") is None


def test_model_audio_plays_and_the_owner_can_interrupt(page: Page):
    live = FakeLive(page)
    open_call(page, live)
    stage = page.locator(".avatar-stage")
    live.push({"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": pcm16(10)}}]}}})
    talking = re.compile(r"\btalking\b")
    expect(stage).to_have_class(talking)
    live.push({"serverContent": {"interrupted": True}})
    expect(stage).not_to_have_class(talking, timeout=1000)  # 10 s queued: only a flush stops it this fast


def test_typed_message_goes_over_the_live_socket(page: Page):
    live = FakeLive(page)
    open_call(page, live)
    box = page.get_by_role("textbox")
    box.fill("Mimi is limping after jumping off a wardrobe")
    box.press("Enter")
    wait_for(page, lambda: any(f.get("text") == "Mimi is limping after jumping off a wardrobe"
                               for f in live.frames("realtimeInput")), what="typed text frame")
    expect(page.locator(".cap-user")).to_contain_text("Mimi is limping")


def test_tool_call_is_forwarded_answered_and_rendered(page: Page, app_server):
    evidence = httpx.post(f"{app_server}/api/v1/knowledge/search", json={"query": "accident cover"}).json()
    live = FakeLive(page, tool_ui={"search_policy": evidence})
    open_call(page, live)
    live.push({"toolCall": {"functionCalls": [{"id": "fc-1", "name": "search_policy", "args": {"query": "accident cover"}}]}})
    wait_for(page, lambda: live.frames("toolResponse"), what="toolResponse")

    call = live.tool_requests[0]
    assert (call["id"], call["name"], call["args"], call["share_with_gemini"]) == ("fc-1", "search_policy", {"query": "accident cover"}, True)
    assert call["context"] == {"language": "en", "share_location": False}  # no location without consent
    [answer] = live.frames("toolResponse")[0]["functionResponses"]
    assert (answer["id"], answer["name"], answer["response"]) == ("fc-1", "search_policy", {"ok": True, "echo": "fc-1"})
    card = page.locator("details", has_text="search_policy")
    card.locator("summary").click()
    expect(card).to_contain_text("Demo policy")
    expect(card).to_contain_text(evidence["evidence"][0]["snippet"][:40])


def test_clinic_call_only_offers_the_dialer_and_places_no_call(page: Page):
    live = FakeLive(page, tool_ui={"open_clinic_call": CLINIC_UI})
    open_call(page, live)
    live.push({"toolCall": {"functionCalls": [{"id": "fc-2", "name": "open_clinic_call", "args": {"clinic_index": 0}}]}})
    card = page.locator("details", has_text="open_clinic_call")
    card.locator("summary").click()
    expect(card).to_contain_text("No call placed")
    expect(card.get_by_role("link", name="Open device dialer for Tierarztpraxis Seefeld")).to_have_attribute("href", "tel:+41440000000")


def test_duplicate_tool_call_runs_once(page: Page):
    live = FakeLive(page)
    open_call(page, live)
    call = {"toolCall": {"functionCalls": [{"id": "fc-3", "name": "search_policy", "args": {"query": "physio"}}]}}
    live.push(call)
    live.push(call)
    wait_for(page, lambda: live.frames("toolResponse"), what="toolResponse")
    page.wait_for_timeout(500)
    assert len(live.tool_requests) == 1 and len(live.frames("toolResponse")) == 1


def test_token_failure_is_explained(page: Page):
    live = FakeLive(page, token_status=503)
    page.goto(LIVE)
    page.locator(".start-btn").click()
    page.get_by_role("button", name="Agree and start").click()
    expect(page.locator(".cap-error")).to_contain_text("not configured")
    assert live.socket is None


def test_denied_microphone_is_explained_and_typing_still_works(page: Page):
    page.add_init_script(DENY_MIC)
    live = FakeLive(page)
    open_call(page, live)
    mic_button(page).click()
    expect(page.locator(".cap-error")).to_contain_text("Couldn't open the microphone")
    box = page.get_by_role("textbox")
    box.fill("My cat is limping")
    box.press("Enter")
    wait_for(page, lambda: any(f.get("text") == "My cat is limping" for f in live.frames("realtimeInput")), what="typed text")


def test_dropped_socket_is_reported_and_the_mic_released(page: Page):
    page.add_init_script(TRACK_SPY)
    live = FakeLive(page)
    open_call(page, live)
    turn_mic_on(page, live)
    live.socket.close(code=1011, reason="internal error")
    expect(page.locator(".cap-error")).to_contain_text("disconnected")
    page.wait_for_function(MIC_RELEASED)


def test_hang_up_closes_the_session_and_releases_the_mic(page: Page):
    page.add_init_script(TRACK_SPY)
    live = FakeLive(page)
    open_call(page, live)
    turn_mic_on(page, live)
    page.get_by_role("button", name="Hang up").click()
    wait_for(page, lambda: live.closed, what="socket close")
    page.wait_for_function(MIC_RELEASED)
    expect(page.locator(".start-btn")).to_be_visible()
