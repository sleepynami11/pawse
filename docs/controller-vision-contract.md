# Pawse Vision Controller Contract

The Vision Agent separates what is visible from what the owner reports. **Current:** a photo can accompany a care request. **Proposed v1:** a separate observation resource, followed by bounded video input. [Multimodal contracts](MULTIMODAL_CONTRACTS.md) maps both stages to the other agents.

## 1. Current photo boundary

There is no `/vision` controller today. Use either `POST /api/v1/care/requests` or `POST /api/v1/agents/runs` with nested `care`; do not send both. Schema: `CareRequest.photo: Photo | null` in [models.py](../pawse/models.py).

| Field | Current contract |
| --- | --- |
| `photo.mime_type` | `image/jpeg`, `image/png` or `image/webp` |
| `photo.data` | Strict base64, at most 4,200,000 encoded characters; decoded payload 12–3,000,000 bytes |
| Image validation | Matches the expected JPEG/PNG/WebP signature; this is not a complete image-decoding/metadata sanitization pipeline |
| `query` | Up to 4,000 characters; optional when a photo or reported warning sign is present |
| `share_with_ai` | Explicit consent required before the photo is sent to Gemini |
| Response | Existing `Assessment` inside `CareResult`; no separate observations, bounding boxes, media ID or timestamped evidence |

Photos are sent to care assessment, not to the clinic discovery adapter. A photo cannot rule out an emergency. Owner-reported red flags retain the existing deterministic emergency rule even when Gemini fails or disagrees. Missing sharing consent keeps the fallback flow available without sending the image.

The care model uses `GEMINI_CARE_MODEL`, otherwise `GEMINI_MODEL`, otherwise `gemini-3-flash-preview`. The selected upgrade is `gemini-3.8-flash`, with access evidence in [Model allocation](MODEL_ALLOCATION.md); this contract does not switch configuration. Unsupported PDF/video MIME types return 422. Existing care errors, deadlines and SSE behavior follow the [Care contract](controller-care-contract.md).

## 2. Proposed observation controller

Proposed prefix: `/api/v1/cases/{case_id}/vision`. The orchestration module owns validated observations; media input must use the same case ownership and revision rules as [Case handoffs](controller-case-contract.md).

| Proposed route | Input | Success |
| --- | --- | --- |
| `POST /observations` | Multipart `file` and JSON `metadata`, case `If-Match` | 202 `VisionResult` with `status: queued` |
| `GET /observations/{observation_id}` | Same-owner case | 200 queued/running/complete/partial/failed/cancelled result |
| `DELETE /observations/{observation_id}` | Resource `If-Match` | 202 cancellation/deletion state; prevent late-result merge |
| `GET /observations/{observation_id}/deletion` | Same-owner case | 200 `pending`, `complete` or `retry_required` cleanup state |

Proposed metadata:

```json
{
  "media_kind": "photo",
  "owner_description": "Mimi seems to avoid putting weight on her left front paw.",
  "language": "en",
  "share_with_gemini": true
}
```

Metadata cannot supply the owner, source hash, case revision or a model diagnosis. The case ETag selects the input revision; the backend records `based_on_revision`. Language accepts `en`, `zh`, `de`, `hi`; preserve the original description. A later owner correction requires a new version/result.

Start with one JPEG/PNG/WebP photo per request, at most 3 MB decoded, and implement full decode, dimension bounds and metadata removal before this new route is exposed. For a subsequent video milestone, propose MP4/WebM, at most ten seconds and 3 MB, with server-validated duration and MIME. Sample at most ten timestamped frames, with bounded decoder resources; explicitly exclude video audio from this first visual-only path. These are application limits, not Gemini capacity claims. Longer video and audio/video fusion need a revised contract.

## 3. Vision-to-care result

`VisionResult` contains `observation_id`, `case_id`, `based_on_revision`, `media_kind`, `media_id`, `source_sha256`, `status`, `observations`, `not_assessable`, `questions`, `warnings`, `created_at` and `expires_at`.

Each observation has:

| Field | Meaning |
| --- | --- |
| `observation_id` | Stable ID within this result |
| `description` | Narrow visible description; no claimed diagnosis or accident classification |
| `evidence_ref` | Same-case photo/video `EvidenceRef` with hash and media/version locator |
| `time_start_ms`, `time_end_ms` | Null for a photo; actual source time range for video |
| `visibility` | `clear` or `limited`; not a calibrated medical probability |
| `review_state` | Initially `unreviewed`; owner correction must retain the original observation |

Use `not_assessable` for facts the input cannot show, such as pain severity or whether a fracture exists. Preserve the owner statement separately: “the owner reports a jump” and “limited view of the front paw” must not become “the video proves an accident.” Missing/occluded footage is a partial result, not reassurance.

The coordinator consumes source-linked observations as context for care questions. It must not replace reported red flags, infer unseen events or treat generated illustrations as clinical evidence. Merge only against a compatible case revision. Until the standalone controller exists, the existing photo assessment cannot be presented as this richer `VisionResult`.

## 4. Failure, retention and acceptance

Proposed synchronous failures follow the Case error contract, plus 413 for size/duration bounds and 415 for unsupported media. After 202, expose safe failure reasons such as `media_unreadable` or `vision_unavailable`. Impose a 45-second analysis deadline; preserve owner text when visual processing fails.

Keep source media, sampled frames and derived observations private with a proposed 24-hour expiry, at most ten retained visual assets and 30 MB of source media per case, and explicit deletion. Deletion must invalidate dependent evidence/drafts and clear provider copies if any were created. The deletion-status route tracks cleanup; ordinary reads return 404 once deleted. A deleted/cancelled result may not reappear when an old worker completes.

Acceptance covers a valid photo, poor visibility, spoofed formats, malformed image decoding, excessive dimensions, unsupported video, timestamps, provider timeout, deletion during work and a late result for an edited concern. Keep live media understanding verification separate from the existing successful synthetic-image model probe.
