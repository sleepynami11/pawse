---
name: demo-check
description: >-
  Verify the Pawse demo story end to end in a real browser and through the API, capture screenshots,
  and check console errors. Use when someone says "does the demo work", "check the demo",
  "take screenshots", or before feature freeze and before pitching.
---

# Demo check

The demo story in [research/pet-insurance/demo-video-script.md](../../../research/pet-insurance/demo-video-script.md)
is the acceptance test.

## 1. Automated first

```bash
bash scripts/check.sh                                   # safety, skills, JS syntax, OpenAPI, pytest
uvicorn pawse.app:app --host 127.0.0.1 --port 8765      # in a second terminal
curl -s http://127.0.0.1:8765/docs >/dev/null && echo up
```

The rehearsal and demo-policy search work without provider keys. Story logic belongs in pytest
(`tests/test_orchestration.py`): assert visible outcomes (costs, citations, statuses), not internals.

## 2. Browser walkthrough

Open http://127.0.0.1:8765 and click through every scene of the story. With browser automation
(Playwright or the Chrome extension), capture a screenshot per scene and collect console errors:

```js
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
```

Look at every screenshot: overflow, cut-off text, mobile/narrow width, loading and error states,
"simulated" labels visible on every fake step. Keep screenshots out of git unless they go in the README.

## 3. Real providers

With keys in `.env`: run the care flow once with real Gemini, a voice preview with Gradium (owner
consent), and `python scripts/probe_models.py` for model access. Record results in
[docs/VALIDATION.md](../../../docs/VALIDATION.md); do not claim anything that did not run.

## 4. Demo-day checklist

- [ ] Story passes 3 times in a row on the demo machine (LLMs are flaky: tighten prompts or fake the step)
- [ ] Works on venue Wi-Fi / phone hotspot; rehearsal mode as last resort
- [ ] Microphone permission granted in the demo browser; backup video exists ([pitch](../pitch/SKILL.md))
- [ ] Zoom, notifications off, tabs pre-opened, demo state reset

## Keep this skill current

Keep commands in sync with the README quick start. Run `python scripts/validate_skills.py` after editing.
