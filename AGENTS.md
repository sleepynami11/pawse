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
- Demo story (Mimi): [research/pet-insurance/demo-video-script.md](research/pet-insurance/demo-video-script.md)

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
8. **Stay in your lane.** Several people and agents work in parallel by module (see AGENT_DEVELOPMENT).
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
