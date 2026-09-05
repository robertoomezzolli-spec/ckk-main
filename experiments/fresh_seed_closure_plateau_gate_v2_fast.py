#!/usr/bin/env python3
"""Semantics-preserving fast runner for the frozen V2 preregistration.

Scientific thresholds and evaluation are imported unchanged from
fresh_seed_closure_plateau_gate_v2.py. Only graph expansion is optimized:
operators are evaluated exactly when at least one input state first enters the pool,
instead of re-evaluating every old-old pair at every later level.

Before the larger run, this runner asserts exact equality with the original expander
on both fresh contexts at a smaller audit depth for:
- generated structural states,
- unique derivation-event keys,
- earliest event levels.
No scientific result is emitted if that equivalence check fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import fresh_seed_closure_plateau_gate_v2 as V2  # noqa: E402

G = V2.G
Derivation = V2.Derivation

AUDIT_LEVELS = 7
AUDIT_CAP = 100_000


def expand_incremental(seeds, levels, cap):
    identity = lambda s: s.structural_sig()
    pool = {identity(s): s for s in seeds}
    frontier = dict(pool)
    derivations = []
    cap_hit = False

    for lvl in range(levels):
        if not frontier:
            break
        items = list(pool.values())
        old_items = [s for sig, s in pool.items() if sig not in frontier]
        frontier_items = list(frontier.values())
        new = {}

        # Unary operators only need the newest states. Every older state was already
        # evaluated when it entered the pool.
        for s in frontier_items:
            for op in G.UNARY:
                r = op(s)
                if not r:
                    continue
                a, z = identity(s), identity(r)
                if a == z:
                    continue
                derivations.append(Derivation(op.__name__, (a,), z, lvl + 1))
                if z not in pool and z not in new:
                    new[z] = r

        def eval_pair(a, b):
            for op in G.BINARY:
                r = op(a, b)
                if not r:
                    continue
                ins = (identity(a), identity(b))
                z = identity(r)
                if z in ins:
                    continue
                derivations.append(Derivation(op.__name__, ins, z, lvl + 1))
                if z not in pool and z not in new:
                    new[z] = r

        # All ordered pairs with >=1 frontier operand, exactly once:
        # frontier x all, plus old x frontier. This is equivalent to all x all
        # modulo old-old pairs, whose deterministic events were already seen earlier.
        for a in frontier_items:
            for b in items:
                eval_pair(a, b)
        for a in old_items:
            for b in frontier_items:
                eval_pair(a, b)

        pool.update(new)
        frontier = new
        if len(pool) > cap:
            cap_hit = True
            break

    return pool, derivations, cap_hit


def event_min_levels(derivations):
    out = {}
    for d in derivations:
        k = d.event_key()
        out[k] = min(out.get(k, d.level), d.level)
    return out


def assert_equivalent_expansion():
    for occ in V2.FRESH_OCC:
        seeds = V2.V1.fresh_seeds(occ)
        p0, d0, c0 = V2.V1.expand_with_seeds(seeds, levels=AUDIT_LEVELS, cap=AUDIT_CAP)
        p1, d1, c1 = expand_incremental(seeds, levels=AUDIT_LEVELS, cap=AUDIT_CAP)

        s0 = set(p0)
        s1 = set(p1)
        if s0 != s1:
            raise AssertionError(
                f"incremental state mismatch occ={occ}: original_only={len(s0-s1)} fast_only={len(s1-s0)}"
            )
        e0 = event_min_levels(d0)
        e1 = event_min_levels(d1)
        if e0 != e1:
            raise AssertionError(
                f"incremental event mismatch occ={occ}: original={len(e0)} fast={len(e1)}"
            )
        if c0 != c1:
            raise AssertionError(f"incremental cap mismatch occ={occ}: original={c0} fast={c1}")
        print(
            f"EXPANSION_EQUIVALENCE_PASS occ={occ} levels={AUDIT_LEVELS} "
            f"states={len(s0)} unique_events={len(e0)} cap_hit={c0}"
        )


def build_graph_fast(occ: int):
    # Reproduce V2.build_graph exactly, replacing only its expander.
    seeds = V2.V1.fresh_seeds(occ)
    pool, derivs, cap_hit = expand_incremental(seeds, levels=V2.LEVELS, cap=V2.CAP)
    states = {s.structural_sig(): s for s in pool.values()}
    first_seen = {s.structural_sig(): 0 for s in seeds if s.structural_sig() in states}
    unique = {}
    for d in derivs:
        if d.output not in states:
            continue
        first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)
        unique.setdefault(d.event_key(), d)

    from collections import defaultdict

    edges = set()
    for d in unique.values():
        for u in set(d.inputs):
            if u in states and u != d.output:
                edges.add((u, d.output))

    adj = defaultdict(set)
    rev = defaultdict(set)
    for u, v in edges:
        adj[u].add(v)
        rev[v].add(u)

    sys.setrecursionlimit(max(100000, len(states) * 4))
    seen = set()
    order = []

    def d1(u):
        seen.add(u)
        for v in adj.get(u, ()):
            if v not in seen:
                d1(v)
        order.append(u)

    for n in states:
        if n not in seen:
            d1(n)

    comp = {}
    members = defaultdict(set)

    def d2(u, c):
        comp[u] = c
        members[c].add(u)
        for v in rev.get(u, ()):
            if v not in comp:
                d2(v, c)

    cid = 0
    for n in reversed(order):
        if n not in comp:
            d2(n, cid)
            cid += 1

    crev = defaultdict(set)
    for u, v in edges:
        cu, cv = comp[u], comp[v]
        if cu != cv:
            crev[cv].add(cu)

    fiber_targets = defaultdict(set)
    for d in unique.values():
        if d.operator != "op_fiber" or len(d.inputs) != 2:
            continue
        base, fib = d.inputs
        if base not in states or fib not in states or d.output not in states:
            continue
        if states[fib].kind != G.CYCLE:
            continue
        kind = states[base].kind
        if kind not in (G.BOUNDARY, G.CYCLE, G.PRODUCT):
            continue
        cb, ct = comp[base], comp[d.output]
        if cb != ct:
            fiber_targets[(cb, kind)].add(ct)

    return {
        "states": states,
        "first_seen": first_seen,
        "adj": adj,
        "crev": crev,
        "members": members,
        "comp": comp,
        "fiber_targets": fiber_targets,
        "cap_hit": cap_hit,
        "derivations": len(unique),
        "edges": len(edges),
        "sccs": len(members),
    }


def main():
    assert_equivalent_expansion()
    V2.build_graph = build_graph_fast
    V2.main()


if __name__ == "__main__":
    main()
