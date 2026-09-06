import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('research_loop', ROOT / 'scripts/structural-research-loop.py')
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)


class ResearchLoopTests(unittest.TestCase):
    def test_resume_preserves_completed_work_and_matches_fresh_run(self):
        with tempfile.TemporaryDirectory() as directory:
            resumed, fresh = Path(directory)/'resumed.json', Path(directory)/'fresh.json'
            args = dict(schedule=[(1, 1), (2, 1)], seconds=20)
            partial = loop.run(resumed, stop_after=1, **args)
            self.assertEqual(partial['completion'], 'CHECKPOINTED')
            self.assertEqual(len(partial['iterations']), 1)
            done = loop.run(resumed, **args)
            control = loop.run(fresh, **args)
            self.assertEqual(done, control)
            self.assertEqual(done['iterations'][0], partial['iterations'][0])
            self.assertEqual(loop.run(resumed, **args), done)
            self.assertEqual(done['external_evaluation']['status'], 'NOT_RUN')
            self.assertEqual(done['nature_coverage'], 'NOT_DEFINED')

    def test_changed_protocol_or_corrupted_checkpoint_cannot_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'run.json'
            loop.run(path, schedule=[(1, 1), (2, 1)], stop_after=1)
            with self.assertRaises(ValueError): loop.run(path, schedule=[(1, 1), (3, 1)])
            data = json.loads(path.read_text())
            data['iterations'][0]['fingerprint']['nodes'] = 'corrupt'
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): loop.run(path, schedule=[(1, 1), (2, 1)])

    def test_truncated_run_does_not_become_plateau_or_regression(self):
        self.assertEqual(loop.decision({'termination': 'BOUNDED_SATURATION'},
                                      {'termination': 'NODE_BUDGET'}, 0, 50), 'COMPUTE_LIMIT_REACHED')
        self.assertEqual(loop.decision({'termination': 'BOUNDED_SATURATION'},
                                      {'termination': 'BOUNDED_SATURATION'}, 0, 0), 'NO_STATE_GROWTH_IN_THIS_SCOPE')
        with self.assertRaises(ValueError):
            loop.decision({'termination': 'BOUNDED_SATURATION'}, {'termination': 'BOUNDED_SATURATION'}, 20, 1)

    def test_node_budget_stops_schedule_with_valid_partial_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            result = loop.run(Path(directory)/'run.json', schedule=[(2, 2), (3, 3)], max_nodes=12)
            self.assertEqual(result['completion'], 'COMPUTE_LIMIT_REACHED')
            self.assertEqual(len(result['iterations']), 1)
            self.assertTrue(result['iterations'][0]['result']['validation']['clean'])

    def test_non_nested_schedule_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                loop.run(Path(directory)/'run.json', schedule=[(3, 3), (4, 2)])


if __name__ == '__main__':
    unittest.main()
