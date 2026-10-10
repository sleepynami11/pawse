# Multimodal agent design

**Target design, 10 October 2026.** This extends Pawse with separate voice, visual and document responsibilities. It does not change the seven IDs returned by `/api/v1/agents/graph`, add document endpoints, or switch deployed defaults. [Current runtime](ARCHITECTURE.md) · [Model decisions and access evidence](MODEL_ALLOCATION.md).

The end-to-end acceptance scenario is [Mimi in Zurich: the 120-second journey](DEMO_STORY.md). It connects four-language intake, document-backed insurance questions and reviewed German own-voice audio to the proposed vet/insurer/taxi calling sequence. [Voice requirements](VOICE_CONCIERGE.md#language-and-delivery-requirements) define the language and delivery-mode boundaries.

![Pawse multimodal agent design with selected models and integration status](images/pawse-multi-agent-architecture.png)

Implementation agreements: [Multimodal contract map](MULTIMODAL_CONTRACTS.md) · [Live](controller-live-contract.md) · [Vision](controller-vision-contract.md) · [Document](controller-document-contract.md) · [Case handoffs](controller-case-contract.md) · [Actions](controller-action-contract.md). These specify payloads, boundaries and acceptance criteria for each role below.

## Agent responsibilities

| Agent / component | Selected model or tool | Input → output | Current integration |
| --- | --- | --- | --- |
| Voice Agent | `gemini-3.8-live` | Owner speech → dialogue, transcripts and tool requests; initial languages: English, Mandarin Chinese, German, Hindi | Live token and server tool endpoints exist; server-session smoke check recorded. Browser mic/playback is still to do. Recorded-audio transcription exists. |
| Vision Agent | `gemini-3.8-flash` | Cat photo or short clip → visible observations, uncertainty and questions | Photo care intake exists using the previous Flash default. Video intake and a separate observation handoff are proposed. |
| Document Agent | `gemini-3.8-flash` | Policy PDF, invoice, vet report or scanned page → typed fields and page-linked evidence | New upload/extraction/review pipeline required. Synthetic one-page PDF extraction passed the access check. |
| Orchestrator | Gemini Live tool routing + bounded execution | Validated facts → selected tools → joined results and next-action state | Live tools and the care coordinator exist. Document tools and shared evidence-backed case state are proposed. No additional planner-model call is required. |
| Care Guidance Agent | `gemini-3.8-flash` | Owner account + observations → care-navigation summary and questions for a vet | Existing Gemini assessment; model upgrade and new modality handoffs remain to be integrated. |
| Vet Discovery & Ranking | Clinic data APIs + deterministic rules | Consented location and requested services → source-bearing clinic cards | Adapters and ranking exist. Provider configuration is required; unknown hours and services stay unknown. |
| Policy Evidence Agent | Retrieval + `gemini-3.8-flash` synthesis | Question + reviewed policy evidence → cited explanation, gaps and questions for the insurer | Current search is lexical over a demo schedule and adapted real terms. Private-document indexing and grounded synthesis are proposed. |
| Communication Agent | `gemini-3.8-flash` | Selected facts, recipient and purpose → German draft with paired subtitles | Script endpoint exists with the previous Flash default. Generating a script sends nothing. |
| Own-Voice / Speech Agent | Gradium custom voices, localization and TTS (`model_name: default`) | Consented sample → previewed German voice; reviewed text → audio | Adapters exist. No Gradium key was configured during this check; real cloning and playback need validation. |
| Action gateway | Phone transport / calendar / booking connectors | Explicitly approved action → provider receipt or failure | Confirm-before-opening a clinic `tel:` link exists as a Live tool result. Autonomous calls, call audio injection, appointments, calendar writes and taxi bookings are not connected. |

These are responsibility boundaries, not separate servers or a different paid model for every box. Care assessment and clinic search already run concurrently. The proposed document pipeline runs once per upload/version; urgent guidance must not wait for a policy upload or voice enrollment.

## How documents become useful

Extraction identifies what a file says; retrieval finds relevant passages; synthesis explains those passages for this case.

1. **Receive and validate.** Accept an owner-selected file after provider-sharing consent. Implement MIME/content, size and page checks, session-scoped storage and retention before exposing an upload route. Do not fetch arbitrary document URLs.
2. **Extract with provenance.** Classify policy schedule, terms, invoice or clinical record. Preserve original-language text, page, section, document hash and version. Keep model summaries separate from source excerpts. An unreadable or absent value is `null` plus a reason.
3. **Review facts.** Ask the owner to check identity, policy dates, insurer contact and monetary fields. A terms booklet alone does not prove enrollment, selected plan, remaining deductible or eligibility.
4. **Retrieve within the case.** Query only that owner's reviewed corpus. Start with lexical retrieval; add embeddings when corpus size or evaluation justifies them. Use matching model/version vectors for indexing and queries.
5. **Explain and calculate.** Flash writes a cited explanation from retrieved passages. Application code validates citations and computes estimates from explicit inputs. Coverage stays `unconfirmed` without an actual insurer response; missing inputs produce an incomplete estimate.
6. **Prepare a handoff.** Put questions into the reviewed German script and assemble an evidence checklist. Claim deadlines come from the applicable policy; the demo's 30-day value is not a universal rule.

Documents and provider results are untrusted data. Instructions embedded in a PDF cannot grant consent, change tools or cause an external action.

### Proposed handoff contract

This is a **design contract**, not a callable HTTP schema. Proposed v1 route names and application limits are now specified in the [Document](controller-document-contract.md), [Case](controller-case-contract.md) and [Action](controller-action-contract.md) contracts. Implement and validate them before exporting OpenAPI and enabling frontend consumers.

| Object | Required information | Consumer |
| --- | --- | --- |
| `DocumentEvidence` | Document/case IDs, kind, language, hash, version, scope, page/section, original excerpt, extraction warnings | Owner-scoped evidence storage and retriever |
| `ReviewedFact` | Field, value or `null`, unit/currency, evidence references, review state, conflict/unknown reason | Care context, estimate calculator, script drafting |
| `EvidenceAnswer` | Question, answer, citations, unsupported questions, `coverage_status: unconfirmed` | Orchestrator and evidence card |
| `ActionDraft` | Recipient, purpose, German text, subtitle language, selected voice, evidence references, revision | Owner review; approval binds to this exact revision |
| `ActionReceipt` | Provider, external ID, actual status, timestamp and approved revision | Future gateway; generated text cannot create a success receipt |

Changed facts, recipient, script or voice invalidate an earlier approval. Demo and private evidence use separate scopes; the current `synthetic_demo` endpoint must not silently accept a private-policy request.

## Two voice modes

**Talk to Pawse:** Gemini Live handles the owner's conversation and requests backend tools. The server issues a locked, short-lived token; permanent credentials stay server-side. App logic validates tool arguments and action permissions. Recorded audio and typed input remain the fallback. See the [Live contract](GEMINI_LIVE.md).

**Speak for the owner:** record the owner's sample with cloning/provider consent, localize it to German and preview it. Then synthesize the approved German script through Gradium. Gemini Live's assistant audio is separate from the owner's cloned voice. Enroll and audition before the urgent demo. Gradium's current sample-language contract accepts English, German, French, Spanish and Portuguese; Chinese/Hindi conversation support does not imply Chinese/Hindi cloning support. [Custom voices](https://docs.gradium.ai/guides/voices/custom-voices) · [Localization](https://docs.gradium.ai/guides/voices/voice-localization).

Gradium also documents `s2s-translate` for speech translation. Keep it as an optional later experiment after checking the language pair and own-voice behavior. The selected first path preserves German text review before synthesis. A telephone carrier and media bridge are still needed to speak inside a real call; neither a WAV file nor a `tel:` link supplies them. [S2S documentation](https://docs.gradium.ai/guides/speech-to-speech-overview) · [Telephony audio formats](https://docs.gradium.ai/guides/recipes/telephony-audio).

## Module handoffs and build order

Use the existing module branches; these assignments do not create new branches.

| Module / branch | Owns next | Handoff |
| --- | --- | --- |
| Frontend / `feat/frontend-experience` | Live mic/playback, modality selector, document review, citations, own-voice preview and confirmation | Typed controller results; visible source and implementation status |
| Orchestration / `feat/llm-orchestrator` | Case state, validation, care/vision handoff, scheduling, grounded summary and deterministic estimates | Shared schemas, document status events and cancellation |
| Voice / `feat/voice-calling` | Live integration with frontend, Gradium enrollment/localization, German audio and future phone bridge | Script revision + selected voice → audio; provider receipts for later calls |
| Evidence & data / `feat/rag-open-data` | Document intake/extraction, scoped retrieval, provenance and clinic normalization | Reviewed document evidence + clinic records → coordinator |

Finish Live browser audio and own-voice enrollment first. Add a small PDF upload/extraction/review slice, then connect cited answers to shared case state. Rehearse photo → care → clinic → document explanation → reviewed German audio. Add video and actual calls as separate acceptance milestones. Keep the two-minute rehearsal working throughout.

## Optional background and creative work

Deep Research can investigate public sources and propose corpus updates for review. It must not delay urgent care or substitute for an insurer's decision. Antigravity and Entire can support engineering and cross-agent code context. Nano Banana, Omni and Lyria are optional presentation tools; generated assets are not case evidence. Exact IDs, reasons and sources are in [Model allocation](MODEL_ALLOCATION.md).
