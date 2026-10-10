# Pawse Controller–Service Contract

This is the backend integration agreement: which controller owns each route, which existing service it calls, and what crosses that boundary. Public HTTP details belong to the [frontend contract](controller-frontend-contract.md) and domain contracts. The code paths below exist today; proposed refactoring is isolated in section 7.

## 1. Controller modules and ownership

| Logical controller | Existing implementation | Routes under `/api/v1` | Module / branch |
| --- | --- | --- | --- |
| Care | `pawse/app.py` | `/care/requests`, `/care/requests/{request_id}` | LLM/orchestration: `feat/llm-orchestrator` |
| Agent workflow | `pawse/orchestration.py` router | `/agents/graph`, `/agents/runs` | LLM/orchestration: `feat/llm-orchestrator` |
| Voice communication | `pawse/voice.py` router | `/voice/*` | Voice: `feat/voice-calling` |
| Knowledge evidence | `pawse/knowledge.py` router | `/knowledge/search` | RAG/data: `feat/rag-open-data` |
| Legacy bridge | `pawse/app.py` | `/agent/requests` | Shared integration, with legacy backend maintained separately |
| Metadata and rehearsal | `pawse/app.py`, `pawse/demo.py` router | `/health`, `/capabilities`, `/demo/mimi` | Shared integration / scenario fixtures |

Frontend consumes these contracts on `feat/frontend-experience`. Shared edits to `app.py`, models, TypeScript types and generated OpenAPI need one coordinated integration change. `providers.py` currently contains both LLM and clinic functions; split work at the function boundary until a dedicated refactor is merged.

## 2. Controller responsibilities

Controllers validate Pydantic payloads, derive the owner from `request.state.owner`, enforce operation limits, call services, serialize responses and release active-work slots in `finally` blocks. They do not accept an owner ID or provider key in care/voice request bodies.

The app middleware checks host/origin, bounds mutation bodies and establishes the local session cookie. This is a local single-user prototype. The session must not be treated as production authentication.

Use [models.py](../pawse/models.py) for shared domain models. Agent, voice and knowledge models currently live alongside their routers. Extra fields are forbidden and strings are stripped. The final service response must satisfy its public response model before being exposed.

## 3. Care and orchestration services

The signatures below describe actual call shapes and returned values, including functions whose source does not yet annotate every type.

| Controller/helper | Existing dependency | Input → output | Responsibility |
| --- | --- | --- | --- |
| `app.create_care` | `service.care_events(req)` | `CareRequest` → async iterator of event dictionaries | Initial safety/contact events; concurrent assessment and discovery; final result |
| `app.create_care` | `app.event_line(event)` | event dict → SSE frame string | `data: <JSON>\n\n`, without named events |
| `app.get_care`, `app.delete_care` | `state.records`, `state.prune()` | request ID + owner → stored result / 404 | Same-session lookup and deletion |
| `orchestration.graph` | `agent_graph()` | no input → `AgentGraph` | Roles, dependency metadata and configuration flags |
| `orchestration.create_run` | `run_workflow(req)` | `CareRequest` → awaitable `AgentRunResult` | Deadline, terminal traces, action gates and useful partial results |
| Care/run controllers | `state.remember(owner, result)` | owner + serialized `CareResult` → cache entry | Prune/evict and store under `request_id` |
| Care service | `providers.assess(req, client)` | validated request + shared `httpx.AsyncClient` → `Assessment` | Gemini text/photo care guidance |
| Care service | `providers.discover(req, client)` | validated request + client → `list[Clinic]` | Select and call the configured clinic adapter |
| Care service | `providers.rank_clinics(clinics)` | `list[Clinic]` → ranked list | Sort deterministically and set explanatory `reasons` |
| Care/run fallback | `providers.fallback_assessment(req)` | `CareRequest` → `Assessment` | Preserve owner-reported warning signs without a provider |

`care_events` does not generate a public request ID or write the result cache. The care controller adds the ID before streaming/storing the final event. `run_workflow` assigns a UUID and uses it for both `run_id` and nested care `request_id`; `create_run` stores that nested result. Direct service callers must provide their own persistence boundary.

`rank_clinics` returns a sorted list and mutates each clinic's `reasons`; do not share those mutable instances between unrelated requests.

### Execution budget and failure boundary

| Operation | Current limit / behavior |
| --- | --- |
| Care provider orchestration | 40-second internal deadline, concurrent assessment/discovery, cancel unfinished tasks |
| Agent run | 45-second outer deadline around the care workflow |
| Gemini care HTTP request | 25-second HTTP client timeout |
| Google Places request | 15-second HTTP client timeout |
| Mapify search / each place detail | 25 / 5-second HTTP client timeouts; up to ten details concurrently |
| Care and agent concurrency | Shared pool: one active request per local session, five globally |
| Completed summaries | Shared in-memory cache: 100 entries maximum, 900-second lifetime |

HTTP client timeouts are not all whole-workflow wall-clock guarantees. The 60-second product target is descriptive, not an SLA.

Adapters raise `ProviderError` with a safe public code. `care_events` converts expected failures to warnings and `unavailable` stage status; unexpected exceptions become `provider_unavailable`. The final result can be partial with one successful provider. Missing consent prevents the corresponding external call. Reported red flags cannot be downgraded by Gemini.

## 4. Provider and retrieval boundaries

| Function | Contract |
| --- | --- |
| `google_clinics(req, client)` | Nearby Search `veterinary_care` → up to 20 normalized `Clinic` records |
| `mapify_clinics(req, client)` | Generic vet query + coordinates → initial results + up to ten place-detail lookups |
| `normalize_mapify(summary, detail, origin)` | Upstream dictionaries + `Location` → `Clinic` or `None` when not recognizable as veterinary care |
| `search_knowledge(payload)` | `KnowledgeQuery` → `KnowledgeResult`; synchronous, local lexical retrieval |
| `knowledge.search(payload)` | HTTP wrapper translating missing/invalid corpus failures into safe HTTP 503 |

`discover` selects Google Places when its key exists, otherwise Mapify. It does not silently switch provider on failure. Clinic output retains nullable phone, coordinates and opening state. Mapify opening state is deliberately `null` because the inspected upstream implementation can assume open when hours are missing. See [Mapify adapter](MAPIFY_ADAPTER.md).

Gemini care receives concern, warning signs and optional photo, plus the language instruction. Clinic providers receive a generic veterinary query or category, coordinates and search radius; Mapify also receives language. Cat name, symptoms, photo and insurer details do not go to the clinic provider.

Knowledge search is callable independently; it is **not invoked inside the current agent run**. Its evidence is restricted to the synthetic demo corpus. Integrating it later must preserve scope, citations and `insurance_approval: not_obtained`; a demo search cannot satisfy the live `insurance_coverage` gate. See the [knowledge controller](controller-knowledge-contract.md).

## 5. Voice services and state

Voice route handlers and provider helpers currently share `pawse/voice.py`; there is no independent voice-service class. The [voice controller contract](controller-voice-contract.md) defines request schemas, operation ordering and responses.

| Existing helper | Input → output / behavior |
| --- | --- |
| `inspect_wav(data)` | Base64 → decoded bytes and duration; raises validation error for unsupported/incomplete WAV |
| `operation(owner)` | Async context manager; one voice operation per session, five globally, separate from care |
| `gemini_json(client, instruction, parts)` | Gemini request parts → parsed JSON; 40-second HTTP timeout; safe 502/503 on failure/configuration |
| `gradium(client, method, path, max_bytes=2000000, **kwargs)` | Authenticated server request → buffered `httpx.Response`; 45-second wall deadline, response-size bound |
| `uid(response)` | Validated Gradium JSON → provider voice ID; safe 502 if missing/invalid |
| `profile(owner)` / `require_profile(owner)` | Session voice state; the latter requires a source voice or raises 409 |
| `tts(client, voice_id, text)` | Provider synthesis → validated `audio/wav` response; response cap 30 MB |

Only voice IDs and readiness flags are retained in local voice state. Provider voices persist separately. Do not give a frontend caller arbitrary control over provider voice IDs. `GRADIUM_VOICE_ID_DE` can select a server-configured voice, and is outside session deletion.

Model settings: `GEMINI_CARE_MODEL` and `GEMINI_VOICE_MODEL` override `GEMINI_MODEL`, whose current code default is `gemini-3-flash-preview`. The coordinator and ranking use Python, and knowledge search currently uses no embedding model. Access observations are recorded in [Model allocation](MODEL_ALLOCATION.md); no credentials belong in a contract.

## 6. Legacy and demo controllers

`app.agent_request` validates `LegacyRequest`, requires a configured legacy backend/user/cat allowlist, then consumes `legacy_events(req)` under a 45-second deadline. The server supplies `LEGACY_AGENT_USER_ID`; clients cannot select another user. Old named SSE events become `{type: "legacy", event: originalName, data: originalPayload}`. A failure after opening the stream becomes a safe `legacy_agent_unavailable` event.

The existing bridge covers chat and supported analysis requests. Device ingestion, WebSocket push and storage mutation are not exposed through this contract. The imported backend's catalog does not establish live availability.

`GET /demo/mimi` returns synthetic scenario data from `pawse/demo.py`. It has no booking, insurance or call side effects. Scenario cost arithmetic is deterministic and uses the fictional policy assumptions documented in [API overview](API_CONTRACT.md).

## 7. Proposed extraction and phone integration

If routing is split later, suggested files are `pawse/controllers/care.py`, `agents.py`, `voice.py`, `knowledge.py` and `legacy.py`, with business functions retained behind those routers. **These files do not exist today.** Keep public paths and schemas unchanged during extraction; migrate one domain at a time and regenerate OpenAPI after any schema change.

Phone transport is a separate future service. Before adding callable routes, agree on recipient/purpose approval, verified destination number, provider call ID, event IDs for deduplication, transcript language, AI disclosure and explicit completed/failed/cancelled outcomes. A call ending is not sufficient evidence that a slot, coverage or taxi was confirmed. No phone endpoint or event schema is promised by the current API.

## 8. Handoff validation

For implementation changes, use the relevant existing suite: `tests/test_care.py`, `tests/test_orchestration.py`, `tests/test_voice.py` or `tests/test_knowledge.py`. Validate request/response examples against Pydantic and re-export OpenAPI. Include failure and cancellation behavior in handoffs; separate mocked contract checks from live provider verification. See [Agent development](AGENT_DEVELOPMENT.md) for module integration order.
