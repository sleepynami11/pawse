# Team integration snapshot

Reviewed 10 October 2026 against GitHub `main` at `35a9ea5`, open PRs and module branches. This snapshot connects teammate work to Pawse's existing [multimodal contracts](MULTIMODAL_CONTRACTS.md). Status is evidence-based: merged code, branch experiments and proposed behavior are separate.

## Already on main and in the local checkout

| Work | Source | Integration effect |
| --- | --- | --- |
| Gemini Live backend | [PR #21](https://github.com/yyyuanfish/pawse/pull/21) | Tokens and four validated tools; browser capture/playback still pending |
| Demo recording tooling | [PR #16](https://github.com/yyyuanfish/pawse/pull/16) | Scripted, mocked rehearsal recording; not a real call recording |
| Cloud Run/container and public request quota | [PR #28](https://github.com/yyyuanfish/pawse/pull/28) | Optional public-demo mode; host allowlist, Secret Manager deployment script and process-local limits |
| Pitch/tagline | [PR #35](https://github.com/yyyuanfish/pawse/pull/35) | Updated README positioning and suggested About copy |
| Entire settings and agent guidance | [PR #34](https://github.com/yyyuanfish/pawse/pull/34) | Shared configuration and Claude hooks; does not establish local CLI installation, Codex hooks or hosted import |

The default local app and public demo use the same API. The [API contract](API_CONTRACT.md#runtime-and-session-boundaries) now describes both. The public quota response supplies the `detail` field consumed by all current frontend request helpers and preserves common response headers/session setup. Configuration defaults are listed in `.env.example`.

No deployment was performed as part of this alignment. A container/deploy script is not evidence of a working public URL. Keep keys in the server secret store; one process/instance reduces state fragmentation but does not provide durable storage or authenticated accounts.

## Work available outside main

| Work | Inspected revision | What is reusable | Remaining boundary |
| --- | --- | --- | --- |
| Gradium streaming STT/TTS experiment | [`9f033a4`](https://github.com/yyyuanfish/pawse/commit/9f033a4f4cd7075d9a6b622c9e9541553b70fe15), `feat/voice-calling` | WebSocket client and synthetic latency spike in `pawse/gradium_stream.py` / `scripts/gradium_spike.py` | No call controller/media bridge; review voice selection, readiness, bounds and cleanup before runtime integration |
| Browser/microphone/Live tests | [PR #29](https://github.com/yyyuanfish/pawse/pull/29), `f08c1c4` | Fake microphone, fake Live socket, layout checks and optional real-recording metrics | PR reports 31 failing browser checks against the old UI; required frontend hooks/behavior are not implemented yet |

The frontend, orchestration and RAG module branches inspected in this review had no additional commits beyond main. This says nothing about teammates' unpushed local work. Old remote branch names can survive squash merges; their presence alone does not mean missing functionality.

## Streaming voice handoff to preserve

The branch experiment sends `ulaw_8000` through Gradium STT/TTS, intended for a future telephone media bridge. It is a low-level helper and opt-in experiment, not a replacement for the current recorded WAV, cloning/localization or German-script routes.

Before integrating it into a real action:

1. Resolve the owner's approved German voice from the session/profile. The experiment's `voice_for()` falls back to a standard voice when a configured clone is absent; the product must instead require an explicit standard-voice choice or report missing own-voice setup.
2. Keep Chinese/Hindi owner input on the Gemini path; a German/English streaming experiment does not validate every language or own-voice cloning.
3. Establish provider readiness, bounded frame sizes, deadlines and cancellation/close behavior. The inspected client uses `max_size=None`, and `open()` sends setup without awaiting readiness; the controller must not assume setup acceptance.
4. Treat provider error payloads as internal diagnostic data and return safe public errors. Do not expose raw provider messages, credentials or arbitrary voice IDs.
5. Apply the [Action contract](controller-action-contract.md): recipient, purpose, approved revision and disclosure first; transport status separate from actual booking/coverage outcome.
6. Add mocked streaming tests, then a separately consented provider check. The teammate commit reports latency observations; they were not reproduced in this checkout and are not an SLA.

The current clone/localization/preview/save lifecycle remains authoritative in the [Voice contract](controller-voice-contract.md). No standalone streaming code has been copied into main by this alignment; the owning voice branch remains the integration source.

## Next integration order

1. Frontend completes Live microphone/playback and the agreed browser-test hooks; run PR #29's opt-in suite, not only backend checks.
2. Voice integrates the streaming experiment behind reviewed actions, with explicit own-voice selection and safe lifecycle handling.
3. Evidence/data implements the Document → reviewed private evidence path using the new contracts; the current demo corpus stays separate.
4. Connect calendar, booking and taxi only with actual provider outcomes; the story's simulated results remain labeled.

Entire onboarding is tracked separately in [issue #33](https://github.com/yyyuanfish/pawse/issues/33). Do not infer permission to upload private transcripts from shared repository settings. Session capture/import and hosted repository access require their own setup; this integration review did not enable them or upload conversation history.
