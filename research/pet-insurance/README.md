# Pet insurance research: mock policy, terms and demo scenarios

Research input for the Pawse **pet emergency action assistant**. Nothing here is wired into the app yet; it is kept
separate from `backend/` on purpose. Everything is **fictional and synthetic**: the policy, the insurer name and the invoices.
The terms are adapted from a real Swiss product so the coverage logic is realistic.

| File | What it is |
| --- | --- |
| [`policy/policy.json`](policy/policy.json) | Policy schedule for the demo owner (`user_id` 1) and the three cats from `backend/utils/mock_data.py`: chosen coverages, limits, deductible, waiting period, declared lifestyle |
| [`avb/avb-en.md`](avb/avb-en.md) | General terms (AVB), English adaptation of the Calingo AVB, December 2025 edition, with clause numbers kept for citations |
| [`scenarios/scenarios.yaml`](scenarios/scenarios.yaml) | 8 emergency scenarios following the demo flow, plus 5 routine follow-up questions, each with expected triage, coverage verdict, AVB clauses and payout |
| [`check_scenarios.py`](check_scenarios.py) | Recomputes every expected payout from the invoice lines and the policy (`python research/pet-insurance/check_scenarios.py`) |
| [`demo-video-script.md`](demo-video-script.md) | 2-minute demo video script: limping cat, German calls to vet, insurer and taxi, limited coverage (home visit not covered) |

## Demo flow

In the panicked first minutes the assistant answers three questions: *How urgent is it? Where do I go and what do I say?
How do I spend as little as possible?*

1. **Input:** photo, video or voice.
2. **Two or three follow-up questions.**
3. **Triage:** 🔴 go to a vet now · 🟡 see a vet within 24h · 🟢 monitor at home.
4. **Next steps:** copy-ready case summary, nearby emergency clinic search, insurance claim checklist.

### Insurance comes in early, not only at step 4

The coverage answer changes what the owner should do *before* leaving the house, so the scenarios use it in steps 2 and 3:

- **Follow-up questions do double duty.** "Could she have swallowed something?" is a triage question *and* decides
  accident vs. illness. Accidents are covered from day one; illness only after the 30-day waiting period (S02).
  "Did something happen just now, or has the limp come and gone?" separates a new injury from a pre-existing condition (S04).
- **Evidence is captured at input.** The photo or video from step 1 becomes claim evidence (string in vomit, bite wounds).
- **Third parties.** A dog bite is paid by the dog owner's liability insurer if known, so get their details on the spot
  and report it to the police (S06).
- **Logistics.** A house call is not covered on this plan, so drive to the clinic (S08). Ask the vet to itemise covered and
  uncovered lines separately (S04) and to confirm the treatment could not wait (out-of-hours surcharge).
- **Expected cost up front.** Remaining deductible and limit per cat are known, so the agent can say "you'll get about
  80% back" before the bill arrives.
- **Policy vs. app data.** Xiaohua is declared indoor-only, but her collar logs show outdoor time. The owner must notify
  the insurer (S06).

### Hero demos

| Scenario | Triage | Coverage | Why it demos well |
| --- | --- | --- | --- |
| S02 vomiting on demo day | 🟡 or 🔴 | ❌ illness in waiting period, ✅ if swallowed object | One question flips both urgency and coverage; date-dependent on the hackathon day |
| S01 balcony fall | 🔴 | ✅ 1'680 of 2'400 | Accident covered on day 18; real deductible + 80% maths |
| S06 dog bite | 🟡 | ❓ depends on the dog owner | Insurance changes the first five minutes; collar-data cross-check |
| S08 can't pee at 2am | 🔴 | ✅ mostly, ❌ house call | Coverage changes logistics in a real emergency |

Mixed answers are the point: S03 (physio not in plan after a covered surgery), S04 (accident covered but under the
deductible, arthritis pre-existing), S07 (four invoice lines, three different reasons).

## The policy in one paragraph

Policy `PAWSE-DEMO-2026-000001`, start **2026-09-15**, illness covered from **2026-10-15** (30-day waiting period).
Per cat: CHF 5'000 annual limit, CHF 300 annual deductible, 80% reimbursement. Included: prevention (CHF 200, after the
deductible), emergency pet boarding (CHF 40 per cat per day), prescription diet (CHF 300). **Not selected:** complementary
medicine (physio, acupuncture), advanced treatments, behavioural medicine, pre-existing conditions add-on.
Dahuang has pre-existing mild arthritis; Xiaohua is declared indoor-only; Dahuang missed his annual check-up.

## Relation to the backend

The cats and owner match `MockDataFactory.cat_data()` / `user_data()` in `backend/utils/mock_data.py`
(咪咪 Mimi, 小花 Xiaohua, 大黄 Dahuang). A future `check_coverage` tool could load `policy.json` and the AVB,
and be evaluated against `scenarios.yaml` (expected verdict, clauses and payout per scenario).

## Sources

The real AVB PDFs were fetched for this research and are **not committed** (third-party copyrighted documents);
only our English adaptation is. Originals:

| Document | URL | SHA-256 |
| --- | --- | --- |
| Calingo AVB "Unfall- & Krankenversicherung für Hunde und Katzen", Dec 2025 (basis of `avb-en.md`) | https://dam.swica.ch/image/upload/v1766064934/d_Spezialversicherung_Haustierverischerung_Calingo_ZB_rere34.pdf | `b02861f1…bd328` |
| Same product, Feb 2024 edition | https://egk.ch/egk/downloads/haustierversicherung/avb-calingo-unfall--krankenversicherung-fuer-hunde-und-katzen-ausgabe-02.2024-d.pdf | `2f38c25b…c6272` |
| Allianz Suisse pet insurance AVB (risk carrier of Calingo; for comparison) | https://www.allianz.ch/content/dam/onemarketing/azch/common/allianz/de/AVB_Allianz_Haustierversicherung_D.pdf | `f58470dc…878b3` |

Calingo Insurance AG is a tied intermediary; the risk carrier is Allianz Suisse Versicherungs-Gesellschaft AG.
"Pawse Demo Pet Insurance" is fictional and not affiliated with either. Triage levels in the scenarios were written
by non-vets for demo purposes and are not veterinary advice.
