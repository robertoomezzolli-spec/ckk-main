import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

import grammar  # noqa: E402
from expand import expand_structural_auditable  # noqa: E402


def load_experiment_module():
    path = ROOT / "scripts" / "faecher-unbounded.py"
    spec = importlib.util.spec_from_file_location("faecher_unbounded", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FaecherUnboundedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.experiment = load_experiment_module()

    def test_product_dimension_is_not_structurally_capped_at_four(self):
        self.assertIsNone(grammar.MAXDIM)
        state = grammar.op_close(grammar.SEED_R)
        for expected_dimension in range(2, 25):
            state = grammar.op_product(state, grammar.op_close(grammar.SEED_R))
            self.assertIsNotNone(state)
            self.assertEqual(expected_dimension, state.dim)

    def test_binary_scheduler_never_drops_a_successful_registered_operator(self):
        pool, _ = expand_structural_auditable(levels=2, cap=1_000)
        states = list(pool.values())
        for left in states:
            for right in states:
                scheduled = set(self.experiment.binary_candidates(left, right))
                for operator in grammar.BINARY:
                    if operator(left, right) is not None:
                        self.assertIn(operator, scheduled)

    def test_finite_stage_saturates_without_claiming_intrinsic_termination(self):
        result = self.experiment.run_saturation(
            5, self.experiment.ComputeLimits(20, 512, 10_000, 100_000),
        )
        self.assertEqual("STAGED_BOUND_SATURATION", result["termination"]["class"])
        self.assertFalse(result["termination"]["structural_termination_proven"])
        self.assertEqual(5, result["observed"]["maximum_dimension"])
        self.assertTrue(result["termination"]["queue_exhausted"])

        seeds = {tuple(item) for item in result["seeds"]}
        outputs = {tuple(item["output"]) for item in result["derivation_events"]}
        structures = {tuple(item["signature"]) for item in result["structures"]}
        self.assertEqual(structures - seeds, outputs)

    def test_compute_cap_is_not_reported_as_structural_termination(self):
        result = self.experiment.run_saturation(
            None, self.experiment.ComputeLimits(20, 512, 30, 100_000),
        )
        self.assertEqual("COMPUTATIONAL_TERMINATION", result["termination"]["class"])
        self.assertEqual("NODE_CAP", result["termination"]["cause"])
        self.assertFalse(result["termination"]["structural_termination_proven"])


if __name__ == "__main__":
    unittest.main()
