import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ckk_snapshot/ckk/gen'))
import factor_kernel as k
import grammar as g
from expand import expand_structural_auditable

spec = importlib.util.spec_from_file_location('factor_runner', ROOT / 'scripts/factor-expansion.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def cycle(order):
    return k.apply('close', [{'type': 'RECURRENCE', 'order': order}])


class FactorKernelTests(unittest.TestCase):
    def test_multiset_identity_and_composition_laws(self):
        a, b, c = map(cycle, (0, 2, 3))
        compose = lambda x, y: k.apply('compose', [x, y])
        self.assertEqual(compose(a, b), compose(b, a))
        self.assertEqual(compose(compose(a, b), c), compose(a, compose(b, c)))
        self.assertNotEqual(compose(a, a), a)
        with self.assertRaises(ValueError):
            k.factors([])

    def test_dual_laws_and_class_action(self):
        a, b = cycle(2), cycle(3)
        ab = k.apply('compose', [a, b])
        dual = lambda n: k.apply('dual_all', [n])
        self.assertEqual(dual(dual(ab)), ab)
        self.assertEqual(dual(ab), k.apply('compose', [dual(a), dual(b)]))
        pa, pb = ({'class': k.component_classes(n)[0]} for n in (a, b))
        act = lambda n, p: k.apply('dual_component', [n], p)
        self.assertEqual(act(act(ab, pa), pa), ab)
        self.assertEqual(act(act(ab, pa), pb), act(act(ab, pb), pa))
        self.assertEqual(act(ab, pa), k.apply('compose', [dual(a), b]))
        # Equal copies are not addressable by arbitrary provenance position.
        aa = k.apply('compose', [a, a])
        self.assertEqual(act(aa, pa), dual(aa))

    def test_projection_against_unchanged_legacy_operators(self):
        pool, _ = expand_structural_auditable(levels=3, cap=20000)
        cycles = [s for s in pool.values() if s.kind == g.CYCLE]
        def lift(s):
            return k.factors([{f: getattr(s, f) for f in k.FIELDS}])
        checked = 0
        for a in cycles:
            self.assertEqual(k.legacy_projection(k.apply('dual_all', [lift(a)])),
                             {f: getattr(g.op_dual(a), f) for f in k.FIELDS})
            for b in cycles:
                old = g.op_product(a, b)
                projected = k.legacy_projection(k.apply('compose', [lift(a), lift(b)]))
                self.assertEqual(projected, None if old is None else {f: getattr(old, f) for f in k.FIELDS})
                checked += 1
        self.assertGreater(checked, 100)

    def test_factor_distinction_is_available_to_downstream_action(self):
        c = g.op_close(g.SEED_R)
        lift = lambda s: k.factors([{f: getattr(s, f) for f in k.FIELDS}])
        finite, free = (lift(g.op_exclude(c, carrier)) for carrier in g.SEED_C)
        mixed = k.apply('compose', [finite, free])
        unspecified = k.apply('compose', [lift(c), lift(c)])
        self.assertEqual(k.legacy_projection(mixed), k.legacy_projection(unspecified))
        self.assertNotEqual(mixed, unspecified)
        p = {'class': k.component_classes(finite)[0]}
        changed = k.apply('dual_component', [mixed], p)
        self.assertEqual(sorted((f['occ'], f['dual']) for f in changed['factors']), [(-1, 0), (1, 1)])
        with self.assertRaises(ValueError):
            k.apply('dual_component', [unspecified], p)

    def test_counts_against_independent_multiset_formula_and_seed_replay(self):
        for bound in (2, 3, 4):
            graph, report = runner.generate(bound, 'heterogeneous')
            self.assertEqual(report['termination'], 'BOUNDED_SATURATION')
            self.assertEqual(report['factor_states'], math.comb(8+bound, bound)-1)
            old, baseline = runner.generate(bound, 'legacy-compatible')
            self.assertEqual(baseline['factor_states'], 8*bound)
            self.assertTrue({n['id'] for n in old['nodes']} <= {n['id'] for n in graph['nodes']})

    def test_adversarial_replay(self):
        initial, _ = runner.generate(2, 'heterogeneous')
        for mutation in ('operator', 'parent', 'output', 'level', 'seed', 'duplicate', 'version'):
            graph = copy.deepcopy(initial)
            e = graph['events'][0]
            if mutation == 'operator': e['operator'] = 'unknown'
            if mutation == 'parent': e['inputs'][0] = 'missing'
            if mutation == 'output': e['output'] = graph['admitted'][0]
            if mutation == 'level': e['level'] = 0
            if mutation == 'seed': graph['admitted'] = graph['admitted'][:-1]
            if mutation == 'duplicate': graph['events'].append(copy.deepcopy(e))
            if mutation == 'version': e['version'] = 'other'
            e['id'] = k.digest(k.event_identity(e))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                k.validate_graph(graph, runner.VERSION)

    def test_schema_rejects_hidden_fields_and_invalid_parameters(self):
        a = cycle(2)
        a['factors'][0]['label'] = 'external meaning'
        with self.assertRaises(ValueError): k.normalize(a)
        with self.assertRaises(ValueError): k.apply('compose', [cycle(2)])
        with self.assertRaises(ValueError): k.apply('dual_all', [cycle(2)], {'override': True})
        with self.assertRaises(ValueError): k.apply('close', [{'type': 'RECURRENCE', 'order': True}])
        cls = k.component_classes(cycle(2))[0]
        cls['dim'] = True
        with self.assertRaises(ValueError): k.apply('dual_component', [cycle(2)], {'class': cls})

    def test_fixed_points_follow_explicit_multiset_equivalence(self):
        a = cycle(2)
        dual = k.apply('dual_all', [a])
        pair = k.apply('compose', [a, dual])
        self.assertEqual(k.apply('dual_all', [pair]), pair)
        self.assertNotEqual(a, dual)
        self.assertEqual({f['dual'] for f in pair['factors']}, {0, 1})

    def test_budget_stop_is_not_saturation(self):
        graph, report = runner.generate(4, 'heterogeneous', max_nodes=12)
        self.assertEqual(report['termination'], 'NODE_BUDGET')
        self.assertLessEqual(len(graph['nodes']), 12)
        self.assertTrue(report['validation']['clean'])


if __name__ == '__main__':
    unittest.main()
