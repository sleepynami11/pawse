"""Check .claude/skills/*/SKILL.md: front matter, name = folder, description, relative links resolve,
a "Keep this skill current" section, and a row in the AGENTS.md catalog (both ways).

Third-party skills pinned in skills-lock.json (`npx skills add/update`) skip the "Keep current" rule.
Usage: python scripts/validate_skills.py  (part of scripts/check.sh and CI)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(".claude/skills")
agents = Path("AGENTS.md").read_text()
lock = Path("skills-lock.json")
vendored = set(json.loads(lock.read_text()).get("skills", {})) if lock.exists() else set()
errors = []
skills = sorted(d.name for d in ROOT.iterdir() if d.is_dir())
for name in skills:
    file = ROOT / name / "SKILL.md"
    if not file.exists():
        errors.append(f"{name}: missing SKILL.md")
        continue
    text = file.read_text()
    fm = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not fm:
        errors.append(f"{file}: no front matter")
        continue
    if not re.search(rf"^name:\s*{re.escape(name)}\s*$", fm.group(1), re.M):
        errors.append(f'{file}: name must be "{name}"')
    if not re.search(r"^description:", fm.group(1), re.M):
        errors.append(f"{file}: description missing")
    if name not in vendored and not re.search(r"^## Keep this skill current", text, re.M):
        errors.append(f'{file}: needs a "## Keep this skill current" section')
    for m in re.finditer(r"\]\(([^)#\s]+)(#[^)]*)?\)", text):
        target = m.group(1)
        if not re.match(r"https?:", target) and not (file.parent / target).exists():
            errors.append(f"{file}: broken link {target}")
    if f"(.claude/skills/{name}/SKILL.md)" not in agents:
        errors.append(f"{name}: no row in the AGENTS.md skills catalog")
for m in re.finditer(r"\(\.claude/skills/([^/]+)/SKILL\.md\)", agents):
    if m.group(1) not in skills:
        errors.append(f'AGENTS.md lists skill "{m.group(1)}" which does not exist')
if errors:
    print("✖ Skill check:\n" + "\n".join(f"  - {e}" for e in errors), file=sys.stderr)
    sys.exit(1)
print(f"✔ {len(skills)} skills valid and catalogued.")
