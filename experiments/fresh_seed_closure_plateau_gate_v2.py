#!/usr/bin/env python3
"""Preregistered closure-completion plateau + floor-corrected coupling gate.

Interpretation tested externally against the unchanged CKK grammar/kernel:
- attaching CYCLE closure to an open BOUNDARY preserves/opens future potential,
- attaching the same closure to already-closed CYCLE/PRODUCT collapses future potential,
- any pressure->opening coupling must be tested against a floor-matched null,
- persistence is a plateau question, not a monotone-growth question.

This file intentionally delegates graph generation / feature extraction to the v1 fresh-seed
gate and changes only the preregistered decision layer and graph horizon/cap.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

# Reuse the already-audited measurement implementation; do not touch the kernel.
from fresh_seed_fiber_jump_gate import (
    build_context,
    evaluate_horizon,
    permutation_mean_difference,
    spearman_rho,
)

SCHEMA = "ckk.external.fresh-seed-closure-plateau-floor-null.v2"
OUT = Path("results/fresh_seed_closure_plateau_gate_v2.json")

# -------- PREREGISTRATION --------
FRESH_OCC = (2, 3)
LEVELS = 10
CAP = 100_000
HORIZONS = (2, 3, 4, 5, 6, 7)
COMPRESSION_LAG = 3
PERMUTATIONS = 4000
RNG_SEED = 20260905

# Closure-completion specificity: same op_fiber, different base structure.
MIN_OPENING_ADVANTAGE_BITS = 0.25
MAX_PAIRWISE_P = 0.01

# Plateau criterion is fixed before the larger-graph run.
PLATEAU_H = (5, 6, 7)
PLATEAU_MAX_RANGE_BITS = 0.05
PLATEAU_MIN_MEAN_BITS = 0.15
MIN_PLATEAU_N_PER_H = 5

# Floor-corrected null: pressure-opening coupling on BOUNDARY must exceed a null built
# from controls matched on the observable post-transition floor (future-potential bin),
# not raw controls. A matched null is considered usable only with enough pairs.
FLOOR_BIN_BITS = 0.25
MIN_FLOOR_MATCHED_PAIRS = 20
MIN_BOUNDARY_RHO = 0.25
MIN_RHO_ADVANTAGE_OVER_FLOOR_NULL = 0.20
MAX_RHO_PERMUTATION_P = 0.01


def finite(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def floor_bin(v: float) -> int:
    return math.floor(v / FLOOR_BIN_BITS)


def floor_matched_null(boundary_rows, control_rows, rng: random.Random):
    """Construct a control null matched to BOUNDARY on post-transition future-potential floor.

    Rows are expected to carry pressure_bits, opening_bits, and post_bits. For every boundary
    row, sample (with replacement) a control row from the same post_bits bin. This preserves
    the compression floor that mechanically constrains further loss.
    """
    pools = {}
    for r in control_rows:
        if all(finite(r.get(k)) for k in ("pressure_bits", "opening_bits", "post_bits")):
            pools.setdefault(floor_bin(r["post_bits"]), []).append(r)

    matched_b = []
    matched_c = []
    for b in boundary_rows:
        if not all(finite(b.get(k)) for k in ("pressure_bits", "opening_bits", "post_bits")):
            continue
        pool = pools.get(floor_bin(b["post_bits"]), [])
        if not pool:
            continue
        matched_b.append(b)
        matched_c.append(rng.choice(pool))

    def rho(rows):
        if len(rows) < 3:
            return None
        return spearman_rho([r["pressure_bits"] for r in rows], [r["opening_bits"] for r in rows])

    rb = rho(matched_b)
    rc = rho(matched_c)
    advantage = None if rb is None or rc is None else rb - rc

    # Permutation null on the matched sample: shuffle opening labels between BOUNDARY and
    # floor-matched controls while keeping pressures and floor matching fixed.
    p = None
    if len(matched_b) >= MIN_FLOOR_MATCHED_PAIRS and rb is not None and rc is not None:
        observed = rb - rc
        combined_openings = [r["opening_bits"] for r in matched_b] + [r["opening_bits"] for r in matched_c]
        bp = [r["pressure_bits"] for r in matched_b]
        cp = [r["pressure_bits"] for r in matched_c]
        ge = 0
        for _ in range(PERMUTATIONS):
            vals = combined_openings[:]
            rng.shuffle(vals)
            bo = vals[: len(matched_b)]
            co = vals[len(matched_b) :]
            prb = spearman_rho(bp, bo)
            prc = spearman_rho(cp, co)
            if prb is not None and prc is not None and (prb - prc) >= observed:
                ge += 1
        p = (ge + 1) / (PERMUTATIONS + 1)

    return {
        "matched_pairs": len(matched_b),
        "boundary_rho": rb,
        "floor_null_control_rho": rc,
        "rho_advantage": advantage,
        "permutation_p": p,
        "pass": (
            len(matched_b) >= MIN_FLOOR_MATCHED_PAIRS
            and rb is not None and rb >= MIN_BOUNDARY_RHO
            and advantage is not None and advantage >= MIN_RHO_ADVANTAGE_OVER_FLOOR_NULL
            and p is not None and p <= MAX_RHO_PERMUTATION_P
        ),
    }


def extract_rows(detail):
    """Compatibility adapter for v1 evaluator detail rows."""
    rows = detail.get("rows") or detail.get("records") or []
    out = {"BOUNDARY": [], "CYCLE": [], "PRODUCT": []}
    for r in rows:
        k = r.get("base_kind") or r.get("kind")
        if k not in out:
            continue
        # v1 naming aliases
        pressure = r.get("pressure_bits", r.get("compression_bits"))
        opening = r.get("opening_bits")
        post = r.get("post_bits", r.get("future_after_bits", r.get("after_bits")))
        out[k].append({"pressure_bits": pressure, "opening_bits": opening, "post_bits": post})
    return out


def main():
    rng = random.Random(RNG_SEED)
    result = {
        "schema": SCHEMA,
        "kernel_modified": False,
        "preregistered": {
            "fresh_occ": list(FRESH_OCC),
            "levels": LEVELS,
            "cap": CAP,
            "H": list(HORIZONS),
            "compression_lag": COMPRESSION_LAG,
            "specificity": {
                "min_opening_advantage_bits": MIN_OPENING_ADVANTAGE_BITS,
                "max_pairwise_p": MAX_PAIRWISE_P,
            },
            "plateau": {
                "H": list(PLATEAU_H),
                "max_range_bits": PLATEAU_MAX_RANGE_BITS,
                "min_mean_bits": PLATEAU_MIN_MEAN_BITS,
                "min_n_per_H": MIN_PLATEAU_N_PER_H,
            },
            "floor_corrected_null": {
                "floor_bin_bits": FLOOR_BIN_BITS,
                "min_matched_pairs": MIN_FLOOR_MATCHED_PAIRS,
                "min_boundary_rho": MIN_BOUNDARY_RHO,
                "min_rho_advantage": MIN_RHO_ADVANTAGE_OVER_FLOOR_NULL,
                "max_permutation_p": MAX_RHO_PERMUTATION_P,
            },
        },
        "contexts": {},
    }

    for occ in FRESH_OCC:
        ctx = build_context(occ=occ, levels=LEVELS, cap=CAP)
        c_out = {"generator": ctx.get("generator", {}), "horizons": {}}

        plateau_vals = []
        plateau_ns = []
        floor_passes = []
        specificity_passes = []

        for H in HORIZONS:
            ev = evaluate_horizon(ctx, H=H, compression_lag=COMPRESSION_LAG, permutations=PERMUTATIONS, rng=rng)
            by = ev.get("by_base_kind", {})

            # Re-register closure-completion specificity at every horizon where both controls exist.
            spec = {}
            for control in ("CYCLE", "PRODUCT"):
                b = by.get("BOUNDARY", {})
                c = by.get(control, {})
                mb = b.get("mean_opening_bits")
                mc = c.get("mean_opening_bits")
                if finite(mb) and finite(mc):
                    diff = mb - mc
                    # use evaluator's already computed pairwise p if available
                    old = ev.get("opening_specificity", {}).get(f"BOUNDARY_vs_{control}", {})
                    p = old.get("permutation_p")
                    passed = diff >= MIN_OPENING_ADVANTAGE_BITS and finite(p) and p <= MAX_PAIRWISE_P
                else:
                    diff = p = None
                    passed = False
                spec[control] = {"mean_difference_bits": diff, "permutation_p": p, "pass": passed}

            rows = extract_rows(ev)
            floor_null = floor_matched_null(rows["BOUNDARY"], rows["CYCLE"] + rows["PRODUCT"], rng)

            bstat = by.get("BOUNDARY", {})
            if H in PLATEAU_H:
                plateau_vals.append(bstat.get("mean_opening_bits"))
                plateau_ns.append(bstat.get("n", 0))

            horizon_spec_pass = all(v["pass"] for v in spec.values())
            specificity_passes.append(horizon_spec_pass)
            floor_passes.append(floor_null["pass"])

            c_out["horizons"][str(H)] = {
                "by_base_kind": by,
                "closure_completion_specificity": spec,
                "specificity_pass": horizon_spec_pass,
                "floor_corrected_null": floor_null,
            }

        plateau_finite = len(plateau_vals) == len(PLATEAU_H) and all(finite(v) for v in plateau_vals)
        plateau_range = (max(plateau_vals) - min(plateau_vals)) if plateau_finite else None
        plateau_mean = (sum(plateau_vals) / len(plateau_vals)) if plateau_finite else None
        plateau_n_ok = len(plateau_ns) == len(PLATEAU_H) and all(n >= MIN_PLATEAU_N_PER_H for n in plateau_ns)
        plateau_pass = (
            plateau_finite
            and plateau_n_ok
            and plateau_range <= PLATEAU_MAX_RANGE_BITS
            and plateau_mean >= PLATEAU_MIN_MEAN_BITS
        )

        c_out["plateau"] = {
            "H": list(PLATEAU_H),
            "mean_opening_bits": plateau_vals,
            "n": plateau_ns,
            "range_bits": plateau_range,
            "mean_bits": plateau_mean,
            "pass": plateau_pass,
        }
        c_out["closure_completion_specificity_pass_all_H"] = all(specificity_passes)
        c_out["floor_corrected_coupling_pass_all_H"] = all(floor_passes)
        c_out["pass"] = (
            not c_out.get("generator", {}).get("cap_hit", False)
            and c_out["closure_completion_specificity_pass_all_H"]
            and c_out["floor_corrected_coupling_pass_all_H"]
            and plateau_pass
        )
        result["contexts"][str(occ)] = c_out

    result["status"] = (
        "FRESH_SEED_CLOSURE_COMPLETION_PLATEAU_AND_FLOOR_COUPLING_CONFIRMED"
        if all(v["pass"] for v in result["contexts"].values())
        else "FRESH_SEED_CLOSURE_PLATEAU_FLOOR_GATE_NOT_CONFIRMED"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
