#!/usr/bin/env python3
"""Blind post-boundary re-expansion gate over the frozen structural CKK graph.

Hypothesis under test
---------------------
The previous gate found robust contraction on d=2 -> d=1 and further
contraction on d=1 -> BOUNDARY. This gate does not redefine that result. It
asks a new question: after entering the maximally compressed endogenous
BOUNDARY state, does accessible structural future space re-expand at a later
post-boundary step?

No thermodynamics, Landauer constant, energy, heat, gravity, spacetime,
quantum rule, or target physical law is inserted.

For equal restart horizon H:
    Omega_H(x) = number of distinct structural states reachable from x in <=H
                 generated edges, including x.

A source chain begins at a d=1 state s with at least one d=2 predecessor and
an outgoing edge s->b to an endogenous BOUNDARY b. For each b, exact shortest
post-boundary shells k=1..MAX_POST_STEPS are measured. A lateral control begins
at an outgoing d=1 state l from the SAME source s and is evaluated at the same
post-branch depth k.

Selection control
-----------------
Sources are deterministically split by SHA-256 of their structural signature.
The DISCOVERY half may select only the earliest k in {1,2,3} where the mean,
median, and majority sign of log2(Omega_shell/Omega_boundary) are positive.
The CONFIRMATION half then tests that frozen k. No confirmation statistic is
used to choose k.

Frozen confirmation tests, repeated at H=2 and H=3
--------------------------------------------------
R1 POST-BOUNDARY RE-EXPANSION:
    source-normalized log2(mean Omega_shell_k / Omega_boundary) > 0;
    mean>0, median>0, >50% positive, sign-flip p<=.01.

R2 NEW SPACE EXCEEDS PRE-BOUNDARY COMPRESSED SOURCE:
    source-normalized log2(mean Omega_shell_k / Omega_source) > 0 with the
    same thresholds.

R3 BOUNDARY-ROUTE SPECIFICITY:
    from the same source and at the same k, boundary-route expansion relative
    to Omega_source exceeds the lateral-route value; same thresholds.

R4 COMPLETE COMPRESSION->MINIMUM->RE-EXPANSION TRAJECTORY:
    >50% of confirmation sources satisfy
        mean Omega(d=2 predecessor) > Omega(s)
        mean Omega(boundary target) < Omega(s)
        mean Omega(post-boundary shell at selected k) > Omega(s).

A pass identifies only this structural trajectory in the current grammar.
"""
from __future__ import annotations

import hashlib
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

LEVELS = 7
CAP = 30000
HORIZONS = (2, 3)
MAX_POST_STEPS = 3
PERMUTATIONS = 4000
SEED = 20260905
OUT = ROOT / "results" / "post_boundary_reexpansion_gate.json"


def sign_flip_p(values, observed, direction, seed):
    if not values:
        return None
    rng = random.Random(seed)
    vals = list(values)
    extreme = 0
    null_sum = 0.0
    null_min = float("inf")
    null_max = float("-inf")
    for _ in range(PERMUTATIONS):
        x = sum(v if rng.random() < 0.5 else -v for v in vals) / len(vals)
        null_sum += x
        null_min = min(null_min, x)
        null_max = max(null_max, x)
        if direction == "positive" and x >= observed:
            extreme += 1
        elif direction == "negative" and x <= observed:
            extreme += 1
    return {
        "permutations": PERMUTATIONS,
        "seed": seed,
        "direction": direction,
        "one_sided_p": (1 + extreme) / (PERMUTATIONS + 1),
        "null_mean": null_sum / PERMUTATIONS,
        "null_min": null_min,
        "null_max": null_max,
    }


def summarize_positive(values, seed):
    if not values:
        return {
            "n": 0,
            "mean_log2_ratio": None,
            "median_log2_ratio": None,
            "fraction_positive": None,
            "permutation_null": None,
            "pass": False,
        }
    mean = sum(values) / len(values)
    med = statistics.median(values)
    frac = sum(1 for x in values if x > 0) / len(values)
    null = sign_flip_p(values, mean, "positive", seed)
    return {
        "n": len(values),
        "mean_log2_ratio": mean,
        "median_log2_ratio": med,
        "fraction_positive": frac,
        "permutation_null": null,
        "pass": bool(mean > 0 and med > 0 and frac > 0.5 and null["one_sided_p"] <= 0.01),
    }


def split_source(sig):
    h = hashlib.sha256(repr(sig).encode("utf-8")).digest()
    return "discovery" if (h[0] & 1) == 0 else "confirmation"


def main():
    pool, derivations = expand_structural_auditable(levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}
    cap_hit = len(states) >= CAP

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

    @lru_cache(maxsize=None)
    def shortest_shells(root, max_k):
        seen = {root}
        frontier = {root}
        out = []
        for _ in range(max_k):
            nxt = set()
            for u in frontier:
                nxt.update(adj.get(u, ()))
            nxt -= seen
            seen.update(nxt)
            out.append(frozenset(nxt))
            frontier = nxt
            if not frontier:
                while len(out) < max_k:
                    out.append(frozenset())
                break
        return tuple(out)

    results = {}
    overall_pass = not cap_hit

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

        records = []
        for s in sorted(states, key=repr):
            if s not in eligible or dist.get(s) != 1:
                continue
            preds = [p for p in rev.get(s, ()) if p in eligible and dist.get(p) == 2]
            bs = [b for b in adj.get(s, ()) if b in eligible and b in boundaries]
            ls = [l for l in adj.get(s, ()) if l in eligible and dist.get(l) == 1]
            if not preds or not bs or not ls:
                continue

            os = omega(s)
            rec = {
                "source": repr(s),
                "split": split_source(s),
                "omega_source": os,
                "mean_pred_omega": sum(omega(p) for p in preds) / len(preds),
                "mean_boundary_omega": sum(omega(b) for b in bs) / len(bs),
                "k": {},
            }

            for k in range(1, MAX_POST_STEPS + 1):
                b_to_b = []
                b_to_s = []
                b_shell_omegas = []
                for b in bs:
                    shell = [x for x in shortest_shells(b, MAX_POST_STEPS)[k - 1] if x in eligible]
                    if not shell:
                        continue
                    m = sum(omega(x) for x in shell) / len(shell)
                    b_shell_omegas.append(m)
                    b_to_b.append(math.log2(m / omega(b)))
                    b_to_s.append(math.log2(m / os))

                l_to_s = []
                for l in ls:
                    shell = [x for x in shortest_shells(l, MAX_POST_STEPS)[k - 1] if x in eligible]
                    if not shell:
                        continue
                    m = sum(omega(x) for x in shell) / len(shell)
                    l_to_s.append(math.log2(m / os))

                if b_to_b:
                    mean_b_to_b = sum(b_to_b) / len(b_to_b)
                    mean_b_to_s = sum(b_to_s) / len(b_to_s)
                    mean_b_shell = sum(b_shell_omegas) / len(b_shell_omegas)
                else:
                    mean_b_to_b = None
                    mean_b_to_s = None
                    mean_b_shell = None

                mean_l_to_s = (sum(l_to_s) / len(l_to_s)) if l_to_s else None
                specificity = (
                    mean_b_to_s - mean_l_to_s
                    if mean_b_to_s is not None and mean_l_to_s is not None
                    else None
                )
                rec["k"][str(k)] = {
                    "boundary_to_boundary_log2": mean_b_to_b,
                    "boundary_to_source_log2": mean_b_to_s,
                    "lateral_to_source_log2": mean_l_to_s,
                    "boundary_minus_lateral_log2": specificity,
                    "mean_boundary_shell_omega": mean_b_shell,
                }
            records.append(rec)

        discovery = [r for r in records if r["split"] == "discovery"]
        confirmation = [r for r in records if r["split"] == "confirmation"]

        discovery_scan = {}
        selected_k = None
        for k in range(1, MAX_POST_STEPS + 1):
            vals = [
                r["k"][str(k)]["boundary_to_boundary_log2"]
                for r in discovery
                if r["k"][str(k)]["boundary_to_boundary_log2"] is not None
            ]
            if vals:
                mean = sum(vals) / len(vals)
                med = statistics.median(vals)
                frac = sum(1 for x in vals if x > 0) / len(vals)
            else:
                mean = med = frac = None
            candidate = bool(mean is not None and mean > 0 and med > 0 and frac > 0.5)
            discovery_scan[str(k)] = {
                "n": len(vals),
                "mean_boundary_to_boundary_log2": mean,
                "median_boundary_to_boundary_log2": med,
                "fraction_positive": frac,
                "candidate": candidate,
            }
            if selected_k is None and candidate:
                selected_k = k

        if selected_k is None:
            results[str(H)] = {
                "eligible_nodes": len(eligible),
                "sources": len(records),
                "discovery_sources": len(discovery),
                "confirmation_sources": len(confirmation),
                "discovery_scan": discovery_scan,
                "selected_k": None,
                "status": "NO_POST_BOUNDARY_REEXPANSION_CANDIDATE_WITHIN_K",
                "pass": False,
            }
            overall_pass = False
            continue

        kkey = str(selected_k)
        r1_vals = [
            r["k"][kkey]["boundary_to_boundary_log2"] for r in confirmation
            if r["k"][kkey]["boundary_to_boundary_log2"] is not None
        ]
        r2_vals = [
            r["k"][kkey]["boundary_to_source_log2"] for r in confirmation
            if r["k"][kkey]["boundary_to_source_log2"] is not None
        ]
        r3_vals = [
            r["k"][kkey]["boundary_minus_lateral_log2"] for r in confirmation
            if r["k"][kkey]["boundary_minus_lateral_log2"] is not None
        ]

        r1 = summarize_positive(r1_vals, SEED + H)
        r2 = summarize_positive(r2_vals, SEED + 100 + H)
        r3 = summarize_positive(r3_vals, SEED + 200 + H)

        trajectory_flags = []
        for r in confirmation:
            mpost = r["k"][kkey]["mean_boundary_shell_omega"]
            if mpost is None:
                continue
            trajectory_flags.append(
                r["mean_pred_omega"] > r["omega_source"]
                and r["mean_boundary_omega"] < r["omega_source"]
                and mpost > r["omega_source"]
            )
        traj_frac = (
            sum(1 for x in trajectory_flags if x) / len(trajectory_flags)
            if trajectory_flags else None
        )
        r4_pass = bool(traj_frac is not None and traj_frac > 0.5)

        hp = r1["pass"] and r2["pass"] and r3["pass"] and r4_pass
        overall_pass = overall_pass and hp
        results[str(H)] = {
            "eligible_nodes": len(eligible),
            "sources": len(records),
            "discovery_sources": len(discovery),
            "confirmation_sources": len(confirmation),
            "discovery_scan": discovery_scan,
            "selected_k": selected_k,
            "R1_post_boundary_reexpansion": r1,
            "R2_exceeds_preboundary_source": r2,
            "R3_boundary_route_vs_lateral": r3,
            "R4_complete_trajectory": {
                "n": len(trajectory_flags),
                "fraction_complete_compression_minimum_reexpansion": traj_frac,
                "pass": r4_pass,
            },
            "pass": hp,
        }

    if cap_hit:
        status = "INCONCLUSIVE_STRUCTURAL_CAP_REACHED"
    elif overall_pass:
        status = "POST_BOUNDARY_REEXPANSION_CONFIRMED_H2_H3"
    else:
        status = "POST_BOUNDARY_REEXPANSION_NOT_FULLY_SUPPORTED"

    result = {
        "schema": "ckk.external.post-boundary-reexpansion.v1",
        "status": status,
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "cap_hit": cap_hit,
            "states": len(states),
            "unique_structural_edges": len(edges),
            "endogenous_boundary_states": len(boundaries),
        },
        "frozen_definitions": {
            "omega_H": "distinct structural states reachable in <=H generated edges including start",
            "post_boundary_shell_k": "nodes at exact shortest generated-edge distance k from boundary target",
            "selection": "SHA256 deterministic discovery/confirmation split; discovery selects earliest k in 1..3 only",
            "R1": "confirmation: post-boundary shell exceeds boundary potential",
            "R2": "confirmation: post-boundary shell exceeds pre-boundary d=1 source potential",
            "R3": "confirmation: boundary route exceeds same-source lateral route at same k",
            "R4": "confirmation: majority complete d2 larger -> d1 compressed -> boundary minimum -> post-boundary larger trajectory",
        },
        "horizons": results,
        "pass_rule": "R1 && R2 && R3 && R4 on confirmation split at discovery-selected k for H=2 and H=3, with no cap hit",
        "interpretation": (
            "A pass would establish only a structural delayed re-expansion after the endogenous boundary minimum in the frozen grammar. "
            "It would not establish thermodynamic pressure, Landauer heat, physical hysteresis, quantum measurement, gravity, spacetime, "
            "or the neutron-star analogy."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
