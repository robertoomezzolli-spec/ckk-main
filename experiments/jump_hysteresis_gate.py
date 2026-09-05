#!/usr/bin/env python3
"""Blind jump / hysteresis-candidate gate over the frozen CKK grammar.

This gate tests the structural claim that boundary approach behaves like a
metastable regime with lateral alternatives followed by a discrete irreversible
commit, rather than a smooth one-for-one approach.

Nothing thermodynamic or gravitational is inserted. No temperature, k_B,
Landauer constant, energy, heat, mass, force, metric, curvature, spacetime,
quantum rule, or target physical law is used.

Frozen definitions
------------------
Structural graph: provenance-free expand_structural_auditable graph.
d(x): shortest directed distance to any endogenous BOUNDARY.
Jump: edge s->t with d(s)=1 and t.kind == BOUNDARY.
Lateral-near: edge s->t with d(s)=1 and d(t)=1.
Irreversible: s and t lie in different SCCs, so t cannot return to s in the
generated graph.

Equal-budget structural potential loss for horizon H:
  Omega_H(s)     = distinct states reachable from s in <=H transitions,
  Omega_{H-1}(t) = distinct states reachable from t in <=H-1 transitions,
  delta_I        = log2(|Omega_H(s)| / |Omega_{H-1}(t)|).
This is combinatorial distinguishability loss only.

Frozen tests, repeated at H=2 and H=3:
J1 cost barrier: within the SAME d=1 source, irreversible Jump delta_I exceeds
   irreversible lateral delta_I on average; median paired excess >0, >50% of
   paired sources positive, fixed-seed within-source label permutation p<=.01.
J2 metastable branching: among d=1 sources with both classes, lateral choices
   outnumber Jump choices for >50% of sources and in aggregate.
J3 return asymmetry: within the SAME d=1 source, Jump irreversibility fraction
   exceeds lateral irreversibility fraction on average, with fixed-seed
   within-source label permutation p<=.01.

A pass is a structural jump/hysteresis candidate only. It does not identify
Landauer heat, physical hysteresis, quantum measurement, gravity, or spacetime.
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
from expand import expand_auditable, expand_structural_auditable  # noqa: E402

LEVELS = 6
CAP = 30000
HORIZONS = (2, 3)
PERMUTATIONS = 1000
SEED = 20260905
OUT = ROOT / "results" / "jump_hysteresis_gate.json"


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


def permutation_p_mean_excess(groups, observed, seed):
    """Within-source label permutation preserving each source's class counts."""
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
        "null_mean_of_means": sum(null) / len(null),
        "null_max_mean": max(null),
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

    def cls(s, t):
        if dist.get(s) != 1:
            return None
        if t in boundaries:
            return "jump"
        if dist.get(t) == 1:
            return "lateral"
        return None

    by_source_all = defaultdict(lambda: {"jump": [], "lateral": []})
    for s, t in edges:
        c = cls(s, t)
        if c:
            by_source_all[s][c].append(t)

    # Provenance memory audit only: how many historical signatures inhabit the
    # same structural BOUNDARY state. This is descriptive because sig() is
    # explicitly provenance-bearing by design.
    hist_pool, _ = expand_auditable(levels=LEVELS, cap=CAP)
    hist_by_struct = defaultdict(set)
    for obj in hist_pool.values():
        hist_by_struct[obj.structural_sig()].add(obj.sig())
    jump_targets = {t for s, t in edges if cls(s, t) == "jump"}
    provenance_mult = [len(hist_by_struct.get(t, ())) for t in jump_targets]
    provenance_audit = {
        "jump_structural_targets": len(jump_targets),
        "targets_with_multiple_historical_signatures": sum(1 for n in provenance_mult if n > 1),
        "fraction_with_multiple_historical_signatures": (
            sum(1 for n in provenance_mult if n > 1) / len(provenance_mult)
            if provenance_mult else None
        ),
        "median_historical_signatures_per_structural_target": (
            statistics.median(provenance_mult) if provenance_mult else None
        ),
        "max_historical_signatures_per_structural_target": max(provenance_mult) if provenance_mult else None,
        "audit_note": "descriptive only; historical sig() intentionally carries provenance",
    }

    results = {}
    all_pass = True

    for H in HORIZONS:
        eligible = {
            s for s in states
            if dist.get(s) == 1 and first_seen.get(s, LEVELS) <= LEVELS - H
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

        @lru_cache(maxsize=None)
        def cost(s, t):
            before = potential(s, H)
            after = potential(t, H - 1)
            if not after.issubset(before):
                raise AssertionError("equal-budget future inclusion violated")
            return math.log2(len(before) / len(after))

        paired_cost_diffs = []
        cost_groups = []
        branching_sources = []
        paired_irrev_diffs = []
        irrev_groups = []

        for s in sorted(eligible, key=repr):
            jumps = by_source_all[s]["jump"]
            laterals = by_source_all[s]["lateral"]
            if not jumps or not laterals:
                continue

            branching_sources.append((len(jumps), len(laterals)))

            jump_costs = [cost(s, t) for t in jumps if comp[s] != comp[t]]
            lat_costs = [cost(s, t) for t in laterals if comp[s] != comp[t]]
            if jump_costs and lat_costs:
                d = sum(jump_costs) / len(jump_costs) - sum(lat_costs) / len(lat_costs)
                paired_cost_diffs.append(d)
                cost_groups.append((jump_costs, lat_costs))

            jump_ir = [1.0 if comp[s] != comp[t] else 0.0 for t in jumps]
            lat_ir = [1.0 if comp[s] != comp[t] else 0.0 for t in laterals]
            if jump_ir and lat_ir:
                d = sum(jump_ir) / len(jump_ir) - sum(lat_ir) / len(lat_ir)
                paired_irrev_diffs.append(d)
                irrev_groups.append((jump_ir, lat_ir))

        mean_cost_excess = sum(paired_cost_diffs) / len(paired_cost_diffs) if paired_cost_diffs else None
        med_cost_excess = statistics.median(paired_cost_diffs) if paired_cost_diffs else None
        frac_cost_pos = (
            sum(1 for x in paired_cost_diffs if x > 0) / len(paired_cost_diffs)
            if paired_cost_diffs else None
        )
        cost_null = (
            permutation_p_mean_excess(cost_groups, mean_cost_excess, SEED + H)
            if paired_cost_diffs else None
        )
        j1 = bool(
            mean_cost_excess is not None and mean_cost_excess > 0
            and med_cost_excess is not None and med_cost_excess > 0
            and frac_cost_pos is not None and frac_cost_pos > 0.5
            and cost_null["one_sided_p"] <= 0.01
        )

        frac_lateral_dominant = (
            sum(1 for j, l in branching_sources if l > j) / len(branching_sources)
            if branching_sources else None
        )
        total_jumps = sum(j for j, _ in branching_sources)
        total_lateral = sum(l for _, l in branching_sources)
        j2 = bool(
            frac_lateral_dominant is not None and frac_lateral_dominant > 0.5
            and total_lateral > total_jumps
        )

        mean_irrev_excess = sum(paired_irrev_diffs) / len(paired_irrev_diffs) if paired_irrev_diffs else None
        med_irrev_excess = statistics.median(paired_irrev_diffs) if paired_irrev_diffs else None
        frac_irrev_pos = (
            sum(1 for x in paired_irrev_diffs if x > 0) / len(paired_irrev_diffs)
            if paired_irrev_diffs else None
        )
        irrev_null = (
            permutation_p_mean_excess(irrev_groups, mean_irrev_excess, SEED + 100 + H)
            if paired_irrev_diffs else None
        )
        j3 = bool(
            mean_irrev_excess is not None and mean_irrev_excess > 0
            and frac_irrev_pos is not None and frac_irrev_pos > 0.5
            and irrev_null["one_sided_p"] <= 0.01
        )

        hp = j1 and j2 and j3
        all_pass = all_pass and hp
        results[str(H)] = {
            "eligible_boundary_adjacent_sources": len(eligible),
            "sources_with_both_jump_and_lateral": len(branching_sources),
            "J1_cost_barrier": {
                "paired_sources": len(paired_cost_diffs),
                "mean_jump_minus_lateral_bits": mean_cost_excess,
                "median_jump_minus_lateral_bits": med_cost_excess,
                "fraction_sources_positive": frac_cost_pos,
                "permutation_null": cost_null,
                "pass": j1,
            },
            "J2_metastable_branching": {
                "paired_sources": len(branching_sources),
                "fraction_sources_lateral_count_exceeds_jump_count": frac_lateral_dominant,
                "aggregate_jump_edges": total_jumps,
                "aggregate_lateral_edges": total_lateral,
                "aggregate_lateral_to_jump_ratio": (total_lateral / total_jumps) if total_jumps else None,
                "pass": j2,
            },
            "J3_return_asymmetry": {
                "paired_sources": len(paired_irrev_diffs),
                "mean_jump_minus_lateral_irreversibility_fraction": mean_irrev_excess,
                "median_jump_minus_lateral_irreversibility_fraction": med_irrev_excess,
                "fraction_sources_positive": frac_irrev_pos,
                "permutation_null": irrev_null,
                "pass": j3,
            },
            "pass": hp,
        }

    status = (
        "SOURCE_MATCHED_METASTABLE_JUMP_WITH_RETURN_ASYMMETRY_H2_H3"
        if all_pass else
        "JUMP_HYSTERESIS_CANDIDATE_NOT_FULLY_SUPPORTED"
    )

    result = {
        "schema": "ckk.external.jump-hysteresis-gate.v1",
        "status": status,
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "states": len(states),
            "unique_structural_edges": len(edges),
            "endogenous_boundary_states": len(boundaries),
            "strongly_connected_components": n_components,
        },
        "frozen_definitions": {
            "jump": "d(source)=1 and target.kind==BOUNDARY",
            "lateral_near": "d(source)=1 and d(target)=1",
            "irreversible": "source and target are in different SCCs",
            "delta_I_bits": "log2(|Omega_H(source)|/|Omega_{H-1}(target)|) under equal transition budget",
            "J1": "same-source irreversible Jump cost exceeds lateral cost, H=2 and H=3, paired + permutation",
            "J2": "lateral alternatives dominate Jump alternatives before commit",
            "J3": "same-source Jump irreversibility fraction exceeds lateral irreversibility fraction, paired + permutation",
        },
        "horizons": results,
        "provenance_memory_audit": provenance_audit,
        "pass_rule": "J1 && J2 && J3 at both H=2 and H=3",
        "interpretation": (
            "A pass identifies a structural metastable-jump / hysteresis candidate: boundary-adjacent states "
            "prefer many lateral alternatives, while the discrete boundary commit is more costly in equal-budget "
            "future distinguishability and more return-asymmetric than lateral alternatives from the same source. "
            "This is not yet thermodynamic hysteresis or Landauer heat; the provenance audit is descriptive because "
            "historical sig() intentionally stores provenance."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
