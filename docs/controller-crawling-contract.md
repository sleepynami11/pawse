# Pawse Crawling and Data Handoff Contract

Your module collects attributable public facts. It supplies the Vet Discovery Agent and the evidence/RAG module; frontend rendering, LLM recommendations, voice generation and telephone execution belong to their respective modules.

**Implemented here:** an offline Zurich OpenStreetMap collector and a staging dataset. **Not implemented:** crawling arbitrary clinic websites, private policy ingestion, scheduled refresh, a crawler HTTP endpoint or OSM discovery inside the live care route.

## 1. What to collect first

| Priority | Source | Collect | Consumer |
| --- | --- | --- | --- |
| P0 | OSM veterinary POIs via Overpass | Name, coordinates, address, published phone/website, raw opening-hours and emergency tags | Vet Discovery and deterministic ranking |
| P1 | A small allowlist of official clinic websites | Contact/emergency numbers, published hours, explicit services, appointment link, original excerpts and source timestamps | Clinic verification and cited service evidence |
| P2 | Official insurer product/terms pages selected for a user question | Public contact information, document edition/date and relevant clauses, subject to reuse terms | Document/Policy Evidence module |

Do not crawl owners' policies, bills, medical records or personal calendars. Those enter through the future consented [Document controller](controller-document-contract.md). Insurer information initially comes from the owner. A public product page cannot prove the owner's plan, deductible remaining or coverage.

Use structured API/open-data collection before HTML crawling. OSM's `amenity=veterinary` identifies veterinary places and may include address, website, opening hours and emergency tags. It is an incomplete community directory, not a list of every practice or live appointment availability. [OSM tag definition](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dveterinary).

## 2. Run the first collector

From the repository root:

```bash
.venv/bin/python scripts/crawl_zurich_vets.py
# A smaller area and explicit output location:
.venv/bin/python scripts/crawl_zurich_vets.py --radius-km 5 --output tmp/crawling/zurich-5km.json
# Only when a new source snapshot is needed:
.venv/bin/python scripts/crawl_zurich_vets.py --refresh
```

No provider keys, Gemini calls or browser automation are required. Default: a 10 km query around **Zurich city centre**, not the owner's current location. The radius is an integer from 1 to 20 km. The collector contacts only `https://overpass-api.de/api/interpreter`; it does not follow returned website links or accept a remote URL argument.

Default output: `tmp/crawling/zurich-vets.json`, outside version control. An existing snapshot is protected unless `--refresh` is supplied. Failure leaves the previous output untouched. One invocation makes one bounded query, with a 15-second query budget, 30-second client deadline and 2 MB response limit. An Overpass error remark rejects the whole response instead of accepting a partial dataset. No automatic retry or endpoint rotation is performed.

Public Overpass capacity is shared; reuse the saved snapshot and normally refresh no more than daily for this demo. A rate limit/timeout means retry later, not launch parallel requests. These are Pawse's conservative collection settings, not a guaranteed operator SLA. [Overpass usage guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html).

## 3. Actual dataset contract

Top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | `pawse-crawled-clinic-v1` |
| `manifest` | Endpoint, exact query, centre/radius, retrieval timestamp, original response SHA-256, counts, licence/attribution, coverage statement and refresh policy |
| `clinics` | Normalized `CrawledClinic[]`, sorted by straight-line distance then source ID |
| `source_elements` | Original parsed OSM elements; audit the canonical record hash and original tags here |

`CrawledClinic` extends the shape of the current `Clinic` for an **offline handoff**. It does not change the API's `Clinic` model.

| Field | Normalization rule |
| --- | --- |
| `id` | `osm:node:<id>`, `osm:way:<id>` or `osm:relation:<id>`; duplicate source IDs removed |
| `name` | Required, verbatim trimmed source name; unnamed entries rejected |
| `location` | Node coordinates or way/relation centre; invalid/missing coordinates rejected |
| `address` | Join available `addr:*` components; do not infer missing house number/postcode |
| `phone`, `call_url` | Prefer `contact:phone`, then `phone`; normalize international notation or a Swiss ten-digit national number; ambiguous/multiple numbers become null |
| `website` | HTTP(S) source link only; not fetched or treated as verified ownership |
| `opening_hours_raw` | Original OSM string; no parsing into live opening state |
| `open_now`, `rating` | Always null in this collector |
| `emergency_raw` | Original tag if present; retained separately from the live `emergency_service: unknown` |
| `services` | Empty until explicit service evidence is reviewed; no invented cat specialty, surgery or home visit |
| `distance_km` | Rounded straight-line distance from the collection centre, not an owner-specific ETA |
| `source`, `source_url` | `openstreetmap` and the OSM element permalink |
| `retrieved_at` | Collection time, not proof of when the clinic information was last verified |
| `record_sha256` | SHA-256 of canonical JSON of the source element (`sort_keys=True`, `ensure_ascii=False`) |
| `field_tags` | Mapping of normalized fields to source tag names or coordinate/centre fields |
| `verification` | `community_listing_unverified` |
| `license` | `ODbL-1.0`; retain dataset attribution |

Different OSM objects may describe the same physical practice. This version deduplicates source IDs only; compare name, phone, address and proximity in a review queue before merging physical entities. Keep both source references and conflicting values until reviewed.

Veterinary POIs can include livestock facilities or departments on a hospital campus. **Cat acceptance remains unverified.** Review official small-animal/cat service evidence before promoting a candidate for a cat-care recommendation; the current collector does not claim every returned institution treats cats.

Preserve **© OpenStreetMap contributors** attribution and applicable ODbL terms when handing on or distributing the dataset. Pawse's MIT licence covers its code, not the OSM database. [OSM copyright and licence](https://www.openstreetmap.org/copyright).

## 4. Official website enrichment: next slice

Start with five selected clinics and at most two relevant pages per clinic: contact/opening hours and services/emergency information. This is a proposed follow-up collector, not included in the current script.

1. Review each official domain, applicable terms and `robots.txt`. A discovered website link is a candidate, not permission to crawl everything.
2. Maintain an explicit domain/path allowlist. Fetch public HTTP(S) pages only; reject credentials, local/private network destinations and off-allowlist redirects. Do not submit forms, log in or bypass access controls.
3. Use one request at a time, at least one second apart, a clear user agent, a 15-second timeout and a 1 MB HTML bound. Respect slower source limits. On 403/429, stop that source and preserve the existing evidence.
4. Extract visible facts from reviewed sections or structured data; exclude navigation and unrelated boilerplate. Keep original German text and any English summary separately.
5. Record each fact as an evidence item; missing or contradictory facts stay unknown/conflicted. A contact number may be an emergency line rather than reception, so retain its label/purpose.
6. Review records before promoting them into the clinic index. `24/7 emergency contact` must not become `all services available 24/7`. Do not infer open status from incomplete hours, holidays or a clinic name.

Proposed `ClinicWebEvidence` fields: `evidence_id`, `clinic_id`, `field`, `value`, `source_url`, `page_title`, `language`, `original_excerpt`, `section`, `retrieved_at`, `content_sha256`, `review_state`, `reuse_basis`. Review states: `unreviewed`, `accepted`, `rejected`, `conflicted`. Store allowed excerpts/metadata according to the source's terms; do not automatically commit entire third-party pages or PDFs.

Gemini extraction can be an optional helper after permitted HTML collection. It must return source-backed candidate fields; it cannot manufacture missing prices, insurance acceptance, operating hours or appointments. The crawler works without an LLM.

## 5. Exactly what to hand to teammates

| Recipient | Deliverable | They own |
| --- | --- | --- |
| LLM/orchestration | Normalized clinic snapshot, provenance, unknown/conflicted fields and freshness metadata | Recommendation/ranking, user-specific distance and care summary |
| RAG/evidence | Reviewed webpage evidence with original excerpt, source/hash/date and clinic ID | Retrieval, citations and grounded answers |
| Voice/phone | Selected published contact plus purpose/source/verification status | Owner confirmation, calls, transcription and provider receipts |
| Frontend | Backend-owned agreed schema via orchestration; no direct raw-page scraping | Cards, map and displayed attribution |

**Current integration gap:** live `Clinic.source` permits only `google_places` and `mapify`. Never relabel OSM records as either provider. The next integration PR must explicitly add an OSM source/adapter, preserve attribution, agree source selection in `discover`, regenerate OpenAPI and update consumers. Recompute distance for the consented user location; do not reuse distance from the crawl centre as if it were user distance. The current UI does not consume this snapshot yet.

Public clinic evidence stays separate from `synthetic_demo` insurance knowledge and owner-private documents. Do not put clinic data into `/knowledge/search`'s fixed policy corpus.

## 6. Completion checklist for your module

- Run the collector and report actual row count, rejected rows, duplicate IDs and missing phone/website/hours counts; do not promise full Zurich coverage.
- Manually inspect at least five records against their source; review official contact purpose before a real call.
- Supply one sample record, manifest and source evidence to the orchestrator/RAG teammate.
- Run `.venv/bin/python -m pytest -q tests/test_crawling.py`; tests use synthetic fixtures and a mocked network.
- Keep personal policies, keys and recordings out of the crawler and Git.
- Mark official-site enrichment and live adapter integration incomplete until they actually exist.

Primary source definitions and licences above were checked on 10 October 2026 (high confidence for source format/licence; individual clinic facts remain unverified until reviewed). See [Data sources](DATA_SOURCES.md) and [Knowledge/Data controller](controller-knowledge-contract.md) for the broader module boundary.

## 7. Initial collection result

The initial live query on 10 October 2026 returned 29 OSM elements and retained 27 named, located candidates after validation/radius filtering. There were no repeated source IDs. Of those candidates, 12 had no usable phone, 10 had no website and 13 had no hours string. These counts are a snapshot, not a completeness estimate.

That first local file was produced before raw-element retention was added and is kept as `tmp/crawling/zurich-vets-initial.json`, an exploratory snapshot rather than the complete section 3 handoff. A follow-up refresh of the final collector failed because Overpass was unavailable or rate-limited; no old data was overwritten. Full final-schema behavior is covered by mocked tests, but a successful live refresh with `source_elements` still needs to be recorded. No official clinic websites or insurer documents were crawled in this slice.
