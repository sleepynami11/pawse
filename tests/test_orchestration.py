import asyncio

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pawse import orchestration, service
from pawse.models import Assessment, CareRequest, Clinic, Location


def states(result):
    return {item.agent_id: item.state for item in result.trace}


def test_graph_has_seven_roles_and_separates_models_from_tools(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    monkeypatch.delenv("GEMINI_CARE_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_VOICE_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "private-test-key")
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("MAPIFY_BASE_URL", raising=False)
    graph = orchestration.agent_graph()
    by_id = {agent.id: agent for agent in graph.agents}
    assert len(by_id) == 7
    assert graph.parallel_groups == [["care_guidance", "nearby_vets"]]
    assert by_id["care_guidance"].model == "test-model"
    assert by_id["orchestrator"].model is None
    assert by_id["nearby_vets"].availability == "needs_configuration"
    assert by_id["policy_evidence"].availability == "local_synthetic_only"
    assert "private-test-key" not in graph.model_dump_json()
    completed = set()
    while len(completed) < len(by_id):
        ready = {id_ for id_, agent in by_id.items() if set(agent.depends_on) <= completed} - completed
        assert ready, "Agent dependency graph must be acyclic"
        completed |= ready


def test_run_reuses_concurrent_care_and_retrieval_and_preserves_action_gates(monkeypatch):
    async def scenario():
        assessment_started, places_started = asyncio.Event(), asyncio.Event()

        async def assess(req, client):
            assessment_started.set()
            await asyncio.wait_for(places_started.wait(), 1)
            return Assessment(urgency="contact_vet", summary="Ask a veterinarian to assess the limp.", source="gemini")

        async def discover(req, client):
            places_started.set()
            await asyncio.wait_for(assessment_started.wait(), 1)
            return [Clinic(id="test-vet", name="Example clinic", source="mapify", retrieved_at="2026-10-10T12:00:00Z", open_now=None)]

        monkeypatch.setattr(service, "assess", assess)
        monkeypatch.setattr(service, "discover", discover)
        return await orchestration.run_workflow(CareRequest(query="Mimi is limping", share_with_ai=True,
                                                              share_location=True, location=Location(lat=47.37, lng=8.54)))

    result = asyncio.run(scenario())
    assert result.status == "complete"
    assert states(result)["care_guidance"] == "complete"
    assert states(result)["nearby_vets"] == "complete"
    assert states(result)["policy_evidence"] == "evidence_required"
    assert states(result)["communication"] == "review_required"
    assert result.care.clinics[0].open_now is None
    assert result.care.clinics[0].reasons == ["Opening hours unconfirmed"]
    assert not result.external_actions_performed
    assert all(gate.state != "complete" for gate in result.actions)
    assert next(gate for gate in result.actions if gate.id == "outbound_call").state == "not_connected"


def test_deadline_retains_completed_guidance_and_cancels_pending_work(monkeypatch):
    cancelled = []

    async def delayed(req):
        try:
            yield {"type": "assessment", "assessment": Assessment(summary="Retained guidance", source="gemini").model_dump()}
            yield {"type": "progress", "agent": "assessment", "status": "complete"}
            await asyncio.sleep(20)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(orchestration, "care_events", delayed)
    graph = orchestration.agent_graph()
    monkeypatch.setattr(orchestration, "RUN_DEADLINE_SECONDS", 0.01)
    monkeypatch.setattr(orchestration, "agent_graph", lambda: graph)
    result = asyncio.run(orchestration.run_workflow(CareRequest(query="limping", share_with_ai=True,
                                                                  share_location=True, location=Location(lat=47.37, lng=8.54))))
    assert result.status == "partial"
    assert result.care.assessment.summary == "Retained guidance"
    assert states(result)["care_guidance"] == "complete"
    assert states(result)["nearby_vets"] == "timeout"
    assert result.care.warnings == ["workflow_deadline_reached"]
    assert cancelled == [True]


def test_no_consent_keeps_emergency_fallback_without_network_or_policy_claims():
    result = asyncio.run(orchestration.run_workflow(CareRequest(query="breathing trouble", red_flags=["breathing_difficulty"])))
    assert result.status == "partial"
    assert result.care.assessment.urgency == "emergency"
    assert states(result)["care_guidance"] == "skipped"
    assert states(result)["nearby_vets"] == "skipped"
    assert result.care.insurance is None
    assert "synthetic" in next(item.detail.lower() for item in result.trace if item.agent_id == "policy_evidence")


def test_provider_exception_is_sanitized_and_terminal_states_are_reported(monkeypatch):
    async def broken(req):
        raise RuntimeError("secret-provider-response")
        yield

    monkeypatch.setattr(orchestration, "care_events", broken)
    result = asyncio.run(orchestration.run_workflow(CareRequest(query="limping", share_with_ai=True)))
    assert result.status == "partial"
    assert result.care.warnings == ["workflow_unavailable"]
    assert "secret-provider-response" not in result.model_dump_json()
    assert all(trace.state not in {"running", "pending"} for trace in result.trace)


def test_router_contract_and_per_session_concurrency_gate():
    app = FastAPI()

    @app.middleware("http")
    async def owner(request: Request, call_next):
        request.state.owner = "test-owner"
        return await call_next(request)

    app.include_router(orchestration.router)
    with TestClient(app) as client:
        assert client.get("/api/v1/agents/graph").status_code == 200
        assert client.post("/api/v1/agents/runs", json={"care": {"query": "limping"}}).status_code == 201
        assert "test-owner" not in orchestration.active_runs
        orchestration.active_runs.add("test-owner")
        try:
            assert client.post("/api/v1/agents/runs", json={"care": {"query": "limping"}}).status_code == 429
        finally:
            orchestration.active_runs.discard("test-owner")
        assert client.post("/api/v1/agents/runs", json={"care": {"query": "limping"}, "place_call": True}).status_code == 422
