# MapifyAI integration notes

Reference: [qing-dai/MapifyAI](https://github.com/qing-dai/MapifyAI), inspected at commit `4f3923868e5a4cc30362e72590faa025c0064d2d`.

Pawse implements an independent HTTP adapter. No MapifyAI source, frontend, seeded datasets, scraped reviews or credentials were copied. The upstream README states MIT; no standalone license file was reported by GitHub during review. Confirm applicable notices before any later source import.

## Actual API differences found

| Upstream documentation / assumption | Observed code | Pawse decision |
| --- | --- | --- |
| `stream` shown inside the JSON body | Controller accepts it as a query parameter | Send `?stream=false` to `POST /api/requests/` |
| GET request state described as returning results | Controller returns `request` and `offers` | Consume the initial POST response; no polling dependency |
| Separate GET search SSE suggested | Not implemented in inspected controller | Use Pawse's own POST SSE |
| Unknown opening hours | Place controller can default to open | Mapify-derived opening state stays unknown |
| Nearby service search | Generic provider categories and optional seed fallback | Retain only recognizable veterinary listings; never claim exhaustive live results |

## Configuration

Set `MAPIFY_BASE_URL` to the root of a backend you are authorized to use, without `/api`. A Vercel frontend URL is not the backend URL. Optional `MAPIFY_API_TOKEN` becomes an Authorization bearer header. Upstream deployment credentials and its dependencies must be configured by its operator.

Pawse submits only coordinates, radius expressed in a veterinary-only query, and language. It does not transmit the user's health concern, photo or insurance details. It retrieves up to ten place details concurrently and extracts provider phones and website links. The veterinary filter is conservative and may omit valid clinics with ambiguous names/categories.

Only actual provided phones become call actions, and only if they parse as international numbers. Local-only phone formats remain visible as data but do not create a dial link. Never infer a phone number from an LLM response.

## Alternative source

`GOOGLE_PLACES_API_KEY` enables the official Nearby Search API with type `veterinary_care`. This source takes precedence when both are configured. It returns up to 20 nearby places, including phone and current opening state when available. It requires Maps Platform API enablement, restrictions and billing; a Gemini key alone is not proof of Places access. There is no silent fallback between paid providers.

No live clinic lookup was verified in this workspace because neither a Mapify backend URL nor a Places key was supplied. Both adapters have contract tests against synthetic HTTP responses.

Sources: [Nearby Search](https://developers.google.com/maps/documentation/places/web-service/nearby-search), [upstream controller contract](https://github.com/qing-dai/MapifyAI/blob/main/doc/controller-frontend-contract.md), [upstream requests controller](https://github.com/qing-dai/MapifyAI/blob/main/backend/app/api/requests.py).
