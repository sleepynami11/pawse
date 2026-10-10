---
name: commit-secure
description: >-
  Commit safely: read the diff, block secrets and junk, stage files by name, write a clear message.
  Use for "commit", "save my changes", "checkpoint this", or when gp finds a dirty tree.
---

# Secure commit

Small, frequent commits on a working state are the hackathon safety net: any broken build should be
one `git revert` away.

1. **Look:** `git status`, `git diff`, `git diff --staged`. Summarise the change in one line. If the diff
   mixes two unrelated things, make two commits.
2. **Never stage:** `.env*` (except `.env.example`), `.venv/`, `__pycache__/`, `tmp/`, `*.zip`, recordings
   of real people, large binaries, the private paths listed in `.gitignore` (`backend/.memory/`,
   `backend/rag/`, ...), third-party data you may not redistribute.
3. **Scan:** `python scripts/check_safety.py` (API keys, private keys, env files, symlinks). A hit means
   stop: move the value to `.env` (git-ignored), re-run. Never weaken the scanner to pass.
4. **Check:** `bash scripts/check.sh`. Short on time: at least `python -m pytest -q tests`.
5. **Stage by name:** `git add <file> <file>`. No `git add -A` / `git add .` unless you read every file in
   `git status`.
6. **Commit:** `type: plain-English what` (feat/fix/chore/docs/test/research), e.g.
   `fix: clinic ranking keeps unknown opening hours unknown`. When an agent wrote most of it, end with a
   blank line and a `Co-Authored-By:` trailer naming the agent.
7. `git log -1 --stat` to confirm only the intended files went in.

## Safety

- A key that was ever pushed is leaked, even if a later commit deletes it: **rotate it** (event Gemini
  keys: one leaked key revokes every key in the project, see [gemini](../gemini/SKILL.md)).
- Never `--no-verify`, never `git commit --amend` on a commit that is already pushed.
- Never paste keys into commit messages, issues, or public pastebins/gists.

## Keep this skill current

Sync the "never stage" list with `.gitignore` and the scan list with `scripts/check_safety.py`.
Run `python scripts/validate_skills.py` after editing.
