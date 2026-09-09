import hashlib
import hmac
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.host import HostSettings, create_app, experiment_completion_observation  # noqa: E402
from ckk.sovereign.media import MediaObservationEnricher  # noqa: E402
from ckk.sovereign.whatsapp import JsonTransportResult  # noqa: E402


class RecordingResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output=[],
            output_text=json.dumps({
                "action": "service_message",
                "text": "Dokument gelesen.",
                "template": None,
                "reason": "read supplied document",
                "salience": 0.8,
                "learning": [],
            }),
        )


class RecordingOutboundTransport:
    def post(self, url, headers, payload):
        return JsonTransportResult(200, {"messages": [{"id": "wamid.document-reply"}]})


class FixtureMediaTransport:
    content = b"%PDF-test"

    def metadata(self, media_id, access_token, graph_api_version):
        return {
            "id": media_id,
            "url": "https://lookaside.fbsbx.com/fixture",
            "mime_type": "application/pdf",
            "file_size": len(self.content),
            "sha256": hashlib.sha256(self.content).hexdigest(),
        }

    def download(self, url, access_token, maximum_bytes):
        return self.content, "application/pdf"


class FixtureTextExtractor:
    def extract(self, content, mime_type, filename):
        return {
            "extracted_text": "Content extracted from the PDF fixture.",
            "page_count": 1,
            "processed_pages": 1,
            "text_pages": 1,
            "ocr_pages": 0,
            "methods": ["pdftotext"],
            "truncated": False,
        }


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

    def test_signed_document_is_enriched_before_production_cognition(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = HostSettings(
                owner_wa_id="491701234567",
                business_phone_number_id="phone-1",
                meta_app_secret="app-secret",
                meta_verify_token="verify-token",
                whatsapp_access_token="access-token",
                state_path=str(Path(directory) / "state.sqlite3"),
            )
            responses = RecordingResponses()
            enricher = MediaObservationEnricher(
                "access-token", transport=FixtureMediaTransport(), extractor=FixtureTextExtractor()
            )
            app = create_app(
                settings=settings,
                client=SimpleNamespace(responses=responses),
                transport=RecordingOutboundTransport(),
                media_enricher=enricher,
            )
            message = {
                "object": "whatsapp_business_account",
                "entry": [{"changes": [{"value": {
                    "metadata": {"phone_number_id": "phone-1"},
                    "messages": [{
                        "id": "document-message",
                        "from": "491701234567",
                        "timestamp": str(int(time.time())),
                        "type": "document",
                        "document": {
                            "id": "123456789",
                            "filename": "paper.pdf",
                            "mime_type": "application/pdf",
                            "sha256": hashlib.sha256(FixtureMediaTransport.content).hexdigest(),
                        },
                    }],
                }}]}],
            }
            raw = json.dumps(message, separators=(",", ":")).encode()
            signature = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
            with TestClient(app) as client:
                posted = client.post("/webhook", content=raw, headers={"x-hub-signature-256": signature})
                self.assertEqual(posted.status_code, 202)
                deadline = time.time() + 3
                while not responses.calls and time.time() < deadline:
                    time.sleep(0.02)
                self.assertTrue(responses.calls)
                model_input = responses.calls[0]["input"][0]["content"]
                payload = json.loads(model_input)
                media = payload["current_observations"][0]["payload"]
                self.assertEqual(media["extraction_status"], "extracted")
                self.assertEqual(media["extracted_text"], "Content extracted from the PDF fixture.")
                self.assertEqual(media["document_provenance"]["artifact_sha256"], hashlib.sha256(FixtureMediaTransport.content).hexdigest())
                deadline = time.time() + 3
                while client.get("/healthz").json()["queue"].get("done") != 1 and time.time() < deadline:
                    time.sleep(0.02)
                self.assertEqual(client.get("/healthz").json()["queue"].get("done"), 1)


if __name__ == "__main__":
    unittest.main()
