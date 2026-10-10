"""Shared plumbing for tests/e2e: the real app server, Chromium's fake microphone, a fake Gemini Live socket."""
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
KEYS = ("GEMINI_API_KEY", "GRADIUM_API_KEY", "GRADIUM_VOICE_ID_DE", "GRADIUM_STANDARD_VOICE_ID_DE",
        "GOOGLE_PLACES_API_KEY", "MAPIFY_BASE_URL")


def ensure_web_build():
    """The React app is served from web/dist: (re)build it when missing or older than any web/ source."""
    built = WEB / "dist" / "index.html"
    sources = [WEB / "index.html", WEB / "package-lock.json", WEB / "vite.config.js",
               *(WEB / "src").rglob("*"), *(WEB / "public").rglob("*")]
    if built.is_file() and all(f.stat().st_mtime <= built.stat().st_mtime for f in sources if f.is_file()):
        return
    if not (WEB / "node_modules").is_dir():
        subprocess.run(["npm", "ci"], cwd=WEB, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["npm", "run", "build"], cwd=WEB, check=True, stdout=subprocess.DEVNULL)


def serve(env):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "pawse.app:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/api/v1/health", timeout=1).status_code == 200:
                return proc, url
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise RuntimeError(f"uvicorn exited: {proc.stderr.read().decode()[-2000:]}")
        time.sleep(0.1)
    proc.terminate()
    raise RuntimeError("uvicorn did not become healthy within 10 s")


def fake_mic_args(wav_path, loop=True):
    """Chromium's fake capture device plays this WAV as the microphone (no real hardware)."""
    return ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-audio-capture={wav_path}{'' if loop else '%noloop'}",
            "--autoplay-policy=no-user-gesture-required"]


# Records every audio MediaStreamTrack the page opens, so tests can check the mic is released.
TRACK_SPY = """
window.__micTracks = [];
const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = async (constraints) => {
  const stream = await original(constraints);
  window.__micTracks.push(...stream.getAudioTracks());
  return stream;
};
"""
MIC_RELEASED = "window.__micTracks.length > 0 && window.__micTracks.every(t => t.readyState === 'ended')"

DENY_MIC = """
navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
"""


def wait_for(page, condition, seconds=10, what="condition"):
    end = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > end:
            raise AssertionError(f"timed out waiting for {what}")
        page.wait_for_timeout(50)  # lets Playwright deliver socket and route events


LIVE_SOCKET = re.compile(r"wss://generativelanguage\.googleapis\.com/.*")
TOKEN = {"token": "auth_tokens/e2e-test", "model": "gemini-3.8-live", "api_version": "v1alpha",
         "expires_at": "2099-01-01T00:00:00Z", "new_session_expires_at": "2099-01-01T00:00:00Z",
         "tools": ["assess_and_find_vets", "search_policy", "draft_vet_call_script", "open_clinic_call"]}


class FakeLive:
    """Plays Gemini Live (BidiGenerateContent wire format): records what the browser sends, pushes server messages.

    `/live/tokens` and `/live/tool-calls` are mocked; `tool_ui` maps a tool name to the `ui` it returns.
    """

    def __init__(self, page, token_status=201, tool_ui=None):
        self.sent, self.socket, self.url, self.closed = [], None, None, False
        self.token_requests, self.tool_requests, self.tool_ui = [], [], tool_ui or {}
        page.route_web_socket(LIVE_SOCKET, self._connect)
        page.route("**/api/v1/live/tokens", lambda r: (
            self.token_requests.append(r.request.post_data_json),
            r.fulfill(status=token_status, json=TOKEN if token_status == 201 else {"detail": "Gemini Live is not configured."})))
        page.route("**/api/v1/live/tool-calls", self._tool)

    def _connect(self, ws):
        self.socket, self.url = ws, ws.url
        ws.on_message(self._message)
        # ws.on_close() raises KeyError('code') in Playwright 1.63 when the page calls close() without a code,
        # so listen on the route's channel, which still forwards the close to the default handler.
        ws._impl_obj._channel.on("closePage", lambda _: setattr(self, "closed", True))

    def _message(self, message):
        data = json.loads(message if isinstance(message, str) else message.decode())
        self.sent.append(data)
        if "setup" in data:
            self.push({"setupComplete": {}})

    def _tool(self, route):
        call = route.request.post_data_json
        self.tool_requests.append(call)
        route.fulfill(json={"id": call["id"], "name": call["name"], "response": {"ok": True, "echo": call["id"]},
                            "ui": self.tool_ui.get(call["name"])})

    def push(self, message):
        self.socket.send(json.dumps(message))

    def frames(self, key):
        return [m[key] for m in self.sent if key in m]

    def audio_frames(self):
        return [f["audio"] for f in self.frames("realtimeInput") if "audio" in f]
