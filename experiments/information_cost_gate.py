#!/usr/bin/env python3
"""Blind irreversible information-cost gate over frozen CKK grammar.

Purpose
-------
Test a narrow structural bridge proposed after the causal-approach dilation gate:
when a generated transition commits toward an endogenous BOUNDARY, does it erase
more equal-budget future distinguishability than non-approach alternatives?

Nothing thermodynamic or gravitational is inserted. In particular this file does
NOT use temperature, k_B, Landauer's constant, energy, heat, mass, force, metric,
curvature, spacetime, pi, a quantum rule, or a target physical law.

Definitions frozen before the run
---------------------------------
1. Generate the provenance-free structural graph with the existing CKK grammar.
2. d(x) = shortest directed generated-edge distance from x to any endogenous
   BOUNDARY.
3. A transition s->t is a Landauer *candidate* only if it is structurally
   irreversible in the generated graph: t cannot return to s. Equivalently,
   s and t lie in different strongly connected components (SCCs).
4. Equal total transition budget H is enforced:

      Omega_H(s)     = distinct structural states reachable from s in <= H
                       generated transitions, including s.
      Omega_{H-1}(t) = distinct structural states reachable from t in <= H-1
                       generated transitions, including t.

   Since s->t is one transition, Omega_{H-1}(t) is a subset of Omega_H(s).
5. Structural potential loss for the chosen transition is

      delta_I_bits(s->t) = log2( |Omega_H(s)| / |Omega_{H-1}(t)| ).

   This is a combinatorial distinguishability loss, NOT thermodynamic entropy.
6. Boundary-approach classes use the already tested distance observable:
      inward  : d(s)-d(t) == 1
      lateral : d(s)-d(t) == 0
      outward : d(s)-d(t) < 0

Primary frozen hypotheses
-------------------------
H1: At d=1, irreversible inward transitions have larger mean delta_I than
    irreversible lateral transitions, in both unique-edge and derivation-event
    projections.
H2: Mean irreversible inward delta_I decreases with boundary distance in both
    projections (negative Spearman rho over >=3 resolved shells).
H3: At source-state level, larger inward-vs-lateral information-cost excess is
    associated with smaller approach efficiency A (negative Spearman rho), when
    enough states contain both classes.

A positive result is only a structural information-cost result. A later bridge
would still be required before invoking Landauer heat, quantum measurement, or
emergent geometry physically.
"""
from __future__ import annotations

import json
import math
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
HORIZON = 2
OUT = ROOT / "results" / "information_cost_gate.json"


def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and xs[order[j]] == xs[order[i]]:
            j += 1
        r = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = r
        i = j
    return ranks


def pearson(x, y):
    if len(x) < 3:
        return None
    mx, my = sum(x) / len(x), sum(y) / len(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx == 0 or vy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy)


def spearman(x, y):
    return pearson(rankdata(x), rankdata(y))


def tarjan_scc(nodes, adj):
    """Return node -> SCC id for the generated directed graph."""
    sys.setrecursionlimit(max(10000, len(nodes) * 4))
    index = 0
    stack = []
    on_stack = set()
    idx = {}
    low = {}
    comp = {}
    comp_id = 0

    def strongconnect(v):
        nonlocal index, comp_id
        idx[v] = index
        low[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj.get(v, ()):
            if w not in idx:
                strongconnect(w)
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
            strongconnect(v)
    return comp, comp_id


def summary(values):
    if not values:
        return {
            "n": 0,
            "mean_delta_I_bits": None,
            "median_delta_I_bits": None,
            "mean_erased_fraction": None,
            "min_delta_I_bits": None,
            "max_delta_I_bits": None,
        }
    erased = [1.0 - 2.0 ** (-v) for v in values]
    return {
        "n": len(values),
        "mean_delta_I_bits": sum(values) / len(values),
        "median_delta_I_bits": statistics.median(values),
        "mean_erased_fraction": sum(erased) / len(erased),
        "min_delta_I_bits": min(values),
        "max_delta_I_bits": max(values),
    }


def main():
    pool, derivations = expand_structural_auditable(levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}

    # First appearance from ALL records, before event deduplication.
    first_seen = {s.structural_sig(): 0 for s in G.SEEDS if s.structural_sig() in states}
    for d in derivations:
        if d.output in states:
            first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)

    # Keep earliest instance of each derivation event.
    unique_events = {}
    for d in derivations:
        if d.output in states:
            unique_events.setdefault(d.event_key(), d)

    unique_edges = set()
    event_edges = set()
    for d in unique_events.values():
        for inp in set(d.inputs):
            if inp in states and inp != d.output:
                unique_edges.add((inp, d.output))
                event_edges.add((d.event_key(), inp, d.output))

    adj = defaultdict(set)
    rev = defaultdict(set)
    for s, t in unique_edges:
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

    # Require a full H-step future budget for every source, removing the finite
    # frontier as a trivial cause of low future diversity.
    eligible = {
        s for s in states
        if s in dist
        and dist[s] > 0
        and first_seen.get(s, LEVELS) <= LEVELS - HORIZON
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
    def edge_cost(s, t):
        before = potential(s, HORIZON)
        after = potential(t, HORIZON - 1)
        # Structural inclusion must hold because s->t is a generated edge and
        # the total transition budget is equalized.
        if not after.issubset(before):
            raise AssertionError("equal-budget future inclusion violated")
        ratio = len(before) / len(after)
        if ratio < 1.0:
            raise AssertionError("negative potential loss under equal budget")
        return math.log2(ratio), len(before), len(after)

    def edge_class(s, t):
        dt = dist.get(t)
        if dt is None:
            return "unresolved"
        delta = dist[s] - dt
        if delta == 1:
            return "inward"
        if delta == 0:
            return "lateral"
        if delta < 0:
            return "outward"
        raise AssertionError("shortest boundary distance decreased by >1 on one edge")

    unique_records = []
    for s, t in unique_edges:
        if s not in eligible:
            continue
        cls = edge_class(s, t)
        irreversible = comp[s] != comp[t]
        cost = None
        before_n = after_n = None
        if irreversible:
            cost, before_n, after_n = edge_cost(s, t)
        unique_records.append({
            "s": s,
            "t": t,
            "shell": dist[s],
            "class": cls,
            "irreversible": irreversible,
            "delta_I_bits": cost,
            "omega_before": before_n,
            "omega_after": after_n,
        })

    # Event projection reweights the same structural edge by distinct operator
    # applications without changing its structural information cost.
    event_records = []
    for event_key, s, t in event_edges:
        if s not in eligible:
            continue
        cls = edge_class(s, t)
        irreversible = comp[s] != comp[t]
        cost = None
        if irreversible:
            cost, _, _ = edge_cost(s, t)
        event_records.append({
            "event": event_key,
            "s": s,
            "t": t,
            "shell": dist[s],
            "class": cls,
            "irreversible": irreversible,
            "delta_I_bits": cost,
        })

    shells = sorted({r["shell"] for r in unique_records})

    def projection_profile(records):
        profile = {}
        for d in shells:
            sd = [r for r in records if r["shell"] == d]
            classes = {}
            for cls in ("inward", "lateral", "outward", "unresolved"):
                vals = [
                    r["delta_I_bits"] for r in sd
                    if r["class"] == cls and r["irreversible"] and r["delta_I_bits"] is not None
                ]
                classes[cls] = summary(vals)
                classes[cls]["all_transitions"] = sum(1 for r in sd if r["class"] == cls)
                classes[cls]["irreversible_transitions"] = len(vals)
            classes["reversible_all_classes"] = sum(1 for r in sd if not r["irreversible"])
            profile[str(d)] = classes
        return profile

    unique_profile = projection_profile(unique_records)
    event_profile = projection_profile(event_records)

    def mean_inward_series(profile):
        ds, ys = [], []
        for d in shells:
            v = profile[str(d)]["inward"]["mean_delta_I_bits"]
            if v is not None:
                ds.append(d)
                ys.append(v)
        return ds, ys

    du, yu = mean_inward_series(unique_profile)
    de, ye = mean_inward_series(event_profile)
    rho_cost_distance_unique = spearman(du, yu) if len(du) >= 3 else None
    rho_cost_distance_event = spearman(de, ye) if len(de) >= 3 else None

    near_u = unique_profile.get("1", {})
    near_e = event_profile.get("1", {})

    def mean_cost(profile, cls):
        return profile.get(cls, {}).get("mean_delta_I_bits")

    near_u_in = mean_cost(near_u, "inward")
    near_u_lat = mean_cost(near_u, "lateral")
    near_e_in = mean_cost(near_e, "inward")
    near_e_lat = mean_cost(near_e, "lateral")

    h1_unique = bool(near_u_in is not None and near_u_lat is not None and near_u_in > near_u_lat)
    h1_event = bool(near_e_in is not None and near_e_lat is not None and near_e_in > near_e_lat)
    h1_both = h1_unique and h1_event

    h2_unique = bool(rho_cost_distance_unique is not None and rho_cost_distance_unique < 0)
    h2_event = bool(rho_cost_distance_event is not None and rho_cost_distance_event < 0)
    h2_both = h2_unique and h2_event

    # Source-normalized H3 on unique structural successors. A uses all RESOLVED
    # outgoing transitions, while information-cost excess uses only irreversible
    # inward/lateral transitions from the same source.
    source_pairs = []
    by_source = defaultdict(list)
    for r in unique_records:
        by_source[r["s"]].append(r)
    for s, rows in by_source.items():
        resolved = [r for r in rows if r["class"] != "unresolved"]
        if not resolved:
            continue
        inward_count = sum(1 for r in resolved if r["class"] == "inward")
        A = inward_count / len(resolved)
        inward_costs = [r["delta_I_bits"] for r in rows if r["irreversible"] and r["class"] == "inward" and r["delta_I_bits"] is not None]
        lateral_costs = [r["delta_I_bits"] for r in rows if r["irreversible"] and r["class"] == "lateral" and r["delta_I_bits"] is not None]
        if inward_costs and lateral_costs:
            excess = (sum(inward_costs) / len(inward_costs)) - (sum(lateral_costs) / len(lateral_costs))
            source_pairs.append((A, excess, dist[s]))

    rho_A_vs_cost_excess = spearman(
        [p[0] for p in source_pairs], [p[1] for p in source_pairs]
    ) if len(source_pairs) >= 3 else None
    h3 = bool(rho_A_vs_cost_excess is not None and rho_A_vs_cost_excess < 0)

    if h1_both and h2_both and h3:
        status = "IRREVERSIBLE_INFORMATION_COST_COUPLES_TO_BOUNDARY_APPROACH"
    elif h1_both and h2_both:
        status = "BOUNDARY_APPROACH_INFORMATION_COST_GRADIENT_OBSERVED"
    elif h1_both:
        status = "BOUNDARY_ADJACENT_INFORMATION_COST_EXCESS_OBSERVED"
    else:
        status = "NO_BOUNDARY_ADJACENT_INFORMATION_COST_EXCESS"

    def global_counts(records):
        return {
            "transitions": len(records),
            "irreversible_transitions": sum(1 for r in records if r["irreversible"]),
            "reversible_transitions": sum(1 for r in records if not r["irreversible"]),
            "resolved_transitions": sum(1 for r in records if r["class"] != "unresolved"),
            "unresolved_transitions": sum(1 for r in records if r["class"] == "unresolved"),
        }

    result = {
        "schema": "ckk.external.information-cost-gate.v1",
        "status": status,
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "equal_total_transition_budget_H": HORIZON,
            "states": len(states),
            "raw_derivation_records": len(derivations),
            "unique_derivation_events": len(unique_events),
            "unique_structural_edges": len(unique_edges),
            "endogenous_boundary_states": len(boundaries),
            "eligible_sources_with_full_H_budget": len(eligible),
            "distance_shells": shells,
            "strongly_connected_components": n_components,
        },
        "frozen_definitions": {
            "irreversible": "source and target lie in different SCCs; generated target cannot return to generated source",
            "omega_before": "distinct structural states reachable from source in <=H transitions, including source",
            "omega_after": "distinct structural states reachable from target in <=H-1 transitions, including target",
            "delta_I_bits": "log2(omega_before/omega_after)",
            "erased_fraction": "1 - 2^(-delta_I_bits); structural potential fraction only",
            "inward": "d(source)-d(target)==1",
            "lateral": "d(source)-d(target)==0",
            "outward": "d(source)-d(target)<0",
            "H1": "at d=1 mean irreversible delta_I(inward) > mean irreversible delta_I(lateral), both projections",
            "H2": "mean irreversible inward delta_I decreases with distance, negative Spearman rho, both projections",
            "H3": "source-level approach efficiency A anticorrelates with inward-minus-lateral irreversible information-cost excess",
        },
        "global": {
            "unique_successor_projection": global_counts(unique_records),
            "derivation_event_projection": global_counts(event_records),
        },
        "distance_profile": {
            str(d): {
                "unique_successor_projection": unique_profile[str(d)],
                "derivation_event_projection": event_profile[str(d)],
            }
            for d in shells
        },
        "tests": {
            "H1_boundary_adjacent_inward_cost_exceeds_lateral_unique": h1_unique,
            "H1_boundary_adjacent_inward_cost_exceeds_lateral_event": h1_event,
            "H1_both": h1_both,
            "H2_spearman_distance_vs_mean_inward_cost_unique": rho_cost_distance_unique,
            "H2_spearman_distance_vs_mean_inward_cost_event": rho_cost_distance_event,
            "H2_negative_gradient_both": h2_both,
            "H3_source_states_with_both_irreversible_classes": len(source_pairs),
            "H3_spearman_A_vs_information_cost_excess": rho_A_vs_cost_excess,
            "H3_negative_association": h3,
        },
        "interpretation": (
            "Blind structural test only. A positive result means irreversible generated "
            "boundary-approach choices remove more equal-budget structural future "
            "distinguishability than lateral alternatives and/or show a proximity gradient. "
            "delta_I is not yet thermodynamic entropy. Landauer heat requires an independent "
            "physical identification of these irreversible structural commits with logically "
            "irreversible information erasure. No quantum or gravitational claim follows "
            "from this gate alone."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
