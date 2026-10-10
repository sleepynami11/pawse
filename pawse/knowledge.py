"""Local evidence retrieval for the fictional insurance demo, never live coverage.

Only the two reviewed repository documents below are indexed. This deliberately
small lexical baseline does not need an embedding API, a vector database, or any
owner documents. A reasoning agent may cite its evidence but must retain scope.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from .models import Model


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = "research/pet-insurance/policy/policy.json"
AVB_PATH = "research/pet-insurance/avb/avb-en.md"
DISCLAIMER = (
    "Demo policy schedule and an English adaptation of real Swiss terms only. These excerpts do not "
    "establish an owner's real insurance coverage or constitute insurer approval."
)
router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge evidence"])


class KnowledgeQuery(Model):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=5)
    scope: Literal["synthetic_demo"] = "synthetic_demo"


class Evidence(Model):
    evidence_id: str
    source_id: Literal["pawse-demo-policy", "pawse-demo-avb"]
    source_path: str
    source_sha256: str
    section: str
    title: str
    snippet: str = Field(max_length=4000)
    synthetic: Literal[True] = True
    score: float = Field(ge=0)


class KnowledgeResult(Model):
    scope: Literal["synthetic_demo"] = "synthetic_demo"
    synthetic: Literal[True] = True
    method: Literal["lexical"] = "lexical"
    insurance_approval: Literal["not_obtained"] = "not_obtained"
    corpus_version: str
    status: Literal["evidence_found", "no_evidence"]
    evidence: list[Evidence] = Field(max_length=5)
    disclaimer: str = DISCLAIMER


@dataclass(frozen=True)
class Chunk:
    source_id: str
    path: str
    digest: str
    section: str
    title: str
    snippet: str


STOP_WORDS = frozenset(
    "a an and are as at be by can could do does for from have how i if in is it "
    "me my of on or our please policy insurance the their there these they this "
    "to was we what when where which who will with would you your cover covered "
    "coverage tell about help".split()
)
ALIASES = {
    "physio": "physiotherapy",
    "reimburse": "reimbursement",
    "reimbursed": "reimbursement",
    "reimbursements": "reimbursement",
    "accidents": "accident",
    "claims": "claim",
    "invoices": "invoice",
    "deductibles": "deductible",
}


def tokens(text: str) -> set[str]:
    text = re.sub(r"\bhome[ -]visits?\b", "house call", text.lower())
    text = re.sub(r"\bhouse[ -]calls?\b", "house call", text)
    return {
        ALIASES.get(word, word)
        for word in re.findall(r"[a-z]+|\d+(?:\.\d+)*", text)
        if word not in STOP_WORDS and (len(word) > 1 or word.isdigit())
    }


@lru_cache(maxsize=1)
def corpus() -> tuple[tuple[Chunk, ...], str]:
    """Load a fixed allowlist; no request can select a file or a collection."""
    raw_policy = (ROOT / POLICY_PATH).read_bytes()
    raw_avb = (ROOT / AVB_PATH).read_bytes()
    policy = json.loads(raw_policy)
    # Refuse to silently treat replacement owner data as the demo corpus.
    if policy.get("policy_number") != "PAWSE-DEMO-2026-000001" or "FICTIONAL" not in policy.get("_comment", ""):
        raise ValueError("The configured corpus is not the synthetic demo policy")
    avb = raw_avb.decode("utf-8")
    if "FICTIONAL demo terms" not in avb:
        raise ValueError("The configured corpus is not the synthetic demo terms")
    policy_digest = hashlib.sha256(raw_policy).hexdigest()
    avb_digest = hashlib.sha256(raw_avb).hexdigest()
    chunks = []
    selected = {key: policy[key] for key in ("term", "cost_sharing", "claims_process")}
    selected.update({f"coverages/{key}": value for key, value in policy["coverages"].items()})
    for section, value in selected.items():
        # JSON snippets preserve exact key/value evidence and avoid owner details.
        chunks.append(Chunk(
            "pawse-demo-policy", POLICY_PATH, policy_digest, "/" + section,
            "Demo policy: " + section.replace("/", " / ").replace("_", " "),
            json.dumps(value, ensure_ascii=False, indent=2),
        ))
    headings = list(re.finditer(r"^#{2,4} (\d+(?:\.\d+)*) (.+)$", avb, re.MULTILINE))
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(avb)
        snippet = avb[heading.end():end].strip()
        if snippet:
            if len(snippet) > 4000:
                raise ValueError("A demo clause exceeds the reviewed chunk size")
            chunks.append(Chunk(
                "pawse-demo-avb", AVB_PATH, avb_digest, heading[1],
                heading[2], snippet,
            ))
    version = hashlib.sha256(raw_policy + b"\0" + raw_avb).hexdigest()[:16]
    return tuple(chunks), version


def search_knowledge(payload: KnowledgeQuery) -> KnowledgeResult:
    """Return matching excerpts; relevance scores are not coverage confidence."""
    chunks, version = corpus()
    query_tokens = tokens(payload.query)
    document_tokens = [tokens(chunk.section + " " + chunk.title + " " + chunk.snippet) for chunk in chunks]
    frequencies = {term: sum(term in terms for terms in document_tokens) for term in query_tokens}
    ranked = []
    for chunk, terms in zip(chunks, document_tokens):
        matches = query_tokens & terms
        if not matches:
            continue
        score = sum(math.log(1 + len(chunks) / (1 + frequencies[term])) for term in matches)
        score += len(matches & tokens(chunk.title)) * 0.5
        # A requested clause number is a stronger signal than incidental numbers.
        if chunk.source_id == "pawse-demo-avb" and re.search(r"(?<![\d.])" + re.escape(chunk.section) + r"(?![\d.])", payload.query):
            score += 10
        ranked.append((score, chunk))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].source_id, pair[1].section))
    evidence = [Evidence(
        evidence_id=f"{chunk.source_id}:{chunk.section}",
        source_id=chunk.source_id,
        source_path=chunk.path,
        source_sha256=chunk.digest,
        section=chunk.section,
        title=chunk.title,
        snippet=chunk.snippet,
        score=round(score, 4),
    ) for score, chunk in ranked[:payload.top_k]]
    return KnowledgeResult(
        corpus_version=version,
        status="evidence_found" if evidence else "no_evidence",
        evidence=evidence,
    )


@router.post("/search", response_model=KnowledgeResult)
def search(payload: KnowledgeQuery) -> KnowledgeResult:
    try:
        return search_knowledge(payload)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "The synthetic evidence corpus is unavailable") from exc
