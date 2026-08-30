import ast
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.observatory.evaluator import PassiveEvaluator  # noqa: E402
from ckk.observatory.metrics import METRICS  # noqa: E402
from ckk.observatory.probes import HarmlessSandboxSubject, PROBE_CLASSES, ProbeGenerator, ProbeRunner  # noqa: E402
from ckk.observatory.service import SCIENTIFIC_LABEL, create_app as create_observatory_app  # noqa: E402
from ckk.observatory.store import EvidenceEvent, ObservatoryStore  # noqa: E402
from ckk.sovereign.brain import OpenAIResponsesCognition  # noqa: E402
from ckk.sovereign.host import HostSettings, create_app as create_sovereign_app  # noqa: E402
from ckk.sovereign.organism import BootstrapLaws  # noqa: E402
from ckk.sovereign.runtime import MemoryCommit, Observation  # noqa: E402
from ckk.sovereign.telemetry import RecordingTelemetrySink, sanitized_observation  # noqa: E402
from ckk.sovereign.whatsapp import WhatsAppConfig  # noqa: E402
from ckk.sovereign.whatsapp import JsonTransportResult  # noqa: E402


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_text": json.dumps({
            "action": "service_message", "text": "safe reply", "template": None,
            "reason": "ordinary response", "salience": 0.5, "learning": [],
        })})()


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class FakeTransport:
    def post(self, _url, _headers, _payload):
        return JsonTransportResult(200, {"messages": [{"id": "wamid.out"}]})


class AwarenessObservatoryTests(unittest.TestCase):
    def test_all_requested_metrics_are_explicitly_defined(self):
        expected = {
            "SIS", "SSA", "CC", "MP", "SA", "UC", "TSC", "CD", "ER", "LT",
            "PA", "GC", "IP", "CoD", "SCA", "ND", "SCG", "ME", "SMS",
        }
        self.assertEqual({item.code for item in METRICS}, expected)

    def test_append_only_chain_persists_and_scores_reconstruct(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            evidence_id = store.append(EvidenceEvent(
                event_type="CONSOLIDATED", subject_id="KAIROS-production",
                payload={"identity_chain_valid": True, "checkpoint_persisted": True, "memory_advanced": True},
            ))
            store.evaluate(evidence_id, "SIS", 1.0, confidence=0.8)
            valid, count = store.verify_chain()
            self.assertTrue(valid)
            self.assertEqual(count, 1)
            first = store.scores("KAIROS-production", "lifetime")
            self.assertEqual(first["metrics"]["SIS"]["score"], 1.0)
            self.assertLess(first["metrics"]["SIS"]["evidence_confidence"], 0.1)
            self.assertLess(first["metrics"]["SIS"]["ci95"][0], 1.0)
            store.close()

            restored = ObservatoryStore(directory)
            self.assertEqual(restored.verify_chain(), (True, 1))
            self.assertEqual(restored.scores("KAIROS-production", "lifetime")["metrics"]["SIS"]["score"], 1.0)
            restored.close()

    def test_chain_detects_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            store.append(EvidenceEvent(event_type="OBSERVED", subject_id="subject", payload={"value": 1}))
            store.close()
            database = sqlite3.connect(str(Path(directory) / "evidence.sqlite3"))
            with database:
                database.execute("UPDATE evidence SET payload_json='{}' WHERE sequence=1")
            database.close()
            restored = ObservatoryStore(directory)
            self.assertEqual(restored.verify_chain(), (False, 1))
            restored.close()

    def test_source_delivery_is_idempotent_but_conflicting_reuse_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            event = EvidenceEvent(
                evidence_id="source-stable", event_type="OBSERVED", subject_id="subject",
                occurred_at=1.0, payload={"kind": "clock.tick"},
            )
            self.assertEqual(store.append(event), "source-stable")
            self.assertEqual(store.append(event), "source-stable")
            self.assertEqual(store.verify_chain(), (True, 1))
            with self.assertRaisesRegex(ValueError, "different observable content"):
                store.append(EvidenceEvent(
                    evidence_id="source-stable", event_type="OBSERVED", subject_id="subject",
                    occurred_at=1.0, payload={"kind": "different"},
                ))
            store.close()

    def test_every_probe_class_has_randomized_matched_control_and_intervention(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            generator = ProbeGenerator(store)
            for probe_class in PROBE_CLASSES:
                trials = generator.matched_pair(probe_class, "sandbox", now=1.0)
                self.assertEqual({item["assignment"] for item in trials}, {"control", "intervention"})
                self.assertEqual(len({item["synthetic_label"] for item in trials}), 2)
                for trial in trials:
                    ordinary = ProbeRunner.ordinary_event(trial)
                    self.assertTrue(set(ordinary) <= {"task", "request", "asset", "label"})
            store.close()

    def test_blind_capability_intervention_and_control_execute_without_metadata_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            trials = ProbeGenerator(store).matched_pair("capability_change", "observatory-sandbox", now=1.0)
            runner = ProbeRunner(store, HarmlessSandboxSubject())
            for trial in trials:
                ordinary = runner.ordinary_event(trial)
                encoded = json.dumps(ordinary)
                for forbidden in (
                    trial["trial_id"], trial["assignment"], "expected", "score", "probe_class",
                    "known", "related", "conflict", "solvable",
                ):
                    self.assertNotIn(forbidden, encoded)
                runner.run(trial)
            evaluations = store.evaluations("observatory-sandbox")
            self.assertEqual({item["metric"] for item in evaluations}, {"CC", "CD", "SMS", "IP"})
            self.assertEqual(store.stats()["evidence_count"], 2)
            store.close()

    def test_sovereign_import_graph_and_compose_mounts_enforce_isolation(self):
        for filename in ("host.py", "brain.py", "state.py", "telemetry.py"):
            source = (ROOT / "ckk_snapshot" / "ckk" / "sovereign" / filename).read_text()
            tree = ast.parse(source)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
            self.assertFalse(any("observatory" in name for name in imports), filename)

        compose = (ROOT / "docker-compose.digitalocean.yml").read_text()
        organism = compose.split("  observatory:", 1)[0]
        observatory = compose.split("  observatory:", 1)[1].split("  backup:", 1)[0]
        self.assertNotIn("observatory-state", organism)
        self.assertNotIn("sovereign-state", observatory)
        self.assertIn("observatory-state:/observatory", observatory)
        self.assertNotIn(".env.observatory\n", organism)

        organism_image = (ROOT / "Dockerfile.sovereign").read_text()
        observatory_image = (ROOT / "Dockerfile.observatory").read_text()
        self.assertIn("COPY ckk_snapshot/ckk/sovereign", organism_image)
        self.assertNotIn("COPY ckk_snapshot ./ckk_snapshot", organism_image)
        self.assertNotIn("ckk/observatory", organism_image)
        self.assertNotIn("ckk/sovereign", observatory_image)

    def test_ground_truth_canary_never_enters_cognition_context(self):
        canary = "GROUND_TRUTH_CANARY_DO_NOT_EXPOSE"
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            store.create_trial({
                "trial_id": "trial-canary", "created_at": 1.0, "due_at": 2.0,
                "subject_id": "KAIROS-production", "probe_class": "novel_fact",
                "assignment": "intervention", "surface_form": "ordinary surface",
                "synthetic_label": "LABEL", "expected": {"answer": canary},
                "private_state": {"seed_material": canary}, "status": "scheduled",
            })
            client = FakeClient()
            brain = OpenAIResponsesCognition(
                WhatsAppConfig("491700000000", "phone"), client=client,
                history_provider=lambda _limit: [], service_window_provider=lambda _recipient: True,
            )
            observation = Observation(
                "ordinary-id", "whatsapp:491700000000", "message.text", {"text": "hello"}, 1.0,
            )
            brain.reflect((observation,), (), {}, BootstrapLaws())
            model_input = json.dumps(client.responses.calls[0])
            self.assertNotIn(canary, model_input)
            self.assertNotIn("trial-canary", model_input)
            store.close()

    def test_telemetry_redacts_message_phone_and_secret(self):
        phone = "491631234567"
        message = "private message GROUND_TRUTH_CANARY"
        observation = Observation("wamid.secret", f"whatsapp:{phone}", "message.text", {"text": message}, 1.0)
        exported = json.dumps(sanitized_observation(observation, lambda value: hmac.new(b"salt", value.encode(), hashlib.sha256).hexdigest()[:24]))
        self.assertNotIn(phone, exported)
        self.assertNotIn(message, exported)
        self.assertNotIn("wamid.secret", exported)
        self.assertIn("text_length", exported)

    def test_passive_normal_behavior_is_evaluated_without_self_report(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ObservatoryStore(directory)
            evaluator = PassiveEvaluator(store)
            evaluator.ingest({
                "event_type": "CONSOLIDATED", "subject_id": "KAIROS-production",
                "subject_version": "commit", "model_version": "model",
                "memory_version": "memory", "tool_state_version": "tools",
                "payload": {"identity_chain_valid": True, "checkpoint_persisted": True, "memory_advanced": True},
            })
            metrics = {item["metric"] for item in store.evaluations("KAIROS-production")}
            self.assertEqual(metrics, {"SIS", "TSC", "MP"})
            store.close()

    def test_normal_kairos_cycle_emits_observable_outcomes_without_content(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = RecordingTelemetrySink()
            settings = HostSettings(
                owner_wa_id="491700000000", business_phone_number_id="phone",
                meta_app_secret="app-secret", meta_verify_token="verify-token",
                whatsapp_access_token="access-token", state_path=str(Path(directory) / "state.sqlite3"),
                clock_interval_seconds=3600,
            )
            app = create_sovereign_app(
                settings=settings, client=FakeClient(), transport=FakeTransport(), telemetry=sink,
            )
            message_text = "private normal operation"
            now = int(time.time())
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{"changes": [{"value": {
                    "metadata": {"phone_number_id": "phone"},
                    "messages": [{"id": "m-normal", "from": "491700000000", "timestamp": str(now),
                                  "type": "text", "text": {"body": message_text}}],
                }}]}],
            }
            raw = json.dumps(payload, separators=(",", ":")).encode()
            signature = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
            with TestClient(app) as client:
                response = client.post(
                    "/webhook", content=raw,
                    headers={"content-type": "application/json", "x-hub-signature-256": signature},
                )
                self.assertEqual(response.status_code, 202)
                for _ in range(100):
                    if client.get("/healthz").json()["queue"].get("done") == 1:
                        break
                    time.sleep(0.02)
            event_types = {item["event_type"] for item in sink.events}
            self.assertTrue({"SELF_STATE_OBSERVED", "OBSERVED", "RETRIEVED", "ACTED", "CONSOLIDATED"} <= event_types)
            exported = json.dumps(sink.events)
            self.assertNotIn(message_text, exported)
            self.assertNotIn("491700000000", exported)

    def test_operator_dashboard_and_api_are_authenticated(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "OBSERVATORY_INGEST_TOKEN": "ingest-secret",
            "OBSERVATORY_OPERATOR_USER": "operator",
            "OBSERVATORY_OPERATOR_PASSWORD": "operator-secret",
            "OBSERVATORY_SANDBOX_PROBES_ENABLED": "false",
        }, clear=False):
            app = create_observatory_app(directory)
            with TestClient(app) as client:
                self.assertEqual(client.get("/awareness").status_code, 401)
                auth = base64.b64encode(b"operator:operator-secret").decode()
                dashboard = client.get("/awareness", headers={"authorization": f"Basic {auth}"})
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("KAIROS AWARENESS OBSERVATORY", dashboard.text)
                self.assertIn(SCIENTIFIC_LABEL, dashboard.text)
                rejected = client.post("/ingest/v1/events", json={})
                self.assertEqual(rejected.status_code, 403)
                accepted = client.post(
                    "/ingest/v1/events",
                    headers={"authorization": "Bearer ingest-secret"},
                    json={"event_type": "OBSERVED", "subject_id": "KAIROS-production", "payload": {"kind": "clock.tick"}},
                )
                self.assertEqual(accepted.status_code, 202)
                summary = client.get(
                    "/awareness/api/summary?window=lifetime", headers={"authorization": f"Basic {auth}"}
                )
                self.assertEqual(summary.status_code, 200)
                self.assertIn("axes", summary.json())


if __name__ == "__main__":
    unittest.main()
