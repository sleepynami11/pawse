"""Public-demo guard: host allowlist and a quota on paid endpoints. Off unless PAWSE_PUBLIC_DEMO=1."""
import os
import time
from collections import deque

LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]
# POST paths that spend Gemini/Gradium/Places quota. The keyless Mimi rehearsal is not listed.
PAID_PREFIXES = ("/api/v1/care/requests", "/api/v1/clinics/", "/api/v1/voice/", "/api/v1/agents/runs", "/api/v1/live/", "/api/v1/knowledge/search")
WINDOW = 3600
calls: dict[str, deque] = {}


def enabled():
    return os.getenv("PAWSE_PUBLIC_DEMO") == "1"


def allowed_hosts():
    extra = [h.strip() for h in os.getenv("PAWSE_ALLOWED_HOSTS", "").split(",") if h.strip()]
    return LOCAL_HOSTS + extra


def over_quota(owner, method, path):
    """Record a paid call; True when this session or the whole instance is over its hourly budget."""
    if not enabled() or method != "POST" or not path.startswith(PAID_PREFIXES):
        return False
    now = time.monotonic()
    per_session = int(os.getenv("PAWSE_SESSION_CALLS_PER_HOUR", "60"))
    total = int(os.getenv("PAWSE_TOTAL_CALLS_PER_HOUR", "600"))
    for key in list(calls):
        while calls[key] and now - calls[key][0] > WINDOW:
            calls[key].popleft()
        if not calls[key]:
            del calls[key]
    if len(calls.get(owner, ())) >= per_session or sum(map(len, calls.values())) >= total:
        return True
    calls.setdefault(owner, deque()).append(now)
    return False
