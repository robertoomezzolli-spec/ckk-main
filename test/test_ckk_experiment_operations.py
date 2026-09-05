import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.knowledge_adapter.experiment_ops import ExperimentOperations, ExperimentSettings  # noqa: E402
from ckk.knowledge_adapter.index import GitMirror  # noqa: E402


REPOSITORY = "https://github.com/robertoomezzolli-spec/ckk-main"
BRANCH = "experiment/solar-system-provenance-cascade"


def git(path, *args):
    result = subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True, text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.test",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.test",
        },
    )
    return result.stdout.strip()


class ExperimentOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        source = root / "source"
        source.mkdir()
        git(source, "init", "-b", BRANCH)
        experiment = source / "experiments" / "fixed.py"
        experiment.parent.mkdir()
        experiment.write_text("print('fixed')\n", encoding="utf-8")
        git(source, "add", ".")
        git(source, "commit", "-m", "frozen")
        commit = git(source, "rev-parse", "HEAD")
        mirror_path = root / "cache" / "repository.git"
        mirror_path.parent.mkdir()
        subprocess.run(["git", "clone", "--mirror", str(source), str(mirror_path)], check=True, capture_output=True)
        git(mirror_path, "remote", "set-url", "origin", REPOSITORY + ".git")
        manifest = {
            "schema_version": 1,
            "experiment_id": "test",
            "repository": REPOSITORY,
            "branch": BRANCH,
            "target_commit": commit,
            "experiment_entry_point": "experiments/fixed.py",
            "source_files": [{
                "path": "experiments/fixed.py",
                "sha256": hashlib.sha256(experiment.read_bytes()).hexdigest(),
            }],
            "freeze_statement": (
                "No hypothesis, threshold, horizon, initial condition, null, permutation count, "
                "or inclusion rule may be changed after execution begins."
            ),
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        settings = ExperimentSettings(
            repository_url=REPOSITORY + ".git",
            branch=BRANCH,
            target_commit=commit,
            cache_directory=str(root / "cache"),
            control_directory=str(root / "control"),
            artifact_directory=str(root / "artifacts"),
            manifest_path=str(manifest_path),
        )
        self.root = root
        self.commit = commit
        self.ops = ExperimentOperations(settings, GitMirror(settings.repository_url, mirror_path, BRANCH))

    def tearDown(self):
        self.temporary.cleanup()

    def test_manifest_source_hashes_and_read_only_repository_status(self):
        manifest = self.ops.manifest()
        self.assertEqual(manifest["status"], "verified")
        self.assertTrue(manifest["source_verification"][0]["matches"])
        selected = self.ops.repo("checkout", ref=self.commit)
        self.assertEqual(selected["commit_sha"], self.commit)
        self.assertFalse(selected["source_writable"])
        status = self.ops.repo("status")
        self.assertTrue(status["clean"])
        self.assertEqual(status["push_url"], "disabled://read-only")
        read = self.ops.repo("read", path="experiments/fixed.py", ref=self.commit)
        self.assertEqual(read["content_sha256"], manifest["source_verification"][0]["actual_sha256"])

    def test_production_manifest_contains_every_frozen_preregistered_threshold(self):
        manifest = json.loads(
            (ROOT / "sealed" / "fresh_seed_closure_plateau_v2_execution_manifest.json").read_text()
        )
        self.assertEqual(manifest["target_commit"], "5faf926d6cc324e08c32649e1b92cf57f3c56cb3")
        self.assertEqual(manifest["generator"]["horizons"], [2, 3, 4, 5, 6, 7])
        self.assertEqual(manifest["generator"]["fresh_initial_carrier_occupancies"], [2, 3])
        self.assertEqual(manifest["closure_completion_specificity"]["permutations_per_preregistered_test"], 4000)
        self.assertEqual(manifest["closure_completion_specificity"]["minimum_n_per_kind"], 3)
        self.assertEqual(manifest["closure_completion_specificity"]["maximum_one_sided_pairwise_permutation_p"], 0.01)
        self.assertEqual(manifest["nonzero_plateau"]["minimum_n_per_horizon"], 5)
        self.assertEqual(manifest["nonzero_plateau"]["maximum_range_bits"], 0.05)
        self.assertEqual(manifest["nonzero_plateau"]["minimum_mean_bits"], 0.15)
        coupling = manifest["floor_corrected_pressure_opening_coupling"]
        self.assertEqual(coupling["minimum_n_per_horizon"], 20)
        self.assertEqual(coupling["minimum_observed_rho"], 0.25)
        self.assertEqual(coupling["minimum_rho_excess_over_null_median"], 0.20)
        self.assertEqual(coupling["maximum_one_sided_permutation_p"], 0.01)

    def test_queue_is_allowlisted_and_full_run_requires_equivalence(self):
        digest = self.ops.manifest()["manifest_sha256"]
        self.ops.repo("checkout", ref=self.commit)
        queued = self.ops.start("supervisor_smoke", digest)
        self.assertRegex(queued["job_id"], r"^[0-9a-f]{32}$")
        request = json.loads((self.root / "control" / "requests" / f"{queued['job_id']}.json").read_text())
        self.assertEqual(request["task"], "supervisor_smoke")
        self.assertNotIn("command", request)
        with self.assertRaises(ValueError):
            self.ops.start("arbitrary_shell", digest)
        request_path = self.root / "control" / "requests" / f"{queued['job_id']}.json"
        request_path.unlink()
        status_path = self.root / "control" / "status" / f"{queued['job_id']}.json"
        status = json.loads(status_path.read_text())
        status["state"] = "STOPPED"
        status_path.write_text(json.dumps(status))
        with self.assertRaisesRegex(PermissionError, "equivalence"):
            self.ops.start("fresh_seed_closure_plateau_v2", digest)

    def test_stop_file_read_hash_and_metrics_are_workspace_bounded(self):
        digest = self.ops.manifest()["manifest_sha256"]
        self.ops.repo("checkout", ref=self.commit)
        queued = self.ops.start("supervisor_smoke", digest)
        stopped = self.ops.stop(queued["job_id"])
        self.assertEqual(stopped["status"], "stop_requested")
        artifact = self.root / "artifacts" / queued["job_id"]
        artifact.mkdir()
        (artifact / "result.json").write_text('{"status":"ok"}\n')
        path = f"{queued['job_id']}/result.json"
        read = self.ops.file_read(path)
        hashed = self.ops.file_hash(path)
        self.assertIn('"status":"ok"', read["excerpt"])
        self.assertEqual(hashed["sha256"], hashlib.sha256((artifact / "result.json").read_bytes()).hexdigest())
        self.assertIn("excerpt_sha256", read)
        with self.assertRaises(ValueError):
            self.ops.file_read("../../etc/passwd")
        metrics = self.ops.metrics(queued["job_id"])
        self.assertFalse(metrics["kernel_log_access"])
        self.assertIn("artifact_disk", metrics)


if __name__ == "__main__":
    unittest.main()
