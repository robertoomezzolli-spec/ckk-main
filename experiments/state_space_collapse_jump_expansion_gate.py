#!/usr/bin/env python3
"""Blind state-space collapse -> jump -> re-expansion gate.

This gate tests a structural hypothesis only:

    larger accessible future space
      -> compression while approaching an endogenous BOUNDARY
      -> discrete boundary jump
      -> re-expansion into a larger accessible future space.

It deliberately does NOT test Landauer heat, energy, temperature, gravity,
spacetime, quantum measurement, or a target physical law. The earlier logical
many-to-one Landauer bridge remains a separate falsified hypothesis.

Frozen definitions
------------------
Structural graph: existing provenance-free expand_structural_auditable graph.
d(x): shortest directed generated-edge distance to endogenous BOUNDARY.
For an equal restart horizon H,

    Omega_H(x) = number of distinct structural states reachable from x in <=H
                 generated edges, including x.

A matched collapse/jump chain is p -> s -> b where
    d(p)=2, d(s)=1, d(b)=0 and b is an endogenous BOUNDARY.
A lateral control from the same s is s -> l with d(l)=1.
All compared nodes must have been created early enough to receive the same H
remaining generator sweeps in the finite graph.

Frozen tests, repeated at H=2 and H=3
-------------------------------------
C1 PRE-JUMP COLLAPSE:
    source-normalized mean log2(Omega_H(s)/Omega_H(p)) < 0;
    median <0; >50% sources negative; sign-flip permutation p<=.01.

C2 POST-JUMP RE-EXPANSION:
    source-normalized mean log2(Omega_H(b)/Omega_H(s)) > 0;
    median >0; >50% sources positive; sign-flip permutation p<=.01.

C3 JUMP-SPECIFIC RE-EXPANSION:
    from the same d=1 source s, mean jump expansion exceeds mean lateral
    change: [log2 Omega(b)/Omega(s)] - [log2 Omega(l)/Omega(s)] > 0;
    median >0; >50% sources positive; sign-flip permutation p<=.01.

C4 V-SHAPE:
    among sources for which both a d=2 predecessor and boundary target are
    available, >50% satisfy mean Omega(p) > Omega(s) < mean Omega(b).

A pass identifies only a structural collapse-jump-re-expansion pattern.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

import grammar as G  # noqa: E402
from expand import expand_structural_auditable  # noqa: E402

LEVELS = 6
CAP = 30000
HORIZONS = (2, 3)
PERMUTATIONS = 4000
SEED = 20260905
OUT = ROOT / "results" / "state_space_collapse_jump_expansion_gate.json"


def sign_flip_p(values, observed, direction, seed):
    """Fixed-seed one-sample sign-flip null around zero."""
    if not values:
        return None
    rng = random.Random(seed)
    null = []
    vals = list(values)
    for _ in range(PERMUTATIONS):
        sample = [v if rng.random() < 0.5 else -v for v in vals]
        null.append(sum(sample) / len(sample))
    if direction == "negative":
        extreme = sum(1 for x in null if x <= observed)
    else:
        extreme = sum(1 for x in null if x >= observed)
    return {
        "permutations": PERMUTATIONS,
        "seed": seed,
        "direction": direction,
        "one_sided_p": (1 + extreme) / (PERMUTATIONS + 1),
        "null_mean": sum(null) / len(null),
        "null_min": min(null),
        "null_max": max(null),
    }


def summarize_signed(values, desired, seed):
    if not values:
        return {
            "n": 0,
            "mean_log2_ratio": None,
            "median_log2_ratio": None,
            "fraction_desired_sign": None,
            "permutation_null": None,
            "pass": False,
        }
    mean = sum(values) / len(values)
    med = statistics.median(values)
    if desired == "negative":
        frac = sum(1 for x in values if x < 0) / len(values)
        null = sign_flip_p(values, mean, "negative", seed)
        passed = mean < 0 and med < 0 and frac > 0.5 and null["one_sided_p"] <= 0.01
    else:
        frac = sum(1 for x in values if x > 0) / len(values)
        null = sign_flip_p(values, mean, "positive", seed)
        passed = mean > 0 and med > 0 and frac > 0.5 and null["one_sided_p"] <= 0.01
    return {
        "n": len(values),
        "mean_log2_ratio": mean,
        "median_log2_ratio": med,
        "fraction_desired_sign": frac,
        "permutation_null": null,
        "pass": passed,
    }


def main():
    pool, derivations = expand_structural_auditable(levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}

    first_seen = {s.structural_sig(): 0 for s in G.SEEDS if s.structural_sig() in states}
    for d in derivations:
        if d.output in states:
            first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)

    unique_events = {}
    for d in derivations:
        if d.output in states:
            unique_events.setdefault(d.event_key(), d)

    edges = set()
    for d in unique_events.values():
        for inp in set(d.inputs):
            if inp in states and inp != d.output:
                edges.add((inp, d.output))

    adj = defaultdict(set)
    rev = defaultdict(set)
    for s, t in edges:
        adj[s].add(t)
        rev[t].add(s)

    boundaries = {k for k, s in states.items() if s.kind == G.BOUNDARY}
    dist = {b: 0 for b in boundaries}
    q = deque(boundaries)
    while q:
        v = q.popleft()
        for u in rev.get(v, ()):
            nd = dist[v] + 1
            if u not in dist or nd < dist[u]:
                dist[u] = nd
                q.append(u)

    results = {}
    all_pass = True

    for H in HORIZONS:
        eligible = {
            n for n in states
            if first_seen.get(n, LEVELS) <= LEVELS - H
        }

        @lru_cache(maxsize=None)
        def omega(node):
            seen = {node}
            frontier = {node}
            for _ in range(H):
                nxt = set()
                for u in frontier:
                    nxt.update(adj.get(u, ()))
                nxt -= seen
                if not nxt:
                    break
                seen.update(nxt)
                frontier = nxt
            return len(seen)

        source_records = []
        for s in sorted(states, key=repr):
            if s not in eligible or dist.get(s) != 1:
                continue
            preds = [p for p in rev.get(s, ()) if p in eligible and dist.get(p) == 2]
            jumps = [b for b in adj.get(s, ()) if b in eligible and b in boundaries]
            laterals = [l for l in adj.get(s, ()) if l in eligible and dist.get(l) == 1]
            if not preds or not jumps:
                continue

            os = omega(s)
            pre_logs = [math.log2(os / omega(p)) for p in preds]
            post_logs = [math.log2(omega(b) / os) for b in jumps]
            lat_logs = [math.log2(omega(l) / os) for l in laterals]

            pre = sum(pre_logs) / len(pre_logs)
            post = sum(post_logs) / len(post_logs)
            lateral = (sum(lat_logs) / len(lat_logs)) if lat_logs else None
            jump_minus_lateral = (post - lateral) if lateral is not None else None

            mean_pred_omega = sum(omega(p) for p in preds) / len(preds)
            mean_jump_omega = sum(omega(b) for b in jumps) / len(jumps)
            v_shape = mean_pred_omega > os and mean_jump_omega > os

            source_records.append({
                "source": repr(s),
                "omega_source": os,
                "n_d2_predecessors": len(preds),
                "n_boundary_targets": len(jumps),
                "n_lateral_targets": len(laterals),
                "mean_d2_predecessor_omega": mean_pred_omega,
                "mean_boundary_target_omega": mean_jump_omega,
                "mean_pre_jump_log2_ratio": pre,
                "mean_post_jump_log2_ratio": post,
                "mean_lateral_log2_ratio": lateral,
                "jump_minus_lateral_log2_ratio": jump_minus_lateral,
                "v_shape": v_shape,
            })

        pre_values = [r["mean_pre_jump_log2_ratio"] for r in source_records]
        post_values = [r["mean_post_jump_log2_ratio"] for r in source_records]
        jl_values = [r["jump_minus_lateral_log2_ratio"] for r in source_records if r["jump_minus_lateral_log2_ratio"] is not None]

        c1 = summarize_signed(pre_values, "negative", SEED + H)
        c2 = summarize_signed(post_values, "positive", SEED + 100 + H)
        c3 = summarize_signed(jl_values, "positive", SEED + 200 + H)

        v_n = len(source_records)
        v_frac = sum(1 for r in source_records if r["v_shape"]) / v_n if v_n else None
        c4_pass = bool(v_frac is not None and v_frac > 0.5)

        # Descriptive shell profile only; pass/fail is source-matched above.
        shell_profile = {}
        for d in (0, 1, 2, 3):
            vals = [omega(n) for n in eligible if dist.get(n) == d]
            if vals:
                shell_profile[str(d)] = {
                    "states": len(vals),
                    "mean_omega": sum(vals) / len(vals),
                    "median_omega": statistics.median(vals),
                    "min_omega": min(vals),
                    "max_omega": max(vals),
                }

        hp = c1["pass"] and c2["pass"] and c3["pass"] and c4_pass
        all_pass = all_pass and hp
        results[str(H)] = {
            "eligible_nodes": len(eligible),
            "matched_d2_to_d1_to_boundary_sources": len(source_records),
            "C1_pre_jump_collapse": c1,
            "C2_post_jump_re_expansion": c2,
            "C3_jump_specific_vs_lateral": c3,
            "C4_v_shape": {
                "sources": v_n,
                "fraction_v_shape": v_frac,
                "pass": c4_pass,
            },
            "descriptive_shell_profile": shell_profile,
            "pass": hp,
        }

    result = {
        "schema": "ckk.external.state-space-collapse-jump-expansion.v1",
        "status": (
            "SOURCE_MATCHED_COLLAPSE_JUMP_REEXPANSION_H2_H3"
            if all_pass else
            "COLLAPSE_JUMP_REEXPANSION_NOT_FULLY_SUPPORTED"
        ),
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "states": len(states),
            "unique_structural_edges": len(edges),
            "endogenous_boundary_states": len(boundaries),
        },
        "frozen_definitions": {
            "omega_H": "distinct structural states reachable in <=H generated edges including the start state",
            "collapse_chain": "p->s with d(p)=2,d(s)=1",
            "jump": "s->b with d(s)=1 and b an endogenous BOUNDARY",
            "lateral_control": "s->l from same d=1 source with d(l)=1",
            "C1": "source-normalized pre-jump log2 Omega(s)/Omega(p) is significantly negative",
            "C2": "source-normalized post-jump log2 Omega(b)/Omega(s) is significantly positive",
            "C3": "same-source jump re-expansion exceeds lateral state-space change",
            "C4": "majority of matched sources satisfy mean Omega(p)>Omega(s)<mean Omega(b)",
        },
        "horizons": results,
        "pass_rule": "C1 && C2 && C3 && C4 at H=2 and H=3",
        "interpretation": (
            "A pass would identify only a structural compression-before-jump and re-expansion-after-jump pattern. "
            "It would not by itself establish energy pressure, Landauer heat, physical hysteresis, quantum measurement, "
            "gravity, spacetime, or a neutron-star mechanism. A failure would falsify this specific state-space V-shape "
            "in the current frozen grammar rather than the broader theory."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
