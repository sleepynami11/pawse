---
name: gradium-voice
description: >-
  Work on Pawse's Gradium voice pipeline (own-voice cloning, German localization, TTS preview/speech) or
  add STT/streaming: API facts, endpoints, formats, credits. Use when someone says "Gradium", "clone my
  voice", "German voice", "text to speech", "speech to text", "GRADIUM_API_KEY", or targets the Gradium prize.
---

# Gradium voice

Verified 2026-10-10 against https://docs.gradium.ai (API reference, limits, credits).

## What is already wired

- Code: `pawse/voice.py` (helper `gradium()` adds auth, timeouts, size caps); tests: `tests/test_voice.py` (mocked).
- Product rules, endpoints, consent and limits: [docs/VOICE_CONCIERGE.md](../../../docs/VOICE_CONCIERGE.md).
- Env: `GRADIUM_API_KEY` (server only, `.env`), optional `GRADIUM_VOICE_ID_DE`, `GRADIUM_STANDARD_VOICE_ID_DE`.
  Missing key: voice routes return 503 and the UI disables paid operations.
- Used upstream calls: `POST /voices/` (clone), `POST /voice-generator/localize`,
  `GET /voice-generator/embeddings`, `POST /voices/from-embedding`, `POST /post/speech/tts`, `DELETE /voices/...`.

## API facts

- Auth header `x-api-key: <key>`. REST base `https://api.gradium.ai/api`, WebSocket `wss://api.gradium.ai/api`.
- TTS REST: `POST /post/speech/tts` body `{text, voice_id, output_format, only_audio, model_name?, json_config?}`.
  `only_audio: true` returns raw bytes; otherwise NDJSON with base64 `audio`.
- TTS WebSocket `/speech/tts`: send `{"type":"setup","voice_id":...,"output_format":"pcm"}`, wait for
  `ready`, then `{"type":"text","text":...}` chunks, then `{"type":"end_of_stream"}`.
- STT REST: `POST /post/speech/asr?json_config={"language":"de"}` with raw audio body and
  `Content-Type: audio/wav`. NDJSON; join messages with `type: "text"`.
- STT WebSocket `/speech/asr`: first message is setup with required `json_config.language`
  (`en`, `fr`, `es`, `pt`, `de`, `any`); audio frames 24 kHz 16-bit mono PCM, 80 ms.
- Languages for cloning/speech: English, French, German, Spanish, Portuguese. Chinese and Hindi input go through Gemini.
- Output formats: `wav`, `pcm` (48 kHz), `opus`, `pcm_8000`..`pcm_48000`, `ulaw_8000`, `alaw_8000` (telephony).
- Errors before streaming: HTTP 500 plain text, e.g. `error from server 1008: API key is revoked or expired`.
- Credits: TTS 1 per character, STT 3 per second of audio. Sessions max 3000 s.

## Latency tips

For long text open the TTS WebSocket, send phrase-sized chunks with punctuation, play `pcm` as it
arrives. Speak the first sentence while the agent is still generating.

## Safety

Never ship the key to the browser (for live mic streaming the server mints a one-time token via
`GET /api/api-keys/token`). Clone only the owner's own voice with explicit consent; preview before saving.

## Links

Docs index https://docs.gradium.ai/llms.txt · TTS https://docs.gradium.ai/api-reference/endpoint/tts-post ·
Limits https://docs.gradium.ai/guides/limits · Browser tokens https://docs.gradium.ai/guides/browser-websockets

## Keep this skill current

Re-check the API reference before relying on a field; update `pawse/voice.py`, its test and the verified
date together. Run `python scripts/validate_skills.py` after editing.
