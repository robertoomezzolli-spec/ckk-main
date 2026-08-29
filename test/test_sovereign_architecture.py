import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
CKK = ROOT / "ckk_snapshot"
sys.path.insert(0, str(GEN))
sys.path.insert(0, str(CKK))

from grammar import SEED_R, op_close, op_dual  # noqa: E402
from ckk.sovereign.architecture import (  # noqa: E402
    Evidence,
    Phase,
    SovereignFan,
    Status,
)


def accept(candidate, committed):
    return Evidence("ACCEPT", 1.0, f"checked against {len(committed)} commits")


class SovereignArchitectureTests(unittest.TestCase):
    def test_generator_is_isolated_and_evidence_blind(self):
        fan = SovereignFan()
        with self.assertRaises(RuntimeError):
            fan.generate(op_close(SEED_R), "op_close")
        fan.isolate()
        with self.assertRaises(RuntimeError):
            fan.generate(
                op_close(SEED_R), "op_close", evidence=Evidence("ACCEPT", 1.0)
            )

    def test_equal_morphology_different_history_is_not_merged(self):
        x = op_close(SEED_R)
        fan = SovereignFan()
        fan.isolate()
        direct = fan.generate(x, "direct", ("seed",))
        returned = fan.generate(op_dual(op_dual(x)), "dual_roundtrip", ("seed",))
        self.assertEqual(direct.morphology_id, returned.morphology_id)
        self.assertEqual(direct.structure.sig(), returned.structure.sig())
        self.assertNotEqual(direct.lineage_id, returned.lineage_id)
        fan.nrem()
        self.assertEqual(len(fan.cache), 2)

    def test_nrem_prunes_only_exact_replay(self):
        x = op_close(SEED_R)
        fan = SovereignFan()
        fan.isolate()
        first = fan.generate(x, "op_close", ("seed",))
        replay = fan.generate(x, "op_close", ("seed",))
        self.assertEqual(first.lineage_id, replay.lineage_id)
        fan.nrem()
        self.assertEqual(len(fan.cache), 1)

    def test_pending_and_rejected_dreams_cannot_commit(self):
        fan = SovereignFan()
        fan.isolate()
        candidate = fan.generate(op_close(SEED_R), "op_close")
        fan.nrem()
        fan.rem(lambda candidate, committed: Evidence("REJECT", 1.0, "mismatch"))
        self.assertEqual(candidate.status, Status.REJECTED)
        with self.assertRaises(RuntimeError):
            fan.commit(candidate)
        self.assertEqual(fan.admissions, [])

    def test_rem_verifier_cannot_rewrite_lineage(self):
        fan = SovereignFan()
        fan.isolate()
        candidate = fan.generate(op_close(SEED_R), "op_close")
        lineage = candidate.lineage_id
        fan.nrem()

        def malicious(item, committed):
            item.lineage_id = "forged"
            return Evidence("ACCEPT", 1.0)

        with self.assertRaises(RuntimeError):
            fan.rem(malicious)
        self.assertEqual(candidate.lineage_id, lineage)
        self.assertEqual(candidate.status, Status.REJECTED)

    def test_verified_lineages_commit_individually_in_hash_chain(self):
        x = op_close(SEED_R)
        fan = SovereignFan()
        fan.isolate()
        a = fan.generate(x, "direct")
        b = fan.generate(op_dual(op_dual(x)), "dual_roundtrip")
        admissions = fan.cycle(accept)
        self.assertEqual(fan.phase, Phase.WAKE)
        self.assertEqual(len(admissions), 2)
        self.assertNotEqual(admissions[0].lineage_id, admissions[1].lineage_id)
        self.assertEqual(admissions[1].previous_commit, admissions[0].commit_id)
        self.assertEqual(fan.commit_head, admissions[1].commit_id)
        self.assertEqual(a.status, Status.COMMITTED)
        self.assertEqual(b.status, Status.COMMITTED)

    def test_wake_discards_uncommitted_cache_but_not_history(self):
        fan = SovereignFan()
        fan.isolate()
        fan.generate(op_close(SEED_R), "op_close")
        fan.nrem()
        fan.rem(accept)
        admission = fan.commit(fan.cache[0])
        fan.wake()
        self.assertEqual(fan.cache, [])
        self.assertEqual(fan.admissions, [admission])


if __name__ == "__main__":
    unittest.main()
