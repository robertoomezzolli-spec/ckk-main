import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from functools import lru_cache
from math import comb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ckk_snapshot/ckk/gen'))
import boundary_kernel as k
import factor_kernel as f
import grammar as g
from expand import expand_structural_auditable
spec = importlib.util.spec_from_file_location('boundary_runner', ROOT / 'scripts/boundary-expansion.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def cycle(order):
    return k.apply('close', [{'type': 'RECURRENCE', 'order': order}])


class BoundaryTests(unittest.TestCase):
    def test_product_boundary_fiber_path_preserves_every_factor(self):
        a, b, c = map(cycle, (2, 3, 4))
        product = k.apply('compose', [a, b])
        boundary = k.apply('boundary', [product])
        fiber = k.apply('fiber', [boundary, c])
        final = k.apply('boundary', [fiber])
        self.assertEqual(boundary['carrier'], product)
        self.assertEqual(fiber['base'], boundary)
        self.assertEqual(fiber['fiber'], c)
        self.assertEqual([k.dimension(n) for n in (product, boundary, fiber, final)], [2, 1, 1, 0])
        self.assertEqual(k.measure(final), (3, 3))

    def test_normal_forms_do_not_remember_factor_order_or_parenthesization(self):
        a, b, c = map(cycle, (0, 2, 3))
        compose = lambda x, y: k.apply('compose', [x, y])
        left = k.apply('boundary', [compose(compose(a, b), c)])
        right = k.apply('boundary', [compose(c, compose(b, a))])
        self.assertEqual(left, right)

    def test_projection_matches_old_boundary_and_fiber_on_boundary(self):
        pool, _ = expand_structural_auditable(levels=3, cap=20000)
        cycles = [s for s in pool.values() if s.kind == g.CYCLE]
        lift = lambda s: f.factors([{key: getattr(s, key) for key in f.FIELDS}])
        checked = 0
        for s in cycles:
            for old_carrier, carrier in (
                (g.op_product(s, s), k.apply('compose', [lift(s), lift(s)])),
                (g.op_fiber(s, s), k.apply('fiber', [lift(s), lift(s)]))):
                old_boundary = g.op_boundary(old_carrier)
                boundary = k.apply('boundary', [carrier])
                self.assertEqual(k.legacy_projection(boundary), {key: getattr(old_boundary, key) for key in f.FIELDS})
                for fib in cycles:
                    old = g.op_fiber(old_boundary, fib)
                    new = k.apply('fiber', [boundary, lift(fib)])
                    self.assertEqual(k.legacy_projection(new), None if old is None else {key: getattr(old, key) for key in f.FIELDS})
                    checked += 1
        self.assertGreater(checked, 1000)

    def test_dual_commuting_square_and_intrinsic_selector(self):
        product = k.apply('compose', [cycle(2), cycle(3)])
        bd = k.apply('boundary', [product])
        dual = lambda n: k.apply('dual_all', [n])
        self.assertEqual(dual(bd), k.apply('boundary', [dual(product)]))
        self.assertEqual(dual(dual(bd)), bd)
        fiber = k.apply('fiber', [bd, cycle(4)])
        selector = next(s for s in k.selectors(fiber) if s['path'] == ['base', 'carrier'] and s['class']['order'] == 2)
        changed = k.apply('dual_component', [fiber], selector)
        self.assertEqual(changed['fiber'], fiber['fiber'])
        self.assertEqual(k.dimension(changed), k.dimension(fiber))
        self.assertNotEqual(changed['base'], fiber['base'])
        self.assertEqual(k.apply('dual_component', [changed], selector), fiber)

    def test_zero_rank_tower_is_distinguished_from_dimension_growth(self):
        c = cycle(2)
        bd = k.apply('boundary', [k.apply('fiber', [c, c])])
        next_bd = k.apply('boundary', [k.apply('fiber', [bd, c])])
        self.assertEqual(k.dimension(bd), 0)
        self.assertEqual(k.dimension(next_bd), 0)
        self.assertNotEqual(bd, next_bd)
        self.assertGreater(k.measure(next_bd)[1], k.measure(bd)[1])
        self.assertEqual(k.legacy_projection(bd), k.legacy_projection(next_bd))

    def test_bad_rank_carrier_and_selector_are_rejected(self):
        c = cycle(2)
        with self.assertRaises(ValueError): k.apply('boundary', [c])
        bd = k.apply('boundary', [k.apply('compose', [c, c])])
        with self.assertRaises(ValueError): k.normalize(dict(bd, rank=999))
        with self.assertRaises(ValueError): k.normalize(dict(bd, rank=True))
        with self.assertRaises(ValueError): k.apply('boundary', [bd])
        with self.assertRaises(ValueError): k.normalize(dict(bd, interpretation='external'))
        with self.assertRaises(ValueError): k.apply('dual_component', [bd], {'path': [], 'class': f.component_classes(c)[0]})

    def test_runner_replay_and_resource_termination(self):
        graph, report = runner.generate('heterogeneous', leaves=2, depth=2)
        self.assertEqual(report['termination'], 'BOUNDED_SATURATION')
        self.assertTrue(report['validation']['clean'])
        self.assertEqual(report['kinds'], {'RECURRENCE': 4, 'FACTORS': 44, 'FIBER': 64, 'BOUNDARY': 100})
        # Independent counting of the declared constructor language, without
        # generating, hashing or applying operators.
        @lru_cache(None)
        def relative(kind, leaves, depth):
            if depth < 1 or leaves < 1:
                return 0
            if kind == 'FIBER':
                return 0 if leaves < 2 else 8*(comb(8+leaves-2, leaves-1) + relative('BOUNDARY', leaves-1, depth-1))
            return (comb(8+leaves-1, leaves) if leaves >= 2 else 0) + relative('FIBER', leaves, depth-1)
        self.assertEqual(report['kinds']['BOUNDARY'], sum(relative('BOUNDARY', n, 2) for n in (1, 2)))
        self.assertEqual(report['kinds']['FIBER'], sum(relative('FIBER', n, 2) for n in (1, 2)))
        _, truncated = runner.generate('heterogeneous', leaves=3, depth=3, max_nodes=12)
        self.assertEqual(truncated['termination'], 'NODE_BUDGET')
        self.assertLessEqual(truncated['nodes'], 12)
        for mutation in ('input', 'output', 'level', 'operator', 'seed', 'version'):
            bad = copy.deepcopy(graph)
            e = next(e for e in bad['events'] if e['operator'] == 'boundary')
            if mutation == 'input': e['inputs'][0] = 'missing'
            if mutation == 'output': e['output'] = e['inputs'][0]
            if mutation == 'level': e['level'] = 1
            if mutation == 'operator': e['operator'] = 'unknown'
            if mutation == 'seed': bad['admitted'] = bad['admitted'][:-1]
            if mutation == 'version': e['version'] = 'unsupported'
            e['id'] = k.digest(k.event_identity(e))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                k.validate_graph(bad, runner.VERSION)

    def test_previous_fiber_dialect_translates_without_changing_outputs(self):
        import fiber_kernel as previous
        a, b = cycle(2), cycle(3)
        values = [a, k.apply('compose', [a, b]), previous.apply('fiber', [a, b])]
        for node in values:
            self.assertEqual(k.normalize(node), previous.normalize(node))
            self.assertEqual(k.apply('dual_all', [node]), previous.apply('dual_all', [node]))
            if node['type'] == 'FIBER':
                for role in ('base', 'fiber'):
                    cls = f.component_classes(node[role])[0]
                    self.assertEqual(k.apply('dual_component', [node], {'path': [role], 'class': cls}),
                                     previous.apply('dual_component', [node], {'role': role, 'class': cls}))
            else:
                cls = f.component_classes(node)[0]
                self.assertEqual(k.apply('dual_component', [node], {'path': [], 'class': cls}),
                                 previous.apply('dual_component', [node], {'class': cls}))


if __name__ == '__main__':
    unittest.main()
