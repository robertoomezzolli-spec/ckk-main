#!/usr/bin/env python3
"""Reproducible domain-neutral diagnostics; no kernel edits or proposed new seeds."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ckk_snapshot/ckk/gen'))
import grammar as g
from expand import expand_structural_auditable

FIELDS = ('kind', 'dim', 'order', 'sym', 'sq', 'anti', 'mult', 'bc', 'dual', 'occ')
def sig(s):
    return {f: getattr(s, f) for f in FIELDS}

pool, raw = expand_structural_auditable(levels=5, cap=20000)
events = {e.event_key(): e for e in raw}.values()
states = list(pool.values())
used = {key for e in events for key in e.inputs}
unused = [sig(s) for s in g.SEEDS if s.structural_sig() not in used]
c0 = g.op_close(g.SEED_R)
c2 = g.op_close(next(s for s in g.SEED_Rn if s.order == 2))
c3 = g.op_close(next(s for s in g.SEED_Rn if s.order == 3))
finite = g.op_exclude(c0, g.SEED_C[0])
free = g.op_exclude(c0, g.SEED_C[1])
mixed_occ = g.op_product(finite, free)
unspecified_occ = g.op_product(c0, c0)
assert mixed_occ.structural_sig() == unspecified_occ.structural_sig()
assert mixed_occ.sig() != unspecified_occ.sig()
assert g.op_product(c2, c3) is None
assert g.op_product(c0, g.op_dual(c0)) is None
assert {s.order for s in states} == {0, 2, 3, 4}
assert all(s.bc is None for s in states)
assert all(g.op_degenerate(c0, s) is None for s in g.SEED_S if not s.anti)

transfers = {}
for e in events:
    inp = [pool[k] for k in e.inputs]
    out = pool[e.output]
    counts = transfers.setdefault(e.operator, {f: Counter() for f in FIELDS})
    for f in FIELDS:
        value = getattr(out, f)
        matches = [i for i, s in enumerate(inp) if getattr(s, f) == value]
        # Equality is observational only: max, constants and copying can coincide.
        key = 'equal_to_input_' + '_'.join(map(str, matches)) if matches else 'differs_from_all_inputs'
        counts[f][key] += 1

report = {
    'grammar_sha256': hashlib.sha256((ROOT / 'ckk_snapshot/ckk/gen/grammar.py').read_bytes()).hexdigest(),
    'scope': {'levels': 5, 'cap': 20000, 'states': len(states), 'unique_events': len(list(events))},
    'observed_orders': sorted({s.order for s in states}),
    'observed_boundary_conditions': [None],
    'unused_canonical_seeds_in_run': unused,
    'witnesses': {
        'mixed_recurrence_product': {'inputs': [sig(c2), sig(c3)], 'output': None},
        'mixed_dual_product': {'inputs': [sig(c0), sig(g.op_dual(c0))], 'output': None},
        'occupancy_factor_distinction': {
            'first_inputs': [sig(finite), sig(free)], 'second_inputs': [sig(c0), sig(c0)],
            'common_output_signature': sig(mixed_occ),
            'historical_parts_differ': True,
            'interpretation': 'The distinction survives in provenance but is unavailable to downstream scalar-only operators. This is a quotient design choice, not proof of an incorrect equivalence.'
        }
    },
    'property_equality_counts': transfers,
    'property_equality_warning': 'These are value comparisons, NOT native DIRECT/INHERITED verdicts or proof of causal inheritance.',
    'source_based_invariants': [
        'Starting with canonical seeds, order stays in {0,2,3,4}: close copies it, binary compositions require equality, and other operators preserve it.',
        'Starting with canonical seeds, bc remains None: no registered operator introduces a boundary-condition value. op_boundary changes kind/dimension instead.',
        'The two anti=False symmetry seeds are never accepted as symmetry arguments; increasing levels cannot activate them under this registry.',
        'Product/fiber reject unequal recurrence order or dual markers. More dimension does not remove these preconditions.',
        'All current operators inspect scalar fields (and canonical symmetry labels), not the parts tree. Retaining event history alone cannot make factor distinctions influence later structural applications.'
    ],
    'candidate_priority': [
        {'candidate': 'Explicit structural factor descriptors for heterogeneous composition',
         'reason': 'Represents combinations currently rejected or flattened without injecting domain names.',
         'required_decisions': ['Declare product semantics and structural equivalence before counting states.', 'Retain existing homogeneous behavior as a projection, not an assumed full equivalence.', 'Test associativity, factor reversal, dual action and replay on all co-inputs.', 'Keep experimental generation separate from the pinned core.'],
         'success_criterion': 'A previously unavailable factor distinction is preserved and supports a predefined downstream operation; extra labels or histories alone do not count.'},
        {'candidate': 'Recurrence composition', 'status': 'Requires declared algebra; lcm for periodic synchronous products is a model assumption, not something forced by the current order label.'},
        {'candidate': 'Action/composition of symmetry transformations', 'status': 'Requires a representation of actions and composition; merely adding symmetry labels would not establish new relations.'}
    ],
    'claim_limit': 'Identifies expressivity boundaries of this grammar. Does not establish which extension describes nature or predict a physical discovery.'
}
print(json.dumps(report, indent=2, sort_keys=True))
