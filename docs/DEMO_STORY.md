# Mimi in Zurich: the 120-second care journey

## Product promise

Describe a concern in your own language. Pawse brings the cat's situation, nearby veterinary care, policy evidence and a conversation in the local language into one app. The owner can speak **Mandarin Chinese, English, German or Hindi**; the Zurich demo prepares **German** speech with subtitles in the owner's selected language. The headline story uses English subtitles.

This is the target product journey and the script for a **simulated rehearsal**. The running rehearsal is `GET /api/v1/demo/mimi`; its calls, replies, calendar slots, estimates and coverage decisions are simulated. It makes no bookings. The 120 seconds describe edited presentation time, not a guarantee that live providers will finish in two minutes. The roughly one-minute product goal concerns organizing the first useful next steps.

[Multimodal architecture](MULTIMODAL_ARCHITECTURE.md) · [Voice requirements](VOICE_CONCIERGE.md) · [Frontend contract and palette](controller-frontend-contract.md#8-journey-layout-and-visual-requirements) · [Detailed production script](../research/pet-insurance/demo-video-script.md).

## Before the story

- The owner has entered their insurer name and contact; Pawse does not guess the insurer from location.
- The rehearsal uses the [demo policy schedule](../research/pet-insurance/policy/policy.json) and [adapted terms](../research/pet-insurance/avb/avb-en.md). A live case needs the owner's actual documents and insurer confirmation.
- For own-voice audio, enroll the owner before the timed demo: record their own voice, obtain cloning/provider consent, create a German voice or localization, preview it and save it. Gradium credentials and a successful preview are prerequisites, not consequences of starting the story.
- The scenario assumes no additional reported emergency warning signs. In a real case, urgent guidance must not wait for insurance research, a price comparison or voice setup.

## The story (120 s)

| Time | Beat | Screen and interaction |
| --- | --- | --- |
| **0:00–0:17** | Video of Mimi limping, captioned **“Zurich. You don't speak German.”** The owner films her in the app and says, **“My cat is limping, please help me.”** | Camera/attachment preview, microphone and selected input language. Show the recognized words for correction. Video is part of the target story; current live intake accepts photos and recorded audio. |
| **0:17–0:30** | Pawse asks one follow-up: **“Did she fall or jump?”** The owner says, **“She jumped off the wardrobe.”** The story treats this as a possible accident and shows **🟡 See a vet today**. Pawse offers to call the nearest open practice. | Care summary, one follow-up and nearby-clinic cards with source, opening status and contact. A real result must not infer confirmed opening hours, travel time or a diagnosis from the story. |
| **0:30–0:58** | **Vet call in German with English subtitles.** The practice offers **16:30** or a home visit tonight. Pawse checks the calendar, finds the owner free from **16:00**, and the owner accepts 16:30 as the preferred option. Treatment is estimated at **CHF 600**, plus **CHF 150** for a home visit. Pawse asks whether to check the pet insurance. | German/subtitle pairs, two appointment options and the estimate. The owner reviews the option before a binding confirmation. Calendar availability and the practice reply are simulated; in live use they require separate connectors and actual responses. |
| **0:58–1:30** | **Insurer call.** In this demo, accidents are covered from day one. The owner pays the first **CHF 300**, then **80% of the remaining eligible treatment cost** is reimbursed. The home-visit surcharge is excluded on this plan: it requires a **CHF 12'000** annual sum insured (adapted AVB **1.2.5**). Physiotherapy is also excluded because the complementary module was not selected (adapted AVB **1.2.6**). Show **A: clinic, about CHF 385 including taxi** and **B: home visit, CHF 510**. The owner chooses the clinic. | Cited evidence panel, deductible/exclusion chips, two cost cards and an explicit choice. The insurer reply is simulated; retrieved text by itself cannot approve a real claim. |
| **1:30–1:42** | **Vet confirmation call.** Pawse requests the **16:30** clinic appointment and passes on the owner's instructions: **itemised invoice; no physiotherapy without asking first**. | Reviewed confirmation script, selected recipient and owner approval. A real appointment becomes confirmed only after the practice confirms it. |
| **1:42–2:00** | **Taxi call:** “Is a cat in a carrier OK?” **“Ja, kein Problem.”** Pickup is **16:05**. The closing sheet shows the case summary and claim checklist: **keep the video, keep the itemised invoice, submit within 30 days**. | Pet-carrier acceptance, pickup time and fare review, then the final handoff. The taxi segment can occupy 1:42–1:54 and the summary 1:54–2:00. The 30-day deadline belongs to this demo policy; a live checklist must use the applicable policy. |

The jump is an owner-reported fact for the vet and insurer to assess. Before any actual insurer response, use wording such as **“You have pet insurance. Shall I check whether this is covered?”** The app must not present a draft assumption as confirmed coverage or say an appointment, taxi or video was saved unless that action succeeded.

## Cost cards and evidence

These numbers match `pawse/demo.py`. Assumptions: CHF 600 eligible treatment, CHF 300 deductible entirely unused, sufficient annual limit, CHF 25 owner-paid taxi, and CHF 150 excluded home-visit surcharge.

```text
Eligible amount after deductible = CHF 600 − CHF 300 = CHF 300
Insurance reimbursement          = CHF 300 × 80%    = CHF 240
Owner treatment share            = CHF 600 − CHF 240 = CHF 360
Clinic + taxi                    = CHF 360 + CHF 25  = CHF 385
Home visit                       = CHF 360 + CHF 150 = CHF 510
```

| Demo fact | Evidence / condition |
| --- | --- |
| Accident treatment and waiting-period exception | Adapted AVB 1.2.1, 1.4(d), 3.2(a); synthetic schedule active for the scenario |
| Deductible and reimbursement | Demo schedule `cost_sharing`: CHF 300, then 80%; unused deductible assumed |
| Home-visit surcharge excluded | Adapted AVB 1.2.5; demo base plan is CHF 5'000, below CHF 12'000 |
| Physiotherapy excluded | Adapted AVB 1.2.6; complementary medicine not selected |
| Taxi paid by the owner | Explicit demo estimate assumption; confirm transport benefits independently for a real policy |
| Invoice submission within 30 days | Adapted AVB 2.2 and demo `claims_process.submit_within_days` |

The adapted clause identifiers are the repository's citation labels. The [research source list](../research/pet-insurance/README.md#sources) links the original terms; the home-visit and complementary-medicine provisions appear under section 1.2 headings there. The policyholder and schedule are synthetic. No insurer has approved a real claim.

## Agent handoffs for this story

| Responsibility | Contribution | Current boundary |
| --- | --- | --- |
| Voice Agent | Owner dialogue/transcription; selected language; requests tools | Recorded-audio route exists. Gemini Live token/tool backend exists; browser streaming remains to do. |
| Vision + Care Guidance | Photo observations, reported jump, care summary and vet questions | Photo assessment exists; video intake and a separate Vision handoff are planned. |
| Document + Policy Evidence | Extract policy/invoice facts; retrieve clauses with page/source references | Demo lexical retrieval exists. Private-document upload, scoped indexing and grounded synthesis are planned. |
| Vet Discovery + Ranking | Find suitable nearby practices and retain unknown opening/service data | Provider adapters exist; configured live discovery must be checked. |
| Orchestrator | Coordinate results, keep unknowns, validate estimates and pause for decisions | Bounded care run and Live tools exist; full shared case/document integration remains planned. |
| Communication + Gradium Speech | German script, paired subtitles, owner-consented German voice audio | Scripts and voice adapters exist. Live Gradium output still needs a key, sample and verification. |
| Action gateway | Dial/connect, handle replies, confirm appointment, calendar and taxi | Opening a clinic dialer link is distinct from an agent call. Network calling, call audio injection, calendar and booking connectors are not implemented. |

## Acceptance checklist

These are delivery requirements, not a record that all checks have passed. Record actual results in [Validation](VALIDATION.md).

- [ ] Rehearse the same intent with Mandarin Chinese, English, German and Hindi input. Preserve the original transcript, names, times, prices and uncertainty; allow correction.
- [ ] Generate German scripts with separately selected `en` / `zh` / `de` / `hi` subtitles. An input-language change must not silently change the recipient language or selected voice.
- [ ] Enroll only the owner's consented voice, preview German pronunciation, then play/download audio with a clear AI-assistant disclosure. Never silently substitute a stock voice.
- [ ] Keep “Draft”, “Audio ready”, “Simulated call” and a future provider-confirmed call visibly distinct. Playback alone cannot mark a call connected or a booking confirmed.
- [ ] Show both CHF 385 and CHF 510 demo options with their assumptions. Keep live coverage unconfirmed without evidence from the actual insurer.
- [ ] Preserve the owner gates: initial contact, preferred appointment, insurer sharing, clinic/home choice, final booking and taxi approval. For future calls, material changes to recipient, scope or cost require renewed approval.
- [ ] Complete the story with missing location, no policy, a denied microphone or missing Gradium key using honest partial results and text/script fallbacks.
- [ ] Keep the final summary/checklist usable on mobile and desktop; show pink/gray styling, readable subtitles and explicit status text alongside urgency colors.

The frontend, orchestration, voice and evidence modules divide this work using the [existing branch assignments](MULTIMODAL_ARCHITECTURE.md#module-handoffs-and-build-order).
