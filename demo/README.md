# Demo video recorder

Records the 2-minute demo as a 1920x1080 video, scripted and repeatable, so a re-take after a UI change takes a
single command and no screen-recording session. Same pipeline as our SwissHacks 2026 DRIFTWATCH recorder.

The page being recorded is currently a **mock** ([`mock/index.html`](mock/index.html)): a static page that plays the
"Mimi is limping" story from [the demo script](../research/pet-insurance/demo-video-script.md) with canned lines,
cards and timings. It has no backend, model, calls or bookings. It shows a "DEMO MOCK · SIMULATED CALLS" pill, so
it is never mistaken for working features.

## Run

Node 20+, Python 3 (serves the mock), and ffmpeg on `PATH` for the mp4 (optional; without it you still get the webm).

```sh
cd demo
npm install
npx playwright install chromium   # first time only
npm run record:demo
```

Output in `demo/demo-out/` (git-ignored):

| File | What |
| --- | --- |
| `pawse-demo.mp4` | The deliverable: opening load trimmed, h264, synthesized click/glide soundtrack |
| `pawse-demo.webm` | Raw Playwright take, keeps the browser load |
| `trim.json`, `events.json` | Cut point and action log the post-step uses |

Knobs (environment variables):

- `SPEED=1.5`: faster take. It scales both the spec's holds and the mock's own pauses. The default (1) runs about 85 s.
- `DEMO_LOOPS=2`: repeat the clean pass, for a looping clip on a slide.

To preview the mock by hand: `npm run mock`, then open http://127.0.0.1:4173.

## How it works

1. [`e2e/demo-recording.spec.ts`](e2e/demo-recording.spec.ts) drives the page like a user would: it taps the mic, picks
   reply chips and chooses option A, with a visible cursor that glides along curved paths. Each `expect()` doubles
   as a smoke test, so a missing story beat fails the take. The spec writes where the load ends (`trim.json`) and
   every click and glide (`events.json`).
2. [`scripts/finalize-demo.mjs`](scripts/finalize-demo.mjs) trims the head, renders a soundtrack from the
   action log ([`scripts/demo-audio.mjs`](scripts/demo-audio.mjs), deterministic, unit-tested by `npm test`), and muxes
   it onto the mp4.

The voiceover and the simulated German call audio are not part of this pipeline. Add them in the video editor on top
of the mp4.

## Swapping the mock for the real app

Once the real app can run the story end to end, point `baseURL` and `webServer` in
[`playwright.config.ts`](playwright.config.ts) at it (for example `uvicorn pawse.app:app --port 8765`). Then keep the
same element names (`Talk to Pawse` button, reply chips, `#opt-a`, `data-state`) or update the locators in the spec.
