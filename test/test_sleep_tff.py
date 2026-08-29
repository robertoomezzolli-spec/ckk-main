import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.sleep_tff import Experience, SleepAgent, run_comparison  # noqa: E402


HOLDOUT = (Experience(0, -1), Experience(1, 1))


class SleepTFFTests(unittest.TestCase):
    def test_isolation_rejects_external_input(self):
        agent = SleepAgent(awake=False)
        with self.assertRaises(RuntimeError):
            agent.wake_learn(Experience(0, -1))

    def test_always_on_drifts_but_circadian_agent_consolidates(self):
        result = run_comparison()
        self.assertGreater(result["always_on_peak_error"], 0.0)
        self.assertEqual(result["circadian_peak_error"], 0.0)
        self.assertGreater(result["always_on_error"], result["circadian_error"])

    def test_sleep_preserves_committed_identity(self):
        agent = SleepAgent()
        for item in HOLDOUT:
            agent.commit_experience(item)
        identity = agent.identity_hash
        agent.wake_learn(Experience(0, -1))
        self.assertTrue(agent.sleep(HOLDOUT))
        self.assertEqual(agent.identity_hash, identity)

    def test_rem_rolls_back_harmful_consolidation(self):
        agent = SleepAgent(weights=[-1.0, 1.0])
        for item in HOLDOUT:
            agent.commit_experience(item)
        before = agent.weights[:]
        self.assertFalse(agent.sleep(HOLDOUT, sabotage=True))
        self.assertEqual(agent.weights, before)
        self.assertEqual(agent.rollbacks, 1)

    def test_cold_reboot_loses_identity_but_persisted_clone_does_not(self):
        agent = SleepAgent()
        agent.commit_experience(Experience(0, -1))
        persisted = agent.clone()
        cold = SleepAgent()
        self.assertEqual(persisted.identity_hash, agent.identity_hash)
        self.assertNotEqual(cold.identity_hash, agent.identity_hash)


if __name__ == "__main__":
    unittest.main()
