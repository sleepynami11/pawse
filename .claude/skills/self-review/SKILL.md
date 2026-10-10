---
name: self-review
description: >-
  Adversarial review of your own diff before pushing: correctness, edge cases, security (secrets, SSRF,
  prompt injection via tools, consent), tests, demo-story breakage, honesty of claims. Use for
  "review my change", "self-review", "did we miss anything", or before gp on a bigger change.
---

# Self-review

Treat the diff as if a stranger wrote it: find what is wrong, do not defend it. List findings first, fix after.

## Scope

1. `git status`, `git diff`, `git diff --staged`, plus unpushed commits: `git log -p origin/main..HEAD`.
2. Only files you touched. Empty scope: say "Nothing to review" and stop.
3. Restate the request in one sentence. Every hunk should map to it; anything else is scope creep.

## Lenses (one line each: ✔ or the problem with `file:line`)

1. **Correctness.** Does it do what was asked? Read the code paths, not just the hunk.
2. **Edge cases.** Empty input, huge audio/image, `None`, provider timeout or 429, non-English text
   (Chinese, Hindi), double click, concurrent runs.
3. **Security and consent.**
   - Secrets: no keys in code, logs, `pawse/static/` or responses. `python scripts/check_safety.py`.
   - SSRF: anything that fetches a URL blocks `localhost`, private IPs, `file:` and metadata hosts.
   - Prompt injection: provider/tool output is data, never instructions.
   - Consent: AI, location, own-voice and provider-sharing consent stay separate and are enforced server-side.
   - Untrusted input never flows unescaped into shell, SQL, HTML (`innerHTML`) or file paths.
4. **Tests.** New logic has a pytest with mocked providers. Would a plausible regression go unnoticed?
5. **Contract.** API model changed: `python scripts/export_contract.py` and `docs/openapi.json` committed,
   consumers (`pawse/static/`, `schemas/pawse.ts`) checked. See [docs/AGENT_DEVELOPMENT.md](../../../docs/AGENT_DEVELOPMENT.md).
6. **Honesty.** No UI text, doc or README claims a booking, call, approval, clone or "verified" result
   that did not happen. Simulated steps stay visibly simulated. Docs match the code.

## Output

```
Summary: <n> High / <n> Medium / <n> Low
| # | Sev | Lens | file:line | Problem | Fix |
```

High = wrong behavior, broken demo, security or consent issue, false claim. Fix the Highs, run
`bash scripts/check.sh`, then [commit-secure](../commit-secure/SKILL.md) and [gp](../gp/SKILL.md).

## Keep this skill current

Add a lens when a bug class slips through twice. Run `python scripts/validate_skills.py` after editing.
