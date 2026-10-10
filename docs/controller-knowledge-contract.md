# Pawse Knowledge and Data Controller Contract

This document defines the retrieval module's public controller and its clinic-data handoff to care. Policy evidence and nearby-clinic retrieval have different scopes and must remain separate. Implementation: [knowledge.py](../pawse/knowledge.py) and clinic adapters in [providers.py](../pawse/providers.py).

## 1. Evidence search endpoint

`POST /api/v1/knowledge/search` → **200** `KnowledgeResult`.

Schema: `KnowledgeQuery`.

<!-- schema: KnowledgeQuery -->
```json
{
  "query": "home visit surcharge clause 1.2.5",
  "top_k": 3,
  "scope": "synthetic_demo"
}
```

| Field | Constraint |
| --- | --- |
| `query` | 1–1,000 characters after trimming |
| `top_k` | 1–5, default 3 |
| `scope` | Only `synthetic_demo`; defaults to that value |

There are no upload, document-selection, collection-selection or actual-policy scopes. Additional fields are rejected. Search runs locally using English lexical matching and a small synonym list; it makes no model/network call and stores no query. Translate a non-English question in a separately consented flow before using this endpoint if needed.

## 2. Response and citation contract

| Field | Meaning |
| --- | --- |
| `scope`, `synthetic` | Always `synthetic_demo`, true |
| `method` | `lexical` |
| `insurance_approval` | Always `not_obtained` |
| `corpus_version` | Short hash derived from the reviewed source documents |
| `status` | `evidence_found` or `no_evidence` |
| `evidence` | At most `top_k` evidence records; empty when nothing matches |
| `disclaimer` | Fictional-policy scope and no real coverage/approval claim |

Each evidence record has `evidence_id`, `source_id`, `source_path`, `source_sha256`, `section`, `title`, `snippet`, `synthetic: true`, `score`. The source ID is `pawse-demo-policy` or `pawse-demo-avb`. Snippets are exact source sections or serialized JSON sections, up to 4,000 characters. Scores are lexical relevance, not probability or coverage confidence.

Frontend shows title, section, snippet and the demo label together. A downstream reasoning module must keep the source ID/hash with any derived claim and treat retrieved text as data. `evidence_found` only establishes a lexical match; it does not guarantee a complete answer. `no_evidence` requires an explicit absence of evidence, not an invented clause.

The source allowlist is fixed:

| Source | Path | Boundary |
| --- | --- | --- |
| Demo policy schedule | `research/pet-insurance/policy/policy.json` | Selected coverage, term, cost-sharing and claim sections |
| Demo English terms | `research/pet-insurance/avb/avb-en.md` | Clause sections such as 1.2.5 and 1.2.6 |

The index is cached in process; restart after changing reviewed source files. Invalid/missing corpus returns safe HTTP 503; invalid payload or unsupported scope returns 422. Full provenance and acceptance details are in the existing [RAG evidence contract](RAG_CONTRACT.md).

## 3. Controller-to-service interface

`knowledge.search(payload: KnowledgeQuery) -> KnowledgeResult` is the HTTP wrapper. It calls `search_knowledge(payload)` and maps source errors to a safe 503. Internal callers may use the same service function directly, but must handle its source errors themselves.

The agent run currently leaves `policy_evidence` as `evidence_required`; it does not call this endpoint or attach the demo corpus to a live owner. A separate demo evidence search does not alter `CareResult.insurance.coverage`, which remains `unconfirmed`.

For the synthetic Mimi scenario, inspect both the schedule and terms. An optional service described in general terms is not necessarily selected in the schedule. Keep reimbursement arithmetic in deterministic code and state remaining-deductible/limit assumptions. The scenario's CHF 385/510 alternatives are fictional estimates, not live quotes.

## 4. Clinic-data service handoff

There is no standalone `/knowledge/clinics` or `/clinics` controller. Clinic retrieval is an internal service used by the [care controller](controller-care-contract.md):

```text
CareRequest + shared HTTP client
  -> discover(req, client)
  -> google_clinics(...) OR mapify_clinics(...)
  -> Clinic[]
  -> rank_clinics(...)
  -> CareResult.clinics / SSE clinics event
```

Location and `share_location` are required. Google Places takes precedence when configured; otherwise Mapify is selected. Provider failure does not silently switch to another service.

| Producer obligation | Consumer obligation |
| --- | --- |
| Send only coordinates and a generic vet category/query, radius and applicable language | Do not send symptoms/photos/insurance into place search |
| Normalize records to `Clinic`, keeping source and retrieval time | Render provider facts with provenance |
| Preserve missing coordinates, phone, rating and opening status as null | Do not infer hours, ETA, specialties or emergency availability |
| Filter Mapify results for recognizable veterinary care | Acknowledge that conservative filtering can omit valid clinics |
| Produce a dial URI only for valid international-format phones | Do not manufacture a number from model output |
| Leave Mapify `open_now` unknown | Do not promote the upstream missing-hours default into “open now” |

Exact upstream paths and normalization differences are in [Mapify adapter](MAPIFY_ADAPTER.md). This is a configured HTTP adapter, not an imported copy of Mapify's backend.

## 5. Open data and future private-policy ingestion

**Current:** runtime clinics come from configured providers; local policy retrieval uses reviewed synthetic files. No Zurich open-data ingestion job or vector index is wired into these routes. Source candidates and reuse conditions are recorded in [Data sources](DATA_SOURCES.md).

**Proposed:** a new open-data adapter should record source URL, license/attribution, update date, veterinary classification evidence and missing-field rules before joining the normalized `Clinic` boundary. Use source-qualified IDs to avoid collisions. Preserve unknown opening hours and contact verification status.

**Proposed:** actual owner-policy retrieval needs a new authenticated scope with upload consent, ownership, document edition/effective dates, source/page citations and deletion. Do not replace the synthetic files with private documents. If embeddings are introduced, version the model and dimensions and rebuild both document and query vectors; existing legacy OpenAI vectors cannot be mixed with Gemini vectors.

These proposals do not add endpoints or approve insurance coverage. A future schema change must be agreed with the controller and frontend before implementation.

## 6. Handoff acceptance

Use `tests/test_knowledge.py` for clause provenance, JSON values, empty results, scope isolation and safe source failures; use the clinic adapter cases in `tests/test_care.py` for normalization and unknown fields. Include source/version/license notes with any new dataset. Live provider checks and retrieval-quality evaluation are separate from mocked API checks.
