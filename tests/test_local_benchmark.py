"""Acceptance must distinguish disposable text fixtures from protected code."""
import base64
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_benchmark', ROOT / 'evaluations/local-model-benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def pack(values):
    return [{'path': name, 'data': base64.b64encode(value.encode()).decode()} for name, value in values.items()]


class BenchmarkAcceptanceTests(unittest.TestCase):
    def review(self, change_test=False):
        original = {'autoproteus/tools.py': 'original runtime', 'autoproteus/agent.py': 'protected loop',
                    'tests/test_seed.py': 'protected regression', 'sample.txt': 'old disposable fixture'}
        edited = {**original, 'autoproteus/tools.py': 'new runtime', 'sample.txt': 'new disposable fixture',
                  'tests/test_feature.py': 'def test_feature(): pass'}
        if change_test:
            edited['tests/test_seed.py'] = 'altered regression'
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=parent) as directory, \
                patch.object(benchmark, 'candidate_source', return_value=pack(edited)), \
                patch.object(benchmark, 'freeze_source'), \
                patch.object(benchmark, 'upgrade_review', return_value={}), \
                patch.object(benchmark, 'run_regressions', return_value={'passed': True}), \
                patch.object(benchmark, 'verify_feature', return_value={'passed': True}), \
                patch.object(benchmark, 'verify_public', return_value={'passed': True}):
            return benchmark.assess(Mock(), pack(original),
                                    {'session': 'fixture', 'status': 'completed', 'timed_out': False},
                                    'file_summary', Path(directory))

    def test_reused_text_fixture_can_change_when_all_independent_checks_pass(self):
        self.assertTrue(self.review()['accepted'])

    def test_changing_protected_tests_is_still_rejected(self):
        result = self.review(change_test=True)
        self.assertFalse(result['accepted'])
        self.assertFalse(result['protected_unchanged'])


if __name__ == '__main__':
    unittest.main()
