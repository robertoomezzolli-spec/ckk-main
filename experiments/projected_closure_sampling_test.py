#!/usr/bin/env python3
"""External projection test: exact hidden closure, inexact observed recurrence.

This experiment is deliberately OUTSIDE the CKK kernel.
It tests an epistemic hypothesis only:

    An exactly closed underlying state can fail to exhibit exact recurrence
    in a lower-dimensional finite observation stream when the observation
    cadence is incommensurate with the hidden period and the observer sees
    only a projection.

No claim is made that this models spacetime, SRT, pi, or any physical system.
The point is to distinguish exact structural closure from finite observed
reconstruction.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "results" / "projected_closure_sampling.json"

TAU = 1.0  # hidden exact period, intentionally NOT 2*pi
ALPHAS = {
    "commensurate_half": 0.5,
    "commensurate_third": 1.0/3.0,
    "irrational_sqrt2": math.sqrt(2.0) - 1.0,
    "irrational_phi": (math.sqrt(5.0) - 1.0) / 2.0,
}
HORIZONS = [16, 64, 256, 1024, 4096]


def hidden_state(t: float) -> tuple[float, float]:
    # Exact closure is represented by the quotient phase t mod TAU.
    # Cos/sin are used only as an embedding for observation, not to define TAU.
    u = (t % TAU) / TAU
    ang = 2.0 * math.pi * u
    return math.cos(ang), math.sin(ang)


def observe(state: tuple[float, float]) -> float:
    # 1D projection that loses phase information.
    x, y = state
    return x + math.sqrt(2.0) * y


def recurrence_error(alpha: float, n: int) -> float:
    y0 = observe(hidden_state(0.0))
    best = float("inf")
    for k in range(1, n + 1):
        y = observe(hidden_state(k * alpha))
        best = min(best, abs(y - y0))
    return best


def exact_hidden_return(alpha: float, n: int, tol: float = 1e-14) -> bool:
    for k in range(1, n + 1):
        phase = (k * alpha) % TAU
        if min(phase, TAU - phase) < tol:
            return True
    return False


def run() -> dict:
    arms = {}
    for name, alpha in ALPHAS.items():
        rows = []
        for n in HORIZONS:
            rows.append({
                "horizon": n,
                "hidden_exact_return_seen": exact_hidden_return(alpha, n),
                "best_observed_recurrence_error": recurrence_error(alpha, n),
            })
        arms[name] = rows

    # Gates:
    # 1) rational/commensurate controls must show an exact hidden return quickly.
    commensurate_pass = all(
        any(r["hidden_exact_return_seen"] for r in arms[name])
        for name in ("commensurate_half", "commensurate_third")
    )
    # 2) irrational cadence arms must show no exact hidden return over all finite horizons.
    irrational_no_exact = all(
        not any(r["hidden_exact_return_seen"] for r in arms[name])
        for name in ("irrational_sqrt2", "irrational_phi")
    )
    # 3) nevertheless their observed recurrence error must shrink with more samples.
    irrational_approach = all(
        arms[name][-1]["best_observed_recurrence_error"] < arms[name][0]["best_observed_recurrence_error"]
        for name in ("irrational_sqrt2", "irrational_phi")
    )

    status = "PROJECTED_CLOSURE_PASS" if commensurate_pass and irrational_no_exact and irrational_approach else "PROJECTED_CLOSURE_FAIL"

    result = {
        "schema": "ckk.external.projected-closure.v1",
        "status": status,
        "hidden_structure": {
            "period_T": TAU,
            "closure_rule": "phase ~ phase + T",
            "exact": True,
        },
        "observation": {
            "dimension": 1,
            "map": "y = x + sqrt(2) y_hidden",
            "finite_horizons": HORIZONS,
        },
        "tests": {
            "commensurate_controls_exact_return": commensurate_pass,
            "irrational_sampling_no_exact_return": irrational_no_exact,
            "irrational_sampling_approaches_return": irrational_approach,
        },
        "arms": arms,
        "claim_boundary": (
            "This establishes only that exact hidden closure and finite observed recurrence are not equivalent. "
            "A finite lower-dimensional observer with incommensurate sampling can see arbitrarily close returns without ever sampling the exact closure event. "
            "It does not establish that physical reality has hidden dimensions or that SRT/pi are projections."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    r = run()
    raise SystemExit(0 if r["status"] == "PROJECTED_CLOSURE_PASS" else 1)
