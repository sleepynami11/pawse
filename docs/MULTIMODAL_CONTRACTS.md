# Multimodal controller and agent contracts

This is the integration map for the [Pawse Multimodal Agents diagram](images/pawse-multi-agent-architecture.png). **Current** means implemented in this repository; **Proposed v1** means an interface design for the next implementation, with no callable endpoint yet. Provider access checks are recorded separately in [Model allocation](MODEL_ALLOCATION.md).

The end-to-end target is [Mimi's 120-second journey](DEMO_STORY.md): understand an owner speaking English, Mandarin Chinese, German or Hindi; combine visual and document evidence; find care in Zurich; prepare reviewed German speech in the owner's voice. Telephone, appointment, calendar and taxi execution remain future connectors.

## 1. Diagram-to-controller map

| Diagram responsibility | Controller / contract | Current boundary | Next integration |
| --- | --- | --- | --- |
| Voice Agent | [Live](controller-live-contract.md), [Voice](controller-voice-contract.md) | Live tokens and four server tools; recorded WAV transcription | Browser microphone, playback and interrupted-turn handling |
| Vision Agent | [Vision](controller-vision-contract.md) | Photo inside `CareRequest` | Separate cited observations; bounded video intake |
| Document Agent | [Document](controller-document-contract.md) | No upload or extraction controller | PDF/image validation, extraction, owner review and deletion |
| Orchestrator | [Agents](controller-agent-contract.md), [Case](controller-case-contract.md) | Bounded care run and Live tool dispatch | Versioned multimodal case state and stale-result rejection |
| Care Guidance | [Care](controller-care-contract.md) | Text/photo assessment and immediate reported-warning-sign handling | Consume reviewed modality facts without waiting on insurance |
| Vet Discovery & Ranking | [Knowledge/Data](controller-knowledge-contract.md) | Clinic adapters and deterministic ranking inside care | Verified open-data adapter; preserve unknown hours/services |
| Policy Evidence | [Knowledge/Data](controller-knowledge-contract.md), [Document](controller-document-contract.md) | Fixed demo corpus, lexical search, source hashes | Owner-scoped retrieval with page citations and grounded explanation |
| Communication Agent | [Voice](controller-voice-contract.md), [Action](controller-action-contract.md) | German draft and paired subtitles | Bind the reviewed draft to case/recipient/voice revisions |
| Own-Voice Setup / Speech Agent | [Voice](controller-voice-contract.md) | Gradium clone, localization, preview/save and WAV adapters | Real provider validation with a configured key |
| Owner review / Care handoff | [Action](controller-action-contract.md) | Script/audio review and manual dialer handoff | Approval, idempotent execution and verifiable connector receipts |

The diagram's roles do not add IDs to the existing `/agents/graph`. Keep the current seven runtime IDs stable until an implementation and client migration land together. Controllers are logical boundaries; they do not require separate deployments or one LLM invocation per box.

## 2. Interface status and source of truth

All paths below have the `/api/v1` prefix.

| Status | Paths | Schema authority |
| --- | --- | --- |
| Current | `/care/requests`, `/agents/graph`, `/agents/runs`, `/live/tokens`, `/live/tool-calls`, `/voice/*`, `/knowledge/search` | Pydantic models and generated [OpenAPI](openapi.json); domain docs cover dynamic results and streaming |
| Proposed v1 | `/cases/*`, including document, vision, evidence and action resources | Drafts in the contracts below; deliberately absent from OpenAPI and `schemas/pawse.ts` |

**Do not call proposed paths from the shipped frontend.** Each proposed controller specifies its own payload, lifecycle and acceptance boundary. Implement and validate the server first, export OpenAPI, update client types, then enable its UI. Proposed `case_id` values are not the current care `request_id` or agent `run_id`.

## 3. Shared handoff rules

- The [Case contract](controller-case-contract.md) owns IDs, revisions, facts, evidence references, language context and partial-result merging.
- The [Document contract](controller-document-contract.md) owns source versions and reviewed extraction. Policy retrieval selects evidence; it does not grant coverage.
- The [Action contract](controller-action-contract.md) owns the exact approved recipient, script, voice and limits. A generated script, WAV or ended call cannot establish a booking or insurer approval.
- Current and proposed requests derive the owner from server session/authentication. Never accept owner IDs, permanent provider credentials or arbitrary provider voice IDs from an agent.
- Mandarin/Hindi conversation support is separate from Gradium sample-language support. `input_language`, `subtitle_language`, `recipient_language` and `sample_language` are independent; German is the first recipient language.
- Urgent care guidance must remain available while documents, policy search, localization or external connectors fail or are still running.

## 4. Module ownership and integration order

| Module / branch | Owns | Delivers to the next module |
| --- | --- | --- |
| Frontend / `feat/frontend-experience` | Capture, consent, paired subtitles, citations, voice preview, approval and status screens | Validated user choices; renders only server-confirmed progress |
| Orchestration / `feat/llm-orchestrator` | Case schema, care/vision results, revision merge, deterministic estimates | Versioned facts, partial summaries and unresolved requirements |
| Voice / `feat/voice-calling` | Live session integration, scripts, Gradium lifecycle and future phone media bridge | Draft/audio references; actual connector outcomes when implemented |
| Evidence & data / `feat/rag-open-data` | Document extraction, private retrieval, provenance, clinics and open data | Reviewed evidence and normalized clinic records |

These are existing branch assignments, not new branches created by this documentation. Shared changes to application routing, models, OpenAPI or client types should land in one coordinated integration PR.

1. Finish Live browser audio and validate the existing own-voice enrollment flow.
2. Implement case ownership/revisions, then one PDF → extract → review → cited-answer path.
3. Add separate photo observations and connect them to the care summary; add video after that path is evaluated.
4. Bind reviewed German drafts/audio to case revisions.
5. Add one telephone connector with verified outcomes before connecting booking, calendar and taxi actions.

## 5. Release evidence

The controller contracts below are the implementation checklist. Record mocked API checks separately from live Gemini/Gradium/connector checks in [Validation](VALIDATION.md). Keep the [120-second rehearsal](DEMO_STORY.md) labeled as simulated until each actual integration has evidence. Never count a successful model probe as an implemented controller.
