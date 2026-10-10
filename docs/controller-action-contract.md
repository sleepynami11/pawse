# Pawse Communication and Action Controller Contract

**Current:** German scripts, owner-reviewed Gradium audio and a confirm-before-opening clinic dialer tool. **Proposed v1:** a case-bound action lifecycle for real telephone, booking, calendar and taxi connectors. Nothing in this document adds a callable action endpoint. [Mimi's story](DEMO_STORY.md) is the acceptance scenario; its calls and outcomes remain simulated.

## 1. Current delivery modes

| Mode | Existing boundary | What the UI may claim |
| --- | --- | --- |
| Talk to Pawse | `/live/tokens`, `/live/tool-calls` backend; browser audio pending | Assistant conversation once connected; separate from a telephone call |
| Draft in German | `POST /voice/scripts` | `draft_not_sent`, paired German/subtitle lines |
| Generate own-voice audio | Gradium enrollment/localization/preview/save, then `POST /voice/speech` | Generated WAV available to play/download; no proof that a recipient heard it |
| Manual dialer | Live `open_clinic_call` result and owner confirmation | Open the returned `tel:` link; call status remains unknown |
| Automated recipient call | No connected telephone transport/media bridge | Planned only |

The [Voice contract](controller-voice-contract.md) is authoritative for current recording formats, fields and errors. The current speech route accepts text and session voice choice; it does **not** enforce the proposed revision-bound action approval described below.

Chinese, English, German and Hindi input/subtitles are independent from the recipient language. Initially use German (`de`) for Zurich recipient scripts. Gradium owns the approved German voice profile; Gemini Live assistant audio is not the owner's clone. Preview/save the owner's voice before the urgent story; a standard voice requires an explicit choice. No private key or arbitrary provider `voice_id` belongs in client requests.

## 2. Proposed controller and routes

Prefix: `/api/v1/cases/{case_id}/actions`. The voice module owns communication and telephone transport; orchestration owns case dependencies and approval checks. Every route derives case ownership on the server.

| Proposed route | Input | Success |
| --- | --- | --- |
| `POST /` | `ActionCreate` with current case `If-Match` | 201 `ActionDraft`, action ETag |
| `GET /{action_id}` | Same-owner case | 200 draft/state/receipts, ETag |
| `PATCH /{action_id}` | Draft changes with action `If-Match` | 200 new draft revision; previous approval invalidated |
| `POST /{action_id}/approve` | `ActionApproval` and action `If-Match` | 200 approved revision with expiry |
| `POST /{action_id}/execute` | Server-issued approval ID, action `If-Match`, `Idempotency-Key` | 202 execution record, or existing record for an identical retry |
| `POST /{action_id}/cancel` | Action `If-Match` | 202 cancellation request; await provider acknowledgement if dispatched |

A proposed `ActionDraft` contains `action_id`, `case_id`, `case_revision`, `revision`, `kind`, `recipient`, `purpose`, `script`, `voice_selection`, `evidence_refs`, `constraints`, `missing_requirements`, `status` and timestamps. **Proposed v1 accepts only `kind: phone_call`.** Vet, insurer and taxi conversations use that kind with different recipients and purposes. Direct booking/calendar connector kinds require their own payload schemas before acceptance. A script/audio-only flow can continue through the current voice endpoints.

`ActionCreate` supplies `kind`, selected recipient reference, purpose, script request, voice selection and constraints. The server resolves verified contact details and referenced facts; an LLM cannot insert a new destination number or a provider receipt. Example proposed body, with the current case ETag in `If-Match`:

```json
{
  "kind": "phone_call",
  "recipient_ref": {"type": "vet", "contact_id": "contact_selected_clinic"},
  "purpose": "Ask about an appointment for Mimi today.",
  "script_request": {
    "message": "The owner reports that Mimi is limping after a jump. Ask when she can be seen.",
    "input_language": "en",
    "subtitle_language": "hi",
    "recipient_language": "de",
    "share_with_gemini": true
  },
  "voice_selection": "my_voice",
  "evidence_refs": ["ev_owner_turn_2"],
  "constraints": {
    "allowed_disclosures": ["cat_name", "reported_concern"],
    "allow_booking": false,
    "max_charge_minor": null,
    "currency": "CHF"
  }
}
```

Purpose is 1–500 characters; script message is 1–4,000; reference lists are bounded to 20 existing same-case records/fields. `share_with_gemini: true` permits draft generation, not a phone call. `allow_booking` defaults false; a null charge limit grants no spending authority. A booking-capable revision must additionally specify the requested timezone-aware slot and a nonnegative owner-approved minor-unit charge limit. Server-set IDs, hashes, states and receipts are not patchable client fields.

## 3. Draft, languages and own-voice binding

| Draft component | Required contract |
| --- | --- |
| Recipient | Type `vet`, `insurer` or `taxi`, display name, verified contact reference, normalized international phone and verification source/time |
| Purpose | Narrow request: ask availability, clarify exclusions, confirm a reviewed slot or arrange an approved ride |
| Script | German lines with paired owner-language subtitles, language codes and a content hash; identify Pawse as an AI assistant acting for the owner |
| Voice selection | `my_voice` or explicitly chosen `standard`; server-resolved profile version and preview status |
| Evidence | Same-case, current-version references; unknown facts remain questions |
| Constraints | Owner-approved choices and limits: requested slot, maximum charge if applicable, disclosure scope, excluded actions and conditions requiring another confirmation |

`input_language` and `subtitle_language` accept `en`, `zh`, `de`, `hi`; `recipient_language` initially accepts only `de`. Own-voice `sample_language` is a separate enrollment field, following the current Gradium language contract. Do not promise a Swiss dialect when only German localization has been selected and checked.

Owner-provided insurer contact is allowed as an explicitly reviewed contact source; a generated number is not. Clinic phones come from selected provider records, and taxi contacts require a configured source. Verification confirms the chosen destination, not the recipient's authority to promise coverage.

## 4. Approval and execution state

```text
draft -> review_required -> approved -> queued -> in_progress
                                      |            |
                                      +-> failed   +-> completed / failed / outcome_unknown
any undispatched state -> cancelled
queued / in_progress -> cancellation_requested -> cancelled / outcome_unknown
approved -> review_required when content or dependencies change
approved -> expired when approval time elapses
```

Proposed `ActionApproval` binds `action_revision`, `case_revision`, reviewed script hash, destination, voice-profile version, allowed disclosures and constraints. Require an explicit owner gesture; the model cannot approve. The server issues the approval ID with a proposed five-minute dispatch expiry. Case/script/contact/voice/limit changes invalidate approval; undispatched expired actions require review again. In-flight actions retain their original approved scope and must pause or request new confirmation before exceeding it.

The execute endpoint rechecks all dependencies and the approval for a new dispatch. Use an idempotency key scoped to owner + case + action + revision, persist the request fingerprint before calling a provider, and reuse the same execution record on identical retries. Authenticate ownership and resolve an existing key before applying fresh-dispatch ETag/expiry checks, so retrying an already accepted request returns its record even if its state has advanced. A reused key with different inputs returns 409. After a timeout, reconcile the provider call ID before retrying; never blindly redial or repeat a booking.

Cancellation is a request, not proof an external action stopped. A provider may already have completed it. Record that actual result and tell the owner when cancellation or the outcome cannot be confirmed. Keep a visible stop/take-over control during an eventual live call; its media behavior must be tested with the chosen carrier.

## 5. Provider events and receipts

Provider webhook/media integration remains unselected. Its adapter must authenticate callbacks, deduplicate event IDs, correlate the execution, handle reordered events and normalize outcomes. The frontend cannot POST a fabricated receipt.

| Record | Required fields |
| --- | --- |
| `ExecutionRecord` | `execution_id`, `action_id`, approved revision, provider, provider call/job ID, dispatch timestamp and transport status |
| `ActionReceipt` | `receipt_id`, execution ID, provider event ID, received timestamp, normalized outcome, supporting evidence and unresolved conditions |
| Conversation segment | Turn ID, actual speaker, source language/text, translated subtitle, timestamp and whether it is a draft or an observed recipient reply |

Transport status and business outcome are separate. A call may connect/end while `appointment`, `coverage` or `taxi_acceptance` stays unconfirmed. Label `completed` only for the action's defined goal when attributable evidence supports it; otherwise use `outcome_unknown` or report the remaining requirement. Store timezone-aware dates (`Europe/Zurich` for display) and distinguish an offered slot, owner preference and confirmed appointment.

German WAV playback or a `tel:` URL cannot inject audio into a phone call. Real speaking/listening needs a telephone carrier, bidirectional media transport, compatible audio conversion, interruption control, transcription, subtitles and consented voice selection. Gradium provides speech; it is not the telephone carrier. Provider-specific callback fields belong in a later adapter contract.

## 6. Mimi action sequence

| Step | Required evidence before next action |
| --- | --- |
| Ask the vet about care | Reviewed concern, selected clinic/contact and disclosure approval |
| Choose 16:30 or a home visit | Actual offer and price; calendar availability is checked only with a connected, permitted calendar |
| Ask the insurer | Owner-entered insurer/policy details, relevant documents and separate disclosure approval; record exclusions/conditions |
| Compare clinic/home options | Explicit estimate inputs and assumptions; never infer coverage from a generated answer |
| Confirm 16:30 | Owner choice plus limits: itemised invoice, ask before physio; obtain clinic confirmation |
| Arrange taxi at 16:05 | Owner-approved pickup/destination/cost and actual carrier acceptance; no automatic booking from a story scene |
| Produce final handoff | Confirmed outcomes plus unresolved items, reviewed audio and evidence checklist; deadline sourced to the applicable policy |

The story's 16:30 slot, CHF 385/510 totals and 30-day claim deadline remain demo values. Full assumptions and timing are in [Demo story](DEMO_STORY.md).

## 7. Errors and acceptance

Proposed failures: 404 inaccessible action; 409 missing prerequisite, expired approval or conflicting idempotency key; 412 stale ETag; 422 invalid language/contact/constraint; 428 missing precondition; 429 bounded execution queue; 503 connector not configured. Accepted executions report provider failures in their execution record without pretending the task completed.

Before enabling a connector, test altered script/recipient/voice after approval, duplicate execute requests, disconnect after dispatch, reordered/duplicate callbacks, wrong-owner access, unknown recipient replies, cancellation races and offers above the owner's limit. Validate all four input/subtitle languages with German delivery, then complete a consented test call and verify receipt accuracy. Mocked story dialogue is not that test.
