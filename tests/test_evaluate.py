import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import evaluate
from autoproteus.agent import Agent
from autoproteus.config import DEFAULTS, Settings
from autoproteus.providers import tool_definitions
from evaluate import check, harness_changes, harness_files


def temporary_directory():
    root = Path(__file__).resolve().parents[1] / '.data/test-tmp'
    root.mkdir(parents=True, exist_ok=True)
    directory = tempfile.TemporaryDirectory(dir=root)
    if not Path(directory.name).resolve().is_relative_to(root.resolve()):
        raise RuntimeError('Unexpected temporary directory')
    return directory


class EvaluationTests(unittest.TestCase):
    def test_self_improvement_disables_commands_without_saving_preference(self):
        task = (Path(evaluate.__file__).parent / 'evaluations/harness-feature.json').read_bytes()
        captured = {}
        class CommandClient:
            calls = 0
            def complete(self, messages, cancel):
                self.calls += 1
                decision = {'action': {'tool': 'run_command', 'arguments': {'command': 'echo should-not-run'}}} if self.calls == 1 else {'status': 'completed'}
                return {'content': json.dumps(decision)}
        class EvaluationAgent(Agent):
            def __init__(self, root, store, settings):
                captured['tools'] = [tool['function']['name'] for tool in tool_definitions(settings.values['terminal'])]
                captured['store'] = store
                super().__init__(root, store, settings, lambda _: CommandClient())
        with temporary_directory() as directory:
            root = Path(directory)
            (root / 'evaluations').mkdir()
            (root / 'evaluations/tasks.json').write_text('[]', encoding='utf-8')
            (root / 'evaluations/harness-feature.json').write_bytes(task)
            settings = Settings(root / '.data')
            settings.update({'provider': 'ollama', 'model': 'offline-test', 'configured': True, 'terminal': True})
            saved = settings.path.read_bytes()
            with patch.object(evaluate, '__file__', str(root / 'evaluate.py')), patch.object(evaluate, 'Agent', EvaluationAgent), \
                 patch('sys.argv', ['evaluate.py', '--live', '--self-improve']), patch('sys.stdout', new_callable=io.StringIO), \
                 patch('autoproteus.tools.subprocess.Popen') as process:
                self.assertEqual(evaluate.main(), 1)
                process.assert_not_called()
            self.assertNotIn('run_command', captured['tools'])
            self.assertEqual(settings.path.read_bytes(), saved)
            self.assertTrue(Settings(root / '.data').values['terminal'])
            session = next(iter(captured['store'].sessions.values()))
            journal = [json.loads(line) for line in (captured['store'].directory(session['id']) / 'events.jsonl').read_text().splitlines()]
            result = next(event['data'] for event in journal if event['type'] == 'action_result')
            self.assertFalse(result['ok'])
            self.assertIn('Terminal access is disabled', result['result']['error'])

    def test_harness_changes_include_entry_point_and_web_features(self):
        with temporary_directory() as directory:
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
        with temporary_directory() as directory:
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
        with temporary_directory() as directory:
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
        with temporary_directory() as directory:
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
