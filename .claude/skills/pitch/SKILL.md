---
name: pitch
description: >-
  Prepare the pitch, live-demo script, backup video and README submission text for Pawse.
  Use when someone says "pitch", "slides", "demo script", "submission", "write the README",
  "record the video", or it is less than 2 hours before demos.
---

# Pitch

Judges score: problem/impact, working demo, technical depth (how agentic), use of partner tech
(Google DeepMind Gemini, Gradium), presentation. Structure the time around the live demo.
Event facts and open checklist: [docs/HACKATHON.md](../../../docs/HACKATHON.md).

## 1. Script

Start from [research/pet-insurance/demo-video-script.md](../../../research/pet-insurance/demo-video-script.md) (the Mimi story).

| Time | Beat | Content |
|---|---|---|
| 0:00-0:20 | Hook | A worried owner, a limping cat, a foreign-language phone call ahead. |
| 0:20-0:35 | Promise | The one-liner from the README overview. |
| 0:35-2:05 | **Live demo** | Narrate what the *agents* decide (care, clinics, policy citation, German script in the owner's voice). Hit the wow moment by ~1:30. |
| 2:05-2:35 | How it works | One architecture sentence + Gemini + Gradium + one hard thing you solved. |
| 2:35-3:00 | Next + ask | Real telephony, live policy ingestion, who pays. End on "Pawse". |

Write spoken sentences, rehearse with a timer twice, cut anything over time.

## 2. Honesty

Say what is simulated (vet/insurer/taxi replies, booking, claim submission). Claim only what
[docs/VALIDATION.md](../../../docs/VALIDATION.md) records as verified.

## 3. Backup video (before freeze)

Record the full demo path (1080p, at most 2 min). If the live demo fails, switch to it without
apologising. Upload unlisted and link it in the README.

## 4. README for submission

Keep the README structure; add at the top: live/video links, team with GitHub handles, 1-2 screenshots.

## Keep this skill current

Adjust judging criteria and timing to the event's rules. Run `python scripts/validate_skills.py` after editing.
