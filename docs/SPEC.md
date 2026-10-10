# Pawse product scope

## Goal

Give a worried cat owner useful next steps in one app within roughly a minute: prepare a vet call, locate nearby care, find their insurer's contact, and keep relevant context together. Initial demo: Zurich, Switzerland; insurance contact is entered by the owner.

The required journey is [Mimi's 120-second story](DEMO_STORY.md). The owner speaks Mandarin Chinese, English, German or Hindi; Pawse prepares German communication with paired subtitles and a consented Gradium own-voice option. The story covers vet options, insurance limitations, clinic/home cost comparison, appointment confirmation, a pet-friendly taxi and a claim checklist. Its current rehearsal simulates calls and arrangements; presentation timing is not a live-service guarantee.

## Implemented vertical slice

- English responsive web UI with concern input, optional photo, warning signs, location and insurer contact.
- Gemini text/photo API adapter; real structured text connectivity verified.
- Immediate warning-sign response followed by concurrent assessment and clinic search.
- MapifyAI and Google Places adapters, safe phone links, map links and provider-attributed results.
- Copyable call summary, short-lived session-scoped results and explicit partial failure states.
- Complete inventory of imported agent intents/tools and a bridge for its chat and report routes.
- Four-language recorded-audio transcription, German script/subtitle drafting and Gradium clone/localize/preview/speech adapters; live Gradium validation remains outstanding.
- Gemini Live token and tool-call backend; browser microphone capture/playback remains to do.
- Cited demo-policy retrieval and a six-scene Mimi rehearsal with explicit simulated call, calendar and insurance states.

## Required experience

- Separate input and subtitle languages from the recipient language and voice identity; start with standard German for Zurich. Preserve an editable original transcript and source-linked facts.
- Prioritize recording and previewing the owner's own voice. Generate German audio as a usable outcome even before network calling is connected.
- Separate audio playback, opening a phone dialer and an agent conducting a call. Future calls need carrier audio, recipient replies, cancellation and owner approval of binding actions.
- Keep policy documents, cited exclusions and cost assumptions beside the choice of care. Live coverage remains unconfirmed until the actual insurer responds.
- Use the existing pink accent, pale blush, light gray and dark text palette, with readable bilingual transcript cards and clear state labels. See the [frontend requirements](controller-frontend-contract.md#8-journey-layout-and-visual-requirements).

## Product boundaries

The one-minute target concerns organizing next steps, not completing treatment, reaching a clinic, securing an appointment or approving insurance. Unknown clinic availability is never treated as open. A generic veterinary listing does not establish emergency or specialist capability. Photo analysis cannot establish that a cat is safe.

AI organizes information and questions; current clinic ranking is deterministic. No automated calling, insurance eligibility inference, claim filing, booking or medication advice is implemented.

## Remaining integrations

1. Configure a real Mapify backend or Google Places project and validate Zurich results and phone data.
2. Bring up the pre-existing agent with the required storage/device/model services; test each intended demo feature.
3. Replace excluded knowledge collections with permitted, reviewed sources.
4. Finish the Gemini Live browser client (mic capture, playback, transcript, tool chips). The token and tool backend is done; see [Gemini Live](GEMINI_LIVE.md).
5. Add authenticated users, cat ownership and persistent care profiles before public deployment.
6. Validate clinic/insurer service information with authoritative data partners.
7. Configure and validate Gradium own-voice enrollment, German localization and playback using a consented sample; test human recordings in all four input languages.
8. Implement private policy/invoice upload, document extraction and source-linked retrieval; add short-video intake as a separate capability.
9. Add a telephone/media gateway for German agent calls and translated replies, then calendar and appointment/taxi connectors with actual confirmations. Keep these distinct from script/audio preparation.

See [API contract](API_CONTRACT.md), [capability inventory](CAPABILITIES.md), and [Mapify notes](MAPIFY_ADAPTER.md).
