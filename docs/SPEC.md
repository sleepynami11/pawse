# Pawse product scope

## Goal

Give a worried cat owner useful next steps in one app within roughly a minute: prepare a vet call, locate nearby care, find their insurer's contact, and keep relevant context together. Initial demo: Zurich, Switzerland; insurance contact is entered by the owner.

## Implemented vertical slice

- English responsive web UI with concern input, optional photo, warning signs, location and insurer contact.
- Gemini text/photo API adapter; real structured text connectivity verified.
- Immediate warning-sign response followed by concurrent assessment and clinic search.
- MapifyAI and Google Places adapters, safe phone links, map links and provider-attributed results.
- Copyable call summary, short-lived session-scoped results and explicit partial failure states.
- Complete inventory of imported agent intents/tools and a bridge for its chat and report routes.

## Product boundaries

The one-minute target concerns organizing next steps, not completing treatment, reaching a clinic, securing an appointment or approving insurance. Unknown clinic availability is never treated as open. A generic veterinary listing does not establish emergency or specialist capability. Photo analysis cannot establish that a cat is safe.

AI organizes information and questions; current clinic ranking is deterministic. No automated calling, insurance eligibility inference, claim filing, booking or medication advice is implemented.

## Remaining integrations

1. Configure a real Mapify backend or Google Places project and validate Zurich results and phone data.
2. Bring up the pre-existing agent with the required storage/device/model services; test each intended demo feature.
3. Replace excluded knowledge collections with permitted, reviewed sources.
4. Connect Gemini Live (`GEMINI_LIVE_MODEL=gemini-3.8-live`, listed for the team key) for continuous voice; browser dictation/read-aloud are only optional conveniences.
5. Add authenticated users, cat ownership and persistent care profiles before public deployment.
6. Validate clinic/insurer service information with authoritative data partners.

See [API contract](API_CONTRACT.md), [capability inventory](CAPABILITIES.md), and [Mapify notes](MAPIFY_ADAPTER.md).
