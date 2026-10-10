# Validation record

Date: 2026-10-10. Scope: the unified `pawse/` app and its new voice, agent and evidence interfaces. This is not a certification of the imported backend.

## Passed

- Team integration alignment: 73 tests pass, including a regression first reproduced against the new public quota guard. HTTP 429 now provides the frontend-readable `detail`, no-store/nosniff headers and a session cookie. On a separate local server with public quota set to zero and provider keys blank, the browser care form displayed the specific quota message; all six Mimi clinic-path scenes remained usable through the CHF 385 handoff. The completed walkthrough reported no browser console errors. This did not exercise real providers, own-voice cloning, telephone transport or PR #29's unmerged opt-in suite.

- 68 automated tests with synthetic HTTP responses. Coverage includes warning signs, provider failure/deadlines, consent, image/audio validation, bounded streaming, session ownership, shared care/run cache, safe phone links, clinic normalization/ranking, legacy authorization, the seven-role workflow, exact policy citations, Gradium clone/localize/preview/save/delete contracts and synthetic scenario arithmetic.
- JavaScript syntax checks for both `app.js` and `voice.js`, formatting, HTML identifier binding checks and generated OpenAPI export.
- Gemini Live end to end against the real API (`gemini-3.8-live`): REST-minted single-use token locked to model, prompt and tools; constrained v1alpha session; a text turn triggered `assess_and_find_vets`, `/live/tool-calls` ran the workflow, and Gemini answered in audio with transcripts using the result. Browser microphone capture and playback are not built yet. See [Gemini Live](GEMINI_LIVE.md).
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

- Gradium live cloning, German localization, TTS and speaker similarity: no Gradium key was supplied. Provider contracts are mocked; no owner sample has been uploaded.
- Microphone permissions, real microphone capture and local uploaded-audio playback still require a manual browser check. An automated file-chooser attempt timed out, so no successful browser audio-upload test is claimed.
- Chinese, English, German and Hindi recognition quality with representative human recordings. The API audio smoke check used silence only.
- Live clinic discovery: no Mapify backend URL or Google Places key was supplied. Only provider adapters and normalization are tested.
- Telephone transport, audio injection into a mobile call, actual calendar checks, appointment/taxi booking and claim submission are not connected. Mimi's calls and policy decisions are explicitly synthetic.
- Real owner-policy ingestion and vector RAG: the current retrieval baseline is lexical and searches only the demo schedule and adapted terms under `synthetic_demo`. Legacy book collections and OpenAI/Chroma indexes remain excluded.
- Imported device/report services, live video ingestion, full desktop-width QA beyond the rehearsal and public multi-user deployment have not been validated in this iteration.

`gemini-2.5-flash` appeared in the model listing but returned HTTP 404 for generation in this project. Credentials and recordings are not included in test fixtures or publication artifacts.
