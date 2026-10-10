from fastapi.testclient import TestClient

from pawse import public
from pawse.app import app


def setup_function():
    public.calls.clear()


def test_quota_off_by_default(monkeypatch):
    monkeypatch.delenv("PAWSE_PUBLIC_DEMO", raising=False)
    assert not any(public.over_quota("a", "POST", "/api/v1/voice/scripts") for _ in range(100))


def test_paid_calls_capped_per_session_but_rehearsal_stays_open(monkeypatch):
    monkeypatch.setenv("PAWSE_PUBLIC_DEMO", "1")
    monkeypatch.setenv("PAWSE_SESSION_CALLS_PER_HOUR", "2")
    with TestClient(app) as c:
        body = {"text": "hi"}
        codes = [c.post("/api/v1/knowledge/search", json=body).status_code for _ in range(3)]
        assert 429 not in codes[:2] and codes[2] == 429
        assert c.post("/api/v1/knowledge/search", json=body).json()["error"] == "demo_quota_reached"
        assert c.get("/api/v1/demo/mimi").status_code == 200
        assert c.get("/api/v1/health").json()["mode"] == "public_demo"
    with TestClient(app) as other:
        assert other.post("/api/v1/knowledge/search", json=body).status_code != 429


def test_total_cap_covers_all_sessions(monkeypatch):
    monkeypatch.setenv("PAWSE_PUBLIC_DEMO", "1")
    monkeypatch.setenv("PAWSE_TOTAL_CALLS_PER_HOUR", "3")
    assert [public.over_quota(s, "POST", "/api/v1/care/requests") for s in "abcd"] == [False, False, False, True]
    assert not public.over_quota("e", "GET", "/api/v1/care/requests/x")


def test_extra_hosts_come_from_env(monkeypatch):
    monkeypatch.setenv("PAWSE_ALLOWED_HOSTS", "pawse-abc.a.run.app, demo.example")
    assert public.allowed_hosts()[-2:] == ["pawse-abc.a.run.app", "demo.example"]
    monkeypatch.delenv("PAWSE_ALLOWED_HOSTS")
    assert public.allowed_hosts() == public.LOCAL_HOSTS
