# Validation record

Date: 2026-10-10. Scope: the new `pawse/` application, not a certification of the imported backend.

## Passed

- 20 automated tests using synthetic HTTP responses: warning-sign preservation, consent gates, input/photo validation, safe dial URLs, unknown opening hours, clinic filtering/ranking, Mapify and Places contracts, partial provider failures, timeout cancellation, session isolation, deletion, legacy cat authorization, named-SSE forwarding, and OpenAPI result schemas.
- Python application imports and syntax checks.
- JavaScript syntax check with `node --check pawse/static/app.js`.
- English Markdown local-link checks and publication scan for the local Gemini credential.
- Real Gemini structured text response with `gemini-3-flash-preview` using synthetic test input.
- Browser workflow: no-consent partial result; then an opt-in real Gemini request using synthetic routine-check-up text. The latter returned care guidance and call notes in approximately 4.8 seconds with clinic discovery unavailable.

The browser timing is one observation, not a latency guarantee or a clinic-search benchmark. A Starlette/httpx test-client deprecation warning was emitted; all tests passed.

## Not verified or not implemented

- Live clinic discovery: no Mapify backend URL or Google Places key was supplied.
- Real cat-photo assessment, microphone permission/dictation, and device phone calls.
- Live execution of legacy device, report and health-analysis flows: their runtime and data services are not configured.
- Gemini Live continuous voice, insurance coverage lookup, appointment booking, insurer claims, and automatic calls are not implemented.
- Production authentication, persistent care records and multi-user hosting are outside this local prototype.

`gemini-2.5-flash` appeared in the model listing but returned HTTP 404 on generation for this development setup. `gemini-3-flash-preview` returned HTTP 200 and passed the structured response validation. The key was neither printed nor committed.
