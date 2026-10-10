# Pawse engineering docs

Start here to integrate the existing Pawse app. The contracts describe the current implementation; sections marked **Proposed** describe work that has no callable endpoint yet. All public API paths start with `/api/v1`.

## Product and system

| Document | Purpose |
| --- | --- |
| [Product scope](SPEC.md) | Zurich care journey, implemented features and remaining integrations |
| [Architecture](ARCHITECTURE.md) | Runtime agents, dependencies and execution boundaries |
| [Agent development](AGENT_DEVELOPMENT.md) | Module responsibilities, feature branches and handoff checks |
| [Model allocation](MODEL_ALLOCATION.md) | Which operations use Gemini, Gradium or deterministic code |
| [Validation record](VALIDATION.md) | Automated checks and limits of live verification |

## Controller and integration contracts

| Document | Producer → consumer | Read this for |
| --- | --- | --- |
| [Controller–Frontend](controller-frontend-contract.md) | HTTP controllers → web app | Screen-to-endpoint mapping, rendering, consent and error handling |
| [Controller–Service](controller-service-contract.md) | Controllers → Python services/adapters | Function boundaries, routing ownership, deadlines and data handoffs |
| [Care controller](controller-care-contract.md) | Care navigation → frontend/coordinator | Request/result schemas, nearby clinics, SSE and result retention |
| [Agent controller](controller-agent-contract.md) | Runtime coordinator → frontend | Graph metadata, run requests, traces and action gates |
| [Voice controller](controller-voice-contract.md) | Voice pipeline → frontend/coordinator | Transcription, German scripts, own-voice lifecycle and WAV output |
| [Knowledge controller](controller-knowledge-contract.md) | Retrieval/data → frontend/coordinator | Evidence search, clinic-data boundary and demo isolation |
| [API overview](API_CONTRACT.md) | All modules | Complete route inventory and shared conventions |
| [OpenAPI](openapi.json) | Pydantic/FastAPI → API clients | Generated request/response schemas |

These are documentation boundaries. Care and legacy routes currently live in `pawse/app.py`; agent, voice and knowledge routes already use routers in their corresponding modules. The document names do not imply that new controller classes or services have been implemented.

## Provider and data references

- [Voice concierge](VOICE_CONCIERGE.md): provider lifecycle, recording and verification.
- [RAG evidence contract](RAG_CONTRACT.md): citation semantics and retrieval acceptance cases.
- [Mapify adapter](MAPIFY_ADAPTER.md): actual upstream differences and clinic normalization.
- [Data sources](DATA_SOURCES.md): open data, licensed providers and private documents.
- [Gemini integration](GEMINI_INTEGRATION.md): configuration and model migration.
- [Existing capabilities](CAPABILITIES.md): imported CatAgent tools and reports.
- [Import review](IMPORT_REVIEW.md) and [hackathon notes](HACKATHON.md): provenance and project context.

## Contract maintenance

Check implementation and [OpenAPI](openapi.json) together: streaming events, dynamic voice-status dictionaries and some error responses need the written contracts because they are not fully typed in OpenAPI. TypeScript helpers in [schemas/pawse.ts](../schemas/pawse.ts) assist the frontend but do not replace server validation.

When changing an interface, update its controller contract and consumers, then run `python scripts/export_contract.py` to regenerate OpenAPI. Keep example payloads synthetic and valid. Coordinate shared schemas and route changes through the integration module described in [Agent development](AGENT_DEVELOPMENT.md).

The documentation layout is inspired by MapifyAI's [frontend contract](https://github.com/qing-dai/MapifyAI/blob/main/doc/controller-frontend-contract.md) and [service contract](https://github.com/qing-dai/MapifyAI/blob/main/doc/controller-service-contract.md). Pawse's paths, schemas and behavior below are derived from Pawse's own code.
