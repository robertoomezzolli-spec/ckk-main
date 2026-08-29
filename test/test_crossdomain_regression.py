import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_regression_module():
    path = ROOT / "scripts" / "crossdomain-regression.py"
    spec = importlib.util.spec_from_file_location("crossdomain_regression", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CrossDomainRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_regression_module()
        cls.report = cls.module.build_report()

    def test_true_confluence_definition_uses_distinct_events(self):
        metrics = self.report["domains"]["physics"]["current_core_diagnostic"]
        self.assertIn("distinct DerivationEvent", metrics["confluence_definition"])
        self.assertLessEqual(metrics["true_derivational_confluences"], metrics["structural_states"])

    def test_current_core_information_loss_repairs_hold(self):
        invariants = self.report["core_invariants"]
        self.assertEqual("PASS", invariants["fiber_order_compatibility"]["status"])
        self.assertEqual("PASS", invariants["product_dual_factor_preservation"]["status"])
        self.assertEqual("PASS", invariants["fiber_dual_factor_preservation"]["status"])
        metrics = self.report["domains"]["physics"]["current_core_diagnostic"]
        self.assertEqual(0, metrics["cross_order_fiber_events"])
        self.assertEqual(0, metrics["mixed_dual_product_events"])
        self.assertEqual(0, metrics["mixed_dual_fiber_events"])
        self.assertEqual(0, metrics["self_transition_events"])

    def test_selfduality_remains_not_evaluated(self):
        self.assertEqual("NOT_EVALUATED", self.report["core_invariants"]["dual_structural_roundtrip"]["selfduality"])
        self.assertEqual("NOT_EVALUATED", self.report["run34"]["selfduality"])

    def test_missing_domains_are_not_executed(self):
        for domain in ("chemistry", "biology", "computation"):
            row = self.report["domains"][domain]
            self.assertEqual("BLOCKED_PARTIAL_HISTORICAL_ARTIFACT", row["regression"])
            self.assertEqual("NOT_RUN_WITHOUT_EXECUTABLE_SEEDS", row["current_core_diagnostic"])

    def test_failed_gate_forbids_new_generation(self):
        self.assertFalse(self.report["new_generation"]["eligible"])
        self.assertFalse(self.report["new_generation"]["created"])
        self.assertEqual("BLOCKED_MISSING_GOLDEN_BASELINE", self.report["domains"]["physics"]["regression"])
        self.assertTrue(self.report["run34"]["unchanged"])


if __name__ == "__main__":
    unittest.main()
