# Preregistration — Fresh-seed closure-completion plateau + floor-corrected coupling (V2)

Frozen before observing any V2 result.

## Motivation

The previous preregistered jump gate remained red. Its surviving descriptive structure suggested a narrower hypothesis: adding a CYCLE to an open BOUNDARY preserves or slightly opens future potential, while adding the same CYCLE closure to already-closed CYCLE/PRODUCT structures collapses future potential. The previous raw pressure-opening rho comparison is not reused as evidence because the controls can exhibit a mechanical floor effect.

## Generator

- Kernel/grammar unchanged.
- Fresh initial conditions: `carrier.occ = 2` and `carrier.occ = 3`.
- Levels: 10.
- State cap: 100,000.
- Horizons: H = 2, 3, 4, 5, 6, 7.
- Compression lag: 3.

## Test A — closure-completion specificity

At every horizon where both controls are populated, BOUNDARY must exceed CYCLE and PRODUCT by at least 0.25 bit in mean opening, with pairwise permutation p <= 0.01.

Interpretation if supported: attaching closure to an open edge preserves/opens potential relative to redundant closure on already-closed structures. This is not called a "jump".

## Test B — plateau

Primary persistence criterion:

- H5, H6, H7 BOUNDARY mean opening values must all exist,
- each must have n >= 5,
- max(H5,H6,H7) - min(H5,H6,H7) <= 0.05 bit,
- mean(H5,H6,H7) >= 0.15 bit.

This directly tests a nonzero plateau rather than monotone growth or an arbitrary H4/H5 threshold.

## Test C — floor-corrected pressure coupling

Controls are not compared raw. They are matched to BOUNDARY observations on the observable post-transition future-potential floor using fixed 0.25-bit bins. The null then compares pressure-opening rho after this floor matching.

Pass criteria:

- at least 20 matched pairs,
- Boundary rho >= 0.25,
- Boundary rho - floor-matched control rho >= 0.20,
- permutation p <= 0.01.

## Overall gate

Both fresh initial conditions must pass the preregistered criteria and neither may hit the state cap. Otherwise the overall status remains red.

No thresholds are to be changed after seeing the V2 output.
