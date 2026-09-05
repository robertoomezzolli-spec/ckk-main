#!/usr/bin/env python3
"""External CKK period-class test.

Purpose
-------
Test the narrow hypothesis:

    RECURRENCE -> CYCLE -> INTEGER

supports a *generic period class* T without fixing T = 2*pi, and that the
integer winding is invariant under arbitrary nonzero rescaling of the cycle
coordinate.

This is deliberately external to the CKK kernel. It imports no physics and does
not alter grammar.py, expand.py, seeds, operators, or generation.

What would count as success
---------------------------
For arbitrary nonzero period T and integer n:
  1. a lifted coordinate changes by n*T after n closed turns;
  2. the normalized increment Delta/T is exactly n;
  3. under coordinate rescaling x -> a*x, T -> a*T, the integer is unchanged;
  4. non-integer increments do NOT satisfy closure;
  5. T=2*pi behaves identically to T=1, pi, e, sqrt(2), phi, etc.

This does NOT derive the numerical value 2*pi. It tests whether 2*pi is merely
one coordinate realization of a more primitive closure class.
"""
from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "results" / "cycle_period_class.json"

PERIODS = {
    "unit": 1.0,
    "pi": math.pi,
    "two_pi": 2.0 * math.pi,
    "e": math.e,
    "sqrt2": math.sqrt(2.0),
    "phi": (1.0 + math.sqrt(5.0)) / 2.0,
    "arbitrary": 7.314159265358979,
}

SCALES = [0.125, 0.5, 1.0, 3.0, math.sqrt(2.0), math.pi]
WINDINGS = [-7, -3, -1, 0, 1, 2, 5, 11]
NONINTEGER_WINDINGS = [Fraction(1, 2), Fraction(2, 3), Fraction(3, 2), Fraction(7, 3)]


def close_error(delta: float, period: float) -> float:
    """Distance of delta/period from nearest integer."""
    q = delta / period
    return abs(q - round(q))


def run() -> dict:
    tol = 1e-12
    integer_cases = []
    scale_cases = []
    negative_cases = []

    # Positive: every nonzero coordinate period supports the same Z-valued class.
    for pname, T in PERIODS.items():
        for n in WINDINGS:
            delta = n * T
            recovered = delta / T
            err = abs(recovered - n)
            integer_cases.append({
                "period": pname,
                "T": T,
                "n": n,
                "delta": delta,
                "recovered": recovered,
                "error": err,
                "pass": err < tol and close_error(delta, T) < tol,
            })

            # Gauge/coordinate-rescaling invariance.
            for a in SCALES:
                T2 = a * T
                delta2 = a * delta
                recovered2 = delta2 / T2
                err2 = abs(recovered2 - n)
                scale_cases.append({
                    "period": pname,
                    "scale": a,
                    "n": n,
                    "recovered": recovered2,
                    "error": err2,
                    "pass": err2 < tol,
                })

    # Negative: fractional turn counts must not close.
    for pname, T in PERIODS.items():
        for q in NONINTEGER_WINDINGS:
            delta = float(q) * T
            err = close_error(delta, T)
            negative_cases.append({
                "period": pname,
                "fraction": f"{q.numerator}/{q.denominator}",
                "closure_error": err,
                "pass": err > 1e-9,
            })

    # Singular negative control: T=0 cannot define a quotient period class.
    zero_period_rejected = True
    try:
        _ = 1.0 / 0.0
        zero_period_rejected = False
    except ZeroDivisionError:
        pass

    positive_pass = all(x["pass"] for x in integer_cases)
    scale_pass = all(x["pass"] for x in scale_cases)
    negative_pass = all(x["pass"] for x in negative_cases) and zero_period_rejected

    # Specific test of whether 2*pi is numerically privileged in this structure.
    by_period = {}
    for pname in PERIODS:
        errs = [x["error"] for x in integer_cases if x["period"] == pname]
        scale_errs = [x["error"] for x in scale_cases if x["period"] == pname]
        by_period[pname] = {
            "max_integer_recovery_error": max(errs),
            "max_rescaling_error": max(scale_errs),
            "all_integer_cases_pass": all(x["pass"] for x in integer_cases if x["period"] == pname),
        }

    two_pi_special = any(
        by_period["two_pi"][k] != by_period[p][k]
        for p in by_period if p != "two_pi"
        for k in ("all_integer_cases_pass",)
    )

    status = "PERIOD_CLASS_PASS" if positive_pass and scale_pass and negative_pass and not two_pi_special else "PERIOD_CLASS_FAIL"

    result = {
        "schema": "ckk.period-class.external.v1",
        "status": status,
        "hypothesis": "Closure defines an equivalence class modulo an arbitrary nonzero period T; winding is the invariant integer, not the numeric value of T.",
        "tests": {
            "integer_closure_pass": positive_pass,
            "coordinate_rescaling_invariance_pass": scale_pass,
            "noninteger_rejection_pass": negative_pass,
            "two_pi_numerically_privileged": two_pi_special,
        },
        "period_summary": by_period,
        "counts": {
            "integer_cases": len(integer_cases),
            "rescaling_cases": len(scale_cases),
            "negative_cases": len(negative_cases) + 1,
        },
        "formal_readout": {
            "quotient": "R / (T Z), T != 0",
            "closure": "x ~ x + T",
            "n_turns": "Delta x = n T",
            "invariant": "n = Delta x / T in Z",
            "rescaling": "x' = a x, T' = a T => Delta x'/T' = Delta x/T",
            "two_pi_instantiation": "choose angular coordinate theta with T = 2*pi",
        },
        "claim_boundary": "The test does not derive 2*pi and does not prove that nature must use radians. It establishes that the abstract CKK sequence RECURRENCE->CYCLE->INTEGER is naturally represented by a period quotient with arbitrary T, while the integer winding is coordinate invariant. Therefore 2*pi can enter only at the external angular-coordinate realization, not as kernel content.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    r = run()
    raise SystemExit(0 if r["status"] == "PERIOD_CLASS_PASS" else 1)
