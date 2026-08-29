import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.deadman import (  # noqa: E402
    ACTIVE_SECONDS,
    QUARANTINE_SECONDS,
    DeadmanGuard,
    DeadmanActuator,
    DeadmanState,
    canonical_payload,
)


class DeadmanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.private = Ed25519PrivateKey.generate()
        (self.root / "deadman-public.pem").write_bytes(
            self.private.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    def tearDown(self):
        self.temporary.cleanup()

    def lease(self, issued_at=1000, mutate=None):
        payload = {
            "version": 1,
            "sequence": issued_at,
            "issued_at": issued_at,
            "restricted_at": issued_at + ACTIVE_SECONDS,
            "quarantine_at": issued_at + QUARANTINE_SECONDS,
            "nonce": "test",
        }
        signature = self.private.sign(canonical_payload(payload))
        if mutate:
            mutate(payload)
        (self.root / "deadman-lease.json").write_text(
            json.dumps({"payload": payload, "signature": base64.b64encode(signature).decode()})
        )

    def guard(self, now):
        return DeadmanGuard.from_control_directory(str(self.root), now=lambda: now)

    def test_active_restricted_and_quarantined_windows(self):
        self.lease()
        self.assertEqual(self.guard(1001).evaluate().state, DeadmanState.ACTIVE)
        self.assertEqual(self.guard(1000 + ACTIVE_SECONDS).evaluate().state, DeadmanState.RESTRICTED)
        self.assertEqual(self.guard(1000 + QUARANTINE_SECONDS).evaluate().state, DeadmanState.QUARANTINED)

    def test_missing_or_tampered_material_fails_closed(self):
        self.assertEqual(self.guard(1000).evaluate().state, DeadmanState.QUARANTINED)
        self.lease(mutate=lambda payload: payload.update(restricted_at=999999))
        self.assertEqual(self.guard(1000).evaluate().state, DeadmanState.QUARANTINED)

    def test_operator_kill_file_overrides_valid_lease(self):
        self.lease()
        (self.root / "KILL").touch()
        result = self.guard(1001).evaluate()
        self.assertEqual(result.state, DeadmanState.QUARANTINED)
        self.assertFalse(result.ingress_allowed)
        self.assertFalse(result.processing_allowed)

    def test_actuator_checks_lease_at_effect_time(self):
        class Target:
            capability = "test.effect"

            def __init__(self):
                self.calls = 0

            def execute(self, intent):
                self.calls += 1
                return intent

        self.lease()
        target = Target()
        active = DeadmanActuator(target, self.guard(1001))
        self.assertEqual(active.execute("ok"), "ok")
        blocked = DeadmanActuator(target, self.guard(1000 + ACTIVE_SECONDS))
        with self.assertRaises(PermissionError):
            blocked.execute("blocked")
        self.assertEqual(target.calls, 1)


if __name__ == "__main__":
    unittest.main()
