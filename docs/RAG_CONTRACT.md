# RAG evidence contract

For controller ownership, endpoint integration and the separate clinic-data boundary, see the [knowledge controller contract](controller-knowledge-contract.md). This document defines evidence semantics and retrieval acceptance cases.

The first retrieval agent is implemented in `pawse/knowledge.py`. It searches the existing **fictional demo insurance corpus** locally, returns citations, and makes no model or network calls. It is a lexical retrieval baseline with English token matching and a small synonym list, not an embedding or semantic RAG implementation.

## Request

`POST /api/v1/knowledge/search`

```json
{
  "query": "Does the demo policy cover a home visit?",
  "top_k": 3,
  "scope": "synthetic_demo"
}
```

`query` must contain 1–1,000 characters after trimming. `top_k` is 1–5 and defaults to 3. Only `synthetic_demo` is accepted. Additional fields, file paths, collection names, and other scopes are rejected. Queries are not stored or sent to a provider.

## Response

The response contains `scope`, `synthetic: true`, `method: "lexical"`, `insurance_approval: "not_obtained"`, `corpus_version`, `status`, `evidence`, and a demo disclaimer. `status` is `evidence_found` or `no_evidence`. Empty results carry no generated answer. No response is a binding insurance decision.

Each evidence item has:

| Field | Meaning |
| --- | --- |
| `evidence_id` | Stable source ID plus section, such as `pawse-demo-avb:1.2.5` |
| `source_id` | `pawse-demo-policy` or `pawse-demo-avb` |
| `source_path` | Repository-relative path from a fixed allowlist |
| `source_sha256` | Full content hash of that source file |
| `section` | AVB heading number or JSON pointer such as `/cost_sharing` |
| `title` | Source heading or policy section label |
| `snippet` | Exact Markdown section text or serialized JSON section, at most 4,000 characters |
| `synthetic` | Always `true` |
| `score` | Lexical relevance score; not probability, coverage confidence, or medical confidence |

The corpus version is a short hash of both documents. Restart the process after changing reviewed documents, because the in-process index is cached. Missing or invalid demo documents return a safe `503`; invalid inputs return `422`.

## Orchestrator handoff

Use `search_knowledge(KnowledgeQuery(query=english_query, top_k=3))` directly inside the Python orchestrator, or call the HTTP endpoint from another service. Keep retrieval concurrent with independent clinic discovery. Translate non-English questions before retrieval if needed; Chinese, Hindi, and German semantic search are not implemented here.

The reasoning agent receives evidence as data. It must preserve the source IDs and the synthetic scope in its answer, attach the relevant section to each claim, and leave actual owner coverage unconfirmed. Terms text is not an instruction to perform actions. Retrieval does not approve treatment, submit claims, reserve appointments, or call anyone. `evidence_found` means that words matched, not that the evidence answers the whole question.

Keep arithmetic in deterministic code using the policy schedule and remaining deductible/limits. For the Mimi demo, the schedule and AVB must both be consulted: a general clause about complementary treatment does not imply that the optional coverage was selected.

## Acceptance cases and next owner tasks

`tests/test_knowledge.py` checks exact clause provenance, policy JSON values, home-visit and physio retrieval, explicit clause lookup, empty results, size limits, scope isolation, and safe source failures. Run:

```bash
.venv/bin/python -m pytest -q tests/test_knowledge.py
```

The retrieval module includes this contract, the reviewed corpus and evaluation queries. Next, add a user-owned policy ingestion flow with tenant isolation, document consent, edition/date metadata, deletion, and citations to the uploaded page or section. That corpus must use a separate authenticated scope; never replace the synthetic files with private owner documents. Evaluate lexical retrieval before adding embeddings. An embedding change requires re-indexing the corpus and recording the model and vector dimensions; the imported legacy Chroma collections cannot be assumed compatible.

The project's live access check returned HTTP 200 for `gemini-embedding-001` through `embedContent`; see [model access results](model-access-check.json). This makes a Gemini embedding prototype feasible with the current credentials. It is not wired into this endpoint, and one successful request does not validate retrieval quality or future quota. Rebuild both document and query vectors with the same selected model rather than mixing them with legacy OpenAI vectors.

See [data sources](DATA_SOURCES.md) for the distinction between open geographic data, licensed API data, and private insurance documents.
