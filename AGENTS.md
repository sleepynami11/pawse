# Pawse: guide for coding agents

Read this first. It tells you what Pawse is, how to run and check it, the rules every change follows,
and which skill to read before a task. Claude Code loads it through `CLAUDE.md`; other agents
(Cursor, Codex, Gemini CLI) read it directly.

## What Pawse is

A hackathon prototype (Tech Europe AI Hackathon, Google DeepMind) that helps a worried cat owner get
to a clear next step: care guidance, nearby vets, a cited insurance-policy explanation, and a German
phone script spoken in the owner's own voice. Python/FastAPI backend, plain HTML/CSS/JS frontend,
Gemini for reasoning and transcription, Gradium for voice.

- Product scope: [docs/SPEC.md](docs/SPEC.md) · Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Modules, owners' branches, shared files: [docs/AGENT_DEVELOPMENT.md](docs/AGENT_DEVELOPMENT.md)
- What is actually verified: [docs/VALIDATION.md](docs/VALIDATION.md)
- Demo story (Mimi): see [The golden path](#the-golden-path-the-2-minute-mimi-demo) below

## The golden path: the 2-minute Mimi demo

This story is the product's acceptance test. Full script with German lines and timings:
[research/pet-insurance/demo-video-script.md](research/pet-insurance/demo-video-script.md).

**Mimi jumped off the wardrobe and is limping → 🟡 see a vet today → Pawse calls the vet in German → the insurer
confirms the accident is covered, but not the home visit or physio → the owner picks the clinic (about CHF 385
instead of 510) → Pawse confirms the vet, books a cat-friendly taxi, and hands over a case summary and claim checklist.**

| Time | Beat | Backed by | Today |
|---|---|---|---|
| 0:00–0:17 | Owner records Mimi and says "My cat is limping" in English | `voice.py` transcription, `/care` intake | ✅ photo + audio via Gemini · ⚠️ video intake not connected |
| 0:17–0:30 | Triage card 🟡, follow-up "fall or jump?", nearest open practice | `providers.py` care guidance + clinic adapters, `orchestration.py` ranking | ✅ Gemini guidance · ⚠️ clinic search needs `GOOGLE_PLACES_API_KEY` or `MAPIFY_BASE_URL` |
| 0:30–0:58 | German call to the vet: 16:30 or a home visit, ~CHF 600 + 150 | `voice.py` German script + subtitles, Gradium speech | ✅ script · ⚠️ own voice needs a Gradium key · 🎭 call and reply simulated (no telephony) |
| 0:58–1:30 | Insurer call: accident covered, home visit and physio not; clinic CHF 385 vs home CHF 510 | `knowledge.py` cited AVB clauses, `demo.py` cost maths, `research/pet-insurance/` | ✅ citations + maths (real AVB terms, synthetic policyholder) · 🎭 insurer reply simulated |
| 1:30–1:42 | Pawse confirms 16:30 with the vet, asks for an itemised invoice | `voice.py` script | ✅ script · 🎭 reply and booking simulated |
| 1:42–1:54 | Taxi for 16:05 that accepts a cat in a carrier | `voice.py` script | ✅ script · 🎭 reply and booking simulated |
| 1:54–2:00 | Case summary + claim checklist (keep video, itemised invoice, 30 days) | `demo.py`, frontend | ✅ |

The in-app rehearsal (`GET /api/v1/demo/mimi`, first screen of the app) plays the whole story with no keys. It is the
fallback, not the goal.

**Keep it really running.**
- The goal is the live path: each ⚠️ above is open work to turn into ✅ (or, if cut, an honest 🎭 label), not a footnote.
- Every change must leave the golden path working end to end. Before pushing anything that touches it, run
  `bash scripts/check.sh` and walk the story in the browser ([demo-check](.claude/skills/demo-check/SKILL.md)).
- Story outcomes live in pytest (`tests/test_orchestration.py`): costs, citations, statuses. If you change a number,
  a German line or a clause, change the script, `pawse/demo.py` and the tests together so the video and the app agree.
- 🎭 steps stay labelled "simulated" on screen. Don't present a simulated reply as real (rule 3).
- When a ⚠️ becomes ✅, update this table and [docs/VALIDATION.md](docs/VALIDATION.md) in the same change.

## Where things are

| Path | What |
|---|---|
| `pawse/app.py` | FastAPI app and routes (shared file: coordinate changes) |
| `pawse/service.py`, `orchestration.py`, `state.py`, `demo.py` | Agent run, deadlines, ranking, the synthetic Mimi story |
| `pawse/providers.py` | Gemini care guidance + clinic adapters (Mapify, Google Places) |
| `pawse/voice.py` | Gemini transcription/translation, Gradium cloning and German speech |
| `pawse/knowledge.py` | Cited search over the synthetic policy corpus in `research/` |
| `pawse/static/` | Frontend (no build step) |
| `tests/` | pytest, providers always mocked |
| `docs/openapi.json` | Generated API contract: never edit by hand |
| `backend/` | Imported legacy CatAgent backend: leave alone unless the task needs it |
| `scripts/` | `check.sh` (all checks), `export_contract.py`, `probe_models.py`, checkers |

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp -n .env.example .env                          # add keys; many flows work without them
uvicorn pawse.app:app --host 127.0.0.1 --port 8765   # app on :8765, API docs on /docs
bash scripts/check.sh                            # everything CI runs (needs Node for the JS check)
python -m pytest -q tests/test_voice.py -k clone # one test
python scripts/export_contract.py                # after changing API models
```

CI (`.github/workflows/check.yml`) runs `bash scripts/check.sh` on every push to `main` and every PR:
secret scan, skill validation, JS syntax, OpenAPI contract in sync, pytest. Keep it green.

## Rules for every change

1. **Read the matching skill first.** If a row below fits the task, read that SKILL.md end to end before acting.
2. **Never commit secrets.** Keys live only in `.env` (git-ignored). Never put a key in frontend code,
   logs or docs. One leaked event Gemini key revokes every key in the project.
3. **Honesty over polish.** Never show or claim a booking, call, insurance approval or voice clone that did
   not happen. Simulated steps stay visibly labelled "simulated". Docs and README match the code.
4. **Consent is enforced server-side.** AI, location, own-voice and provider-sharing consent are separate.
5. **Tests with mocks.** New logic gets a pytest with mocked providers; bugs get a failing test first ([bugfix](.claude/skills/bugfix/SKILL.md)).
6. **Contract changes** (request/response models): regenerate `docs/openapi.json` and update consumers
   (`pawse/static/`, `schemas/pawse.ts`) in the same change.
7. **Small commits, clear messages:** `type: plain-English what` (feat/fix/chore/docs/test/research),
   stage files by name. Push small in-module changes straight to `main`; use a PR for shared files ([gp](.claude/skills/gp/SKILL.md)).
8. **Protect the golden path.** No change may break the 2-minute demo (see [The golden path](#the-golden-path-the-2-minute-mimi-demo)); check it before pushing.
9. **Stay in your lane.** Several people and agents work in parallel by module (see AGENT_DEVELOPMENT).
   Don't refactor files outside your task; pull/rebase before pushing.

## Skills catalog

Skills live in `.claude/skills/<name>/SKILL.md`. Claude Code picks them up automatically; other agents
should open the file named in the row.

| Skill | Read it when |
|---|---|
| [gemini](.claude/skills/gemini/SKILL.md) | Anything Gemini: model IDs, event key, Live API voice, ephemeral tokens, 429s |
| [gemini-api-dev](.claude/skills/gemini-api-dev/SKILL.md) | Writing Gemini API code (Google's official skill, vendored: `npx skills update`) |
| [gemini-live-api-dev](.claude/skills/gemini-live-api-dev/SKILL.md) | Real-time Gemini Live voice/video streaming (Google's official skill, vendored) |
| [gradium-voice](.claude/skills/gradium-voice/SKILL.md) | Voice cloning, German TTS, STT with Gradium |
| [scope-cut](.claude/skills/scope-cut/SKILL.md) | Deciding what to build, fake or drop; running out of time; feature freeze |
| [frontend-design](.claude/skills/frontend-design/SKILL.md) | Making the UI in `pawse/static/` look demo-ready |
| [demo-check](.claude/skills/demo-check/SKILL.md) | Verifying the demo story end to end, screenshots, demo-day checklist |
| [pitch](.claude/skills/pitch/SKILL.md) | Pitch script, backup video, README submission text |
| [research](.claude/skills/research/SKILL.md) | Sourced lookups: API currency, vet/insurance facts, competitors |
| [bugfix](.claude/skills/bugfix/SKILL.md) | Any bug: failing test first, root-cause fix, sweep siblings |
| [self-review](.claude/skills/self-review/SKILL.md) | Before pushing a bigger change: adversarial review of your own diff |
| [commit-secure](.claude/skills/commit-secure/SKILL.md) | Committing safely (no keys, no junk, good message) |
| [gp](.claude/skills/gp/SKILL.md) | Pushing: straight to main or PR + CI + squash-merge |
| [create-skill](.claude/skills/create-skill/SKILL.md) | Adding or changing a skill (then `python scripts/validate_skills.py`) |
