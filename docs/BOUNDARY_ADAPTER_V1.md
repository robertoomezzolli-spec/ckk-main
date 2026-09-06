# Boundary adaptation: rule contract

This contract is written before the paired boundary experiment. It adapts the
existing rank-lowering `op_boundary`; it does not define a geometric boundary.
All previously published kernel modules remain unchanged.

## Representation

BOUNDARY has exactly `type`, `carrier`, and `rank`. Its carrier is a PRODUCT
(a FACTORS state with at least two factors) or a FIBER state. Rank must equal
`max(dimension(carrier)-1, 0)`. Dimension of a FACTORS state is its factor count;
dimension of FIBER is the dimension of its base; dimension of BOUNDARY is rank.

Every carrier descriptor is retained. No factor is arbitrarily deleted, no
orientation or gluing relation is chosen, and no equation such as boundary
squared equals zero is asserted. Applying boundary directly to BOUNDARY is
inadmissible, as in the old kernel.

FIBER now accepts a BOUNDARY base, retaining the ordered base/fiber roles and a
singleton fiber. Direct FIBER-on-FIBER remains inadmissible. Thus the existing
route PRODUCT -> BOUNDARY -> FIBER -> BOUNDARY is executable.

Equality is equality of canonical relative structural descriptors. The retained
carrier is an explicit part of this experimental structure, not an event ID or
an arbitrary historical label. Associative/commutative factor normal forms
remain in force. Two different retained incidence trees are not assumed equal
merely because their legacy scalar projections agree.

This is a modeling choice: it constructs relative carrier/rank descriptors.
It does not establish that all such distinctions are necessary in nature.
Alternating fiber and boundary can keep adding incidence at rank zero. Such
growth must be reported separately from rank growth and is not evidence of new
physical dimensions. No automatic quotient of those towers is assumed.

## Dual actions

Dual transport preserves the relative carrier/rank relationship and toggles
factor markers in the selected structural role. Component selectors are paths
through intrinsic roles (`carrier`, `base`, `fiber`) followed by a factor class,
never event history or arbitrary positions of identical factors. The path and
class are invariant under the selected action, making it an involution.

Global dual transport on BOUNDARY is a new rule of this experimental dialect;
the old kernel does not directly admit `op_dual(BOUNDARY)`. Its compatibility
check is instead the derived old path boundary(dual(carrier)). Global duality
commutes with boundary in this representation. Fiber role actions are lifted
through a BOUNDARY base by transporting its carrier.

## Planned gates

1. Compare scalar projections with old boundary and fiber-on-boundary outputs
   for generated homogeneous examples, including rank zero.
2. Check normal-form equality, role preservation, dual involution, and the
   boundary/dual commuting square.
3. Reject fabricated ranks, unsupported carriers, bad selector paths, missing
   co-inputs, false outputs and unadmitted seeds even when hashes are recomputed.
4. Run identical seed sets and explicit leaf/depth/resource budgets. The two
   arms differ only in whether a legacy-compatible scalar projection is required.
   This control is not claimed to be the entire old eleven-operator generator.
5. Replay every recorded application; distinguish finite budget saturation from
   a truncated run. Preserve a full PRODUCT -> BOUNDARY -> FIBER witness.

The kernel does not impose leaf or depth bounds. These are experiment-runner
controls. Source hashes will pin the result. Domain interpretation, native
DIRECT/INHERITED labels, production data and the UI are outside this sprint.
