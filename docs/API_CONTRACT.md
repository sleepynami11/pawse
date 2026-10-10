# Pawse frontend / backend contract v0.2

Base URL: `/api/v1`. The executable schema is [openapi.json](openapi.json); the running app also serves `/openapi.json` and `/docs`. This overview describes the implemented Pawse HTTP API.

For integration work, use the [docs index](README.md), [Controller–Frontend](controller-frontend-contract.md) and [Controller–Service](controller-service-contract.md) agreements. Domain contracts cover [Care](controller-care-contract.md), [Agents](controller-agent-contract.md), [Live](controller-live-contract.md), [Voice](controller-voice-contract.md) and [Knowledge/Data](controller-knowledge-contract.md), with request examples, lifecycle rules and handoff responsibilities. The [Multimodal contract map](MULTIMODAL_CONTRACTS.md) additionally defines proposed Vision, Document, Case and Action interfaces. Proposed routes are not included in this inventory or generated OpenAPI.

## Runtime and session boundaries

The default app is a **local single-user prototype**, bound to `127.0.0.1`. A public demo mode now exists through `PAWSE_PUBLIC_DEMO=1` and the Cloud Run/container setup. Host checking accepts localhost/test hosts plus `PAWSE_ALLOWED_HOSTS`, read at startup. A random HttpOnly, SameSite=Strict browser cookie isolates result retrieval between sessions and is Secure on HTTPS. It is not a login system; public demo mode does not provide authenticated private-document storage or production multi-user authorization.

Public mode caps selected POST requests at 60 per session and 600 per process per rolling hour by default. Limits are configurable with `PAWSE_SESSION_CALLS_PER_HOUR` and `PAWSE_TOTAL_CALLS_PER_HOUR`. Covered prefixes are `/care/requests`, `/clinics/`, `/agents/runs`, `/voice/`, `/live/` and `/knowledge/search`; rejected validation/provider requests also consume an admitted attempt. Knowledge search is local but is currently included. The quota counts HTTP requests, not tokens, audio duration or provider spend; a Live token's subsequent provider audio stream is outside this HTTP counter. State resets on restart and is not shared across workers/instances.

Exhaustion returns HTTP 429 with `error: demo_quota_reached`, plus identical human-readable `detail` and `message` fields. Existing frontend helpers read `detail`; the keyless Mimi rehearsal and GET routes remain available. Quota errors retain the normal session cookie and no-store headers. This is separate from the active-work limits of care, Live and voice. See [team integration status](TEAM_INTEGRATION.md) for deployment and pending frontend/testing work.

Mutation request bodies are bounded at 4.5 MB by both declared Content-Length and actual streamed bytes. Photos and WAV audio are each limited to 3 MB decoded. Validation errors omit submitted payloads. Responses use `Cache-Control: no-store`; no wildcard CORS is enabled.

## Routes

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Local app health; does not assert upstream readiness |
| GET | `/capabilities` | New feature configuration plus 25 legacy intents, 14 tools and 10 report types |
| POST | `/care/requests` | JSON result, HTTP 201; use `?stream=true` for SSE, HTTP 200 |
| GET | `/care/requests/{id}` | Completed result for the same browser session; HTTP 404 if absent/expired/other session |
| DELETE | `/care/requests/{id}` | Remove a completed result, HTTP 204 |
| POST | `/clinics/search` | Nearby clinics only (`ClinicSearchRequest`: `location`, `share_location: true`, optional `radius_km`, `language`); `ClinicSearchResult`, HTTP 200. Only coordinates leave the server. Not blocked by an active care request; at most 2 lookups per session and 10 per process at once (HTTP 429), HTTP 400 without location consent. |
| POST | `/agent/requests` | SSE bridge to configured existing CatAgent |
| GET | `/agents/graph` | Seven runtime roles, model/tool types, owners, dependencies and configuration state |
| POST | `/agents/runs` | HTTP 201; nested `care` request → care result, agent trace and action gates |
| POST | `/knowledge/search` | Cited lexical search of the fixed synthetic insurance corpus |
| POST | `/live/tokens` | HTTP 201; consented → single-use Gemini Live token locked to model, prompt and tools ([Gemini Live](GEMINI_LIVE.md)) |
| POST | `/live/tool-calls` | Run a Gemini Live tool call server-side → `response` for Gemini plus `ui` data |
| GET | `/voice/status` | Current session's voice readiness and configuration booleans |
| POST | `/voice/transcriptions` | Consented WAV → Gemini transcript |
| POST | `/voice/scripts` | Consented message → German script and paired subtitles |
| POST | `/voice/clone` | HTTP 201; consented own-voice sample → Gradium voice ID |
| POST | `/voice/localizations` | HTTP 202; start German voice candidate generation |
| GET | `/voice/localizations/current` | Read current candidate readiness |
| POST | `/voice/preview` | German WAV preview of a ready voice/candidate |
| POST | `/voice/localizations/current/save` | HTTP 201; save a candidate after preview and owner acknowledgement |
| POST | `/voice/speech` | Reviewed German text → WAV bytes with AI-assistant disclosure |
| DELETE | `/voice/profile` | HTTP 204; delete provider voices/candidates created by this session |
| GET | `/demo/mimi` | Synthetic six-scene story, German/English dialogue, costs and claim checklist |

There is no separate GET search-stream endpoint. Use fetch streaming on the POST response. Polling only works after a result has completed, and a dropped stream is not guaranteed to finish in the background.

## Create a care request

```json
{
  "query": "My cat has been eating less since yesterday. What should I tell the vet?",
  "cat_name": "Mochi",
  "location": {"lat": 47.3769, "lng": 8.5417},
  "radius_km": 10,
  "language": "en",
  "red_flags": [],
  "photo": null,
  "insurance": null,
  "share_with_ai": true,
  "share_location": true
}
```

- `location` is optional. The interface starts at Zurich city centre and lets the user edit it or request geolocation.
- `red_flags`: `breathing_difficulty`, `collapse`, `seizure`, `unable_to_urinate`, `suspected_poisoning`, `major_trauma`. A reported flag always makes the final urgency `emergency`; Gemini cannot downgrade it.
- `photo`: `{ "mime_type": "image/jpeg", "data": "<base64>" }`. JPEG, PNG and WebP only; maximum 3 MB decoded. No arbitrary image URL fetching.
- `insurance`: `{ "company": "Your insurer", "phone": "+41 ..." }`. Use a real international-format number from the policy; the app validates format, not ownership. No policy number, coverage decision or claim submission is requested.
- `share_with_ai` permits transmitting the concern, flags and photo to Gemini. Name, location and insurance are omitted from that provider request.
- `share_location` permits transmitting coordinates and a generic veterinary search query to the configured clinic service. Symptoms, photo and insurance are not sent to MapifyAI or Places.
- Empty input without a photo or warning sign returns HTTP 422.

## Result semantics

A `CareResult` contains:

| Field | Meaning |
| --- | --- |
| `request_id` | Opaque identifier; do not log/share care links publicly |
| `status` | `complete` when both providers finish; `partial` otherwise. An empty clinic list can still be a completed search. |
| `assessment` | `urgency`, `summary`, follow-up questions, services to ask about, `source` and disclaimer |
| `clinics` | Provider-derived clinics; may be empty. Not an exhaustive directory. |
| `insurance` | User-provided contact with a validated `tel:` URI; coverage always `unconfirmed` |
| `handoff` | Owner concern and care-navigation summary for the vet call |
| `providers` | Per-stage `complete`, `unavailable` or `timeout` |
| `warnings` | Safe codes for missing configuration, consent, provider errors or deadline |
| `elapsed_ms` | Actual elapsed orchestration time |
| `target_seconds` | 60-second product target, not a guarantee |
| `search_url` | Google Maps search link, opened only by user action |

Urgency is `emergency`, `contact_vet` or `unknown`. The app never returns a diagnosis or a claim that a photo rules out illness. The initial safety response is deterministic; provider failure does not suppress it.

Clinic records include `id`, `name`, `address`, `phone`, `call_url`, `maps_url`, `website`, coordinates, straight-line `distance_km`, rating, nullable `open_now`, services, reasons, source and retrieval time. `open_now=null` means unknown. `emergency_service=unknown` is the default: generic veterinary listings do not prove emergency capability. Services suggested by AI are questions for the clinic, not claims about what it offers.

Ranking is deterministic: provider-reported open clinics, then unknown, then reported closed; nearest first within each group, rating as a tie-breaker. AI helps organize concerns and questions; it does not fabricate provider facts or diagnose. Travel times, booking slots and insurer acceptance are not implemented.

## Agent graph and runs

`GET /agents/graph` describes seven roles: intake, care guidance, nearby vets, policy evidence, ranking, communication and orchestration. It distinguishes model calls, tools and deterministic code. Configuration flags do not prove a live provider was checked; see [model allocation](MODEL_ALLOCATION.md) and the sanitized access report.

`POST /agents/runs` accepts an `AgentRunRequest` containing the `care` object. It reuses the existing concurrent care providers and adds a 45-second outer deadline. The final JSON response contains `run_id`, `mode: bounded_workflow`, `status`, the complete nested `CareResult`, `trace`, `actions`, `external_actions_performed: false` and `note`. See the [agent controller contract](controller-agent-contract.md) for a valid request example and field/state tables. This endpoint does not stream.

Trace `elapsed_ms` records the offset from run start when the role was last updated, not that agent's individual duration.

`trace.state` is `pending`, `running`, `complete`, `unavailable`, `timeout`, `skipped`, `review_required` or `evidence_required`. The finished response contains terminal states. A complete care run does not mean every future action is available: live policy evidence remains required, communication requires owner review, and calls/calendar/bookings are unconnected.

The nested care result is stored in the same session cache as `/care/requests`, under its `request_id`; use the existing GET/DELETE routes for it. The trace itself has no history endpoint. Care and agent-run requests share the concurrency limit. See [architecture](ARCHITECTURE.md) and [module development](AGENT_DEVELOPMENT.md).

## Voice and multilingual contracts

Text and transcription language codes are `en`, `zh`, `de` and `hi`. Hindi does not imply support for all Indian languages. The current output language is `de`; Gemini produces translations and paired subtitles, while Gradium provides German speech.

- Transcription: `{ "audio": { "data": "<base64 WAV>" }, "language": "zh", "share_with_gemini": true }` → `{ "text": "..." }`.
- Script: `{ "message": "...", "input_language": "en", "subtitle_language": "en", "target_language": "de", "recipient": "vet", "share_with_gemini": true }` → `lines` with `german`/`subtitle` pairs and `status: "draft_not_sent"`. Recipient is `vet`, `insurer` or `taxi`.
- Clone: `{ "audio": { "data": "<base64 WAV>" }, "sample_language": "en", "own_voice_consent": true, "share_with_gradium": true }`. The sample language must be one of Gradium's `en`, `de`, `fr`, `es`, `pt` languages; no Chinese/Hindi clone sample is claimed.
- Localization and preview: `{ "share_with_gradium": true }`. Saving additionally requires `listened_to_preview: true` and a server-observed ready candidate and preview request.
- Speech: `{ "text": "...", "language": "de", "voice": "my_voice", "share_with_gradium": true }` → `audio/wav`. `standard` is an explicit voice choice; it is never a silent fallback for a missing owner voice.

Audio must be complete mono 16-bit PCM WAV, 8–48 kHz, 0.5–60 seconds, up to 3 MB decoded. Cloning requires 10–30 seconds. Browser recording is converted locally before upload. Gemini operations use a 40-second request timeout; Gradium operations use 45 seconds. Voice work has its own limit of one active operation per session and five globally.

The server adds an AI-assistant disclosure to generated speech. There is no telephone transport, remote-recipient audio stream or OS phone-call audio injection in these routes. The [voice concierge guide](VOICE_CONCIERGE.md) documents the provider lifecycle, full flow and remaining live verification.

## Evidence search and Mimi rehearsal

`POST /knowledge/search` accepts `{ "query": "home visit surcharge 1.2.5", "top_k": 3, "scope": "synthetic_demo" }`. `top_k` is 1–5. It performs local English lexical retrieval over the reviewed demo policy and English AVB, without an embedding call or owner-document upload.

The result carries `synthetic: true`, `method: "lexical"`, `insurance_approval: "not_obtained"`, a corpus version, `evidence_found`/`no_evidence` status and evidence entries with source path/hash, clause or JSON section, exact snippet and relevance score. The score is not coverage confidence. No request may choose an arbitrary file, collection or live-policy scope. See the [RAG contract](RAG_CONTRACT.md).

`GET /demo/mimi` supplies the six-scene rehearsal and explicit synthetic notice. CHF 385 clinic and CHF 510 home-visit costs assume CHF 600 eligible treatment, an unused CHF 300 deductible, 80% reimbursement after that deductible, unused annual limit, CHF 25 owner-paid taxi and an excluded CHF 150 home surcharge. Real policy terms and clinic costs are not inferred from this example. All recipient replies, calendar slots and arrangements in the story remain simulated.

## SSE wire format

Each event is `data: <JSON>\n\n`, without an `event:` field:

```text
data: {"type":"created","request_id":"..."}

data: {"type":"safety","assessment":{"...":"..."}}

data: {"type":"insurance","insurance":null}

data: {"type":"progress","agent":"clinics","status":"starting"}

data: {"type":"clinics","clinics":[]}

data: {"type":"progress","agent":"clinics","status":"complete"}

data: {"type":"result","request_id":"...","status":"partial","...":"..."}

```

`assessment`, `clinics`, `progress`, and `heartbeat` can interleave. Treat the final `result` as authoritative. The application runs assessment and discovery concurrently and cancels remaining work at a 40-second internal deadline, leaving room within the one-minute interaction target. Insurance contact and initial safety guidance are sent before these providers complete.

## Existing Agent bridge

Chat:

```json
{"mode":"chat","cat_id":1,"message":"Summarize my cat's recent activity","analysis_type":null,"time_range":"24h"}
```

Analysis:

```json
{"mode":"analysis","cat_id":1,"message":"","analysis_type":"daily_summary","time_range":"24h"}
```

`analysis_type` supports all ten existing factory values: `daily_summary`, `weekly_report`, `monthly_report`, `health_prediction`, `trend_analysis`, `behavior_pattern`, `vet_recommendation`, `comparison`, `multi_cat_comparison`, `anomaly_detection`.

The server selects `LEGACY_AGENT_USER_ID`; the client cannot choose another user. `cat_id` must be in the server's `LEGACY_AGENT_CAT_IDS` allowlist. This is a local development boundary, not production identity management.

Chat is translated into legacy `POST /chat`, then `GET /chat/stream/{stream_id}`. Analysis calls legacy `POST /analyze/{user_id}`. Both old named SSE events and data-only events are wrapped as:

```json
{"type":"legacy","event":"result","data":{"...":"legacy payload"}}
```

The gateway does not duplicate clinical, device or report logic. Old WebSocket push, device webhooks, video ingestion and direct storage mutation are not exposed by this new UI. They remain in the existing source for later authenticated integration.

## Failure and retention

- 403: cross-origin mutation or disallowed legacy cat.
- 404: completed care result missing/expired or belongs to another session.
- 409: a voice action is out of sequence, such as saving before preview or requesting an absent own voice.
- 413: declared or actual request body too large.
- 422: invalid request (sanitized field messages).
- 429: same session already has active care/agent work, five global care runs are active, or the separate voice-operation limit is reached.
- 502: voice provider returned an error or an unusable result; messages omit raw provider responses.
- 503: required voice/legacy configuration or the synthetic evidence corpus is unavailable.
- Care provider failures return useful `partial` results, not fabricated replacements.
- Legacy SSE failures return `{"type":"error","code":"legacy_agent_unavailable",...}`.

Pawse keeps at most 100 completed care summaries from care or agent runs in process memory for 15 minutes, pruning expired entries on subsequent requests. No photos or audio recordings are written to disk or stored in these results. Process restart clears the cache.

Voice IDs are held separately in session memory. Gradium-created voices persist in the provider account; restarting Pawse or losing a session does not delete them. Session deletion removes only voices/candidates created in that session, preserving failed deletions for retry. A voice configured through `GRADIUM_VOICE_ID_DE` is not deleted by that action. Provider retention is governed separately by those services; see [voice lifecycle details](VOICE_CONCIERGE.md).
