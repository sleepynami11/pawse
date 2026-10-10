"""Deadline-bounded coordination with useful results even when providers fail."""
import asyncio
import time
import httpx
from .models import phone_uri
from .providers import assess, discover, fallback_assessment, maps_link, ProviderError, rank_clinics

COMPLETENESS = "Provider-limited nearby results; not an exhaustive directory. No appointment, call, or insurance approval has been made."


CARE_DEADLINE_SECONDS = 40


async def care_events(req):
    started = time.monotonic()
    assessment = fallback_assessment(req)
    clinics, warnings = [], []
    statuses = {"assessment": "pending", "clinics": "pending"}
    yield {"type": "safety", "assessment": assessment.model_dump()}
    insurance = None
    if req.insurance:
        insurance = {"company": req.insurance.company, "phone": req.insurance.phone, "plan": req.insurance.plan,
                     "call_url": phone_uri(req.insurance.phone), "source": "user_provided", "coverage": "unconfirmed",
                     "questions": ["Is this policy active for my cat?", "Is emergency treatment covered and is pre-authorization required?", "Which invoices and records do you need?"],
                     "note": "Use the number on your policy. Do not delay urgent veterinary care while checking insurance."}
    yield {"type": "insurance", "insurance": insurance}
    async with httpx.AsyncClient(follow_redirects=False) as client:
        async def job(name, operation):
            try:
                return name, await operation, None
            except ProviderError as exc:
                return name, None, str(exc)
            except Exception:
                return name, None, "provider_unavailable"
        tasks = {asyncio.create_task(job("assessment", assess(req, client))), asyncio.create_task(job("clinics", discover(req, client)))}
        try:
            for stage in statuses:
                yield {"type": "progress", "agent": stage, "status": "starting"}
            pending = tasks.copy()
            while pending:
                remaining = CARE_DEADLINE_SECONDS - (time.monotonic() - started)
                if remaining <= 0:
                    warnings.append("deadline_reached")
                    break
                done, pending = await asyncio.wait(pending, timeout=min(remaining, 5), return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    yield {"type": "heartbeat"}
                for task in done:
                    name, value, error = task.result()
                    statuses[name] = "unavailable" if error else "complete"
                    if error:
                        warnings.append(error)
                    elif name == "assessment":
                        assessment = value
                        yield {"type": "assessment", "assessment": assessment.model_dump()}
                    else:
                        clinics = rank_clinics(value)
                        yield {"type": "clinics", "clinics": [c.model_dump() for c in clinics]}
                    yield {"type": "progress", "agent": name, "status": statuses[name]}
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    for name, value in statuses.items():
        if value == "pending":
            statuses[name] = "timeout"
    handoff = f"Cat: {req.cat_name}\nOwner's concern: {req.query or 'Photo / warning signs supplied'}\nReported warning signs: {', '.join(req.red_flags) or 'Not specified'}\nAI/care-navigation summary (not a diagnosis): {assessment.summary}"
    yield {"type": "result", "status": "complete" if all(s == "complete" for s in statuses.values()) else "partial",
           "assessment": assessment.model_dump(), "clinics": [c.model_dump() for c in clinics],
           "insurance": insurance, "handoff": handoff, "warnings": warnings, "providers": statuses,
           "elapsed_ms": round((time.monotonic() - started) * 1000), "target_seconds": 60,
           "search_url": maps_link("emergency veterinarian", req.location),
           "completeness": COMPLETENESS}


async def find_clinics(req):
    """Clinic lookup without the triage run, so it never waits on a care request still in flight."""
    started = time.monotonic()
    clinics, warnings = [], []
    try:
        async with asyncio.timeout(CARE_DEADLINE_SECONDS), httpx.AsyncClient(follow_redirects=False) as client:
            clinics = rank_clinics(await discover(req, client))
    except ProviderError as exc:
        warnings.append(str(exc))
    except TimeoutError:
        warnings.append("deadline_reached")
    except Exception:
        warnings.append("provider_unavailable")
    return {"status": "complete" if clinics else "unavailable", "clinics": [c.model_dump() for c in clinics], "warnings": warnings,
            "elapsed_ms": round((time.monotonic() - started) * 1000), "search_url": maps_link("emergency veterinarian", req.location),
            "completeness": COMPLETENESS}
