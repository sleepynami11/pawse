# Pawse Agent Controller Contract

Implementation: [pawse/orchestration.py](../pawse/orchestration.py). Prefix: `/api/v1/agents`. This is a bounded workflow over named responsibilities, not a recursive autonomous loop. It reuses the care service and exposes execution states and unresolved actions.

## 1. Agent graph

`GET /graph` → **200** `AgentGraph`.

Top-level fields: `mode: bounded_workflow`, `agents: AgentSpec[]`, `parallel_groups`, `deadline_seconds: 45`, `note`. Each spec has `id`, `name`, `implementation`, `owner`, nullable `model`, `availability`, `responsibility`, `depends_on` and nullable `endpoint`. Here `owner` means a source module, not a user identity or team size.

| Stable agent ID | Implementation / module | Current execution boundary |
| --- | --- | --- |
| `intake` | Deterministic / `llm` | Validated input and immediate warning-sign guidance |
| `care_guidance` | Model / `llm` | Gemini assessment, concurrent with clinic retrieval |
| `nearby_vets` | Tool / `rag_data` | Places or Mapify adapter |
| `policy_evidence` | Tool / `rag_data` | Separate synthetic knowledge endpoint; not called by a run |
| `ranking` | Deterministic / `llm` | Opening status, distance and rating |
| `orchestrator` | Deterministic / `llm` | Merge partial results and expose action gates |
| `communication` | Model and voice tools / `voice` | Separate reviewed script/audio flow; not called by a run |

Only `care_guidance` and `nearby_vets` are in `parallel_groups`. `depends_on` expresses the role relationship; it does not promise automatic execution of every listed agent. `configured_not_verified` means a setting exists, not a successful provider call. The actual model string is resolved from server configuration; do not hardcode it into the frontend.

## 2. Start a run

`POST /runs` → **201** `AgentRunResult`. Request schema: `AgentRunRequest`.

<!-- schema: AgentRunRequest -->
```json
{
  "care": {
    "query": "Mimi is limping after jumping off a wardrobe.",
    "cat_name": "Mimi",
    "location": {"lat": 47.3769, "lng": 8.5417},
    "language": "en",
    "share_with_ai": false,
    "share_location": false
  }
}
```

`care` follows the [care request contract](controller-care-contract.md). There is no `stream` option for this route. A run returns one final JSON document:

| Field | Contract |
| --- | --- |
| `run_id` | UUID string allocated for this run |
| `mode` | Always `bounded_workflow` |
| `status` | `complete` or `partial`, matching nested care provider completion |
| `care` | Full `CareResult`; its `request_id` currently equals `run_id` |
| `trace` | One final `AgentTrace` per role; not a chronological event log |
| `actions` | Current `ActionGate[]` with missing requirements |
| `external_actions_performed` | Always false |
| `note` | Explains that navigation completion does not mean external actions happened |

The nested care result is retrievable/deletable through `/api/v1/care/requests/{request_id}` in the same session. There is no run-history, trace-history, run-polling or run-stream endpoint. The server retains the care summary, not the full trace.

## 3. Trace contract

Each trace has `agent_id`, `state`, `detail`, `elapsed_ms`. The elapsed value is the offset from workflow start when that role was last updated; it is **not per-agent execution duration**. List order follows graph definition, not completion time.

| State | Meaning |
| --- | --- |
| `pending`, `running` | Internal lifecycle states; current returned traces contain final states |
| `complete` | That role finished its responsibility, which may be merging a partial result |
| `unavailable` | Provider/configuration/operation failed |
| `timeout` | Deadline prevented completion |
| `skipped` | A prerequisite such as consent/location/successful retrieval was absent |
| `review_required` | Separate owner-reviewed communication is needed |
| `evidence_required` | Actual policy evidence is missing for this live case |

Do not equate trace `complete` with overall run `complete`. For example, the orchestrator can finish merging a partial result while clinic retrieval is unavailable. When sharing consent is absent, care provider status is `unavailable` but the corresponding agent trace is `skipped`; these fields describe different boundaries.

## 4. Action gates

Each gate includes `id`, `state`, a list of `required` conditions and nullable `endpoint`.

| Action ID | State now | Required next integration/evidence |
| --- | --- | --- |
| `german_script` | `review_required` | Review handoff facts, obtain separate Gemini consent, request and review script via `/api/v1/voice/scripts` |
| `insurance_coverage` | `evidence_required` | Actual policy, dates, remaining deductible/limits and relevant insurer confirmation |
| `outbound_call` | `not_connected` | Telephone transport, verified number, recipient/purpose approval and AI disclosure |
| `appointment` | `not_connected` | Real offered slot, owner choice and clinic confirmation |
| `calendar` | `not_connected` | Calendar connector, permission and confirmed appointment details |
| `taxi` | `not_connected` | Pickup/destination, carrier acceptance/fare, owner choice and provider confirmation |

These are explanatory gates, not action commands. There is no endpoint to mark a gate completed. A separate script or audio request does not mutate the stored run or establish that a call took place.

## 5. Execution and errors

The run consumes the same care event generator used by direct care requests, with a 45-second outer deadline around the 40-second care budget. It preserves already received assessment/clinic/contact information on interruption where possible and returns a partial result with safe warning codes.

Care and run controllers share one active-work pool: one per session and five globally. Input validation returns 422; active-work rejection returns 429. The normal workflow handles provider errors inside a 201 partial result. The run does not automatically invoke RAG, voice, a second reasoning model, phone, calendar or bookings.

## 6. Module handoff

The orchestration module owns these role IDs and state semantics. Frontend consumes them without fabricating progress. RAG/data supplies normalized clinics and separately scoped evidence. Voice consumes owner-reviewed handoff facts through its own contract. Proposed action execution requires a new contract and evidence of actual provider confirmation.

Use `tests/test_orchestration.py` for deadline, partial-result, consent, trace, action-gate and shared-cache checks. See [Controller–Service](controller-service-contract.md) for function boundaries and [Agent development](AGENT_DEVELOPMENT.md) for branches.
