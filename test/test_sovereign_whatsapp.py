import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.runtime import (  # noqa: E402
    Approval,
    CapabilityPolicy,
    IngressPolicy,
    SovereignRuntime,
)
from ckk.sovereign.whatsapp import (  # noqa: E402
    WhatsAppConfig,
    WhatsAppInbox,
    WhatsAppSimulationActuator,
    service_intent,
    template_intent,
    verify_challenge,
)


SECRET = "app-secret"
OWNER = "491701234567"
PHONE_ID = "phone-1"


def signed(payload):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, signature


def webhook(message):
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"metadata": {"phone_number_id": PHONE_ID}, "messages": [message]}}]}],
    }


class SovereignWhatsAppTests(unittest.TestCase):
    def setUp(self):
        self.config = WhatsAppConfig(OWNER, PHONE_ID, frozenset({"agent_has_thought"}), 1)
        self.inbox = WhatsAppInbox(self.config)

    def test_meta_challenge_is_fail_closed(self):
        self.assertEqual(verify_challenge("subscribe", "token", "123", "token"), "123")
        with self.assertRaises(PermissionError):
            verify_challenge("subscribe", "wrong", "123", "token")
        with self.assertRaises(PermissionError):
            verify_challenge("subscribe", "token", "", "token")

    def test_invalid_signature_is_rejected(self):
        raw, _ = signed(webhook({"id": "m1", "from": OWNER, "timestamp": "100", "type": "text", "text": {"body": "hi"}}))
        with self.assertRaises(PermissionError):
            self.inbox.parse(raw, "sha256=bad", SECRET)

    def test_owner_text_becomes_trusted_observation(self):
        raw, signature = signed(webhook({"id": "m1", "from": OWNER, "timestamp": "100", "type": "text", "text": {"body": "Denk weiter"}}))
        observations = self.inbox.parse(raw, signature, SECRET)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].kind, "message.text")
        self.assertEqual(observations[0].payload["text"], "Denk weiter")
        self.assertEqual(self.inbox.last_owner_message_at, 100)

    def test_document_metadata_crosses_ingress_without_unverified_bytes(self):
        raw, signature = signed(webhook({"id": "m2", "from": OWNER, "timestamp": "101", "type": "document", "document": {"id": "media-7", "filename": "paper.pdf", "mime_type": "application/pdf", "sha256": "abc"}}))
        observation = self.inbox.parse(raw, signature, SECRET)[0]
        self.assertEqual(observation.kind, "message.document")
        self.assertEqual(observation.payload["media_id"], "media-7")
        self.assertNotIn("bytes", observation.payload)

    def test_voice_note_and_image_are_sensory_metadata(self):
        for index, (message_type, media) in enumerate(
            (
                ("audio", {"id": "a1", "mime_type": "audio/ogg", "voice": True}),
                ("image", {"id": "i1", "mime_type": "image/jpeg", "caption": "look"}),
            ),
            1,
        ):
            raw, signature = signed(
                webhook(
                    {
                        "id": f"media-{index}",
                        "from": OWNER,
                        "timestamp": str(101 + index),
                        "type": message_type,
                        message_type: media,
                    }
                )
            )
            observation = self.inbox.parse(raw, signature, SECRET)[0]
            self.assertEqual(observation.kind, f"message.{message_type}")
            self.assertEqual(observation.payload["media_id"], media["id"])

    def test_other_sender_is_rejected(self):
        raw, signature = signed(webhook({"id": "m1", "from": "other", "timestamp": "100", "type": "text", "text": {"body": "hi"}}))
        with self.assertRaises(PermissionError):
            self.inbox.parse(raw, signature, SECRET)

    def test_agent_may_choose_silence(self):
        actuator = WhatsAppSimulationActuator(self.config, self.inbox, now=lambda: 100)
        runtime = SovereignRuntime(
            ingress=IngressPolicy(frozenset({f"whatsapp:{OWNER}"}), frozenset({"message.text", "message.document"})),
            capabilities=CapabilityPolicy(frozenset({"whatsapp.send"}), frozenset({"whatsapp.send"})),
            actuators={"whatsapp.send": actuator},
        )
        result = runtime.deliberate(lambda observations, memory: None)
        self.assertIsNone(result)
        self.assertEqual(actuator.effects, [])

    def test_free_text_only_inside_service_window(self):
        self.inbox.last_owner_message_at = 100
        actuator = WhatsAppSimulationActuator(self.config, self.inbox, now=lambda: 100 + 3600)
        effect = actuator.execute(service_intent(self.config, "Ich habe etwas gesehen.", "emergent salience"))
        self.assertTrue(effect.simulated)
        actuator.now = lambda: 100 + 25 * 3600
        with self.assertRaises(PermissionError):
            actuator.execute(service_intent(self.config, "Zu spät", "closed window"))

    def test_outside_window_requires_admitted_template_and_budget(self):
        actuator = WhatsAppSimulationActuator(self.config, self.inbox, now=lambda: 100000)
        with self.assertRaises(PermissionError):
            actuator.execute(template_intent(self.config, "unknown", "no"))
        actuator.execute(template_intent(self.config, "agent_has_thought", "self-initiated thought"))
        with self.assertRaises(PermissionError):
            actuator.execute(template_intent(self.config, "agent_has_thought", "budget"))

    def test_recipient_is_pinned_to_owner(self):
        self.inbox.last_owner_message_at = 100
        actuator = WhatsAppSimulationActuator(self.config, self.inbox, now=lambda: 100)
        intent = service_intent(self.config, "hello", "test")
        forged = type(intent)(intent.action, intent.capability, {**intent.payload, "to": "other"}, intent.reason)
        with self.assertRaises(PermissionError):
            actuator.execute(forged)


if __name__ == "__main__":
    unittest.main()
