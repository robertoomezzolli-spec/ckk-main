#!/usr/bin/env python3
"""Execution-only accelerator for the frozen closure plateau V2 preregistration.

All scientific definitions, thresholds, contexts, horizons and decision rules remain
in fresh_seed_closure_plateau_gate_v2.py unchanged.

This runner constructs the SAME structural transition graph without materializing
millions of derivation records whose inputs have identical operator effects. Before
running H=2..7 it must reproduce the brute-force runner exactly on a reference graph:
structural states, first-seen levels, graph edges, op_fiber base->target pairs and cap
status. Any mismatch aborts before a scientific result is produced.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import fresh_seed_fiber_jump_gate as V1  # noqa: E402
import fresh_seed_closure_plateau_gate_v2 as V2  # noqa: E402

G = V1.G
AUDIT_LEVELS = 4
AUDIT_CAP = 20_000


def _compat(s):
    return (s.sym, s.bc, s.order, s.dual)


def _prod_effect(s):
    return (s.dim, s.mult, s.occ)


def _fiber_base_effect(s):
    # op_fiber output does not depend on base.kind or base.occ.
    return (s.dim, s.mult)


def _fiber_effect(s):
    # op_fiber output does not depend on fiber.dim.
    return (s.mult, s.occ)


def expand_graph_direct(seeds, levels, cap):
    """Return structural pool, first_seen, edges, fiber base-target pairs, event count.

    Exact state-pair derivations are counted analytically where outputs are identical;
    structural edges are inserted for every participating structural input state.
    """
    identity = lambda s: s.structural_sig()
    pool = {identity(s): s for s in seeds}
    frontier = dict(pool)
    first_seen = {identity(s): 0 for s in seeds}
    edges = set()
    fiber_pairs = set()
    unique_event_count = 0
    cap_hit = False

    for lvl0 in range(levels):
        if not frontier:
            break
        lvl = lvl0 + 1
        items = list(pool.values())
        frontier_ids = set(frontier)
        frontier_items = list(frontier.values())
        new = {}

        def install(r, input_sigs):
            nonlocal unique_event_count
            if not r:
                return None
            z = identity(r)
            if z in input_sigs:
                return None
            unique_event_count += 1
            for u in set(input_sigs):
                if u != z:
                    edges.add((u, z))
            if z not in pool and z not in new:
                new[z] = r
                first_seen[z] = lvl
            return z

        # Unary events: each structural state is evaluated once, when first seen.
        for s in frontier_items:
            a = identity(s)
            for op in G.UNARY:
                r = op(s)
                install(r, (a,))

        # ---------- op_product ----------
        # Bucket states by the exact fields that determine a product output.
        # Within one compatibility class, kind CYCLE vs PRODUCT does not affect output.
        prod_all = defaultdict(lambda: defaultdict(list))
        prod_front_n = defaultdict(lambda: defaultdict(int))
        for s in items:
            if s.kind in (G.CYCLE, G.PRODUCT):
                k, e = _compat(s), _prod_effect(s)
                prod_all[k][e].append(s)
                if identity(s) in frontier_ids:
                    prod_front_n[k][e] += 1

        for k, buckets in prod_all.items():
            effects = list(buckets)
            for i, e1 in enumerate(effects):
                b1 = buckets[e1]
                f1 = prod_front_n[k].get(e1, 0)
                for j in range(i, len(effects)):
                    e2 = effects[j]
                    b2 = buckets[e2]
                    f2 = prod_front_n[k].get(e2, 0)
                    if f1 == 0 and f2 == 0:
                        continue
                    r = G.op_product(b1[0], b2[0])
                    if not r:
                        continue
                    z = identity(r)
                    # Product output cannot equal a positive-dimensional CYCLE/PRODUCT
                    # input under this grammar, but keep the structural guard explicit.
                    if z in (identity(b1[0]), identity(b2[0])):
                        continue
                    if z not in pool and z not in new:
                        new[z] = r
                        first_seen[z] = lvl
                    for s in b1:
                        edges.add((identity(s), z))
                    for s in b2:
                        edges.add((identity(s), z))

                    n1, n2 = len(b1), len(b2)
                    if i == j:
                        old = n1 - f1
                        # unordered exact input pairs with replacement, minus old-old
                        unique_event_count += n1 * (n1 + 1) // 2 - old * (old + 1) // 2
                    else:
                        old1, old2 = n1 - f1, n2 - f2
                        unique_event_count += n1 * n2 - old1 * old2

        # ---------- op_fiber ----------
        # Group bases/fibers only by fields that actually alter the BUNDLE output.
        base_all = defaultdict(lambda: defaultdict(list))
        base_front_n = defaultdict(lambda: defaultdict(int))
        fib_all = defaultdict(lambda: defaultdict(list))
        fib_front_n = defaultdict(lambda: defaultdict(int))
        for s in items:
            k = _compat(s)
            sig = identity(s)
            if s.kind in (G.CYCLE, G.PRODUCT, G.BOUNDARY):
                e = _fiber_base_effect(s)
                base_all[k][e].append(s)
                if sig in frontier_ids:
                    base_front_n[k][e] += 1
            if s.kind == G.CYCLE:
                e = _fiber_effect(s)
                fib_all[k][e].append(s)
                if sig in frontier_ids:
                    fib_front_n[k][e] += 1

        for k in set(base_all) & set(fib_all):
            for be, bases in base_all[k].items():
                fb = base_front_n[k].get(be, 0)
                for fe, fibs in fib_all[k].items():
                    ff = fib_front_n[k].get(fe, 0)
                    if fb == 0 and ff == 0:
                        continue
                    r = G.op_fiber(bases[0], fibs[0])
                    if not r:
                        continue
                    z = identity(r)
                    if z not in pool and z not in new:
                        new[z] = r
                        first_seen[z] = lvl
                    for base in bases:
                        bs = identity(base)
                        edges.add((bs, z))
                        fiber_pairs.add((bs, z))
                    for fib in fibs:
                        edges.add((identity(fib), z))
                    old_b, old_f = len(bases) - fb, len(fibs) - ff
                    # Directed base,fiber applications with >=1 newly seen operand.
                    unique_event_count += len(bases) * len(fibs) - old_b * old_f

        # ---------- op_degenerate ----------
        all_anti = [s for s in items if s.kind == G.SYMMETRY and s.anti]
        front_anti = [s for s in all_anti if identity(s) in frontier_ids]
        all_deg = [
            s for s in items
            if s.kind in (G.CYCLE, G.PRODUCT, G.BUNDLE, G.WEIGHT) and s.mult == 1
        ]
        front_deg = [s for s in all_deg if identity(s) in frontier_ids]
        old_deg = [s for s in all_deg if identity(s) not in frontier_ids]
        for base in front_deg:
            for sym in all_anti:
                install(G.op_degenerate(base, sym), (identity(base), identity(sym)))
        for base in old_deg:
            for sym in front_anti:
                install(G.op_degenerate(base, sym), (identity(base), identity(sym)))

        # ---------- op_exclude ----------
        all_carriers = [s for s in items if s.kind == G.CARRIER]
        front_carriers = [s for s in all_carriers if identity(s) in frontier_ids]
        all_excl = [
            s for s in items
            if s.kind in (G.CYCLE, G.PRODUCT, G.BUNDLE, G.INTEGER, G.WEIGHT)
            and s.occ is None
        ]
        front_excl = [s for s in all_excl if identity(s) in frontier_ids]
        old_excl = [s for s in all_excl if identity(s) not in frontier_ids]
        for base in front_excl:
            for carrier in all_carriers:
                install(G.op_exclude(base, carrier), (identity(base), identity(carrier)))
        for base in old_excl:
            for carrier in front_carriers:
                install(G.op_exclude(base, carrier), (identity(base), identity(carrier)))

        pool.update(new)
        frontier = new
        print(
            f"DIRECT_EXPAND level={lvl} states={len(pool)} frontier={len(frontier)} "
            f"edges={len(edges)} events={unique_event_count}",
            flush=True,
        )
        # Preserve the frozen experiment's level-boundary cap semantics.
        if len(pool) > cap:
            cap_hit = True
            break

    return {
        "pool": pool,
        "first_seen": first_seen,
        "edges": edges,
        "fiber_pairs": fiber_pairs,
        "cap_hit": cap_hit,
        "derivations": unique_event_count,
    }


def brute_reference(seeds, levels, cap):
    pool, derivs, cap_hit = V1.expand_with_seeds(seeds, levels=levels, cap=cap)
    states = {s.structural_sig(): s for s in pool.values()}
    first_seen = {s.structural_sig(): 0 for s in seeds if s.structural_sig() in states}
    unique = {}
    for d in derivs:
        if d.output not in states:
            continue
        first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)
        unique.setdefault(d.event_key(), d)
    edges = set()
    fiber_pairs = set()
    for d in unique.values():
        for u in set(d.inputs):
            if u in states and u != d.output:
                edges.add((u, d.output))
        if d.operator == "op_fiber" and len(d.inputs) == 2:
            base, fib = d.inputs
            if base in states and fib in states and d.output in states and states[fib].kind == G.CYCLE:
                if states[base].kind in (G.BOUNDARY, G.CYCLE, G.PRODUCT):
                    fiber_pairs.add((base, d.output))
    return {
        "pool": pool,
        "first_seen": first_seen,
        "edges": edges,
        "fiber_pairs": fiber_pairs,
        "cap_hit": cap_hit,
        "derivations": len(unique),
    }


def prove_equivalence():
    reports = {}
    for occ in V2.FRESH_OCC:
        seeds = V1.fresh_seeds(occ)
        old = brute_reference(seeds, AUDIT_LEVELS, AUDIT_CAP)
        new = expand_graph_direct(seeds, AUDIT_LEVELS, AUDIT_CAP)
        report = {
            "levels": AUDIT_LEVELS,
            "cap": AUDIT_CAP,
            "states": len(old["pool"]),
            "old_unique_events": old["derivations"],
            "new_unique_events": new["derivations"],
            "state_set_equal": set(old["pool"]) == set(new["pool"]),
            "first_seen_equal": old["first_seen"] == new["first_seen"],
            "edge_set_equal": old["edges"] == new["edges"],
            "fiber_pair_set_equal": old["fiber_pairs"] == new["fiber_pairs"],
            "unique_event_count_equal": old["derivations"] == new["derivations"],
            "cap_status_equal": old["cap_hit"] == new["cap_hit"],
        }
        report["pass"] = all(
            report[k]
            for k in (
                "state_set_equal", "first_seen_equal", "edge_set_equal",
                "fiber_pair_set_equal", "unique_event_count_equal", "cap_status_equal"
            )
        )
        reports[str(occ)] = report
        if not report["pass"]:
            raise RuntimeError(
                "Direct runner failed brute-force equivalence proof: "
                + json.dumps({"occ": occ, **report}, sort_keys=True)
            )
        print("DIRECT_EQUIVALENCE_PASS", occ, json.dumps(report, sort_keys=True), flush=True)
    return reports


def finish_graph(raw):
    states = {s.structural_sig(): s for s in raw["pool"].values()}
    edges = raw["edges"]
    adj = defaultdict(set)
    rev = defaultdict(set)
    for u, v in edges:
        if u in states and v in states:
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
        if u not in comp or v not in comp:
            continue
        cu, cv = comp[u], comp[v]
        if cu != cv:
            crev[cv].add(cu)

    fiber_targets = defaultdict(set)
    for base, target in raw["fiber_pairs"]:
        if base not in states or target not in states:
            continue
        cb, ct = comp[base], comp[target]
        if cb != ct:
            fiber_targets[(cb, states[base].kind)].add(ct)

    return {
        "states": states,
        "first_seen": raw["first_seen"],
        "adj": adj,
        "crev": crev,
        "members": members,
        "comp": comp,
        "fiber_targets": fiber_targets,
        "cap_hit": raw["cap_hit"],
        "derivations": raw["derivations"],
        "edges": len(edges),
        "sccs": len(members),
    }


def build_graph_fast(occ: int):
    raw = expand_graph_direct(V1.fresh_seeds(occ), V2.LEVELS, V2.CAP)
    return finish_graph(raw)


def main():
    equivalence = prove_equivalence()
    V2.build_graph = build_graph_fast
    V2.main()

    data = json.loads(V2.OUT.read_text())
    data["runner"] = "aggregated_structural_graph_after_exact_bruteforce_equivalence_check"
    data["runner_equivalence"] = equivalence
    V2.OUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print("DIRECT_V2_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
