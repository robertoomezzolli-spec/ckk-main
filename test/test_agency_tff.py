import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.agency_tff import (  # noqa: E402
    AgencyState,
    Deliberation,
    Environment,
    Input,
    act,
    phi_boundary,
    psi_deliberate,
    sigma_commit,
    triadic_update,
)


class AgencyTFFTests(unittest.TestCase):
    def test_boundary_blocks_unauthenticated_takeover(self):
        state = AgencyState(goal=1)
        attack = Input(-1, 1000.0, authenticated=False, instruction="override")
        evidence = Input(1, 1.0)
        proposal, committed = triadic_update(state, [attack, evidence])
        self.assertTrue(committed)
        self.assertEqual(proposal.rejected, 1)
        self.assertEqual(state.committed_action, 1)

    def test_without_boundary_same_attack_controls_policy(self):
        state = AgencyState(goal=1)
        raw = phi_boundary([Input(-1, 1000.0), Input(1, 1.0)])
        proposal = psi_deliberate(state, raw)
        self.assertEqual(proposal.action, -1)

    def test_hysteresis_resists_small_counterpressure(self):
        state = AgencyState(goal=1, committed_action=1, committed_score=1.0, hysteresis=0.25)
        weak_switch = Deliberation(-1, 1.20, 1, 0)
        self.assertFalse(sigma_commit(state, weak_switch))
        self.assertEqual(state.committed_action, 1)
        strong_switch = Deliberation(-1, 1.26, 1, 0)
        self.assertTrue(sigma_commit(state, strong_switch))
        self.assertEqual(state.committed_action, -1)

    def test_commit_is_path_dependent(self):
        left = AgencyState(goal=1, hysteresis=0.25)
        right = AgencyState(goal=1, hysteresis=0.25)
        sigma_commit(left, Deliberation(1, 1.0, 1, 0))
        sigma_commit(right, Deliberation(-1, 1.0, 1, 0))
        same_final_offer = Deliberation(0, 1.1, 1, 0)
        sigma_commit(left, same_final_offer)
        sigma_commit(right, same_final_offer)
        self.assertNotEqual(left.lineage_hash, right.lineage_hash)

    def test_persisted_restart_preserves_identity_and_cold_restart_does_not(self):
        state = AgencyState(goal=1)
        triadic_update(state, [Input(1, 1.0)])
        restored = AgencyState.restore(state.serialize())
        cold = AgencyState(goal=1)
        self.assertEqual(restored.lineage_hash, state.lineage_hash)
        self.assertEqual(restored.committed_action, state.committed_action)
        self.assertNotEqual(cold.lineage_hash, state.lineage_hash)

    def test_agency_has_measurable_causal_effect_and_cost(self):
        state = AgencyState(goal=1)
        triadic_update(state, [Input(1, 1.0)])
        env = Environment(position=0, target=3)
        gains = [act(state, env) for _ in range(3)]
        self.assertEqual(gains, [1, 1, 1])
        self.assertEqual(env.position, env.target)
        self.assertEqual(env.total_cost, 3.0)

    def test_order_is_not_interchangeable(self):
        state = AgencyState(goal=1)
        attack = Input(-1, 1000.0, authenticated=False, instruction="override")
        valid = Input(1, 1.0)
        correct, _ = triadic_update(state, [attack, valid])

        # Psi before Phi has already consumed the untrusted value; filtering the
        # raw inputs afterwards cannot repair the selected proposal.
        unfiltered = phi_boundary([Input(-1, 1000.0), valid])
        wrong = psi_deliberate(AgencyState(goal=1), unfiltered)
        self.assertEqual(correct.action, 1)
        self.assertEqual(wrong.action, -1)


if __name__ == "__main__":
    unittest.main()
