#!/usr/bin/env python3
"""Read-only audit of the frozen CKK grammar for a Riemann-relevant path.

Question fixed before execution:
Does the existing grammar already contain a generative path of the form
SYMMETRY -> FIXPOINT/SELF-DUAL STATE -> CLOSURE/INTEGER, without adding an
operator or an equivalence relation?

This script does not modify/import-patch the kernel. It imports the frozen
snapshot, expands it as-is, and inspects derivations plus the involution op_dual.
A negative result is the intended hard gate: no new operator may be invented
for Riemann after seeing the target.
"""
from __future__ import annotations
import importlib.util, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/'ckk_snapshot'/'ckk'/'gen'
OUT=ROOT/'results'/'riemann_existing_path_audit.json'

def load():
    sys.path.insert(0,str(GEN))
    gs=importlib.util.spec_from_file_location('grammar',GEN/'grammar.py'); g=importlib.util.module_from_spec(gs); gs.loader.exec_module(g); sys.modules['grammar']=g
    es=importlib.util.spec_from_file_location('expand',GEN/'expand.py'); e=importlib.util.module_from_spec(es); es.loader.exec_module(e)
    return g,e

def main():
    g,e=load()
    pool,der=e.expand_structural_auditable(levels=5,cap=20000)
    states=list(pool.values())
    sym_states=[s for s in states if s.kind==g.SYMMETRY]
    cycles=[s for s in states if s.kind==g.CYCLE]
    integers=[s for s in states if s.kind==g.INTEGER]

    # A genuine fixed point under the grammar's only explicit involution would
    # require D(X) structurally equivalent to X using the grammar's own identity.
    dual_candidates=[]; dual_fixed=[]
    for s in states:
        d=g.op_dual(s)
        if d is not None:
            dual_candidates.append(s)
            if d.structural_sig()==s.structural_sig():
                dual_fixed.append(s)

    # Search whether any derivation consumes a SYMMETRY state and outputs a state
    # that is subsequently closed/wound. In the frozen grammar symmetry can enter
    # only through op_degenerate; record that rather than interpreting it.
    sym_ids={s.structural_sig() for s in sym_states}
    sym_events=[x for x in der if any(i in sym_ids for i in x.inputs)]
    sym_output_ids={x.output for x in sym_events}
    descendants=[x for x in der if any(i in sym_output_ids for i in x.inputs)]
    descendant_ops=sorted({x.operator for x in descendants})

    explicit_fixpoint_symbol=any(getattr(g,n,None) is not None for n in ('FIXPOINT','SELFDUAL','SELF_DUAL'))
    has_existing_fixpoint_path=bool(dual_fixed) or explicit_fixpoint_symbol

    result={
      'schema':'ckk.readonly.riemann-existing-path-audit.v1',
      'status':'EXISTING_PATH_PASS' if has_existing_fixpoint_path else 'EXISTING_PATH_FAIL',
      'run':{'states':len(states),'derivations':len(der)},
      'counts':{'symmetry_states':len(sym_states),'cycles':len(cycles),'integers':len(integers),'dual_candidates':len(dual_candidates),'dual_fixed_points':len(dual_fixed),'symmetry_consuming_events':len(sym_events)},
      'symmetry_descendant_operator_types':descendant_ops,
      'explicit_fixpoint_symbol':explicit_fixpoint_symbol,
      'existing_fixpoint_path':has_existing_fixpoint_path,
      'claim_boundary':'PASS would mean the frozen grammar already contains its own fixed-point/self-dual structure. FAIL means it does not. FAIL forbids adding a Riemann-specific operator/equivalence after seeing the target; it is not evidence against RH or against CKK generally.',
      'kernel_rule_note':'grammar.py explicitly states self-duality is deliberately not generative and requires a separately specified/tested structural equivalence relation.'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); print(json.dumps(result,indent=2,sort_keys=True))
    # We return 0 for both scientific outcomes so CI reports execution success;
    # scientific status is read from JSON.
    return 0
if __name__=='__main__': raise SystemExit(main())
