#!/usr/bin/env python3
"""External Flatland/closure projection test.

Question
--------
Can an abstract closure class be realized without assuming a 2D Euclidean
circle, while a lower-dimensional observer only ever sees finite-resolution
approximations and therefore never lands exactly on closure?

This is intentionally external to the CKK kernel. It does not modify or steer
CKK generation.

Construction
------------
Use the unit complex phase z = exp(i t) as a closure class in a 2D ambient
representation. The observer is denied direct access to the phase manifold and
only receives polygonal/chordal samples at finite N.

We measure:
  * exact ambient closure: z(t+T) == z(t) analytically for T = 2*pi;
  * finite-sample perimeter P_N = 2 N sin(pi/N), which approaches 2*pi but
    never equals it for finite N;
  * projection/chord error, which vanishes only in the N -> infinity limit;
  * quotient invariance under arbitrary coordinate rescaling T -> a T.

The point is not that 'circles do not exist'. The test distinguishes exact
closure of the abstract quotient from finite observational reconstruction of
that closure.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "results" / "flatland_closure_projection.json"


def polygon_perimeter(n: int, r: float = 1.0) -> float:
    return 2.0 * n * r * math.sin(math.pi / n)


def sagitta_error(n: int, r: float = 1.0) -> float:
    # max radial gap between arc and chord over one segment
    return r * (1.0 - math.cos(math.pi / n))


def run() -> dict:
    ns = [6, 12, 24, 48, 96, 192, 384, 768, 1536, 3072, 6144]
    rows = []
    target = 2.0 * math.pi

    for n in ns:
        p = polygon_perimeter(n)
        rows.append({
            "N": n,
            "perimeter": p,
            "gap_to_2pi": target - p,
            "relative_gap": (target - p) / target,
            "sagitta": sagitta_error(n),
            "exact_equal": p == target,
        })

    finite_never_exact = all(not r["exact_equal"] for r in rows)
    monotone_convergence = all(rows[i+1]["gap_to_2pi"] < rows[i]["gap_to_2pi"] for i in range(len(rows)-1))
    gap_shrinks = rows[-1]["gap_to_2pi"] < rows[0]["gap_to_2pi"]

    # Quotient closure itself is exact and coordinate-scale independent.
    scales = [0.125, 0.5, 1.0, 3.0, math.sqrt(2), math.pi]
    windings = [-5, -1, 0, 1, 2, 7]
    quotient_cases = []
    for a in scales:
        T = a * target
        for k in windings:
            delta = k * T
            recovered = delta / T
            quotient_cases.append({
                "scale": a,
                "k": k,
                "recovered": recovered,
                "pass": abs(recovered - k) < 1e-12,
            })

    quotient_pass = all(x["pass"] for x in quotient_cases)

    result = {
        "schema": "ckk.flatland-closure-projection.external.v1",
        "status": "FLATLAND_CLOSURE_PASS" if finite_never_exact and monotone_convergence and gap_shrinks and quotient_pass else "FLATLAND_CLOSURE_FAIL",
        "tests": {
            "finite_polygon_never_equals_exact_closure": finite_never_exact,
            "finite_reconstruction_converges_monotonically": monotone_convergence,
            "finite_gap_shrinks": gap_shrinks,
            "quotient_winding_exact_under_rescaling": quotient_pass,
        },
        "rows": rows,
        "interpretation": {
            "abstract_closure": "Exact closure belongs to the quotient/phase structure itself.",
            "observer_reconstruction": "A finite-resolution observer reconstructing via chords/polygons approaches the closure invariant but does not hit it at finite N.",
            "not_claimed": "This does not show physical reality is higher-dimensional, nor that circles do not exist. It shows why exact closure can coexist with measurements/approximations that only converge toward it.",
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    r = run()
    raise SystemExit(0 if r["status"] == "FLATLAND_CLOSURE_PASS" else 1)
