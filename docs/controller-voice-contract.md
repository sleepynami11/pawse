# Pawse Voice Controller Contract

Implementation: [pawse/voice.py](../pawse/voice.py). Prefix: `/api/v1/voice`. Gemini handles transcription and German scripts; Gradium handles own-voice cloning, localization and audio. The current output is playable WAV, with `telephony: not_connected`.

## 1. Routes and schemas

| Method and path | Request model | Success response | Handler |
| --- | --- | --- | --- |
| `GET /status` | None | 200 voice status dictionary | `voice_status` |
| `POST /transcriptions` | `TranscriptionRequest` | 200 `Transcript` | `transcribe` |
| `POST /scripts` | `ScriptRequest` | 200 `CallScript` | `script` |
| `POST /clone` | `CloneRequest` | 201 voice status | `clone` |
| `POST /localizations` | `VoiceConsent` | 202 voice status | `localize` |
| `GET /localizations/current` | None | 200 refreshed voice status | `localization_status` |
| `POST /preview` | `VoiceConsent` | 200 `audio/wav` bytes | `preview` |
| `POST /localizations/current/save` | `SaveVoice` | 201 voice status | `save_voice` |
| `POST /speech` | `SpeechRequest` | 200 `audio/wav` bytes | `speak` |
| `DELETE /profile` | None | 204, no body | `delete_voice` |

JSON request schemas are generated in [OpenAPI](openapi.json). Voice-status responses are currently dynamic dictionaries; their stable fields and subtleties are specified in section 4. No route accepts a client-selected owner or provider voice ID.

## 2. Multilingual input and script drafting

Transcription input is `{audio: {data: base64Wav}, language, share_with_gemini: true}`. `audio.data` must contain an actual complete WAV, not a URL or browser WebM recording. Convert recorded audio before submission.

Accepted WAV: mono, 16-bit PCM, 8–48 kHz, 0.5–60 seconds and at most 3 MB decoded. Response is `{text: string}` with at most 4,000 characters; silence/unintelligible input can produce empty text. Display it for review before starting another request.

Transcription `language`, script `input_language` and `subtitle_language` accept `en`, `zh` (Mandarin Chinese), `de` and `hi` (Hindi). These are the input options implemented in this app, not measured accuracy guarantees. Hindi does not imply support for every Indian language.

Schema: `ScriptRequest`.

<!-- schema: ScriptRequest -->
```json
{
  "message": "My cat Mimi is limping after jumping off a wardrobe. Can a vet see her today?",
  "input_language": "en",
  "subtitle_language": "en",
  "target_language": "de",
  "recipient": "vet",
  "share_with_gemini": true
}
```

The message is 1–4,000 characters. `recipient` is `vet`, `insurer` or `taxi`. The response is a draft, not a message sent to that recipient. Synthetic response example, schema `CallScript`:

<!-- schema: CallScript -->
```json
{
  "lines": [
    {
      "german": "Guten Tag, hier ist Pawse, die KI-Assistenz im Auftrag der Katzenhalterin oder des Katzenhalters.",
      "subtitle": "Hello, this is Pawse, the AI assistant speaking on behalf of the cat's owner."
    },
    {
      "german": "Mimi hinkt nach einem Sprung vom Schrank. Kann sie heute untersucht werden?",
      "subtitle": "Mimi is limping after jumping off a wardrobe. Can she be examined today?"
    }
  ],
  "target_language": "de",
  "status": "draft_not_sent"
}
```

Gemini drafts 1–5 content lines, bounded to 2,500 German characters total; the server prepends a fixed AI-assistant disclosure and paired subtitle. Each German line is at most 900 characters and each subtitle at most 1,600. Preserve numbers, uncertainty and negation when reviewing; recipient replies and appointments are not generated as facts.

## 3. Own-voice lifecycle

1. **Record:** capture 10–30 seconds of the owner's voice. Obtain own-voice and Gradium-sharing consent separately. `CloneRequest` contains `audio`, `sample_language`, `own_voice_consent: true`, `share_with_gradium: true`.
2. **Clone:** `POST /clone` creates a source voice in Gradium. A session with existing voice state must delete it before replacement. Sample languages are `en`, `de`, `fr`, `es`, `pt`; Chinese/Hindi cloning samples are not exposed by this route.
3. **Localize:** for a non-German source, `POST /localizations` with `VoiceConsent` creates one German embedding candidate. A 202 response means the candidate has been requested, not that it is ready to save.
4. **Poll:** `GET /localizations/current` refreshes `candidate_ready`. Poll sequentially and stop after a terminal error, navigation or cancellation; this call consumes a voice-operation slot.
5. **Preview:** once ready, `POST /preview` generates German WAV using the candidate. Play it for the owner. This records that a preview was generated, not proof a human listened.
6. **Save:** after playback and owner acknowledgement, `POST /localizations/current/save` with `listened_to_preview: true` creates a reusable German voice. The server also checks candidate readiness and that a preview was generated.
7. **Speak:** submit reviewed text to `/speech` with `voice: my_voice`. Play or download the returned audio.

Schema: `VoiceConsent`, used for localization and preview:

<!-- schema: VoiceConsent -->
```json
{"share_with_gradium": true}
```

Schema: `SaveVoice`:

<!-- schema: SaveVoice -->
```json
{"share_with_gradium": true, "listened_to_preview": true}
```

**German-source exception:** cloning a German sample immediately sets the session's German voice ID. Skip localization and candidate saving; use `/preview` for owner review before speech. The backend does not require a saved-candidate acknowledgement for this direct-German path. Frontend review remains part of the interaction contract.

**Configured-voice exception:** `GRADIUM_VOICE_ID_DE` can make `my_voice_ready` true without a session source. `/speech` can use it, but `/preview` requires a session source and cannot preview that environment-only voice through the candidate endpoint.

## 4. Voice status and UI precedence

| Field | Type / meaning |
| --- | --- |
| `gradium_configured`, `gemini_configured` | Booleans based on server credential presence |
| `input_languages` | Code-to-label map for English, Mandarin Chinese, German and Hindi |
| `speech_language` | `de` |
| `telephony` | `not_connected` |
| `source_id` | Nullable source voice ID created in this session |
| `german_voice_id` | Nullable saved/direct-German session voice ID |
| `candidate_ready` | Boolean for localization candidate readiness |
| `candidate_pending` | Whether a candidate ID exists; not the inverse of readiness |
| `my_voice_ready` | Whether a German session voice or server-configured own voice exists |
| `sample_language` | Nullable source sample language |

Render state in this order: own voice ready → candidate ready → candidate pending → source cloned → no voice. `candidate_pending` can remain true after the candidate is ready or saved. `my_voice_ready` can be true while `german_voice_id` is null when configuration supplies the voice. Readiness does not prove that provider credentials are valid or that speech synthesis will succeed.

## 5. Generate speech and handle failures

Schema: `SpeechRequest`. German `text` is 1–3,500 characters.

<!-- schema: SpeechRequest -->
```json
{
  "text": "Mimi hinkt nach einem Sprung vom Schrank. Kann sie heute untersucht werden?",
  "language": "de",
  "voice": "my_voice",
  "share_with_gradium": true
}
```

Success is **binary WAV**, not JSON/base64. The server prepends the AI disclosure if missing and validates that the provider returned a complete playable WAV. `voice: standard` is an explicit alternative. There is no silent fallback from `my_voice` to another voice.

| Status | Meaning / recovery |
| --- | --- |
| 404 | No localization candidate in an otherwise valid source profile |
| 409 | Missing source/ready candidate/preview, duplicate candidate, existing profile or absent own voice; follow the relevant prerequisite |
| 422 | Invalid WAV, language, consent or request shape |
| 429 | Another voice operation is running, global limit reached, or source-profile capacity reached |
| 502 | Provider request or output validation failed; retain user input and retry explicitly |
| 503 | Required Gemini or Gradium key is missing |

Common app 403/413 behavior also applies. Voice has one active operation per session and five globally, separate from the care pool; at most 100 session voice profiles can be created. Gemini voice requests use a 40-second HTTP timeout; each Gradium call has a 45-second wall deadline. Stop duplicate clicks and overlapping polls. An upstream error can leave provider-side work that the app did not receive an ID for; inspect the provider library before blindly recreating it.

## 6. Deletion and retention

`DELETE /profile` deletes session-created candidate embeddings, localized voices and source voices, deduplicating identical IDs. Provider 404 on deletion is treated as already deleted. On partial failure, remaining IDs are kept for retry; do not show deletion complete until HTTP 204.

Pawse stores voice IDs and flags in process memory, not raw recordings. Restart or loss of the browser session does not delete Gradium resources. A server-configured `GRADIUM_VOICE_ID_DE` is never deleted by session deletion. Provider retention is separate from Pawse's summary TTL; see [Voice concierge](VOICE_CONCIERGE.md).

## 7. Integration boundary and acceptance

The coordinator may supply reviewed handoff text, but it does not automatically trigger these operations. Playing a WAV or opening a `tel:` link does not make Pawse speak into a phone call. Telephone transport, recipient audio, live interruption handling and call outcomes remain future integration work.

`tests/test_voice.py` covers request bounds, consent, state order, provider contracts, speech validation and deletion behavior with mocks. Real cloning, localization and voice similarity require a configured Gradium account and an owner sample; do not present mocked checks as successful live voice verification.
