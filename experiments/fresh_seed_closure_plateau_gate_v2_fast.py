#!/usr/bin/env python3
"""Execution-only accelerator for the frozen closure plateau V2 preregistration.

Scientific definitions, thresholds, fresh contexts, horizons and output logic remain
in fresh_seed_closure_plateau_gate_v2.py unchanged. This file changes only how
impossible binary operator candidates are skipped.

Before the large run, the accelerator is required to match the original brute-force
runner on a reference expansion for:
- exact structural-state set,
- exact unique derivation-event set with earliest level,
- exact output first-seen levels,
- cap status.
If equivalence fails, no scientific result is emitted.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import fresh_seed_fiber_jump_gate as V1  # noqa: E402
import fresh_seed_closure_plateau_gate_v2 as V2  # noqa: E402

G = V1.G
Derivation = V1.Derivation
ORIGINAL_EXPAND = V1.expand_with_seeds

AUDIT_LEVELS = 4
AUDIT_CAP = 20_000
EXPECTED_BINARY = {"op_product", "op_fiber", "op_degenerate", "op_exclude"}


def indexed_incremental_expand(seeds, levels, cap):
    """Semantics-preserving structural expansion without impossible old-old scans.

    Deterministic old-old operator applications cannot create a state after the level
    in which that same pair first coexisted. We therefore evaluate a binary pair only
    when at least one operand is in the newest frontier. Applicability indexing uses
    only predicates already present in grammar.py; every candidate is still evaluated
    by the original Grammar operator.
    """
    binary_names = {op.__name__ for op in G.BINARY}
    if binary_names != EXPECTED_BINARY:
        raise RuntimeError(
            f"Grammar binary operator set changed: {sorted(binary_names)} != {sorted(EXPECTED_BINARY)}"
        )

    identity = lambda s: s.structural_sig()
    pool = {identity(s): s for s in seeds}
    frontier = dict(pool)
    derivations = []
    cap_hit = False

    for lvl in range(levels):
        if not frontier:
            break

        items = list(pool.values())
        frontier_items = list(frontier.values())
        frontier_ids = set(frontier)
        old_items = [s for s in items if identity(s) not in frontier_ids]
        new = {}

        def record(op, inputs, r):
            if not r:
                return
            ins = tuple(identity(x) for x in inputs)
            z = identity(r)
            if z in ins:
                return
            derivations.append(Derivation(op.__name__, ins, z, lvl + 1))
            if z not in pool and z not in new:
                new[z] = r

        # Unary deterministic operators: only a newly entered state needs evaluation.
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

        def compat_key(s):
            return (s.sym, s.bc, s.order, s.dual)

        all_keyed = defaultdict(list)
        front_keyed = defaultdict(list)
        old_keyed = defaultdict(list)
        for s in items:
            if s.kind in (G.CYCLE, G.PRODUCT, G.BOUNDARY):
                all_keyed[compat_key(s)].append(s)
        for s in frontier_items:
            if s.kind in (G.CYCLE, G.PRODUCT, G.BOUNDARY):
                front_keyed[compat_key(s)].append(s)
        for s in old_items:
            if s.kind in (G.CYCLE, G.PRODUCT, G.BOUNDARY):
                old_keyed[compat_key(s)].append(s)

        # op_product is commutative at derivation identity. Enumerate compatible
        # pairs with >=1 frontier member, canonicalized once per level.
        seen_product = set()
        for key, fgroup in front_keyed.items():
            all_prod = [s for s in all_keyed[key] if s.kind in (G.CYCLE, G.PRODUCT)]
            front_prod = [s for s in fgroup if s.kind in (G.CYCLE, G.PRODUCT)]
            for a in front_prod:
                for b in all_prod:
                    sa, sb = identity(a), identity(b)
                    pair = tuple(sorted((sa, sb)))
                    if pair in seen_product:
                        continue
                    seen_product.add(pair)
                    record(G.op_product, (a, b), G.op_product(a, b))

        # op_fiber is directed. Evaluate frontier-base x all-fiber plus
        # old-base x frontier-fiber, with exact Grammar compatibility key.
        for key in set(all_keyed):
            all_fibers = [s for s in all_keyed[key] if s.kind == G.CYCLE]
            front_fibers = [s for s in front_keyed.get(key, ()) if s.kind == G.CYCLE]
            front_bases = [
                s for s in front_keyed.get(key, ())
                if s.kind in (G.CYCLE, G.PRODUCT, G.BOUNDARY)
            ]
            old_bases = [
                s for s in old_keyed.get(key, ())
                if s.kind in (G.CYCLE, G.PRODUCT, G.BOUNDARY)
            ]
            for base in front_bases:
                for fib in all_fibers:
                    record(G.op_fiber, (base, fib), G.op_fiber(base, fib))
            for base in old_bases:
                for fib in front_fibers:
                    record(G.op_fiber, (base, fib), G.op_fiber(base, fib))

        # op_degenerate(s, sym): antiunitary SYMMETRY second input only.
        all_anti = [s for s in items if s.kind == G.SYMMETRY and s.anti]
        front_anti = [s for s in frontier_items if s.kind == G.SYMMETRY and s.anti]
        front_deg = [
            s for s in frontier_items
            if s.kind in (G.CYCLE, G.PRODUCT, G.BUNDLE, G.WEIGHT) and s.mult == 1
        ]
        old_deg = [
            s for s in old_items
            if s.kind in (G.CYCLE, G.PRODUCT, G.BUNDLE, G.WEIGHT) and s.mult == 1
        ]
        for base in front_deg:
            for sym in all_anti:
                record(G.op_degenerate, (base, sym), G.op_degenerate(base, sym))
        for base in old_deg:
            for sym in front_anti:
                record(G.op_degenerate, (base, sym), G.op_degenerate(base, sym))

        # op_exclude(s, carrier): CARRIER second input, occ-free base only.
        all_carriers = [s for s in items if s.kind == G.CARRIER]
        front_carriers = [s for s in frontier_items if s.kind == G.CARRIER]
        front_excl = [
            s for s in frontier_items
            if s.kind in (G.CYCLE, G.PRODUCT, G.BUNDLE, G.INTEGER, G.WEIGHT)
            and s.occ is None
        ]
        old_excl = [
            s for s in old_items
            if s.kind in (G.CYCLE, G.PRODUCT, G.BUNDLE, G.INTEGER, G.WEIGHT)
            and s.occ is None
        ]
        for base in front_excl:
            for carrier in all_carriers:
                record(G.op_exclude, (base, carrier), G.op_exclude(base, carrier))
        for base in old_excl:
            for carrier in front_carriers:
                record(G.op_exclude, (base, carrier), G.op_exclude(base, carrier))

        pool.update(new)
        frontier = new
        # Exactly the original level-boundary cap semantics.
        if len(pool) > cap:
            cap_hit = True
            break

    return pool, derivations, cap_hit


def earliest_events(derivs):
    out = {}
    for d in derivs:
        k = d.event_key()
        out[k] = min(out.get(k, d.level), d.level)
    return out


def output_first_seen(seeds, derivs):
    out = {s.structural_sig(): 0 for s in seeds}
    for d in derivs:
        out[d.output] = min(out.get(d.output, d.level), d.level)
    return out


def prove_equivalence():
    reports = {}
    for occ in V2.FRESH_OCC:
        seeds = V1.fresh_seeds(occ)
        old_pool, old_derivs, old_cap = ORIGINAL_EXPAND(
            seeds, levels=AUDIT_LEVELS, cap=AUDIT_CAP
        )
        new_pool, new_derivs, new_cap = indexed_incremental_expand(
            seeds, levels=AUDIT_LEVELS, cap=AUDIT_CAP
        )
        report = {
            "levels": AUDIT_LEVELS,
            "cap": AUDIT_CAP,
            "old_states": len(old_pool),
            "new_states": len(new_pool),
            "old_unique_events": len(earliest_events(old_derivs)),
            "new_unique_events": len(earliest_events(new_derivs)),
            "state_set_equal": set(old_pool) == set(new_pool),
            "earliest_event_map_equal": earliest_events(old_derivs) == earliest_events(new_derivs),
            "output_first_seen_equal": output_first_seen(seeds, old_derivs) == output_first_seen(seeds, new_derivs),
            "cap_status_equal": old_cap == new_cap,
        }
        report["pass"] = all(
            report[k]
            for k in (
                "state_set_equal",
                "earliest_event_map_equal",
                "output_first_seen_equal",
                "cap_status_equal",
            )
        )
        reports[str(occ)] = report
        if not report["pass"]:
            raise RuntimeError(
                "Indexed runner failed brute-force equivalence proof: "
                + json.dumps({"occ": occ, **report}, sort_keys=True)
            )
        print("EXPANSION_EQUIVALENCE_PASS", occ, json.dumps(report, sort_keys=True), flush=True)
    return reports


def build_graph_fast(occ: int):
    # Reproduce V2.build_graph exactly, replacing only its expander.
    seeds = V1.fresh_seeds(occ)
    pool, derivs, cap_hit = indexed_incremental_expand(
        seeds, levels=V2.LEVELS, cap=V2.CAP
    )
    states = {s.structural_sig(): s for s in pool.values()}
    first_seen = {s.structural_sig(): 0 for s in seeds if s.structural_sig() in states}
    unique = {}
    for d in derivs:
        if d.output not in states:
            continue
        first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)
        unique.setdefault(d.event_key(), d)

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
    equivalence = prove_equivalence()
    V2.build_graph = build_graph_fast
    V2.main()

    # Execution provenance only; scientific fields produced by V2 are untouched.
    data = json.loads(V2.OUT.read_text())
    data["runner"] = "indexed_incremental_after_bruteforce_equivalence_check"
    data["runner_equivalence"] = equivalence
    V2.OUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print("INDEXED_V2_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
