#!/usr/bin/env python3
"""Equal-horizon control for the blind provenance-context measure test.

The previous full-history comparison can confuse provenance context with birth level:
instances created later have fewer remaining expansion rounds. This control takes
historical instances sharing exactly the same structural_sig(), restarts each at
the same horizon with the same canonical environment, and compares only DISTINCT
STRUCTURAL futures. Kernel remains read-only.

No physics, geometry, pi, metric, curvature, gravity, spacetime, mass, energy,
Lorentz, or external time variable is used.
"""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/'ckk_snapshot'/'ckk'/'gen'
sys.path.insert(0,str(GEN))
import grammar as G  # noqa
from expand import expand_auditable  # noqa

OUT=ROOT/'results'/'context_measure_equal_horizon_gate.json'
SOURCE_LEVELS=4
CAP=30000
HORIZON=2
MAX_GROUPS=400
CLOSED={G.CYCLE,G.PRODUCT,G.BUNDLE,G.BOUNDARY}


def structural_rollout(instance, horizon=HORIZON):
    """Same structural environment and same expansion budget for every instance.

    Historical parts are preserved in objects, but deduplication and comparison are
    by structural_sig. This tests whether provenance alone changes structural futures.
    """
    # include same canonical environment for binary operators; replace any exact
    # structural duplicate with the tested instance so only provenance differs.
    pool={s.structural_sig():s for s in G.SEEDS}
    pool[instance.structural_sig()]=instance
    origin=instance.structural_sig()
    seen_future=set()
    for _ in range(horizon):
        items=list(pool.values()); new={}
        for s in items:
            for op in G.UNARY:
                r=op(s)
                if not r: continue
                k=r.structural_sig()
                if k!=s.structural_sig() and k not in pool and k not in new:
                    new[k]=r
        for a in items:
            for b in items:
                for op in G.BINARY:
                    r=op(a,b)
                    if not r: continue
                    k=r.structural_sig()
                    if k in (a.structural_sig(),b.structural_sig()): continue
                    if k not in pool and k not in new: new[k]=r
        for k in new:
            if k!=origin: seen_future.add(k)
        pool.update(new)
        if len(pool)>CAP: break
    # Include pre-existing canonical states reachable only insofar as rollout creates
    # them is awkward; compare generated structural set under identical setup, which
    # is sufficient for provenance discrimination.
    return frozenset(seen_future)


def main():
    hp,hd=expand_auditable(levels=SOURCE_LEVELS,cap=CAP)
    groups=defaultdict(list)
    for s in hp.values():
        if s.kind in CLOSED: groups[s.structural_sig()].append(s)
    repeated=[(k,v) for k,v in groups.items() if len(v)>=2][:MAX_GROUPS]
    differing=[]; invariant=[]
    for k,instances in repeated:
        futures=[structural_rollout(s) for s in instances]
        counts=[len(x) for x in futures]
        same=all(x==futures[0] for x in futures[1:])
        rec={'structural_state':repr(k),'instances':len(instances),'equal_horizon_future_counts':counts,'same_future_set':same}
        (invariant if same else differing).append(rec)
    result={
      'schema':'ckk.external.context-measure-equal-horizon.v1',
      'kernel_modified':False,
      'source_levels':SOURCE_LEVELS,'equal_restart_horizon':HORIZON,
      'frozen_control':'same structural state + distinct historical provenance; restart each with identical horizon and canonical environment; compare structural futures only',
      'tests':{
        'repeated_closed_structural_groups_tested':len(repeated),
        'context_dependent_equal_horizon_groups':len(differing),
        'context_invariant_equal_horizon_groups':len(invariant),
        'context_dependent_fraction':len(differing)/len(repeated) if repeated else None,
      },
      'examples_context_dependent':differing[:10],
      'examples_invariant':invariant[:5],
    }
    if not repeated: result['status']='NO_REPEATED_CONTEXTS'
    elif differing: result['status']='PROVENANCE_CHANGES_EQUAL_HORIZON_STRUCTURAL_FUTURE'
    else: result['status']='EQUAL_HORIZON_STRUCTURAL_FUTURE_CONTEXT_INVARIANT'
    result['interpretation']='This controls the finite-depth/birth-level confound in the previous full-history context test. It still does not derive geometry or physics.'
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__': main()
