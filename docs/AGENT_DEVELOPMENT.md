# Agent development

Development follows the product modules: frontend experience, orchestration, voice communication and evidence retrieval. Each module has a feature branch, an API boundary and a validation target. The runtime workflow is described in [ARCHITECTURE.md](ARCHITECTURE.md).

Start integration work with [Controller–Frontend](controller-frontend-contract.md) and [Controller–Service](controller-service-contract.md). Detailed contracts are grouped by [Care](controller-care-contract.md), [Agents](controller-agent-contract.md), [Voice](controller-voice-contract.md) and [Knowledge/Data](controller-knowledge-contract.md). The [docs index](README.md) links the supporting provider and data references.

## Modules and branches

| Module | Branch | Source files | Deliverable | Validation |
| --- | --- | --- | --- | --- |
| Frontend | `feat/frontend-experience` | `pawse/static/` | Mapify-inspired pink/gray UI; multilingual input, own-voice recording, agent progress, clinic cards and the Mimi rehearsal | Complete the story with keyboard or touch; show partial/error states; clearly distinguish simulated calls from live audio and API results. |
| LLM/orchestration backend | `feat/llm-orchestrator` | `pawse/orchestration.py`, `pawse/service.py`, `pawse/state.py`, assessment logic in `pawse/providers.py`, `pawse/demo.py`, orchestration tests | A bounded agent run, care guidance, explainable ranking, action gates and deterministic scenario costs | Independent providers start concurrently; urgent guidance survives provider failure; no invented booking, policy decision or deadline guarantee. |
| Multimodal/voice/phone backend | `feat/voice-calling` | `pawse/voice.py`, voice tests, future telephony module | Record the owner's voice, clone/localize it, preview German audio, and translate input with paired subtitles | Validate consent and audio bounds; preview before sharing; stop microphone tracks; handle missing Gradium credentials; label all current calls as simulated/unconnected. |
| RAG/open-data backend | `feat/rag-open-data` | `pawse/knowledge.py`, retrieval tests, `research/`, clinic-adapter functions in `pawse/providers.py` | Cited policy search and a documented Zurich clinic-data adapter | Keep demo policy evidence separate from live cases; return source/version and relevant clauses; preserve unknown hours/services; document dataset reuse conditions. |

Feature branches start from a shared reviewed baseline. Integrate changes through the common API contract and validate dependent modules before merging.

Shared integration files include `pawse/app.py`, request/response models, `schemas/pawse.ts`, generated `docs/openapi.json`, dependency files and the root README. Coordinate these changes through the orchestration branch. Regenerate OpenAPI after changing a contract and check its consumers; avoid concurrent manual edits to the generated schema.

`pawse/providers.py` currently combines care guidance and clinic adapters. Coordinate function-level edits until it is split: orchestration covers `assess` and `rank_clinics`; retrieval covers `google_clinics`, `mapify_clinics`, `normalize_mapify` and `discover`. Make the module split a separate agreed change, not parallel refactoring. Keep the imported legacy `backend/` stable unless an integration specifically needs it.

## Models that this project can access

The checks below ran on **2026-10-10** with synthetic inputs and this development project's credential. Full sanitized results are in [model-access-check.json](model-access-check.json). A successful request proves access to that API operation; it does not establish clinical reliability, speech recognition quality, latency under load or production suitability.

| Component | Model/tool | Check result | Assignment |
| --- | --- | --- | --- |
| Care guidance and image intake | `gemini-3-flash-preview` | Text and synthetic image requests returned HTTP 200 with usable responses | Default fast model for care guidance. |
| Audio transcription and German script/subtitle drafting | `gemini-3-flash-preview` | A one-second silent WAV was accepted with HTTP 200; real language accuracy remains unmeasured | Voice pipeline; evaluate actual English, Chinese, German and Hindi recordings. |
| Optional complex review | `gemini-3.1-pro-preview` | Text request returned HTTP 200 with a usable response | Evaluate for difficult reasoning; no automatic second-model review is wired into the current graph. |
| Future vector retrieval | `gemini-embedding-001` | `embedContent` returned HTTP 200 with an embedding | Retrieval pipeline; the current small demo corpus can use deterministic lexical retrieval without a vector database. |
| Older Flash choice | `gemini-2.5-flash` | Generation returned HTTP 404 despite appearing in the listing | Do not use it as the current default; listing a model is not the same as being able to invoke it. |
| Own-voice cloning and German output | Gradium voice APIs | Adapter implemented; no configured Gradium credential at this check | Validate the voice pipeline with a consented sample and preview. No live cloning or voice-similarity result is claimed. |
| Coordination, ranking and cost arithmetic | Python rules and asynchronous tasks | Covered by local tests | Orchestration rules; these roles do not need a separate generative model. |

`GEMINI_MODEL` supplies the shared default. `GEMINI_CARE_MODEL` and `GEMINI_VOICE_MODEL` can override their respective routes. Keep credentials only in the ignored local `.env`; configure each development environment separately.

If the existing CatAgent vector store was created with an OpenAI embedding model, switching to Gemini embeddings requires a fresh index. Embeddings from different model spaces cannot be mixed or substituted just by changing the API key. Preserve document identifiers and source citations during reindexing.

## Module Interfaces

| Producer → consumer | Contract | Boundary |
| --- | --- | --- |
| Frontend → care/orchestrator | `CareRequest`, `/api/v1/care/requests`, `/api/v1/agents/runs` | Text/photo facts and separate AI/location consent. The agent run body is `{ "care": CareRequest }`. |
| Orchestrator → frontend | `CareResult`, `AgentRunResult`, `/api/v1/agents/graph` | Provider-backed clinics, safe partial result, per-agent state and unresolved action requirements. |
| Frontend → voice | `/api/v1/voice/transcriptions`, `/voice/scripts`, `/voice/clone`, localization/preview/audio endpoints | Own-voice consent and provider-sharing consent are separate; generated scripts are drafts. |
| RAG/data → frontend or future coordinator | `/api/v1/knowledge/search` | Cited synthetic corpus results; not actual policy approval. Live policy ingestion is later work. |
| Clinic adapter → ranking | `Clinic[]` | Source, retrieval time, phone, coordinates and nullable `open_now`; never manufacture travel time or specialties. |
| Future phone adapter → coordinator | Proposed call events with recipient, transcript, provider status and owner approval reference | Design after choosing a telephone transport. Do not represent generated audio as a completed call. |

Use the exported [OpenAPI contract](openapi.json) as the route/schema authority. The legacy agent bridge has a separate configured-user contract and external runtime dependencies; its catalog is not proof all legacy tools are running.

## Integration Workflow

1. Merge the shared baseline: request schemas, agent trace/action states, evidence scope and the synthetic story. Publish the generated OpenAPI contract.
2. Develop backend modules against those contracts in parallel. Keep provider adapters independently testable and use mocks for missing credentials. Frontend develops against recorded synthetic responses with prominent demo labels.
3. Merge RAG/data and orchestration changes, including the clinic adapter boundary; verify policy citations and provider failure paths together.
4. Merge voice changes and validate a real owner-provided recording once Gradium is configured. Only then claim a successful clone or German localization.
5. Merge the frontend integration, run the full test suite once, and rehearse the two-minute Mimi story. Every simulated vet/insurer/taxi reply must remain visibly simulated. A real call transport and calendar connector are separate acceptance milestones.

For the hackathon demonstration, a useful first finish is multilingual intake → care navigation and nearby search → cited demo-policy explanation → reviewed German script in the owner's voice → explicit owner choice and claim checklist. Rehearsal can demonstrate the complete story while availability labels show which providers are genuinely connected.

## Development Agents

Use the tasks below to run focused development agents. Each task targets its module branch and source files; coordinate shared contract changes through the orchestration module.

| Coding agent | Task | Required evidence before handoff |
| --- | --- | --- |
| Frontend agent | Consume existing APIs, present seven role states, complete the multilingual own-voice and Mimi flows, preserve the Mapify palette. | Browser walkthrough at desktop and narrow widths; accessible controls; screenshot; documented simulated states. |
| LLM coordinator agent | Maintain bounded care runs, trace statuses, partial failures, emergency-first rules, ranking and deterministic costs. | Tests proving concurrent retrieval and assessment, cancellation, unknown-field preservation and no external-action success without evidence. |
| Voice agent | Finish recording/clone/localization/playback, multilingual scripts and a separately designed phone adapter. | Consent/validation tests; live Gradium preview when configured; explicit report of which languages and transport paths were actually checked. |
| RAG/data agent | Retrieve policy clauses with source references, define reusable Zurich data sources, and normalize clinic evidence. | Citation tests, out-of-scope rejection, document/version metadata, source/license notes, and no synthetic-to-live policy leakage. |

Development agents work on source modules. Runtime agents execute the product workflow. Model selection follows the requirements of each operation; deterministic steps do not require a generative model.
