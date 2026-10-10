# Pawse Document Controller Contract

**Proposed v1 — not implemented.** The Document Agent will extract policy schedules, terms, invoices and veterinary records into reviewable facts and page citations. A successful Gemini PDF access probe is recorded in [Model allocation](MODEL_ALLOCATION.md); it does not establish an upload pipeline. Current `/knowledge/search` accepts only the fixed demo corpus.

## 1. Scope and ownership

The evidence/data module owns intake, extraction, source retention and review. The [Case contract](controller-case-contract.md) supplies authenticated ownership, scope, revisions and common evidence records. The selected extraction model is `gemini-3.8-flash`; the app must validate structured results before exposing them.

Proposed prefix: `/api/v1/cases/{case_id}/documents`. No document URL fetching, private GitHub storage or document bytes in analytics. Uploaded content, including instructions inside a PDF, is evidence data and cannot grant consent or trigger tools.

## 2. Proposed routes

| Route under the prefix | Input | Success / responsibility |
| --- | --- | --- |
| `POST /` | Multipart `file` plus JSON `metadata`; case `If-Match` | 202 `DocumentRecord`; validate and queue extraction |
| `GET /{document_id}` | Same-owner case | 200 `DocumentRecord`, candidate facts and evidence; document `ETag` |
| `POST /{document_id}/review` | Accept/reject/correct field decisions; document `If-Match` | 200 reviewed record; publish accepted facts to the case with a revision check |
| `DELETE /{document_id}` | Document `If-Match` | 202 deletion status; cancel work and invalidate dependent evidence/actions |
| `GET /{document_id}/deletion` | Same-owner case | 200 `pending`, `complete` or `retry_required` |

Upload metadata example:

```json
{
  "kind": "policy_schedule",
  "language_hint": "de",
  "share_with_gemini": true
}
```

`kind`: `policy_schedule`, `policy_terms`, `invoice`, `vet_record` or `unknown`. `language_hint` is optional; extraction stores detected language independently. Gemini sharing requires literal `true` for this first extraction route. Do not infer it from previous voice or care consent. `case_id` supplies scope; the client cannot override the document owner or private/demo classification.

### Initial application limits

These are **proposed product limits**, not provider capacity claims. Implement all checks before accepting requests.

| Boundary | Proposed v1 rule |
| --- | --- |
| Formats | PDF, JPEG or PNG verified from file content; one file per request |
| File size / pages | At most 3,000,000 bytes; PDF at most 20 pages; image counts as one page |
| Case budget | At most ten active documents and 30,000,000 stored source bytes per case |
| Concurrency | One extraction per case, five globally; bounded queue |
| Deadline | 60-second extraction deadline; failure remains retryable on explicit owner request |
| Storage | Private temporary files, expire within 24 hours; deleting the case/document starts cleanup immediately |

The existing middleware caps mutation bodies at 4,500,000 bytes. A 3 MB multipart upload can fit without raising that bound; verify actual encoded size and streamed-byte enforcement. Reject encrypted, malformed, oversized or unsupported content before provider upload. Ignore embedded attachments and scripts; do not execute active PDF content or follow embedded links.

## 3. Extraction and provenance

`DocumentRecord` fields: `document_id`, `case_id`, immutable `version`, `source_sha256`, `kind`, `language`, `page_count`, `status`, `created_at`, `expires_at`, `facts`, `evidence`, `warnings`, `unknown_fields`. Re-uploading changed bytes creates a new document/version; do not overwrite a citation's source.

Status progression:

```text
validating -> queued -> extracting -> review_required -> reviewed
                    \-> failed
any retained state -> deleting -> deleted / deletion_retry_required
```

The deletion-status route reports the cleanup state; ordinary reads of a deleted resource return 404. Results arriving after cancellation/deletion are discarded and cannot recreate the document.

| Document kind | Candidate fields | Consumer |
| --- | --- | --- |
| Policy schedule | Insurer contact, policy identifier, insured pet, effective dates, selected benefits, annual limit, stated deductible and reimbursement rate | Policy retrieval and owner review |
| Policy terms | Edition, clauses, conditions, exclusions and stated claim deadlines | Cited evidence; no assumption that optional benefits were purchased |
| Invoice | Issuer, date, currency, item descriptions/amounts and total | Evidence checklist and deterministic estimate reconciliation |
| Vet record | Visit date, clinician-authored observations/instructions and document provenance | Owner-reviewed care handoff; no new model-authored diagnosis |

Each extracted `CaseFact` starts `origin: extracted`, `review_state: unreviewed`. Use null with a reason for unreadable or absent values. A deductible amount printed in a policy is not the current remaining deductible. Identity, edition/effective dates, money and contact numbers need owner review before use.

Every document `EvidenceRef` includes document ID/version/hash, **one-based PDF page number**, optional section, original-language excerpt and language. Preserve a stable page rendering for owner verification. OCR/model text is provisional until checked against the page; an unverified transcription must not be labeled an exact quote. Store translations and summaries separately from the excerpt. Reject out-of-range pages and unmatched citations instead of inventing a source.

## 4. Review and evidence publication

Example proposed review body (document revision in `If-Match`):

```json
{
  "case_revision": 4,
  "decisions": [
    {"fact_id": "fact_policy_currency", "decision": "accept"},
    {"fact_id": "fact_policy_contact", "decision": "reject"}
  ]
}
```

Decisions apply only to existing facts: `accept`, `reject`, or `correct`. A `correct` decision additionally requires `corrected_value` and a nonempty `reason`; the server validates the value against that field's type, rejects the original fact and creates a new accepted `origin: owner_reported` fact with an owner-statement evidence record. It does not rewrite the original excerpt or claim the correction was extracted from it. Reject duplicate/unknown fact IDs and correction fields on accept/reject decisions. Compare document ETag and `case_revision` atomically; return 412 on either stale value. Publishing changes the case revision and invalidates dependent drafts.

Only accepted facts and reviewed source passages may enter the private retriever. Unreviewed or rejected values remain visible as extraction work, not approved insurance facts. A document can be `reviewed` with unresolved fields; retrieval must return those gaps. Provider-sharing consent for extraction does not authorize sending documents to a veterinarian or insurer.

The [Knowledge controller](controller-knowledge-contract.md#7-proposed-private-evidence-search) owns retrieval and grounded answers. It receives case-scoped evidence and preserves source versions. It never silently falls back from private evidence to the demo policy. No vector database is required for the first small corpus.

## 5. Errors and deletion

Proposed responses: 404 inaccessible case/document; 409 invalid review/lifecycle; 412 stale document/case revision; 413 file/page/case-budget exceeded; 415 unsupported content; 422 malformed metadata or invalid review; 428 missing `If-Match`; 429 queue full; 503 missing provider configuration. Once accepted with 202, processing failures appear in `status: failed` with a safe reason such as `unreadable_document` or `extraction_unavailable`.

Track provider file IDs if an upload API is used. Expiry/deletion must remove source bytes, page renders, extracted text, index entries and any provider copies within documented retention. Until provider cleanup is confirmed, report retryable cleanup rather than successful erasure. Existing Gradium voice profiles are separate resources.

## 6. Acceptance before enabling uploads

Check valid PDF/image extraction, unreadable scans, spoofed MIME types, excessive pages, expired files, owner/scope isolation and instruction-bearing documents. Verify real page/excerpt matches, money/date nulls, review conflicts, deletion during extraction and rejection of stale citations. Use synthetic documents for repository fixtures; keep private policies outside Git. Export implemented models into OpenAPI only when these routes exist.
