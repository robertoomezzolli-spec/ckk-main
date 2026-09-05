import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.knowledge_adapter.publishing import PublicationError, ResearchPublisher  # noqa: E402
from ckk.knowledge_adapter.research_site import create_research_site  # noqa: E402


RUN_ID = "a" * 32
SHA = "b" * 40
REPOSITORY = "https://github.com/robertoomezzolli-spec/ckk"
PATHS = ["ckk_snapshot/ckk/gen/grammar.py", "ckk_snapshot/ckk/gen/expand.py"]
LIMITS = {"levels": 1, "state_cap": 100, "derivation_cap": 1000, "wall_seconds": 5, "memory_mb": 256}


def write_run(root: Path, *, extra_result=None):
    seed = "SEED_R"
    request = {
        "schema_version": 1, "run_id": RUN_ID, "repository": REPOSITORY, "commit_sha": SHA,
        "seed": seed, "seed_hash": hashlib.sha256(seed.encode()).hexdigest(), "operators": [],
        "controls": ["structural_identity"], "compute_limits": LIMITS, "source_paths": PATHS,
    }
    result = {
        "schema_version": 1, "status": "completed", "source_kind": "GENERATED_RUN",
        "evidence_labels": ["generated_run"], "truth_status": "external_evidence_unverified",
        "belief_status": "not_committed", "repository": REPOSITORY, "commit_sha": SHA, "paths": PATHS,
        "operator_names": ["op_close"], "registered_operator_names": ["op_close", "op_product"],
        "run_id": RUN_ID, "seed": seed, "seed_hash": request["seed_hash"],
        "controls": ["structural_identity"], "compute_limits": LIMITS,
        "state_count": 2, "derivation_count": 1, "max_dim": 1, "kinds": ["R", "closed"],
        "state_signature_sha256": "c" * 64, "wall_seconds": 0.012,
        "provenance": [{"operator": "op_close", "inputs": [["R", 1]], "output": ["closed", 1], "level": 1}],
        "artifact": f"{RUN_ID}/result.json",
    }
    if extra_result:
        result.update(extra_result)
    directory = root / RUN_ID
    directory.mkdir(parents=True)
    (directory / "request.json").write_text(json.dumps(request), encoding="utf-8")
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")


class ResearchPublishingTests(unittest.TestCase):
    def test_deterministic_publication_has_required_sections_provenance_and_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts, publications = root / "artifacts", root / "publications"
            write_run(artifacts)
            publisher = ResearchPublisher(artifacts, publications, "https://example.test/research")
            first = publisher.publish(RUN_ID)
            first_html = (publications / RUN_ID / "index.html").read_bytes()
            second = publisher.publish(RUN_ID)
            self.assertEqual(first, second)
            self.assertEqual(first_html, (publications / RUN_ID / "index.html").read_bytes())
            self.assertEqual(first["publication_url"], f"https://example.test/research/{RUN_ID}")
            self.assertEqual(first["commit_sha"], SHA)
            self.assertTrue(first["controls_completed"])
            report = json.loads((publications / RUN_ID / "report.json").read_text())
            self.assertEqual(report["seed_text"], "SEED_R")
            self.assertEqual(report["operator_set_observed"], ["op_close"])
            self.assertEqual(report["classification"], "DIRECT")
            page = first_html.decode()
            for heading in ("SOURCE", "RUN", "INTERPRETATION", "HYPOTHESIS", "VERDICT", "PROVENANCE / BACKTRACE"):
                self.assertIn(heading, page)
            for artifact in ("report.json", "report.md", "artifacts/request.json", "artifacts/result.json"):
                self.assertTrue((publications / RUN_ID / artifact).is_file())
            index = json.loads((publications / "index.json").read_text())
            self.assertEqual(index["experiments"][0]["run_id"], RUN_ID)

    def test_sensitive_artifact_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            write_run(artifacts, extra_result={"access_token": "must-not-publish"})
            with self.assertRaises(PublicationError):
                ResearchPublisher(artifacts, root / "publications", "https://example.test/research").publish(RUN_ID)

    def test_public_surface_is_read_only_and_allowlisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts, publications = root / "artifacts", root / "publications"
            write_run(artifacts)
            ResearchPublisher(artifacts, publications, "https://example.test/research").publish(RUN_ID)
            with TestClient(create_research_site(publications)) as client:
                page = client.get(f"/research/{RUN_ID}")
                self.assertEqual(page.status_code, 200)
                self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
                self.assertEqual(client.get("/research/").status_code, 200)
                self.assertEqual(client.get(f"/research/{RUN_ID}/report.json").status_code, 200)
                self.assertEqual(client.get(f"/research/{RUN_ID}/artifacts/result.json").status_code, 200)
                self.assertEqual(client.get(f"/research/{RUN_ID}/../../etc/passwd").status_code, 404)
                self.assertEqual(client.post(f"/research/{RUN_ID}").status_code, 405)


if __name__ == "__main__":
    unittest.main()
