#!/usr/bin/env python3
"""Preregistered V2: closure completion, long-horizon plateau, floor-corrected coupling.

No kernel/grammar modification. This is an external measurement layer over the same CKK grammar.
The previous all-in-one "jump" gate stays red; V2 tests three narrower claims separately.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import fresh_seed_fiber_jump_gate as V1  # noqa: E402

G = V1.G
Derivation = V1.Derivation

# ---------------- FROZEN PREREGISTRATION ----------------
FRESH_OCC = (2, 3)
LEVELS = 12
CAP = 100_000
HORIZONS = (2, 3, 4, 5, 6, 7)
LAG = 3
PERMUTATIONS = 4000

# A. Replication of the narrower closure-completion contrast.
SPECIFICITY_H = (2, 3, 4)
MIN_OPENING_ADVANTAGE_BITS = 0.25
MAX_PAIRWISE_P = 0.01
MIN_KIND_N = 3

# B. Persistence as a nonzero plateau, not monotone growth.
PLATEAU_H = (5, 6, 7)
PLATEAU_MAX_RANGE_BITS = 0.05
PLATEAU_MIN_MEAN_BITS = 0.15
MIN_PLATEAU_N_PER_H = 5

# C. Pressure/opening coupling against a null with the exact same mechanical floor.
# Opening = log2(Omega_target/Omega_source) has row-wise lower bound
# floor_i = -log2(Omega_source), because Omega_target >= 1.
# The null keeps (pressure_i, floor_i) fixed and permutes only nonnegative headroom
# h_i = opening_i - floor_i = log2(Omega_target). Thus any rho generated purely by
# pressure<->floor structure survives the null by construction.
COUPLING_H = (2, 3)
MIN_BOUNDARY_N_COUPLING = 20
MIN_BOUNDARY_RHO = 0.25
MIN_RHO_EXCESS_OVER_FLOOR_NULL = 0.20
MAX_FLOOR_NULL_P = 0.01

OUT = ROOT / "results" / "fresh_seed_closure_plateau_gate_v2.json"


def spearman(xs, ys):
    return V1.spearman(xs, ys)


def perm_mean_diff_p(a, b, observed, seed):
    if len(a) < MIN_KIND_N or len(b) < MIN_KIND_N:
        return None
    rng = random.Random(seed)
    pool = list(a) + list(b)
    na = len(a)
    ge = 0
    for _ in range(PERMUTATIONS):
        z = pool[:]
        rng.shuffle(z)
        d = sum(z[:na]) / na - sum(z[na:]) / (len(z) - na)
        if d >= observed:
            ge += 1
    return (ge + 1) / (PERMUTATIONS + 1)


def build_graph(occ: int):
    seeds = V1.fresh_seeds(occ)
    pool, derivs, cap_hit = V1.expand_with_seeds(seeds, levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}
    first_seen = {s.structural_sig(): 0 for s in seeds if s.structural_sig() in states}
    unique = {}
    for d in derivs:
        if d.output not in states:
            continue
        first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)
        unique.setdefault(d.event_key(), d)

    edges = set()
    for d in unique.values():
        for u in set(d.inputs):
            if u in states and u != d.output:
                edges.add((u, d.output))

    adj = defaultdict(set)
    rev = defaultdict(set)
    for u, v in edges:
        adj[u].add(v)
        rev[v].add(u)

    sys.setrecursionlimit(max(100000, len(states) * 4))
    seen = set()
    order = []

    def d1(u):
        seen.add(u)
        for v in adj.get(u, ()):
            if v not in seen:
                d1(v)
        order.append(u)

    for n in states:
        if n not in seen:
            d1(n)

    comp = {}
    members = defaultdict(set)

    def d2(u, c):
        comp[u] = c
        members[c].add(u)
        for v in rev.get(u, ()):
            if v not in comp:
                d2(v, c)

    cid = 0
    for n in reversed(order):
        if n not in comp:
            d2(n, cid)
            cid += 1

    crev = defaultdict(set)
    for u, v in edges:
        cu, cv = comp[u], comp[v]
        if cu != cv:
            crev[cv].add(cu)

    fiber_targets = defaultdict(set)
    for d in unique.values():
        if d.operator != "op_fiber" or len(d.inputs) != 2:
            continue
        base, fib = d.inputs
        if base not in states or fib not in states or d.output not in states:
            continue
        if states[fib].kind != G.CYCLE:
            continue
        kind = states[base].kind
        if kind not in (G.BOUNDARY, G.CYCLE, G.PRODUCT):
            continue
        cb, ct = comp[base], comp[d.output]
        if cb != ct:
            fiber_targets[(cb, kind)].add(ct)

    return {
        "states": states,
        "first_seen": first_seen,
        "adj": adj,
        "crev": crev,
        "members": members,
        "comp": comp,
        "fiber_targets": fiber_targets,
        "cap_hit": cap_hit,
        "derivations": len(unique),
        "edges": len(edges),
        "sccs": len(members),
    }


def floor_preserving_null(rows, seed):
    """Exact-floor null for rho(pressure, opening).

    Keep each row's pressure and exact lower floor fixed. Shuffle only the nonnegative
    headroom above that floor. This preserves the mechanical floor effect but destroys
    any pressure/headroom association beyond it.
    """
    if len(rows) < MIN_BOUNDARY_N_COUPLING:
        return {
            "n": len(rows),
            "observed_rho": None,
            "null_mean_rho": None,
            "null_median_rho": None,
            "rho_excess_over_null_median": None,
            "permutation_p": None,
            "pass": False,
        }

    pressures = [r["pressure_bits"] for r in rows]
    openings = [r["opening_bits"] for r in rows]
    floors = [r["opening_floor_bits"] for r in rows]
    headroom = [o - f for o, f in zip(openings, floors)]
    observed = spearman(pressures, openings)
    if observed is None:
        return {
            "n": len(rows), "observed_rho": None, "null_mean_rho": None,
            "null_median_rho": None, "rho_excess_over_null_median": None,
            "permutation_p": None, "pass": False,
        }

    rng = random.Random(seed)
    null_rhos = []
    ge = 0
    for _ in range(PERMUTATIONS):
        h = headroom[:]
        rng.shuffle(h)
        null_opening = [f + x for f, x in zip(floors, h)]
        r = spearman(pressures, null_opening)
        if r is None:
            continue
        null_rhos.append(r)
        if r >= observed:
            ge += 1

    if not null_rhos:
        null_mean = null_median = excess = p = None
        passed = False
    else:
        null_mean = sum(null_rhos) / len(null_rhos)
        null_median = statistics.median(null_rhos)
        excess = observed - null_median
        p = (ge + 1) / (len(null_rhos) + 1)
        passed = (
            observed >= MIN_BOUNDARY_RHO
            and excess >= MIN_RHO_EXCESS_OVER_FLOOR_NULL
            and p <= MAX_FLOOR_NULL_P
        )

    return {
        "n": len(rows),
        "observed_rho": observed,
        "null_mean_rho": null_mean,
        "null_median_rho": null_median,
        "rho_excess_over_null_median": excess,
        "permutation_p": p,
        "pass": passed,
    }


def evaluate(g, occ: int, H: int):
    states = g["states"]
    first_seen = g["first_seen"]
    adj = g["adj"]
    crev = g["crev"]
    members = g["members"]

    eligible_nodes = {n for n in states if first_seen.get(n, LEVELS) <= LEVELS - H}
    eligible_comps = {c for c, ns in members.items() if ns and all(n in eligible_nodes for n in ns)}

    @lru_cache(maxsize=None)
    def omega(c):
        seen = set(members[c])
        front = set(members[c])
        for _ in range(H):
            nxt = set()
            for u in front:
                nxt.update(adj.get(u, ()))
            nxt -= seen
            if not nxt:
                break
            seen.update(nxt)
            front = nxt
        return len(seen)

    @lru_cache(maxsize=None)
    def exact_anc(c, lag):
        front = {c}
        for _ in range(lag):
            nxt = set()
            for x in front:
                nxt.update(crev.get(x, ()))
            front = nxt
            if not front:
                break
        return frozenset(front)

    def pressure(c):
        aa = [a for a in exact_anc(c, LAG) if a in eligible_comps]
        if not aa:
            return None
        oc = omega(c)
        vals = [math.log2(omega(a) / oc) for a in aa if omega(a) > 0 and oc > 0]
        return sum(vals) / len(vals) if vals else None

    obs = {G.BOUNDARY: [], G.CYCLE: [], G.PRODUCT: []}
    for (c, kind), targets in g["fiber_targets"].items():
        if c not in eligible_comps:
            continue
        ts = [t for t in targets if t in eligible_comps]
        if not ts:
            continue
        p = pressure(c)
        if p is None:
            continue
        oc = omega(c)
        if oc <= 0:
            continue
        source_bits = math.log2(oc)
        target_bits = [math.log2(omega(t)) for t in ts if omega(t) > 0]
        if not target_bits:
            continue
        mean_target_bits = sum(target_bits) / len(target_bits)
        opening = mean_target_bits - source_bits
        floor = -source_bits
        obs[kind].append({
            "source": c,
            "pressure_bits": p,
            "opening_bits": opening,
            "opening_floor_bits": floor,
            "headroom_bits": opening - floor,
            "source_future_bits": source_bits,
            "mean_target_future_bits": mean_target_bits,
            "n_targets": len(ts),
        })

    summary = {}
    for kind, rows in obs.items():
        openings = [r["opening_bits"] for r in rows]
        pressures = [r["pressure_bits"] for r in rows]
        summary[kind] = {
            "n": len(rows),
            "mean_opening_bits": sum(openings) / len(openings) if openings else None,
            "median_opening_bits": statistics.median(openings) if openings else None,
            "raw_rho_pressure_opening": spearman(pressures, openings) if len(rows) >= 4 else None,
        }

    specificity = {}
    for idx, kind in enumerate((G.CYCLE, G.PRODUCT), start=1):
        b = [r["opening_bits"] for r in obs[G.BOUNDARY]]
        c = [r["opening_bits"] for r in obs[kind]]
        if len(b) >= MIN_KIND_N and len(c) >= MIN_KIND_N:
            diff = sum(b) / len(b) - sum(c) / len(c)
            p = perm_mean_diff_p(b, c, diff, 20272000 + occ * 100 + H * 10 + idx)
            passed = diff >= MIN_OPENING_ADVANTAGE_BITS and p is not None and p <= MAX_PAIRWISE_P
        else:
            diff = p = None
            passed = False
        specificity[kind] = {
            "mean_difference_bits": diff,
            "permutation_p": p,
            "pass": passed,
        }

    floor_null = {
        kind: floor_preserving_null(rows, 20273000 + occ * 100 + H * 10 + idx)
        for idx, (kind, rows) in enumerate(obs.items(), start=1)
    }

    return {
        "H": H,
        "eligible_nodes": len(eligible_nodes),
        "eligible_sccs": len(eligible_comps),
        "by_base_kind": summary,
        "closure_completion_specificity": specificity,
        "floor_preserving_null": floor_null,
    }


def main():
    result = {
        "schema": "ckk.external.fresh-seed-closure-plateau-floor-null.v2",
        "kernel_modified": False,
        "preregistered": {
            "fresh_occ": list(FRESH_OCC),
            "levels": LEVELS,
            "cap": CAP,
            "H": list(HORIZONS),
            "compression_lag": LAG,
            "closure_completion_specificity": {
                "H": list(SPECIFICITY_H),
                "min_opening_advantage_bits": MIN_OPENING_ADVANTAGE_BITS,
                "max_pairwise_p": MAX_PAIRWISE_P,
                "min_kind_n": MIN_KIND_N,
            },
            "plateau": {
                "H": list(PLATEAU_H),
                "max_range_bits": PLATEAU_MAX_RANGE_BITS,
                "min_mean_bits": PLATEAU_MIN_MEAN_BITS,
                "min_n_per_H": MIN_PLATEAU_N_PER_H,
            },
            "floor_corrected_coupling": {
                "H": list(COUPLING_H),
                "null": "keep each row's pressure and exact opening floor=-log2(Omega_source); permute only nonnegative headroom=log2(Omega_target)",
                "min_boundary_n": MIN_BOUNDARY_N_COUPLING,
                "min_boundary_rho": MIN_BOUNDARY_RHO,
                "min_rho_excess_over_null_median": MIN_RHO_EXCESS_OVER_FLOOR_NULL,
                "max_permutation_p": MAX_FLOOR_NULL_P,
            },
        },
        "contexts": {},
    }

    for occ in FRESH_OCC:
        g = build_graph(occ)
        hrs = {str(H): evaluate(g, occ, H) for H in HORIZONS}

        specificity_pass = all(
            all(hrs[str(H)]["closure_completion_specificity"][k]["pass"] for k in (G.CYCLE, G.PRODUCT))
            for H in SPECIFICITY_H
        )

        plateau_vals = [hrs[str(H)]["by_base_kind"][G.BOUNDARY]["mean_opening_bits"] for H in PLATEAU_H]
        plateau_ns = [hrs[str(H)]["by_base_kind"][G.BOUNDARY]["n"] for H in PLATEAU_H]
        plateau_finite = all(isinstance(v, (int, float)) and math.isfinite(v) for v in plateau_vals)
        plateau_range = max(plateau_vals) - min(plateau_vals) if plateau_finite else None
        plateau_mean = sum(plateau_vals) / len(plateau_vals) if plateau_finite else None
        plateau_pass = bool(
            plateau_finite
            and all(n >= MIN_PLATEAU_N_PER_H for n in plateau_ns)
            and plateau_range <= PLATEAU_MAX_RANGE_BITS
            and plateau_mean >= PLATEAU_MIN_MEAN_BITS
        )

        coupling_pass = all(
            hrs[str(H)]["floor_preserving_null"][G.BOUNDARY]["pass"]
            for H in COUPLING_H
        )

        result["contexts"][str(occ)] = {
            "generator": {
                "levels": LEVELS,
                "cap": CAP,
                "cap_hit": g["cap_hit"],
                "states": len(g["states"]),
                "derivation_events": g["derivations"],
                "edges": g["edges"],
                "sccs": g["sccs"],
            },
            "horizons": hrs,
            "closure_completion_specificity_pass": specificity_pass,
            "plateau": {
                "H": list(PLATEAU_H),
                "mean_opening_bits": plateau_vals,
                "n": plateau_ns,
                "range_bits": plateau_range,
                "mean_bits": plateau_mean,
                "pass": plateau_pass,
            },
            "floor_corrected_coupling_pass": coupling_pass,
        }

    contexts = result["contexts"].values()
    result["closure_completion_specificity_status"] = (
        "CONFIRMED" if all((not c["generator"]["cap_hit"]) and c["closure_completion_specificity_pass"] for c in contexts)
        else "NOT_CONFIRMED"
    )
    contexts = result["contexts"].values()
    result["boundary_opening_plateau_status"] = (
        "CONFIRMED" if all((not c["generator"]["cap_hit"]) and c["plateau"]["pass"] for c in contexts)
        else "NOT_CONFIRMED"
    )
    contexts = result["contexts"].values()
    result["floor_corrected_coupling_status"] = (
        "CONFIRMED" if all((not c["generator"]["cap_hit"]) and c["floor_corrected_coupling_pass"] for c in contexts)
        else "NOT_CONFIRMED"
    )
    result["status"] = "THREE_SEPARATE_PREREGISTERED_GATES_REPORTED_NO_POSTHOC_COMPOSITE"

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
