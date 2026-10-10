"""Explicit bridge to the existing agent, bound to a configured development user."""
import json
import os
from pathlib import Path
import httpx
from .models import ANALYSIS_TYPES
from .providers import ProviderError


def model_ids():
    """Model ids the backend will use (env defaults only, never keys), so the UI can say what runs."""
    base = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    return {"care": os.getenv("GEMINI_CARE_MODEL") or base,
            "voice": os.getenv("GEMINI_VOICE_MODEL") or base,
            "live": os.getenv("GEMINI_LIVE_MODEL") or "gemini-3.8-live"}


def capabilities():
    catalog = json.loads((Path(__file__).parent / "legacy_catalog.json").read_text())
    configured = bool(os.getenv("LEGACY_AGENT_BASE_URL") and os.getenv("LEGACY_AGENT_USER_ID") and os.getenv("LEGACY_AGENT_CAT_IDS"))
    return {"new_features": [
        {"id": "care_navigation", "status": "implemented"},
        {"id": "gemini_text_and_photo", "status": "configured" if os.getenv("GEMINI_API_KEY") else "needs_configuration"},
        {"id": "nearby_clinics", "status": "configured" if os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("MAPIFY_BASE_URL") else "needs_configuration"},
        {"id": "insurance_contact", "status": "user_provided"},
        {"id": "click_to_call", "status": "implemented"},
        {"id": "multilingual_audio_and_scripts", "status": "configured" if os.getenv("GEMINI_API_KEY") else "needs_configuration"},
        {"id": "gradium_voice_clone_and_german_audio", "status": "configured_not_verified" if os.getenv("GRADIUM_API_KEY") else "needs_configuration"},
        {"id": "mimi_story", "status": "synthetic_demo"},
        {"id": "outbound_phone_calls", "status": "not_connected"}],
        "models": model_ids(),
        "clinic_providers": [n for n, on in (("google_places", os.getenv("GOOGLE_PLACES_API_KEY")), ("mapify", os.getenv("MAPIFY_BASE_URL"))) if on],
        "legacy_bridge": "configured_not_verified" if configured else "needs_configuration",
        "legacy_intents": catalog["intents"], "legacy_tools": catalog["tools"],
        "analysis_types": list(ANALYSIS_TYPES),
        "note": "Catalogued source capabilities are not a runtime guarantee. Knowledge collections, device services, storage and legacy model credentials may still be required."}


async def legacy_events(req):
    base = os.getenv("LEGACY_AGENT_BASE_URL", "").rstrip("/")
    user = os.getenv("LEGACY_AGENT_USER_ID", "")
    allowed = {v.strip() for v in os.getenv("LEGACY_AGENT_CAT_IDS", "").split(",")}
    if not base or not user.isdigit() or str(req.cat_id) not in allowed:
        raise ProviderError("legacy_not_configured_or_cat_not_allowed")
    async with httpx.AsyncClient(timeout=40, follow_redirects=False) as client:
        if req.mode == "chat":
            r = await client.post(base + "/chat", json={"user_id": int(user), "cat_id": req.cat_id, "user_input": req.message})
            r.raise_for_status()
            stream_id = r.json()["stream_id"]
            from urllib.parse import quote
            method, url, kwargs = "GET", base + "/chat/stream/" + quote(stream_id, safe=""), {}
        else:
            method, url, kwargs = "POST", base + "/analyze/" + user, {"json": {"cat_id": req.cat_id, "analysis_type": req.analysis_type, "time_range": req.time_range}}
        async with client.stream(method, url, **kwargs) as response:
            response.raise_for_status()
            data, event = [], "message"
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data.append(line[5:].strip())
                elif not line and data:
                    payload = json.loads("\n".join(data))
                    yield {"type": "legacy", "event": event, "data": payload}
                    data, event = [], "message"
