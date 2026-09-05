#!/usr/bin/env python3
"""Blind CKK possibility-distance gate.

Question: does frozen CKK provenance already support the purely structural rule

    fewer admissible continuations -> larger operational distance,
    zero continuations -> unreachable/infinite resistance

without importing physics, gravity, relativity, pi, time, mass, energy, or a
preselected inverse-square / Lorentz law?

Kernel policy: READ ONLY. This script only inspects frozen audit/provenance
artifacts already committed on the experiment branch.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
OUT = ROOT / "results" / "possibility_distance_gate.json"

FORBIDDEN = [
    r"\bgravity\b", r"\bgravitation\b", r"\bnewton\b", r"\blorentz\b",
    r"\brelativity\b", r"\bmass\b", r"\benergy\b", r"\bmomentum\b",
    r"\bpi\b", r"3\.14159", r"\btime\b", r"speed\s*of\s*light",
    r"inverse[-_ ]square", r"1\s*/\s*r\s*\*\*\s*2",
]

SRC_KEYS = ("source", "source_id", "src", "src_id", "from", "parent", "parent_id")
DST_KEYS = ("target", "target_id", "dst", "dst_id", "to", "child", "child_id")
OP_KEYS = ("operator", "op", "operation", "kind", "type", "event")


def first(row, keys):
    low = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        if k in low and low[k] not in (None, ""):
            return str(low[k])
    return None


def load_edges():
    edges = []
    sources = []
    # Prefer tabular provenance because it preserves explicit source/target edges.
    for p in sorted(AUDIT.rglob("*.csv")):
        try:
            with p.open(newline="", errors="ignore") as f:
                rd = csv.DictReader(f)
                if not rd.fieldnames:
                    continue
                rows = list(rd)
        except Exception:
            continue
        local = 0
        for row in rows:
            s, t = first(row, SRC_KEYS), first(row, DST_KEYS)
            if s is None or t is None or s == t:
                continue
            op = first(row, OP_KEYS) or ""
            edges.append((s, t, op, str(p.relative_to(ROOT))))
            local += 1
        if local:
            sources.append({"file": str(p.relative_to(ROOT)), "edges": local})
    return edges, sources


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
    mx, my = sum(x)/len(x), sum(y)/len(y)
    vx = sum((a-mx)**2 for a in x)
    vy = sum((b-my)**2 for b in y)
    if vx == 0 or vy == 0:
        return None
    return sum((a-mx)*(b-my) for a,b in zip(x,y)) / math.sqrt(vx*vy)


def spearman(x, y):
    return pearson(rankdata(x), rankdata(y))


def main():
    script = Path(__file__).read_text()
    leakage = {p: bool(re.search(p, script, re.I)) for p in FORBIDDEN}
    # Labels are allowed only in this audit's deny-list/docstring; test logic must not use them.
    # Remove the deny-list block before checking operational code.
    operational = script.split("SRC_KEYS", 1)[1] if "SRC_KEYS" in script else script
    operational_leakage = {p: bool(re.search(p, operational, re.I)) for p in FORBIDDEN}

    edges, edge_sources = load_edges()
    if not edges:
        result = {
            "schema": "ckk.external.possibility-distance-gate.v1",
            "status": "NO_PROVENANCE_EDGE_TABLE_FOUND",
            "kernel_modified": False,
            "edge_sources": edge_sources,
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
        print(json.dumps(result, indent=2, sort_keys=True))
        raise SystemExit(2)

    adj = defaultdict(set)
    rev = defaultdict(set)
    op_counter = Counter()
    for s,t,op,_ in edges:
        adj[s].add(t)
        rev[t].add(s)
        if op:
            op_counter[op] += 1
    nodes = set(adj) | set(rev)

    # Purely endogenous accessibility: number of distinct admissible next states.
    outdeg = {n: len(adj.get(n, ())) for n in nodes}
    indeg = {n: len(rev.get(n, ())) for n in nodes}
    terminals = {n for n in nodes if outdeg[n] == 0}

    # Distance to a frozen terminal is graph-theoretic only, via reverse BFS.
    dist = {}
    q = deque()
    for n in terminals:
        dist[n] = 0
        q.append(n)
    while q:
        v = q.popleft()
        for u in rev.get(v, ()):
            nd = dist[v] + 1
            if u not in dist or nd < dist[u]:
                dist[u] = nd
                q.append(u)

    # Operational resistance is intentionally not a fitted formula: it is the
    # reciprocal of the count of admissible continuations. Zero means no
    # admissible continuation, represented as infinity rather than a number.
    resistance = {n: (math.inf if outdeg[n] == 0 else 1.0/outdeg[n]) for n in nodes}

    finite = [n for n in nodes if n in dist and dist[n] > 0 and outdeg[n] > 0]
    dvals = [dist[n] for n in finite]
    avals = [outdeg[n] for n in finite]
    rvals = [resistance[n] for n in finite]

    # If boundary approach is endogenous, closer-to-terminal states (smaller d)
    # should tend to have fewer continuations and therefore greater resistance.
    rho_d_a = spearman(dvals, avals) if finite else None
    rho_d_r = spearman(dvals, rvals) if finite else None

    # Edge-local ratchet: among edges that strictly approach a terminal by one
    # graph step, how often does accessibility fail to increase / resistance fail
    # to decrease? No physical law or exponent is imposed.
    approach = []
    nonincrease_A = 0
    nondecrease_R = 0
    strict_R = 0
    for s,t,_,_ in edges:
        if s in dist and t in dist and dist[t] == dist[s]-1:
            approach.append((s,t))
            if outdeg[t] <= outdeg[s]:
                nonincrease_A += 1
            if resistance[t] >= resistance[s]:
                nondecrease_R += 1
            if resistance[t] > resistance[s]:
                strict_R += 1

    n_app = len(approach)
    frac_A = nonincrease_A/n_app if n_app else None
    frac_R = nondecrease_R/n_app if n_app else None
    frac_strict = strict_R/n_app if n_app else None

    # Null comparison: edges that do NOT move toward a terminal.
    other = [(s,t) for s,t,_,_ in edges if not (s in dist and t in dist and dist[t] == dist[s]-1)]
    other_nondec_R = sum(1 for s,t in other if resistance[t] >= resistance[s])
    other_frac_R = other_nondec_R/len(other) if other else None

    enough = len(nodes) >= 20 and n_app >= 20 and len(terminals) > 0
    ratchet = bool(enough and frac_R is not None and frac_R >= 0.75 and frac_strict is not None and frac_strict >= 0.25)
    contrast = None if other_frac_R is None or frac_R is None else frac_R - other_frac_R
    discriminates = bool(contrast is not None and contrast >= 0.10)

    if ratchet and discriminates:
        status = "ENDOGENOUS_POSSIBILITY_RESISTANCE_CANDIDATE"
    elif enough:
        status = "POSSIBILITY_METRIC_PRESENT_NO_BOUNDARY_RATCHET"
    else:
        status = "INSUFFICIENT_FROZEN_PROVENANCE"

    result = {
        "schema": "ckk.external.possibility-distance-gate.v1",
        "status": status,
        "kernel_modified": False,
        "physics_used_in_test_logic": any(operational_leakage.values()),
        "operational_leakage_matches": operational_leakage,
        "edge_sources": edge_sources,
        "graph": {
            "nodes": len(nodes), "edges": len(edges), "terminals": len(terminals),
            "outdegree_min": min(outdeg.values()), "outdegree_max": max(outdeg.values()),
        },
        "definition_frozen_before_result": {
            "accessibility": "A(v)=number of distinct admissible outgoing successors in frozen provenance",
            "operational_resistance": "R(v)=1/A(v); A=0 is unreachable and represented as +infinity",
            "boundary_proxy": "terminal provenance state (outdegree zero)",
            "approach": "edge reducing shortest directed graph distance to a terminal by exactly one",
        },
        "tests": {
            "zero_accessibility_maps_to_unreachable": all(math.isinf(resistance[n]) for n in terminals),
            "approach_edges": n_app,
            "approach_accessibility_nonincrease_fraction": frac_A,
            "approach_resistance_nondecrease_fraction": frac_R,
            "approach_resistance_strict_increase_fraction": frac_strict,
            "other_edges_resistance_nondecrease_fraction": other_frac_R,
            "ratchet_contrast": contrast,
            "spearman_distance_vs_accessibility": rho_d_a,
            "spearman_distance_vs_resistance": rho_d_r,
            "boundary_ratchet": ratchet,
            "approach_specific_discrimination": discriminates,
        },
        "interpretation": (
            "This gate does not derive gravity or a spacetime metric. It asks only whether frozen CKK provenance "
            "itself contains a directional accessibility ratchet: as admissible continuation collapses near an "
            "endogenous boundary, reciprocal accessibility grows and zero accessibility becomes operationally unreachable."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
