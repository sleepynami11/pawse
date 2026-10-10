# Pawse Controller–Frontend Contract

This document maps the current screens to backend controllers. It defines what the frontend sends, what it may display as confirmed, and how it handles incomplete work. For payload details, follow the domain contracts below.

## 1. Global conventions

- **Base URL:** `/api/v1`, on the same origin as the app. Send JSON for POST bodies; read the response content type before treating it as JSON, SSE or WAV.
- **Session:** retain the `pawse_session` cookie across requests. It isolates local results and voice IDs; it is not an account or authentication system. API tools must use a cookie jar to reproduce a browser workflow.
- **Configuration:** only server-side code receives API keys. `/health` reports local process health; `/capabilities`, `/agents/graph` and `/voice/status` report configuration and supported flows, not successful live provider checks.
- **Consent:** care AI, location sharing, Gemini voice processing, Gradium sharing and own-voice consent are separate choices. Do not infer one from another.
- **Validation:** unknown request fields are rejected. The mutation body limit is 4,500,000 bytes; decoded photos and WAV inputs are each limited to 3,000,000 bytes.
- **Persistence:** keep recordings, photos and care data out of browser analytics and persistent browser storage. Responses use `Cache-Control: no-store`.

The implementation is the static app in [pawse/static](../pawse/static/) with controllers in [pawse/app.py](../pawse/app.py), [orchestration.py](../pawse/orchestration.py), [voice.py](../pawse/voice.py) and [knowledge.py](../pawse/knowledge.py).

## 2. Screen-to-controller map

| Screen/action | Method and path | Success | Frontend responsibility |
| --- | --- | --- | --- |
| Startup/configuration | `GET /health`, `GET /capabilities` | 200 JSON | Distinguish configured, unavailable and verified behavior |
| Care form, streamed mode | `POST /care/requests?stream=true` | 200 SSE | Display safety immediately; merge events until the final result |
| Care form, single response | `POST /care/requests` | 201 `CareResult` | Display useful results even when status is `partial` |
| Agent mode | `GET /agents/graph`, `POST /agents/runs` | 200 graph; 201 run | Render roles and the final execution trace |
| Retrieve/delete summary | `GET` / `DELETE /care/requests/{request_id}` | 200 / 204 | Use the same session; remove deleted results from the UI |
| Dictation and call draft | `POST /voice/transcriptions`, `POST /voice/scripts` | 200 JSON | Let the owner review transcript, facts and subtitles |
| My voice | Voice clone/localization routes | JSON or WAV | Follow the [voice state sequence](controller-voice-contract.md) |
| Generate German audio | `POST /voice/speech` | 200 WAV | Play/download after user action; do not label as a completed call |
| Demo policy evidence | `POST /knowledge/search` | 200 `KnowledgeResult` | Show synthetic scope, exact snippets and citations |
| Mimi rehearsal | `GET /demo/mimi` | 200 JSON | Keep simulated replies, costs and arrangements visibly labeled |
| Existing CatAgent chat/report | `POST /agent/requests` | 200 SSE | Render wrapped legacy events and stream-level failures |

Full paths add the `/api/v1` prefix. Singular `/agent/requests` is the legacy bridge; plural `/agents/runs` is the new coordinator.

## 3. Care form, results and clinic cards

Submit either a direct `CareRequest` or an `AgentRunRequest` containing `{ "care": CareRequest }`. Do not submit both for one interaction: they share the active-work limit and would duplicate provider calls. The current interface supports selecting the workflow.

The [care contract](controller-care-contract.md) defines valid input and events. Store the returned `request_id`; an agent run's care ID is `response.care.request_id`. A follow-up answer currently requires a new request containing the updated concern. There is no conversation-turn or case-update endpoint for care navigation.

Render `assessment.urgency` independently from provider progress. An urgent warning must remain visible during loading and failure. Follow-up questions are questions for the owner/vet, not a confirmed diagnosis. The API's language pattern is broader than the current UI's `en`, `zh`, `de`, `hi` options; built-in fallback and some explanatory text remain English.

| Result field | Rendering rule |
| --- | --- |
| `status: partial` | Show available guidance, contacts and warnings; offer an explicit retry |
| `clinics: []` | Show no retrieved matches; do not invent nearby practices |
| `open_now: null` | “Opening hours unconfirmed”; never convert null to open or closed |
| `distance_km` | Label as straight-line distance, not driving time or ETA |
| `call_url: null` | No dial action; display the supplied phone as text if present |
| `services` / `services_to_ask_about` | Keep reported clinic data separate from suggested questions |
| `insurance.coverage` | Always display `unconfirmed` for the current live care route |
| `handoff` | Editable/reviewable facts for a later script request, not a message already sent |
| `search_url` / `maps_url` | Open only on user action |

Clinic cards are populated from the care result. There is no Pawse clinic-detail, reviews, map-tile or booking endpoint. Any future map uses the returned coordinates and retains the same source/unknown-state labels.

## 4. Progress and agent trace

Use `fetch` to consume POST SSE; native `EventSource` issues a GET and cannot submit this body. Decode incrementally, retain incomplete chunks, split complete frames at the blank line, and parse the `data:` JSON. See the exact [event table](controller-care-contract.md#3-streaming-contract).

Use `type` as the discriminator. Provider events may finish in either order. A `created` event does not mean the result is already retrievable. A connection closed before `result` is incomplete; there is no stream replay, event ID or guaranteed background completion. Do not automatically resubmit after a dropped stream because POST has no idempotency key.

`/agents/runs` returns a final JSON snapshot, not incremental trace events. Show a pending run state while awaiting it; do not animate fabricated agent completions. Trace `elapsed_ms` is an offset from run start, not the duration of an individual model call. Run completion does not unlock unconnected call, appointment or calendar actions. See the [agent contract](controller-agent-contract.md).

## 5. Voice, evidence and rehearsal handoffs

1. Record/transcribe input, then let the owner correct it before passing it to care or script generation. An empty transcript means no usable speech was recognized.
2. Review the care handoff and choose `vet`, `insurer` or `taxi` before requesting a German script. Retain paired subtitles and `draft_not_sent` status.
3. Use the own-voice recording and localization flow in the [voice contract](controller-voice-contract.md). A standard voice is an explicit selection, not an automatic replacement.
4. Read speech responses as blobs. Revoke replaced object URLs and stop microphone tracks after recording, cancellation or page exit.
5. Display policy snippets using the [knowledge contract](controller-knowledge-contract.md). The current demo corpus must not change a live owner's insurance status.
6. Keep the Mimi story's recorded steps separate from live responses. A scene's fictional 16:30 appointment is not a calendar event or confirmed reservation.

## 6. Errors and retention

The frontend must accept the existing error shapes:

| Shape | When |
| --- | --- |
| `{ "error": { "code": "validation_error", "fields": [...] } }` | 422 field validation; each field has `location` and `message` |
| `{ "detail": "..." }` | Controller/provider HTTP exceptions such as 409, 429, 502 or 503 |
| `{ "error": "cross_origin_request_rejected" }` | Middleware rejects a mutation's Origin, HTTP 403 |
| `{ "error": "request_too_large" }` | Middleware body bound, HTTP 413 |
| SSE `{ "type": "error", "code": "legacy_agent_unavailable", "message": "..." }` | Legacy failure after a stream has opened |

Treat 404 on summary retrieval as absent, expired or inaccessible. A 409 voice response means a prerequisite is missing or the action is out of sequence. A 429 means wait for the active operation; keep current input available. Care-provider errors generally arrive inside a successful HTTP response with a `partial` result.

Completed summaries share a maximum of 100 in-memory entries and a 15-minute lifetime, with expiry pruned on subsequent requests. Restart clears them. Voice IDs have a separate lifecycle: clearing a summary does not delete provider voices. See [voice retention](controller-voice-contract.md#6-deletion-and-retention).

## 7. Frontend handoff checks

- Exercise complete, partial, empty-list, no-consent, expired-result and provider-error views.
- Confirm real SSE progress and final-only agent traces are presented accurately.
- Complete record → clone → localize → preview → save → speech with mocks; record real provider verification separately.
- Check keyboard controls and narrow layouts while preserving the existing pink/gray palette in `style.css`.
- Keep transcripts and provider/model output as text; never insert them as trusted HTML.
