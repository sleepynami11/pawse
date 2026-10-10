# 2-minute demo video: "Mimi is limping"

One continuous story: a hurt cat, an English speaker in Zurich, and Pawse making three German phone calls
(vet, insurer, taxi) while the user only says a few words in English. Coverage is **limited**, and Pawse's
choices around that limit drive the second half.

Grounded in the demo policy ([`policy/policy.json`](policy/policy.json)) and terms ([`avb/avb-en.md`](avb/avb-en.md));
scenario `S13-limping-home-visit-vs-clinic` in [`scenarios/scenarios.yaml`](scenarios/scenarios.yaml) holds the numbers.

## Story in one line

Mimi jumped off the wardrobe and is limping → 🟡 see a vet today → Pawse books the vet in German → the insurer
confirms the accident is covered, **but not the home-visit surcharge** → the user picks the clinic → Pawse tells the
vet about the coverage limits and books a taxi that accepts cats.

## Why this coverage limit

| Item | Covered? | Clause |
| --- | --- | --- |
| Exam + X-ray after a jump injury | ✅ Accident: covered from day one, even inside the 30-day illness waiting period. CHF 300 deductible, then 80% | AVB 1.2.1, 3.2 a, 1.5 |
| Home-visit surcharge (CHF 150) | ❌ Only on plans with an annual sum of CHF 12'000 or more; this plan has CHF 5'000 | AVB 1.2.5 |
| Physiotherapy afterwards | ❌ Complementary medicine not in the plan | AVB 1.2.6 |
| Taxi | ❌ Transport is not an insured cost | (not listed in AVB 1.2) |

Choice shown to the user (estimate CHF 600 for exam + X-ray, deductible not yet used this year):

| Option | Total | Insurance pays | You pay |
| --- | --- | --- | --- |
| 🅰 Clinic today 16:30 | CHF 600 + ~25 taxi | CHF 240 | **~CHF 385** |
| 🅱 Home visit tonight | CHF 750 | CHF 240 | **CHF 510** |

## Timeline (120 s)

Calls run in the background: show a small "📞 Calling … (German)" card with live English subtitles, with the German
audio low. Speed up hold music and pauses.

| Time | Screen | Audio / dialogue |
| --- | --- | --- |
| **0:00–0:07** | Phone video: orange cat limping on three legs across a living room. Caption: *Zurich. Your cat is hurt. You don't speak German.* | Ambient. |
| **0:07–0:17** | Pawse app, camera open. User records 5 s of Mimi walking, taps mic. | **User:** "My cat is limping, please help me." |
| **0:17–0:30** | Pawse cat avatar "thinking", then triage card: **🟡 See a vet today**. Bullets: *putting no weight on front left paw · no bleeding · keep her calm in the carrier*. One follow-up chip. | **Pawse:** "She isn't putting weight on her front left paw. Did she fall or jump?" **User:** "She jumped off the wardrobe." **Pawse:** "Then see a vet today, not an emergency room. The closest open practice is Kleintierpraxis am See, 1.2 km away. Shall I call them?" **User:** "Yes, call them." |
| **0:30–0:48** | 📞 *Calling Kleintierpraxis am See (German)*. Subtitles. Calendar sheet slides in: *free 16:00–18:00, team call 15:00*. | **Pawse (DE):** "Grüezi, ich rufe für Familie Demo an. Ihre Katze Mimi, drei Jahre, hinkt seit einer Stunde vorne links nach einem Sprung vom Schrank." **Vet (DE):** "Wir können sie heute um 16:30 in der Praxis sehen, oder heute Abend einen Hausbesuch machen." **Pawse (to user, EN):** "16:30 at the practice or a home visit tonight. You're free from 4. 16:30?" **User:** "16:30 works." |
| **0:48–0:58** | Subtitles continue; cost estimate highlighted. | **Vet (DE):** "Mit Untersuchung und Röntgen rechnen Sie mit etwa 600 Franken. Der Hausbesuch kostet 150 Franken extra." **Pawse (EN):** "That's about 600 francs, plus 150 for a home visit. You have pet insurance, and a jump injury counts as an accident, so I think it's covered. Shall I check with them?" **User:** "Yes, please." |
| **0:58–1:18** | 📞 *Calling your pet insurer (German)*. Policy card on screen: *Accident ✅ from day 1 · Deductible CHF 300 · 80%*. Two lines turn red: *Home visit ❌*, *Physio ❌*. | **Insurer (DE):** "Unfälle sind ab dem ersten Tag gedeckt, auch in der Karenzfrist. Nach der Franchise von 300 Franken übernehmen wir 80 Prozent. Der Hausbesuch ist in Ihrem Vertrag aber nicht gedeckt, das gibt es erst ab einer Versicherungssumme von 12'000 Franken. Und eine Physiotherapie danach wäre auch nicht versichert." |
| **1:18–1:30** | Option cards 🅰 / 🅱 from the table above. User taps 🅰. | **Pawse (EN):** "The visit is covered, but not the home-visit fee, and not physio later. Going to the clinic, you'd pay about 385, including a taxi. A home visit, about 510." **User:** "Let's go to the clinic." |
| **1:30–1:42** | 📞 *Calling Kleintierpraxis am See (German)*. Appointment card: ✅ *16:30*. | **Pawse (DE):** "Wir bestätigen 16:30 in der Praxis. Bitte stellen Sie die Rechnung detailliert aus. Physiotherapie ist nicht versichert, bitte vorher mit der Familie absprechen." **Vet (DE):** "Alles klar, bis später." |
| **1:42–1:54** | 📞 *Calling Taxi Zürich (German)*. Taxi card: 🐾 *pet-friendly · arrives 16:05 · ~CHF 25*. | **Pawse (DE):** "Ein Taxi für 16:05, mit einer Katze in der Transportbox. Ist das in Ordnung?" **Driver (DE):** "Ja, kein Problem, in der Box." **Pawse (EN):** "Taxi at 4:05, the driver's fine with Mimi in her carrier. The vet visit is covered by insurance after your deductible; the taxi isn't." |
| **1:54–2:00** | Summary sheet: *16:05 taxi → 16:30 vet*, **copy-ready case summary**, **claim checklist**: *keep this video · itemised invoice · submit within 30 days*. Logo. | **Pawse:** "I've saved your video and checklist for the claim." Caption: **Pawse. A little cat. A helping hand.** |

Roughly 230 spoken English words plus subtitled German, which fits 2 minutes when calls are sped up.

## Copy-ready case summary (shown at 1:54)

> Mimi, 3-year-old orange tabby cat, 5.2 kg. Since about 14:00 today: not putting weight on the front left paw after jumping
> from a wardrobe (~2 m). No bleeding, eating normally. Vaccinated (rabies, FVRCP). No known conditions. Video attached.
> Insurance: accident claim, policy PAWSE-DEMO-2026-000001.

## Production notes

- **Pre-record the calls.** The vet, insurer and taxi voices are actors or TTS reading the German lines above.
  Say so in the submission ("simulated calls"); the hackathon checklist asks to separate working features from future plans.
- **Insurer name on screen.** The script says "your pet insurer" and the policy is the fictional *Pawse Demo Pet Insurance*,
  with terms adapted from Calingo's. Don't show a real insurer's name or logo answering a call it never made in a
  public video. If you want the Calingo name, use it only as "terms based on Calingo's AVB" in the credits.
- **Honest money.** Don't say the taxi is covered: transport is not in the AVB. The saving is that Pawse steered the
  user away from the CHF 150 home-visit fee, which the insurance would not have paid.
- **Triage wording** is demo copy written by non-vets, not veterinary advice; keep the 🟡 card text conservative.
- **Calendar** is the user's own calendar (read-only); show the free slot, not private event titles.

## Fallbacks if time runs short

Cut the taxi (1:42–1:54) and end on the vet confirmation. The coverage story is complete without it.
