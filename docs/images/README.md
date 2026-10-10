# Pawse architecture diagram

![Pawse multi-agent architecture](pawse-multi-agent-architecture.png)

[Download PNG](pawse-multi-agent-architecture.png) · [Editable SVG](pawse-multi-agent-architecture.svg) · [Architecture reference](../ARCHITECTURE.md)

## Reading the diagram

- Read from top to bottom: owner input → intake → parallel care guidance and vet discovery → ranking and coordination → care summary.
- Solid arrows show the bounded care workflow. Vet discovery feeds ranking; care guidance and ranked clinics feed the orchestrator.
- The dashed pink arrow is an owner-reviewed follow-up through separate communication APIs. The agent run does not automatically call voice endpoints.
- The separate policy tool returns cited demo clauses. It has no edge into the live care run because that integration is not implemented.
- The footer lists future actions. Telephone, appointment, calendar and taxi execution are not connected.

Numbers identify roles in this diagram, not execution order or developer headcount. Care guidance and nearby-vet retrieval run concurrently.

| Number | Runtime ID | Implementation |
| --- | --- | --- |
| 1 | `intake` | Validated input, consent and deterministic warning-sign handling |
| 2 | `care_guidance` | Gemini text/photo care navigation |
| 3 | `nearby_vets` | Clinic discovery adapters |
| 4 | `ranking` | Deterministic opening-status, distance and rating rules |
| 5 | `orchestrator` | Bounded Python coordination, partial results, trace and action gates |
| 6 | `policy_evidence` | Separate local lexical retrieval over the synthetic demo corpus |
| 7 | `communication` | Separate Gemini transcription/script and Gradium voice APIs |

## Scope and maintenance

This English diagram reflects the current [agent controller](../controller-agent-contract.md), [care controller](../controller-care-contract.md), [voice controller](../controller-voice-contract.md) and [knowledge controller](../controller-knowledge-contract.md). It uses the app's pink and gray palette and is original project artwork.

The overview deliberately leaves API paths, timeout values and provider configuration in the controller contracts. Provider adapters require configuration and live validation. Policy snippets are synthetic and do not establish real coverage.

The communication node summarizes script and audio generation; the voice contract defines recording, cloning, localization and review. Recorded speech is transcribed through a separate endpoint before entering the care request.

The SVG is the editable source. The PNG is a 2160 × 2900 raster export. The narrow layout and larger labels are designed to remain readable at GitHub README width. When roles or boundaries change, edit the SVG text/connectors and regenerate the PNG from it; keep both files and the contract references aligned. The Mermaid flow in the architecture reference is an additional text-based overview, not the source used to render this image.
