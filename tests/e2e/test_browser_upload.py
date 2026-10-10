"""Audio upload. Only the original page at / has it (the React app records but has no audio upload)."""
import pytest
from playwright.sync_api import Page, expect

from audio_fixtures import read_wav, speechlike
from pawse.voice import inspect_wav


@pytest.fixture(autouse=True)
def gemini_reported_configured(page: Page):
    """Transcription is mocked, so let the page enable it although the test server has no Gemini key."""
    def handle(route):
        status = route.fetch().json() | {"gemini_configured": True}
        route.fulfill(json=status)
    page.route("**/api/v1/voice/status", handle)


def upload(page: Page, name: str, data: bytes, mime="audio/wav"):
    page.locator("#message-upload").set_input_files({"name": name, "mimeType": mime, "buffer": data})


def preview_seconds(page: Page) -> float:
    player = page.locator("#message-player")
    expect(player).to_be_visible()
    return player.evaluate("""a => new Promise((ok, fail) => {
      if (a.readyState >= 1 && isFinite(a.duration)) return ok(a.duration);
      a.addEventListener("loadedmetadata", () => ok(a.duration), { once: true });
      a.addEventListener("error", () => fail(new Error("preview cannot load")), { once: true });
    })""")


def transcribe(page: Page):
    page.locator("#gemini-voice-consent").check()
    page.locator("#transcribe-message").click()
    expect(page.locator("#voice-message")).to_have_value("My cat Mimi is limping after jumping off the wardrobe.")


@pytest.mark.parametrize("rate,channels", [(48000, 2), (44100, 1), (8000, 1)], ids=["48k-stereo", "44k-mono", "8k-phone"])
def test_uploaded_wav_plays_locally_and_is_sent_as_mono_16_bit(page: Page, transcriptions, rate, channels):
    page.goto("/")
    upload(page, "mimi.wav", speechlike(seconds=3, rate=rate, channels=channels))
    assert preview_seconds(page) == pytest.approx(3, abs=0.2)
    transcribe(page)
    channels_out, width, _, seconds, rms = read_wav(transcriptions[0]["audio"]["data"])
    assert (channels_out, width) == (1, 2)
    assert seconds == pytest.approx(3, abs=0.2)
    assert rms > 0.02
    inspect_wav(transcriptions[0]["audio"]["data"])


@pytest.mark.parametrize("name,data,reason", [
    ("short.wav", speechlike(seconds=0.2), "seconds"),
    ("long.wav", speechlike(seconds=65, rate=8000), "seconds"),
    ("notes.wav", b"this is not audio" * 100, "record or upload a new one"),
], ids=["too-short", "too-long", "not-audio"])
def test_unusable_upload_is_explained_and_never_sent(page: Page, transcriptions, name, data, reason):
    page.goto("/")
    upload(page, name, data)
    expect(page.locator("#message-status")).to_contain_text(reason)
    expect(page.locator("#message-player")).to_be_hidden()
    page.locator("#gemini-voice-consent").check()
    expect(page.locator("#transcribe-message")).to_be_disabled()
    assert transcriptions == []


def test_a_new_upload_replaces_the_previous_one(page: Page, transcriptions):
    page.goto("/")
    upload(page, "first.wav", speechlike(seconds=2))
    assert preview_seconds(page) == pytest.approx(2, abs=0.2)
    upload(page, "second.wav", speechlike(seconds=4))
    page.wait_for_function("document.querySelector('#message-player').duration > 3")
    transcribe(page)
    assert len(transcriptions) == 1
    assert read_wav(transcriptions[0]["audio"]["data"])[3] == pytest.approx(4, abs=0.2)


def test_recorded_message_on_the_original_page_is_audible(page: Page, transcriptions):
    page.goto("/")
    page.locator("#message-record").click()
    page.wait_for_timeout(3000)
    page.locator("#message-record").click()
    preview_seconds(page)
    transcribe(page)
    channels, width, _, seconds, rms = read_wav(transcriptions[0]["audio"]["data"])
    assert (channels, width) == (1, 2) and 2 <= seconds <= 4.5 and rms > 0.02
    inspect_wav(transcriptions[0]["audio"]["data"])
