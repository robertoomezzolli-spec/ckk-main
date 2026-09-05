import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.knowledge_adapter.index import CKKIndex, GitMirror, classify_source  # noqa: E402
from ckk.knowledge_adapter.api import AdapterSettings, create_app  # noqa: E402
from ckk.sovereign.knowledge import CKKKnowledgeClient  # noqa: E402
from ckk.sovereign.runtime import Observation  # noqa: E402
from ckk.sovereign.state import SQLiteStateStore  # noqa: E402


def git(path, *args):
    result = subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.test",
             "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.test"},
    )
    return result.stdout.strip()


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _maximum):
        return self.payload


class CKKKnowledgeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        source = root / "source"
        source.mkdir()
        git(source, "init", "-b", "main")
        grammar = source / "ckk_snapshot" / "ckk" / "gen"
        grammar.mkdir(parents=True)
        (grammar / "grammar.py").write_text(
            "MAXDIM = 3\n\ndef op_close(s):\n    return ('CYCLE', s)\n\ndef op_winding(s):\n    return ('INTEGER', s)\n"
        )
        git(source, "add", ".")
        git(source, "commit", "-m", "introduce grammar limit")
        self.first_commit = git(source, "rev-parse", "HEAD")
        (grammar / "grammar.py").write_text(
            "MAXDIM = 4\n\ndef op_close(s):\n    return ('CYCLE', s)\n\ndef op_winding(s):\n    return ('INTEGER', s)\n"
        )
        snapshot = source / "site" / "public" / "data"
        snapshot.mkdir(parents=True)
        (snapshot / "run34.json").write_text(
            json.dumps({"signature": {"snapshot_node": {"factor": "catalog metadata"}}, "operator": "snapshot_v6:0000"})
        )
        audit = source / "audit"
        audit.mkdir()
        (audit / "run34-audit.md").write_text(
            "# Run 34 audit\nSnapshot metadata is not a reconstructed grammar operator.\n"
        )
        git(source, "add", ".")
        git(source, "commit", "-m", "change dimension parameter and add snapshot")
        self.head = git(source, "rev-parse", "HEAD")
        mirror_path = root / "mirror.git"
        subprocess.run(["git", "clone", "--mirror", str(source), str(mirror_path)], check=True, capture_output=True)
        mirror = GitMirror("https://github.com/robertoomezzolli-spec/ckk.git", mirror_path, "main")
        self.index = CKKIndex(mirror, root / "index.sqlite3")
        self.index.rebuild(self.head)

    def test_ssh_remote_is_reported_as_canonical_github_source(self):
        mirror = GitMirror("git@github.com:robertoomezzolli-spec/ckk.git", self.index.mirror.path, "main")
        self.assertEqual(mirror.canonical_repository, "https://github.com/robertoomezzolli-spec/ckk")

    def tearDown(self):
        self.temporary.cleanup()

    def test_exact_symbol_and_text_retrieval_have_complete_provenance(self):
        for symbol in ("op_close", "op_winding"):
            result = self.index.search(f"show me {symbol}", mode="hybrid")
            item = result["items"][0]
            self.assertEqual(item["path"], "ckk_snapshot/ckk/gen/grammar.py")
            self.assertEqual(item["commit_sha"], self.head)
            self.assertEqual(len(item["blob_sha"]), 40)
            self.assertIn(symbol, item["symbols"])
            self.assertIn("exact_symbol", item["retrieval_methods"])
            self.assertEqual(item["source_kind"], "source_code")
            self.assertEqual(item["truth_status"], "external_evidence_unverified")

    def test_maxdim_current_value_and_history_are_distinct(self):
        current = self.index.search("MAXDIM", mode="exact")["items"][0]
        self.assertIn("MAXDIM = 4", current["excerpt"])
        history = self.index.history("MAXDIM", 10)["items"]
        commits = {item["commit_sha"] for item in history}
        self.assertIn(self.first_commit, commits)
        self.assertIn(self.head, commits)
        self.assertTrue(all(item["path"] == "ckk_snapshot/ckk/gen/grammar.py" for item in history))

    def test_snapshot_metadata_is_not_grammar_generated_source(self):
        snapshot = self.index.search("run34.json", mode="filename")["items"][0]
        source = self.index.search("op_close", mode="symbol")["items"][0]
        self.assertEqual(snapshot["source_kind"], "snapshot")
        self.assertIn("generated_result", snapshot["evidence_labels"])
        self.assertEqual(source["source_kind"], "source_code")
        self.assertNotIn("snapshot", source["evidence_labels"])
        audit_kind, audit_labels = classify_source("audit/run34-audit.md")
        self.assertEqual(audit_kind, "audit")
        self.assertEqual(audit_labels, ["audit", "documentation"])
        combined = self.index.search(
            "distinguish Run-34 snapshot metadata from grammar-generated fields", limit=8, mode="hybrid"
        )["items"]
        self.assertTrue(any(item["source_kind"] == "snapshot" for item in combined))
        self.assertTrue(any(item["path"] == "ckk_snapshot/ckk/gen/grammar.py" for item in combined))

    def test_commit_diff_is_bounded_and_provenanced(self):
        result = self.index.diff(self.first_commit[:10], self.head[:10])
        grammar = next(item for item in result["items"] if item["path"] == "ckk_snapshot/ckk/gen/grammar.py")
        self.assertEqual(grammar["base_commit_sha"], self.first_commit)
        self.assertEqual(grammar["commit_sha"], self.head)
        self.assertIn("-MAXDIM = 3", grammar["excerpt"])
        self.assertIn("+MAXDIM = 4", grammar["excerpt"])

    def test_semantic_retrieval_is_local_and_code_aware(self):
        result = self.index.search("where is the dimensional cutoff defined", mode="semantic")
        grammar = next(item for item in result["items"] if item["path"] == "ckk_snapshot/ckk/gen/grammar.py")
        self.assertIn("semantic_symbol_expansion", grammar["retrieval_methods"])
        self.assertTrue(any("semantic_vector" in item["retrieval_methods"] for item in result["items"]))

    def test_disk_index_remains_available_without_live_git_checkout(self):
        reopened = CKKIndex(self.index.mirror, self.index.database_path)
        result = reopened.search("op_close", mode="symbol")
        self.assertEqual(result["items"][0]["commit_sha"], self.head)
        self.assertEqual(result["items"][0]["path"], "ckk_snapshot/ckk/gen/grammar.py")

    def test_all_evidence_classes_are_explicit(self):
        self.assertEqual(classify_source("docs/design.md")[0], "documentation")
        self.assertEqual(classify_source("hypotheses/proposal.md")[0], "hypothesis")
        self.assertEqual(classify_source("audit/result.json")[0], "generated_result")

    def test_internal_api_is_authenticated_and_health_discloses_read_only_mode(self):
        self.index.refresh = lambda: self.index.status()
        settings = AdapterSettings(
            "https://github.com/robertoomezzolli-spec/ckk.git", "main", self.temporary.name, "z" * 32, 3600
        )
        app = create_app(settings, self.index)
        with TestClient(app) as client:
            self.assertEqual(client.post("/v1/search", json={"query": "op_close"}).status_code, 401)
            accepted = client.post(
                "/v1/search", json={"query": "op_close", "mode": "symbol"},
                headers={"authorization": f"Bearer {'z' * 32}"},
            )
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.json()["items"][0]["commit_sha"], self.head)
            health = client.get("/healthz")
            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["read_only_source"])

    def test_read_and_symbol_are_git_tree_bounded_and_commit_pinned(self):
        read = self.index.mirror.read_path("ckk_snapshot/ckk/gen/grammar.py", self.head)
        self.assertEqual(read["commit_sha"], self.head)
        self.assertEqual(read["paths"], ["ckk_snapshot/ckk/gen/grammar.py"])
        self.assertEqual(read["source_class"], "SOURCE_CODE")
        self.assertIn("def op_winding", read["excerpt"])
        symbol = self.index.symbol("op_winding")
        self.assertEqual(symbol["commit_sha"], self.head)
        self.assertIn("op_winding", symbol["operator_names"])
        with self.assertRaises(ValueError):
            self.index.mirror.read_path("../outside", self.head)

    def test_run_api_delegates_only_validated_request_to_sealed_queue(self):
        class FakeRunQueue:
            def __init__(self):
                self.calls = []

            def run(self, seed, operators, controls, budgets, ref):
                self.calls.append((seed, operators, controls, budgets, ref))
                return {
                    "status": "completed", "repository": "https://github.com/robertoomezzolli-spec/ckk",
                    "commit_sha": self_head, "paths": ["ckk_snapshot/ckk/gen/grammar.py"],
                    "operator_names": ["op_close"], "run_id": "a" * 32, "seed_hash": "b" * 64,
                    "controls": controls, "compute_limits": budgets,
                }

        self_head = self.head
        queue = FakeRunQueue()
        self.index.refresh = lambda: self.index.status()
        settings = AdapterSettings(
            "https://github.com/robertoomezzolli-spec/ckk.git", "main", self.temporary.name, "z" * 32, 3600
        )
        with TestClient(create_app(settings, self.index, queue)) as client:
            response = client.post(
                "/v1/run",
                headers={"authorization": f"Bearer {'z' * 32}"},
                json={
                    "seed": "SEED_R", "operators": [], "controls": ["structural_identity"],
                    "budgets": {"levels": 1, "state_cap": 100, "derivation_cap": 1000,
                                "wall_seconds": 5, "memory_mb": 256}, "ref": self.head,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queue.calls[0][0], "SEED_R")
        self.assertEqual(queue.calls[0][4], self.head)

    def test_client_bounds_context_and_marks_external_evidence(self):
        payload = self.index.search("op_close", limit=1)
        client = CKKKnowledgeClient("http://adapter", "x" * 32, maximum_results=1)
        client._opener = lambda *_args, **_kwargs: Response(payload)
        inbound = Observation("wa:1", "whatsapp:1", "message.text", {"text": "show me op_close"}, 1.0)
        evidence = client.observations_for(inbound)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].sensor, "ckk.repository")
        self.assertEqual(evidence[0].kind, "evidence.source")
        self.assertEqual(evidence[0].payload["commit_sha"], self.head)
        self.assertEqual(evidence[0].payload["belief_status"], "not_committed")
        self.assertLessEqual(len(evidence[0].payload["excerpt"]), 2800)
        unrelated = Observation("wa:2", "whatsapp:1", "message.text", {"text": "hello"}, 1.0)
        self.assertEqual(client.observations_for(unrelated), ())

    def test_client_reserves_budget_for_history_and_current_source(self):
        payload = self.index.retrieve("where does MAXDIM originate", limit=6)
        client = CKKKnowledgeClient("http://adapter", "x" * 32, maximum_results=6)
        client._opener = lambda *_args, **_kwargs: Response(payload)
        inbound = Observation(
            "wa:history", "whatsapp:1", "message.text", {"text": "where does MAXDIM originate"}, 1.0
        )
        evidence = client.observations_for(inbound)
        kinds = {item.payload["evidence_type"] for item in evidence}
        self.assertIn("commit_history", kinds)
        self.assertIn("retrieved_chunk", kinds)
        origin = next(item for item in evidence if item.payload["history_position"] == "oldest_matching_change")
        self.assertEqual(origin.payload["commit_sha"], self.first_commit)
        self.assertEqual(origin.payload["path"], "ckk_snapshot/ckk/gen/grammar.py")

    def test_client_prioritizes_query_relevant_file_in_bounded_diff(self):
        payload = {
            "commit_sha": self.head,
            "items": [],
            "diff": [
                {"repository": "https://github.com/robertoomezzolli-spec/ckk", "commit_sha": self.head,
                 "base_commit_sha": self.first_commit, "path": "README.md", "source_kind": "commit_diff",
                 "evidence_labels": ["commit_diff"], "excerpt": "unrelated prose"},
                {"repository": "https://github.com/robertoomezzolli-spec/ckk", "commit_sha": self.head,
                 "base_commit_sha": self.first_commit, "path": "ckk_snapshot/ckk/gen/grammar.py",
                 "source_kind": "commit_diff", "evidence_labels": ["commit_diff"],
                 "excerpt": "-MAXDIM = 3\n+MAXDIM = 4"},
            ],
        }
        client = CKKKnowledgeClient("http://adapter", "x" * 32, maximum_results=1)
        client._opener = lambda *_args, **_kwargs: Response(payload)
        inbound = Observation(
            "wa:diff", "whatsapp:1", "message.text",
            {"text": "what changed between commits for MAXDIM"}, 1.0,
        )
        evidence = client.observations_for(inbound)
        self.assertEqual(evidence[0].payload["path"], "ckk_snapshot/ckk/gen/grammar.py")

    def test_provenance_persists_but_content_never_enters_episode_retrieval(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStateStore(str(Path(directory) / "state.sqlite3"))
            observation = Observation(
                "ckk:e1", "ckk.repository", "evidence.source",
                {
                    "repository": "https://github.com/robertoomezzolli-spec/ckk", "ref": "main",
                    "commit_sha": self.head, "base_commit_sha": "", "blob_sha": "a" * 40,
                    "path": "ckk_snapshot/ckk/gen/grammar.py", "start_line": 1, "end_line": 8,
                    "source_kind": "source_code", "evidence_labels": ["source_code"],
                    "content_sha256": "b" * 64, "excerpt": "SECRET EXCERPT MUST NOT PERSIST",
                }, 0.75,
            )
            store.record_external_evidence("wa:1", (observation,))
            self.assertEqual(store.external_evidence_count(), 1)
            self.assertEqual(store.recent_episodes(), [])
            with sqlite3.connect(store.path) as db:
                serialized = "\n".join(str(row) for row in db.execute("SELECT * FROM external_evidence"))
            self.assertNotIn("SECRET EXCERPT", serialized)


if __name__ == "__main__":
    unittest.main()
