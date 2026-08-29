import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "crossdomain"
FIXTURES = SUITE / "fixtures"


class CrossDomainGoldenPolicyTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))

    def test_required_domains_are_declared(self):
        required = {"physics", "chemistry", "biology", "computation"}
        self.assertEqual(required, set(self.manifest["domains"]))

    def test_partial_historical_records_are_not_executable_fixtures(self):
        for domain in ("chemistry", "biology", "computation"):
            entry = self.manifest["domains"][domain]
            self.assertEqual("FOUND_PARTIAL", entry["status"])
            fixture = json.loads((FIXTURES / entry["seed_fixture"]).resolve().read_text(encoding="utf-8"))
            self.assertFalse(fixture["executable"])
            self.assertIsNone(fixture["seeds"])

    def test_physics_fixture_is_exact_but_not_a_complete_regression(self):
        entry = self.manifest["domains"]["physics"]
        self.assertEqual("FOUND_EXACT", entry["status"])
        fixture = json.loads((FIXTURES / entry["seed_fixture"]).resolve().read_text(encoding="utf-8"))
        self.assertEqual("physics", fixture["domain"])
        self.assertTrue(fixture["executable"])
        self.assertEqual(10, len(fixture["seeds"]))
        kinds = [s["kind"] for s in fixture["seeds"]]
        self.assertEqual(4, kinds.count("RECURRENCE"))
        self.assertEqual(4, kinds.count("SYMMETRY"))
        self.assertEqual(2, kinds.count("CARRIER"))

    def test_no_fixture_claims_outputs_without_a_frozen_baseline(self):
        for domain in ("physics", "chemistry", "biology", "computation"):
            entry = self.manifest["domains"][domain]
            expected = json.loads((FIXTURES / entry["expected_structural"]).resolve().read_text(encoding="utf-8"))
            self.assertIsNone(expected["expected_structural_signatures"])
            self.assertIsNone(expected["expected_derivation_events"])

    def test_all_sealed_files_match_raw_byte_hashes(self):
        sums = json.loads((SUITE / "SHA256SUMS.json").read_text(encoding="utf-8"))
        for relative, expected in sums["files"].items():
            actual = hashlib.sha256((SUITE / relative).read_bytes()).hexdigest()
            self.assertEqual(expected, actual, relative)

    def test_gate_fails_closed(self):
        spec = importlib.util.spec_from_file_location("crossdomain_gate", ROOT / "scripts" / "crossdomain-golden-gate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.build_report()
        self.assertEqual("FAIL", report["result"])
        self.assertEqual("PASS", report["hashes"]["status"])
        self.assertEqual("BLOCKED", report["domains"]["physics"]["gate"])
        self.assertFalse(any(row["gate"] == "READY" for row in report["domains"].values()))


if __name__ == "__main__":
    unittest.main()
