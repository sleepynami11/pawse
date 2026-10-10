"""Evidence provenance and synthetic-scope checks; no provider calls."""

import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pawse.knowledge import (
    AVB_PATH, POLICY_PATH, ROOT, KnowledgeQuery, corpus, router, search_knowledge,
)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


def test_home_visit_retrieves_exact_clause_and_marks_every_item_synthetic():
    result = search_knowledge(KnowledgeQuery(query="home visit house call", top_k=5))
    clause = next(item for item in result.evidence if item.section == "1.2.5")
    text = (ROOT / AVB_PATH).read_text()
    assert clause.snippet in text
    assert "CHF 12'000" in clause.snippet
    assert clause.source_sha256 == hashlib.sha256((ROOT / AVB_PATH).read_bytes()).hexdigest()
    assert result.scope == "synthetic_demo"
    assert result.synthetic is True
    assert result.method == "lexical"
    assert result.insurance_approval == "not_obtained"
    assert all(item.synthetic for item in result.evidence)
    assert "do not establish" in result.disclaimer


def test_physio_matches_policy_selection_and_terms():
    result = search_knowledge(KnowledgeQuery(query="physio complementary medicine", top_k=5))
    policy = next(item for item in result.evidence if item.section == "/coverages/complementary_medicine")
    assert json.loads(policy.snippet)["selected"] is False
    assert any(item.section == "1.2.6" for item in result.evidence)


def test_policy_json_citation_is_exact_value_not_generated_text():
    result = search_knowledge(KnowledgeQuery(query="deductible reimbursement rate", top_k=5))
    item = next(item for item in result.evidence if item.section == "/cost_sharing")
    actual = json.loads((ROOT / POLICY_PATH).read_text())["cost_sharing"]
    assert json.loads(item.snippet) == actual
    assert actual["annual_deductible_chf"] == 300
    assert actual["reimbursement_rate"] == .8


def test_explicit_clause_number_ranks_first():
    result = search_knowledge(KnowledgeQuery(query="AVB 1.2.6", top_k=1))
    assert result.evidence[0].section == "1.2.6"


@pytest.mark.parametrize("query", ["quantum spaceship astrophotography", "what is my insurance", "   "])
def test_no_evidence_or_empty_query_never_produces_an_answer(client, query):
    response = client.post("/api/v1/knowledge/search", json={"query": query})
    if not query.strip():
        assert response.status_code == 422
    else:
        assert response.status_code == 200
        assert response.json()["status"] == "no_evidence"
        assert response.json()["evidence"] == []


@pytest.mark.parametrize("update", [
    {"top_k": 0}, {"top_k": 6}, {"query": "x" * 1001},
    {"scope": "user_policy"}, {"source_path": "../../.env"},
])
def test_contract_rejects_unbounded_or_other_scope_requests(client, update):
    response = client.post("/api/v1/knowledge/search", json={"query": "house call", **update})
    assert response.status_code == 422


def test_corpus_is_a_fixed_document_allowlist_without_owner_details():
    chunks, version = corpus()
    assert len(version) == 16
    assert {chunk.path for chunk in chunks} == {POLICY_PATH, AVB_PATH}
    assert not any("user1@example.com" in chunk.snippet for chunk in chunks)
    assert not any(chunk.section.startswith("/policyholder") for chunk in chunks)


def test_corpus_failure_is_a_safe_503(client, monkeypatch):
    def missing():
        raise OSError("PRIVATE_PATH_SHOULD_NOT_LEAK")
    monkeypatch.setattr("pawse.knowledge.corpus", missing)
    response = client.post("/api/v1/knowledge/search", json={"query": "house call"})
    assert response.status_code == 503
    assert "PRIVATE_PATH_SHOULD_NOT_LEAK" not in response.text


def test_policy_view_shows_the_demo_schedule_without_policyholder_contact(client):
    response = client.get("/api/v1/knowledge/policy")
    assert response.status_code == 200
    body = response.json()
    assert body["policy_number"] == "PAWSE-DEMO-2026-000001" and body["synthetic"] is True
    assert body["cost_sharing"]["annual_deductible_chf"] == 300
    assert body["cost_sharing"]["reimbursement_rate"] == 0.8
    coverages = {c["key"]: c for c in body["coverages"]}
    assert coverages["accident_illness_base"]["selected"] is True
    assert coverages["complementary_medicine"]["selected"] is False
    assert "Mimi" in body["insured_animals"][0]["name"]
    assert any(c["section"] == "1.2.5" and "CHF 12'000" in c["text"] for c in body["clauses"])
    assert "user1@example.com" not in response.text and "Demo user 1" not in response.text
