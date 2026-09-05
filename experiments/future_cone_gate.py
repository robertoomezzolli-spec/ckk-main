#!/usr/bin/env python3
"""Blind complete-future-cone accessibility gate over frozen CKK grammar.

Kernel is imported read-only. No physics, pi, gravity, spacetime, Lorentz,
mass, energy, metric, curvature, or external time variable is supplied.
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

OUT = ROOT / "results" / "future_cone_gate.json"
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


def future_cone_size(start, adj):
    """Distinct transitive successors. Confluence is counted once."""
    seen = set()
    stack = list(adj.get(start, ()))
    while stack:
        v = stack.pop()
        if v == start or v in seen:
            continue
        seen.add(v)
        stack.extend(adj.get(v, ()))
    return len(seen)


def main():
    pool, derivations = expand_structural_auditable(levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}

    adj = defaultdict(set)
    rev = defaultdict(set)
    first_seen = {s.structural_sig(): 0 for s in G.SEEDS if s.structural_sig() in states}
    for d in derivations:
        if d.output not in states:
            continue
        first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)
        for inp in d.inputs:
            if inp in states and inp != d.output:
                adj[inp].add(d.output)
                rev[d.output].add(inp)

    boundaries = {k for k, s in states.items() if s.kind == G.BOUNDARY}

    dist = {}
    q = deque(boundaries)
    for b in boundaries:
        dist[b] = 0
    while q:
        v = q.popleft()
        for u in rev.get(v, ()):
            nd = dist[v] + 1
            if u not in dist or nd < dist[u]:
                dist[u] = nd
                q.append(u)

    # Same frontier guard as the already-audited V2 gate.
    eligible = {
        n for n in states
        if n in dist and first_seen.get(n, LEVELS) <= LEVELS - 1
    }

    # Complete remaining possibility space, not local out-degree.
    cone = {n: future_cone_size(n, adj) for n in eligible}

    approach = []
    other = []
    for s in eligible:
        for t in adj.get(s, ()):
            if t not in eligible:
                continue
            rec = (s, t)
            if dist[t] == dist[s] - 1:
                approach.append(rec)
            else:
                other.append(rec)

    def nonincrease(rows):
        return sum(1 for s, t in rows if cone[t] <= cone[s]) / len(rows) if rows else None

    def strict_decrease(rows):
        return sum(1 for s, t in rows if cone[t] < cone[s]) / len(rows) if rows else None

    app_noninc = nonincrease(approach)
    app_strict = strict_decrease(approach)
    other_noninc = nonincrease(other)
    contrast = (
        app_noninc - other_noninc
        if app_noninc is not None and other_noninc is not None else None
    )

    nodes = sorted(eligible)
    dvals = [dist[n] for n in nodes]
    fvals = [cone[n] for n in nodes]
    rho = spearman(dvals, fvals) if nodes else None

    # Descriptive distance bins are frozen before status assignment.
    profile = {}
    for d in sorted(set(dvals)):
        vals = [cone[n] for n in nodes if dist[n] == d]
        profile[str(d)] = {
            "states": len(vals),
            "mean_future_cone": sum(vals) / len(vals),
            "min_future_cone": min(vals),
            "max_future_cone": max(vals),
        }

    enough = len(eligible) >= 20 and len(boundaries) > 0 and len(approach) >= 20
    # Boundary-specific signal must beat the control, not merely narrow generically.
    discriminates = bool(contrast is not None and contrast >= 0.10)
    directional = bool(rho is not None and rho > 0)
    ratchet = bool(enough and app_noninc is not None and app_noninc >= 0.75 and app_strict is not None and app_strict >= 0.25)

    if ratchet and discriminates and directional:
        status = "BOUNDARY_SPECIFIC_FUTURE_CONE_RATCHET"
    elif enough:
        status = "FUTURE_CONE_PRESENT_NO_BOUNDARY_SPECIFIC_RATCHET"
    else:
        status = "INSUFFICIENT_GENERATED_PROVENANCE"

    result = {
        "schema": "ckk.external.future-cone-gate.v2",
        "status": status,
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "states": len(states),
            "derivation_events": len(derivations),
            "endogenous_boundary_states": len(boundaries),
            "eligible_nonfrontier_states_reaching_boundary": len(eligible),
        },
        "frozen_definitions": {
            "boundary": "CKK state with kind == BOUNDARY; never finite-run terminal",
            "future_cone": "F(v)=count of all distinct generated states transitively reachable from v; confluence counted once",
            "approach": "directed edge lowering shortest graph distance to endogenous BOUNDARY by one",
            "frontier_guard": "states first generated in final expansion level are excluded",
            "operational_distance": "only monotone inverse intuition; no metric or physical law inserted",
        },
        "tests": {
            "approach_edges": len(approach),
            "other_edges": len(other),
            "approach_future_cone_nonincrease_fraction": app_noninc,
            "approach_future_cone_strict_decrease_fraction": app_strict,
            "other_future_cone_nonincrease_fraction": other_noninc,
            "approach_vs_other_contrast": contrast,
            "spearman_boundary_distance_vs_future_cone": rho,
            "boundary_ratchet": ratchet,
            "approach_specific_discrimination": discriminates,
            "directional_distance_relation": directional,
            "min_future_cone_eligible": min(fvals) if fvals else None,
            "max_future_cone_eligible": max(fvals) if fvals else None,
        },
        "distance_profile": profile,
        "interpretation": "Structural blind CKK test only. A positive result identifies a boundary-specific narrowing of the complete generated future possibility cone; it does not by itself derive geometry, gravity, or any physical force law.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
