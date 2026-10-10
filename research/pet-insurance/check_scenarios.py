"""Recompute every scenario's expected payout from its invoice and the demo policy.

Usage: python research/pet-insurance/check_scenarios.py
Exits non-zero if any `expected_payout_chf` disagrees with the AVB 1.5 payout rule.
"""

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
POLICY = json.loads((HERE / "policy" / "policy.json").read_text())
SCENARIOS = yaml.safe_load((HERE / "scenarios" / "scenarios.yaml").read_text())

DEDUCTIBLE = POLICY["cost_sharing"]["annual_deductible_chf"]
RATE = POLICY["cost_sharing"]["reimbursement_rate"]
COV = POLICY["coverages"]
BASE_LIMIT = COV["accident_illness_base"]["annual_limit_chf"]


def payout(coverage: dict) -> float:
    """Deductible first, then reimbursement rate, then the remaining limit (AVB 1.5)."""
    base = prevention = diet = outside_deductible = 0.0
    for item in coverage["invoice"]:
        # "depends" items are computed for the branch the policy itself pays (e.g. unknown third party).
        if item["decision"] not in ("covered", "depends"):
            continue
        kind = item.get("coverage")
        if kind == "prevention":
            prevention += item["chf"]
        elif kind == "prescription_diet":
            diet += item["chf"]
        elif kind == "emergency_pet_care" or coverage.get("deductible_used_before_chf") is None:
            outside_deductible += item["chf"]
        else:
            base += item["chf"]
    diet = min(diet, COV["prescription_diet"]["annual_limit_chf"])

    remaining_deductible = DEDUCTIBLE - (coverage.get("deductible_used_before_chf") or 0)
    base_after = max(0.0, base + diet - remaining_deductible)
    remaining_deductible = max(0.0, remaining_deductible - (base + diet))
    prevention_after = max(0.0, prevention - remaining_deductible)

    limit_left = BASE_LIMIT - (coverage.get("limit_used_before_chf") or 0)
    paid = min(base_after * RATE, limit_left)
    paid += min(prevention_after * COV["prevention"]["reimbursement_rate"], COV["prevention"]["annual_limit_chf"])
    return round(paid + outside_deductible, 2)


def coverages(scenario: dict):
    if "coverage" in scenario:
        yield scenario["id"], scenario["coverage"]
    for name, branch in (scenario.get("branches") or {}).items():
        if "invoice" in branch.get("coverage", {}):
            yield f"{scenario['id']}[{name}]", branch["coverage"]


failures = 0
for scenario in SCENARIOS["emergency_scenarios"] + SCENARIOS["routine_scenarios"]:
    for label, cov in coverages(scenario):
        got, want = payout(cov), cov["expected_payout_chf"]
        ok = abs(got - want) < 0.01
        failures += not ok
        print(f"{'OK ' if ok else 'BAD'} {label:45} expected {want:>8} computed {got:>8}")

sys.exit(1 if failures else 0)
