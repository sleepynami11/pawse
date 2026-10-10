"""Local, single-user Pawse API. OpenAPI is the generated frontend contract."""
import asyncio
import json
import os
import secrets
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .models import CareRequest, LegacyRequest, CareResult
from .service import care_events
from .legacy import capabilities, legacy_events
from .voice import router as voice_router
from .live import router as live_router
from .demo import router as demo_router
from .knowledge import router as knowledge_router
from .orchestration import router as orchestration_router
from .state import records, active, TTL, MAX_RECORDS, prune, remember
from . import public

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
app = FastAPI(title="Pawse Care API", version="0.2.0", description="Cat care navigation, nearby veterinary clinics, insurance contacts, and a bridge to the existing CatAgent.")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=public.allowed_hosts())


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # FastAPI's default error can echo inputs, including uploaded photos. Strip them.
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "fields": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]}})


@app.middleware("http")
async def local_session(request: Request, call_next):
    if request.method in {"POST", "PUT", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(status_code=403, content={"error": "cross_origin_request_rejected"})
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 4_500_000:
            return JSONResponse(status_code=413, content={"error": "request_too_large"})
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4_500_000:
                return JSONResponse(status_code=413, content={"error": "request_too_large"})
        request._body = bytes(body)
    owner = request.cookies.get("pawse_session") or secrets.token_urlsafe(32)
    request.state.owner = owner
    if public.over_quota(owner, request.method, request.url.path):
        return JSONResponse(status_code=429, content={"error": "demo_quota_reached", "message": "This public demo has reached its hourly limit. The Mimi rehearsal still works; try live features again later."})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if not request.cookies.get("pawse_session"):
        response.set_cookie("pawse_session", owner, httponly=True, samesite="strict", max_age=TTL, secure=request.url.scheme == "https")
    return response


def event_line(event):
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "mode": "public_demo" if public.enabled() else "local_single_user", "version": "0.2.0"}


@app.get("/api/v1/capabilities")
async def get_capabilities():
    return capabilities()


@app.post("/api/v1/care/requests", response_model=CareResult, status_code=201, responses={200: {"description": "SSE when stream=true", "content": {"text/event-stream": {"schema": {"type": "string"}}}}})
async def create_care(payload: CareRequest, request: Request, stream: bool = False):
    prune()
    owner = request.state.owner
    if owner in active or len(active) >= 5:
        raise HTTPException(429, "A care request is already active; try again shortly")
    if len(records) >= MAX_RECORDS:
        oldest = min(records, key=lambda k: records[k]["created"])
        del records[oldest]
    request_id = secrets.token_urlsafe(24)
    active.add(owner)
    async def events():
        try:
            yield {"type": "created", "request_id": request_id}
            async for event in care_events(payload):
                if event["type"] == "result":
                    event["request_id"] = request_id
                    remember(owner, event)
                yield event
        finally:
            active.discard(owner)
    if stream:
        async def body():
            async for event in events():
                yield event_line(event)
        return StreamingResponse(body(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})
    result = None
    async for event in events():
        if event["type"] == "result":
            result = event
    return JSONResponse(CareResult.model_validate(result).model_dump(), status_code=201)


@app.get("/api/v1/care/requests/{request_id}", response_model=CareResult)
async def get_care(request_id: str, request: Request):
    prune()
    record = records.get(request_id)
    if not record or record["owner"] != request.state.owner:
        raise HTTPException(404, "Request not found or expired")
    return record["result"]


@app.delete("/api/v1/care/requests/{request_id}", status_code=204)
async def delete_care(request_id: str, request: Request):
    await get_care(request_id, request)
    del records[request_id]


@app.post("/api/v1/agent/requests")
async def agent_request(payload: LegacyRequest, request: Request):
    if capabilities()["legacy_bridge"] == "needs_configuration":
        raise HTTPException(503, "Configure the legacy agent URL, user and allowed cat IDs first")
    allowed = {v.strip() for v in os.getenv("LEGACY_AGENT_CAT_IDS", "").split(",")}
    if str(payload.cat_id) not in allowed:
        raise HTTPException(403, "Cat ID is not permitted for this local user")
    async def body():
        try:
            async with asyncio.timeout(45):
                async for event in legacy_events(payload):
                    yield event_line(event)
        except Exception:
            yield event_line({"type": "error", "code": "legacy_agent_unavailable", "message": "The existing agent could not complete this request. Check its configuration and dependencies."})
    return StreamingResponse(body(), media_type="text/event-stream")


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static/index.html")

app.include_router(voice_router)
app.include_router(live_router)
app.include_router(demo_router)
app.include_router(knowledge_router)
app.include_router(orchestration_router)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
