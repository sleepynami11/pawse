# Pawse engineering docs

Start here to integrate the existing Pawse app. The contracts describe the current implementation; sections marked **Proposed** describe work that has no callable endpoint yet. All public API paths start with `/api/v1`.

## Product and system

| Document | Purpose |
| --- | --- |
| [Product scope](SPEC.md) | Zurich care journey, implemented features and remaining integrations |
| [Mimi: the 120-second story](DEMO_STORY.md) | Complete scenario, four-language experience, demo cost maths, agent handoffs and acceptance checklist |
| [Multilingual voice concierge](VOICE_CONCIERGE.md) | EN/ZH/DE/HI input and subtitles, German own-voice audio, enrollment and future phone calls |
| [Architecture](ARCHITECTURE.md) | Runtime agents, dependencies and execution boundaries |
| [Multimodal design](MULTIMODAL_ARCHITECTURE.md) | Voice, Vision and Document agents, proposed document handoffs and module assignments |
| [Architecture diagram](images/README.md) | English diagram, full-resolution PNG, editable SVG and arrow legend |
| [Agent development](AGENT_DEVELOPMENT.md) | Module responsibilities, feature branches and handoff checks |
| [Model allocation](MODEL_ALLOCATION.md) | Event model menu, Gemini 3.8 checks, Gradium and optional background models |
| [Validation record](VALIDATION.md) | Automated checks and limits of live verification |

## Controller and integration contracts

| Document | Producer → consumer | Read this for |
| --- | --- | --- |
| [Multimodal contract map](MULTIMODAL_CONTRACTS.md) | All modules | Diagram-to-controller mapping, current/proposed routes, ownership and integration order |
| [Controller–Frontend](controller-frontend-contract.md) | HTTP controllers → web app | Screen-to-endpoint mapping, journey layout, pink/gray palette, consent and errors |
| [Controller–Service](controller-service-contract.md) | Controllers → Python services/adapters | Function boundaries, routing ownership, deadlines and data handoffs |
| [Care controller](controller-care-contract.md) | Care navigation → frontend/coordinator | Request/result schemas, nearby clinics, SSE and result retention |
| [Agent controller](controller-agent-contract.md) | Runtime coordinator → frontend | Graph metadata, run requests, traces and action gates |
| [Live controller](controller-live-contract.md) | Voice session → validated backend tools | Current token, function-call, UI-result and error contracts |
| [Vision controller](controller-vision-contract.md) | Photo/video intake → care context | Current photo limits; proposed timestamped observations and evidence |
| [Document controller](controller-document-contract.md) | Private documents → reviewed evidence | Proposed uploads, extraction, page citations, review and deletion |
| [Case and agent handoffs](controller-case-contract.md) | Modality agents → coordinator | Proposed facts, revisions, conflicts, language context and result merging |
| [Communication and actions](controller-action-contract.md) | Reviewed draft → future connectors | Current audio/dialer boundary; proposed approvals, execution and provider receipts |
| [Voice controller](controller-voice-contract.md) | Voice pipeline → frontend/coordinator | Transcription, German scripts, own-voice lifecycle and WAV output |
| [Knowledge controller](controller-knowledge-contract.md) | Retrieval/data → frontend/coordinator | Evidence search, clinic-data boundary and demo isolation |
| [API overview](API_CONTRACT.md) | All modules | Complete route inventory and shared conventions |
| [OpenAPI](openapi.json) | Pydantic/FastAPI → API clients | Generated request/response schemas |

These are documentation boundaries. Care and legacy routes currently live in `pawse/app.py`; agent, Live, voice and knowledge routes already use routers in their corresponding modules. The document names do not imply that new controller classes or services have been implemented. Case, document and action routes are proposed, and intentionally absent from generated OpenAPI.

## Provider and data references

- [Voice concierge](VOICE_CONCIERGE.md): provider lifecycle, recording and verification.
- [Gemini Live](GEMINI_LIVE.md): live voice session, token and tool-call contract, browser client to-do.
- [RAG evidence contract](RAG_CONTRACT.md): citation semantics and retrieval acceptance cases.
- [Mapify adapter](MAPIFY_ADAPTER.md): actual upstream differences and clinic normalization.
- [Data sources](DATA_SOURCES.md): open data, licensed providers and private documents.
- [Gemini integration](GEMINI_INTEGRATION.md): configuration and model migration.
- [Existing capabilities](CAPABILITIES.md): imported CatAgent tools and reports.
- [Import review](IMPORT_REVIEW.md) and [hackathon notes](HACKATHON.md): provenance and project context.

## Contract maintenance

Check implementation and [OpenAPI](openapi.json) together: streaming events, dynamic voice-status dictionaries and some error responses need the written contracts because they are not fully typed in OpenAPI. TypeScript helpers in [schemas/pawse.ts](../schemas/pawse.ts) assist the frontend but do not replace server validation.

When changing an interface, update its controller contract and consumers, then run `python scripts/export_contract.py` to regenerate OpenAPI. Keep example payloads synthetic and valid. Coordinate shared schemas and route changes through the integration module described in [Agent development](AGENT_DEVELOPMENT.md).

Current paths, schemas and behavior are derived from Pawse's code. Proposed interfaces are implementation agreements to review and test before enabling their UI.
