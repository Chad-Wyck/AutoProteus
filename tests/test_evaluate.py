import base64
import json
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from controller.config import Settings
from controller.errors import Cancelled
from controller.evaluation import EvaluationService, artifact_check, freeze_source, source_changes, source_identity, upgrade_review
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store
from test_seed import temporary_directory
from evaluate import check, harness_changes, harness_files

ROOT = Path(__file__).resolve().parents[1]


def source(path, data):
    return {'path': path, 'data': base64.b64encode(data).decode()}


class EvaluationTests(unittest.TestCase):
    def test_upgrade_review_records_evidence_without_importing_code_or_requiring_a_report(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Add a tool.', 'demo', 'fixture')
            store.feed(session, 'assistant', 'Added the capability and checked its Unicode boundary.')
            store.event(session, 'action_result', {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 harness/seed.py check'}},
                                                'result': {'exit_code': 0, 'output': 'fixture result'}, 'ok': True})
            session['status'] = 'completed'
            starter = [source('autoproteus/tools.py', b'original')]
            candidate = [source('autoproteus/tools.py', b'raise RuntimeError("never import")'),
                         source('tests/test_added.py', b'def test_added(): pass')]
            review = upgrade_review(store, session, starter, candidate)
            self.assertEqual(set(review['files']), {'autoproteus/tools.py', 'tests/test_added.py'})
            self.assertNotEqual(review['starter_sha256'], review['candidate_sha256'])
            self.assertEqual(review['commands'][0]['result']['exit_code'], 0)
            self.assertIn('Unicode', review['model_explanation'])
            self.assertIn('independent checks', review['verification'])

    def test_exact_checks_preserve_bytes_and_do_not_accept_claimed_completion(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('task', 'demo', 'test')
            artifacts = Artifacts(store, session)
            artifacts.put('result.txt', base64.b64encode(b'expected\r\n').decode())
            artifacts.checkpoint(['result.txt'])
            session['status'] = 'completed'
            self.assertFalse(artifact_check(artifacts, {'path':'result.txt', 'equals':'expected\n'}))
            self.assertFalse(artifact_check(artifacts, {'path':'missing.txt'}))
            self.assertTrue(artifact_check(artifacts, {'path':'missing.txt', 'absent':True}))
            with self.assertRaises(ValueError):
                artifact_check(artifacts, {'path':'../../controller/server.py'})

    def test_source_identity_and_diff_detect_additions_deletions_and_byte_changes(self):
        old = [source('seed.py', b'a=1\r\n'), source('removed.py', b'old')]
        new = [source('seed.py', b'a=1\n'), source('added.py', b'new')]
        self.assertEqual(source_identity(old), source_identity(list(reversed(old))))
        self.assertNotEqual(source_identity(old), source_identity(new))
        self.assertEqual([(c['path'], c['kind']) for c in source_changes(old, new)],
                         [('added.py','added'), ('removed.py','deleted'), ('seed.py','changed')])

    def test_source_is_frozen_without_importing_candidate_code(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            frozen = freeze_source(store, [source('seed.py', b'raise RuntimeError("never import")')], 'snapshot')
            self.assertEqual(Artifacts(store, frozen).read('harness/seed.py'), b'raise RuntimeError("never import")')
            self.assertFalse((Path(frozen['workspace']) / 'harness/seed.py').exists())

    def test_comparison_uses_frozen_sources_and_settings_and_requires_independent_review(self):
        with temporary_directory() as directory:
            directory = Path(directory)
            settings = Settings(directory)
            settings.update({'provider':'hosted', 'model':'offline-test', 'configured':True})
            saved = settings.path.read_bytes()
            store = Store(directory / 'sessions')
            candidate = freeze_source(store, seed_files(ROOT), 'candidate')
            task_agent = IsolatedAgent(ROOT, store, settings)
            service = EvaluationService(ROOT, directory / 'evaluations', settings, task_agent)
            visited = []
            def run(agent, eval_store, config, task, frozen, **kwargs):
                visited.append((config['model'], Artifacts(eval_store, frozen).read('harness/seed.py')))
                return {'task':task['name'], 'session':'f'*32, 'status':'completed', 'passed':True,
                        'checks':[], 'steps':1, 'seconds':1, 'format_repairs':0, 'action_errors':0, 'detail':''}
            with patch.object(task_agent.appliance, 'verify'), patch('controller.evaluation.run_task', side_effect=run), \
                    patch('controller.evaluation.run_regressions', return_value={'passed':True, 'tests':23}):
                report = service.start(candidate, repeats=2)
                settings.values['model'] = 'different-model'
                # Forty persisted mock runs can exceed ten seconds on a mounted filesystem.
                service.thread.join(timeout=30)
            final = service.load(report['id'])
            self.assertEqual(final['status'], 'completed')
            self.assertEqual(len(visited), 64)
            self.assertTrue(all(model == 'offline-test' for model, _ in visited))
            self.assertEqual(final['starter_sha256'], final['edited_sha256'])
            self.assertEqual(final['summary']['edited']['passed'], 32)
            self.assertIn('independent review', final['scope'])
            self.assertEqual(settings.path.read_bytes(), saved)
            self.assertNotIn('base_url', final['configuration'])
            for bad in ('../settings', 'A'*32, 'x'*32):
                with self.assertRaises(ValueError): service.load(bad)

    def test_regression_failure_rejects_candidate_without_model_tasks(self):
        with temporary_directory() as directory:
            directory = Path(directory)
            settings = Settings(directory)
            settings.values.update(provider='hosted', model='offline', configured=True)
            store = Store(directory / 'sessions')
            candidate = freeze_source(store, seed_files(ROOT), 'candidate')
            task_agent = IsolatedAgent(ROOT, store, settings)
            service = EvaluationService(ROOT, directory / 'evaluations', settings, task_agent)
            with patch.object(task_agent.appliance, 'verify'), \
                    patch('controller.evaluation.run_regressions', side_effect=[
                        {'passed':True, 'tests':23}, {'passed':False, 'tests':0}]), \
                    patch('controller.evaluation.run_task') as task:
                report = service.start(candidate, repeats=1)
                service.thread.join(timeout=10)
                task.assert_not_called()
            final = service.load(report['id'])
            self.assertEqual(final['status'], 'rejected')
            self.assertEqual(final['results'], [])
            self.assertFalse(final['regressions']['edited']['passed'])

    def test_cancellation_saves_incomplete_report_and_ends_evaluation(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            settings.values.update(provider='hosted', model='offline', configured=True)
            store = Store(Path(directory) / 'sessions')
            candidate = freeze_source(store, seed_files(ROOT), 'candidate')
            task_agent = IsolatedAgent(ROOT, store, settings)
            service = EvaluationService(ROOT, Path(directory) / 'evaluations', settings, task_agent)
            entered = threading.Event()
            def run(*args, cancel, **kwargs):
                entered.set(); cancel.wait(timeout=5); raise Cancelled()
            with patch.object(task_agent.appliance, 'verify'), patch('controller.evaluation.run_task', side_effect=run), \
                    patch('controller.evaluation.run_regressions', return_value={'passed':True, 'tests':23}):
                service.start(candidate, repeats=1)
                self.assertTrue(entered.wait(timeout=2))
                service.stop(); service.thread.join(timeout=5)
            self.assertFalse(service.busy)
            self.assertEqual(service.public()['status'], 'cancelled')
            self.assertEqual(service.public()['results'], [])

    def test_task_and_demo_conflicts_prevent_comparison(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            store = Store(Path(directory) / 'sessions')
            task_agent = IsolatedAgent(ROOT, store, settings)
            service = EvaluationService(ROOT, Path(directory) / 'evaluations', settings, task_agent)
            with self.assertRaisesRegex(ValueError, 'real model'):
                service.start(store.create('task', 'demo', 'test'))
            worker = Mock(); worker.is_alive.return_value = True
            task_agent.workers['active'] = threading.Event(), worker
            with self.assertRaisesRegex(ValueError, 'current task'):
                service.start(store.create('task', 'demo', 'test'))

    def test_fingerprints_detect_added_and_deleted_guest_source(self):
        with temporary_directory() as directory:
            workspace = Path(directory)
            harness = workspace / 'harness'
            (harness / 'autoproteus').mkdir(parents=True)
            path = harness / 'autoproteus/feature.py'
            path.write_bytes(b'old = True\n')
            baseline = harness_files(harness)
            path.unlink()
            (harness / 'seed.py').write_bytes(b'new = True\n')
            self.assertEqual(harness_changes(workspace, baseline), ['autoproteus/feature.py','seed.py'])
            self.assertFalse(check(workspace, {'path':'../outside.py'}))

    def test_host_interfaces_and_transport_are_absent_from_the_editable_seed(self):
        names = {item['path'] for item in seed_files(ROOT)}
        for excluded in ('autoproteus/server.py', 'autoproteus/runtime.py', 'autoproteus/config.py', 'web/app.js', 'evaluations/tasks.json'):
            self.assertNotIn(excluded, names)
        self.assertIn('README.md', names)
        self.assertIn('tests/test_seed.py', names)


if __name__ == '__main__':
    unittest.main()
