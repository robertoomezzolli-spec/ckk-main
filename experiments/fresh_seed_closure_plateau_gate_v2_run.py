#!/usr/bin/env python3
"""Lean execution wrapper for the frozen V2 closure plateau gate.

This wrapper does NOT change any preregistered decision. It skips expensive
permutation diagnostics outside the horizons/base-kind combinations that enter
the frozen gates:
- closure specificity permutations: H=2,3,4 only (both controls)
- floor-preserving coupling null: BOUNDARY at H=2,3 only
- plateau H=5,6,7 uses the unchanged mean opening and sample-count criteria

All actually gated permutation tests still use the frozen 4000 permutations.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import fresh_seed_closure_plateau_gate_v2_fast as FAST  # noqa: E402

V2 = FAST.V2
G = FAST.G
_ORIG_FLOOR_NULL = V2.floor_preserving_null
_ORIG_MEAN_DIFF = V2.perm_mean_diff_p


def _decode(seed: int, base: int):
    x = seed - base
    occ = x // 100
    rem = x % 100
    H = rem // 10
    idx = rem % 10
    return occ, H, idx


def gated_floor_null(rows, seed):
    _occ, H, idx = _decode(seed, 20273000)
    # obs insertion order in V2 is BOUNDARY, CYCLE, PRODUCT => BOUNDARY idx=1.
    if H in V2.COUPLING_H and idx == 1:
        return _ORIG_FLOOR_NULL(rows, seed)
    return {
        "n": len(rows),
        "observed_rho": None,
        "null_mean_rho": None,
        "null_median_rho": None,
        "rho_excess_over_null_median": None,
        "permutation_p": None,
        "pass": False,
        "skipped_non_preregistered_diagnostic": True,
    }


def gated_mean_diff(a, b, observed, seed):
    _occ, H, _idx = _decode(seed, 20272000)
    if H in V2.SPECIFICITY_H:
        return _ORIG_MEAN_DIFF(a, b, observed, seed)
    return None


def main():
    V2.floor_preserving_null = gated_floor_null
    V2.perm_mean_diff_p = gated_mean_diff
    FAST.main()


if __name__ == "__main__":
    main()
