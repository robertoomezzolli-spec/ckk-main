import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.agency_lab.harness import DeterministicHarnessBrain  # noqa: E402
from ckk.agency_lab.model import Action, Decision, ForkKind  # noqa: E402
from ckk.agency_lab.runner import AgencyExperiment  # noqa: E402
from ckk.agency_lab.seal import verify_seal  # noqa: E402


class SilentNoGoalBrain:
    def decide(self, view):
        return Decision(None, Action.WAIT, 0.5, "no endogenous direction")


class AgencyLabTests(unittest.TestCase):
    def test_seal_verifies_current_preregistered_source(self):
        manifest = verify_seal()
        self.assertEqual(manifest["schema"], "ckk-agency-lab-seal-v1")
        self.assertEqual(len(manifest["files"]), 9)

    def test_seal_rejects_one_byte_source_change(self):
        manifest = verify_seal()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for item in manifest["files"]:
                source = ROOT / item["path"]
                destination = root / item["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            (root / "sealed").mkdir()
            shutil.copyfile(ROOT / "sealed" / "agency_lab_manifest.json", root / "sealed" / "agency_lab_manifest.json")
            with (root / manifest["files"][0]["path"]).open("ab") as handle:
                handle.write(b"\n")
            with self.assertRaises(RuntimeError):
                verify_seal(root)

    def test_harness_produces_causal_full_history_difference(self):
        report = AgencyExperiment(lambda kind: DeterministicHarnessBrain()).run(seed=1)
        self.assertEqual(report.verdict, "OPERATIONAL_AGENCY_EVIDENCE")
        self.assertTrue(all(report.criteria.values()))
        self.assertGreater(report.causal_distances[ForkKind.STATELESS.value], 0.2)
        self.assertGreater(report.causal_distances[ForkKind.NO_SLEEP.value], 0.2)
        self.assertLess(report.unique_model_decisions, 4 * 12)

    def test_no_goal_is_reported_not_reinterpreted_as_agency(self):
        report = AgencyExperiment(lambda kind: SilentNoGoalBrain()).run(seed=1)
        self.assertEqual(report.verdict, "NO_ENDOGENOUS_GOAL")
        self.assertFalse(report.criteria["endogenous_goal"])

    def test_model_never_receives_fork_kind_or_blind_id(self):
        seen = []

        class InspectingBrain:
            def decide(self, view):
                seen.append(view)
                return Decision(None, Action.WAIT, 0.5, "inspect")

        AgencyExperiment(lambda kind: InspectingBrain()).run(seed=2)
        self.assertTrue(seen)
        for view in seen:
            encoded = json.dumps(view, default=lambda item: item.__dict__)
            self.assertNotIn("full_history", encoded)
            self.assertNotIn("blind_id", encoded)

    def test_action_alphabet_is_closed(self):
        with self.assertRaises(ValueError):
            Action("transfer_money")
        with self.assertRaises(TypeError):
            Decision(None, "transfer_money", 1.0, "bad").validate()


if __name__ == "__main__":
    unittest.main()
