# Pawse architecture diagram

![Pawse multi-agent architecture](pawse-multi-agent-architecture.png)

[Download PNG](pawse-multi-agent-architecture.png) · [Editable SVG](pawse-multi-agent-architecture.svg) · [Architecture reference](../ARCHITECTURE.md)

## Reading the diagram

- Solid muted arrows: execution/data flow in the bounded care workflow.
- Dashed pink arrows: owner-reviewed handoff and separate communication API calls. The agent run does not automatically call the voice endpoints.
- Dashed gray arrows: future integration, with no current telephone, appointment, calendar or taxi execution.
- The separate policy panel is an implemented synthetic evidence API. It has no edge into the live care run because that integration is not implemented.

Numbers identify roles in this diagram, not execution order or developer headcount. Care guidance and nearby-vet retrieval run concurrently.

| Number | Runtime ID | Implementation |
| --- | --- | --- |
| 1 | `intake` | Validated input, consent and deterministic warning-sign handling |
| 2 | `care_guidance` | Gemini text/photo care navigation |
| 3 | `nearby_vets` | Google Places or Mapify HTTP adapter |
| 4 | `ranking` | Deterministic opening-status, distance and rating rules |
| 5 | `orchestrator` | Bounded Python coordination, partial results, trace and action gates |
| 6 | `policy_evidence` | Separate local lexical retrieval over the synthetic demo corpus |
| 7 | `communication` | Separate Gemini transcription/script and Gradium voice APIs |

## Scope and maintenance

This English diagram reflects the current [agent controller](../controller-agent-contract.md), [care controller](../controller-care-contract.md), [voice controller](../controller-voice-contract.md) and [knowledge controller](../controller-knowledge-contract.md). It uses the app's pink and gray palette and is original project artwork.

The 40/45-second labels are software execution budgets, not promises to finish a real vet or insurer call. Provider adapters require configuration and live validation. Policy snippets are synthetic and do not establish real coverage.

The voice sequence is the non-German source-sample path. A German source sample skips localization/save; see the voice contract for that exception and configured-voice behavior. Recorded speech is transcribed through a separate endpoint before entering the care request.

The SVG is the editable source. The PNG is a 3600 × 2560 raster export for GitHub and slides. When roles or boundaries change, edit the SVG text/connectors and regenerate the PNG from it; keep both files and the contract references aligned. The Mermaid flow in the architecture reference is an additional text-based overview, not the source used to render this image.
