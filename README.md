# Pawse 🐾

**A little help. Right when it matters.**

An integrated cat-care app that helps you prepare for a vet call, discover nearby veterinary clinics, organize insurance contacts, and access an existing CatAgent from one place. The initial demo is centred on Zurich, Switzerland; users can change the location.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stage: Hackathon prototype](https://img.shields.io/badge/Stage-Hackathon_prototype-orange.svg)](docs/SPEC.md)
[![Built for: Tech Europe](https://img.shields.io/badge/Built_for-Tech_Europe_AI_Hackathon-purple.svg)](docs/HACKATHON.md)

[API contract](docs/API_CONTRACT.md) · [Mapify integration](docs/MAPIFY_ADAPTER.md) · [Capabilities](docs/CAPABILITIES.md) · [Contributing](CONTRIBUTING.md)

## Built for the hackathon

Pawse is being built specifically for the **Tech Europe AI Hackathon, sponsored by Google DeepMind**, as described by the team. It is an independent participant project, not an endorsed Google product.

The cat-care and IoT backend in `backend/` is pre-existing work. The unified Pawse interface, care-navigation API, Gemini text/photo adapter and Mapify/Places adapters are the hackathon extension. See the [source import review](docs/IMPORT_REVIEW.md).

## The experience

1. Describe your concern, optionally attach a cat photo, and select any warning signs.
2. Receive immediate safety guidance while Gemini and clinic search run concurrently.
3. Review nearby clinics, provider-derived phone numbers, map links and transparent ranking reasons.
4. Contact the insurer using the phone number you entered from your policy.
5. Copy a concise summary for the vet, or open the existing CatAgent for other care tasks.

The target is useful next steps within one minute. The app does not promise a diagnosis, a complete directory, an appointment, an answered call or an insurance decision. Clicking a call action opens your device's dialer; the app does not place calls itself.

## Current status

| Capability | Status |
| --- | --- |
| Responsive English web app and unified FastAPI API | Implemented; local workflow checked |
| Gemini text/photo adapter | Implemented; real structured text request verified |
| Photo attachment and validation | Implemented; real cat-photo analysis not yet tested |
| Initial warning-sign guidance and partial results | Implemented; tested |
| Nearby clinics through MapifyAI or Google Places | Adapters tested with synthetic responses; live provider configuration needed |
| Insurance contact, dial links, map links, call notes | Implemented; insurance details are user-provided |
| 25 existing intents, 14 tools and 10 analysis types | Catalogued; chat/report bridge implemented, legacy deployment needed |
| Browser dictation and read-aloud | Browser-dependent; not Gemini Live |
| Gemini Live voice, bookings, insurer coverage lookup | Not implemented |

No MapifyAI source or datasets are bundled. Its API conventions inform our independent adapter. Clinic ranking currently uses reported opening state, proximity and rating; Gemini helps organize the concern and questions, without inventing clinic facts.

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
- `GEMINI_MODEL`: default `gemini-3-flash-preview`, verified with the development project's key; availability varies by project.
- `MAPIFY_BASE_URL` **or** `GOOGLE_PLACES_API_KEY`: required for live clinic results. Gemini access does not automatically enable Google Places.
- `LEGACY_AGENT_BASE_URL`, `LEGACY_AGENT_USER_ID`, `LEGACY_AGENT_CAT_IDS`: optional bridge settings. Configure and run the [existing backend](backend/README.md) separately.

The app remains useful without every provider: it returns explicit partial results, policy contact actions and a map-search link. It never fills the gaps with fake clinic listings.

This version is for local single-user development. It intentionally accepts localhost hosts only. Add real identity, ownership checks and deployment controls before publishing a multi-user service.

## Test

```sh
pip install -r requirements-dev.txt
pytest -q tests
```

Tests cover consent boundaries, warning-sign escalation, image validation, provider contracts, partial failures, deadlines, result isolation, phone sanitization and the legacy cat allowlist. Automated tests use synthetic responses and do not consume live API credits.

## Repository

```text
pawse/                 New unified app, provider adapters and web UI
backend/               Selected pre-existing CatAgent backend
schemas/               Frontend TypeScript contract
scripts/               Contract generation and verification utilities
tests/                 Tests for the unified integration
docs/API_CONTRACT.md   Frontend handoff contract
docs/openapi.json      Generated OpenAPI schema
docs/CAPABILITIES.md   Existing feature inventory and dependencies
```

## Data handling

AI and location sharing are separate opt-ins. Gemini receives the concern and optional photo, not insurance or location. Clinic providers receive location and a generic veterinary search query, not symptoms or images. Photos are not written to disk. Completed summaries are cached in process memory for 15 minutes and can be deleted. Browser dictation may use the browser vendor's service.

Unknown opening hours, clinic services and coverage stay unknown. Third-party provider data must be confirmed directly. The original book corpus, extracted knowledge content, credentials and local backup remain excluded from publication.

## License

[MIT](LICENSE) for project contributions. See [third-party notices](THIRD_PARTY_NOTICES.md) for upstream references and exclusions.
