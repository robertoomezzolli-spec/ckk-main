#!/usr/bin/env python3
"""Preregistered fresh-initial-condition test for the discovered fiber jump.

This is a confirmation test, not subgroup discovery.
Kernel/grammar are imported read-only. The two external seed contexts introduce
carrier occupancies 2 and 3, neither present in grammar.SEEDS, so the generated
state spaces are fresh initial conditions rather than new hash splits of the
previous graph.

Frozen before run:
- base kinds: BOUNDARY vs CYCLE vs PRODUCT for op_fiber only
- H = 2,3,4,5
- compression lag L = 3 for every H
- BOUNDARY mean opening must exceed EACH control by >= 0.25 bit, permutation p<=.01
- rho(pressure, opening)_BOUNDARY >= .25, permutation p<=.01, and exceed each
  control rho by >= .20
- at H=4 and H=5 BOUNDARY mean opening itself must remain >= .25 bit
- both fresh contexts (occ=2 and occ=3) must pass; otherwise overall RED
"""
from __future__ import annotations

import json, math, random, statistics, sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))
import grammar as G  # noqa: E402
from expand import Derivation  # noqa: E402

LEVELS = 8
CAP = 20000
HORIZONS = (2, 3, 4, 5)
LAG = 3
PERMUTATIONS = 4000
OPENING_ADVANTAGE_BITS = 0.25
MIN_BOUNDARY_RHO = 0.25
MIN_RHO_ADVANTAGE = 0.20
MIN_LONG_H_OPENING_BITS = 0.25
OUT = ROOT / "results" / "fresh_seed_fiber_jump_gate.json"


def fresh_seeds(occ: int):
    # Fresh recurrence order and, crucially, fresh finite carrier occupancy.
    # occ changes fill/multiplicity behavior, so occ=2 and occ=3 are not merely
    # relabelings of the canonical occ=1 seed context.
    return [G.Struct(G.RECURRENCE, label=f"fresh~x+5/occ{occ}", order=5)] + list(G.SEED_S) + [
        G.Struct(G.CARRIER, label=f"fresh-occ-{occ}", occ=occ),
        G.Struct(G.CARRIER, label="fresh-free", occ=G.INF),
    ]


def expand_with_seeds(seeds, levels=LEVELS, cap=CAP):
    identity = lambda s: s.structural_sig()
    pool = {identity(s): s for s in seeds}
    derivations = []
    cap_hit = False
    for lvl in range(levels):
        new = {}
        items = list(pool.values())
        for s in items:
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
        for a in items:
            for b in items:
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
        pool.update(new)
        if len(pool) > cap:
            cap_hit = True
            break
    return pool, derivations, cap_hit


def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and xs[order[j]] == xs[order[i]]:
            j += 1
        r = (i + 1 + j) / 2.0
        for k in range(i, j): ranks[order[k]] = r
        i = j
    return ranks


def pearson(xs, ys):
    if len(xs) < 4 or len(xs) != len(ys): return None
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    dx, dy = [x-mx for x in xs], [y-my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return sum(a*b for a,b in zip(dx,dy))/den if den else None


def spearman(xs, ys):
    return pearson(rankdata(xs), rankdata(ys))


def perm_diff_p(a, b, observed, seed):
    if len(a) < 3 or len(b) < 3: return None
    rng = random.Random(seed)
    pool = list(a) + list(b)
    na = len(a)
    extreme = 0
    for _ in range(PERMUTATIONS):
        rng.shuffle(pool)
        d = sum(pool[:na])/na - sum(pool[na:])/(len(pool)-na)
        if d >= observed: extreme += 1
    return (1 + extreme)/(PERMUTATIONS + 1)


def perm_rho_p(xs, ys, observed, seed):
    if observed is None or len(xs) < 4: return None
    rng = random.Random(seed)
    base = list(ys)
    extreme = 0
    for _ in range(PERMUTATIONS):
        z = base[:]
        rng.shuffle(z)
        r = spearman(xs, z)
        if (r if r is not None else -2) >= observed: extreme += 1
    return (1 + extreme)/(PERMUTATIONS + 1)


def graph_from(occ):
    seeds = fresh_seeds(occ)
    pool, derivs, cap_hit = expand_with_seeds(seeds)
    states = {s.structural_sig(): s for s in pool.values()}
    first_seen = {s.structural_sig(): 0 for s in seeds if s.structural_sig() in states}
    unique = {}
    for d in derivs:
        if d.output not in states: continue
        first_seen[d.output] = min(first_seen.get(d.output, d.level), d.level)
        unique.setdefault(d.event_key(), d)

    edges = set(); edge_ops = defaultdict(set)
    for d in unique.values():
        for u in set(d.inputs):
            if u in states and u != d.output:
                edges.add((u, d.output)); edge_ops[(u,d.output)].add(d.operator)
    adj=defaultdict(set); rev=defaultdict(set)
    for u,v in edges: adj[u].add(v); rev[v].add(u)

    sys.setrecursionlimit(max(100000, len(states)*4))
    seen=set(); order=[]
    def d1(u):
        seen.add(u)
        for v in adj.get(u,()):
            if v not in seen: d1(v)
        order.append(u)
    for n in states:
        if n not in seen: d1(n)
    comp={}; members=defaultdict(set)
    def d2(u,c):
        comp[u]=c; members[c].add(u)
        for v in rev.get(u,()):
            if v not in comp: d2(v,c)
    cid=0
    for n in reversed(order):
        if n not in comp:
            d2(n,cid); cid += 1

    cadj=defaultdict(set); crev=defaultdict(set)
    for u,v in edges:
        cu,cv=comp[u],comp[v]
        if cu!=cv: cadj[cu].add(cv); crev[cv].add(cu)

    # op_fiber observations keyed by base SCC and base kind. Use only base->output,
    # never the CYCLE-fiber input->output projection.
    fiber_targets=defaultdict(set)
    for d in unique.values():
        if d.operator != "op_fiber" or len(d.inputs) != 2: continue
        base, fib = d.inputs
        if base not in states or fib not in states or d.output not in states: continue
        if states[fib].kind != G.CYCLE: continue
        kind = states[base].kind
        if kind not in (G.BOUNDARY, G.CYCLE, G.PRODUCT): continue
        cb, ct = comp[base], comp[d.output]
        if cb == ct: continue
        fiber_targets[(cb,kind)].add(ct)

    return {
        "states":states,"first_seen":first_seen,"adj":adj,"crev":crev,"members":members,
        "comp":comp,"fiber_targets":fiber_targets,"cap_hit":cap_hit,
        "derivations":len(unique),"edges":len(edges),"sccs":len(members)
    }


def evaluate(g, occ, H):
    states, first_seen, adj, crev, members = g["states"],g["first_seen"],g["adj"],g["crev"],g["members"]
    eligible_nodes={n for n in states if first_seen.get(n,LEVELS) <= LEVELS-H}
    eligible_comps={c for c,ns in members.items() if ns and all(n in eligible_nodes for n in ns)}

    @lru_cache(maxsize=None)
    def omega(c):
        seen=set(members[c]); front=set(members[c])
        for _ in range(H):
            nxt=set()
            for u in front: nxt.update(adj.get(u,()))
            nxt -= seen
            if not nxt: break
            seen.update(nxt); front=nxt
        return len(seen)

    @lru_cache(maxsize=None)
    def exact_anc(c, lag):
        front={c}
        for _ in range(lag):
            nxt=set()
            for x in front: nxt.update(crev.get(x,()))
            front=nxt
            if not front: break
        return frozenset(front)

    def pressure(c):
        aa=[a for a in exact_anc(c,LAG) if a in eligible_comps]
        if not aa: return None
        oc=omega(c)
        vals=[math.log2(omega(a)/oc) for a in aa if omega(a)>0 and oc>0]
        return sum(vals)/len(vals) if vals else None

    obs={G.BOUNDARY:[], G.CYCLE:[], G.PRODUCT:[]}
    for (c,kind), targets in g["fiber_targets"].items():
        if c not in eligible_comps: continue
        ts=[t for t in targets if t in eligible_comps]
        if not ts: continue
        p=pressure(c)
        if p is None: continue
        oc=omega(c)
        openings=[math.log2(omega(t)/oc) for t in ts]
        obs[kind].append({"source":c,"pressure":p,"opening":sum(openings)/len(openings),"omega":oc,"n_targets":len(ts)})

    summary={}
    for kind, rows in obs.items():
        xs=[r["pressure"] for r in rows]; ys=[r["opening"] for r in rows]
        rho=spearman(xs,ys)
        summary[kind]={
            "n":len(rows),
            "mean_opening_bits":sum(ys)/len(ys) if ys else None,
            "median_opening_bits":statistics.median(ys) if ys else None,
            "mean_pressure_bits":sum(xs)/len(xs) if xs else None,
            "rho_pressure_opening":rho,
            "rho_permutation_p":perm_rho_p(xs,ys,rho, 20270000 + occ*100 + H) if rho is not None else None,
        }

    b=[r["opening"] for r in obs[G.BOUNDARY]]
    comparisons={}; t1=True
    for idx,kind in enumerate((G.CYCLE,G.PRODUCT), start=1):
        c=[r["opening"] for r in obs[kind]]
        diff=(sum(b)/len(b)-sum(c)/len(c)) if b and c else None
        p=perm_diff_p(b,c,diff, 20271000 + occ*100 + H*10 + idx) if diff is not None else None
        passed=bool(diff is not None and diff >= OPENING_ADVANTAGE_BITS and p is not None and p <= .01)
        comparisons[f"BOUNDARY_vs_{kind}"]={"mean_difference_bits":diff,"permutation_p":p,"pass":passed}
        t1=t1 and passed

    rb=summary[G.BOUNDARY]["rho_pressure_opening"]
    pb=summary[G.BOUNDARY]["rho_permutation_p"]
    rho_adv={}; t2=bool(rb is not None and rb>=MIN_BOUNDARY_RHO and pb is not None and pb<=.01)
    for kind in (G.CYCLE,G.PRODUCT):
        rc=summary[kind]["rho_pressure_opening"]
        adv=(rb-rc) if rb is not None and rc is not None else None
        ok=bool(adv is not None and adv>=MIN_RHO_ADVANTAGE)
        rho_adv[f"BOUNDARY_minus_{kind}"]={"rho_difference":adv,"pass":ok}
        t2=t2 and ok

    mb=summary[G.BOUNDARY]["mean_opening_bits"]
    t3=True if H<4 else bool(mb is not None and mb>=MIN_LONG_H_OPENING_BITS)
    return {
        "H":H,"eligible_nodes":len(eligible_nodes),"eligible_sccs":len(eligible_comps),
        "by_base_kind":summary,"opening_specificity":comparisons,"rho_specificity":rho_adv,
        "T1_boundary_opens_more_than_controls":t1,
        "T2_boundary_only_pressure_coupling":t2,
        "T3_long_horizon_opening_survives":t3,
        "pass": t1 and t2 and t3,
    }


def main():
    all_results={}; overall=True
    for occ in (2,3):
        g=graph_from(occ)
        hrs={str(H):evaluate(g,occ,H) for H in HORIZONS}
        context_pass=(not g["cap_hit"]) and all(v["pass"] for v in hrs.values())
        overall=overall and context_pass
        all_results[str(occ)]={
            "generator":{"levels":LEVELS,"cap":CAP,"cap_hit":g["cap_hit"],"states":len(g["states"]),"derivation_events":g["derivations"],"edges":g["edges"],"sccs":g["sccs"]},
            "horizons":hrs,"pass":context_pass,
        }
    result={
        "schema":"ckk.external.fresh-seed-fiber-jump.v1",
        "kernel_modified":False,
        "fresh_initial_conditions":{"carrier_occ":[2,3],"canonical_seed_occ_values":[1,G.INF],"note":"occ=2 and occ=3 are absent from grammar.SEEDS and alter fill/multiplicity behavior"},
        "preregistered_thresholds":{"H":[2,3,4,5],"compression_lag":LAG,"opening_advantage_bits":OPENING_ADVANTAGE_BITS,"max_pairwise_p":.01,"min_boundary_rho":MIN_BOUNDARY_RHO,"min_rho_advantage":MIN_RHO_ADVANTAGE,"min_H4_H5_boundary_opening_bits":MIN_LONG_H_OPENING_BITS,"contexts_must_both_pass":True},
        "contexts":all_results,
        "pass_rule":"Both fresh occ contexts pass T1,T2,T3 at every H=2..5 and neither hits cap",
        "status":"FRESH_SEED_BOUNDARY_FIBER_JUMP_CONFIRMED" if overall else "FRESH_SEED_BOUNDARY_FIBER_JUMP_NOT_CONFIRMED",
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__ == "__main__": main()
