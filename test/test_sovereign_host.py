import hashlib
import hmac
import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.host import HostSettings, create_app, experiment_completion_observation  # noqa: E402


class SovereignHostTests(unittest.TestCase):
    def test_terminal_experiment_status_becomes_bounded_reply_channel_observation(self):
        observation = experiment_completion_observation({
            "job_id": "a" * 32,
            "task": "fresh_seed_closure_plateau_v2",
            "state": "COMPLETED",
            "commit_sha": "b" * 40,
            "manifest_sha256": "c" * 64,
            "exit_code": 0,
            "termination_class": "NORMAL_EXIT",
            "runtime_seconds": 42.5,
            "peak_rss_bytes": 1234,
            "result_path": f"{'a' * 32}/result.json",
            "result_sha256": "d" * 64,
            "equivalence_passed": None,
        }, "491701234567")
        self.assertEqual(observation.sensor, "whatsapp:491701234567")
        self.assertEqual(observation.kind, "message.experiment_status")
        self.assertNotIn("recipient", observation.payload)
        self.assertFalse(observation.payload["content_exported"])

    def test_meta_get_verification_and_signed_post_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = HostSettings(
                owner_wa_id="491701234567",
                business_phone_number_id="phone-1",
                meta_app_secret="app-secret",
                meta_verify_token="verify-token",
                whatsapp_access_token="access-token",
                state_path=str(Path(directory) / "state.sqlite3"),
            )
            app = create_app(settings=settings, client=object())

            with TestClient(app) as client:
                health = client.get("/healthz")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["status"], "ok")
                self.assertNotIn("deadman", health.json())
                privacy = client.get("/privacy")
                self.assertEqual(privacy.status_code, 200)
                self.assertIn("KAIROS Privacy Policy", privacy.text)
                self.assertTrue(privacy.headers["content-type"].startswith("text/html"))
                self.assertEqual(client.get("/data-deletion").status_code, 200)

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
                self.assertEqual(
                    client.get(
                        "/webhook",
                        params={
                            "hub.mode": "subscribe",
                            "hub.verify_token": "verify-token",
                        },
                    ).status_code,
                    403,
                )

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
