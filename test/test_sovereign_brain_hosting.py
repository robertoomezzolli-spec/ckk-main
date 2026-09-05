import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.brain import OpenAIResponsesCognition  # noqa: E402
from ckk.sovereign.organism import BootstrapLaws, CognitionResult, SovereignOrganism  # noqa: E402
from ckk.sovereign.runtime import CapabilityPolicy, IngressPolicy, Observation, SovereignRuntime  # noqa: E402
from ckk.sovereign.state import SQLiteStateStore  # noqa: E402
from ckk.sovereign.whatsapp import (  # noqa: E402
    JsonTransportResult,
    WhatsAppCloudActuator,
    WhatsAppConfig,
    WhatsAppInbox,
    WhatsAppTransportError,
    service_intent,
)


OWNER = "491701234567"


class FakeResponses:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=json.dumps(self.result))


class FakeClient:
    def __init__(self, result):
        self.responses = FakeResponses(result)


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, url, headers, payload):
        self.calls.append((url, headers, payload))
        return JsonTransportResult(200, {"messages": [{"id": "wamid.out"}]})


class SilentBrain:
    def reflect(self, observations, memory, learned_context, laws):
        return CognitionResult(salience=0.1)


def decision(action="silence", text=None, template=None, learning=None):
    return {
        "action": action,
        "text": text,
        "template": template,
        "reason": "bounded decision",
        "salience": 0.8,
        "learning": learning or [],
    }


class SovereignBrainHostingTests(unittest.TestCase):
    def test_brain_has_no_seeded_persona_and_maps_schema_to_service_intent(self):
        client = FakeClient(decision("service_message", "Hallo"))
        config = WhatsAppConfig(OWNER, "phone")
        brain = OpenAIResponsesCognition(config, client=client, service_window_provider=lambda recipient: True)
        observation = Observation("wa:1", f"whatsapp:{OWNER}", "message.text", {"text": "Hi"}, 1.0)
        result = brain.reflect((observation,), (), {}, BootstrapLaws())
        self.assertEqual(result.intent.payload["to"], OWNER)
        self.assertEqual(result.intent.payload["text"], "Hallo")
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-5.6")
        self.assertTrue(call["text"]["format"]["strict"])
        self.assertEqual(call["text"]["format"]["schema"]["properties"]["action"]["enum"], ["service_message"])
        self.assertTrue(json.loads(call["input"])["conversation_policy"]["direct_message_reply_required"])
        self.assertNotIn("You are called", call["instructions"])

    def test_published_research_is_routed_to_short_whatsapp_verdict_and_url(self):
        client = FakeClient(decision("service_message", "DIRECT\nhttps://example.test/research/run"))
        brain = OpenAIResponsesCognition(
            WhatsAppConfig(OWNER, "phone"), client=client, service_window_provider=lambda recipient: True
        )
        observation = Observation("wa:publish", f"whatsapp:{OWNER}", "message.text", {"text": "publish run"}, 1.0)
        brain.reflect((observation,), (), {}, BootstrapLaws())
        instructions = client.responses.calls[0]["instructions"]
        self.assertIn("invoke research.publish", instructions)
        self.assertIn("only a short verdict and the returned publication_url", instructions)
        self.assertIn("never the long-form report", instructions)

    def test_brain_may_choose_silence(self):
        brain = OpenAIResponsesCognition(WhatsAppConfig(OWNER, "phone"), client=FakeClient(decision()))
        self.assertIsNone(brain.reflect((), (), {}, BootstrapLaws()).intent)

    def test_direct_message_cannot_silently_disappear_inside_service_window(self):
        brain = OpenAIResponsesCognition(
            WhatsAppConfig(OWNER, "phone"),
            client=FakeClient(decision()),
            service_window_provider=lambda recipient: True,
        )
        observation = Observation("wa:1", f"whatsapp:{OWNER}", "message.text", {"text": "Hi"}, 1.0)
        with self.assertRaisesRegex(ValueError, "requires a service reply"):
            brain.reflect((observation,), (), {}, BootstrapLaws())

    def test_direct_reply_is_pinned_to_the_actual_admitted_sender(self):
        additional = "491609876543"
        client = FakeClient(decision("service_message", "Hallo"))
        config = WhatsAppConfig(OWNER, "phone", additional_wa_ids=frozenset({additional}))
        brain = OpenAIResponsesCognition(
            config,
            client=client,
            service_window_provider=lambda recipient: recipient == additional,
        )
        observation = Observation("wa:2", f"whatsapp:{additional}", "message.text", {"text": "Hi"}, 1.0)
        result = brain.reflect((observation,), (), {}, BootstrapLaws())
        self.assertEqual(result.intent.payload["to"], additional)

    def test_brain_cannot_forge_learning_evidence(self):
        learning = [{"key": "self.name", "value": "X", "confidence": 0.9, "evidence_ids": ["fake"], "reason": "no"}]
        brain = OpenAIResponsesCognition(WhatsAppConfig(OWNER, "phone"), client=FakeClient(decision(learning=learning)))
        observation = Observation("wa:1", f"whatsapp:{OWNER}", "message.text", {"text": "Hi"}, 1.0)
        with self.assertRaises(PermissionError):
            brain.reflect((observation,), (), {}, BootstrapLaws())

    def test_ckk_evidence_is_scoped_to_current_wake_and_labeled_external(self):
        client = FakeClient(decision("service_message", "Evidence checked"))
        brain = OpenAIResponsesCognition(
            WhatsAppConfig(OWNER, "phone"), client=client, service_window_provider=lambda recipient: True
        )
        inbound = Observation("wa:ckk", f"whatsapp:{OWNER}", "message.text", {"text": "show op_close"}, 1.0)
        evidence = Observation(
            "ckk:one", "ckk.repository", "evidence.source",
            {"path": "ckk_snapshot/ckk/gen/grammar.py", "commit_sha": "a" * 40,
             "source_kind": "source_code", "truth_status": "external_evidence_unverified",
             "belief_status": "not_committed", "excerpt": "def op_close(s): ..."}, 0.75,
        )
        result = brain.reflect((inbound, evidence), (), {}, BootstrapLaws())
        self.assertEqual(result.learning, ())
        call = client.responses.calls[0]
        payload = json.loads(call["input"])
        self.assertEqual(payload["current_observations"][1]["observation_id"], "ckk:one")
        self.assertIn("not truth and not committed belief", call["instructions"])

    def test_real_actuator_sends_only_after_policy_check(self):
        config = WhatsAppConfig(OWNER, "phone")
        inbox = WhatsAppInbox(config, last_owner_message_at=int(time.time()))
        transport = FakeTransport()
        actuator = WhatsAppCloudActuator(config, inbox, access_token="token", transport=transport)
        effect = actuator.execute(service_intent(config, "Hallo", "test"))
        self.assertFalse(effect.simulated)
        self.assertEqual(effect.output["provider_http_status"], 200)
        self.assertEqual(effect.output["mode"], "service")
        self.assertEqual(transport.calls[0][2]["to"], OWNER)
        self.assertNotIn("token", json.dumps(transport.calls[0][2]))

    def test_real_actuator_surfaces_provider_http_error(self):
        class RejectingTransport:
            def post(self, url, headers, payload):
                return JsonTransportResult(
                    400,
                    {"error": {"type": "OAuthException", "code": 131030, "message": "recipient rejected"}},
                )

        config = WhatsAppConfig(OWNER, "phone")
        inbox = WhatsAppInbox(config, last_owner_message_at=int(time.time()))
        actuator = WhatsAppCloudActuator(config, inbox, access_token="token", transport=RejectingTransport())
        with self.assertRaisesRegex(WhatsAppTransportError, "HTTP 400"):
            actuator.execute(service_intent(config, "Hallo", "test"))

    def test_sqlite_checkpoint_restores_identity_memory_and_episodes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(str(Path(directory) / "state.sqlite3"))
            actuator = WhatsAppCloudActuator(
                WhatsAppConfig(OWNER, "phone"), WhatsAppInbox(WhatsAppConfig(OWNER, "phone")),
                access_token="unused", transport=FakeTransport(),
            )
            runtime = SovereignRuntime(
                IngressPolicy(frozenset({"internal.clock"}), frozenset({"clock.tick"})),
                CapabilityPolicy(frozenset({"whatsapp.send"})), {"whatsapp.send": actuator},
            )
            organism = SovereignOrganism(runtime, SilentBrain())
            observation = Observation("tick:1", "internal.clock", "clock.tick", {"unix_time": 1}, 1.0)
            store.enqueue((observation,))
            queued = store.next_observation()
            organism.perceive(queued)
            organism.think()
            commit = organism.sleep()
            store.complete(observation, {"observation": {"id": "tick:1"}, "commit": commit.identity}, organism)

            runtime2 = SovereignRuntime(
                IngressPolicy(frozenset({"internal.clock"}), frozenset({"clock.tick"})),
                CapabilityPolicy(frozenset({"whatsapp.send"})), {"whatsapp.send": actuator},
            )
            restored = SovereignOrganism(runtime2, SilentBrain())
            self.assertTrue(store.restore(restored))
            self.assertEqual(restored.identity, organism.identity)
            self.assertEqual(restored.runtime.memory[0].observation_ids, ("tick:1",))
            self.assertEqual(len(store.recent_episodes()), 1)


if __name__ == "__main__":
    unittest.main()
