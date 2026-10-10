# Hackathon notes

Pawse is being built specifically for the **Tech Europe AI Hackathon**, sponsored by **Google DeepMind**, as described by the project team.

The exact event edition, location, dates, submission URL, and judging criteria have not yet been recorded here. Add the official event link when available. This repository does not claim an award, official partnership, or product endorsement.

## Working pitch

> Pawse helps cat owners turn a worried moment into a clear next step: describe a concern or add a photo, find nearby veterinary care, keep insurance contacts ready, and prepare for a vet call in one app.

## Technology and prior work

The new unified app uses Gemini for structured text/photo care navigation. It includes independent MapifyAI and Google Places adapters, and a bridge to the team's pre-existing CatAgent. Real Gemini text connectivity has been verified. Live clinic discovery requires provider configuration. Gemini Live (`gemini-3.8-live`) runs end to end on the backend: locked ephemeral tokens, a live session and server-run tool calls, verified against the real API; the browser audio client is in progress. See [Gemini Live](GEMINI_LIVE.md).

The existing backend predates this event and must be disclosed as prior work. Identify the new `pawse/` interface and integration work separately in the submission. See [source import review](IMPORT_REVIEW.md).

## Temporary account setup

Following the [organizer-provided account guide](https://goo.gle/hackathon-account):

1. Sign into the assigned temporary Google account, preferably in a separate browser profile.
2. Open [AI Studio API Keys](https://aistudio.google.com/api-keys).
3. Import the assigned project if it is missing.
4. Create or retrieve a key; check the quota tier shown for that project.
5. Keep the key in local/server configuration only.

The guide says temporary accounts may be deleted as soon as the day after the event. Export code and generated assets before the event ends, and move any continuing deployment to your own project. Higher quotas are not unlimited usage.

Gotchas:

- A key pushed to GitHub gets every key in the project revoked. If one leaks, delete it in AI Studio and create a new one.
- Rate limits apply per project, not per key: teammates share them. Don't hammer the live key in loops; abuse can disqualify.
- Model choice, rate limits, and Live API notes: the [gemini skill](../.claude/skills/gemini/SKILL.md).

## Submission checklist

- [ ] Record official event details and submission requirements.
- [ ] Add team members with their consent.
- [ ] Document the implemented stack and setup commands.
- [ ] Add demo URL, screenshots, and a short video when available.
- [ ] Explain which Gemini capabilities actually work in the demo.
- [ ] Note limitations and any pre-existing components.
- [ ] Check that all assets have suitable licenses.
- [ ] Save work before temporary access expires.
