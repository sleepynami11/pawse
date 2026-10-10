---
name: gp
description: >-
  Publish work: commit (via commit-secure), push straight to main (small changes), or open a PR and
  squash-merge it (shared files, bigger changes). CI is on request; the local check is the gate. Use for "push", "git push", "make a PR",
  "merge the PR", or "/gp".
disable-model-invocation: true
---

# Git push (`/gp`)

## Pre-flight

1. `gh auth status` (fails: `gh auth login`, GitHub.com, HTTPS, browser).
2. `git status --porcelain`. Anything uncommitted: run [commit-secure](../commit-secure/SKILL.md) first.
3. `bash scripts/check.sh` must be green. It is the gate: CI is on request and `main` has no branch
   protection, so nothing else stops a red build reaching teammates.

## Which mode

- **Push to main:** a small change inside your own module (see the module table in
  [docs/AGENT_DEVELOPMENT.md](../../../docs/AGENT_DEVELOPMENT.md)), or the user says "push directly".
- **PR:** you touch shared integration files (`pawse/app.py`, request/response models,
  `docs/openapi.json`, `schemas/pawse.ts`, requirements, README), or the user asks for a PR.

## Push to main

1. `git fetch origin && git pull --rebase origin main`. Conflicts: resolve, re-run the check,
   `git rebase --continue`. Unsure whose change wins: ask, do not guess.
2. `git push origin HEAD:main`.
3. Report the commit URL: `gh browse -n "$(git rev-parse HEAD)"` prints it.

## PR + squash-merge

1. **Existing PR?** `gh pr view --json number,url,state 2>/dev/null`. One open for this branch: push to it.
2. **On main?** Branch first: `git checkout -b <feat|fix|chore|docs>/<short-name>`.
3. **Sync:** `git fetch origin && git rebase origin/main`, then `bash scripts/check.sh`.
4. **Push + open:** `git push -u origin HEAD`, then `gh pr create --base main --title "<type: what>" --body-file <tmpfile>`
   using `.github/pull_request_template.md` (what changed, how verified, known gaps).
5. **CI only on request:** if the user asks for CI, `gh workflow run check --ref <branch>`, then `gh run watch`.
   Red: `gh run view <id> --log-failed`; fix, push, re-run.
6. **Merge:** after a green local check (and green CI, if it was requested), `gh pr merge <n> --squash --delete-branch`, then confirm
   `gh pr view <n> --json state` says `MERGED`.
7. Report the full PR URL (`https://github.com/<owner>/<repo>/pull/<n>`), not just `#<n>`.

## Safety

- Never `git push --force` to `main`; on your own branch only `--force-with-lease`.
- Never merge with a red local check or a red requested CI run.

## Keep this skill current

Update when branch rules, CI checks or the merge method change. Run `python scripts/validate_skills.py` after editing.
