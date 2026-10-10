# Pawse multimodal architecture diagram

![Pawse multimodal agents](pawse-multi-agent-architecture.png)

[Full-size PNG](pawse-multi-agent-architecture.png) · [Editable SVG](pawse-multi-agent-architecture.svg) · [Target design](../MULTIMODAL_ARCHITECTURE.md) · [Current runtime](../ARCHITECTURE.md)

## Reading the diagram

This is the **target multimodal design**, dated 10 October 2026. Card badges describe existing integration, not model quality or completion of the entire path.

- Voice, Vision and Document are separate input responsibilities. Only the applicable inputs are required; the owner need not supply all three.
- Gray arrows show the proposed task/result flow. Gemini Live routes tools; bounded backend execution retains partial results and enforces consent.
- The dashed pink arrow carries page-linked document evidence to retrieval. It is a proposed handoff, not a private-policy feature already exposed by the API.
- Care guidance, clinic discovery/ranking and policy evidence return results to the case summary. Urgent guidance should not wait for an unavailable policy or voice setup.
- Own-voice enrollment is performed separately, ideally before the demo. Script drafting and the saved voice meet at owner review, followed by Gradium speech.
- Audio generation does not place a phone call. The footer lists unconnected action integrations.

The selected text/vision/document model is Gemini 3.8 Flash; the current text routes still default to Gemini 3 Flash Preview. A synthetic PDF probe verifies model access, not an implemented upload screen. Live has token and server tool endpoints, but its browser microphone/playback remains unfinished. Gradium adapters require a separate credential and consented live validation. See [Model allocation](../MODEL_ALLOCATION.md).

## Relationship to the runtime graph

Design roles are not new runtime IDs. The existing `/api/v1/agents/graph` continues to expose these seven roles:

| Runtime ID | Current responsibility | Relationship to the target design |
| --- | --- | --- |
| `intake` | Validation, consent, reported warning signs | Shared input boundary |
| `care_guidance` | Gemini text/photo care navigation | Care Guidance; proposed separate Vision handoff |
| `nearby_vets` | Clinic provider adapters | Vet Discovery |
| `ranking` | Deterministic clinic ordering | Included inside the Vet Discovery card |
| `orchestrator` | Bounded coordination, trace, partial results and action gates | Execution layer used by the conversational orchestrator |
| `policy_evidence` | Separate lexical search under `synthetic_demo` | Existing foundation for proposed private-document retrieval and synthesis |
| `communication` | Gemini scripts/transcription and Gradium voice adapters | Split visually into communication, enrollment and speech responsibilities |

Live token/tool endpoints are a separate controller in `pawse/live.py`. Document extraction has no callable endpoint yet. Demo evidence includes a fictional schedule and an English adaptation of real Swiss terms; it never establishes an owner's actual coverage.

## Editing

The SVG is original editable project artwork in Pawse's pink and gray palette, with accessible title/description text. Its viewBox is 1200 × 1910; the PNG export is 2400 × 3820. Regenerate the PNG after SVG edits and inspect it at README width. Keep labels, model decisions, implementation badges and this legend aligned. The Mermaid diagram in the runtime reference describes current implementation separately.
