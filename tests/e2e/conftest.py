"""Browser and real-speech tests (issue #25). Opt-in so `bash scripts/check.sh` stays fast and keyless.

PAWSE_E2E=1 collects the Playwright tests (test_browser_*.py); they need `pip install -r
requirements-e2e.txt`, `python -m playwright install chromium` and Node (to build web/ once). The
speech-metric tests always run; the real-recording tests skip unless PAWSE_LIVE_SPEECH=1 (README.md).
"""
import importlib.util
import os

import pytest

from e2e_helpers import KEYS, ensure_web_build, fake_mic_args, serve

if os.getenv("PAWSE_E2E") != "1" or importlib.util.find_spec("playwright") is None:
    collect_ignore_glob = ["test_browser_*.py"]

# Chrome logs every 4xx/5xx response as a console error; tests that mock one assert the visible outcome instead.
EXPECTED_CONSOLE = ("Failed to load resource: the server responded with a status of",)


@pytest.fixture(scope="session")
def app_server():
    """The real app (legacy page at /, React app at /app) with every provider key blanked."""
    ensure_web_build()
    proc, url = serve(os.environ | {key: "" for key in KEYS})
    yield url
    proc.terminate()
    proc.wait(10)


@pytest.fixture(scope="session")
def speech_wav(tmp_path_factory):
    from audio_fixtures import speech_then_pause
    path = tmp_path_factory.mktemp("audio") / "speech-turn.wav"
    path.write_bytes(speech_then_pause())
    return path


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, speech_wav):
    return {**browser_type_launch_args, "args": fake_mic_args(speech_wav)}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, app_server):
    return {**browser_context_args, "base_url": app_server, "permissions": ["microphone"], "locale": "en-US",
            "viewport": {"width": 1440, "height": 900}}


@pytest.fixture(autouse=True)
def no_console_errors(request):
    """Every browser test also fails on an unexpected console error or an uncaught page exception."""
    if not request.node.path.name.startswith("test_browser_") or "page" not in request.fixturenames:
        yield
        return
    page = request.getfixturevalue("page")
    page.set_default_timeout(5_000)  # local app: anything slower is a failure
    errors = []
    page.on("console", lambda m: m.type == "error" and not m.text.startswith(EXPECTED_CONSOLE) and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    yield
    assert not errors, f"console errors: {errors}"


@pytest.fixture
def transcriptions(page):
    """Captures POST /voice/transcriptions bodies and answers with a canned transcript."""
    seen = []

    def handle(route):
        seen.append(route.request.post_data_json)
        route.fulfill(status=200, json={"text": "My cat Mimi is limping after jumping off the wardrobe."})

    page.route("**/api/v1/voice/transcriptions", handle)
    return seen
