# Preregistration — Fresh-seed closure-completion plateau + floor-corrected coupling (V2)

Frozen before observing any valid V2 result.

The first V2 workflow wiring attempt did not constitute a valid measurement because its adapter imported names that do not exist in the audited V1 gate. The implementation was corrected before reading any V2 scientific output. No threshold below was chosen from a valid V2 result.

## Motivation

The previous preregistered jump gate remained red. Its surviving descriptive structure suggested a narrower hypothesis: adding a CYCLE to an open BOUNDARY preserves or slightly opens future potential, while adding the same CYCLE closure to already-closed CYCLE/PRODUCT structures collapses future potential. The previous raw pressure-opening rho comparison is not reused as evidence because the controls can exhibit a mechanical floor effect.

## Generator

- Kernel/grammar unchanged.
- Fresh initial conditions remain `carrier.occ = 2` and `carrier.occ = 3`.
- Levels: 12.
- State cap: 100,000.
- Horizons: H = 2, 3, 4, 5, 6, 7.
- Compression lag: 3.
- Any state-cap hit invalidates confirmation for that context.

The deeper graph is deliberate: at H=7, eligibility is `first_seen <= LEVELS-H = 5`, giving the long-horizon test materially more source support than the previous levels=8, H=5 case (`first_seen <= 3`).

## Test A — closure-completion specificity

This is a replication gate for the narrower surviving claim, not for the old jump picture.

At H=2, H=3, and H=4, in each fresh context:

- BOUNDARY, CYCLE, and PRODUCT must each have n >= 3;
- mean opening(Boundary) - mean opening(Cycle) >= 0.25 bit;
- mean opening(Boundary) - mean opening(Product) >= 0.25 bit;
- each pairwise permutation p <= 0.01.

Interpretation if supported: attaching a CYCLE closure to an open BOUNDARY preserves/opens future potential relative to attaching the same closure to already-closed CYCLE/PRODUCT structure. This is not called a jump.

## Test B — nonzero plateau

Primary persistence criterion, evaluated independently in each fresh context:

- H5, H6, H7 BOUNDARY mean-opening values must all exist;
- each must have n >= 5;
- `max(H5,H6,H7) - min(H5,H6,H7) <= 0.05 bit`;
- `mean(H5,H6,H7) >= 0.15 bit`.

This directly tests the proposed approximately 0.23-bit plateau while allowing the result to land elsewhere. A stable plateau at zero does not pass.

## Test C — pressure/opening coupling against an exact-floor null

Raw control rho is not the null.

For each observation at a fixed H,

`opening = log2(Omega_target / Omega_source)`

and because `Omega_target >= 1`, the exact row-wise mechanical lower bound is

`floor_i = -log2(Omega_source)`.

Decompose

`opening_i = floor_i + headroom_i`,

where

`headroom_i = log2(Omega_target) >= 0`.

The null keeps each row's `(pressure_i, floor_i)` fixed exactly and randomly permutes only the nonnegative `headroom` values across rows. Therefore any rho caused solely by pressure being correlated with how close the source already is to its opening floor is preserved by construction. The permutation destroys only pressure/headroom association beyond that floor effect.

This coupling gate is evaluated only at H=2 and H=3, where the prior graph had enough BOUNDARY observations to support a correlation test. In each fresh context and at both horizons:

- BOUNDARY n >= 20;
- observed Boundary rho >= 0.25;
- observed Boundary rho - median(floor-preserving null rho) >= 0.20;
- one-sided floor-preserving permutation p <= 0.01.

CYCLE and PRODUCT floor-null results are reported diagnostically but are not used as raw comparators in the pass rule.

## Reporting

The three claims are reported as three separate preregistered statuses:

1. closure-completion specificity;
2. nonzero H5-H7 plateau;
3. floor-corrected pressure/opening coupling.

There is deliberately no post-hoc composite "jump confirmed" status. The previous jump gate remains red regardless of V2.

No thresholds are to be changed after observing a valid V2 output.
