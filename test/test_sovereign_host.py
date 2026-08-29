import hashlib
import hmac
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.deadman import DeadmanDecision, DeadmanState  # noqa: E402
from ckk.sovereign.host import HostSettings, create_app  # noqa: E402


class RestrictedGuard:
    def evaluate(self):
        return DeadmanDecision(DeadmanState.RESTRICTED, "test fixture")


class SovereignHostTests(unittest.TestCase):
    def test_meta_get_verification_and_signed_post_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = HostSettings(
                owner_wa_id="491701234567",
                business_phone_number_id="phone-1",
                meta_app_secret="app-secret",
                meta_verify_token="verify-token",
                whatsapp_access_token="access-token",
                state_path=str(Path(directory) / "state.sqlite3"),
                deadman_control_dir=directory,
            )
            with patch(
                "ckk.sovereign.host.DeadmanGuard.from_control_directory",
                return_value=RestrictedGuard(),
            ):
                app = create_app(settings=settings, client=object())

            with TestClient(app) as client:
                accepted = client.get(
                    "/webhook",
                    params={
                        "hub.mode": "subscribe",
                        "hub.verify_token": "verify-token",
                        "hub.challenge": "12345",
                    },
                )
                self.assertEqual(accepted.status_code, 200)
                self.assertEqual(accepted.text, "12345")
                self.assertTrue(accepted.headers["content-type"].startswith("text/plain"))

                rejected = client.get(
                    "/webhook",
                    params={
                        "hub.mode": "subscribe",
                        "hub.verify_token": "wrong-token",
                        "hub.challenge": "12345",
                    },
                )
                self.assertEqual(rejected.status_code, 403)
                self.assertNotIn("12345", rejected.text)
                self.assertEqual(client.get("/webhook").status_code, 403)

                payload = {"object": "whatsapp_business_account", "entry": []}
                raw = json.dumps(payload, separators=(",", ":")).encode()
                signature = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
                posted = client.post(
                    "/webhook",
                    content=raw,
                    headers={
                        "content-type": "application/json",
                        "x-hub-signature-256": signature,
                    },
                )
                self.assertEqual(posted.status_code, 202)
                self.assertEqual(posted.json(), {"status": "queued", "admitted": 0, "duplicates": 0})


if __name__ == "__main__":
    unittest.main()
