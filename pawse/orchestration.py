"""Observable, bounded agent workflow over the existing care providers.

An agent is a named responsibility here, not an unrestricted autonomous loop.
The care model and place retrieval run concurrently in ``care_events``. Policy
evidence and external actions remain explicit gates, never invented successes.
"""
import asyncio
import os
import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from .models import Assessment, CareRequest, CareResult, Clinic, InsuranceResult, Model
from .providers import fallback_assessment, maps_link
from .service import care_events
from .state import active as active_runs, remember

router = APIRouter(prefix="/api/v1/agents", tags=["Agent orchestration"])
RUN_DEADLINE_SECONDS = 45

AgentId = Literal["intake", "care_guidance", "nearby_vets", "policy_evidence", "ranking", "communication", "orchestrator"]
AgentState = Literal["pending", "running", "complete", "unavailable", "timeout", "skipped", "review_required", "evidence_required"]


class AgentSpec(Model):
    id: AgentId
    name: str
    implementation: Literal["model", "tool", "deterministic", "model_and_voice_tools"]
    owner: Literal["frontend", "llm", "voice", "rag_data"]
    model: str | None = None
    availability: str
    responsibility: str
    depends_on: list[AgentId] = Field(default_factory=list)
    endpoint: str | None = None


class AgentGraph(Model):
    mode: Literal["bounded_workflow"] = "bounded_workflow"
    agents: list[AgentSpec]
    parallel_groups: list[list[AgentId]]
    deadline_seconds: int
    note: str


class AgentTrace(Model):
    agent_id: AgentId
    state: AgentState = "pending"
    detail: str
    elapsed_ms: int = 0


class ActionGate(Model):
    id: Literal["german_script", "insurance_coverage", "outbound_call", "appointment", "calendar", "taxi"]
    state: Literal["review_required", "evidence_required", "not_connected"]
    required: list[str]
    endpoint: str | None = None


class AgentRunRequest(Model):
    care: CareRequest


class AgentRunResult(Model):
    run_id: str
    mode: Literal["bounded_workflow"] = "bounded_workflow"
    status: Literal["complete", "partial"]
    care: CareResult
    trace: list[AgentTrace]
    actions: list[ActionGate]
    external_actions_performed: Literal[False] = False
    note: str = "Run completion means care navigation finished. Calls, coverage decisions, appointments and calendar changes have not been made."


def agent_graph():
    model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    care_model = os.getenv("GEMINI_CARE_MODEL") or model
    voice_model = os.getenv("GEMINI_VOICE_MODEL") or model
    gemini = "configured_not_verified" if os.getenv("GEMINI_API_KEY") else "needs_configuration"
    places = "configured_not_verified" if os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("MAPIFY_BASE_URL") else "needs_configuration"
    return AgentGraph(agents=[
        AgentSpec(id="intake", name="Intake and safety", implementation="deterministic", owner="llm",
                  availability="implemented", responsibility="Validate input and consent; immediately surface owner-reported warning signs."),
        AgentSpec(id="care_guidance", name="Care guidance", implementation="model", owner="llm", model=care_model,
                  availability=gemini, depends_on=["intake"], responsibility="Use text and an optional photo to prepare questions for a veterinarian; no diagnosis."),
        AgentSpec(id="nearby_vets", name="Nearby veterinary practices", implementation="tool", owner="rag_data",
                  availability=places, depends_on=["intake"], responsibility="Retrieve provider-backed clinics, contacts and reported opening hours; unknowns stay unknown."),
        AgentSpec(id="policy_evidence", name="Policy evidence", implementation="tool", owner="rag_data",
                  availability="local_synthetic_only", depends_on=["intake"], endpoint="/api/v1/knowledge/search",
                  responsibility="Retrieve cited demo policy clauses. A live case needs the owner's actual policy and confirmed coverage; synthetic terms are never applied."),
        AgentSpec(id="ranking", name="Ranking and cost rules", implementation="deterministic", owner="llm",
                  availability="implemented", depends_on=["nearby_vets"], responsibility="Rank clinics by reported opening status, distance and rating; use arithmetic only for evidenced cost inputs."),
        AgentSpec(id="orchestrator", name="Case coordinator", implementation="deterministic", owner="llm",
                  availability="implemented", depends_on=["care_guidance", "ranking", "policy_evidence"],
                  responsibility="Merge available evidence with a deadline, retain partial results, and expose review and connection gates."),
        AgentSpec(id="communication", name="Multilingual communication", implementation="model_and_voice_tools", owner="voice", model=voice_model,
                  availability="review_required", depends_on=["orchestrator"], endpoint="/api/v1/voice/scripts",
                  responsibility="Prepare reviewed German scripts and subtitles with Gemini; use Gradium for an owner-consented voice. Telephone transport is not connected."),
    ], parallel_groups=[["care_guidance", "nearby_vets"]], deadline_seconds=RUN_DEADLINE_SECONDS,
        note="Configured means a credential or URL exists, not a successful live check. The current run executes care guidance, clinic retrieval, ranking and handoff; policy retrieval and voice have separate contracts. Model calls are bounded; there is no recursive agent loop.")


def action_gates():
    return [
        ActionGate(id="german_script", state="review_required", endpoint="/api/v1/voice/scripts",
                   required=["Owner reviews the handoff facts", "Separate Gemini consent", "Owner reviews the German script and subtitles before sharing"]),
        ActionGate(id="insurance_coverage", state="evidence_required",
                   required=["Owner's actual policy and effective dates", "Remaining deductible and limits", "Insurer confirmation where required"]),
        ActionGate(id="outbound_call", state="not_connected",
                   required=["Telephone transport integration", "Verified recipient number", "Owner approval of recipient and purpose", "AI-assistant disclosure"]),
        ActionGate(id="appointment", state="not_connected",
                   required=["Clinic offers an actual slot", "Owner confirms that slot", "Clinic confirms the booking"]),
        ActionGate(id="calendar", state="not_connected",
                   required=["Calendar connector and owner permission", "Confirmed appointment details"]),
        ActionGate(id="taxi", state="not_connected",
                   required=["Confirmed pickup and destination", "Carrier acceptance and fare", "Owner approves the ride", "Taxi provider confirms"]),
    ]


def fallback_result(req, request_id):
    return CareResult(request_id=request_id, status="partial", assessment=fallback_assessment(req), clinics=[],
                      handoff=f"Cat: {req.cat_name}\nOwner's concern: {req.query or 'Photo / warning signs supplied'}",
                      warnings=["workflow_unavailable"], providers={"assessment": "unavailable", "clinics": "unavailable"},
                      elapsed_ms=0, target_seconds=60, search_url=maps_link("emergency veterinarian", req.location),
                      completeness="Partial care navigation only. No call, appointment or insurance approval has been made.")


async def run_workflow(req: CareRequest):
    started = time.monotonic()
    run_id = str(uuid.uuid4())
    trace = {spec.id: AgentTrace(agent_id=spec.id, detail=spec.responsibility) for spec in agent_graph().agents}

    def update(agent, state, detail=None):
        trace[agent].state = state
        trace[agent].elapsed_ms = round((time.monotonic() - started) * 1000)
        if detail is not None:
            trace[agent].detail = detail

    update("intake", "complete", "Input validated. Reported warning signs are handled before provider results.")
    update("orchestrator", "running")
    update("policy_evidence", "evidence_required", "No actual policy was supplied to this run. User-provided insurer contact is retained with coverage unconfirmed. Synthetic demo terms are not applied.")
    update("communication", "review_required", "Review the handoff, then submit a separate consented script or voice request. No call was made.")
    result = fallback_result(req, run_id)
    result.providers = {"assessment": "pending", "clinics": "pending"}
    provider_agents = {"assessment": "care_guidance", "clinics": "nearby_vets"}
    try:
        async with asyncio.timeout(RUN_DEADLINE_SECONDS):
            async for event in care_events(req):
                if event["type"] == "progress" and event.get("agent") in provider_agents:
                    state = "running" if event["status"] == "starting" else event["status"]
                    update(provider_agents[event["agent"]], state)
                    result.providers[event["agent"]] = state
                elif event["type"] in {"safety", "assessment"}:
                    result.assessment = Assessment.model_validate(event["assessment"])
                elif event["type"] == "clinics":
                    result.clinics = [Clinic.model_validate(clinic) for clinic in event["clinics"]]
                elif event["type"] == "insurance":
                    result.insurance = InsuranceResult.model_validate(event["insurance"]) if event.get("insurance") else None
                elif event["type"] == "result":
                    result = CareResult.model_validate({**event, "request_id": run_id})
    except TimeoutError:
        result.warnings = ["workflow_deadline_reached"]
        result.providers = {name: state if state == "complete" else "timeout" for name, state in result.providers.items()}
    except Exception:
        # Provider payloads and exception text can contain private data.
        result.warnings = ["workflow_unavailable"]
    result.providers = {name: state if state in {"complete", "unavailable", "timeout"} else "unavailable" for name, state in result.providers.items()}
    result.status = "complete" if all(state == "complete" for state in result.providers.values()) else "partial"
    if result.warnings in (["workflow_unavailable"], ["workflow_deadline_reached"]):
        result.handoff += "\nCare-navigation summary (not a diagnosis): " + result.assessment.summary
    for provider, agent in provider_agents.items():
        state = result.providers.get(provider, "unavailable")
        update(agent, state if state in {"complete", "unavailable", "timeout"} else "unavailable")
    if not req.share_with_ai:
        update("care_guidance", "skipped", "Gemini was not given consent; deterministic warning-sign guidance remains available.")
    if not req.location or not req.share_location:
        update("nearby_vets", "skipped", "Clinic retrieval needs a location and separate location-sharing consent.")
    if result.providers.get("clinics") == "complete":
        update("ranking", "complete", f"Ranked {len(result.clinics)} retrieved clinics using reported opening status, distance and rating. No travel-time or treatment-price estimate was invented.")
    else:
        update("ranking", "skipped", "No successful clinic retrieval to rank. A manual maps search remains available.")
    update("orchestrator", "complete", "Merged provider results and retained explicit evidence and external-action gates.")
    result.elapsed_ms = round((time.monotonic() - started) * 1000)
    return AgentRunResult(run_id=run_id, status=result.status, care=result, trace=list(trace.values()), actions=action_gates())


@router.get("/graph", response_model=AgentGraph)
async def graph():
    return agent_graph()


@router.post("/runs", response_model=AgentRunResult, status_code=201)
async def create_run(payload: AgentRunRequest, request: Request):
    owner = request.state.owner
    if owner in active_runs or len(active_runs) >= 5:
        raise HTTPException(429, "An agent run is already active; try again shortly")
    active_runs.add(owner)
    try:
        result = await run_workflow(payload.care)
        remember(owner, result.care.model_dump())
        return result
    finally:
        active_runs.discard(owner)
