#!/usr/bin/env python3
"""Blind future-cone accessibility gate.

Read-only with respect to the CKK kernel. Reuses the frozen structural generator,
but replaces one-step out-degree with the complete distinct reachable future cone.
No physics, pi, gravity, spacetime, Lorentz, mass, energy, or time variable.
"""
from __future__ import annotations
import json, math, statistics
from collections import defaultdict, deque
from pathlib import Path

# Reuse the already-audited graph construction from V2 rather than modifying kernel code.
import possibility_distance_gate as base


def rankdata(xs):
    order=sorted(range(len(xs)), key=lambda i: xs[i]); r=[0.0]*len(xs); i=0
    while i<len(order):
        j=i
        while j+1<len(order) and xs[order[j+1]]==xs[order[i]]: j+=1
        avg=(i+j+2)/2.0
        for k in range(i,j+1): r[order[k]]=avg
        i=j+1
    return r

def spearman(x,y):
    if len(x)<3:return None
    rx,ry=rankdata(x),rankdata(y); mx,my=statistics.mean(rx),statistics.mean(ry)
    num=sum((a-mx)*(b-my) for a,b in zip(rx,ry)); den=math.sqrt(sum((a-mx)**2 for a in rx)*sum((b-my)**2 for b in ry))
    return num/den if den else None

def reachable_count(start, succ):
    seen=set(); q=list(succ.get(start,()))
    while q:
        v=q.pop()
        if v==start or v in seen: continue
        seen.add(v); q.extend(succ.get(v,()))
    return len(seen)

def main():
    # V2 exposes build_graph() returning states/events/level metadata; fail loudly if contract changed.
    built=base.build_graph()
    if isinstance(built, dict):
        states=built['states']; events=built['events']; levels=built.get('levels',{})
    else:
        states,events,levels=built
    def sid(s):
        if isinstance(s,str): return s
        for k in ('id','state_id','uid','hash'): 
            if isinstance(s,dict) and k in s:return str(s[k])
            if hasattr(s,k):return str(getattr(s,k))
        return str(s)
    smap={sid(s):s for s in states}
    def kind(s):
        if isinstance(s,dict): return str(s.get('kind',''))
        return str(getattr(s,'kind',''))
    def endpoints(e):
        if isinstance(e,dict):
            a=e.get('source') or e.get('source_id') or e.get('src'); b=e.get('target') or e.get('target_id') or e.get('dst')
        else:
            a=getattr(e,'source',getattr(e,'source_id',None)); b=getattr(e,'target',getattr(e,'target_id',None))
        return sid(a),sid(b)
    succ=defaultdict(set); pred=defaultdict(set)
    for e in events:
        a,b=endpoints(e)
        if a in smap and b in smap and a!=b: succ[a].add(b); pred[b].add(a)
    boundaries={i for i,s in smap.items() if kind(s)=='BOUNDARY'}
    # graph distance to an endogenous boundary, reverse BFS
    dist={b:0 for b in boundaries}; q=deque(boundaries)
    while q:
        v=q.popleft()
        for p in pred.get(v,()):
            if p not in dist: dist[p]=dist[v]+1; q.append(p)
    cone={v:reachable_count(v,succ) for v in smap}
    # frontier guard: if level metadata is unavailable, exclude nodes with no generated successors,
    # since finite truncation makes their cone unknowable rather than zero.
    eligible={v for v in dist if succ.get(v)}
    approach=[]; other=[]
    for a in eligible:
        for b in succ.get(a,()):
            if b not in eligible: continue
            rec=(cone[a],cone[b])
            if dist.get(b)==dist[a]-1: approach.append(rec)
            else: other.append(rec)
    def frac_nonincrease(rows): return sum(b<=a for a,b in rows)/len(rows) if rows else None
    def frac_strict(rows): return sum(b<a for a,b in rows)/len(rows) if rows else None
    ap=frac_nonincrease(approach); ot=frac_nonincrease(other)
    ds=[dist[v] for v in eligible]; cs=[cone[v] for v in eligible]
    result={
      'schema':'ckk.external.future-cone-gate.v1','kernel_modified':False,
      'frozen_definitions':{
        'future_cone':'F(v)=number of distinct states reachable from v by one or more generated derivation edges; confluence counted once',
        'approach':'edge lowering shortest graph distance to endogenous BOUNDARY by one',
        'operational_distance':'monotone inverse of F only as an external diagnostic; no physical law assumed'},
      'generator':{'states':len(smap),'events':len(events),'endogenous_boundaries':len(boundaries),'eligible':len(eligible)},
      'tests':{'approach_edges':len(approach),'other_edges':len(other),'approach_future_cone_nonincrease_fraction':ap,'approach_future_cone_strict_decrease_fraction':frac_strict(approach),'other_future_cone_nonincrease_fraction':ot,'approach_vs_other_contrast':None if ap is None or ot is None else ap-ot,'spearman_boundary_distance_vs_future_cone':spearman(ds,cs),'min_future_cone_eligible':min(cs) if cs else None,'max_future_cone_eligible':max(cs) if cs else None},
    }
    contrast=result['tests']['approach_vs_other_contrast']
    rho=result['tests']['spearman_boundary_distance_vs_future_cone']
    # Positive only if boundary approach narrows the complete future cone more than controls and global distance agrees.
    positive=(contrast is not None and contrast>0 and rho is not None and rho>0)
    result['status']='BOUNDARY_SPECIFIC_FUTURE_CONE_RATCHET' if positive else 'FUTURE_CONE_PRESENT_NO_BOUNDARY_SPECIFIC_RATCHET'
    result['interpretation']='Structural blind test only; a positive result is not a derivation of gravity, geometry, or physics.'
    Path('results').mkdir(exist_ok=True); Path('results/future_cone_gate.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__': main()
