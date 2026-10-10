# Gemini integration plan

This is a migration guide for the imported backend, not an implemented integration.

## Get the hackathon key

Use the temporary Google account assigned by the organizers, import its project in [AI Studio](https://aistudio.google.com/api-keys) if necessary, then create or retrieve a Gemini API key. Check the project's actual quota and available models. Follow the [account guide](https://goo.gle/hackathon-account) for event-specific access.

Keep the key on the server. Temporary accounts may be deleted soon after the event, so save source and assets and switch to your own project for continued use.

## Existing integration points

| Source | Current behavior | Migration work |
| --- | --- | --- |
| `backend/utils/call_llm_async.py` | OpenAI text/streaming; OpenRouter analysis and vision | Configure Gemini credentials, endpoint, model, and compatible request parameters in each path |
| `backend/utils/call_llm.py` | Standalone OpenAI helper | Migrate if retained or used |
| `backend/utils/embedding.py` | OpenAI embeddings and text translation | Decide separately whether to retain or replace; rebuild indexes if the embedding model or dimensions change |
| `backend/api.py` | Chat and analysis routes | Add a distinct Live session/token path and validated tool dispatch |

Setting `GEMINI_API_KEY` alone changes none of these existing clients. It must not be sent to OpenAI or OpenRouter endpoints.

## Minimal text migration example

Google supports an [OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai). Since the backend already uses `AsyncOpenAI`, this is a small first step:

```python
import os
from openai import AsyncOpenAI

async def gemini_reply(message: str) -> str:
    client = AsyncOpenAI(
        api_key=os.environ["GEMINI_API_KEY"],
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    async with client:
        result = await client.chat.completions.create(
            model=os.environ["GEMINI_MODEL"],
            messages=[{"role": "user", "content": message}],
        )
    return result.choices[0].message.content or ""
```

Choose a model accessible to the assigned project. This isolated example is not wired into the source. Validate streaming, vision inputs, structured outputs, and error handling individually before switching existing flows.

## Voice migration

Use [Gemini Live API](https://ai.google.dev/gemini-api/docs/live-api) for real-time voice. A normal chat-completions endpoint does not implement a Live session.

1. Add microphone capture, audio playback, and interruption handling to a frontend.
2. Have a backend endpoint issue constrained [ephemeral tokens](https://ai.google.dev/gemini-api/docs/live-api/ephemeral-tokens).
3. Connect the browser to Live and declare a small set of supported tools.
4. Validate and execute tool calls in the application, then return the real results.
5. Show transcripts and failures honestly; do not announce success without a successful tool response.

Start with one read-only tool. The existing cat-status flow is a candidate if its dependencies can be replaced with explicitly labelled synthetic demo data. The earlier public-page summary example is a separate product idea; the imported backend does not implement a general browsing agent.

## Validation still needed

- Verify the assigned key and model with a small text request.
- Test non-streaming and streaming responses.
- Confirm the demo has no unexpected calls to legacy providers.
- Exercise one actual tool round trip.
- Verify Live audio and interruption behavior in the browser.
- Document which work was pre-existing and which was built during the event.
