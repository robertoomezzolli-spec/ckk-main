#!/usr/bin/env python3
"""Single-resistance unification gate.

KERNEL POLICY: read-only external harness. No CKK kernel files are touched.
No physics constants, named laws, or fitted physical parameters are used by the
construction itself.

Frozen question
---------------
Can ONE primitive architecture, 'constraint load divided by accessible
channels', simultaneously produce:
  (A) an inverse-square spatial scaling in exactly three spatial dimensions;
  (B) a divergent approach-cost as an abstract boundary is approached;
without inserting either target exponent into the primitive?

The experiment also asks a harder question:
Does that architecture uniquely determine the detailed boundary divergence
shape? It should NOT claim so unless the model family collapses to one law.
"""
from __future__ import annotations

import json, math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "results" / "single_resistance_unification_gate.json"


def linreg_slope(xs, ys):
    mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    den = sum((x-mx)**2 for x in xs)
    return num/den


def shell_accessibility(r, d):
    # Only the scaling matters; no sphere constants are used.
    # A shell in d dimensions has channel multiplicity proportional to r^(d-1).
    return r ** (d-1)


def resistance_from_accessibility(accessibility, load=1.0, response_power=1.0):
    return load / (accessibility ** response_power)


def spatial_gate():
    radii = [1.25, 1.6, 2.0, 2.7, 3.8, 5.5, 8.0, 12.0, 18.0, 27.0]
    rows=[]
    for d in range(1,7):
        rs=[resistance_from_accessibility(shell_accessibility(r,d)) for r in radii]
        slope=linreg_slope([math.log(r) for r in radii],[math.log(x) for x in rs])
        expected=-(d-1)
        rows.append({"dimension":d,"measured_loglog_slope":slope,"structural_expected":expected,"abs_error":abs(slope-expected)})
    unique_inverse_square=[r["dimension"] for r in rows if abs(r["measured_loglog_slope"]+2.0)<1e-12]
    return {
        "rows":rows,
        "unique_inverse_square_dimensions":unique_inverse_square,
        "pass":unique_inverse_square==[3]
    }


def boundary_gate():
    # q is only an abstract normalized approach coordinate in [0,1).
    # We deliberately test several channel-closing laws; none is privileged.
    qs=[0.0,0.25,0.5,0.75,0.9,0.97,0.99,0.999,0.9999,0.99999]
    closing_powers=[1,2,3,4]
    response_powers=[0.5,1.0,1.5]
    families=[]
    for p in closing_powers:
        for alpha in response_powers:
            vals=[]
            monotone=True
            prev=None
            for q in qs:
                acc=max(1e-300, 1.0-q**p)
                R=resistance_from_accessibility(acc,response_power=alpha)
                if prev is not None and not (R>prev): monotone=False
                prev=R
                vals.append({"q":q,"accessibility":acc,"resistance":R})
            families.append({"closing_power":p,"response_power":alpha,"monotone":monotone,"last_resistance":vals[-1]["resistance"],"values":vals})
    all_diverge_like=all(f["monotone"] and f["last_resistance"]>100 for f in families)
    # Non-uniqueness test: multiple distinct families satisfy the same qualitative divergence.
    distinct_signatures={(f["closing_power"],f["response_power"]) for f in families if f["monotone"] and f["last_resistance"]>100}
    return {
        "families":families,
        "qualitative_divergence_robust":all_diverge_like,
        "number_of_distinct_divergent_families":len(distinct_signatures),
        "detailed_law_unique":len(distinct_signatures)==1,
        "pass_qualitative":all_diverge_like,
        "pass_uniqueness_guard":len(distinct_signatures)>1
    }


def combined_gate():
    spatial=spatial_gate(); boundary=boundary_gate()
    architecture_pass=spatial["pass"] and boundary["pass_qualitative"] and boundary["pass_uniqueness_guard"]
    if architecture_pass:
        status="SINGLE_RESISTANCE_ARCHITECTURE_PASS_EXACT_BOUNDARY_LAW_UNDERDETERMINED"
    else:
        status="SINGLE_RESISTANCE_ARCHITECTURE_FAIL"
    return {
        "schema":"ckk.external.single-resistance-unification.v1",
        "status":status,
        "primitive":"resistance = constraint_load / accessibility^alpha",
        "physics_labels_used_by_construction":False,
        "spatial":spatial,
        "boundary":boundary,
        "tests":{
            "inverse_square_emerges_only_in_dimension_3":spatial["pass"],
            "boundary_approach_generically_raises_resistance":boundary["pass_qualitative"],
            "exact_boundary_shape_not_forced_by_primitive":boundary["pass_uniqueness_guard"]
        },
        "interpretation":(
            "A single accessibility-based resistance architecture is sufficient to generate an inverse-square spatial law specifically in three dimensions and a divergent cost near a closing boundary. "
            "However the primitive alone does not select one detailed divergence shape; extra structure would be required before mapping the boundary arm to any specific physical law."
        ),
        "claim_boundary":(
            "This is an architecture test, not a derivation of gravity or relativity. The inverse-square result follows from shell multiplicity in d dimensions; the divergence result follows from accessibility tending to zero. "
            "A physical claim would require CKK to generate the accessibility rule and response power independently, then predict held-out observables."
        )
    }


def main():
    result=combined_gate()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if result["status"].startswith("SINGLE_RESISTANCE_ARCHITECTURE_PASS") else 1)

if __name__=="__main__":
    main()
