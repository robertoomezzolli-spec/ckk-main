#!/usr/bin/env python3
"""External projection test: exact higher closure vs finite lower observation.

No CKK kernel modification. No physics constants. The hidden object is a closed
2-torus with period 1 in each coordinate. A lower observer receives only a
scalar projection and finite samples.

Predeclared question: can exact closure upstairs coexist with no exact finite
return downstairs, while best return error converges toward zero?

Controls:
- commensurate hidden flow: exact finite return must be visible;
- irrational hidden flow: no exact hidden return in the tested finite horizon;
- lossy scalar projection must not be allowed to manufacture an exact hidden
  return (false-positive guard).
"""
from __future__ import annotations
import json, math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "results" / "closure_projection_dimension.json"
HORIZONS = [16, 64, 256, 1024, 4096, 16384]
TOL = 1e-12


def torus_state(k, a, b):
    return ((k*a) % 1.0, (k*b) % 1.0)


def hidden_error(s):
    # torus distance to the closure class origin
    x,y=s
    dx=min(x,1-x); dy=min(y,1-y)
    return math.hypot(dx,dy)


def observe(s):
    # deliberately lossy 2D -> 1D projection; no circle/angle/pi semantics
    x,y=s
    return (x + math.sqrt(2.0)*y) % 1.0


def obs_error(z):
    return min(z,1-z)


def arm(name,a,b):
    rows=[]
    exact_hidden=[]; exact_obs=[]
    for H in HORIZONS:
        bh=1.0; bo=1.0; kh=None; ko=None
        for k in range(1,H+1):
            s=torus_state(k,a,b); eh=hidden_error(s); eo=obs_error(observe(s))
            if eh<bh: bh,kh=eh,k
            if eo<bo: bo,ko=eo,k
        rows.append({"H":H,"best_hidden_error":bh,"best_hidden_k":kh,"best_observed_error":bo,"best_observed_k":ko})
        exact_hidden.append(bh<TOL); exact_obs.append(bo<TOL)
    return {"name":name,"a":a,"b":b,"rows":rows,"exact_hidden_by_horizon":exact_hidden,"exact_observed_by_horizon":exact_obs}


def run():
    comm=arm("commensurate",1/3,1/5)  # hidden exact return at lcm 15
    irr=arm("irrational",math.sqrt(2)-1,math.sqrt(3)-1)

    comm_pass = any(comm["exact_hidden_by_horizon"]) and any(comm["exact_observed_by_horizon"])
    irr_no_exact = not any(irr["exact_hidden_by_horizon"])
    hidden_improves = irr["rows"][-1]["best_hidden_error"] < irr["rows"][0]["best_hidden_error"]
    obs_improves = irr["rows"][-1]["best_observed_error"] < irr["rows"][0]["best_observed_error"]

    # A lossy observation may itself collide exactly; such a collision must not
    # be promoted to hidden closure. Count any occurrence as projection aliasing.
    alias=[]
    for k in range(1,HORIZONS[-1]+1):
        s=torus_state(k,math.sqrt(2)-1,math.sqrt(3)-1)
        if obs_error(observe(s)) < TOL and hidden_error(s) >= TOL:
            alias.append(k)
    false_positive_guard = all(hidden_error(torus_state(k,math.sqrt(2)-1,math.sqrt(3)-1)) >= TOL for k in alias)

    status="HIGHER_CLOSURE_PROJECTION_PASS" if (comm_pass and irr_no_exact and hidden_improves and obs_improves and false_positive_guard) else "HIGHER_CLOSURE_PROJECTION_FAIL"
    result={
      "schema":"ckk.external.higher-closure-projection.v1",
      "status":status,
      "hidden_space":"T^2 = R^2 / Z^2; exact quotient closure is primitive",
      "observer":"one scalar lossy projection plus finite samples",
      "tests":{
        "commensurate_exact_return_control":comm_pass,
        "irrational_no_exact_hidden_return_finite_horizon":irr_no_exact,
        "irrational_hidden_best_error_improves":hidden_improves,
        "irrational_observed_best_error_improves":obs_improves,
        "projection_alias_not_promoted_to_hidden_closure":false_positive_guard,
      },
      "arms":{"commensurate":comm,"irrational":irr},
      "projection_alias_exact_hits":alias,
      "claim_boundary":"This is an existence/counterexample test only. It shows that exact quotient closure in a higher state space can coexist with an observer seeing only finite non-closing approximants. It does not establish that physical reality has hidden dimensions, that pi is caused by projection, or that empirical residuals in relativity have this origin."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True)); return result

if __name__=="__main__":
    r=run(); raise SystemExit(0 if r["status"].endswith("PASS") else 1)
