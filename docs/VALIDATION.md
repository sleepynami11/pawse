# Validation record

Date: 2026-10-10. Scope: the unified `pawse/` app and its new voice, agent and evidence interfaces. This is not a certification of the imported backend.

## Passed

- Clinic discovery and owner insurance profile (2026-10-10): 106 backend tests plus web checks pass. The project's Gemini key is blocked for Places API (HTTP 403), but Gemini Grounding with Google Maps (`gemini-3.5-flash-lite`) works with it. One real `POST /api/v1/care/requests` at Zurich's public centre (10 km, `share_with_ai: false`) returned HTTP 201 in 3.2 s with 32 clinics: 9 Google Maps listings (all with phone, address and Maps link; parsed from grounding sources, not model text) and 23 from the local OSM snapshot; 11 snapshot rows lack a phone. Google Maps listings carry no coordinates, so their distance is unknown and two listings likely beyond 10 km could not be filtered. Results vary between calls. Browser check: the static care form rendered the cards with call, map, website and Google Maps attribution; the React home screen saved an owner insurer and plan on the device. Gemini Live asking for the insurer was covered by mocked tool tests only, not a spoken session.

- Crawling slice: 83 automated tests pass, including ten new normalization, source/unknown-state, query bound, malformed-content, provenance, duplicate-ID and mocked HTTP cases. An initial live Zurich Overpass query retained 27 of 29 candidate elements. Final-schema refresh was unavailable; the first exploratory snapshot is retained separately and does not contain the later-added raw `source_elements`. See the [crawling result and limits](controller-crawling-contract.md#7-initial-collection-result). No live API adapter or official-site enrichment is claimed.

- Team integration alignment: 73 tests pass, including a regression first reproduced against the new public quota guard. HTTP 429 now provides the frontend-readable `detail`, no-store/nosniff headers and a session cookie. On a separate local server with public quota set to zero and provider keys blank, the browser care form displayed the specific quota message; all six Mimi clinic-path scenes remained usable through the CHF 385 handoff. The completed walkthrough reported no browser console errors. This did not exercise real providers, own-voice cloning, telephone transport or PR #29's unmerged opt-in suite.

- 68 automated tests with synthetic HTTP responses. Coverage includes warning signs, provider failure/deadlines, consent, image/audio validation, bounded streaming, session ownership, shared care/run cache, safe phone links, clinic normalization/ranking, legacy authorization, the seven-role workflow, exact policy citations, Gradium clone/localize/preview/save/delete contracts and synthetic scenario arithmetic.
- JavaScript syntax checks for both `app.js` and `voice.js`, formatting, HTML identifier binding checks and generated OpenAPI export.
- Gemini Live end to end against the real API (`gemini-3.8-live`): REST-minted single-use token locked to model, prompt and tools; constrained v1alpha session; a text turn triggered `assess_and_find_vets`, `/live/tool-calls` ran the workflow, and Gemini answered in audio with transcripts using the result. Browser capture and playback are now implemented; human microphone testing remains pending. See [Gemini Live](GEMINI_LIVE.md).
- Real API access checks: `gemini-3-flash-preview` text, synthetic PNG and silent WAV; `gemini-3.1-pro-preview` text; `gemini-embedding-001` embeddings. Each returned HTTP 200 with the expected response kind. See [sanitized results](model-access-check.json).
- The later multimodal architecture check used `gemini-3.8-flash` for three synthetic requests: structured text, a tiny PNG and a one-page invoice PDF. All returned HTTP 200 with the expected JSON; PDF ID, currency, total and page matched. See [multimodal results](multimodal-model-access-check.json). This verifies access, not a document-upload feature or model quality.
- Browser walkthrough at the existing narrow in-app viewport: all six Mimi clinic-path scenes; slot review and explicit demo approval gates; CHF 385 clinic / CHF 510 home estimates; taxi script and claim checklist.
- Browser multilingual integration: a fictional Chinese message produced a German script with English subtitles through live Gemini. The translated script preserved the instruction to ask the price without making a booking, and included the AI-assistant disclosure.
- Browser agent integration: a no-consent run visibly skipped external providers; an opt-in synthetic routine-checkup request returned real Gemini guidance and a completed care-agent trace in approximately 4.7 seconds, with clinic search skipped because location consent was off.
- Missing Gradium configuration visibly disables paid voice operations while retaining the recording setup interface. Frontend review fixed replacement-recording races and overlap with voice operations.

Browser timings are isolated observations, not latency guarantees. Model smoke checks establish access, not clinical accuracy or multilingual speech quality. One Starlette/httpx test-client deprecation warning remains; the tests pass.

## Story documentation alignment

The [120-second scenario](DEMO_STORY.md), [four-language delivery requirements](VOICE_CONCIERGE.md#language-and-delivery-requirements) and [frontend palette/layout](controller-frontend-contract.md#8-journey-layout-and-visual-requirements) were aligned on 2026-10-10 with the existing models, scripts and demo arithmetic. This update changes documentation only.

The existing localhost rehearsal was also walked through all six clinic-path scenes at a 1280 × 720 viewport. The 16:30 preference gate, CHF 385 / CHF 510 cards, final approval gate, 16:05 taxi → 16:30 vet summary and claim checklist were visible, with simulation labels retained. No browser console errors were observed. The language menus showed EN/ZH/DE/HI input and subtitle choices; own-voice setup remained visible with paid Gradium operations disabled for missing configuration. No microphone, cloning, provider audio or actual call was exercised in this walkthrough. The new acceptance checklist remains a delivery plan, not a claim that its live-language and calling tests passed.

## Not verified or not connected

- Gradium live cloning, German localization and speaker similarity: unverified, no owner sample has been uploaded. Live German TTS with the standard voice was verified on 2026-10-10 with a real key through `POST /api/v1/voice/speech` (200, 9 s WAV). That test exposed and fixed a bug: Gradium streams WAV with placeholder header sizes, which the app had rejected as incomplete.
- A physical microphone and real speakers. The browser suite (below) uses Chromium's fake capture device and a synthetic signal; it proves the capture, encoding and upload path, not a particular device or room.
- Chinese, English, German and Hindi recognition quality with representative human recordings. Only synthetic `espeak-ng` speech has been run (below); no human recording has been collected.
- Live clinic discovery: no Mapify backend URL or Google Places key was supplied. Only provider adapters and normalization are tested.
- Telephone transport, audio injection into a mobile call, actual calendar checks, appointment/taxi booking and claim submission are not connected. Mimi's calls and policy decisions are explicitly synthetic.
- Real owner-policy ingestion and vector RAG: the current retrieval baseline is lexical and searches only the demo schedule and adapted terms under `synthetic_demo`. Legacy book collections and OpenAI/Chroma indexes remain excluded.
- Imported device/report services, live video ingestion and public multi-user deployment have not been validated in this iteration.

`gemini-2.5-flash` appeared in the model listing but returned HTTP 404 for generation in this project. Credentials and recordings are not included in test fixtures or publication artifacts.

## React backend handoff (10 October 2026)

The merged teammate React frontend was integrated on top of `dd99088`. After rebasing onto the teammate’s Gradium whole-call update (#42), the local check passed 86 backend tests plus all six frontend check scripts; production compilation passed. New checks cover handoff consent, four language codes, binary audio/error propagation, backend ranking preservation and service-worker exclusion of private API responses. Real local HTTP checks exercised workflow traces, demo policy citations and missing-provider/voice-profile errors without paid provider calls. Browser verification at `/app/?live=1` covered the consent gate, typed concern, care result, insurer preparation and rendered policy excerpts with source IDs/hashes and `insurance_approval: not_obtained`; console error list was empty.

This is not a claim that PR #29's unmerged browser suite passes. No real microphone recording, EN/ZH/DE/HI speech accuracy benchmark, Gradium cloning or telephone transport was verified. This was the REST baseline; the native Live update below supersedes it. OSM remains an offline staging dataset. See [integration and evaluation boundaries](WEB_AGENT_INTEGRATION.md).

## Native Live and voice enrollment update

The React client now uses Gemini Live native audio by default in live mode. All 86 backend tests and seven frontend checks pass; production compilation passes. New offline tests cover consent, 16 kHz PCM conversion/resampling, all output audio parts, transcription, interruption, tool deduplication/round trip, mute/end cleanup and token errors.

A real browser Live connection produced a greeting transcript. A fictional Mimi text request invoked the care workflow and rendered “Contact a vet today” with backend results; browser console errors were empty. This proves connection and tool integration, not subjective audio quality or human speech recognition. No owner recording was collected. The Gradium key is still missing, so clone/localization/speaker similarity and the final own-voice rehearsal are unverified.

## Gradium credential and live TTS verification

On 10 October 2026, an owner-authorized Studio API key was configured only in the ignored local `.env`. The restarted backend reports Gradium configured. A real standard-German TTS request through `/api/v1/voice/speech` returned HTTP 200 and a 10.96-second, 48 kHz WAV. No telephone call was placed and no owner recording was uploaded.

The initial request exposed Gradium's streaming WAV headers with unknown RIFF/data lengths (`0xffffffff`). The backend now uses the teammate’s merged streaming-WAV normalization after the bounded HTTP response completes, with an additional guard rejecting incomplete PCM frames. Regression tests cover this layout, empty/partial frames, and continued rejection of truncated finite-length audio. Own-voice clone/localization and subjective speaker similarity remain unverified; earlier missing-key notes describe the previous environment.

## Own-voice clone and German preview

A real owner-authorized sample reached Gradium and returned a source ID with a pending-readiness notice. The app previously rejected that successful-but-preparing result. A regression now preserves the ID for that exact notice, while other errors are still rejected. Through the local browser session, cloning then returned 201, German localization produced a candidate, readiness succeeded, and a German own-voice preview appeared as playable audio. Speaker similarity and permanent save still require the owner's listening approval. No real call was made. Neither the recording, voice IDs nor the preview are committed.

The React enrollment now sequences clone → German localization → bounded readiness polling → preview with visible progress, top-of-page errors, a refresh action and a resume action. Recording directly in German skips localization. No cross-provider speed benchmark was performed. Provider voice storage is permanent only after save; current local browser-to-voice associations remain in server memory.

## Browser suite and real-speech checks (#25)

`PAWSE_E2E=1 python -m pytest tests/e2e` ([tests/e2e](../tests/e2e/README.md)) runs 62 Playwright tests in headless Chromium against the built React app and the original page, with provider keys blanked: 62 passed in two consecutive runs on 10 October 2026. They cover microphone capture through Chromium's fake device (audible 16 kHz PCM to Gemini Live at real-time pace; one audible mono 16 kHz WAV per turn on the REST fallback, accepted by the server validator), mic release after hang-up, drops and recording, denied-microphone messages, audio upload on the original page (stereo/44.1 kHz/8 kHz in, mono 16-bit out; short, long and non-audio files rejected before upload), the Live client against a fake socket in the real wire format (consent, ephemeral token, transcripts as text, interruption, tool round trip, dialer-only clinic calls, failures), and layout at 1280, 1440, 1920 and 390 px (no sideways scroll, no overlapping controls, WCAG 2.2 target size, centred column).

Real Gemini with synthetic speech (`espeak-ng`, 3 sentences per language, stored off git):

- `/voice/transcriptions` (`gemini-3-flash-preview`): English and German transcribed exactly (WER 0); Hindi WER 0 to 0.2 in Devanagari. Two seconds of silence produced invented text in all four languages ("Hello", "你好，请问有什么可以帮您的吗？", "नमस्ते, आप कैसे हैं?", a German sentence). Several requests ran past the 40-second upstream timeout and returned 502.
- `espeak-ng` Mandarin is not usable input: Gemini heard tone codes ("T1 F5 H4 …"). Chinese needs human recordings.
- Gemini Live in the React call: the browser streamed 3.9 s of audible 16 kHz PCM, but with digital silence afterwards Live returned no transcription. With a faint noise floor it transcribed one word of the English sentence and then "heard" Vietnamese in the noise and answered in Vietnamese. This is inconclusive for human speech, but shows Live can invent input from noise.

None of this measures accuracy for human speakers; that still needs consented recordings run through the same tests.

## Public demo deployment (10 October 2026)

- Deployed to Cloud Run (https://pawse-114215092948.europe-west6.run.app), one instance, `PAWSE_PUBLIC_DEMO=1`, Gemini and Gradium keys from Secret Manager.
- Verified on the public URL: health reports `public_demo`; the Mimi rehearsal plays all six scenes in Chromium at desktop and 390px width with no horizontal overflow; a live care request ("jumped off the wardrobe and is limping") returned urgency `contact_vet` from Gemini.
- Not verified on the public URL: clinic search (no Places key or Mapify configured, so care results are `partial`), Gradium voice cloning, Gemini Live voice.
- The React app (`/app/`) loads at desktop and 390px width with no console errors or horizontal overflow; its live flows were not walked on the public URL.
- Known: `/favicon.ico` returns 404 on the rehearsal page (also locally).
