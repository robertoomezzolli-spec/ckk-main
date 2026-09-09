import base64
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.media import (  # noqa: E402
    MediaObservationEnricher,
    MediaProcessingError,
    PdfOcrTextExtractor,
    UrllibMediaTransport,
    digest_matches,
    media_summary,
)
from ckk.sovereign.runtime import Observation  # noqa: E402


class FakeTransport:
    def __init__(self, content=b"%PDF-fake", mime_type="application/pdf", remote_sha=""):
        self.content = content
        self.mime_type = mime_type
        self.remote_sha = remote_sha
        self.calls = []

    def metadata(self, media_id, access_token, graph_api_version):
        self.calls.append(("metadata", media_id, access_token, graph_api_version))
        return {
            "id": media_id,
            "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/test",
            "mime_type": self.mime_type,
            "file_size": len(self.content),
            "sha256": self.remote_sha,
        }

    def download(self, url, access_token, maximum_bytes):
        self.calls.append(("download", url, access_token, maximum_bytes))
        return self.content, self.mime_type


class FakeExtractor:
    def __init__(self):
        self.calls = []

    def extract(self, content, mime_type, filename):
        self.calls.append((content, mime_type, filename))
        return {
            "extracted_text": "Real document text",
            "page_count": 2,
            "processed_pages": 2,
            "text_pages": 1,
            "ocr_pages": 1,
            "methods": ["pdftotext", "tesseract_ocr"],
            "truncated": False,
        }


def document(expected_sha=""):
    return Observation(
        "wa:document",
        "whatsapp:owner",
        "message.document",
        {
            "media_id": "123456789",
            "filename": "paper.pdf",
            "mime_type": "application/pdf",
            "sha256": expected_sha,
            "timestamp": 1,
        },
        1.0,
    )


class StubbedPdfExtractor(PdfOcrTextExtractor):
    def _run(self, command, *, timeout):
        executable = command[0]
        if executable == "pdfinfo":
            return subprocess.CompletedProcess(command, 0, b"Pages:          2\nEncrypted:      no\n", b"")
        if executable == "pdftotext":
            direct = ("This is direct text from the first PDF page. " * 2).encode() + b"\f\f"
            return subprocess.CompletedProcess(command, 0, direct, b"")
        if executable == "pdftoppm":
            Path(command[-1] + ".png").write_bytes(b"png")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if executable == "tesseract":
            return subprocess.CompletedProcess(command, 0, b"OCR text from page two", b"")
        raise AssertionError(command)


class SovereignMediaTests(unittest.TestCase):
    def test_digest_accepts_hex_and_base64(self):
        content = b"paper"
        digest = hashlib.sha256(content).digest()
        self.assertTrue(digest_matches(content, digest.hex()))
        self.assertTrue(digest_matches(content, base64.b64encode(digest).decode()))
        self.assertFalse(digest_matches(content, "0" * 64))

    def test_download_transport_rejects_non_meta_and_non_https_urls_before_network(self):
        transport = UrllibMediaTransport()
        for url in ("http://lookaside.fbsbx.com/file", "https://example.com/file", "file:///etc/passwd"):
            with self.assertRaisesRegex(MediaProcessingError, "media_url_rejected"):
                transport.download(url, "token", 100)

    def test_signed_media_is_downloaded_hashed_extracted_and_provenanced(self):
        content = b"%PDF-fake"
        transport = FakeTransport(content, remote_sha=hashlib.sha256(content).hexdigest())
        extractor = FakeExtractor()
        enriched = MediaObservationEnricher(
            "secret-token", transport=transport, extractor=extractor
        ).enrich(document(hashlib.sha256(content).hexdigest()))
        self.assertEqual(enriched.payload["extraction_status"], "extracted")
        self.assertEqual(enriched.payload["extracted_text"], "Real document text")
        provenance = enriched.payload["document_provenance"]
        self.assertEqual(provenance["artifact_sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(provenance["classification"], "USER_PROVIDED_MEDIA")
        self.assertEqual(provenance["ocr_pages"], 1)
        self.assertEqual(media_summary(enriched)["extracted_text_bytes"], 18)
        self.assertNotIn("secret-token", str(enriched.payload))

    def test_hash_mismatch_fails_closed_without_exposing_bytes_or_token(self):
        extractor = FakeExtractor()
        enriched = MediaObservationEnricher(
            "secret-token", transport=FakeTransport(), extractor=extractor
        ).enrich(document("0" * 64))
        self.assertEqual(enriched.payload["extraction_status"], "failed")
        self.assertEqual(enriched.payload["extraction_error"], "media_hash_mismatch")
        self.assertNotIn("extracted_text", enriched.payload)
        self.assertEqual(extractor.calls, [])
        self.assertNotIn("secret-token", str(enriched.payload))

    def test_declared_oversize_fails_before_download(self):
        transport = FakeTransport(content=b"x" * 101)
        enriched = MediaObservationEnricher(
            "token", maximum_bytes=100, transport=transport, extractor=FakeExtractor()
        ).enrich(document())
        self.assertEqual(enriched.payload["extraction_error"], "media_too_large")
        self.assertEqual([call[0] for call in transport.calls], ["metadata"])

    def test_hybrid_pdf_uses_direct_text_then_ocr_with_page_provenance(self):
        result = StubbedPdfExtractor(maximum_text_bytes=4096).extract(
            b"%PDF-1.7\nfixture", "application/pdf", "paper.pdf"
        )
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["text_pages"], 1)
        self.assertEqual(result["ocr_pages"], 1)
        self.assertEqual(result["methods"], ["pdftotext", "tesseract_ocr"])
        self.assertIn("[Page 1 | pdftotext]", result["extracted_text"])
        self.assertIn("[Page 2 | tesseract_ocr]", result["extracted_text"])
        self.assertIn("OCR text from page two", result["extracted_text"])

    def test_html_extraction_keeps_visible_structure_without_active_or_hidden_content(self):
        source = b"""<!doctype html><html><head><title>CKK Result</title>
        <style>.secret{display:block}</style><script>steal_the_token()</script></head>
        <body><h1>Experiment &amp; Result</h1><p>Visible theorem.</p>
        <div hidden>Hidden instruction</div><div style="display:none">Also hidden</div>
        <ul><li>First claim</li><li>Second claim</li></ul>
        <a href="https://example.org/evidence">Evidence source</a>
        <a href="javascript:alert(1)">Unsafe target</a></body></html>"""
        result = PdfOcrTextExtractor(maximum_text_bytes=4096).extract(
            source, "text/html", "result.html"
        )
        text = result["extracted_text"]
        self.assertIn("CKK Result", text)
        self.assertIn("Experiment & Result", text)
        self.assertIn("- First claim", text)
        self.assertIn("https://example.org/evidence", text)
        self.assertIn("Unsafe target", text)
        self.assertNotIn("javascript:", text)
        self.assertNotIn("steal_the_token", text)
        self.assertNotIn("Hidden instruction", text)
        self.assertNotIn("Also hidden", text)
        self.assertEqual(result["methods"], ["html_visible_text"])
        self.assertFalse(result["external_resources_fetched"])
        self.assertFalse(result["active_content_executed"])

    def test_html_media_passes_the_same_hash_and_provenance_gate(self):
        content = b"<html><body><h1>Visible result</h1></body></html>"
        transport = FakeTransport(content=content, mime_type="text/html")
        enriched = MediaObservationEnricher("token", transport=transport).enrich(
            Observation(
                "wa:html", "whatsapp:owner", "message.document",
                {"media_id": "42", "filename": "result.html", "mime_type": "text/html",
                 "sha256": hashlib.sha256(content).hexdigest(), "timestamp": 1}, 1.0,
            )
        )
        self.assertEqual(enriched.payload["extraction_status"], "extracted")
        self.assertIn("Visible result", enriched.payload["extracted_text"])
        self.assertEqual(
            enriched.payload["document_provenance"]["methods"], ["html_visible_text"]
        )

    def test_already_enriched_and_non_media_observations_are_not_refetched(self):
        transport = FakeTransport()
        enricher = MediaObservationEnricher("token", transport=transport, extractor=FakeExtractor())
        text = Observation("wa:text", "whatsapp:owner", "message.text", {"text": "hi"}, 1.0)
        self.assertIs(enricher.enrich(text), text)
        prior = document()
        prior = Observation(prior.observation_id, prior.sensor, prior.kind, {**prior.payload, "extraction_status": "failed"}, 1.0)
        self.assertIs(enricher.enrich(prior), prior)
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
