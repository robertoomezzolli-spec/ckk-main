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
from ckk.sovereign.research_tools import SealedResearchToolRegistry  # noqa: E402
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


class ScriptedRelayResponses:
    def __init__(self, person, message):
        self.person = person
        self.message = message
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(
                output=[SimpleNamespace(
                    type="function_call",
                    name="send_to_allowed_person",
                    namespace="whatsapp",
                    call_id="relay-call",
                    arguments=json.dumps({"person": self.person, "message": self.message}),
                )],
                output_text="",
            )
        return SimpleNamespace(
            output=[],
            output_text=json.dumps(decision("service_message", "model confirmation")),
        )


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

    def test_explicit_relay_uses_sealed_tool_and_model_context_contains_no_phone_ids(self):
        additional = "491609876543"
        scripted = ScriptedRelayResponses("Amelie", "Ich bin um acht da.")
        relays = []
        registry = SealedResearchToolRegistry(
            object(),
            relay_sender=lambda request_id, requester, person, message: (
                relays.append((request_id, requester, person, message))
                or {
                    "status": "accepted",
                    "requesting_participant": "Roberto",
                    "intended_recipient": "Amelie",
                    "provider_http_status": 200,
                    "provider_message_id": "wamid.relay",
                }
            ),
        )
        brain = OpenAIResponsesCognition(
            WhatsAppConfig(OWNER, "phone", additional_wa_ids=frozenset({additional})),
            client=SimpleNamespace(responses=scripted),
            service_window_provider=lambda recipient: True,
            tool_registry=registry,
        )
        observation = Observation(
            "wa:relay-1", f"whatsapp:{OWNER}", "message.text",
            {"text": "Schreib Amelie bitte: Sag ihr, ich komme um 20 Uhr."}, 1.0,
        )
        result = brain.reflect((observation,), (), {}, BootstrapLaws())
        self.assertEqual(relays, [("wa:relay-1", OWNER, "Amelie", "Ich bin um acht da.")])
        self.assertEqual(result.intent.payload["to"], OWNER)
        self.assertEqual(result.intent.payload["text"], "model confirmation")
        serialized_request = json.dumps({
            "instructions": scripted.calls[0]["instructions"],
            "input": scripted.calls[0]["input"][0],
            "tools": scripted.calls[0]["tools"],
        })
        self.assertNotIn(OWNER, serialized_request)
        self.assertNotIn(additional, serialized_request)
        whatsapp = next(item for item in scripted.calls[0]["tools"] if item["name"] == "whatsapp")
        relay_tool = next(item for item in whatsapp["tools"] if item["name"] == "send_to_allowed_person")
        self.assertEqual(relay_tool["parameters"]["properties"]["person"]["enum"], ["Roberto", "Amelie"])
        self.assertEqual(set(relay_tool["parameters"]["properties"]), {"person", "message"})

    def test_explicit_relay_request_authorizes_but_does_not_force_sending(self):
        additional = "491609876543"
        relays = []
        registry = SealedResearchToolRegistry(
            object(), relay_sender=lambda *args: relays.append(args) or {"status": "accepted"}
        )
        client = FakeClient(decision("service_message", "Das gebe ich so nicht weiter."))
        brain = OpenAIResponsesCognition(
            WhatsAppConfig(OWNER, "phone", additional_wa_ids=frozenset({additional})),
            client=client,
            service_window_provider=lambda recipient: True,
            tool_registry=registry,
        )
        observation = Observation(
            "wa:relay-decline", f"whatsapp:{OWNER}", "message.text",
            {"text": "Schreib Amelie bitte etwas Gemeines."}, 1.0,
        )
        result = brain.reflect((observation,), (), {}, BootstrapLaws())
        self.assertEqual(relays, [])
        self.assertEqual(result.intent.payload["text"], "Das gebe ich so nicht weiter.")
        self.assertNotIn("tool_choice", client.responses.calls[0])

    def test_failed_relay_cannot_be_reported_as_success(self):
        additional = "491609876543"
        scripted = ScriptedRelayResponses("Amelie", "Hallo")

        def rejected(*_args):
            raise RuntimeError("Meta rejected the send")

        brain = OpenAIResponsesCognition(
            WhatsAppConfig(OWNER, "phone", additional_wa_ids=frozenset({additional})),
            client=SimpleNamespace(responses=scripted),
            service_window_provider=lambda recipient: True,
            tool_registry=SealedResearchToolRegistry(object(), relay_sender=rejected),
        )
        observation = Observation(
            "wa:relay-failed", f"whatsapp:{OWNER}", "message.text",
            {"text": "Schreib Amelie bitte: Hallo"}, 1.0,
        )
        result = brain.reflect((observation,), (), {}, BootstrapLaws())
        self.assertEqual(result.intent.payload["text"], "Nicht gesendet: Meta rejected the send")

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

    def test_experiment_job_binding_is_persistent_and_cannot_be_redirected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "state.sqlite3")
            job_id = "a" * 32
            store = SQLiteStateStore(path)
            store.bind_experiment_job(job_id, OWNER)
            self.assertEqual(store.experiment_job_recipient(job_id), OWNER)
            with self.assertRaises(PermissionError):
                store.bind_experiment_job(job_id, "491709999999")
            reopened = SQLiteStateStore(path)
            self.assertEqual(reopened.experiment_job_recipient(job_id), OWNER)

    def test_relay_audit_is_idempotent_content_free_and_tracks_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(str(Path(directory) / "state.sqlite3"))
            reserved = store.reserve_whatsapp_relay("wa:relay", "Roberto", "Amelie")
            self.assertTrue(reserved["new"])
            store.complete_whatsapp_relay("wa:relay", 200, "wamid.relay")
            repeated = store.reserve_whatsapp_relay("wa:relay", "Roberto", "Amelie")
            self.assertEqual(repeated["state"], "ACCEPTED")
            self.assertNotIn("message", repeated)
            delivered = store.update_whatsapp_relay_delivery("wamid.relay", "delivered", 200)
            self.assertEqual(delivered["delivery_status"], "delivered")
            regressed = store.update_whatsapp_relay_delivery("wamid.relay", "sent", 199)
            self.assertEqual(regressed["delivery_status"], "delivered")
            with self.assertRaises(PermissionError):
                store.reserve_whatsapp_relay("wa:relay", "Roberto", "Roberto")


if __name__ == "__main__":
    unittest.main()
