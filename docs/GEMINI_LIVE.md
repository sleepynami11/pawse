# Gemini Live voice session

Pawse holds a real-time voice conversation with the owner through the Gemini Live API (`gemini-3.8-live`). While it talks, Gemini calls Pawse tools, and those tools run the existing backend features. The browser holds only a short-lived, single-use token. The permanent `GEMINI_API_KEY` stays on the server.

```
Browser                     Pawse backend                         Gemini Live
  | POST /live/tokens ------->| mint token locked to model,          |
  |<-------- {token, model} --|   prompt and tools (v1alpha) ------->|
  | ai.live.connect(token) --------------------------------------->|
  | mic PCM 16 kHz ----------------------------------------------->|
  |<--------------------------------- audio 24 kHz + transcripts ---|
  |<---------------------------------------------- toolCall --------|
  | POST /live/tool-calls --->| runs care / policy / script tool     |
  |<-- {response, ui} --------|                                      |
  | sendToolResponse(response) ----------------------------------->|
  | render ui (clinics, script, confirm dialog)                      |
```

## Backend (implemented)

### `POST /api/v1/live/tokens` → 201

Request: `{ "share_with_gemini": true, "language": "en" }`. `language` is `en`, `zh`, `de` or `hi` and sets the language Pawse starts in. Consent is required (422 without it).

Response:
```json
{ "token": "auth_tokens/...", "model": "gemini-3.8-live", "api_version": "v1alpha",
  "expires_at": "...Z", "new_session_expires_at": "...Z",
  "tools": ["assess_and_find_vets", "search_policy", "draft_vet_call_script", "open_clinic_call"] }
```

- The token works for one session (`uses: 1`). The session must start within 60 seconds, and the token expires after 30 minutes.
- The server locks the model, system prompt, AUDIO output, input and output transcription, and the tool declarations into the token. The browser can't change them.
- Errors: 503 when there is no key, 502 when Gemini refuses (safe message only), 429 after 10 sessions per 10 minutes per browser session. The rate limit is per Google project and shared by the team.

### `POST /api/v1/live/tool-calls` → 200

Request: forward each `functionCall` from the `toolCall` message as is, plus browser context:
```json
{ "id": "<functionCall.id>", "name": "<functionCall.name>", "args": { ... },
  "share_with_gemini": true,
  "context": { "language": "en", "cat_name": "Mimi", "share_location": true, "location": { "lat": 47.37, "lng": 8.54 } } }
```
Send `location` only when the owner has turned on location sharing.

Response: `{ "id", "name", "response": { ... }, "ui": { ... } | null }`.
- **`response`** goes back to Gemini unchanged: `session.sendToolResponse({ functionResponses: [{ id, name, response }] })`. Tool failures come back as `response.error` with HTTP 200, so the conversation can continue.
- **`ui`** is the full data to show:

| Tool | What it runs | `ui` |
| --- | --- | --- |
| `assess_and_find_vets` | The agent workflow (`/agents/runs`): care guidance plus ranked clinics | `{ care: CareResult, trace: AgentTrace[] }` |
| `search_policy` | `/knowledge/search` (demo corpus, cited) | `KnowledgeResult` |
| `draft_vet_call_script` | The reviewed German script logic behind `/voice/scripts`, with subtitles in `context.language` | `CallScript` |
| `open_clinic_call` | Looks up a clinic from this session's last search | `{ action: "confirm_call", clinic_name, phone, call_url }` |

**`confirm_call` is an app gate:** show a confirm dialog, and only open `call_url` (`tel:`) if the owner confirms. Pawse never places or joins the call.

Errors: 422 for an unknown tool or missing consent. 429 when 3 tool calls are already running for this session (15 globally).

`GET /api/v1/voice/status` also reports `live_configured` and `live_model`.

## React frontend (implemented)

`web/src/agents/geminiLiveAgent.js` uses the pinned npm `@google/genai` package and the model/API version returned by the token endpoint. `/app/?live=1` selects native Live audio; `&voice=rest` explicitly selects the older REST/browser-speech fallback.

- Explicit sharing consent before token creation; microphone remains off until enabled.
- AudioWorklet resamples input to 16 kHz mono PCM16. Playback queues all returned PCM parts at the advertised rate (normally 24 kHz).
- Interruptions flush playback; input/output transcripts render as text. Tools execute through the session-bound backend and return their original response to Gemini.
- End closes the socket, audio contexts, media tracks and pending HTTP requests. Sessions stop after eight minutes; resumption is not implemented.
- Camera preview stays local; selected photos are sent explicitly. Location stays off in the conversation tool context; use the separate clinic search consent flow.
- Own-voice setup is separate: Gradium enrollment and German rehearsal are available from the React home page. Gemini native voices are not owner clones.

## Verified (2026-10-10)

Against the event key with `gemini-3.8-live`: a token was minted through REST, a session opened on the constrained v1alpha endpoint, and a text turn ("My cat Mimi is limping after jumping off a wardrobe") made Gemini call `assess_and_find_vets`. `/live/tool-calls` ran the workflow, the result was sent back, and Gemini answered in audio with transcripts, using the tool result. The React capture/playback implementation is now present. Browser testing exercised a synthetic typed Live turn and a rendered care-tool result without console errors. Human microphone capture, listening quality and multilingual accuracy remain manual tests.
