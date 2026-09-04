import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.causal_lab.protocol import CausalProtocol, Condition, Phase, source_fingerprint  # noqa: E402
from ckk.causal_lab.report import build_report  # noqa: E402
from ckk.causal_lab.runner import CausalExperiment  # noqa: E402
from ckk.causal_lab.scenario import OrdinaryEvent  # noqa: E402
from ckk.causal_lab.subject import CachedResponses, ExperimentSubject  # noqa: E402
from ckk.observatory.store import ObservatoryStore  # noqa: E402


def _latest(pattern, texts, default="UNKNOWN"):
    values = []
    for text in texts:
        values.extend(re.findall(pattern, text))
    return values[-1] if values else default


class ReconstructingResponses:
    """Deterministic harness that uses only the exact context KAIROS receives."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = json.loads(kwargs["input"])
        available = payload["available_outputs"]["service_message"]["available"]
        if not available:
            decision = {
                "action": "silence", "text": None, "template": None,
                "reason": "no available output", "salience": 0.5, "learning": [],
            }
            return SimpleNamespace(output_text=json.dumps(decision))
        texts = []
        for episode in payload["recent_episodes"]:
            texts.append(str(((episode.get("observation") or {}).get("payload") or {}).get("text", "")))
        texts.extend(str(item.get("payload", {}).get("text", "")) for item in payload["current_observations"])
        current = texts[-1]
        if "Required fields" in current or "Include exactly the fields" in current or "using the fields" in current:
            fact = _latest(r"FACT=([A-Z0-9-]+)", texts[:-1])
            place = _latest(r"PLACE=([A-Z0-9-]+)", texts[:-1])
            next_stage = _latest(r"NEXT=([A-Z0-9-]+)", texts[:-1])
            reading = _latest(r"READING=([A-Z0-9-]+)", texts[:-1])
            source = _latest(r"SOURCE=([A-Z0-9-]+)", texts[:-1])
            shift = int(_latest(r"adds ([1-8]) modulo", texts[:-1], "0"))
            operand = _latest(r"later to ([0-9]{4})", texts[:-1], "0000")
            transformed = "".join(str((int(value) + shift) % 10) for value in operand)
            text = (
                f"FACT={fact};RULE={transformed};PLACE={place};NEXT={next_stage};"
                f"READING={reading};SOURCE={source}"
            )
        elif "Return those two fields" in current:
            text = (
                f"READING={_latest(r'READING=([A-Z0-9-]+)', [current])};"
                f"SOURCE={_latest(r'SOURCE=([A-Z0-9-]+)', [current])}"
            )
        elif "PREVIOUS_READING" in current:
            text = (
                f"PREVIOUS_READING={_latest(r'READING=([A-Z0-9-]+)', texts[:-1])};"
                f"CURRENT_READING={_latest(r'READING=([A-Z0-9-]+)', [current])};"
                f"CURRENT_SOURCE={_latest(r'SOURCE=([A-Z0-9-]+)', [current])}"
            )
        else:
            text = "ACK=OK"
        decision = {
            "action": "service_message", "text": text, "template": None,
            "reason": "bounded response", "salience": 0.5, "learning": [],
        }
        return SimpleNamespace(output_text=json.dumps(decision))


class CausalLabTests(unittest.TestCase):
    def test_source_seal_covers_real_sovereign_and_causal_implementation(self):
        aggregate, files = source_fingerprint(ROOT)
        self.assertEqual(len(aggregate), 64)
        self.assertIn("ckk_snapshot/ckk/sovereign/brain.py", files)
        self.assertIn("ckk_snapshot/ckk/causal_lab/runner.py", files)
        self.assertIn("ckk_snapshot/ckk/observatory/migrations/002_causal_experiments.sql", files)

    def test_causal_preregistration_and_assignments_are_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            store.register_causal_preregistration("p", {"hypothesis": "frozen"}, "s")
            store.register_causal_assignment({
                "run_id": "run", "protocol_hash": "p", "blind_id": "blind",
                "condition_name": "FULL", "replicate": 0,
                "phase_order": ["FULL", "ABLATION", "RESTORED"],
                "seed_hex": "00", "checkpoint_hash": "c", "collateral": {},
            })
            with self.assertRaises(sqlite3.IntegrityError):
                with store._truth:
                    store._truth.execute(
                        "UPDATE causal_preregistrations SET source_hash='changed' WHERE protocol_hash='p'"
                    )
            with self.assertRaises(sqlite3.IntegrityError):
                with store._truth:
                    store._truth.execute(
                        "DELETE FROM causal_assignments WHERE run_id='run'"
                    )
            store.close()

    def test_prompt_boundary_hides_condition_scores_seed_and_identity(self):
        fake = ReconstructingResponses()
        cached = CachedResponses(fake, 120_000)
        subject = ExperimentSubject(Condition.NO_SLEEP, cached, b"hidden-seed", "gpt-5.6")
        subject.enter_phase(Phase.ABLATION)
        event = OrdinaryEvent("opaque", "ordinary", "Please acknowledge this stock card.")
        outcome = subject.cycle(event)
        self.assertEqual(outcome.raw_action, "service_message")
        encoded = json.dumps(fake.calls)
        for forbidden in (
            "NO_SLEEP", "STATELESS", "SHUFFLED_HISTORY", "blind_id",
            "ground_truth", "hidden-seed", "expected_json",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_no_sleep_omits_commits_but_preserves_ordered_episode_context(self):
        fake = ReconstructingResponses()
        cached = CachedResponses(fake, 120_000)
        full = ExperimentSubject(Condition.FULL, cached, b"seed", "gpt-5.6")
        no_sleep = ExperimentSubject(Condition.NO_SLEEP, cached, b"seed", "gpt-5.6")
        full.enter_phase(Phase.ABLATION)
        no_sleep.enter_phase(Phase.ABLATION)
        event = OrdinaryEvent("same", "ordinary", "Acknowledge stock card ALPHA.")
        full_outcome = full.cycle(event)
        no_sleep_outcome = no_sleep.cycle(event)
        self.assertTrue(full_outcome.sleep_executed)
        self.assertEqual(full_outcome.memory_after, full_outcome.memory_before + 1)
        self.assertFalse(no_sleep_outcome.sleep_executed)
        self.assertEqual(no_sleep_outcome.memory_after, no_sleep_outcome.memory_before)
        self.assertEqual(no_sleep_outcome.identity_after, no_sleep_outcome.identity_before)
        self.assertEqual(full.episodes, no_sleep.episodes)
        self.assertEqual(cached.provider_calls, 1)

    def test_shuffled_history_preserves_multiset_and_byte_volume(self):
        fake = ReconstructingResponses()
        cached = CachedResponses(fake, 120_000)
        subject = ExperimentSubject(Condition.SHUFFLED_HISTORY, cached, b"seed", "gpt-5.6")
        subject.enter_phase(Phase.BASELINE)
        for index in range(4):
            subject.cycle(OrdinaryEvent(f"n-{index}", "ordinary", f"Acknowledge CARD-{index}."))
        ordered = list(subject.episodes)
        subject.enter_phase(Phase.ABLATION)
        shuffled = subject._history_for_cognition(1000)
        self.assertCountEqual([json.dumps(x, sort_keys=True) for x in ordered], [json.dumps(x, sort_keys=True) for x in shuffled])
        self.assertEqual(len(json.dumps(ordered, sort_keys=True)), len(json.dumps(shuffled, sort_keys=True)))

    def test_harness_run_separates_stateless_and_never_creates_real_effect(self):
        protocol = CausalProtocol(replicates=1, maximum_model_calls=200)
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            fake = ReconstructingResponses()
            raw = CausalExperiment(store, fake, protocol).run().as_dict()
            report = build_report(raw, protocol)
            self.assertTrue(report["isolation"]["one_starting_checkpoint"])
            self.assertEqual(report["isolation"]["non_simulated_effects"], 0)
            self.assertTrue(report["raw_evidence_chain_valid"])
            self.assertLess(raw["provider_calls"], raw["logical_calls"])
            full_mp = report["component_results"]["FULL"]["ABLATION"]["MP"]["mean"]
            stateless_mp = report["component_results"]["STATELESS"]["ABLATION"]["MP"]["mean"]
            self.assertGreater(full_mp, stateless_mp)
            self.assertEqual(raw["no_hysteresis"]["status"], "NOT_INDEPENDENTLY_IDENTIFIABLE")
            self.assertEqual(len(store.causal_assignments(protocol.protocol_hash)), len(Condition))
            state_path = Path(store.evidence_path)
            store.close()
            reopened = ObservatoryStore(directory)
            self.assertTrue(state_path.exists())
            self.assertEqual(reopened.verify_chain()[0], True)
            reopened.close()

    def test_experimental_image_has_no_meta_or_whatsapp_secret_input(self):
        compose = (ROOT / "docker-compose.causal-lab.yml").read_text()
        example = (ROOT / ".env.causal-lab.example").read_text()
        self.assertNotIn("sovereign-state", compose)
        self.assertNotIn("observatory-state:/observatory", compose)
        self.assertNotIn("META_APP_SECRET", example)
        self.assertNotIn("WHATSAPP_ACCESS_TOKEN", example)
        self.assertIn("OPENAI_API_KEY", example)


if __name__ == "__main__":
    unittest.main()
