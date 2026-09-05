#!/usr/bin/env python3
"""Tick-only asymptotic closure vs entropy-floor gate.

KERNEL POLICY: CKK kernel remains read-only. This is an external harness.

Frozen question:
If there is no external time variable, can a state approach closure indefinitely
under pure iteration while a finite entropy/noise floor renders further
refinement physically indistinguishable before exact mathematical closure?

This test does NOT claim that time does not exist or that this models the real
Universe. It tests the architecture only.
"""
from __future__ import annotations
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "results" / "tick_entropy_closure_gate.json"

# Pure tick process: x_n -> 1 asymptotically, never equals 1 for finite n.
def x_of_n(n: int) -> float:
    return 1.0 - 2.0 ** (-n)

def residual(n: int) -> float:
    return 1.0 - x_of_n(n)

# Entropy/noise floor. We scan several floors including 1e-7, matching the
# user's 0.9999999 intuition, but do not privilege any as physical fact.
FLOORS = [1e-2, 1e-4, 1e-7, 1e-10, 1e-13]
MAX_N = 200

def first_indistinguishable_tick(floor: float):
    for n in range(1, MAX_N + 1):
        if residual(n) <= floor:
            return n
    return None

def main():
    finite_ticks_never_exact = all(x_of_n(n) < 1.0 for n in range(1, 53))
    monotone = all(residual(n+1) < residual(n) for n in range(1, 52))

    rows = []
    for floor in FLOORS:
        n_star = first_indistinguishable_tick(floor)
        rows.append({
            "entropy_floor": floor,
            "n_star": n_star,
            "x_at_n_star": x_of_n(n_star) if n_star is not None else None,
            "residual_at_n_star": residual(n_star) if n_star is not None else None,
            "previous_residual": residual(n_star - 1) if n_star and n_star > 1 else None,
            "criterion_met": n_star is not None and residual(n_star) <= floor,
            "exact_closure_reached": n_star is not None and x_of_n(n_star) == 1.0,
        })

    all_floors_stop_finitely = all(r["criterion_met"] for r in rows)
    none_exact = all(not r["exact_closure_reached"] for r in rows)
    tighter_floor_requires_more_ticks = all(rows[i+1]["n_star"] > rows[i]["n_star"] for i in range(len(rows)-1))

    # Specific audit point for x >= 0.9999999 equivalently residual <= 1e-7.
    audit = next(r for r in rows if r["entropy_floor"] == 1e-7)

    passed = finite_ticks_never_exact and monotone and all_floors_stop_finitely and none_exact and tighter_floor_requires_more_ticks

    result = {
        "schema": "ckk.external.tick-entropy-closure.v1",
        "status": "TICK_ENTROPY_CLOSURE_PASS" if passed else "TICK_ENTROPY_CLOSURE_FAIL",
        "uses_external_time_variable": False,
        "iteration_variable": "n (ordering only; no duration assigned)",
        "closure_target": 1.0,
        "finite_ticks_never_exact": finite_ticks_never_exact,
        "residual_monotone": monotone,
        "rows": rows,
        "audit_0_9999999": audit,
        "interpretation": "A tick-only asymptotic process can remain mathematically non-closed at every finite iteration while any finite entropy/noise floor creates a finite indistinguishability tick n*. Exact closure is therefore not required for operational indistinguishability in this toy architecture.",
        "claim_boundary": "Synthetic architecture test only. It does not establish that cosmic evolution uses this rule, that entropy causes heat death at x=0.9999999, or that time is non-fundamental in nature."
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)

if __name__ == "__main__":
    main()
