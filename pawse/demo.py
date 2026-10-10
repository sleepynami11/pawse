"""The team's simulated Mimi story, priced on a demo policy under real Swiss pet-insurance terms (AVB, December 2025). No external calls, bookings or policy decisions."""
import json
from decimal import Decimal
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/demo", tags=["Synthetic demo"])


def costs():
    policy = json.loads((Path(__file__).resolve().parent.parent / "research/pet-insurance/policy/policy.json").read_text())
    treatment, taxi, house_call = Decimal(600), Decimal(25), Decimal(150)
    deductible = Decimal(str(policy["cost_sharing"]["annual_deductible_chf"]))
    rate = Decimal(str(policy["cost_sharing"]["reimbursement_rate"]))
    limit = Decimal(str(policy["coverages"]["accident_illness_base"]["annual_limit_chf"]))
    reimbursed = min(max(treatment - deductible, Decimal(0)) * rate, limit)
    return {"currency": "CHF", "treatment": float(treatment), "remaining_deductible": float(deductible),
            "reimbursement_rate": float(rate), "reimbursed": float(reimbursed),
            "clinic": float(treatment - reimbursed + taxi), "home": float(treatment - reimbursed + house_call),
            "taxi": float(taxi), "home_visit_extra": float(house_call),
            "assumptions": "Demo accident claim; CHF 300 annual deductible unused, annual limit unused, CHF 600 eligible treatment, CHF 25 taxi paid by the owner. No insurer has approved this claim.",
            "exclusions": ["Home-visit surcharge not covered: it needs an annual limit of at least CHF 12'000 (AVB 1.2, Emergency treatment).", "Physiotherapy is not covered: the complementary medicine module is not in this policy (AVB 1.2, Complementary medicine). Ask the owner before adding it."],
            "claim_days": policy["claims_process"]["submit_within_days"]}


def line(speaker, de, en):
    return {"speaker": speaker, "german": de, "subtitle": en}


@router.get("/mimi")
async def mimi():
    return {"id": "mimi-zurich", "synthetic": True, "title": "Mimi needs a little help.",
            "notice": "Interactive story rehearsal. All calls, replies, calendar slots, prices and coverage are simulated. No appointments or taxi rides are booked.",
            "costs": costs(), "calendar": {"source": "synthetic", "free_from": "16:00", "appointment": "16:30", "taxi": "16:05"},
            "steps": [
                {"time": "0:00–0:17", "title": "Zurich. You don't speak German.", "description": "Mimi is limping. You describe what happened in your own language. In this rehearsal the video is part of the story; live intake currently accepts photos and audio.", "lines": []},
                {"time": "0:17–0:30", "title": "One question that changes the plan.", "description": "Did she fall or jump? In this story, Mimi jumped off the wardrobe. Pawse prepares a same-day vet request for a possible accident; the vet must assess her.", "lines": []},
                {"time": "0:30–0:58", "title": "A German call. Every word understood.", "description": "The simulated practice offers 16:30, or a home visit tonight. The demo calendar is free from 16:00. Review the offer before continuing.", "lines": [
                    line("Pawse", "Meine Katze Mimi hinkt, seit sie vom Kleiderschrank gesprungen ist. Können Sie sie heute untersuchen?", "My cat Mimi has been limping since jumping off the wardrobe. Could you examine her today?"),
                    line("Vet · simulated", "Wir können Ihnen um 16:30 Uhr einen Termin in der Praxis oder heute Abend einen Hausbesuch anbieten. Die Behandlung kostet voraussichtlich 600 Franken, der Hausbesuch zusätzlich 150 Franken.", "We can offer 16:30 at the practice, or a home visit tonight. Treatment is estimated at CHF 600; a home visit adds CHF 150."),
                    line("Pawse", "Vielen Dank. Ich frage die Halterin oder den Halter, welche Option gewünscht ist, und kläre die Versicherung. Noch nichts verbindlich buchen, bitte.", "Thank you. I will ask the owner which option they prefer and check insurance. Please do not make a binding booking yet.")]},
                {"time": "0:58–1:30", "title": "Understand the cost before choosing.", "description": "Your pet insurer checks the policy. These estimates assume the deductible and annual limit have not yet been used.", "lines": [
                    line("Pawse", "Mimi hinkt nach einem Sprung vom Kleiderschrank. Können Sie bitte prüfen, ob dies als Unfall gedeckt wäre und welcher Selbstbehalt gilt? Sind Hausbesuche und Physiotherapie eingeschlossen?", "Mimi is limping after jumping from a wardrobe. Could you check accident coverage and the deductible? Are home visits and physiotherapy included?"),
                    line("Insurer · simulated", "Unfälle sind ab dem ersten Tag gedeckt, auch in der Karenzfrist. Nach der Franchise von 300 Franken übernehmen wir 80 Prozent. Der Hausbesuch ist in Ihrem Vertrag aber nicht gedeckt, das gibt es erst ab einer Versicherungssumme von 12'000 Franken. Und eine Physiotherapie danach wäre auch nicht versichert.", "Accidents are covered from day one, even in the waiting period. After the CHF 300 deductible, we pay 80%. The home visit isn't covered on your policy, though: that needs a sum insured of CHF 12,000. And physiotherapy afterwards wouldn't be covered either.")]},
                {"time": "1:30–1:42", "title": "Your decision. Clear instructions.", "description": "Review the confirmation script. The clinic path requests 16:30, an itemised invoice and owner approval before physiotherapy. The home-visit path asks the vet to confirm an evening time.", "lines": [
                    line("Pawse", "Die Halterin oder der Halter möchte den Termin um 16:30 Uhr in der Praxis bestätigen. Bitte stellen Sie eine detaillierte Rechnung aus. Physiotherapie bitte nur nach vorheriger Rücksprache mit der Halterin oder dem Halter.", "The owner would like to confirm 16:30 at the practice. Please provide an itemised invoice and ask the owner before adding physiotherapy.")],
                 "home_lines": [line("Pawse", "Die Halterin oder der Halter möchte einen Hausbesuch heute Abend. Können Sie bitte eine genaue Uhrzeit bestätigen? Bitte stellen Sie eine detaillierte Rechnung aus und fragen Sie vor einer Physiotherapie nach.", "The owner would like a home visit tonight. Could you confirm the exact time? Please provide an itemised invoice and ask before physiotherapy.")]},
                {"time": "1:42–2:00", "title": "A carrier, a ride, and a clear next step.", "description": "Clinic path: rehearse the taxi request for 16:05. Home-visit path: an evening time still needs confirmation. Keep the case notes and claim checklist together.", "lines": [
                    line("Pawse", "Wir benötigen um 16:05 Uhr ein Taxi zur Tierarztpraxis. Ist eine Katze in einer geschlossenen Transportbox erlaubt? Bitte bestätigen Sie den Preis und die Abholadresse mit der Halterin oder dem Halter.", "We need a taxi to the vet at 16:05. Is a cat in a closed carrier allowed? Please confirm the price and pickup address with the owner."),
                    line("Taxi · simulated", "Ja, eine Katze in der Transportbox ist kein Problem. In dieser Demo beträgt der Fahrpreis 25 Franken.", "Yes, a cat in a carrier is fine. In this demo the fare is CHF 25.")]}],
            "checklist": ["Keep the original video or photo for the vet.", "Keep the itemised invoice, receipts and prescriptions.", "Ask before physiotherapy or other excluded extras.", "Submit the invoice within 30 days (AVB 2.2).", "A real appointment, pickup address, fare and coverage still need direct confirmation."]}
