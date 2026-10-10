# React frontend and backend agent integration

Checked on 10 October 2026. The React app lives in `web/`. Build with `npm ci --prefix web && npm run build --prefix web`, then start FastAPI. Open `/app/?live=1` for backend tools or `/app/?demo=1` for the simulated rehearsal. Vite development uses the configured `/api` proxy. Credentials remain server-side.

| Frontend role | Actual endpoint | Result and boundary |
| --- | --- | --- |
| Voice input | `POST /api/v1/voice/transcriptions` | Browser recordings converted to mono WAV; Gemini transcription. Microphone starts only after the owner enables it. |
| Care / vision / orchestration | `POST /api/v1/agents/runs` | `{care: CareRequest}`; consumes nested `care`, `trace`, `actions`. Text and selected photos require Gemini consent. Video stays local. |
| Vet discovery | `POST /api/v1/care/requests` | Generic veterinary query, location consent, no symptoms and no AI consent. Preserve backend ranking, unknown hours, source and retrieval time. |
| Communication | `POST /api/v1/voice/scripts` | Owner-reviewed facts, separate consent, German draft with EN/ZH/DE/HI subtitles. No recipient replies or bookings. |
| Policy evidence | `POST /api/v1/knowledge/search` | Explicit demo-policy panel; English lexical search and original citations. No private-policy ingestion or coverage approval. |
| Speech | `POST /api/v1/voice/speech` | Reviewed draft, separate Gradium consent, selected approved own voice or explicitly selected standard voice. Binary WAV with playback/download; no silent fallback. |
| Voice enrollment | Existing `/` voice interface | Same-origin browser session; existing clone/localization/preview/save lifecycle. |

The new live handoff uses `LiveHandoff.jsx` and `agents/handoff.js`. It bypasses the older story-backed `livePhoneAgent.js`; the explicit “Open simulated Mimi phone rehearsal” button opens that helper with Gradium sharing initially off. The owner can then enable the teammate’s whole-call Gradium rehearsal. All recipient replies/results remain simulated. Mock phone agents remain rehearsal-only. A validated `tel:` link opens the owner's dialer; audio is not injected into calls.

The language selector offers EN/ZH/DE/HI. German and Hindi use English UI labels where translations are not supplied; their API language and subtitle codes are preserved. Current conversation audio is turn-based transcription and browser speech, not a Gemini Live WebSocket session. No claim of real-time Live integration is made for this React client.

## Evaluation

- `PYTHON=.venv/bin/python bash scripts/check.sh`: safety, skill catalog, JavaScript, all `web/scripts/check-*.mjs`, OpenAPI consistency, backend pytest.
- `npm run check --prefix web`: mock story contracts, clinic mapping, voice workflow, legacy rehearsal helper, real handoff consent/languages/errors, service-worker private-response exclusion.
- `npm run build --prefix web`: production compilation.
- A bounded actual-HTTP smoke check against a local server without credentials verified seven-role workflow traces, local policy citations, explicit missing clinic configuration, missing Gemini and unconfigured own-voice errors. No paid provider calls occurred.
- Browser walkthrough verified the React consent gate, typed care request, agent result entry and separate insurer preparation page. See `VALIDATION.md` for the final observed browser result.

There is no independent evaluation agent in this repository. Open PR #29 contains proposed browser/audio tests for older test hooks; it has not been merged or claimed green here. Real microphone capture, speech accuracy (EN/ZH/DE/HI), Gemini Live streaming, Gradium clone quality and actual telephony are separate evaluations. They cannot be established by mocked contract checks or a successful build.

## Data boundary

The OSM crawling snapshot remains an offline staging dataset under the crawling contract. It is not relabelled as a live provider or silently shown as verified clinics. With no Places key or external clinic backend, the React page displays a configuration/unavailability error. Integrating OSM requires an explicit provider/schema change and reviewed cat-clinic evidence.

The service worker caches only the app shell/assets, not API responses, query URLs or no-store responses. Old Pawse shell caches are cleared on activation.
