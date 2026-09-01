import tempfile
import sys
import unittest
from pathlib import Path


GEN = Path(__file__).resolve().parents[1] / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

from expand import expand_auditable  # noqa: E402
from stream_expand import ComputeLimitReached, ComputeLimits, open_engine  # noqa: E402


LIMITS = ComputeLimits(
    wall_seconds=60,
    ram_mb=2_048,
    minimum_free_disk_mb=1,
)


class StreamingExpansionTests(unittest.TestCase):
    def test_exact_historical_signature_equivalence_through_level_three(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = open_engine(Path(directory) / "scale.sqlite", LIMITS, batch_size=37)
            try:
                result = engine.run_to_level(3)
                self.assertEqual(result["completed_level"], 3)
                reference, _ = expand_auditable(levels=3, cap=1_000_000)
                reconstructed = {
                    engine.reconstruct_signature(row[0])
                    for row in engine.connection.execute("SELECT id FROM states")
                }
                self.assertEqual(reconstructed, set(reference))
                self.assertEqual([row["total_states"] for row in engine.level_rows()], [15, 53, 372])
            finally:
                engine.close()

    def test_provenance_is_referenced_not_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = open_engine(Path(directory) / "scale.sqlite", LIMITS)
            try:
                engine.run_to_level(2)
                columns = {
                    row[1] for row in engine.connection.execute("PRAGMA table_info(derivations)")
                }
                self.assertTrue({"input_a", "input_b", "output"} <= columns)
                self.assertNotIn("signature", columns)
            finally:
                engine.close()

    def test_checkpoint_resumes_at_next_level(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "scale.sqlite"
            first = open_engine(database, LIMITS)
            try:
                first.run_to_level(2)
            finally:
                first.close()
            second = open_engine(database, LIMITS)
            try:
                result = second.run_to_level(3)
                self.assertEqual(result["completed_level"], 3)
                self.assertEqual(second.level_rows()[-1]["total_states"], 372)
            finally:
                second.close()

    def test_no_structural_dimension_limit_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = open_engine(Path(directory) / "scale.sqlite", LIMITS)
            try:
                engine.run_to_level(3)
                self.assertEqual(engine.level_rows()[-1]["max_dim"], 4)
            finally:
                engine.close()

    def test_ranked_product_segments_preserve_exact_states_and_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = open_engine(
                Path(directory) / "scale.sqlite",
                LIMITS,
                symbolic_product_threshold=1,
            )
            try:
                result = engine.run_to_level(2)
                self.assertEqual(result["completed_level"], 2)
                self.assertEqual(engine.level_rows()[-1]["total_states"], 53)
                self.assertEqual(engine.level_rows()[-1]["derivations"], 43)
                ids = [row[0] for row in engine.connection.execute("SELECT id FROM states")]
                for start, count in engine.connection.execute(
                    "SELECT virtual_start,child_count FROM virtual_product_segments"
                ):
                    ids.extend(start - rank for rank in range(count))
                reconstructed = {
                    engine.reconstruct_signature(state_id) for state_id in ids
                }
                reference, _ = expand_auditable(levels=2, cap=1_000_000)
                self.assertEqual(reconstructed, set(reference))
            finally:
                engine.close()

    def test_partial_phase_checkpoint_resumes_without_semantic_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "scale.sqlite"
            first = open_engine(database, LIMITS, batch_size=3)
            try:
                first.run_to_level(2)
                checks = 0

                def stop_after_batches():
                    nonlocal checks
                    checks += 1
                    if checks > 4:
                        raise ComputeLimitReached("TEST_WATERMARK")

                first._check_limits = stop_after_batches
                stopped = first.run_to_level(3)
                self.assertEqual(stopped["completed_level"], 2)
                self.assertEqual(stopped["termination_class"], "COMPUTATIONAL_TERMINATION")
            finally:
                first.close()
            resumed = open_engine(database, LIMITS, batch_size=7)
            try:
                result = resumed.run_to_level(3)
                self.assertEqual(result["completed_level"], 3)
                reference, _ = expand_auditable(levels=3, cap=1_000_000)
                reconstructed = {
                    resumed.reconstruct_signature(row[0])
                    for row in resumed.connection.execute("SELECT id FROM states")
                }
                self.assertEqual(reconstructed, set(reference))
            finally:
                resumed.close()


if __name__ == "__main__":
    unittest.main()
