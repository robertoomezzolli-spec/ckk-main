#!/usr/bin/env python3
"""Paired-source robustness control for the blind information-cost result.

This file is post-result robustness, not a redefinition of the original gate.
It asks whether the inward-vs-lateral information-cost excess survives when both
classes are compared WITHIN THE SAME SOURCE STATE, eliminating source-level
branching heterogeneity / Simpson's-paradox concerns.

It also repeats the paired test at equal total transition budgets H=2 and H=3.
A fixed-seed within-source permutation null preserves every source's costs and
its inward/lateral counts while randomizing which costs receive which label.

No thermodynamics, Landauer constant, heat, energy, gravity, metric, curvature,
spacetime, quantum rule, or target physical law is inserted.
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
PERMUTATIONS = 1000
SEED = 20260905
OUT = ROOT / "results" / "information_cost_robustness_gate.json"


def tarjan_scc(nodes, adj):
    sys.setrecursionlimit(max(10000, len(nodes) * 4))
    index = 0
    stack = []
    on_stack = set()
    idx, low, comp = {}, {}, {}
    comp_id = 0

    def strong(v):
        nonlocal index, comp_id
        idx[v] = low[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in adj.get(v, ()):
            if w not in idx:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp[w] = comp_id
                if w == v:
                    break
            comp_id += 1

    for v in nodes:
        if v not in idx:
            strong(v)
    return comp


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

    comp = tarjan_scc(states.keys(), adj)

    def classify(s, t):
        if t not in dist:
            return "unresolved"
        delta = dist[s] - dist[t]
        if delta == 1:
            return "inward"
        if delta == 0:
            return "lateral"
        if delta < 0:
            return "outward"
        raise AssertionError("distance decreased by >1 on one generated edge")

    results = {}
    all_pass = True

    for H in HORIZONS:
        eligible = {
            s for s in states
            if s in dist and dist[s] > 0 and first_seen.get(s, LEVELS) <= LEVELS - H
        }

        @lru_cache(maxsize=None)
        def potential(node, horizon):
            seen = {node}
            frontier = {node}
            for _ in range(horizon):
                nxt = set()
                for u in frontier:
                    nxt.update(adj.get(u, ()))
                nxt -= seen
                if not nxt:
                    break
                seen.update(nxt)
                frontier = nxt
            return frozenset(seen)

        def cost(s, t):
            before = potential(s, H)
            after = potential(t, H - 1)
            if not after.issubset(before):
                raise AssertionError("equal-budget inclusion violated")
            return math.log2(len(before) / len(after))

        by_source = defaultdict(lambda: {"inward": [], "lateral": []})
        for s, t in edges:
            if s not in eligible or comp[s] == comp[t]:
                continue
            cls = classify(s, t)
            if cls in ("inward", "lateral"):
                by_source[s][cls].append(cost(s, t))

        # Primary paired control is boundary-adjacent d=1 only.
        paired = []
        raw_groups = []
        for s, groups in by_source.items():
            if dist[s] != 1 or not groups["inward"] or not groups["lateral"]:
                continue
            mean_in = sum(groups["inward"]) / len(groups["inward"])
            mean_lat = sum(groups["lateral"]) / len(groups["lateral"])
            paired.append(mean_in - mean_lat)
            raw_groups.append((tuple(groups["inward"]), tuple(groups["lateral"])))

        observed = sum(paired) / len(paired) if paired else None
        median_diff = statistics.median(paired) if paired else None
        positive_fraction = sum(1 for x in paired if x > 0) / len(paired) if paired else None

        rng = random.Random(SEED + H)
        null_means = []
        if raw_groups:
            for _ in range(PERMUTATIONS):
                diffs = []
                for inward_vals, lateral_vals in raw_groups:
                    pooled = list(inward_vals + lateral_vals)
                    rng.shuffle(pooled)
                    n_in = len(inward_vals)
                    pin = pooled[:n_in]
                    plat = pooled[n_in:]
                    diffs.append((sum(pin) / len(pin)) - (sum(plat) / len(plat)))
                null_means.append(sum(diffs) / len(diffs))

        p_one_sided = None
        if observed is not None and null_means:
            p_one_sided = (1 + sum(1 for x in null_means if x >= observed)) / (1 + len(null_means))

        passed = bool(
            observed is not None and observed > 0
            and median_diff is not None and median_diff > 0
            and positive_fraction is not None and positive_fraction > 0.5
            and p_one_sided is not None and p_one_sided <= 0.01
        )
        all_pass = all_pass and passed

        results[str(H)] = {
            "eligible_sources": len(eligible),
            "paired_boundary_adjacent_sources": len(paired),
            "mean_within_source_inward_minus_lateral_bits": observed,
            "median_within_source_inward_minus_lateral_bits": median_diff,
            "fraction_sources_with_positive_excess": positive_fraction,
            "permutation_null": {
                "seed": SEED + H,
                "permutations": PERMUTATIONS,
                "null_mean_of_means": (sum(null_means) / len(null_means)) if null_means else None,
                "null_max_mean": max(null_means) if null_means else None,
                "one_sided_p": p_one_sided,
            },
            "pass": passed,
        }

    status = (
        "PAIRED_SOURCE_INFORMATION_COST_EXCESS_ROBUST_H2_H3"
        if all_pass else
        "PAIRED_SOURCE_INFORMATION_COST_EXCESS_NOT_ROBUST_ACROSS_HORIZONS"
    )

    result = {
        "schema": "ckk.external.information-cost-robustness.v1",
        "status": status,
        "kernel_modified": False,
        "generator": {
            "levels": LEVELS,
            "cap": CAP,
            "states": len(states),
            "unique_structural_edges": len(edges),
            "endogenous_boundary_states": len(boundaries),
        },
        "frozen_control": (
            "within the same d=1 source state, compare irreversible inward vs lateral "
            "equal-budget future-potential loss; repeat H=2,H=3; fixed-seed within-source "
            "label permutation preserving each source's costs and class counts"
        ),
        "pass_rule": (
            "for each H: mean paired excess>0, median paired excess>0, >50% sources positive, "
            "one-sided permutation p<=0.01"
        ),
        "horizons": results,
        "interpretation": (
            "This is a source-matched structural robustness control only. Passing removes a "
            "major source-heterogeneity explanation for the inward information-cost excess, "
            "but still does not identify delta_I with thermodynamic entropy or establish "
            "Landauer heat, quantum measurement, gravity, or spacetime."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
