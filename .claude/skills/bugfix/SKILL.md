---
name: bugfix
description: >-
  Fix a bug the durable way: reproduce it as a failing pytest (red), fix the root cause (green), sweep
  for siblings, `bash scripts/check.sh`. Use for "fix the bug", "it crashes", "wrong output",
  "test is failing", "/bugfix".
---

# Bugfix: Red, Green, Sweep

Skip for new features, pure refactors, docs or formatting.

## 1. Reproduce and find the cause

1. Get a deterministic repro: exact input, request body, steps, or a failing test. Use the literal input
   from the report, not a look-alike. Can't reproduce: gather logs and actual vs expected before editing.
2. Trace from the symptom to the line that is actually wrong. A `None` guard at the crash site is a
   symptom patch; the missing validation upstream is the cause.
3. Name the pattern in one sentence (e.g. "adapter assumes the provider always returns `results`").
   You grep for it in step 4.

## 2. Red: failing test first

- Add a test in `tests/` next to the closest existing one (`test_care.py`, `test_voice.py`,
  `test_knowledge.py`, `test_orchestration.py`). Run `python -m pytest -q tests/<file> -k <name>`.
- Providers (Gemini, Gradium, Mapify, Places) are mocked with `monkeypatch` / fake httpx responses,
  never a live key.
- Confirm it fails **for the right reason** (the assertion, not an import error). A test that passes
  before the fix proves nothing.
- Frontend-only bug in `pawse/static/`, hard to automate: write the repro steps in the commit message, and say so.

## 3. Green: minimal root-cause fix

- Smallest change that fixes the cause and turns the test green. No drive-by refactors.
- Do not edit the red test to make it pass (unless the test itself was wrong; say so).
- Still red after a fix: revert only that attempt (`git restore -p <file>`, keep the red test) and try a
  new hypothesis. Do not stack fixes. After 2 or 3 failed hypotheses, stop and rethink with the team.

## 4. Sweep: fix the siblings

1. Search the pattern from step 1.3 several ways: `grep -rn` by function name, idiom, data shape
   (`pawse/`, `scripts/`, `tests/`).
2. Triage every hit: same bug / related / false positive. Fix real siblings in the same change.
3. Report honestly: "Found N, fixed M, left K because ...".

## 5. Verify and ship

1. `bash scripts/check.sh` (safety, skills, JS syntax, OpenAPI sync, pytest).
2. Ask: what cheap guard (a test, a Pydantic constraint, a type) stops the whole class?
3. Commit via [commit-secure](../commit-secure/SKILL.md) as `fix: <what was wrong>`, body: root cause +
   sweep result. Publish via [gp](../gp/SKILL.md).

## Keep this skill current

Update when test commands or layout change. Run `python scripts/validate_skills.py` after editing.
