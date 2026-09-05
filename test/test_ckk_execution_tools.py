import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.brain import OpenAIResponsesCognition  # noqa: E402
from ckk.sovereign.research_tools import SealedResearchToolRegistry  # noqa: E402
from ckk.sovereign.whatsapp import WhatsAppConfig  # noqa: E402


SHA = "a" * 40
GRAMMAR = "ckk_snapshot/ckk/gen/grammar.py"


class FakeCKK:
    def search(self, query, *, limit, mode):
        return {"repository": "https://github.com/robertoomezzolli-spec/ckk", "commit_sha": SHA,
                "paths": [GRAMMAR], "operator_names": ["op_winding"], "items": [], "query": query,
                "run_id": None, "seed_hash": None, "controls": [], "compute_limits": {}}

    def read(self, path, *, ref=None):
        return {"repository": "https://github.com/robertoomezzolli-spec/ckk", "commit_sha": SHA,
                "path": path, "paths": [path], "operator_names": [], "excerpt": "def op_winding(s): pass",
                "source_class": "SOURCE_CODE", "run_id": None, "seed_hash": None, "controls": [],
                "compute_limits": {}}

    def symbol(self, name, *, limit):
        return self.search(name, limit=limit, mode="symbol")

    def run(self, seed, *, operators, controls, budgets, ref=None):
        return {"repository": "https://github.com/robertoomezzolli-spec/ckk", "commit_sha": SHA,
                "paths": [GRAMMAR, "ckk_snapshot/ckk/gen/expand.py"], "operator_names": ["op_close"],
                "run_id": "b" * 32, "seed_hash": "c" * 64, "controls": controls,
                "compute_limits": budgets, "provenance": [{"operator": "op_close"}],
                "artifact": "b/result.json", "source_kind": "GENERATED_RUN"}

    def publish(self, run_id):
        return {"repository": "https://github.com/robertoomezzolli-spec/ckk", "commit_sha": SHA,
                "paths": [GRAMMAR, "ckk_snapshot/ckk/gen/expand.py"], "operator_names": ["op_close"],
                "run_id": run_id, "seed_hash": "c" * 64, "controls": ["structural_identity"],
                "compute_limits": {"levels": 1, "state_cap": 100, "derivation_cap": 1000,
                                   "wall_seconds": 5, "memory_mb": 256},
                "publication_url": f"https://example.test/research/{run_id}", "classification": "DIRECT",
                "controls_completed": True, "status": "published", "source_kind": "GENERATED_RUN"}


class ScriptedResponses:
    def __init__(self):
        self.calls = []
        self.step = 0

    def create(self, **kwargs):
        self.calls.append(kwargs)
        scripts = [
            SimpleNamespace(type="function_call", name="search", namespace="ckk", call_id="call-search",
                            arguments=json.dumps({"query": "op_winding", "limit": 6, "mode": "hybrid"})),
            SimpleNamespace(type="function_call", name="read", namespace="ckk", call_id="call-read",
                            arguments=json.dumps({"path": GRAMMAR, "ref": SHA})),
            SimpleNamespace(type="function_call", name="run", namespace="ckk", call_id="call-run",
                            arguments=json.dumps({
                                "seed": "SEED_R", "operators": [], "controls": ["structural_identity"],
                                "budgets": {"levels": 1, "state_cap": 100, "derivation_cap": 1000,
                                            "wall_seconds": 5, "memory_mb": 256}, "ref": SHA,
                            })),
        ]
        if self.step < len(scripts):
            item = scripts[self.step]
            self.step += 1
            return SimpleNamespace(output=[item], output_text="")
        result = {"answer": "verified", "commit_sha": SHA, "operator_names": ["op_close"]}
        return SimpleNamespace(output=[], output_text=json.dumps(result))


class ScriptedPublishingResponses:
    def __init__(self):
        self.calls = []
        self.step = 0

    def create(self, **kwargs):
        self.calls.append(kwargs)
        scripts = [
            SimpleNamespace(type="function_call", name="run", namespace="ckk", call_id="call-run",
                            arguments=json.dumps({
                                "seed": "SEED_R", "operators": [], "controls": ["structural_identity"],
                                "budgets": {"levels": 1, "state_cap": 100, "derivation_cap": 1000,
                                            "wall_seconds": 5, "memory_mb": 256}, "ref": None,
                            })),
            SimpleNamespace(type="function_call", name="publish", namespace="research", call_id="call-publish",
                            arguments=json.dumps({"run_id": "b" * 32})),
        ]
        if self.step < len(scripts):
            item = scripts[self.step]
            self.step += 1
            return SimpleNamespace(output=[item], output_text="")
        result = {"short_verdict": "COMPLETED GENERATED RUN",
                  "publication_url": f"https://example.test/research/{'b' * 32}",
                  "run_id": "b" * 32, "commit_sha": SHA}
        return SimpleNamespace(output=[], output_text=json.dumps(result))


class CKKExecutionToolTests(unittest.TestCase):
    def test_production_cognition_receives_namespaced_registry_and_executes_tool_loop(self):
        responses = ScriptedResponses()
        client = SimpleNamespace(responses=responses)
        registry = SealedResearchToolRegistry(FakeCKK())
        brain = OpenAIResponsesCognition(WhatsAppConfig("491701234567", "phone"), client=client,
                                         tool_registry=registry)
        outcome = brain.research("Find the source and run the generator.")
        self.assertEqual([item["logical_name"] for item in outcome["trace"]["calls"]],
                         ["ckk.search", "ckk.read", "ckk.run"])
        first = responses.calls[0]
        self.assertEqual([item["name"] for item in first["tools"]], ["whatsapp", "ckk", "research"])
        self.assertEqual([item["name"] for item in first["tools"][1]["tools"]],
                         ["search", "read", "symbol", "run"])
        self.assertIn("whatsapp.send", outcome["trace"]["capabilities"])
        self.assertIn("ckk.run", outcome["trace"]["capabilities"])
        self.assertIn("research.publish", outcome["trace"]["capabilities"])
        self.assertEqual(first["parallel_tool_calls"], False)
        self.assertTrue(any(
            isinstance(item, dict) and item.get("type") == "function_call_output"
            for call in responses.calls[1:] for item in call["input"]
        ))

    def test_real_repository_generator_files_are_called_without_reimplementation(self):
        request = {
            "schema_version": 1, "run_id": "d" * 32,
            "repository": "https://github.com/robertoomezzolli-spec/ckk", "commit_sha": SHA,
            "seed": "SEED_R", "seed_hash": "e" * 64, "operators": [],
            "controls": ["structural_identity"],
            "compute_limits": {"levels": 1, "state_cap": 100, "derivation_cap": 1000,
                               "wall_seconds": 5, "memory_mb": 256},
            "source_paths": [GRAMMAR, "ckk_snapshot/ckk/gen/expand.py"],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path, result_path = root / "request.json", root / "result.json"
            request_path.write_text(json.dumps(request))
            command = [sys.executable, str(ROOT / "ckk_snapshot/ckk/knowledge_adapter/execute_run.py"),
                       str(request_path), str(ROOT / "ckk_snapshot/ckk/gen"), str(result_path)]
            subprocess.run(command, check=True, capture_output=True)
            result = json.loads(result_path.read_text())
        self.assertEqual(result["source_kind"], "GENERATED_RUN")
        self.assertEqual(result["operator_names"], ["op_close"])
        self.assertEqual(result["provenance"][0]["operator"], "op_close")
        self.assertEqual(result["paths"], request["source_paths"])
        self.assertEqual(result["belief_status"], "not_committed")

    def test_registry_rejects_any_non_allowlisted_capability(self):
        registry = SealedResearchToolRegistry(FakeCKK())
        with self.assertRaises(PermissionError):
            registry.execute("shell", {"command": "id"})

    def test_research_publish_is_sealed_to_run_id(self):
        registry = SealedResearchToolRegistry(FakeCKK())
        result = registry.execute("publish", {"run_id": "b" * 32}, namespace="research")
        self.assertEqual(result["publication_url"], f"https://example.test/research/{'b' * 32}")
        self.assertEqual(registry.invocations[-1]["logical_name"], "research.publish")
        definition = registry.definitions[-1]
        self.assertEqual(definition["name"], "research")
        self.assertEqual([item["name"] for item in definition["tools"]], ["publish"])

    def test_production_cognition_executes_run_then_sealed_publish(self):
        responses = ScriptedPublishingResponses()
        brain = OpenAIResponsesCognition(
            WhatsAppConfig("491701234567", "phone"), client=SimpleNamespace(responses=responses),
            tool_registry=SealedResearchToolRegistry(FakeCKK()),
        )
        outcome = brain.publish_research("Run and publish one bounded experiment.")
        self.assertEqual([item["logical_name"] for item in outcome["trace"]["calls"]],
                         ["ckk.run", "research.publish"])
        self.assertEqual(outcome["result"]["run_id"], "b" * 32)
        self.assertEqual(outcome["trace"]["calls"][1]["status"], "published")
        self.assertEqual(responses.calls[0]["tool_choice"], "required")


if __name__ == "__main__":
    unittest.main()
