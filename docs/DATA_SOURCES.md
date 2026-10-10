# Data sources and ownership

Reviewed on 2026-10-10. The implemented knowledge endpoint indexes only the local synthetic policy and adapted demo AVB. The geographic sources below are integration candidates or existing provider adapters; they are not silently added to that insurance corpus.

## Repository inventory

| Source | Current status | Owner and use |
| --- | --- | --- |
| `research/pet-insurance/policy/policy.json` | Fictional demo schedule; selected sections indexed | Retrieval module: deductible, selected coverages, claims requirements |
| `research/pet-insurance/avb/avb-en.md` | Shortened English adaptation; indexed by heading | Retrieval module: cite the demo clause and retain the synthetic label |
| `research/pet-insurance/scenarios/scenarios.yaml` | Synthetic expected answers and payouts | Use as evaluation material, not independent evidence or real medical validation |
| `backend/utils/embedding.py` | Imported OpenAI embedding/translation implementation | Reference only; depends on separate credentials |
| `backend/utils/chromadb_client.py` and `backend/nodes.py` | Imported Chroma client and four-layer retrieval node | Collections and source books were not imported; the legacy RAG path is incomplete |
| `pawse/knowledge.py` | Working local lexical retrieval service | No credentials, uploads, network calls, or vector database needed |

The source research README identifies real terms that inspired the demo, including which clause sub-numbers were introduced by the project. The local adaptation is not the binding wording of any actual product, and it does not establish a real insurer's current coverage. Original third-party PDFs and unreviewed medical books remain outside this corpus.

## Zurich discovery sources

| Source | Useful fields | Terms and integration status |
| --- | --- | --- |
| [OpenStreetMap veterinary tag](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dveterinary) | Veterinary POIs, coordinates, names, optional contact and hours tags | Candidate open-data adapter. OSM documents `amenity=veterinary`, `opening_hours`, and `emergency=yes`; missing tags remain unknown. |
| [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) | Bounded geographic queries over OSM elements | Candidate read-only query mechanism, not a clinic booking service. Public instances can be overloaded; respect the selected operator's current limits, cache permitted results, and do not assume availability. |
| [opendata.swiss](https://opendata.swiss/en/terms-of-use) | Swiss public datasets and metadata | Candidate catalogue. Terms vary by dataset, including source attribution and possible commercial-use permission. No complete Zurich or Swiss veterinary directory dataset has been verified for this build. |
| [Google Places API](https://developers.google.com/maps/documentation/places/web-service/policies) | Place details, contact, ratings, reported opening information | Adapter exists in `pawse/providers.py`; needs its own configured key. This is licensed API content, not an open-data corpus. Follow storage exceptions, Google Maps attribution, and display requirements. Do not bulk-load reviews into RAG. |
| [Grounding with Google Maps (Gemini API)](https://ai.google.dev/gemini-api/docs/maps-grounding) | Place name, address, phone, website, rating, listed hours, place ID, Maps link | Live adapter `gemini_maps_clinics` in `pawse/providers.py`, used when Places is not configured. Facts are parsed only from grounding source chunks. [Terms](https://ai.google.dev/gemini-api/terms): show results to the requesting user with Google Maps links and attribution; do not modify or intersperse them; no caching beyond the allowed display-evaluation or chat-history windows, no scraping/export and no training. Pawse therefore never writes these results into the OSM dataset. |
| [University Animal Hospital Zurich contact page](https://www.tierspital.uzh.ch/ueber-uns/kontakt-anfahrt/) | Official clinic contact and emergency service information | Primary reference for manual verification; not an asserted open-data licence. The page listed small-animal emergency contact `+41 44 635 81 12`, 24/7 emergency service, and a request to call ahead when checked. Recheck before a real call. |

OSM data is licensed under the [Open Database License](https://www.openstreetmap.org/copyright). Preserve OSM attribution and the applicable database licence when using or redistributing it. The project's MIT code licence does not replace third-party data terms.

A bounded Overpass proof-of-concept query for 10 km around central Zurich is:

```text
[out:json][timeout:15];
nwr["amenity"="veterinary"](around:10000,47.3769,8.5417);
out center tags;
```

This query is now available in the standalone `scripts/crawl_zurich_vets.py` collector, with normalized output and provenance described in the [Crawling contract](controller-crawling-contract.md). The live app reads a local snapshot (`PAWSE_CLINIC_SNAPSHOT`) as a fallback and lists it after live provider results, dropping rows that duplicate a provider listing. Source IDs retain node/way/relation identity. Do not infer phone numbers, round-the-clock service, cat-specific expertise, appointments, road ETA, or current opening from a name alone. Straight-line distance is not travel time.

## Data Module Deliverables

1. Maintain a source manifest with publisher, source URL, applicable terms, edition, retrieval time, checksum, refresh policy, and demo/real classification.
2. Return each clinic fact with provenance and its observation time. Keep optional values null when missing, and confirm appointment availability through the clinic.
3. Keep clinic discovery separate from policy retrieval. A map listing does not establish treatment capability, insurance acceptance, or cost.
4. Add real insurance documents only after a user-owned upload flow exists. Record insurer and policy edition from the user's files, isolate them per owner, and require source evidence for exclusions and reimbursement assumptions.
5. Evaluate citation correctness, unmatched queries, stale information, and conflicting terms. Use deterministic calculations for deductible, reimbursement rate, and annual limits.

The first handoff is a small, auditable evidence service. An embedding model can improve retrieval later; it cannot supply missing licences, missing clinic data, or insurer approval.
