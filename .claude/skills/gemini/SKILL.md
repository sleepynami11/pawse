---
name: gemini
description: >-
  Use Google Gemini (Google DeepMind) in Pawse: pick a model ID, set up the event key, build the Live API
  voice session with ephemeral tokens and tool calling, handle rate limits. Use when the user says
  "use Gemini", "Gemini Live", "which Gemini model", "GEMINI_LIVE_MODEL", "ephemeral token",
  "Gemini rate limit / 429", or targets the Google DeepMind prize. For raw API code, also read
  gemini-api-dev / gemini-live-api-dev.
---

# Gemini (Google DeepMind) in Pawse

Verified 2026-10-10 against ai.google.dev model and deprecation pages and the event brief.
Pawse is a FastAPI app (`pawse/`, static frontend in `pawse/static/`). Gemini text/vision calls live in
`pawse/providers.py` and `pawse/voice.py`. The team's verified model picks are in
[docs/MODEL_ALLOCATION.md](../../../docs/MODEL_ALLOCATION.md) (probe: `scripts/probe_models.py`, results in
`docs/model-access-check.json`). Official code and protocol rules live in Google's skills: [gemini-api-dev](../gemini-api-dev/SKILL.md) and [gemini-live-api-dev](../gemini-live-api-dev/SKILL.md).

## Setup

- `GEMINI_API_KEY`: server-side only, in the root `.env` (git-ignored, loaded by `pawse/app.py`).
- `GEMINI_MODEL=gemini-3-flash-preview` is the team's verified text/vision default (overrides:
  `GEMINI_CARE_MODEL`, `GEMINI_VOICE_MODEL`). Don't switch to an ID the probe has not called successfully.
- `GEMINI_LIVE_MODEL=gemini-3.8-live` for the future Live session: listed for the team key with
  `bidiGenerateContent`, not yet exercised end to end.
- SDKs: `@google/genai` (JS) or `google-genai` (Python). The legacy `@google/generative-ai` and
  `google-generativeai` are deprecated: never use them.

### Event temp account

Guide: https://goo.gle/hackathon-account, steps in [docs/HACKATHON.md](../../../docs/HACKATHON.md). Facts that matter:
- The project is paid **Tier 3**; the account and its keys are **deleted the day after**. Push code, export
  assets, and move any deploy that must outlive the day to your own project.
- A key pushed to GitHub gets **every key in the project revoked**. If one leaks: delete it in AI Studio and
  create a new one (removing it in a later commit is not enough, it stays in history).
- Abuse (thousands of requests) = disqualification. Rehearse against a mock, not the live key in a loop.
- 503 "model overwhelmed" on a freshly launched model: retry, or fall back to an older ID.

## Live API (Pawse's core)

Flow from [docs/SPEC.md](../../../docs/SPEC.md): the backend holds the key and mints a short-lived token,
the browser opens the Live session with it and streams mic audio, the app executes tool calls and sends
results back.

- Ephemeral tokens: https://ai.google.dev/gemini-api/docs/live-api/ephemeral-tokens. Lock the token to the
  model and config server side, keep it short-lived, never ship `GEMINI_API_KEY` to the browser.
- In Pawse: a FastAPI route mints the token with `google-genai` (`client.auth_tokens.create`), and
  `pawse/static/voice.js` opens the session with `ai.live.connect` from `@google/genai` (see gemini-live-api-dev).
- `gemini-3.8-live` calls functions asynchronously by default (`behavior: NON_BLOCKING`): the cat keeps
  talking while a tool runs. Send results back with `sendToolResponse` (JS) / `send_tool_response` (Python); show task status in the UI meanwhile.
- Ask before anything that cannot be undone (purchase, send, post, delete): the app confirms with the user
  before executing the tool, not the model.

## Model IDs

| ID | Use when |
|---|---|
| `gemini-3.8-live` | **Default for Pawse.** Low-latency voice dialogue, async tool calls |
| `gemini-3.8-live-extended-thinking` | Heavier reasoning while talking. Requires `NON_BLOCKING` tools, and `turnComplete` no longer means idle: wait for `interaction_status == "IDLE"` |
| `gemini-3-flash-preview` | Team default for text/vision (verified HTTP 200 on the team key) |
| `gemini-3.8-flash` | Newer Flash, listed for the team key but not yet probed: run `scripts/probe_models.py` before switching |
| `gemini-3.5-flash-lite` | Cheap, fast classify/extract/route |
| `gemini-3.8-flash-tts`, `gemini-3.5-transcribe` | Non-live speech out / speech in |
| `gemini-3.5-transcribe-live` | Live captions for the transcript panel |

Legacy, do not use: `gemini-3.1-flash-live-preview`, `gemini-2.5-flash-native-audio-*`,
`gemini-live-2.5-flash-preview`, `gemini-2.0-flash-live-001` (see gemini-live-api-dev `references/migration.md`).
Check the deprecations page before the demo.

## Rate-limit gotchas

- Limits are per Google Cloud project, not per key: teammates' keys from one project share them.
- RPM, TPM and RPD each apply; RPD resets at midnight Pacific. Live numbers: https://aistudio.google.com/rate-limit
- Preview models have tighter limits. On `429 RESOURCE_EXHAUSTED` switch model or back off.

## Links

- Models: https://ai.google.dev/gemini-api/docs/models
- Deprecations: https://ai.google.dev/gemini-api/docs/deprecations
- Live API: https://ai.google.dev/gemini-api/docs/live-api (tools: `/live-api/tools`)

## Keep this skill current

Google's skills update with `npx skills update gemini-api-dev gemini-live-api-dev` (pinned in
`skills-lock.json`). Re-check the models and deprecations pages, then update the table and the verified date.
