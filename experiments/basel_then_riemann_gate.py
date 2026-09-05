#!/usr/bin/env python3
"""External two-gate experiment: Basel first, Riemann second.

CKK KERNEL IS READ-ONLY. This harness does not import or modify CKK generation.

Gate 1 (Basel): starting only from the reciprocal-square series, test whether
finite partial sums converge to the known closed value pi^2/6. This is a
numerical sanity gate, not a discovery claim.

Gate 2 (Riemann): only if Gate 1 passes, evaluate the functional-equation
symmetry of completed zeta numerically at paired points s and 1-s, then inspect
known nontrivial zeros as external observations and test reflection about 1/2.
This does NOT prove RH. It tests whether the same closure/symmetry language has
an externally measurable realization before any proof attempt.
"""
from __future__ import annotations
import cmath, json, math
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"results"/"basel_then_riemann_gate.json"


def basel():
    target=math.pi**2/6
    Ns=[10,100,1000,10000,100000]
    rows=[]
    for N in Ns:
        s=sum(1.0/(n*n) for n in range(1,N+1))
        rows.append({"N":N,"sum":s,"error":abs(target-s)})
    monotone=all(rows[i+1]["error"]<rows[i]["error"] for i in range(len(rows)-1))
    return {"target":target,"rows":rows,"monotone_error_decay":monotone,"pass":monotone and rows[-1]["error"]<1.1e-5}

# eta continuation, adequate away from pole; zeta=eta/(1-2^(1-s))
def zeta(s, N=300000):
    eta=0j
    for n in range(1,N+1):
        eta += (1 if n%2 else -1) * cmath.exp(-s*math.log(n))
    return eta/(1-cmath.exp((1-s)*math.log(2)))

def gamma_lanczos(z):
    p=[0.99999999999980993,676.5203681218851,-1259.1392167224028,771.32342877765313,-176.61502916214059,12.507343278686905,-0.13857109526572012,9.984369578019571e-6,1.5056327351493116e-7]
    if z.real<0.5:
        return math.pi/(cmath.sin(math.pi*z)*gamma_lanczos(1-z))
    z-=1; x=p[0]
    for i in range(1,len(p)): x+=p[i]/(z+i)
    t=z+7.5
    return math.sqrt(2*math.pi)*t**(z+0.5)*cmath.exp(-t)*x

def xi(s):
    return 0.5*s*(s-1)*(math.pi**(-s/2))*gamma_lanczos(s/2)*zeta(s)

def riemann_gate():
    # functional-equation reflection control at modest imaginary parts
    pts=[0.2+3j,0.37+5j,0.71+7j]
    sym=[]
    for s in pts:
        a=xi(s); b=xi(1-s)
        rel=abs(a-b)/max(1.0,abs(a),abs(b))
        sym.append({"s":[s.real,s.imag],"relative_symmetry_error":rel})
    symmetry_pass=max(r["relative_symmetry_error"] for r in sym)<5e-3

    # external held observations: first well-known ordinates of nontrivial zeros.
    # We do NOT search/tune real parts. We evaluate the frozen line 1/2 and
    # symmetric off-line perturbations as a discrimination check.
    ordinates=[14.134725141734693,21.022039638771555,25.01085758014569,30.424876125859513]
    zero_rows=[]
    for t in ordinates:
        center=abs(zeta(0.5+1j*t,120000))
        left=abs(zeta(0.45+1j*t,120000)); right=abs(zeta(0.55+1j*t,120000))
        zero_rows.append({"t":t,"abs_zeta_half":center,"abs_zeta_045":left,"abs_zeta_055":right,"center_smaller":center<left and center<right})
    zeros_pass=all(r["center_smaller"] for r in zero_rows)
    return {"functional_equation":sym,"symmetry_pass":symmetry_pass,"held_zero_ordinates":zero_rows,"held_zero_line_discrimination_pass":zeros_pass,"pass":symmetry_pass and zeros_pass,
            "claim_boundary":"Passing confirms numerical reflection symmetry and that selected known zero ordinates are locally minimized on Re(s)=1/2. It is not evidence that all nontrivial zeros lie there and is not a proof of RH."}

def main():
    b=basel()
    r=riemann_gate() if b["pass"] else {"pass":False,"skipped":"Basel gate failed"}
    result={"schema":"ckk.external.basel-riemann.v1","basel":b,"riemann":r,"status":"BASEL_AND_RIEMANN_GATE_PASS" if b["pass"] and r["pass"] else "GATE_FAIL",
            "kernel":"read-only / unused by numerical harness",
            "interpretation_boundary":"This sequence tests a mathematical bridge from reciprocal-square closure to zeta reflection. It does not derive pi from CKK, does not prove RH, and cannot be used to alter the kernel."}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2)); return result
if __name__=='__main__':
    rr=main(); raise SystemExit(0 if rr["status"].endswith("PASS") else 1)
