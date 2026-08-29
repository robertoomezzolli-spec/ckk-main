import sys
import unittest
from pathlib import Path

GEN = Path(__file__).resolve().parents[1] / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

from grammar import (  # noqa: E402
    BINARY,
    CYCLE,
    SEED_R,
    SEED_Rn,
    SEED_S,
    UNARY,
    op_close,
    op_degenerate,
    op_dual,
    op_fiber,
    op_product,
)
from expand import (  # noqa: E402
    Derivation,
    derivational_confluences,
    expand,
    expand_auditable,
    expand_structural_auditable,
)


class GeneratorCoreTests(unittest.TestCase):
    def test_selfdual_operator_is_absent(self):
        names = {op.__name__ for op in UNARY + BINARY}
        self.assertNotIn("op_selfdual", names)

    def test_dual_is_true_roundtrip_on_signature(self):
        x = op_close(SEED_R)
        self.assertIsNotNone(x)
        d1 = op_dual(x)
        d2 = op_dual(d1)
        self.assertEqual(d1.dual, 1)
        self.assertEqual(d2.dual, 0)
        self.assertEqual(d2.sig(), x.sig())
        self.assertEqual(d2.structural_sig(), x.structural_sig())

    def test_fiber_rejects_cross_order_inputs(self):
        base = op_close(SEED_R)
        fiber = op_close(SEED_Rn[0])
        self.assertNotEqual(base.order, fiber.order)
        self.assertIsNone(op_fiber(base, fiber))

    def test_product_rejects_mixed_dual_inputs(self):
        x = op_close(SEED_R)
        dx = op_dual(x)
        self.assertIsNone(op_product(x, dx))
        same_branch = op_product(dx, dx)
        self.assertIsNotNone(same_branch)
        self.assertEqual(same_branch.dual, 1)

    def test_fiber_rejects_mixed_dual_inputs(self):
        x = op_close(SEED_R)
        dx = op_dual(x)
        self.assertIsNone(op_fiber(x, dx))
        same_branch = op_fiber(dx, dx)
        self.assertIsNotNone(same_branch)
        self.assertEqual(same_branch.dual, 1)

    def test_structural_signature_does_not_encode_provenance(self):
        x = op_close(SEED_R)
        d = op_dual(x)
        self.assertNotEqual(x.structural_sig(), d.structural_sig())
        self.assertEqual(len(x.structural_sig()), 10)
        self.assertEqual(len(d.structural_sig()), 10)

    def test_antiunitary_plus_one_is_not_labeled_degenerate(self):
        x = op_close(SEED_R)
        anti_plus = next(s for s in SEED_S if s.anti and s.sq == 1)
        r = op_degenerate(x, anti_plus)
        self.assertIsNotNone(r)
        self.assertEqual(r.mult, 1)
        self.assertEqual(r.label, "antiunitary")

    def test_kramers_branch_remains_double(self):
        x = op_close(SEED_R)
        anti_minus = next(s for s in SEED_S if s.anti and s.sq == -1)
        r = op_degenerate(x, anti_minus)
        self.assertIsNotNone(r)
        self.assertEqual(r.mult, 2)
        self.assertEqual(r.label, "degenerate")

    def test_auditable_mode_preserves_historical_node_set(self):
        legacy_pool, legacy_edges = expand()
        audit_pool, derivations = expand_auditable()
        self.assertEqual(set(legacy_pool), set(audit_pool))
        self.assertGreater(len(derivations), 0)
        self.assertGreater(len(legacy_edges), 0)

    def test_binary_arity_is_one_derivation_event(self):
        x = op_close(SEED_R)
        y = op_product(x, x)
        d = Derivation("op_product", (x.sig(), x.sig()), y.sig(), 1)
        self.assertEqual(len(d.inputs), 2)
        self.assertEqual(len({d.event_key()}), 1)

    def test_commutative_product_reversal_has_same_event_identity(self):
        x = op_close(SEED_R)
        y = op_product(x, x)
        a = Derivation("op_product", (x.sig(), x.sig()), y.sig(), 1)
        b = Derivation("op_product", tuple(reversed(a.inputs)), y.sig(), 1)
        self.assertEqual(a.event_key(), b.event_key())

    def test_duplicate_event_does_not_create_confluence(self):
        x = op_close(SEED_R)
        y = op_product(x, x)
        event = Derivation("op_product", (x.sig(), x.sig()), y.sig(), 1)
        self.assertEqual(derivational_confluences([event, event]), {})

    def test_two_distinct_derivations_do_create_confluence(self):
        x = op_close(SEED_R)
        y = op_dual(x)
        target = ("TARGET",)
        d1 = Derivation("op_alpha", (x.sig(),), target, 1)
        d2 = Derivation("op_beta", (y.sig(),), target, 2)
        c = derivational_confluences([d1, d2])
        self.assertIn(target, c)
        self.assertEqual(len(c[target]), 2)

    def test_structural_mode_is_separate_and_auditable(self):
        historical_pool, _ = expand_auditable()
        structural_pool, derivations = expand_structural_auditable()
        self.assertGreater(len(derivations), 0)
        self.assertLessEqual(len(structural_pool), len(historical_pool))

    def test_idempotent_operations_do_not_emit_self_transitions(self):
        _, derivations = expand_structural_auditable(levels=2)
        self.assertFalse(any(event.output in event.inputs for event in derivations))


if __name__ == "__main__":
    unittest.main()
