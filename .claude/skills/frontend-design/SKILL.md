---
name: frontend-design
description: >-
  Make the Pawse UI distinctive and demo-ready instead of generic: consistent tokens, typography, visible
  agent progress, a hero moment. Use when someone asks to "make it look good", "polish the UI",
  "design the demo screen", or before the pitch.
---

# Frontend design

Judges remember one screen. Design that screen; keep the rest clean. The UI lives in `pawse/static/`
(`index.html`, `style.css`, `app.js`, `voice.js`; plain HTML/CSS/JS, no build step).

## 1. Respect the concept

Pawse is Mapify-inspired pink/gray (see [docs/AGENT_DEVELOPMENT.md](../../../docs/AGENT_DEVELOPMENT.md)).
Write one line in the commit before big changes: *"Feels <adjective>, the hero moment is <what reveals>."*

## 2. Tokens, not ad-hoc values

Colors live as custom properties in `:root` of `pawse/static/style.css` (`--ink`, `--muted`, `--green`
(the pink accent), `--paper`, `--line`, ...). Use them everywhere; add a token rather than a hex literal.
Type: one display font + one text font, big size contrast. Check `prefers-color-scheme: dark`.

## 3. Make the agents visible

- The agent run as a live timeline (status icon, agent name, short human label), not raw JSON.
- Show a "working" state within 200 ms of submit; stream results as they arrive.
- Clinic cards, cited policy clauses and the German script with subtitles as structured cards.
- Every simulated step carries a visible "simulated" label.

## 4. Polish (only after the story works)

- One entrance animation for the hero result, 150-300 ms, ease-out. No looping decoration.
- Keyboard and touch both complete the story; focus states visible; text never via `innerHTML` from untrusted data.
- Projector check: 1280x720, 125% zoom, readable from the back of the room. Narrow mobile width too.

## Anti-patterns

Gradient blobs, glassmorphism everywhere, emoji as core icons, six font sizes, centered body text,
lorem ipsum in the demo, tiny gray text on gray.

## Keep this skill current

Update the token list when `style.css` changes. Run `python scripts/validate_skills.py` after editing.
