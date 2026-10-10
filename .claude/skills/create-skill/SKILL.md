---
name: create-skill
description: >-
  Add or update a Claude Code skill in this repo (.claude/skills/<name>/SKILL.md) and list it in the
  AGENTS.md catalog. Use for "make a skill", "turn this workflow into a skill", "update the skill".
---

# Create or update a skill

A skill is a short, repeatable recipe an agent reads end to end before acting. Write one when you have
done the same multi-step thing twice, or a step is easy to get wrong.

1. **Folder:** `.claude/skills/<kebab-name>/SKILL.md`. Check the catalog in `AGENTS.md` first: update an
   existing skill rather than adding an overlapping one.
2. **Front matter:**

   ```yaml
   ---
   name: <kebab-name>          # must equal the folder name
   description: >-
     What it does in one line. Use for "trigger phrase", "another phrase", "/<kebab-name>".
   ---
   ```

   The description decides when the agent picks the skill: concrete verbs and the phrases people say.
   Optional: `disable-model-invocation: true` (only runs when a user types `/<name>`; use for pushes and
   anything with side effects).
3. **Body (30 to 90 lines):** numbered steps, exact commands from this repo (`bash scripts/check.sh`,
   `python -m pytest -q tests`), a `## Safety` section if it can leak secrets or destroy work.
4. **Self-contained:** relative links only (`../gp/SKILL.md`, `../../../docs/...`), no absolute paths, no keys.
5. **End with** `## Keep this skill current` (what to update it with, and the validator command).
6. **Catalog row** in the `AGENTS.md` skills table, copying an existing row's shape.
7. **Validate:** `python scripts/validate_skills.py`. Fix every error.
8. Commit via [commit-secure](../commit-secure/SKILL.md) as `docs: add <name> skill`, then [gp](../gp/SKILL.md).

Vendored Google skills (`gemini-api-dev`, `gemini-live-api-dev`) are pinned in `skills-lock.json`: update
them with `npx skills update`, never by hand.

## Keep this skill current

Update together with `scripts/validate_skills.py`. Run `python scripts/validate_skills.py` after editing.
