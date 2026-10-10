# Pawse Case and Agent Handoff Contract

**Proposed v1 — not implemented.** The current backend stores completed care summaries, not a persistent multimodal case. This contract defines the shared state needed to connect Voice, Vision, Document, Policy Evidence and Communication agents. Existing `CareResult`, `AgentRunResult` and Live tool responses retain their current schemas.

## 1. Case controller

Proposed prefix: `/api/v1/cases`. The orchestration module owns validation and merges; domain modules own their result payloads. Frontend and agents may propose updates, but the server assigns IDs, revisions, ownership and timestamps.

| Proposed route | Request | Success |
| --- | --- | --- |
| `POST /cases` | `CaseCreate` below | 201 `CaseSnapshot`, `Location` and `ETag` |
| `GET /cases/{case_id}` | Same-owner session | 200 `CaseSnapshot` and `ETag` |
| `PATCH /cases/{case_id}` | Allowed owner fields plus required `If-Match` | 200 updated snapshot and `ETag` |
| `DELETE /cases/{case_id}` | Required `If-Match` | 202 deletion job; erase local state and track provider cleanup |
| `GET /cases/{case_id}/deletion` | Same-owner session | 200 cleanup state: `pending`, `complete` or `retry_required` |

These paths are proposals. `GET /care/requests/{request_id}` still retrieves only an existing completed care result. A future case may reference that result, but `case_id`, `request_id`, `run_id` and Live function-call `id` remain distinct identifiers.

Example proposed `CaseCreate`:

```json
{
  "cat_name": "Mimi",
  "concern": "Mimi is limping after jumping off a wardrobe.",
  "scope": "owner_private",
  "languages": {
    "input_language": "zh",
    "subtitle_language": "en",
    "recipient_language": "de"
  }
}
```

`cat_name` is 1–80 characters; concern is 1–4,000. Input/subtitle languages accept `en`, `zh`, `de`, `hi`; recipient language is initially `de`. `scope` is `owner_private` or `synthetic_demo`, immutable after creation. Creating a case stores the owner account locally; it grants no Gemini, Gradium, location or action consent. Production hosting requires authenticated case ownership before private uploads are enabled.

`PATCH` permits `cat_name`, `concern` and `languages`, not result status, provider receipts, revision, scope or ownership. Every successful mutation returns a new opaque ETag. Require `If-Match` for mutations to existing resources: 428 if absent, 412 if stale. Return 404 for unknown and other-owner resources alike.

## 2. Shared records

| Record | Required fields / meaning |
| --- | --- |
| `CaseSnapshot` | `case_id`, integer `revision`, `scope`, cat/concern/languages, timestamps, `facts`, `evidence`, `agent_results`, `unresolved`, `action_ids`, `status` |
| `CaseFact` | `fact_id`, semantic `field`, `value` or null, `unit`/`currency` or null, `origin`, `review_state`, `evidence_refs`, `unknown_reason` or null |
| `EvidenceRef` | `evidence_id`, `case_id`, `scope`, `source_kind`, `source_id`, `source_version`, `source_sha256` or null, `locator`, `original_text`, `language`, `captured_at` |
| `AgentResult` | `result_id`, `case_id`, `based_on_revision`, `agent_role`, `status`, `fact_ids`, `evidence_refs`, `warnings`, `created_at` |
| `ActionDraft` / `ActionReceipt` | Defined by the [Action contract](controller-action-contract.md); never inferred from a case summary |

`CaseSnapshot.status` is `open`, `review_required` or `ready_for_handoff`. The last value means there is a reviewable summary; it does not mean treatment, payment or any external action has occurred. Deleting a case makes it unavailable to new agents/actions immediately; the deletion-status resource remains until cleanup completes.

`CaseFact.origin` is `owner_reported`, `extracted`, `observed`, `calculated` or `provider_confirmed`. `review_state` is `unreviewed`, `accepted`, `rejected` or `conflicted`. Acceptance means the owner checked the transcription/extraction; it does not turn an owner's report into a clinical diagnosis or insurer confirmation.

`EvidenceRef.source_kind` is `owner_statement`, `photo`, `video`, `document`, `clinic_provider` or `connector_receipt`. Document/photo/video bytes require a hash. The locator is type-specific: document page/section, video time range, photo ID, owner turn ID, clinic record ID or connector event ID. Document `original_text` is a source excerpt; visual evidence uses a nullable excerpt and a separate observed fact. Translation or paraphrase never overwrites source text.

Illustrative fact, linked to an owner-statement evidence record in the same snapshot:

```json
{
  "fact_id": "fact_mimi_mechanism",
  "field": "incident.reported_mechanism",
  "value": "jumped off a wardrobe",
  "unit": null,
  "currency": null,
  "origin": "owner_reported",
  "review_state": "accepted",
  "evidence_refs": ["ev_owner_turn_2"],
  "unknown_reason": null
}
```

This is a reported mechanism, not a final accident classification under an insurance policy. Unknown deductible balance, open hours, diagnosis or price must remain null with a reason. `0`, `false` and an empty string must not stand in for unknown values.

## 3. Agent merge protocol

1. Capture `case_id`, `revision`, scope and the minimum consented input for the selected agent. Workers cannot select another owner or change sharing permissions.
2. Return `AgentResult` with `status: complete | partial | unavailable | cancelled`, the captured `based_on_revision`, evidence and explicit missing fields. These are proposed result statuses, not replacements for current `AgentTrace.state` values.
3. Validate the result against its domain schema and resolve every evidence reference to the same owner's case and source version. Reject invalid citations and document instructions that try to change tool behavior.
4. Atomically merge only if the captured case revision still matches. Otherwise retain it as an unapplied stale result for review/retry; never overwrite a newer owner correction. Concurrent results from the same revision need serialized validation and an explicit rebase or rerun after the first merge.
5. Preserve conflicts as separate facts. A model summary cannot silently replace an owner report, unreadable text or a confirmed provider reply. Mark downstream summaries and approvals stale when their inputs change.

Reported warning signs take the existing care priority and cannot be downgraded by photo, document or language-model output. Clinic search and care can complete before policy extraction. Document failure creates an unresolved evidence item; it must not block the owner from contacting a vet.

## 4. Estimates and action preparation

Calculate costs in application code using integer minor currency units. Store the formula, inputs, evidence references, currency and rounding rule. A policy schedule, deductible remaining, treatment quote, exclusions and selected options are independent inputs. Missing any required input yields `incomplete`, not a confident price.

The Mimi fixture's CHF 385/510 comparison follows the explicit assumptions in [Demo story](DEMO_STORY.md); it is not a default price for an owner case. Keep coverage `unconfirmed` until an actual, attributable insurer response is recorded. Even that response must retain its conditions and scope; the system must not widen it into blanket coverage.

Only accepted facts and clearly labeled unresolved questions may enter an action draft. Approvals bind to the case revision, script, recipient, voice and spending/booking limits. Any dependency change requires review again; already executed receipts remain historical evidence and cannot be rewritten by a new draft.

## 5. Errors, deletion and acceptance

Proposed errors use safe `{detail: string}` bodies: 404 inaccessible case, 409 invalid state/cross-scope merge, 412 stale revision, 422 invalid fields/citations, 428 missing precondition, 429 bounded work queue, 503 unavailable dependency. Keep payloads, tokens and private excerpts out of errors/logs.

Deletion cancels pending analysis, disables new actions and removes case files/index entries, derived facts and audio under the case retention policy. Already dispatched external actions need explicit connector cancellation; deleting a case cannot undo a call or booking. Own-voice profiles have a separate lifecycle and are deleted through their own endpoint. Report provider cleanup failures as `retry_required`, without claiming deletion succeeded.

Before implementation is enabled, verify owner isolation, demo/private separation, competing revisions, late results after deletion, conflict preservation, citation version mismatch, incomplete estimates and approval invalidation. No shared case storage, automatic revision merge or durable action history exists in the current app.
