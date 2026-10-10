# Model access and allocation

**Decision date: 10 October 2026.** Use **Gemini 3.8 Live for conversation, Gemini 3.8 Flash for visual/document understanding and grounded text, and Gradium for the owner's German voice**. Clinic lookup, ranking, arithmetic, consent and execution stay in validated tools. The [multimodal design](MULTIMODAL_ARCHITECTURE.md) defines the handoffs.

## Event model menu → Pawse role

| Model / exact ID | Assignment | Boundary |
| --- | --- | --- |
| Gemini 3.8 Flash — `gemini-3.8-flash` | Vision, Document, Care Guidance, evidence synthesis and Communication | One text-output model handles several understanding tasks, including photos and PDFs. Speech output uses a separate provider. |
| Gemini 3.8 Live — `gemini-3.8-live` | Voice Agent and conversational tool routing | Owner dialogue and async tool requests. Backend tools enforce permissions and return structured app results. |
| Deep Research — `deep-research-preview-04-2026` | Optional background source research | Produce a reviewed public-source reading list; keep outside the urgent flow and private-policy retrieval. |
| Antigravity — `antigravity-preview-09-2026` | Optional development / sandbox tasks | Useful for engineering experiments; unnecessary for the bounded care workflow. |
| Nano Banana 2.1 — `gemini-nano-banana-2.1` | Optional illustration and pitch assets | Image creation/editing, separate from the selected photo-observation model. Generated imagery must not become medical evidence. |
| Gemini Omni Flash — `gemini-omni-1.1-flash` | Optional synthetic demo video | Generation differs from understanding uploaded footage. Label synthetic footage. |
| Lyria 3.5 — `lyria-3.5` | Optional demo soundtrack | No role in care, insurance or speech identity. |
| Gemma 4 — `gemma-4-31b-it` | Optional later open-model experiment | Defer until a hosting, privacy or offline requirement and an evaluation justify it. |
| Gradium TTS — `model_name: default`, selected `voice_id` | Own-Voice / Speech Agent | Clone → German localization → preview → reviewed-text speech. A voice ID identifies a voice, not a Gemini model. |

Selections follow the [Google model catalog](https://ai.google.dev/gemini-api/docs/models), [Flash capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [Live capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live), the team's event screenshot and [Gradium TTS documentation](https://docs.gradium.ai/guides/text-to-speech-overview). Assignments are recommendations, not claims that every service has been integrated or invoked.

## What was actually checked

| Check | Evidence | Meaning |
| --- | --- | --- |
| Eight IDs in the screenshot | All appeared in this credential's model listing | Discovery only; not successful invocation, quota or protocol verification. Managed agents have separate API requirements. |
| `gemini-3.8-flash`: structured text | HTTP 200; expected JSON matched | Tiny text/JSON access test passed. |
| `gemini-3.8-flash`: synthetic PNG | HTTP 200; expected JSON matched | Image accepted; no real cat-photo evaluation. |
| `gemini-3.8-flash`: synthetic one-page PDF | HTTP 200; invoice ID, currency, total and page matched | Basic extraction is feasible with this key; no real policy or scanned-document benchmark. |
| `gemini-3.8-live` | [Existing verification](GEMINI_LIVE.md#verified-2026-10-10): token → session → tool call → audio/transcript | Server-session path checked by the Live integration. Browser mic/playback remains unfinished. Not re-run in this architecture task. |
| Gradium | No configured key at this check | Adapters and mocked tests exist. No successful clone, localization or TTS call is claimed. |

The new [access report](multimodal-model-access-check.json) contains metadata only. Three bounded requests used synthetic content with the existing `v1beta generateContent` protocol. The one-page PDF contained only a synthetic-data heading, `DEMO-42` and `CHF 120`. These checks establish access and a simple extraction result; they do not establish clinical reliability, translation accuracy, voice similarity, latency under load or access in another project.

Earlier [checks](model-access-check.json) are preserved: `gemini-3-flash-preview` accepted text, a synthetic PNG and silent WAV; `gemini-3.1-pro-preview` accepted text; `gemini-embedding-001` returned a vector. `gemini-2.5-flash` returned HTTP 404 despite appearing in the listing. A silent WAV is not a multilingual recognition evaluation.

## Configuration and migration boundary

The running default remains `GEMINI_MODEL=gemini-3-flash-preview`. `GEMINI_CARE_MODEL` overrides care; `GEMINI_VOICE_MODEL` overrides recorded-audio transcription and script preparation. `GEMINI_LIVE_MODEL` defaults to `gemini-3.8-live` independently.

The diagram selects 3.8 Flash for the next iteration. This documentation change does not edit `.env`, provider code or defaults. Evaluate real care/schema and language cases before switching a running demo, then run checks and rehearse. There are no implemented `GEMINI_DOCUMENT_MODEL` or `GEMINI_POLICY_MODEL` settings yet. The current coordinator makes no additional planner-model call.

The knowledge module uses lexical retrieval. A future vector index can start with the already accessible `gemini-embedding-001`, but needs a retrieval evaluation. Never mix legacy OpenAI vectors with Gemini vectors; record model, dimension, corpus hash and version, and isolate each owner's documents. Embeddings are optional for the small demo corpus.

Credentials stay in the ignored `.env`. The supplied Gradium coupon URL is an account-credit redemption page, not an API key, voice ID or speech endpoint. Its logged-out HTML showed a redemption loader; no credit amount or redemption result was verified.

## Sources and confidence

Checked on **2026-10-10**. High confidence means a primary source or observed response supports the narrow claim, not that model quality is proven.

| Claim used in the design | Source | Confidence |
| --- | --- | --- |
| Flash accepts text/image/video/audio/PDF and produces structured text | [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) | High; text, PNG and PDF also checked locally |
| Live supports streaming dialogue and tool calling | [Gemini 3.8 Live](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live) | High; browser integration incomplete |
| PDFs support structured, layout-aware extraction | [Document processing](https://ai.google.dev/gemini-api/docs/document-processing) | High for provider capability; app upload proposed |
| Deep Research is a separate research agent | [Deep Research](https://ai.google.dev/gemini-api/docs/deep-research) | High for documentation; not invoked |
| Clone sample languages include en/fr/de/es/pt; localization yields previewable candidates | [Custom voices](https://docs.gradium.ai/guides/voices/custom-voices), [localization](https://docs.gradium.ai/guides/voices/voice-localization) | High for contract; account untested |
| Gradium offers `s2s-translate`, using `stt-translate` and TTS `default` | [Speech-to-speech](https://docs.gradium.ai/guides/speech-to-speech-overview) | High for documentation; optional, untested |
| Gradium supports audio formats for a separate telephone integration | [Telephony audio](https://docs.gradium.ai/guides/recipes/telephony-audio) | High for formats; carrier unconnected |
| Entire's event page describes Checkpoints, Graph/Brain and development-agent handoffs | [Entire at Agentic AI Hack Zürich](https://hack.entire.io/agentic-ai-hack-zurich-2026/) | High; public page read over HTTP |

Entire belongs to development collaboration and repository memory here. Its event page is not a Gemini inference API or a clinic/insurance data source. No Entire installation, repository import or session upload was performed.

## Gaps and next validation

- Real EN/ZH/DE/HI recognition and language switching, including names and addresses.
- Gradium key, consented enrollment, German preview, pronunciation and speaker similarity.
- Blurry/multilingual scans, conflicting policy versions, citation accuracy and private-document isolation.
- Clinic availability, telephone transport, insurer responses, bookings and calendar access.
- Invocation and quota for the optional screenshot models; listing is insufficient.

The opt-in `.venv/bin/python scripts/probe_models.py` repeats the older baseline probes and spends API credits. It does not reproduce the new PDF case or validate Live/Gradium. Ordinary tests remain mocked; the two retained reports distinguish their scopes.
