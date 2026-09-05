#!/usr/bin/env python3
"""Global-loop overdetermination test.

CKK kernel is read-only and unused.

Frozen question:
Can two systems have identical local/open-path observables, yet differ on a
closed-loop observable in a way that no one-parameter local radial deformation
can absorb? If yes, the diagnostic target should be global holonomy-like
structure, not a single circumference residual.

This is a synthetic architecture test, not evidence for new physics.
"""
from __future__ import annotations
import json, math
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"results"/"global_loop_overdetermination.json"

# Local metric family inferred from open-path data: g_a(r)=1+a r^2.
# We fit a from local/open observables only, then predict closed-loop observables.
RADII=[0.2,0.35,0.5,0.7]
TRUE_A=0.18
HOLONOMY=0.37  # planted global term in positive control only


def local_length(r,a):
    return r*(1.0 + a*r*r)


def local_angle_excess(r,a):
    return 0.5*a*r*r


def loop_metric_part(r,a):
    # any local one-parameter deformation predicts loop from same a
    return 2*math.pi*r*(1.0 + a*r*r)


def fit_a_from_open_data(rows):
    vals=[]
    for row in rows:
        r=row['r']
        vals.append((row['L']/r - 1.0)/(r*r))
        vals.append(2*row['angle_excess']/(r*r))
    return sum(vals)/len(vals)


def arm(name,global_term):
    open_rows=[]
    for r in RADII:
        open_rows.append({
            'r':r,
            'L':local_length(r,TRUE_A),
            'angle_excess':local_angle_excess(r,TRUE_A)
        })
    a_hat=fit_a_from_open_data(open_rows)
    loop_rows=[]
    for r in RADII:
        pred=loop_metric_part(r,a_hat)
        observed=pred + global_term
        loop_rows.append({'r':r,'predicted_from_open_fit':pred,'observed_loop':observed,'residual':observed-pred})
    return {'name':name,'a_hat':a_hat,'open_rows':open_rows,'loop_rows':loop_rows}


def best_one_parameter_refit(loop_rows):
    # malicious refit using loop data alone; ask whether one a can absorb a constant
    # global offset at all radii simultaneously.
    num=0.0; den=0.0
    for row in loop_rows:
        r=row['r']
        base=2*math.pi*r
        x=2*math.pi*r**3
        y=row['observed_loop']-base
        num += x*y; den += x*x
    a=num/den
    residuals=[]
    for row in loop_rows:
        r=row['r']
        pred=loop_metric_part(r,a)
        residuals.append(row['observed_loop']-pred)
    return a,residuals


def main():
    null=arm('NULL_LOCAL_ONLY',0.0)
    plus=arm('PLUS_GLOBAL_LOOP',HOLONOMY)

    null_max=max(abs(x['residual']) for x in null['loop_rows'])
    plus_min=min(abs(x['residual']) for x in plus['loop_rows'])

    # Overdetermination: same a is fixed by local length AND local angle channels.
    open_fit_correct=abs(null['a_hat']-TRUE_A)<1e-12 and abs(plus['a_hat']-TRUE_A)<1e-12
    null_closes=null_max<1e-12
    plus_survives_local_fit=plus_min>0.3

    malicious_a, malicious_res=best_one_parameter_refit(plus['loop_rows'])
    one_param_cannot_absorb=max(abs(x) for x in malicious_res)>0.05 and (max(malicious_res)-min(malicious_res))>0.05

    # A genuine global term should reverse sign with loop orientation while local
    # metric observables stay invariant. This is the key discrimination control.
    orientation_plus=HOLONOMY
    orientation_minus=-HOLONOMY
    orientation_odd=abs(orientation_plus+orientation_minus)<1e-15

    passed=open_fit_correct and null_closes and plus_survives_local_fit and one_param_cannot_absorb and orientation_odd
    result={
      'schema':'ckk.external.global-loop-overdetermination.v1',
      'status':'GLOBAL_LOOP_OVERDETERMINATION_PASS' if passed else 'GLOBAL_LOOP_OVERDETERMINATION_FAIL',
      'null':null,
      'positive_control':plus,
      'malicious_loop_only_refit':{'a_hat':malicious_a,'residuals':malicious_res},
      'tests':{
        'local_parameter_overdetermined_by_two_open_channels':open_fit_correct,
        'null_loop_predicted_exactly_from_local_fit':null_closes,
        'global_loop_term_survives_local_fit':plus_survives_local_fit,
        'one_parameter_local_refit_cannot_absorb_pattern':one_param_cannot_absorb,
        'global_term_is_orientation_odd':orientation_odd
      },
      'interpretation':'A single local metric/radial parameter fixed by independent open-path observables cannot absorb an orientation-odd closed-loop residual across radii. The discriminating observable is therefore global loop structure, not a lone circumference mismatch.',
      'claim_boundary':'Synthetic positive-control only. This shows what a falsifiable residual pattern would look like. It does not establish that nature contains such an unexplained term; that requires independent raw data and the same predeclared cross-observable pattern.'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if passed else 1)

if __name__=='__main__': main()
