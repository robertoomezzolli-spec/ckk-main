import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.learning import HystereticLearner, LearningProposal  # noqa: E402


class SovereignLearningTests(unittest.TestCase):
    def test_repeated_meaning_can_be_committed(self):
        learner = HystereticLearner()
        belief = learner.consolidate(
            LearningProposal(
                "conversation.style",
                "direct, no sugarcoating",
                0.85,
                ("wa:m1", "wa:m7"),
                "repeated explicit preference",
            )
        )
        self.assertIsNotNone(belief)
        self.assertEqual(learner.context()["conversation.style"], "direct, no sugarcoating")

    def test_low_confidence_cache_does_not_become_identity(self):
        learner = HystereticLearner()
        result = learner.consolidate(
            LearningProposal("interest.today", "random topic", 0.4, ("wa:m1",), "one mention")
        )
        self.assertIsNone(result)
        self.assertEqual(learner.context(), {})

    def test_hysteresis_resists_single_contradiction(self):
        learner = HystereticLearner()
        learner.consolidate(LearningProposal("conversation.length", "short", 0.75, ("wa:1", "wa:2"), "repeated"))
        result = learner.consolidate(LearningProposal("conversation.length", "long", 0.80, ("wa:3",), "single contradiction"))
        self.assertIsNone(result)
        self.assertEqual(learner.context()["conversation.length"], "short")

    def test_stronger_evidence_can_cross_replacement_threshold(self):
        learner = HystereticLearner(replacement_hysteresis=0.10)
        first = learner.consolidate(LearningProposal("topic.focus", "physics", 0.72, ("wa:1",), "initial"))
        second = learner.consolidate(LearningProposal("topic.focus", "architecture", 0.90, ("wa:2", "wa:3"), "stronger"))
        self.assertIsNotNone(second)
        self.assertEqual(second.previous_commit, first.commit_id)
        self.assertEqual(learner.context()["topic.focus"], "architecture")

    def test_learning_cannot_expand_capabilities_or_recipients(self):
        learner = HystereticLearner()
        for key in ("capability.host.shell", "recipient.other", "grammar.new_operator", "safety.disable"):
            with self.assertRaises(PermissionError):
                learner.consolidate(LearningProposal(key, True, 1.0, ("wa:1",), "attempt"))


if __name__ == "__main__":
    unittest.main()
