#!/usr/bin/env python3
"""Blind causal-approach dilation measurement over frozen CKK grammar.

This gate does NOT insert gravity, force, mass, spacetime, a metric, curvature,
or a physical distance law. It asks a narrower structural question:

For generated states that can reach an endogenous BOUNDARY, what fraction of
admissible generated transitions actually reduce shortest directed boundary
distance by the maximum possible one graph step?

For an edge s -> t, shortest-path distance obeys d(t) >= d(s)-1. Therefore:
  delta = d(s)-d(t) == 1  : inward / full one-step approach
  delta == 0              : lateral
  delta < 0               : outward

Define the descriptive combinatorial quantities
  A = inward / (inward + lateral + outward)
  lambda_branch = 1 / A
on transitions whose target also has defined boundary distance.

A=1 means every defined transition makes the full available one-step approach.
A<1 means generated lateral/outward alternatives make causal approach less than
one-for-one. lambda_branch is only a branch-stretch observable; it is NOT a
physical metric unless a later independent bridge establishes that meaning.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

import grammar as G  # noqa: E402
from expand import expand_structural_auditable  # noqa: E402

OUT = ROOT / "results" / "causal_approach_dilation_gate.json"
LEVELS = 4
CAP = 30000


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


def classify(rows):
    inward = lateral = outward = escape = 0
    signed = []
    for ds, dt in rows:
        if dt is None:
            escape += 1
            continue
        delta = ds - dt
        signed.append(delta)
        if delta == 1:
            inward += 1
        elif delta == 0:
            lateral += 1
        elif delta < 0:
            outward += 1
        else:
            raise AssertionError(f"shortest-distance edge decreased by >1: {ds=} {dt=}")

    defined = inward + lateral + outward
    total = defined + escape
    a = inward / defined if defined else None
    stretch = 1.0 / a if a not in (None, 0.0) else None
    mean_signed = sum(signed) / len(signed) if signed else None
    return {
        "total_projected_transitions": total,
        "distance_defined_transitions": defined,
        "inward_full_step": inward,
        "lateral_zero_step": lateral,
        "outward_negative_step": outward,
        "target_without_generated_boundary_path": escape,
        "approach_efficiency_A": a,
        "branch_stretch_lambda": stretch,
        "mean_signed_boundary_progress": mean_signed,
    }


def main():
    pool, derivations = expand_structural_auditable(levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}

    # Deduplicate repeated re-evaluation of the same derivation event across
    # expansion levels. Then project each n-ary event once per distinct input.
    unique_events = {}
    for d in derivations:
        if d.output not in states:
            continue
        unique_events[d.event_key()] = d

    projected_event_edges = set()
    unique_edges = set()
    first_seen = {s.structural_sig(): 0 for s in G.SEEDS if s.structural_sig() in states}
    for d in unique_events.values():
        first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)
        for inp in set(d.inputs):
            if inp in states and inp != d.output:
                projected_event_edges.add((d.event_key(), inp, d.output))
                unique_edges.add((inp, d.output))

    # Directed shortest distance to endogenous BOUNDARY.
    rev = defaultdict(set)
    for s, t in unique_edges:
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

    # Sources created on the final expansion level are excluded; their outgoing
    # alternatives are incompletely observed by construction.
    eligible_sources = {
        n for n in states
        if n in dist and dist[n] > 0 and first_seen.get(n, LEVELS) <= LEVELS - 1
    }

    unique_rows = []
    event_rows = []
    shell_unique = defaultdict(list)
    shell_event = defaultdict(list)

    for s, t in sorted(unique_edges):
        if s not in eligible_sources:
            continue
        row = (dist[s], dist.get(t))
        unique_rows.append(row)
        shell_unique[dist[s]].append(row)

    for _, s, t in sorted(projected_event_edges, key=repr):
        if s not in eligible_sources:
            continue
        row = (dist[s], dist.get(t))
        event_rows.append(row)
        shell_event[dist[s]].append(row)

    unique_summary = classify(unique_rows)
    event_summary = classify(event_rows)

    profile = {}
    for d in sorted(set(shell_unique) | set(shell_event)):
        profile[str(d)] = {
            "states": sum(1 for n in eligible_sources if dist[n] == d),
            "unique_successor_projection": classify(shell_unique.get(d, [])),
            "derivation_event_projection": classify(shell_event.get(d, [])),
        }

    # Gradient test: under the stated structural hypothesis, resistance is
    # stronger nearer BOUNDARY, so A should tend to increase with distance.
    shell_ds = []
    shell_as_unique = []
    shell_as_event = []
    for d in sorted(profile, key=int):
        du = profile[d]["unique_successor_projection"]["approach_efficiency_A"]
        de = profile[d]["derivation_event_projection"]["approach_efficiency_A"]
        if du is not None and de is not None:
            shell_ds.append(int(d))
            shell_as_unique.append(du)
            shell_as_event.append(de)

    rho_unique = spearman(shell_ds, shell_as_unique) if len(shell_ds) >= 3 else None
    rho_event = spearman(shell_ds, shell_as_event) if len(shell_ds) >= 3 else None

    raw_stretch = bool(
        unique_summary["approach_efficiency_A"] is not None
        and event_summary["approach_efficiency_A"] is not None
        and unique_summary["approach_efficiency_A"] < 1.0
        and event_summary["approach_efficiency_A"] < 1.0
    )
    proximity_gradient = bool(
        rho_unique is not None and rho_event is not None
        and rho_unique > 0 and rho_event > 0
    )

    if raw_stretch and proximity_gradient:
        status = "RAW_CAUSAL_APPROACH_STRETCH_WITH_BOUNDARY_PROXIMITY_GRADIENT"
    elif raw_stretch:
        status = "RAW_CAUSAL_APPROACH_STRETCH_NO_PROXIMITY_GRADIENT"
    else:
        status = "NO_RAW_CAUSAL_APPROACH_STRETCH"

    result = {
        "schema": "ckk.external.causal-approach-dilation.v1",
        "status": status,
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "states": len(states),
            "unique_derivation_events": len(unique_events),
            "projected_event_edges": len(projected_event_edges),
            "unique_structural_edges": len(unique_edges),
            "endogenous_boundary_states": len(boundaries),
            "eligible_nonfrontier_sources_reaching_boundary": len(eligible_sources),
        },
        "frozen_definitions": {
            "boundary": "CKK state with kind == BOUNDARY",
            "distance": "shortest directed structural-edge distance to any endogenous BOUNDARY",
            "inward": "edge with d(source)-d(target)==1",
            "lateral": "edge with d(source)-d(target)==0",
            "outward": "edge with d(source)-d(target)<0",
            "escape": "generated target has no path to any generated BOUNDARY in this finite graph",
            "approach_efficiency_A": "inward/(inward+lateral+outward) on distance-defined transitions",
            "branch_stretch_lambda": "1/A; descriptive combinatorial branch stretch only",
            "hypothesis_gradient": "if boundary proximity adds structural resistance, A should increase with distance from BOUNDARY",
        },
        "global": {
            "unique_successor_projection": unique_summary,
            "derivation_event_projection": event_summary,
        },
        "distance_profile": profile,
        "tests": {
            "raw_A_below_one_in_both_projections": raw_stretch,
            "spearman_distance_vs_A_unique": rho_unique,
            "spearman_distance_vs_A_event": rho_event,
            "positive_boundary_proximity_gradient_in_both": proximity_gradient,
        },
        "interpretation": (
            "Blind structural measurement only. A<1 means not every generated transition "
            "makes the full available one-step approach to BOUNDARY; lambda=1/A records "
            "that combinatorial path branching. A positive distance-vs-A gradient would be "
            "consistent with stronger approach resistance nearer BOUNDARY. Neither result "
            "by itself establishes a physical metric, gravity, mass coupling, or spacetime."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
