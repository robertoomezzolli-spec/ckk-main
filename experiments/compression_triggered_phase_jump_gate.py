#!/usr/bin/env python3
"""Blind compression-triggered irreversible phase-jump gate.

The gate does not assume that BOUNDARY itself is the jump. It searches the
finite generated structural graph for a discontinuous opening that follows
accumulated state-space compression.

Frozen structural interpretation
--------------------------------
* A strongly connected component (SCC) is a reversible phase: every state in
  it can return to every other state using generated transitions.
* A condensation-DAG edge between SCCs is an irreversible commit candidate in
  the finite generated graph.
* A phase-class change is a change in the explicit grammar ``kind`` set of the
  SCC. No physical label is introduced.
* Omega_H(C) is the number of distinct structural states reachable from any
  member of SCC C within <=H generated edges, including the SCC itself.
* For lag L, compression pressure at C is the mean over condensation-DAG
  ancestors A exactly L irreversible commits away of
      log2(Omega_H(A) / Omega_H(C)).
  Positive pressure therefore means the accessible future has compressed.
* Jump opening on C->D is
      log2(Omega_H(D) / Omega_H(C)).
  Positive opening means a reset-horizon future space larger than immediately
  before the commit.

Discovery/confirmation
----------------------
Sources are deterministically split with SHA256. Discovery may inspect only
L=1,2,3 and selects the lag with the largest positive Spearman association
between compression pressure and class-changing commit opening. Confirmation
then tests that frozen lag.

Frozen confirmation tests (H=2 and H=3 independently)
------------------------------------------------------
J1 PRESSURE->OPENING:
    Spearman(pressure, mean class-changing opening per source) > 0 with a
    fixed-seed permutation p <= .01.
J2 COMPRESSED SOURCES OPEN:
    among pressure>0 sources, mean and median class-changing opening >0,
    >50% are positive, sign-flip p<=.01.
J3 CLASS-CHANGE SPECIFICITY:
    where the same source has irreversible same-kind controls, class-changing
    opening exceeds same-kind opening source-matched; mean/median >0,
    >50% positive, sign-flip p<=.01.
J4 JUMP PREVALENCE:
    >50% of confirmation sources with pressure>0 have positive class-changing
    opening. (Descriptive operator/kind exemplars are emitted separately.)

A pass establishes only this graph-structural pattern. It does not establish
Landauer heat, measurement physics, gravity, spacetime, energy, or a physical
phase transition.
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
LAGS = (1, 2, 3)
PERMUTATIONS = 4000
SEED = 20260905
OUT = ROOT / "results" / "compression_triggered_phase_jump_gate.json"


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


def pearson(xs, ys):
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return (sum(a*b for a, b in zip(dx, dy)) / den) if den else None


def spearman(xs, ys):
    return pearson(rankdata(xs), rankdata(ys))


def spearman_perm_p(xs, ys, observed, seed):
    if observed is None or len(xs) < 3:
        return None
    rng = random.Random(seed)
    null = []
    base = list(ys)
    for _ in range(PERMUTATIONS):
        z = base[:]
        rng.shuffle(z)
        r = spearman(xs, z)
        null.append(0.0 if r is None else r)
    extreme = sum(1 for r in null if r >= observed)
    return {
        "permutations": PERMUTATIONS,
        "seed": seed,
        "one_sided_p": (1 + extreme) / (PERMUTATIONS + 1),
        "null_mean": sum(null) / len(null),
        "null_min": min(null),
        "null_max": max(null),
    }


def sign_flip_p(values, observed, seed):
    if not values:
        return None
    rng = random.Random(seed)
    null = []
    vals = list(values)
    for _ in range(PERMUTATIONS):
        null.append(sum(v if rng.random() < .5 else -v for v in vals) / len(vals))
    extreme = sum(1 for x in null if x >= observed)
    return {
        "permutations": PERMUTATIONS,
        "seed": seed,
        "one_sided_p": (1 + extreme) / (PERMUTATIONS + 1),
        "null_mean": sum(null) / len(null),
        "null_min": min(null),
        "null_max": max(null),
    }


def positive_summary(values, seed):
    if not values:
        return {"n": 0, "mean": None, "median": None, "fraction_positive": None,
                "permutation_null": None, "pass": False}
    mean = sum(values) / len(values)
    med = statistics.median(values)
    frac = sum(1 for v in values if v > 0) / len(values)
    null = sign_flip_p(values, mean, seed)
    passed = mean > 0 and med > 0 and frac > .5 and null["one_sided_p"] <= .01
    return {"n": len(values), "mean": mean, "median": med,
            "fraction_positive": frac, "permutation_null": null, "pass": passed}


def split_key(cid, members):
    token = repr(min(members[cid], key=repr)).encode()
    return int(hashlib.sha256(token).hexdigest(), 16) & 1


def main():
    pool, derivations = expand_structural_auditable(levels=LEVELS, cap=CAP)
    states = {s.structural_sig(): s for s in pool.values()}
    cap_hit = len(states) > CAP

    first_seen = {s.structural_sig(): 0 for s in G.SEEDS if s.structural_sig() in states}
    for d in derivations:
        if d.output in states:
            first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)

    unique_events = {}
    for d in derivations:
        if d.output in states:
            unique_events.setdefault(d.event_key(), d)

    edges = set()
    edge_ops = defaultdict(set)
    for d in unique_events.values():
        for inp in set(d.inputs):
            if inp in states and inp != d.output:
                edges.add((inp, d.output))
                edge_ops[(inp, d.output)].add(d.operator)

    adj = defaultdict(set)
    rev = defaultdict(set)
    for u, v in edges:
        adj[u].add(v)
        rev[v].add(u)

    # Kosaraju SCCs.
    seen = set()
    order = []
    sys.setrecursionlimit(max(100000, len(states) * 4))

    def dfs1(u):
        seen.add(u)
        for v in adj.get(u, ()):
            if v not in seen:
                dfs1(v)
        order.append(u)

    for n in states:
        if n not in seen:
            dfs1(n)

    comp = {}
    members = defaultdict(set)

    def dfs2(u, cid):
        comp[u] = cid
        members[cid].add(u)
        for v in rev.get(u, ()):
            if v not in comp:
                dfs2(v, cid)

    cid = 0
    for n in reversed(order):
        if n not in comp:
            dfs2(n, cid)
            cid += 1

    cadj = defaultdict(set)
    crev = defaultdict(set)
    cops = defaultdict(set)
    for u, v in edges:
        cu, cv = comp[u], comp[v]
        if cu != cv:
            cadj[cu].add(cv)
            crev[cv].add(cu)
            cops[(cu, cv)].update(edge_ops[(u, v)])

    class_sig = {
        c: tuple(sorted({states[n].kind for n in ns}))
        for c, ns in members.items()
    }

    @lru_cache(maxsize=None)
    def exact_ancestors(c, lag):
        frontier = {c}
        for _ in range(lag):
            nxt = set()
            for x in frontier:
                nxt.update(crev.get(x, ()))
            frontier = nxt
            if not frontier:
                break
        return frozenset(frontier)

    results = {}
    overall = True

    for H in HORIZONS:
        eligible_nodes = {n for n in states if first_seen.get(n, LEVELS) <= LEVELS - H}
        eligible_comps = {
            c for c, ns in members.items()
            if ns and all(n in eligible_nodes for n in ns)
        }

        @lru_cache(maxsize=None)
        def omega(c):
            # Equal raw-edge restart horizon from the whole reversible SCC.
            seen_nodes = set(members[c])
            frontier = set(members[c])
            for _ in range(H):
                nxt = set()
                for u in frontier:
                    nxt.update(adj.get(u, ()))
                nxt -= seen_nodes
                if not nxt:
                    break
                seen_nodes.update(nxt)
                frontier = nxt
            return len(seen_nodes)

        def pressure(c, lag):
            ancs = [a for a in exact_ancestors(c, lag) if a in eligible_comps]
            if not ancs:
                return None
            oc = omega(c)
            vals = [math.log2(omega(a) / oc) for a in ancs if omega(a) > 0 and oc > 0]
            return (sum(vals) / len(vals)) if vals else None

        # Aggregate outgoing irreversible commits per source SCC.
        base_sources = []
        for c in sorted(eligible_comps):
            class_targets = [d for d in cadj.get(c, ())
                             if d in eligible_comps and class_sig[d] != class_sig[c]]
            same_targets = [d for d in cadj.get(c, ())
                            if d in eligible_comps and class_sig[d] == class_sig[c]]
            if not class_targets:
                continue
            oc = omega(c)
            class_open = [math.log2(omega(d) / oc) for d in class_targets]
            same_open = [math.log2(omega(d) / oc) for d in same_targets]
            base_sources.append({
                "cid": c,
                "class_open": sum(class_open) / len(class_open),
                "same_open": (sum(same_open) / len(same_open)) if same_open else None,
                "class_targets": class_targets,
            })

        discovery = [r for r in base_sources if split_key(r["cid"], members) == 0]
        confirmation = [r for r in base_sources if split_key(r["cid"], members) == 1]

        scan = {}
        best_lag = None
        best_rho = -2.0
        for lag in LAGS:
            xs, ys = [], []
            for r in discovery:
                p = pressure(r["cid"], lag)
                if p is not None:
                    xs.append(p)
                    ys.append(r["class_open"])
            rho = spearman(xs, ys)
            scan[str(lag)] = {
                "n": len(xs),
                "spearman_pressure_vs_opening": rho,
                "mean_pressure": (sum(xs) / len(xs)) if xs else None,
                "mean_opening": (sum(ys) / len(ys)) if ys else None,
            }
            score = rho if rho is not None else -2.0
            if score > best_rho:
                best_rho = score
                best_lag = lag

        conf = []
        for r in confirmation:
            p = pressure(r["cid"], best_lag) if best_lag is not None else None
            if p is None:
                continue
            q = dict(r)
            q["pressure"] = p
            conf.append(q)

        px = [r["pressure"] for r in conf]
        oy = [r["class_open"] for r in conf]
        rho = spearman(px, oy)
        rho_null = spearman_perm_p(px, oy, rho, SEED + 10 * H + (best_lag or 0))
        j1_pass = bool(rho is not None and rho > 0 and rho_null and rho_null["one_sided_p"] <= .01)
        j1 = {"n": len(px), "selected_lag": best_lag, "spearman": rho,
              "permutation_null": rho_null, "pass": j1_pass}

        compressed = [r for r in conf if r["pressure"] > 0]
        j2 = positive_summary([r["class_open"] for r in compressed], SEED + 100 + H)

        matched = [r["class_open"] - r["same_open"] for r in conf if r["same_open"] is not None]
        j3 = positive_summary(matched, SEED + 200 + H)

        jump_frac = (sum(1 for r in compressed if r["class_open"] > 0) / len(compressed)) if compressed else None
        j4_pass = bool(jump_frac is not None and jump_frac > .5)
        j4 = {"compressed_sources": len(compressed), "fraction_positive_class_opening": jump_frac,
              "pass": j4_pass}

        # Emit the strongest actual confirmed jump exemplars, not used for pass/fail.
        exemplars = []
        for r in compressed:
            c = r["cid"]
            oc = omega(c)
            for d in r["class_targets"]:
                opening = math.log2(omega(d) / oc)
                if opening <= 0:
                    continue
                exemplars.append({
                    "source_scc": c,
                    "target_scc": d,
                    "source_class": class_sig[c],
                    "target_class": class_sig[d],
                    "operators": sorted(cops[(c, d)]),
                    "compression_pressure_bits": r["pressure"],
                    "opening_bits": opening,
                    "opening_ratio": 2 ** opening,
                    "source_omega": oc,
                    "target_omega": omega(d),
                    "source_scc_size": len(members[c]),
                    "target_scc_size": len(members[d]),
                })
        exemplars.sort(key=lambda x: (x["compression_pressure_bits"] * x["opening_bits"], x["opening_bits"]), reverse=True)

        hp = j1_pass and j2["pass"] and j3["pass"] and j4_pass
        overall = overall and hp
        results[str(H)] = {
            "eligible_nodes": len(eligible_nodes),
            "eligible_sccs": len(eligible_comps),
            "discovery_sources": len(discovery),
            "confirmation_sources": len(confirmation),
            "discovery_scan": scan,
            "selected_lag": best_lag,
            "J1_pressure_to_opening": j1,
            "J2_compressed_sources_open": j2,
            "J3_class_change_specificity": j3,
            "J4_jump_prevalence": j4,
            "top_confirmed_jump_exemplars": exemplars[:12],
            "pass": hp,
        }

    result = {
        "schema": "ckk.external.compression-triggered-phase-jump.v1",
        "status": "COMPRESSION_TRIGGERED_IRREVERSIBLE_PHASE_JUMP_H2_H3" if overall else "PHASE_JUMP_NOT_FULLY_SUPPORTED",
        "kernel_modified": False,
        "generator": {
            "function": "expand_structural_auditable",
            "levels": LEVELS,
            "cap": CAP,
            "cap_hit": cap_hit,
            "states": len(states),
            "unique_structural_edges": len(edges),
            "sccs": len(members),
            "irreversible_condensation_edges": sum(len(v) for v in cadj.values()),
        },
        "frozen_definitions": {
            "reversible_phase": "strongly connected component of generated structural graph",
            "commit_candidate": "edge between distinct SCCs in condensation DAG",
            "phase_class": "set of explicit grammar kind values within SCC",
            "omega_H": "distinct structural states reachable from entire SCC within <=H raw generated edges",
            "compression_pressure": "mean log2 Omega(ancestor)/Omega(source) over exact-L irreversible ancestors",
            "jump_opening": "log2 Omega(target)/Omega(source) on irreversible class-changing commit",
            "selection": "SHA256 source-SCC discovery/confirmation split; discovery selects L in {1,2,3} only",
        },
        "horizons": results,
        "pass_rule": "J1 && J2 && J3 && J4 at H=2 and H=3 with no kernel modification",
        "interpretation": "A pass identifies only a graph-structural compression-associated irreversible class-changing future-space opening. It does not establish a thermodynamic, quantum, gravitational, spacetime, energetic, or physical phase transition.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
