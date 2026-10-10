# Browser and real-speech tests (issue #25)

Automated versions of the manual checks in [docs/VALIDATION.md](../../docs/VALIDATION.md): microphone capture,
audio upload, desktop layout, the Gemini Live voice client, and recognition of English, Chinese, German and Hindi
speech. They drive the shipped pages: the React app at `/app` (built from `web/`) and the original page at `/`.

## Run

```bash
pip install -r requirements-e2e.txt && python -m playwright install chromium
PAWSE_E2E=1 python -m pytest tests/e2e                      # 62 browser tests, no keys, about 75 s
PAWSE_E2E=1 python -m pytest tests/e2e -k live_voice --headed   # watch one file
```

The suite (re)builds `web/dist` whenever it is missing or older than a `web/` source (needs Node), so it always
tests your current frontend. `bash scripts/check.sh` skips the browser tests and runs only the speech-metric tests.
Layout screenshots land in `test-results/layout/` (git-ignored) for a human look.

## What runs, and how without hardware or keys

| File | Page | What it proves |
| --- | --- | --- |
| `test_browser_live_voice.py` | `/app/?live=1` | Consent before any token; ephemeral token on the constrained socket; mic off until the owner turns it on; audible 16 kHz PCM at real-time pace; mute sends `audioStreamEnd` and stops audio; transcripts as text (no HTML); model audio plays and an interruption flushes it; typed text goes over the socket; tool calls forwarded once, answered and rendered; `open_clinic_call` only offers the dialer; token failure, denied mic and dropped socket are explained; hang-up and drops release the mic |
| `test_browser_recording.py` | `/app/?live=1&voice=rest`, own voice | REST fallback: one audible mono 16 kHz WAV per spoken turn, accepted by the server's validator, in the chosen language; own-voice recorder plays back locally, uploads nothing, rejects under 10 s; denied mic explained |
| `test_browser_upload.py` | `/` | Audio upload (the React app has none): 48 kHz stereo, 44.1 kHz and 8 kHz WAVs play locally and are sent as mono 16-bit; too short, too long and non-audio files are explained and never sent; a new upload replaces the old; a recorded message is audible |
| `test_browser_layout.py` | `/app`, call screen, `/` | At 1280, 1440, 1920 and 390 px: no sideways scroll, no overlapping controls, WCAG 2.2 target size (with its spacing and inline-link exceptions), call controls on screen, app column centred on desktop, demo badge visible |

- **Microphone:** Chromium's fake capture device loops 2.5 s of speech-like sound and 2.5 s of silence, so a
  silent or broken capture path fails and voice-activity detection sees turns end.
- **Gemini Live:** the Live WebSocket is answered by `FakeLive` (`e2e_helpers.py`) in the real `@google/genai`
  wire format; `/live/tokens` and `/live/tool-calls` are mocked. The app's bundled SDK, AudioWorklet and playback
  run for real.
- **Server:** the real app runs with all provider keys blanked; tests mock only the provider-backed routes they need.
- Every browser test also fails on an unexpected console error.

## Real speech (opt-in, spends Gemini quota)

```bash
set -a; . ./.env; set +a     # GEMINI_API_KEY
export PAWSE_LIVE_SPEECH=1 PAWSE_RECORDINGS_DIR=/mnt/pawse-recordings
python -m pytest tests/e2e/test_real_recordings_api.py         # /voice/transcriptions (REST fallback path)
PAWSE_E2E=1 python -m pytest tests/e2e/test_browser_real_speech.py   # spoken into the live call, real Gemini Live
```

`PAWSE_RECORDINGS_DIR/manifest.json` lists the recordings; they never go in git:

```json
{ "recordings": [
  { "file": "de-01.wav", "language": "de", "reference": "Meine Katze Mimi hinkt seit dem Sprung vom Schrank.",
    "speaker": "s1", "device": "laptop mic" }
] }
```

- At least 3 per language (`en`, `zh`, `de`, `hi`), ideally different speakers and devices. Recordings are personal
  data: collect them with the speaker's consent, keep them on `/mnt`, delete them when done.
- Mono 16-bit PCM WAV, 0.5 to 60 s, up to 3 MB: `ffmpeg -i in.m4a -ac 1 -ar 16000 -sample_fmt s16 de-01.wav`.
- `reference` is exactly what was said; write numbers the way they are spoken.

Pass bar ([speech_metrics.py](speech_metrics.py)): word error rate at most 0.15 (en), 0.20 (de), 0.30 (hi);
character error rate at most 0.20 (zh). Chinese must come back in Han characters and Hindi in Devanagari. Silence must
give an empty transcript. Per-recording results go to `test-results/speech-api.json`.

Synthetic speech is a pipeline smoke test, not an accuracy benchmark: `espeak-ng` English, German and Hindi work over
REST, but its Mandarin voice reads tone codes ("T1 F5 …") and Gemini Live barely recognises any of it. Use human
recordings to judge recognition.
