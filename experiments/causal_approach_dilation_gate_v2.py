#!/usr/bin/env python3
"""Blind boundary-approach measurement, v2.

No gravity, mass, metric, curvature, spacetime, force, or target physical law is
inserted. The observable is purely generated-graph structure.

For a generated structural state s, d(s) is shortest directed-edge distance to
an endogenous BOUNDARY. For every generated edge s->t, d(s)-d(t) cannot exceed
one when d(t) is known.

  +1 : full one-step inward approach
   0 : lateral
  <0 : outward
  ?  : target has no observed path to BOUNDARY at this finite generation depth

The primary question is whether boundary-adjacent states (d=1) have approach
fraction < 1. Because unresolved targets can acquire a boundary path at deeper
generation, report conservative bounds:

  A_lower = inward / all outgoing transitions
  A_upper = inward / resolved outgoing transitions

Thus A_upper < 1 is a depth-robust observation that some resolved generated
alternatives fail to make the full available approach step. lambda=1/A is
reported only as a combinatorial branch-stretch interval, not as a metric.
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

LEVELS = 6
CAP = 30000
OUT = ROOT / "results" / "causal_approach_dilation_gate_v2.json"


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
    inward = lateral = outward = unresolved = 0
    signed = []
    for ds, dt in rows:
        if dt is None:
            unresolved += 1
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

    resolved = inward + lateral + outward
    total = resolved + unresolved
    a_lower = inward / total if total else None
    a_upper = inward / resolved if resolved else None
    lam_lower = 1.0 / a_upper if a_upper not in (None, 0.0) else None
    lam_upper = 1.0 / a_lower if a_lower not in (None, 0.0) else None
    return {
        "total_transitions": total,
        "resolved_transitions": resolved,
        "inward_full_step": inward,
        "lateral_zero_step": lateral,
        "outward_negative_step": outward,
        "unresolved_target": unresolved,
        "approach_efficiency_A_lower": a_lower,
        "approach_efficiency_A_upper": a_upper,
        "branch_stretch_lambda_lower": lam_lower,
        "branch_stretch_lambda_upper": lam_upper,
        "mean_signed_progress_resolved": (sum(signed) / len(signed)) if signed else None,
    }


def main():
    pool, derivations = expand_structural_auditable(levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}

    # IMPORTANT v2 fix: first_seen must be computed from ALL derivations before
    # repeated event re-evaluations are deduplicated. Derivations are produced
    # level by level, but use min explicitly to make the invariant obvious.
    first_seen = {s.structural_sig(): 0 for s in G.SEEDS if s.structural_sig() in states}
    for d in derivations:
        if d.output in states:
            first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)

    # Keep the earliest occurrence of each operator application for auditing.
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

    # Exclude only states first created on the final expansion level. Every
    # retained source has had at least one subsequent full operator sweep.
    eligible = {
        n for n in states
        if n in dist and dist[n] > 0 and first_seen.get(n, LEVELS) <= LEVELS - 1
    }

    unique_by_source = defaultdict(list)
    event_by_source = defaultdict(list)
    for s, t in unique_edges:
        if s in eligible:
            unique_by_source[s].append((dist[s], dist.get(t)))
    for _, s, t in event_edges:
        if s in eligible:
            event_by_source[s].append((dist[s], dist.get(t)))

    shell_unique = defaultdict(list)
    shell_event = defaultdict(list)
    for s, rows in unique_by_source.items():
        shell_unique[dist[s]].extend(rows)
    for s, rows in event_by_source.items():
        shell_event[dist[s]].extend(rows)

    profile = {}
    shell_state_means = {}
    all_shells = sorted(set(shell_unique) | set(shell_event))
    for d in all_shells:
        us = classify(shell_unique.get(d, []))
        es = classify(shell_event.get(d, []))
        state_lowers = []
        state_uppers = []
        for s in eligible:
            if dist[s] != d or not unique_by_source.get(s):
                continue
            cs = classify(unique_by_source[s])
            if cs["approach_efficiency_A_lower"] is not None:
                state_lowers.append(cs["approach_efficiency_A_lower"])
            if cs["approach_efficiency_A_upper"] is not None:
                state_uppers.append(cs["approach_efficiency_A_upper"])
        state_mean_lower = sum(state_lowers) / len(state_lowers) if state_lowers else None
        state_mean_upper = sum(state_uppers) / len(state_uppers) if state_uppers else None
        shell_state_means[str(d)] = {
            "A_lower_mean_per_state": state_mean_lower,
            "A_upper_mean_per_state": state_mean_upper,
            "states_with_outgoing": len(state_lowers),
        }
        profile[str(d)] = {
            "states": sum(1 for s in eligible if dist[s] == d),
            "unique_successor_projection": us,
            "derivation_event_projection": es,
            "state_normalized_unique_projection": shell_state_means[str(d)],
        }

    global_unique = classify([r for rows in unique_by_source.values() for r in rows])
    global_event = classify([r for rows in event_by_source.values() for r in rows])

    ds = []
    aus = []
    aes = []
    for d in all_shells:
        u = profile[str(d)]["unique_successor_projection"]["approach_efficiency_A_upper"]
        e = profile[str(d)]["derivation_event_projection"]["approach_efficiency_A_upper"]
        if u is not None and e is not None:
            ds.append(d)
            aus.append(u)
            aes.append(e)

    rho_unique = spearman(ds, aus) if len(ds) >= 3 else None
    rho_event = spearman(ds, aes) if len(ds) >= 3 else None

    near = profile.get("1")
    near_u = near["unique_successor_projection"] if near else None
    near_e = near["derivation_event_projection"] if near else None
    near_resistance_unique = bool(near_u and near_u["approach_efficiency_A_upper"] is not None and near_u["approach_efficiency_A_upper"] < 1.0)
    near_resistance_event = bool(near_e and near_e["approach_efficiency_A_upper"] is not None and near_e["approach_efficiency_A_upper"] < 1.0)
    near_resistance = near_resistance_unique and near_resistance_event

    far_d = max(all_shells) if all_shells else None
    far_u = profile[str(far_d)]["unique_successor_projection"] if far_d is not None else None
    far_e = profile[str(far_d)]["derivation_event_projection"] if far_d is not None else None
    separated_from_far = bool(
        near_u and near_e and far_u and far_e and far_d != 1
        and near_u["approach_efficiency_A_upper"] is not None
        and near_e["approach_efficiency_A_upper"] is not None
        and far_u["approach_efficiency_A_lower"] is not None
        and far_e["approach_efficiency_A_lower"] is not None
        and near_u["approach_efficiency_A_upper"] < far_u["approach_efficiency_A_lower"]
        and near_e["approach_efficiency_A_upper"] < far_e["approach_efficiency_A_lower"]
    )

    if near_resistance and separated_from_far:
        status = "BOUNDARY_ADJACENT_APPROACH_RESISTANCE_WITH_SEPARATED_FAR_CONTROL"
    elif near_resistance:
        status = "BOUNDARY_ADJACENT_APPROACH_RESISTANCE_OBSERVED"
    elif near:
        status = "NO_RESOLVED_BOUNDARY_ADJACENT_APPROACH_RESISTANCE"
    else:
        status = "BOUNDARY_ADJACENT_SHELL_NOT_RESOLVED"

    result = {
        "schema": "ckk.external.causal-approach-dilation.v2",
        "status": status,
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "states": len(states),
            "raw_derivation_records": len(derivations),
            "unique_derivation_events": len(unique_events),
            "unique_structural_edges": len(unique_edges),
            "endogenous_boundary_states": len(boundaries),
            "eligible_nonfrontier_sources_reaching_boundary": len(eligible),
            "distance_shells": all_shells,
        },
        "definitions": {
            "distance": "shortest directed generated structural-edge distance to endogenous BOUNDARY",
            "A_lower": "inward / all observed outgoing transitions",
            "A_upper": "inward / transitions whose target boundary-distance is resolved",
            "lambda_interval": "[1/A_upper, 1/A_lower]; combinatorial only",
            "boundary_resistance_criterion": "at d=1, A_upper<1 in both unique-edge and derivation-event projections",
            "separated_far_control": "d=1 A_upper < farthest-shell A_lower in both projections",
        },
        "global": {
            "unique_successor_projection": global_unique,
            "derivation_event_projection": global_event,
        },
        "distance_profile": profile,
        "tests": {
            "boundary_adjacent_shell_present": near is not None,
            "boundary_adjacent_resistance_unique": near_resistance_unique,
            "boundary_adjacent_resistance_event": near_resistance_event,
            "boundary_adjacent_resistance_both": near_resistance,
            "farthest_shell": far_d,
            "near_interval_separated_from_far_interval_both": separated_from_far,
            "spearman_distance_vs_A_upper_unique": rho_unique,
            "spearman_distance_vs_A_upper_event": rho_event,
        },
        "interpretation": (
            "Blind generated-graph measurement. A_upper<1 at d=1 establishes only that "
            "resolved structural alternatives adjacent to endogenous BOUNDARY do not all "
            "make the full one-step approach. A separated farther-shell control strengthens "
            "boundary specificity. lambda is a combinatorial stretch interval, not a physical "
            "metric; this result alone does not derive gravity, mass coupling, or spacetime."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
