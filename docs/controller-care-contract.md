# Pawse Care Controller Contract

Implementation: [pawse/app.py](../pawse/app.py), [service.py](../pawse/service.py), [models.py](../pawse/models.py), [providers.py](../pawse/providers.py). Prefix: `/api/v1`. This controller prepares care guidance, nearby clinic results and an insurer contact; it performs no calls or bookings.

## 1. Create a care request

`POST /care/requests` → **201** `CareResult`.

`POST /care/requests?stream=true` → **200** `text/event-stream`.

Schema: `CareRequest`. This example deliberately disables external sharing and can be used without provider credentials.

<!-- schema: CareRequest -->
```json
{
  "query": "Mimi is limping after jumping off a wardrobe. What should I tell the vet?",
  "cat_name": "Mimi",
  "location": {"lat": 47.3769, "lng": 8.5417},
  "radius_km": 10,
  "language": "en",
  "red_flags": [],
  "photo": null,
  "insurance": null,
  "share_with_ai": false,
  "share_location": false
}
```

| Field | Contract |
| --- | --- |
| `query` | Up to 4,000 characters; text, photo or at least one red flag is required |
| `cat_name` | 1–80 characters, default `My cat`; included in the owner handoff |
| `location` | Optional `{lat, lng}`; valid latitude/longitude bounds |
| `radius_km` | 0.5–50, default 10 |
| `language` | Two lowercase letters, optionally `-` plus two uppercase region letters; default `en` |
| `red_flags` | At most six values from the enumeration below |
| `photo` | Optional `{mime_type, data}`; base64 JPEG/PNG/WebP, signature checked, decoded size up to 3 MB |
| `insurance` | Optional `{company, phone}`; company 1–100 characters, international phone up to 40 characters |
| `share_with_ai` | Default false; permits Gemini processing of concern, flags and optional photo |
| `share_location` | Default false; permits location-based clinic search |

Red flags: `breathing_difficulty`, `collapse`, `seizure`, `unable_to_urinate`, `suspected_poisoning`, `major_trauma`. Any reported flag forces final urgency `emergency`, including after model assessment. `stream` belongs in the query string, not the request body. A user-provided insurer number is format-validated but not verified as belonging to that insurer.

## 2. Final response

Schema: `CareResult`. The following is a synthetic partial-response example; IDs and timing are illustrative.

<!-- schema: CareResult -->
```json
{
  "type": "result",
  "request_id": "example-care-request",
  "status": "partial",
  "assessment": {
    "urgency": "unknown",
    "summary": "A veterinarian needs to assess this concern. If your cat has difficulty breathing, collapses, cannot urinate, or may have been poisoned, contact an emergency veterinarian immediately.",
    "questions": [],
    "services_to_ask_about": [],
    "source": "fallback",
    "disclaimer": "This is care navigation, not a diagnosis. A photo cannot rule out an emergency."
  },
  "clinics": [],
  "insurance": null,
  "handoff": "Cat: Mimi\nOwner's concern: Mimi is limping after jumping off a wardrobe. What should I tell the vet?\nReported warning signs: Not specified\nAI/care-navigation summary (not a diagnosis): A veterinarian needs to assess this concern. If your cat has difficulty breathing, collapses, cannot urinate, or may have been poisoned, contact an emergency veterinarian immediately.",
  "warnings": ["ai_consent_required", "location_and_consent_required"],
  "providers": {"assessment": "unavailable", "clinics": "unavailable"},
  "elapsed_ms": 12,
  "target_seconds": 60,
  "search_url": "https://www.google.com/maps/search/?api=1&query=emergency+veterinarian+47.3769%2C8.5417",
  "completeness": "Provider-limited nearby results; not an exhaustive directory. No appointment, call, or insurance approval has been made."
}
```

`status` is `complete` only when both provider stages complete; otherwise it is `partial`. A completed clinic search may return an empty list. `providers` has `assessment` and `clinics`, with terminal values `complete`, `unavailable` or `timeout`. Warning ordering can vary because providers run concurrently.

`Assessment` uses urgency `emergency`, `contact_vet` or `unknown`; source is `reported_warning_signs`, `gemini` or `fallback`. It contains a summary, up to five questions and up to six services to ask about. These are preparation for a veterinarian, not a diagnosis or verified clinic services.

### Clinic records

| Field group | Semantics |
| --- | --- |
| `id`, `name`, `address` | Provider identity and supplied address |
| `phone`, `call_url` | Nullable; the dial URI exists only for a usable international-format phone |
| `maps_url`, `website` | Nullable links from the adapter; never LLM-generated contact details |
| `location`, `distance_km` | Nullable coordinates and calculated straight-line distance |
| `rating`, `open_now` | Nullable provider facts; unknown opening hours remain null |
| `emergency_service` | `unknown` or `provider_reported`; current adapters do not establish emergency capability |
| `services`, `reasons` | Supplied service facts and deterministic ranking explanations |
| `source`, `retrieved_at`, `availability_note` | `google_places`/`mapify`, retrieval timestamp, confirmation reminder |

Sort order: reported open → unknown → reported closed, then distance ascending, then rating descending. Missing distance sorts last within the opening group. No ETA, price quote, availability slot or exhaustive-directory claim is returned.

If supplied, `insurance` returns company, phone, `call_url`, `source: user_provided`, `coverage: unconfirmed`, questions and a note. The live care request does not consult the synthetic policy or infer reimbursement.

## 3. Streaming contract

Frames are UTF-8 `data: <JSON>\n\n`, with no `event:` or `id:` field. The top-level JSON `type` selects the event. Payloads below describe fields; they are not extra wrapper objects.

| `type` | Additional fields | Meaning |
| --- | --- | --- |
| `created` | `request_id: string` | Controller allocated the ID |
| `safety` | `assessment: Assessment` | Immediate deterministic guidance |
| `insurance` | `insurance: InsuranceResult or null` | Owner-supplied contact, before providers finish |
| `progress` | `agent: assessment or clinics`, `status: starting, complete or unavailable` | Provider-stage progress |
| `assessment` | `assessment: Assessment` | Validated model guidance |
| `clinics` | `clinics: Clinic[]` | Retrieved and ranked practices |
| `heartbeat` | None | Stream is still waiting; not completion |
| `result` | All `CareResult` fields at the top level | Final authoritative result |

Examples of complete frames:

```text
data: {"type":"created","request_id":"example-care-request"}

data: {"type":"progress","agent":"assessment","status":"starting"}

data: {"type":"clinics","clinics":[]}

data: {"type":"progress","agent":"clinics","status":"complete"}

data: {"type":"heartbeat"}

```

The example omits other frames to show framing only. Actual ordering begins with `created`, `safety`, `insurance`, then stage starts. Assessment and clinic completion events may interleave. At the deadline, final `providers` can contain `timeout` even though no separate timeout progress event was emitted. There is no `duration_ms` field on progress events.

Do not wrap the final result in `{result: ...}`. Read until the final `type: result` and reconcile all fields. The internal deadline is 40 seconds and unfinished tasks are cancelled. A closed stream without a result is not a successful run; no resume route exists.

## 4. Read and delete a completed summary

| Operation | Response |
| --- | --- |
| `GET /care/requests/{request_id}` | 200 `CareResult` for the same local session |
| `DELETE /care/requests/{request_id}` | 204 with no body |
| Missing, expired or another session's ID | 404 with `detail` |

The cache contains completed results only, including nested care results from agent runs. It stores at most 100 summaries for 900 seconds, prunes on subsequent requests, and is cleared on restart. Raw photo/audio bytes are not part of the stored result. Deleting a result does not delete a Gradium voice.

## 5. Failures and acceptance

Validation failures return sanitized 422 messages. Body/origin failures return 413/403. Care and agent runs share a limit of one active operation per session and five globally; excess requests return 429. Consent, configuration, provider failure and deadline warnings normally produce a useful 201/200 partial result.

Acceptance evidence belongs in `tests/test_care.py`: independent provider concurrency, safe fallback, red-flag preservation, provider normalization, same-session retention and payload bounds. Live provider credentials are not required for these mocked contract checks.
