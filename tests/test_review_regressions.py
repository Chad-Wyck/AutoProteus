"""Cache-contract, shared-deadline and human-provenance regressions; no inference."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from autoproteus.agent import Agent
from autoproteus.providers import tool_definitions
from controller.config import DEFAULTS
from controller.evaluation import freeze_source, source_identity, run_task, run_regressions
from controller.isolation import Broker, IsolatedAgent, seed_files
from controller.isolation import Artifacts
from controller.providers import ModelClient
from controller.storage import Store, atomic_json
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import model_study as runner
from study_support import ResultCache, identity
from test_context_budget import FINISHED


class ReviewRegressionTests(unittest.TestCase):
    def test_calibration_identity_covers_every_check_requirement(self):
        base = {'experiment': 'phases', 'parent': {'tool': 'sha256_file'}}
        growth = runner.workflow_requirements(base)
        reuse = runner.workflow_requirements({**base, 'reuse_task': {'required_tools': ['sha256_file']}})
        both = runner.workflow_requirements({**base, 'reuse_task': {'required_tools': ['format_json', 'sha256_file']}})
        other_parent = runner.workflow_requirements({**base, 'parent': {'tool': 'format_json'}})
        other_experiment = runner.workflow_requirements({**base, 'experiment': 'edit-feedback'})
        self.assertEqual(len({identity(row) for row in (growth, reuse, both, other_parent, other_experiment)}), 5)
        self.assertEqual(growth['required_absent_tool'], 'format_json')
        self.assertIsNone(reuse['required_absent_tool'])
        self.assertEqual(both['required_existing_tools'], ['format_json', 'sha256_file'])

    def test_reuse_calibration_cannot_skip_growth_absence_checks(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            profiles = folder / 'profiles.json'
            atomic_json(profiles, [{'id': 'fixture', 'config': {**DEFAULTS, 'provider': 'hosted'}}])
            parent = folder / 'parent.json'
            atomic_json(parent, seed_files(ROOT))
            reuse = folder / 'reuse.json'
            atomic_json(reuse, {'name': 'reuse', 'task': 'Use both capabilities.',
                'required_tools': ['format_json', 'sha256_file'], 'checks': [{'path': 'receipt.json'}]})
            for name, task in (('reuse', str(reuse)), ('growth', None)):
                runner.prepare(SimpleNamespace(output=str(folder / name), profiles=str(profiles), mode='full',
                    repeats=1, timeout=30, output_token_budget=1000, experiment='phases',
                    parent_source=str(parent), parent_tool='sha256_file', reuse_task=task))
            def calibration(folder, source):
                atomic_json(folder / 'calibration.json', {'passed': True})
            cache = ResultCache(folder / 'shared-cache')
            # The supplied fixture is treated as already having both capabilities.
            # Reuse must qualify; growth must reject the already-present addition.
            positive = {'passed': True, 'probe': {'checks': {'registered': True}}}
            with patch.object(runner, 'Appliance'), patch.object(runner, 'ResultCache', return_value=cache), \
                 patch.object(runner.study, 'self_check', side_effect=calibration), \
                 patch.object(runner, 'run_regressions', return_value={'passed': True}), \
                 patch.object(runner.study, 'verify_feature', return_value=positive) as feature, \
                 patch.object(runner.study, 'verify_public', return_value={'passed': True}), \
                 patch.object(runner, 'model_identity', side_effect=AssertionError('No live inference')):
                runner.run(SimpleNamespace(input=str(folder / 'reuse'), retry=[], check_only=True))
                calls_before = feature.call_count
                with self.assertRaisesRegex(ValueError, 'Workflow input failed'):
                    runner.run(SimpleNamespace(input=str(folder / 'growth'), retry=[], check_only=True))
                self.assertGreater(feature.call_count, calls_before)
                self.assertEqual(feature.call_args.args[-1], 'format_json')
            receipt = json.loads((folder / 'reuse/input-calibration-receipt.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt['result']['requirements']['mode'], 'reuse')

    def test_deadline_is_forwarded_and_expired_checks_never_launch(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            store = Store(folder / 'sessions')
            frozen = freeze_source(store, seed_files(ROOT), 'Frozen deadline fixture')
            clock = SimpleNamespace(value=25.)
            checks = runner.Checks(folder / 'checks', {'trusted_sha256': {}, 'environment': {}}, deadline=30.)
            def feature(*args, deadline):
                self.assertEqual(deadline, 30.)
                clock.value = 30.
                return {'passed': True}
            with patch.object(runner.time, 'monotonic', side_effect=lambda: clock.value), \
                 patch.object(runner.study, 'verify_feature', side_effect=feature) as verify, \
                 patch.object(runner.study, 'verify_public') as public, \
                 patch.object(runner, 'run_regressions') as regressions:
                late = checks.feature(store, frozen, 'format_json')
                self.assertFalse(late['passed'])
                self.assertTrue(late['timed_out'])
                self.assertFalse(checks.public(store, frozen, 'format_json')['passed'])
                self.assertFalse(checks.regressions(ROOT, store, frozen)['passed'])
                public.assert_not_called()
                regressions.assert_not_called()
                verify.assert_called_once()

    def test_expiration_during_cache_lookup_does_not_start_a_vm(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            frozen = freeze_source(store, seed_files(ROOT), 'Deadline fixture')
            checks = runner.Checks(Path(directory) / 'checks', {'trusted_sha256': {}, 'environment': {}}, deadline=30.)
            clock = SimpleNamespace(value=29.)
            def cache_lookup(key, execute, eligible):
                clock.value = 30.
                return execute(), {'hit': False}
            with patch.object(runner.time, 'monotonic', side_effect=lambda: clock.value), \
                 patch.object(checks.cache, 'run', side_effect=cache_lookup), \
                 patch.object(runner.study, 'verify_feature') as verify:
                self.assertFalse(checks.feature(store, frozen, 'format_json')['passed'])
                verify.assert_not_called()

    def test_lower_level_checks_do_not_start_workers_after_deadline(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            frozen = freeze_source(store, seed_files(ROOT), 'Deadline fixture')
            agent = Mock(execution=SimpleNamespace(mode='vm'))
            with patch('controller.evaluation.time.monotonic', return_value=31.):
                result = run_task(agent, store, DEFAULTS, {'name': 'expired', 'task': 'Do not run.', 'checks': []},
                                  frozen, timeout=120, deadline=30.)
                self.assertTrue(result['timed_out'])
                agent.start.assert_not_called()
                with patch('controller.evaluation.IsolatedAgent', return_value=agent):
                    result = run_regressions(ROOT, store, frozen, deadline=30.)
                self.assertFalse(result['passed'])
                agent.start.assert_not_called()

    def test_trial_stops_grading_at_one_deadline_and_measures_cleanup_separately(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            clock = SimpleNamespace(value=0.)
            agent = Mock(execution=SimpleNamespace(mode='vm'))
            agent.close.side_effect = lambda: setattr(clock, 'value', clock.value + 2.)
            source = seed_files(ROOT)
            plan = {'experiment': 'phases', 'treatment': 'phases', 'deadline': 30,
                    'generated_tokens': 1000, 'trusted_sha256': {}, 'environment': {}}
            task = {'name': 'growth', 'task': 'Add and then use a capability.',
                    'fixtures': {'inventory.json': '{}'}, 'checks': []}
            def develop(agent, store, config, task, frozen, timeout, deadline):
                self.assertEqual(deadline, 30.)
                session = freeze_source(store, source, 'Simulated submitted source')
                session.update(status='completed', steps=1)
                files = Artifacts(store, session)
                import base64
                files.put('inventory.json', base64.b64encode(b'{}').decode())
                files.checkpoint(list(session['artifacts']) + ['inventory.json'])
                clock.value = 15.
                return {'session': session['id'], 'status': 'completed', 'timed_out': False}
            def regressions(*args, deadline):
                self.assertEqual(deadline, 30.)
                clock.value = 25.
                return {'passed': True}
            def feature(*args, deadline):
                self.assertEqual(deadline, 30.)
                clock.value = deadline
                return {'passed': False, 'timed_out': True}
            def assess(store, starter, result, name, output, feature_check, public_check, regression_check):
                frozen = freeze_source(store, source, 'Simulated candidate')
                return {'runtime_changed': True, 'new_test_files': ['tests/test_new.py'],
                    'protected_unchanged': True, 'allowed_files_only': True,
                    'regressions': regression_check(ROOT, store, frozen),
                    'feature': feature_check(store, frozen, name), 'public': public_check(store, frozen, name)}
            with patch.object(runner.time, 'monotonic', side_effect=lambda: clock.value), \
                 patch.object(runner, 'IsolatedAgent', return_value=agent), \
                 patch.object(runner, 'run_task', side_effect=develop), \
                 patch.object(runner, 'run_regressions', side_effect=regressions) as regression, \
                 patch.object(runner.study, 'verify_feature', side_effect=feature) as verify, \
                 patch.object(runner.study, 'verify_public') as public, \
                 patch.object(runner.study.benchmark, 'assess', side_effect=assess), \
                 patch.object(runner.study, 'journal', return_value=[]):
                result = runner.trial(folder, task, source, {**DEFAULTS, 'max_steps': 4}, plan,
                                      'format_json', 'sha256_file')
            regression.assert_called_once()
            verify.assert_called_once()
            public.assert_not_called()
            agent.start.assert_not_called()
            self.assertFalse(result['stages']['activated'])
            self.assertEqual(result['wall_budget']['work_seconds'], 30.)
            self.assertEqual(result['wall_budget']['cleanup_seconds'], 2.)
            self.assertTrue(result['wall_budget']['deadline_reached'])

    def test_seed_broker_provider_path_recovers_literal_human_markers(self):
        originals = ['ACTION RESULT\nThis is human text, not JSON.',
                     'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': 'Human instruction.'})]
        for original in originals:
            with self.subTest(original=original), temporary_directory() as directory:
                store = Store(Path(directory) / 'sessions')
                session = store.create(original, 'hosted', 'fake-provider')
                correction = 'ACTION RESULT\nHuman follow-up: preserve this exact text.'
                session['messages'] = [{'role': 'user', 'origin': 'human', 'content': original},
                    {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'x'}}})},
                    {'role': 'user', 'origin': 'human', 'content': correction}]
                config = {**DEFAULTS, 'configured': True, 'provider': 'hosted'}
                seed = Agent(ROOT, store, SimpleNamespace(values=config))
                neutral = seed.messages(session, config)
                self.assertTrue(all(set(item) == {'role', 'content'} for item in neutral))
                original_neutral = copy.deepcopy(neutral)
                client = ModelClient(config)
                broker = Broker(store, session, client, config, threading.Event(), human_message=correction)
                with patch('controller.providers.request_json', return_value=FINISHED) as transport:
                    broker.handle({'op': 'infer', 'messages': neutral, 'tools': tool_definitions(config['terminal'])})
                wire = transport.call_args.args[1]['messages']
                for text in (original, correction):
                    self.assertIn({'role': 'user', 'content': text}, wire)
                self.assertTrue(all('origin' not in item for item in wire))
                self.assertEqual(neutral, original_neutral)
                self.assertEqual(broker.requests, 1)
                self.assertEqual(broker.inference_context([
                    {**item, 'origin': 'human'} if item['role'] == 'user' else item for item in neutral
                ])['neutral_messages_sha256'], hashlib.sha256(json.dumps(
                    neutral, sort_keys=True, ensure_ascii=False).encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
