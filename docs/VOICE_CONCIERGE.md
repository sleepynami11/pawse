# Multilingual voice concierge

For endpoint payloads, lifecycle states and frontend/backend responsibilities, see the [voice controller contract](controller-voice-contract.md). This guide provides product flow and provider integration context.

The complete product scenario is [Mimi's 120-second journey](DEMO_STORY.md): multilingual intake → vet conversation in German → cited policy explanation → owner choice → vet/taxi handoff. The [multimodal design](MULTIMODAL_ARCHITECTURE.md) assigns these tasks to agents; [model allocation](MODEL_ALLOCATION.md) distinguishes selected models from deployed defaults.

Pawse accepts typed messages and recorded audio in English, Mandarin Chinese, German and Hindi. Gemini transcribes the original speech and prepares a German telephone script with paired subtitles. Gradium generates German WAV audio using an owner-approved voice. Hindi is one supported Indian language; the app does not claim to support every language spoken in India.

## Language and delivery requirements

| Owner input / subtitle choice | Code | Zurich recipient language | Own-voice output |
| --- | --- | --- | --- |
| English | `en` | German (`de`) | Gradium with the approved German voice |
| Mandarin Chinese | `zh` | German (`de`) | The same approved German voice |
| German | `de` | German (`de`) | The same approved German voice |
| Hindi | `hi` | German (`de`) | The same approved German voice |

Input, subtitles, recipient language and sample language are separate choices. The owner can speak Mandarin and read Mandarin subtitles while Pawse prepares German speech. The current schemas support only `de` as the recipient/synthesis target. Selecting the appropriate language for another country, or changing it after confirming a practice's preference, requires a future contract extension; it is not automatic geographic language detection today. Zurich uses standard German first, without promising Swiss German dialect.

The interface keeps its English shell and offers the four input/subtitle choices. Show the source transcript and allow corrections before translation. Preserve names, addresses, times, CHF amounts and negations. Human recording tests are still required for all four languages, accents and switching mid-conversation.

| Delivery mode | Required behavior | Status |
| --- | --- | --- |
| Talk to Pawse | Gemini Live dialogue with transcripts and server-run tools; keep Gemini's assistant voice distinct from the owner's voice | Token/tool backend and server session checked; browser mic/playback still to do |
| Prepare audio for the owner | Reviewed German text → Gradium own-voice WAV → preview/download | Endpoints exist; real synthesis requires credentials and validation |
| Open the device dialer | Owner chooses a clinic and confirms opening its `tel:` link | Manual dialer handoff; no agent participation in the call |
| Let Pawse conduct a call | Approved recipient/purpose → carrier connection → two-way translated conversation → reviewed offers and provider receipts | Planned; requires a telephony/media adapter in addition to Gradium |

For future live calls, subtitle both the assistant and the recipient, allow interruption or cancellation, and ask before booking or agreeing to costs. The German audio must identify Pawse as an AI assistant acting for the owner even when it uses the owner's voice. Keep ready-to-play audio useful independently of telephone transport.

## Record your own voice first

1. Add `GRADIUM_API_KEY` to the ignored local `.env` and restart the server. No permanent key enters browser JavaScript.
2. Record 10–30 seconds of your own clear speech in English or German. Choose the actual sample language. Listen to the local recording before uploading.
3. Confirm that this is your own voice and permit uploading it to Gradium. Creating a clone stores a custom voice in your Gradium account.
4. For an English sample, generate a German localization candidate. Wait for readiness, play the German preview, and confirm that you have listened before saving it. A German sample can be used directly.
5. Review the German script and subtitles, then generate audio with **My voice**. Standard German speech is an explicit alternative, not a silent fallback.
6. Use the audio player or download the WAV. Delete the session's created voices with the delete action when no longer needed.

The German output uses Gradium's default German accent. It is not a promise of Swiss German dialect or exact speaker identity preservation. Listen to the output before using it with a real recipient.

Gradium currently supports English, French, German, Spanish and Portuguese for cloning and speech. Chinese and Hindi are supported as **Gemini input**, not as Gradium clone sample languages. Speech recognition quality, accents and cross-language voice similarity still need human testing with representative recordings.

## API contract

All routes are under `/api/v1`. JSON bodies use strict schemas; see [generated OpenAPI](openapi.json).

| Endpoint | Input | Result |
| --- | --- | --- |
| `GET /voice/status` | Current session | Configuration booleans, own voice IDs and readiness; never a key |
| `POST /voice/transcriptions` | Base64 mono PCM WAV, `language`, `share_with_gemini: true` | Original-language transcript |
| `POST /voice/scripts` | `message`, input/subtitle languages, recipient `vet/insurer/taxi`, consent | German/subtitle pairs, `status: draft_not_sent` |
| `POST /voice/clone` | WAV, sample language, own-voice and Gradium consent | Session clone ID; German readiness if sample is German |
| `POST /voice/localizations` | Gradium consent | One German candidate; may still be processing |
| `GET /voice/localizations/current` | Current session | Candidate readiness from Gradium |
| `POST /voice/preview` | Gradium consent | Short German WAV preview |
| `POST /voice/localizations/current/save` | Gradium consent, `listened_to_preview: true` | Permanent German voice ID |
| `POST /voice/speech` | German text, `voice: my_voice/standard`, Gradium consent, optional `call_id` | WAV bytes + `X-Pawse-Call-Id` header |
| `DELETE /voice/profile` | Current session | Deletes only voices/candidates created by this session |
| `GET /demo/mimi` | None | Fictional six-scene rehearsal, scripts, cost estimates, claim checklist |

Audio input is limited to 3 MB, 0.5–60 seconds, mono 16-bit PCM WAV at 8–48 kHz. Clone input must be 10–30 seconds. The browser converts recorded audio locally before upload. Gemini requests time out after 40 seconds and Gradium requests after 45 seconds. One voice operation can run per session, up to five globally.

The first audio line of every call begins with an AI-assistant disclosure. A call is a sequence of `/voice/speech` lines: the first response carries a server-issued `X-Pawse-Call-Id`, and later lines that send it back (same browser session, within 30 minutes) are spoken as is, so the whole call keeps one Gradium voice without repeating the greeting. A missing, unknown, expired or other-session id always gets the disclosure again; an id is only remembered after its disclosed audio was produced. The app does not represent the cloned voice as the owner speaking live. Transcripts and translations are drafts to review, not verified clinical facts or insurance decisions.

## Calling boundaries

This implementation generates audio and scripts. It does not dial via a telephone network, listen to a remote recipient, inject audio into a mobile phone call, check a real calendar, book appointments, or submit claims. Device `tel:` links open a dialer only. Browser audio playback cannot be assumed to enter an OS-managed phone call; a second device or a supported telephony connection would be needed.

The voice/calling module can integrate a Twilio/SIP or comparable telephony gateway behind a separate adapter. A real conversation needs bidirectional streaming, interruption handling, recipient transcript events and owner approval before booking or agreeing to costs. Gradium's supported telephony audio formats can supply that adapter, but Gradium TTS is not itself the telephone carrier. No active telephone provider or number has been configured or verified.

Suggested future boundary (not implemented): `POST /calls/proposals` creates a recipient, purpose, script and spending limit; `POST /calls/{id}/confirm` records explicit owner approval; the carrier adapter emits connected/transcript/offer/completed events. Keep these separate from `/voice/speech` so playing a preview never places a call.

## Privacy and lifecycle

Pawse keeps audio in request/browser memory and does not write recordings to disk. Transcription sends the selected recording to Gemini. Cloning sends the selected voice sample to Gradium. Speech generation sends the reviewed German text and voice ID to Gradium. These actions have separate opt-ins.

Approved voice IDs are saved in `.pawse-private/voice.json` in local single-user mode (atomic writes, mode 0600; no recording). This local operator profile survives browser sessions and server restarts. Public-demo mode does not read or write it. `PAWSE_VOICE_PROFILE_PATH` optionally changes its location. Unapproved enrollment stays in session memory. Deletion removes the saved profile after provider deletion; partial failures retain remaining IDs for retry. Gradium voices remain in the provider account until deleted. An optional `GRADIUM_VOICE_ID_DE` is separately operator-managed and not deleted by this endpoint.

This is a localhost-only, single-user prototype. Multi-user deployment needs durable ownership, authentication, retention controls, deletion recovery and abuse limits. Recorded audio is not retained in care results. The app does not claim that downstream providers have zero retention.

## Verification

Mocked tests exercise multipart cloning, candidate readiness, preview before save, German speech, AI disclosure, session isolation, deletion retries, duration checks, explicit consent and redacted errors. Owner-authorized live checks produced a localized German clone and playable preview; local persistence and emergency reuse are covered by regression tests. Gemini text, a synthetic image and a silent WAV were accepted in [the model access check](model-access-check.json); silence acceptance is not a speech-recognition quality evaluation.

## Official references

- [Gradium custom voices](https://docs.gradium.ai/guides/voices/custom-voices)
- [Gradium voice localization](https://docs.gradium.ai/guides/voices/voice-localization)
- [Gradium REST TTS](https://docs.gradium.ai/guides/text-to-speech-rest)
- [Gradium create-voice contract](https://docs.gradium.ai/api-reference/endpoint/create-voice)
- [Gemini audio understanding](https://ai.google.dev/gemini-api/docs/audio)
