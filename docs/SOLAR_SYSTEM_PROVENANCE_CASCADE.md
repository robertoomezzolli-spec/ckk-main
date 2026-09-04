# Solar-System Provenance Cascade — sealed blind test

Status: EXPERIMENTAL. Evidence type: observational inputs + simulation harness. No grammar change.

## Question
Can the present Solar System be treated as the surviving endpoint of a common-origin cascade, where many admissible substrate histories are eliminated by successive physical constraints, without fitting the final eight-planet architecture directly?

The target is not "explain every orbit". The target is whether a common-origin cascade predicts a narrow family of surviving architectures and whether an intentionally held-out outer-system residual is required by that family.

## Integrity boundary
- CKK grammar remains frozen.
- No Solar-System labels enter `ckk_snapshot/ckk/gen/grammar.py`.
- Planet Nine parameters are forbidden from training, fitting, ranking, thresholds, and scoring.
- The first-stage adapter may use only measured properties of the Sun, the eight confirmed planets, and explicitly declared formation constraints.
- A missing-body inference is valid only if it is produced before reading the Planet-Nine holdout and survives shuffled/null controls.

## Common currency
Do not compare "planet histories" to CKK structures by name. All comparisons are made in a common substrate-history representation:

`h = [initial disk state, transition events, retained bodies, ejections/mergers, final orbital invariants]`

The CKK side contributes provenance discipline (many derivations -> structural quotient), not orbital mechanics. The astrophysical adapter supplies the transition model.

## Stage A — observed endpoint
Use JPL J2000 approximate orbital elements and JPL/NASA masses for Mercury through Neptune. The endpoint vector contains, per body:
- mass
- semimajor axis a
- eccentricity e
- inclination i
- longitude of perihelion
- longitude of ascending node

Derived endpoint observables:
- specific angular-momentum proxy `sqrt(a*(1-e^2))`
- adjacent log-spacing
- mutual-Hill spacing (where masses are available)
- angular-momentum-deficit proxy
- plane dispersion
- terrestrial/giant compositional zoning as a categorical constraint only

## Stage B — common-origin cascade
The initial ensemble must be generated from one protoplanetary-disk family, not eight independent planet priors.

Minimum transitions:
1. disk collapse / common angular-momentum plane
2. condensation-zone filtering
3. planetesimal/embryo accretion
4. mergers and ejections
5. giant-planet growth
6. migration / resonance crossing
7. long-term stability filtering
8. surviving endpoint

Every transition must declare whether it is SOURCE, DERIVED, or ASSUMPTION.

## Stage C — nulls
N0: independent endpoint draw preserving each planet's one-dimensional marginals.
N1: same common disk but shuffled planet masses across final orbital slots.
N2: same common disk but randomized angular-momentum directions.
N3: same cascade with transition ordering shuffled where physically legal.
N4: same endpoint score with provenance erased.

The cascade earns information only if it beats all matched nulls on held-out endpoint structure without increasing free parameters.

## Stage D — leave-one-out reconstruction
For each confirmed planet k:
1. remove k from the endpoint;
2. fit/rank histories using the other seven only;
3. predict a distribution for the missing body's orbital region and mass class;
4. unseal k;
5. record calibration error.

This is the instrument calibration. Planet Nine is not touched until the confirmed-planet leave-one-out programme is calibrated.

## Stage E — sealed outer-system residual
After Stage D thresholds are frozen, run the eight-planet endpoint plus public trans-Neptunian summary observables with no Planet-Nine parameters.

Question: do high-ranked surviving histories require an additional long-lived massive outer perturber?

A positive result must output a pre-registered distribution over at least:
- perturber required: yes/no probability or score
- mass interval
- semimajor-axis interval
- eccentricity/perihelion interval
- inclination interval

Only then compare to the external Planet-Nine literature holdout.

## Falsification
The provenance-cascade hypothesis loses this test if any of the following occurs:
- independent endpoint nulls perform equally well;
- leave-one-out confirmed planets are not recovered above null calibration;
- the result depends on labels rather than orbital invariants;
- a missing perturber appears only after TNO/Planet-Nine tuning;
- provenance does not improve predictive performance over a state-only model;
- the inferred residual is broad enough to include almost any outer body.

## Current repo constraint
The present CKK grammar has no masses, orbital phase space, N-body propagator, disk physics, or mapping from `Struct` to orbital state. Therefore this experiment MUST NOT claim that CKK currently predicts the Solar System. The valid bridge is an external astrophysical transition adapter whose outputs retain CKK-style provenance and are evaluated with the same blind/holdout discipline.

## First executable milestone
`experiments/solar_system_provenance.py` performs the endpoint ingest, derived-invariant calculation, integrity checks, and confirms that Planet-Nine information is absent from the training manifest. It deliberately fails closed before any physical cascade claim until a transition adapter is supplied.
