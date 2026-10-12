import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import evaluate
from autoproteus.config import DEFAULTS
from evaluate import check, harness_changes, harness_files


class EvaluationTests(unittest.TestCase):
    def test_harness_changes_include_entry_point_and_web_features(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            harness = workspace / 'harness'
            (harness / 'web').mkdir(parents=True)
            (harness / 'app.py').write_text('old = True\n', encoding='utf-8')
            baseline = harness_files(harness)
            (harness / 'app.py').write_text('new = True\n', encoding='utf-8')
            (harness / 'web' / 'feature.js').write_text('const feature = true;\n', encoding='utf-8')
            self.assertEqual(harness_changes(workspace, baseline), ['app.py', 'web/feature.js'])

    def test_artifact_ready_submission_requires_review_instead_of_functional_pass(self):
        task = (Path(evaluate.__file__).parent / 'evaluations' / 'harness-feature.json').read_text(encoding='utf-8')
        class SubmissionAgent:
            def __init__(self, *args): pass
            def start(self, session):
                workspace = Path(session['workspace'])
                for name, content in [('harness/autoproteus/feature.py', 'candidate = True\n'),
                                      ('harness/tests/test_feature.py', 'pass\n'),
                                      ('feature.md', 'A candidate needing independent verification.\n')]:
                    path = workspace / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding='utf-8')
                session.update(status='completed', steps=1)
            def close(self): pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evaluations').mkdir()
            (root / 'evaluations/tasks.json').write_text('[]', encoding='utf-8')
            (root / 'evaluations/harness-feature.json').write_text(task, encoding='utf-8')
            settings = SimpleNamespace(values={**DEFAULTS, 'provider': 'ollama', 'model': 'test', 'configured': True})
            with patch.object(evaluate, '__file__', str(root / 'evaluate.py')), \
                 patch.object(evaluate, 'Settings', return_value=settings), \
                 patch.object(evaluate, 'Agent', SubmissionAgent), \
                 patch('sys.argv', ['evaluate.py', '--live', '--self-improve']), patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(evaluate.main(), 2)
            result = json.loads(next((root / '.data/evaluations').glob('report-*.json')).read_text())['results'][0]
            self.assertTrue(result['artifact_passed'])
            self.assertTrue(result['review_required'])
            self.assertIsNone(result['passed'])

    def test_harness_changes_use_content_and_include_added_and_deleted_source(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            harness = workspace / 'harness'
            (harness / 'autoproteus').mkdir(parents=True)
            (harness / 'tests').mkdir()
            source = harness / 'autoproteus' / 'feature.py'
            source.write_text('old = True\n', encoding='utf-8')
            baseline = harness_files(harness)
            self.assertEqual(harness_changes(workspace, baseline), [])
            source.write_text('new = True\n', encoding='utf-8')
            (harness / 'tests' / 'test_feature.py').write_text('pass\n', encoding='utf-8')
            self.assertEqual(harness_changes(workspace, baseline),
                             ['autoproteus/feature.py', 'tests/test_feature.py'])
            source.unlink()
            self.assertEqual(harness_changes(workspace, baseline),
                             ['autoproteus/feature.py', 'tests/test_feature.py'])

    def test_independent_checks_and_fingerprints_reject_paths_outside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / 'workspace'
            (workspace / 'autoproteus').mkdir(parents=True)
            outside = root / 'outside.py'
            outside.write_text('secret = True\n', encoding='utf-8')
            self.assertFalse(check(workspace, {'path': '../outside.py'}))
            try:
                (workspace / 'autoproteus' / 'escape.py').symlink_to(outside)
            except OSError:
                self.skipTest('Symlink creation unavailable')
            self.assertEqual(harness_files(workspace), {})


if __name__ == '__main__':
    unittest.main()
