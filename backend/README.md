# Existing CatAgent backend

This folder contains a selected source import of the team's pre-existing cat-care and IoT backend. It is a starting point for Pawse, not a completed hackathon voice application.

## What is in the code

- FastAPI routes for health checks, WebSocket chat, SSE chat, analysis, and push connections.
- PocketFlow routing and workflow nodes.
- Context management and synthetic mock-data helpers.
- Clients for Cloudflare D1, R2, Vectorize, Chroma, and an external device service.
- OpenAI text/embedding calls and OpenRouter analysis/vision calls.

Gemini and Gemini Live are not connected. Existing code comments, multilingual prompts, and historical branding are preserved to avoid changing behavior during import. Public project documentation is English.

## Local setup outline

Use Python 3.10 or newer. The following is an intended setup path, not an end-to-end verified installation:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Configure the services required by the route you intend to test.
python main.py
```

`main.py` loads `.env`; the example binds to localhost. Dependency versions are not locked. Python syntax was checked during import, but dependency installation, API startup, and live task execution were not tested.

`TEST_MODE=true` enables some mock storage paths. It does not guarantee offline execution or prevent LLM calls. Do not use real user data for the initial demo.

## Missing dependencies and limitations

- The external device service, production databases, bucket contents, and credentials are not included.
- The original `.skills`, `.memory`, RAG collections, and `config/core_rules` content are excluded pending data and provenance review. Relevant context/retrieval paths are incomplete.
- Existing tests and generated test reports were not imported; their fixture and network assumptions need a separate review.
- CORS is broad and route-level authentication is not established by this import. Treat this as local development source, not a public deployment.
- Cat-health outputs have not been clinically validated.

See [import review](../docs/IMPORT_REVIEW.md), [Gemini migration](../docs/GEMINI_INTEGRATION.md), and [third-party notices](../THIRD_PARTY_NOTICES.md).
