import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.learning import LearningProposal  # noqa: E402
from ckk.sovereign.media import MediaEnvelope, MediaVault  # noqa: E402
from ckk.sovereign.organism import CognitionResult, SovereignOrganism  # noqa: E402
from ckk.sovereign.runtime import (  # noqa: E402
    CapabilityPolicy,
    IngressPolicy,
    Intent,
    Observation,
    SimulationActuator,
    SovereignRuntime,
)


CAP = "whatsapp.send"


def runtime():
    return SovereignRuntime(
        ingress=IngressPolicy(
            frozenset({"internal.clock", "whatsapp:owner"}),
            frozenset({"clock.tick", "message.text", "message.document", "message.image", "message.audio"}),
        ),
        capabilities=CapabilityPolicy(frozenset({CAP})),
        actuators={CAP: SimulationActuator(CAP)},
    )


class SilentBrain:
    def reflect(self, observations, memory, learned_context, laws):
        return CognitionResult(salience=0.2)


class LearningBrain:
    def reflect(self, observations, memory, learned_context, laws):
        return CognitionResult(
            intent=None,
            learning=(LearningProposal("self.name", "emergent", 0.9, (observations[0].observation_id,), "self-selected"),),
            salience=0.8,
        )


class SpeakingBrain:
    def reflect(self, observations, memory, learned_context, laws):
        return CognitionResult(Intent("send", CAP, {"text": "thought"}, "salient"), (), 0.9)


class SovereignOrganismTests(unittest.TestCase):
    def test_no_language_name_or_persona_is_bootstrapped(self):
        organism = SovereignOrganism(runtime(), SilentBrain())
        self.assertEqual(organism.learner.context(), {})
        self.assertFalse(hasattr(organism.laws, "language"))
        self.assertFalse(hasattr(organism.laws, "persona"))
        self.assertFalse(hasattr(organism.laws, "name"))

    def test_time_is_a_sense_and_thought_may_end_in_silence(self):
        organism = SovereignOrganism(runtime(), SilentBrain())
        organism.clock_tick("tick:1", 100)
        self.assertIsNone(organism.think())
        commit = organism.sleep()
        self.assertEqual(commit.sequence, 1)
        self.assertNotEqual(organism.identity, "0" * 64)

    def test_self_selected_name_only_exists_after_sleep_commit(self):
        organism = SovereignOrganism(runtime(), LearningBrain())
        organism.perceive(Observation("wa:1", "whatsapp:owner", "message.text", {"text": "choose"}, 1.0))
        organism.think()
        self.assertNotIn("self.name", organism.learner.context())
        organism.sleep()
        self.assertEqual(organism.learner.context()["self.name"], "emergent")

    def test_learning_cannot_cite_uncommitted_evidence(self):
        class ForgingBrain:
            def reflect(self, observations, memory, learned_context, laws):
                return CognitionResult(learning=(LearningProposal("self.name", "x", 1.0, ("not-seen",), "forge"),))

        organism = SovereignOrganism(runtime(), ForgingBrain())
        organism.clock_tick("tick:1", 100)
        with self.assertRaises(PermissionError):
            organism.think()
        self.assertEqual(organism.runtime.memory, [])
        self.assertEqual(organism.identity_history, [])

    def test_brain_can_speak_but_only_through_registered_actuator(self):
        organism = SovereignOrganism(runtime(), SpeakingBrain())
        effect = organism.think()
        self.assertTrue(effect.simulated)
        self.assertEqual(effect.output["would_execute"], "send")

    def test_media_vault_checks_type_size_and_hash(self):
        content = b"paper"
        digest = hashlib.sha256(content).hexdigest()
        vault = MediaVault(maximum_bytes=10)
        artifact = vault.admit(MediaEnvelope("m1", "paper.pdf", "application/pdf", digest), content)
        self.assertEqual(vault.read(artifact.artifact_id), content)
        with self.assertRaises(ValueError):
            vault.admit(MediaEnvelope("m2", "bad.pdf", "application/pdf", "wrong"), content)
        with self.assertRaises(PermissionError):
            vault.admit(MediaEnvelope("m3", "run.exe", "application/x-msdownload", digest), content)


if __name__ == "__main__":
    unittest.main()
