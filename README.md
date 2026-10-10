# Pawse 🐾

**A little help. Right when it matters.**

An integrated cat-care app for multilingual intake, nearby veterinary search, insurance evidence and German call preparation in your own voice. The initial demo is centred on Zurich, Switzerland; users can change the location.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stage: Hackathon prototype](https://img.shields.io/badge/Stage-Hackathon_prototype-orange.svg)](docs/SPEC.md)
[![Built for: Tech Europe](https://img.shields.io/badge/Built_for-Tech_Europe_AI_Hackathon-purple.svg)](docs/HACKATHON.md)

[API contract](docs/API_CONTRACT.md) · [Architecture](docs/ARCHITECTURE.md) · [Four-person team plan](docs/TEAM_PLAN.md) · [Model allocation](docs/MODEL_ALLOCATION.md)

[Voice concierge](docs/VOICE_CONCIERGE.md) · [RAG contract](docs/RAG_CONTRACT.md) · [Mapify integration](docs/MAPIFY_ADAPTER.md) · [Contributing](CONTRIBUTING.md)

## Built for the hackathon

Pawse is being built specifically for the **Tech Europe AI Hackathon, sponsored by Google DeepMind**, as described by the team. It is an independent participant project, not an endorsed Google product.

The cat-care and IoT backend in `backend/` is pre-existing work. The unified Pawse interface, care-navigation workflow, Gemini and Gradium adapters, Mapify/Places integration and synthetic Mimi rehearsal are the hackathon extension. See the [source import review](docs/IMPORT_REVIEW.md).

## The experience

1. Describe your concern in English, Mandarin Chinese, German or Hindi, or record a message; optionally attach a cat photo.
2. Receive immediate warning-sign guidance while Gemini and clinic search run concurrently. Inspect the seven-role agent trace.
3. Review clinic contacts and ranking reasons, and add the insurer's number from your own policy.
4. Record your own voice, review a German script and subtitles, then preview or download Gradium audio once configured.
5. Rehearse Mimi's two-minute story: vet options, cited fictional policy clauses, clinic versus home-visit costs and a claim checklist.

The target is useful next steps within one minute. The app does not promise a diagnosis, a complete directory, an appointment, an answered call or an insurance decision. Device call links open a dialer. Mimi's calls, replies, calendar slots and bookings are simulated; actual telephone transport and calendar integration are not connected. Generated audio is not automatically injected into a phone call.

## Current status

| Capability | Status |
| --- | --- |
| Responsive app with Mapify-inspired pink/gray styling | Implemented; English interface with multilingual input and subtitles |
| Gemini text, photo and recorded-audio adapters | Implemented; text, synthetic PNG and silent WAV accepted in project access checks; real speech/photo quality not evaluated |
| Seven-role agent graph and run trace | Implemented; bounded coordinator reuses parallel care and clinic providers |
| Initial warning-sign guidance and partial results | Implemented; consent and deadline behavior tested |
| Nearby clinics through MapifyAI or Google Places | Adapters tested with synthetic responses; live provider configuration needed |
| Insurance contact, dial links, map links, call notes | Implemented; insurance details are user-provided |
| Policy evidence search | Implemented lexical retrieval with source hashes and clause references; synthetic demo corpus only |
| Own-voice recording, clone/localization and German audio | Interface and Gradium adapters implemented; live clone/voice quality pending `GRADIUM_API_KEY` and an owner sample |
| Mimi vet/insurer/taxi story | Interactive synthetic rehearsal; deterministic CHF 385 clinic / CHF 510 home estimates under stated demo assumptions |
| 25 existing intents, 14 tools and 10 analysis types | Catalogued; chat/report bridge implemented, legacy deployment needed |
| Outbound calls, real bookings, calendar access and live coverage verification | Not connected |

No MapifyAI source or datasets are bundled. Its API conventions inform our independent adapter. Clinic ranking currently uses reported opening state, proximity and rating; Gemini helps organize the concern and questions, without inventing clinic facts.

Gradium's current documented speech languages are English, French, German, Spanish and Portuguese. Chinese and Hindi use Gemini for input; the app's Gradium output is German. Own-voice cloning prioritizes an English or German sample, with preview before use. See the [voice guide](docs/VOICE_CONCIERGE.md) for the exact workflow and provider references.

## Four people, four branches

The branches use a common reviewed baseline for parallel development. They are starting points, not four completed independent implementations.

| Owner | Branch | Slice |
| --- | --- | --- |
| Frontend | `feat/frontend-experience` | Unified UI, agent states, recording and story flow |
| LLM backend | `feat/llm-orchestrator` | Care guidance, coordination, ranking and action gates |
| Voice backend | `feat/voice-calling` | Gemini audio, Gradium own voice and future phone transport |
| RAG/data backend | `feat/rag-open-data` | Cited policy retrieval, clinic data and source provenance |

The [team plan](docs/TEAM_PLAN.md) defines file ownership, contracts, merge order and acceptance checks. Runtime agents are responsibilities inside the product; they do not each need a different model.

## Run locally

Python **3.11+**:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# If you do not already have a local .env:
cp -n .env.example .env
# Fill in the relevant server-side settings.
uvicorn pawse.app:app --host 127.0.0.1 --port 8765
```

Open [the local app](http://127.0.0.1:8765) or [interactive API docs](http://127.0.0.1:8765/docs).

- `GEMINI_API_KEY`: obtained from the assigned hackathon project in [AI Studio](https://aistudio.google.com/api-keys).
- `GEMINI_MODEL`: default `gemini-3-flash-preview`; optional `GEMINI_CARE_MODEL` and `GEMINI_VOICE_MODEL` overrides. See [tested model access](docs/MODEL_ALLOCATION.md), including optional Pro and embedding choices.
- `GRADIUM_API_KEY`: required for cloning, localization and speech. Optional `GRADIUM_VOICE_ID_DE` reuses an already approved German voice across server restarts.
- `MAPIFY_BASE_URL` **or** `GOOGLE_PLACES_API_KEY`: required for live clinic results. Gemini access does not automatically enable Google Places.
- `LEGACY_AGENT_BASE_URL`, `LEGACY_AGENT_USER_ID`, `LEGACY_AGENT_CAT_IDS`: optional bridge settings. Configure and run the [existing backend](backend/README.md) separately.

The app remains useful without every provider: it returns explicit partial results, policy contact actions and a map-search link. The synthetic story and local evidence search need no provider key. They are labelled as demo material and never substitute for live clinic or insurance facts.

This version is for local single-user development. It intentionally accepts localhost hosts only. Add real identity, ownership checks and deployment controls before publishing a multi-user service.

## Test

```sh
pip install -r requirements-dev.txt
pytest -q tests
```

Tests cover consent, warning signs, image/audio validation, agent concurrency, deadlines, session isolation, voice lifecycle, evidence citations and the legacy cat allowlist. The current suite has 56 passing tests. Automated tests use synthetic responses and do not consume live API credits; the opt-in model access probe is separate.

## Repository

```text
pawse/                 Unified app, agent coordinator, voice and knowledge adapters
backend/               Selected pre-existing CatAgent backend
schemas/               Frontend TypeScript contract
scripts/               Contract generation and verification utilities
tests/                 Tests for the unified integration
docs/API_CONTRACT.md   Frontend handoff contract
docs/openapi.json      Generated OpenAPI schema
docs/CAPABILITIES.md   Existing feature inventory and dependencies
docs/TEAM_PLAN.md      Four-person branch ownership and acceptance checks
research/              Synthetic insurance evidence and source research
```

## Data handling

AI, location, voice upload and speech generation have separate opt-ins. The care route sends Gemini the concern, flags and optional photo, excluding name, location and insurance. Clinic providers receive a generic search and location. Voice routes send only the selected recording or reviewed script to their respective providers. Photos and recordings are not written to disk. Completed care results from care or agent runs share a session-scoped, in-memory 15-minute cache and can be deleted.

Gradium-created voices persist in the provider account until deleted. Pawse retains their IDs only in local session memory; restarting the app does not delete provider voices. Use the in-app deletion flow or the Gradium account to manage them. See [voice lifecycle details](docs/VOICE_CONCIERGE.md).

Unknown opening hours, clinic services and coverage stay unknown. Third-party provider data must be confirmed directly. The original book corpus, extracted knowledge content, credentials and local backup remain excluded from publication.

## License

[MIT](LICENSE) for project contributions. See [third-party notices](THIRD_PARTY_NOTICES.md) for upstream references and exclusions.
