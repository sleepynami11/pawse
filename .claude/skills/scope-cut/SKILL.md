---
name: scope-cut
description: >-
  Decide what to build for real, what to fake, and what to drop so the Pawse demo works on time.
  Use when someone asks "should we build X", "we're running out of time", "what can we cut",
  "feature freeze", or the demo story is not working end to end yet.
---

# Scope cut

A hackathon is judged on a short demo. Anything the judge does not see is a cost, not a feature.
The demo story is [research/pet-insurance/demo-video-script.md](../../../research/pet-insurance/demo-video-script.md);
the MVP boundary is [docs/SPEC.md](../../../docs/SPEC.md).

## The triage

Put each wish-list item in one bucket and note the result in the PR or `docs/SPEC.md`:

| Bucket | Rule | Pawse examples |
|---|---|---|
| **Real** | On the demo path AND the agentic/Gemini core | care guidance, the agent run trace, cited policy search, German script |
| **Fake** | On the demo path but not the point | vet/insurer/taxi replies (Mimi story), calendar, booking, claim submission |
| **Drop** | Not on the demo path | accounts, multi-user, settings, admin, telephony transport |

Faking rules: fakes are **honest and visibly labelled** ("simulated" in the UI, said in the pitch),
deterministic, and in one obvious place (`pawse/demo.py`, the synthetic corpus in `research/`).
Never report a booking, call or insurance approval that did not happen (see SPEC).

## Timeboxes

- Any single problem: 30 min, then ask a teammate or cut/fake it.
- Unfamiliar API: first make one raw call work in a 10-line script (see `scripts/probe_models.py`) before wiring UI.
- **Feature freeze 90 min before demos.** After that: bugfixes, polish, pitch, backup video only.

## When behind schedule (in order)

1. Make the demo story work with fakes everywhere, then replace fakes with real calls in order of judge impact.
2. Cut breadth (fewer screens, fewer providers), keep depth on the "wow" moment.
3. Record a fallback video (see [pitch](../pitch/SKILL.md)) so a flaky API can't kill the demo.

## Keep this skill current

Add examples from this hackathon; keep it one screen long. Run `python scripts/validate_skills.py` after editing.
