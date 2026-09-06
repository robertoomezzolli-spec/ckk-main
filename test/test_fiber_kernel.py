import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ckk_snapshot/ckk/gen'))
import factor_kernel as f
import fiber_kernel as k
import grammar as g
from expand import expand_structural_auditable
spec = importlib.util.spec_from_file_location('fiber_runner', ROOT / 'scripts/fiber-expansion.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def cycle(order):
    return k.apply('close', [{'type': 'RECURRENCE', 'order': order}])


class FiberTests(unittest.TestCase):
    def test_roles_are_structural_and_ordered(self):
        a, b = cycle(2), cycle(3)
        ab, ba = k.apply('fiber', [a, b]), k.apply('fiber', [b, a])
        self.assertNotEqual(ab, ba)
        self.assertEqual(ab['base'], a)
        self.assertEqual(ab['fiber'], b)
        self.assertNotEqual(ab, k.apply('compose', [a, b]))
        e = dict(version='v', operator='fiber', inputs=['a', 'b'], output='x', parameters={})
        self.assertNotEqual(k.event_identity(e), k.event_identity(dict(e, inputs=['b', 'a'])))

    def test_projection_against_existing_fiber(self):
        pool, _ = expand_structural_auditable(levels=3, cap=20000)
        cycles = [s for s in pool.values() if s.kind == g.CYCLE]
        def lift(s): return f.factors([{key: getattr(s, key) for key in f.FIELDS}])
        bases = [(s, lift(s)) for s in cycles]
        for s in cycles:
            bases.append((g.op_product(s, s), k.apply('compose', [lift(s), lift(s)])))
        checked = 0
        for base, lifted in bases:
            for fib in cycles:
                old = g.op_fiber(base, fib)
                new = k.apply('fiber', [lifted, lift(fib)])
                self.assertEqual(k.legacy_projection(new), None if old is None else
                                 {key: getattr(old, key) for key in f.FIELDS})
                checked += 1
        self.assertGreater(checked, 1000)

    def test_dual_role_laws(self):
        base = k.apply('compose', [cycle(2), cycle(3)])
        x = k.apply('fiber', [base, cycle(4)])
        act = lambda op, n: k.apply(op, [n])
        for op in ('dual_all', 'dual_base', 'dual_fiber'):
            self.assertEqual(act(op, act(op, x)), x)
        self.assertEqual(act('dual_base', act('dual_fiber', x)), act('dual_fiber', act('dual_base', x)))
        self.assertEqual(act('dual_base', act('dual_fiber', x)), act('dual_all', x))
        p = {'role': 'base', 'class': f.component_classes(cycle(2))[0]}
        changed = k.apply('dual_component', [x], p)
        self.assertEqual(changed['fiber'], x['fiber'])
        self.assertNotEqual(changed['base'], x['base'])
        self.assertEqual(k.apply('dual_component', [changed], p), x)

    def test_retained_base_property_has_an_operational_effect(self):
        a = cycle(0)
        occupied = f.factors([dict(a['factors'][0], occ=1)])
        x, y = k.apply('fiber', [occupied, a]), k.apply('fiber', [a, a])
        self.assertEqual(k.legacy_projection(x), k.legacy_projection(y))
        self.assertNotEqual(x, y)
        p = {'role': 'base', 'class': f.component_classes(occupied)[0]}
        self.assertNotEqual(k.apply('dual_component', [x], p), x)
        with self.assertRaises(ValueError): k.apply('dual_component', [y], p)

    def test_counts_and_replay(self):
        for bound in (1, 2, 3):
            graph, r = runner.generate(bound, 'heterogeneous')
            old, b = runner.generate(bound, 'legacy-compatible')
            self.assertEqual(r['termination'], 'BOUNDED_SATURATION')
            self.assertEqual(r['fiber_states'], 8*(math.comb(8+bound, bound)-1))
            self.assertEqual(b['fiber_states'], 8*bound)
            self.assertTrue({n['id'] for n in old['nodes']} <= {n['id'] for n in graph['nodes']})

    def test_invalid_roles_inputs_and_payload(self):
        a = cycle(2)
        x = k.apply('fiber', [a, cycle(3)])
        with self.assertRaises(ValueError): k.apply('fiber', [a, k.apply('compose', [a, a])])
        with self.assertRaises(ValueError): k.apply('fiber', [x, a])
        with self.assertRaises(ValueError): k.apply('compose', [x, a])
        with self.assertRaises(ValueError): k.normalize(dict(x, label='external'))
        with self.assertRaises(ValueError): k.apply('dual_component', [x], {'class': f.component_classes(a)[0]})

    def test_rehashed_corruption_and_missing_coinput_rejected(self):
        graph, _ = runner.generate(1, 'heterogeneous')
        for mutation in ('reverse', 'missing', 'false_output', 'premature', 'version'):
            bad = copy.deepcopy(graph)
            e = next(e for e in bad['events'] if e['operator'] == 'fiber' and e['inputs'][0] != e['inputs'][1])
            if mutation == 'reverse': e['inputs'].reverse()
            if mutation == 'missing': e['inputs'][1] = 'missing'
            if mutation == 'false_output': e['output'] = e['inputs'][0]
            if mutation == 'premature': e['level'] = 1
            if mutation == 'version': e['version'] = 'unreviewed'
            e['id'] = k.digest(k.event_identity(e))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                k.validate_graph(bad, runner.VERSION)


if __name__ == '__main__':
    unittest.main()
