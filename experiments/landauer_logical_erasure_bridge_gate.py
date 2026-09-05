#!/usr/bin/env python3
"""Blind logical-erasure eligibility bridge for the frozen CKK structural graph.

Purpose
-------
Test whether the already-observed boundary Jump has the logical shape required
before a Landauer interpretation is even admissible: a many-to-one map that
loses source identity in the post-state, combined with return asymmetry.

No temperature, k_B, energy, heat, mass, gravity, force, metric, curvature,
spacetime, quantum rule, or target physical law is inserted into the gate.
The Landauer expression is reported only conditionally *after* structural tests.

Frozen structural definitions
-----------------------------
- Generate the provenance-free graph using expand_structural_auditable.
- d(x): shortest directed generated-edge distance from x to endogenous BOUNDARY.
- Near source: d(source)==1 and source was first seen early enough to have a
  subsequent full operator sweep (first_seen <= LEVELS-1).
- Jump edge: near source -> BOUNDARY target.
- Lateral edge: near source -> target with d(target)==1.
- Source ambiguity of a target t:
      H_src(t) = log2(number of DISTINCT eligible d=1 structural predecessors)
  This is the source identity that cannot be reconstructed from t's structural
  state alone under a uniform unique-source prior. H_src>0 means many-to-one.
- Irreversible edge: source and target are in different SCCs of the generated
  directed graph, so target cannot return to source in the observed graph.

Frozen tests
------------
L1 source-matched ambiguity:
   For each near source with both Jump and lateral targets, mean H_src(Jump)
   minus mean H_src(lateral) must have mean>0, median>0, >50% positive sources,
   and a fixed-seed within-source label-permutation p<=.01.
L2 aggregate noninjectivity:
   Fraction of distinct Jump targets with H_src>0 and aggregate predecessor-to-
   target compression ratio must both exceed lateral controls.
L3 irreversible noninjectivity, source matched:
   For each near source with both classes, fraction of outgoing edges whose
   target is many-to-one AND whose edge is irreversible must be larger for Jump
   than lateral on average, >50% positive sources, permutation p<=.01.

Conditional Landauer quantity (NOT a test)
-------------------------------------------
If L1-L3 pass, report for Jump targets
    q_star = Q_min/(k_B T) = ln(2) * H_src
which is the idealized isothermal erasure floor *if* the structural source loss
is physically instantiated as logically irreversible erasure. No physical heat
claim follows from this gate alone.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

import grammar as G  # noqa: E402
from expand import expand_structural_auditable  # noqa: E402

LEVELS = 6
CAP = 30000
PERMUTATIONS = 2000
SEED = 20260905
OUT = ROOT / "results" / "landauer_logical_erasure_bridge_gate.json"


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
    return comp, comp_id


def permutation_p(groups, observed, seed):
    """Within-source label permutation preserving values and class counts."""
    rng = random.Random(seed)
    null = []
    for _ in range(PERMUTATIONS):
        diffs = []
        for left, right in groups:
            vals = list(left) + list(right)
            rng.shuffle(vals)
            nl = len(left)
            a, b = vals[:nl], vals[nl:]
            if a and b:
                diffs.append(sum(a) / len(a) - sum(b) / len(b))
        null.append(sum(diffs) / len(diffs) if diffs else 0.0)
    p = (1 + sum(1 for x in null if x >= observed)) / (PERMUTATIONS + 1)
    return {
        "permutations": PERMUTATIONS,
        "seed": seed,
        "one_sided_p": p,
        "null_mean": sum(null) / len(null),
        "null_max": max(null),
    }


def paired_summary(diffs, groups, seed):
    if not diffs:
        return {
            "paired_sources": 0,
            "mean_excess": None,
            "median_excess": None,
            "fraction_positive": None,
            "permutation_null": None,
            "pass": False,
        }
    mean = sum(diffs) / len(diffs)
    med = statistics.median(diffs)
    frac = sum(1 for x in diffs if x > 0) / len(diffs)
    null = permutation_p(groups, mean, seed)
    passed = mean > 0 and med > 0 and frac > 0.5 and null["one_sided_p"] <= 0.01
    return {
        "paired_sources": len(diffs),
        "mean_excess": mean,
        "median_excess": med,
        "fraction_positive": frac,
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

    comp, n_components = tarjan_scc(states.keys(), adj)

    eligible_near = {
        s for s in states
        if dist.get(s) == 1 and first_seen.get(s, LEVELS) <= LEVELS - 1
    }

    def edge_class(s, t):
        if s not in eligible_near:
            return None
        if t in boundaries:
            return "jump"
        if dist.get(t) == 1:
            return "lateral"
        return None

    # Target source ambiguity is computed from ALL eligible d=1 structural
    # predecessors, independent of whether the target is later called jump or lateral.
    near_predecessors = defaultdict(set)
    for s, t in edges:
        if s in eligible_near:
            near_predecessors[t].add(s)

    def ambiguity_bits(t):
        n = len(near_predecessors.get(t, ()))
        return math.log2(n) if n > 0 else 0.0

    by_source = defaultdict(lambda: {"jump": [], "lateral": []})
    jump_targets = set()
    lateral_targets = set()
    jump_edges = []
    lateral_edges = []
    for s, t in edges:
        c = edge_class(s, t)
        if c is None:
            continue
        by_source[s][c].append(t)
        if c == "jump":
            jump_targets.add(t)
            jump_edges.append((s, t))
        else:
            lateral_targets.add(t)
            lateral_edges.append((s, t))

    # L1: source-matched target source ambiguity.
    l1_diffs = []
    l1_groups = []
    for s in sorted(eligible_near, key=repr):
        js = by_source[s]["jump"]
        ls = by_source[s]["lateral"]
        if not js or not ls:
            continue
        ja = [ambiguity_bits(t) for t in js]
        la = [ambiguity_bits(t) for t in ls]
        l1_diffs.append(sum(ja) / len(ja) - sum(la) / len(la))
        l1_groups.append((ja, la))
    l1 = paired_summary(l1_diffs, l1_groups, SEED + 1)

    # L2: target-level noninjectivity and compression ratio.
    def target_stats(targets):
        counts = [len(near_predecessors.get(t, ())) for t in targets]
        amb = [math.log2(n) for n in counts if n > 0]
        multi = [n for n in counts if n >= 2]
        total_sources = sum(counts)
        return {
            "distinct_targets": len(targets),
            "distinct_predecessor_incidence": total_sources,
            "many_to_one_targets": len(multi),
            "many_to_one_fraction": len(multi) / len(counts) if counts else None,
            "predecessor_to_target_compression_ratio": total_sources / len(counts) if counts else None,
            "mean_source_ambiguity_bits": sum(amb) / len(amb) if amb else None,
            "median_source_ambiguity_bits": statistics.median(amb) if amb else None,
            "max_source_ambiguity_bits": max(amb) if amb else None,
        }

    jump_target_stats = target_stats(jump_targets)
    lateral_target_stats = target_stats(lateral_targets)
    l2 = bool(
        jump_target_stats["many_to_one_fraction"] is not None
        and lateral_target_stats["many_to_one_fraction"] is not None
        and jump_target_stats["predecessor_to_target_compression_ratio"] is not None
        and lateral_target_stats["predecessor_to_target_compression_ratio"] is not None
        and jump_target_stats["many_to_one_fraction"] > lateral_target_stats["many_to_one_fraction"]
        and jump_target_stats["predecessor_to_target_compression_ratio"] > lateral_target_stats["predecessor_to_target_compression_ratio"]
    )

    # L3: source-matched fraction of outgoing class edges that are BOTH
    # many-to-one at target and return-asymmetric (different SCC).
    l3_diffs = []
    l3_groups = []
    for s in sorted(eligible_near, key=repr):
        js = by_source[s]["jump"]
        ls = by_source[s]["lateral"]
        if not js or not ls:
            continue
        jv = [1.0 if ambiguity_bits(t) > 0 and comp[s] != comp[t] else 0.0 for t in js]
        lv = [1.0 if ambiguity_bits(t) > 0 and comp[s] != comp[t] else 0.0 for t in ls]
        l3_diffs.append(sum(jv) / len(jv) - sum(lv) / len(lv))
        l3_groups.append((jv, lv))
    l3 = paired_summary(l3_diffs, l3_groups, SEED + 2)

    passed = l1["pass"] and l2 and l3["pass"]

    # Conditional Landauer floor for target source ambiguity only. This is not
    # evidence and does not enter pass/fail.
    jump_ambiguities = [ambiguity_bits(t) for t in jump_targets]
    lateral_ambiguities = [ambiguity_bits(t) for t in lateral_targets]
    mean_jump_H = sum(jump_ambiguities) / len(jump_ambiguities) if jump_ambiguities else None
    median_jump_H = statistics.median(jump_ambiguities) if jump_ambiguities else None
    conditional_landauer = {
        "formula": "Q_min/(k_B*T) = ln(2) * H_source_given_target_bits",
        "assumption": "only if structural source-identity loss is physically instantiated as logically irreversible erasure in an isothermal reset-like process",
        "mean_jump_H_bits": mean_jump_H,
        "median_jump_H_bits": median_jump_H,
        "mean_jump_Qmin_over_kBT": math.log(2) * mean_jump_H if mean_jump_H is not None else None,
        "median_jump_Qmin_over_kBT": math.log(2) * median_jump_H if median_jump_H is not None else None,
        "mean_lateral_H_bits": (sum(lateral_ambiguities) / len(lateral_ambiguities)) if lateral_ambiguities else None,
    }

    result = {
        "schema": "ckk.external.landauer-logical-erasure-bridge.v1",
        "status": (
            "BOUNDARY_JUMP_HAS_SOURCE_MATCHED_LOGICAL_ERASURE_SHAPE"
            if passed else
            "LOGICAL_ERASURE_BRIDGE_NOT_FULLY_SUPPORTED"
        ),
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "states": len(states),
            "unique_structural_edges": len(edges),
            "endogenous_boundary_states": len(boundaries),
            "eligible_boundary_adjacent_sources": len(eligible_near),
            "strongly_connected_components": n_components,
        },
        "frozen_definitions": {
            "source_ambiguity_bits": "log2(number of distinct eligible d=1 structural predecessors of target)",
            "many_to_one": "target has >=2 distinct eligible d=1 structural predecessors",
            "irreversible": "source and target lie in different SCCs",
            "L1": "same-source mean target source-ambiguity is larger for Jump than lateral, paired + permutation",
            "L2": "Jump targets exceed lateral targets in many-to-one fraction and predecessor/target compression ratio",
            "L3": "same-source fraction of edges that are both many-to-one and irreversible is larger for Jump than lateral, paired + permutation",
        },
        "tests": {
            "L1_source_matched_ambiguity": l1,
            "L2_jump_more_noninjective_than_lateral": l2,
            "L3_source_matched_irreversible_noninjectivity": l3,
            "all_pass": passed,
        },
        "target_controls": {
            "jump": jump_target_stats,
            "lateral": lateral_target_stats,
        },
        "conditional_landauer_floor": conditional_landauer,
        "interpretation": (
            "Passing establishes only the logical shape required for a Landauer bridge: "
            "the generated boundary Jump is more source-noninjective than lateral controls, "
            "and that noninjectivity is coupled to return asymmetry from the same source. "
            "The reported Q_min/(k_B T) is conditional bookkeeping, not measured heat. "
            "A physical identification still requires a thermodynamic state variable, bath/temperature, "
            "and evidence that the lost structural source distinction is physically erased rather than exported elsewhere."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
