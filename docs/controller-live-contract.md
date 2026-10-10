# Pawse Live Controller Contract

**Current backend.** Implementation: [pawse/live.py](../pawse/live.py). Prefix: `/api/v1/live`. This controller supports the Voice Agent and Gemini Live tool routing in the [multimodal design](MULTIMODAL_CONTRACTS.md). Browser microphone capture/playback is still pending; [Gemini Live](GEMINI_LIVE.md) describes that transport work and the recorded server-session check.

## 1. Create a constrained session

`POST /tokens` → **201** `TokenResult`. Request: `TokenRequest`.

<!-- schema: TokenRequest -->
```json
{
  "language": "zh",
  "share_with_gemini": true
}
```

| Field | Contract |
| --- | --- |
| `language` | `en`, `zh`, `de` or `hi`; default `en`; initial conversation language |
| `share_with_gemini` | Required literal `true`; omission/false returns 422 |

The response contains `token`, `model`, `api_version: v1alpha`, `expires_at`, `new_session_expires_at` and `tools: string[]`. Treat the returned token as a secret: keep it in memory, never log it, include it in analytics or publish it in examples. Permanent credentials remain on the server.

The server requests a single-use token with a 60-second start window and 30-minute expiry. It locks model, instruction, AUDIO output, input/output transcription and tool declarations. `GEMINI_LIVE_MODEL` defaults to `gemini-3.8-live`; the client uses the returned model. This assistant voice is separate from the Gradium owner voice.

| Failure | HTTP | Behavior |
| --- | --- | --- |
| Missing Gemini key | 503 | Show setup unavailable; typed input remains usable |
| Provider request or token parsing failure | 502 | Safe message; offer an explicit retry or recorded input |
| More than ten mint attempts in ten minutes for this session | 429 | Wait; do not loop token requests |
| Invalid body or consent | 422 | Correct input before retrying |

The ten-attempt limit is Pawse's local session limit; Gemini project quotas are separate. Failed provider mint attempts also consume a local attempt. The browser session cookie is local isolation, not production authentication.

## 2. Execute a tool request

`POST /tool-calls` → **200** `ToolResult`. Request: `ToolCall`.

<!-- schema: ToolCall -->
```json
{
  "id": "demo-function-1",
  "name": "assess_and_find_vets",
  "args": {
    "concern": "Mimi is limping after jumping off a wardrobe.",
    "warning_signs": []
  },
  "context": {
    "language": "hi",
    "cat_name": "Mimi",
    "location": {"lat": 47.3769, "lng": 8.5417},
    "share_location": true
  },
  "share_with_gemini": true
}
```

`id` is optional, at most 200 characters, and correlates the provider function call. It is **not an idempotency key**. `context` defaults to English, `My cat`, no location and no location sharing. Its language accepts the same four codes; cat name is 1–80 characters. The app supplies context from owner choices, not from model-generated arguments. Only send coordinates when location sharing is enabled.

| Tool name | Validated `args` | Backend service | `ui` on success |
| --- | --- | --- | --- |
| `assess_and_find_vets` | `concern`: 1–4,000 characters; `warning_signs`: up to six [reported red flags](controller-care-contract.md) | `run_workflow(CareRequest)`; stores nested care result and session's latest clinic list | `{care: CareResult, trace: AgentTrace[]}` |
| `search_policy` | `question`: 1–1,000 characters | `search_knowledge(KnowledgeQuery)`; fixed demo corpus | `KnowledgeResult` |
| `draft_vet_call_script` | `message`: 1–4,000 characters; `recipient`: `vet`, `insurer` or `taxi`, default `vet` | `draft_script`; German output and subtitles in `context.language` | `CallScript` |
| `open_clinic_call` | `clinic_id`: 1–300 characters, from this session's latest Live care search | Server lookup; no phone transport | `{action: "confirm_call", clinic_name, phone, call_url}` |

Unknown arguments are rejected by each tool's model. These are direct service calls, not HTTP requests to the corresponding public routes. Their current wrappers use the Live concurrency limit: three active tools per session and fifteen globally. A Live care call still observes the bounded workflow deadline.

The response envelope is `{id, name, response, ui}`. Return only `{id, name, response}` in the Gemini function response; render `ui` in the app. Do not send the entire care/evidence UI object back to the model by default.

| `response` boundary | Meaning |
| --- | --- |
| Care summary | Urgency, summary, questions, up to three clinic summaries, search status and disclaimer; no claim of diagnosis |
| Policy result | Demo excerpts and `insurance_approval: not_obtained`; not a private-policy answer |
| Script result | `status: draft_not_sent`, line count and note; full paired lines stay in `ui` |
| Dialer result | `status: awaiting_owner_confirmation`; the browser must ask before opening `ui.call_url` |

Changing `context.language` changes the subtitle language used by this tool. Independent input/subtitle selection is already supported by `/voice/scripts`; the Live tool has one shared language field today.

## 3. Failure and interaction contract

- Unknown tool name, invalid top-level context or missing Gemini consent returns HTTP 422. Active-tool limits return 429.
- Bad tool arguments return HTTP 200 with `response.error: invalid_arguments` and `ui: null`.
- Handled service/provider failures return HTTP 200 with `response.error: tool_unavailable`; a safe `detail` may be present.
- A missing clinic in the latest search returns `unknown_clinic`; a clinic without a usable dial URL returns `no_phone_number`. Neither result allows a dial action.
- Care can succeed with a partial result. Render available guidance and preserve unknown clinic availability.

The browser must inspect both HTTP status and `response.error`, and send handled tool failures back to Gemini so it can explain the missing result. Do not silently replay a tool after connection loss: the server currently has no duplicate-call suppression or cancellation endpoint. Avoid dispatching the same function-call ID twice within one browser session.

Non-blocking tools can finish out of order. Track pending work by function-call ID; do not attach a delayed result to a different displayed concern. Case revision enforcement is [proposed](controller-case-contract.md), not present in this controller. Interrupting speech playback alone does not cancel a backend tool call.

## 4. Owner review and retention

`open_clinic_call` can only prepare the manual dialer action. A frontend confirmation may open the returned `tel:` URI; it does not establish that a call connected or that Pawse spoke. Actual German speech generation uses the separate [Voice contract](controller-voice-contract.md); automated call execution follows the proposed [Action contract](controller-action-contract.md).

Mint counters, active-call counts and the latest clinic list are process-local. At most 100 session clinic lists are retained; a new search replaces that session's list. Care summaries use the existing bounded result cache. There is no persistent Live conversation or call history. Disconnecting the browser does not revoke or delete a saved Gradium voice.

## 5. Handoff acceptance

Backend checks cover consent, token constraints, argument validation, tool-error envelopes, clinic lookup and concurrency in `tests/test_live.py`. Frontend acceptance must additionally cover all four starting languages, microphone denial, reconnect failure, interrupted playback, simultaneous tools, draft subtitles and confirm-before-dialing. Record real microphone/speaker validation separately from the existing server-session check.
