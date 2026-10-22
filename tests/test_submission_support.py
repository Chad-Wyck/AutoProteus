"""Public feedback, source freshness, and transport receipt regression controls."""
import base64
import copy
import json
from pathlib import Path
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from controller.capabilities import capability_progress, declared_tools
from controller.compatibility import qualify_profile, check_protocol
from controller.config import DEFAULTS, Settings
from controller.evaluation import source_identity
from controller.isolation import seed_files
from controller.providers import ProviderError
from controller.submissions import repair_ticket, ticket_message, submission_policy
from edit_context import build_packet, stale_paths, task_support
from test_providers import FakeModelServer
from test_seed import temporary_directory
from controller.isolation import Artifacts, Broker
from controller.evaluation import candidate_source, freeze_source
from controller.storage import atomic_json
import model_study as runner


def packed(path, text):
    return {'path': path, 'data': base64.b64encode(text.encode()).decode()}


class SubmissionSupportTests(unittest.TestCase):
    def setUp(self):
        self.starter = [packed('seed.py', 'pass\n'), packed('autoproteus/agent.py', 'pass\n'),
                        packed('autoproteus/tools.py', 'x = 1\n'), packed('tests/test_seed.py', 'def test_old(): pass\n')]

    def test_scope_feedback_does_not_silently_repair_or_approve_a_candidate(self):
        candidate = copy.deepcopy(self.starter)
        candidate[2] = packed('autoproteus/tools.py', 'x = 2\n')
        candidate.append(packed('arguments.json', '{}'))
        original = copy.deepcopy(candidate)
        ticket = repair_ticket(self.starter, candidate)
        self.assertEqual({item['kind'] for item in ticket['issues']}, {'tests', 'scope'})
        self.assertEqual(ticket['policy']['unexpected_files'], ['arguments.json'])
        self.assertEqual(ticket['source_sha256'], source_identity(candidate))
        self.assertEqual(candidate, original)
        self.assertIn('not independent approval', ticket_message(ticket))
        candidate.pop()
        candidate.append(packed('tests/test_feature.py', 'def test_feature(): pass\n'))
        ready = repair_ticket(self.starter, candidate)
        self.assertTrue(ready['ready_for_independent_checks'])
        self.assertNotIn('accepted', ready)

    def test_existing_test_edits_and_invalid_syntax_are_reported(self):
        candidate = copy.deepcopy(self.starter)
        candidate[2] = packed('autoproteus/tools.py', 'def broken(:\n')
        candidate[3] = packed('tests/test_seed.py', 'def test_other(): pass\n')
        kinds = {item['kind'] for item in repair_ticket(self.starter, candidate)['issues']}
        self.assertTrue({'syntax', 'tests', 'preservation'}.issubset(kinds))

    def test_latest_development_pass_supersedes_failure_and_prose_is_ignored(self):
        candidate = self.starter + [packed('tests/test_new.py', 'def test_new(): pass\n')]
        failure = {'type': 'action_result', 'data': {'ok': True,
            'action': {'tool': 'run_command', 'arguments': {'command': 'python3 harness/seed.py check'}},
            'result': {'exit_code': 1, 'output': 'Traceback: an invented Workspace method was called'}}}
        ticket = repair_ticket(self.starter, candidate, [{'type': 'assistant', 'data': 'All passed!'}, failure])
        self.assertIn('Traceback', ticket['development_failure']['output'])
        self.assertIn('may differ', ticket['development_failure']['scope'])
        passed = copy.deepcopy(failure); passed['data']['result'] = {'exit_code': 0, 'output': 'OK'}
        self.assertIsNone(repair_ticket(self.starter, candidate, [failure, passed])['development_failure'])

    def test_large_ticket_has_a_bounded_model_message_and_no_hidden_results(self):
        source = self.starter + [packed('scratch/' + 'x' * 230 + str(i) + '.json', '{}') for i in range(100)]
        text = ticket_message(repair_ticket(self.starter, source))
        self.assertLessEqual(len(text.encode()), 10400)
        self.assertNotIn('heldout', text)

    def test_focused_pass_cannot_clear_full_suite_failure_but_a_full_pass_can(self):
        candidate = self.starter + [packed('tests/test_new.py', 'def test_new(): pass\n')]
        def check(command, exit_code):
            return {'type': 'action_result', 'data': {
                'action': {'tool': 'run_command', 'arguments': {'command': command}},
                'result': {'exit_code': exit_code, 'output': 'recorded development check'}}}
        failed = check('python3 harness/seed.py check', 1)
        for option in ('--test tests/test_new.py', '--test=tests/test_new.py', '"--test" tests/test_new.py'):
            focused = check('python3 harness/seed.py check ' + option, 0)
            ticket = repair_ticket(self.starter, candidate, [failed, focused])
            self.assertFalse(ticket['ready_for_independent_checks'])
            self.assertEqual(ticket['development_failure']['command'], 'python3 harness/seed.py check')
            self.assertIn('full', ticket['development_failure']['scope'])
        failed_focus = check('python3 harness/seed.py check --test tests/test_new.py', 1)
        ticket = repair_ticket(self.starter, candidate, [failed, failed_focus])
        self.assertIn('focused', ticket['development_failure']['scope'])
        passed = check('python3 harness/seed.py check', 0)
        self.assertIsNone(repair_ticket(self.starter, candidate, [failed, failed_focus, passed])['development_failure'])

    def test_packet_preserves_real_headers_unicode_offsets_and_freshness(self):
        text = '# 猫\r\nclass Workspace:\r\n    def execute(self, tool, args):\r\n        return tool\r\n    def read_text(self, path, missing_ok=False):\r\n        pass\r\n'
        source = [packed('autoproteus/tools.py', text), packed('autoproteus/providers.py', 'TOOL_SPECS = {}\r\n')]
        packet = build_packet(source)
        item = packet['sources'][0]['observations'][0]
        self.assertEqual(item['excerpt'], text[item['start_character']:item['start_character'] + item['characters']])
        self.assertEqual(packet['sources'][0]['observations'][1]['header'], 'def read_text(self, path, missing_ok=False):')
        self.assertEqual(stale_paths(packet, source), [])
        source[0] = packed('autoproteus/tools.py', text + '# changed\r\n')
        self.assertEqual(stale_paths(packet, source), ['autoproteus/tools.py'])

    def test_packet_is_bounded_with_real_invocation_example_and_no_import_execution(self):
        source = seed_files(ROOT)
        source.append(packed('unrelated.py', 'raise RuntimeError("must never run")'))
        packet = build_packet(source, limit=4000)
        self.assertLessEqual(len(json.dumps(packet, ensure_ascii=False).encode()), 4000)
        self.assertNotIn('unrelated.py', [item['path'] for item in packet['sources']])
        full = build_packet(source)
        test = next(item for item in full['sources'] if item['path'] == 'tests/test_seed.py')
        self.assertIn('.execute(', test['observations'][0]['excerpt'])
        self.assertIn('Workspace.path', str(full))

    def test_opt_in_support_does_not_claim_learning_or_modify_the_source(self):
        source = seed_files(ROOT); before = source_identity(source)
        lesson = task_support(source, 'Original instructions', 'verified-lesson')
        self.assertEqual(lesson['followed'], 'unmeasured')
        self.assertEqual(lesson['independently_useful'], 'unmeasured')
        self.assertIn('Hypothesis:', lesson['fixtures']['experience/verified-submission.md'])
        context = task_support(source, 'Original instructions', 'edit-context')
        self.assertFalse(stale_paths(context['packet'], source))
        self.assertEqual(source_identity(source), before)

    def test_capability_progress_is_source_bound_and_does_not_certify_tools(self):
        source = seed_files(ROOT)
        names = declared_tools(source)
        self.assertIn('read_file', names)
        active = {'source_sha256': source_identity(source), 'direct': ['read_file'], 'development': ['example']}
        status = {'state': 'passed', 'scope': 'Only listed tasks'}
        row = capability_progress(source, active, status)
        self.assertTrue(row['activated'])
        self.assertEqual(row['model_used'], ['read_file'])
        source.append(packed('README.md', 'changed'))
        stale = capability_progress(source, active, status)
        self.assertFalse(stale['activated'])
        self.assertEqual(stale['model_used'], [])
        self.assertIn('not independent proof', row['scope'])

    def test_guest_observation_metadata_cannot_grow_past_the_tool_catalog_limit(self):
        from controller.storage import Store
        with temporary_directory() as directory:
            store = Store(Path(directory))
            session = store.create('Observe calls', 'demo', 'fixture')
            session['active_seed'] = {'source_sha256': 'a' * 64, 'direct': [], 'development': []}
            broker = Broker(store, session, Mock(), dict(DEFAULTS), threading.Event())
            for name in ['x' * 10000, *('tool_' + str(index) for index in range(100))]:
                broker.handle({'op': 'event', 'type': 'action_result', 'data':
                    {'ok': True, 'action': {'tool': name, 'arguments': {}}, 'result': {}}})
            self.assertEqual(len(session['active_seed']['direct']), 64)
            self.assertTrue(all(len(name) <= 64 for name in session['active_seed']['direct']))


class ProfileQualificationTests(unittest.TestCase):
    def diagnostic_client(self, failures=None, wrong=False):
        client = Mock(config=dict(DEFAULTS))
        histories = []
        failures = dict(failures or {})
        def complete(messages, cancel, **kwargs):
            histories.append(copy.deepcopy(messages))
            failure = failures.get(len(histories))
            if isinstance(failure, Exception):
                raise failure
            if failure is not None:
                return failure
            last = next(item['content'] for item in reversed(messages)
                        if item['content'].startswith(('Test value: ', 'ACTION RESULT\n')))
            if last.startswith('Test value: '):
                decision = {'action': {'tool': 'diagnostic_echo', 'arguments': {'value': 'wrong' if wrong else last[12:]}}}
            else:
                result = json.loads(last.split('\n', 1)[1])
                if not result['ok']:
                    value = next(item['content'][12:] for item in reversed(messages) if item['content'].startswith('Test value: '))
                    decision = {'action': {'tool': 'diagnostic_echo', 'arguments': {'value': value}}}
                else:
                    decision = {'status': 'completed', 'message': result['result']['receipt']}
            return {'content': json.dumps(decision)}
        client.complete.side_effect = complete
        return client, histories

    def test_final_native_format_error_is_repaired_without_restarting_diagnostic(self):
        client, history = self.diagnostic_client({7: {'content': '{}', 'normalization_error': 'native response needs a tool call'}})
        with patch('controller.compatibility.ModelClient', return_value=client):
            result = check_protocol(DEFAULTS, rounds=3, recovery=True)
        self.assertEqual(result['requests'], 8)
        self.assertEqual(result['format_repairs'], 1)
        self.assertFalse(result['first_pass'])
        self.assertEqual(history[7][:-1], history[6])
        self.assertIn('No action was executed', history[7][-1]['content'])

    def test_repairs_reset_after_valid_decisions_and_share_fixed_request_deadline(self):
        config = {**DEFAULTS, 'request_timeout': 20}
        client, history = self.diagnostic_client({index: {'content': 'invalid JSON'} for index in (1, 2, 4, 5)})
        with patch('controller.compatibility.ModelClient', return_value=client), \
             patch('controller.compatibility.time.monotonic', side_effect=[0, 1, 2, 3, 4, 5, 55]):
            result = check_protocol(config)
        self.assertEqual(result['requests'], 6)
        self.assertEqual(result['format_repairs'], 4)
        self.assertEqual(client.config['request_timeout'], 5)
        client, history = self.diagnostic_client({1: {'content': 'invalid JSON'}})
        with patch('controller.compatibility.ModelClient', return_value=client), \
             patch('controller.compatibility.time.monotonic', side_effect=[0, 1, 61]), self.assertRaises(ProviderError):
            check_protocol(config)
        self.assertEqual(len(history), 1)

    def test_cutoff_and_protocol_errors_recover_without_disclosing_provider_body(self):
        failures = {1: ProviderError('private key secret', {'raw_content': 'secret'}, category='cutoff'),
                    2: ProviderError('private key secret', {'protocol_reason': 'tool_arguments'}, category='protocol')}
        client, history = self.diagnostic_client(failures)
        with patch('controller.compatibility.ModelClient', return_value=client):
            result = check_protocol(DEFAULTS)
        self.assertEqual(result['requests'], 4)
        self.assertEqual(result['format_repairs'], 2)
        self.assertNotIn('private key secret', json.dumps(history))
        self.assertIn('valid JSON arguments', json.dumps(history))

    def test_bad_format_exhausts_two_repairs_and_valid_wrong_actions_are_not_repaired(self):
        client, history = self.diagnostic_client({index: {'content': 'broken'} for index in range(1, 4)})
        with patch('controller.compatibility.ModelClient', return_value=client), self.assertRaises(ProviderError):
            check_protocol(DEFAULTS)
        self.assertEqual(len(history), 3)
        client, history = self.diagnostic_client(wrong=True)
        with patch('controller.compatibility.ModelClient', return_value=client), self.assertRaises(ProviderError):
            check_protocol(DEFAULTS)
        self.assertEqual(len(history), 1)

    def test_connection_failure_is_not_retried(self):
        client, history = self.diagnostic_client({1: ProviderError('offline', category='connection')})
        with patch('controller.compatibility.ModelClient', return_value=client), self.assertRaises(ProviderError) as error:
            check_protocol(DEFAULTS)
        self.assertEqual(error.exception.category, 'connection')
        self.assertEqual(len(history), 1)

    def test_both_transports_survive_recovery_and_growing_history(self):
        for protocol in ('native', 'json'):
            server = FakeModelServer(hosted=True, native=protocol == 'native', diagnostic=True)
            try:
                config = {**DEFAULTS, 'provider': 'hosted', 'base_url': server.url, 'protocol': protocol}
                result = qualify_profile(config)
                self.assertEqual(result['requests'], 7)
                self.assertTrue(result['first_pass'])
                self.assertEqual(result['format_repairs'], 0)
                self.assertTrue(result['rejected_call_recovery'])
                self.assertEqual(len(server.payloads), 7)
                self.assertGreater(len(server.payloads[-1]['messages']), len(server.payloads[1]['messages']))
                if protocol == 'native':
                    self.assertIn('read_file', [tool['function']['name'] for tool in server.payloads[0]['tools']])
                self.assertFalse(result['identity_complete'])
            finally:
                server.close()

    def test_partial_identity_and_profile_changes_cannot_reuse_a_receipt(self):
        identity = {'engine_version': 'engine1', 'digest': 'weights1', 'template_sha256': 'template1',
                    'parameters_sha256': 'params1', 'details': {'quantization_level': 'Q6'}}
        response = {'passed': True, 'requests': 7, 'rounds': 3, 'rejected_call_recovery': True}
        with patch('controller.compatibility.model_identity', return_value=identity), \
             patch('controller.compatibility.check_protocol', return_value=response) as check:
            first = qualify_profile(DEFAULTS)
            cached = qualify_profile(DEFAULTS, previous=first)
            self.assertTrue(cached['cached']); self.assertEqual(cached['requests_this_check'], 0)
            self.assertEqual(check.call_count, 1)
            qualify_profile({**DEFAULTS, 'temperature': 0.7}, previous=first)
            self.assertEqual(check.call_count, 2)
            with patch('controller.compatibility.model_identity', return_value={**identity, 'identity_available': False}):
                uncertain = qualify_profile(DEFAULTS, previous=first)
            self.assertFalse(uncertain['cached']); self.assertFalse(uncertain['identity_complete'])

    def test_identity_change_during_check_refuses_a_receipt(self):
        identity = {'engine_version': 'engine1', 'digest': 'weights1', 'template_sha256': 'template1',
                    'parameters_sha256': 'params1', 'details': {'quantization_level': 'Q6'}}
        with patch('controller.compatibility.model_identity', side_effect=[identity, {**identity, 'digest': 'changed'}]), \
             patch('controller.compatibility.check_protocol', return_value={'passed': True, 'requests': 7}), \
             self.assertRaises(ProviderError):
            qualify_profile(DEFAULTS)

    def test_sampling_changes_remove_a_saved_receipt(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            settings.record_compatibility({'passed': True})
            settings.update({'temperature': 0.7})
            self.assertNotIn('compatibility', settings.values)


class SubmissionTrialTests(unittest.TestCase):
    def test_public_repairs_precede_hidden_checks_and_share_the_original_allowances(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            source = seed_files(ROOT)
            agent = Mock(); agent.execution.mode = 'vm'
            plan = {'treatment': 'submission-feedback', 'experiment': 'submission-feedback',
                    'trusted_sha256': {}, 'environment': {}, 'deadline': 30, 'ordinary_deadline': 10,
                    'generated_tokens': 100, 'ordinary_generated_tokens': 100}
            context = {}
            def develop(agent, store, config, task, frozen, seconds, **kwargs):
                session = freeze_source(store, source, 'Candidate')
                files = Artifacts(store, session)
                original = next(item for item in source if item['path'] == 'autoproteus/tools.py')
                files.put('harness/autoproteus/tools.py', base64.b64encode(b'# Edited candidate\n' + base64.b64decode(original['data'])).decode())
                files.put('harness/arguments.json', base64.b64encode(b'{}').decode())
                files.checkpoint([*session['artifacts'], 'harness/arguments.json'])
                session.update(status='completed', steps=2)
                context.update(store=store, session=session)
                return {'session': session['id'], 'status': 'completed', 'timed_out': False}
            def repair(session, message, **kwargs):
                self.assertEqual(kwargs.keys(), {'deadline'})  # No activation of unverified edits.
                self.assertIn('arguments.json', message)
                self.assertNotIn('hidden', message.lower())
                self.assertEqual(agent.settings.values['max_steps'], 1)
                files = Artifacts(context['store'], session)
                paths = [name for name in session['artifacts'] if name != 'harness/arguments.json']
                files.put('harness/tests/test_extra.py', base64.b64encode(b'def test_extra(): pass\n').decode())
                files.checkpoint([*paths, 'harness/tests/test_extra.py'])
                session.update(status='waiting', steps=3)
            def assess(store, starter, result, feature, output):
                self.assertEqual(agent.start.call_count, 1)
                self.assertEqual(result['status'], 'waiting')
                self.assertNotIn('arguments.json', [item['path'] for item in candidate_source(store, context['session'])])
                return {'accepted': False}
            def agent_factory(root, store, settings, factory):
                agent.settings = settings
                return agent
            agent.start.side_effect = repair
            with patch.object(runner, 'IsolatedAgent', side_effect=agent_factory), \
                 patch.object(runner, 'run_task', side_effect=develop), \
                 patch.object(runner.study, 'wait', side_effect=lambda *args: {'session': context['session']['id'], 'status': 'waiting', 'timed_out': False}), \
                 patch.object(runner.Checks, 'assess', side_effect=assess), \
                 patch.object(runner.study, 'journal', return_value=[]):
                row = runner.trial(folder, {'name': 'test', 'task': 'Original requirements', 'fixtures': {}},
                                   source, {**DEFAULTS, 'max_steps': 3}, plan, 'sha256_file')
            self.assertEqual(agent.start.call_count, 1)
            self.assertFalse(row['review']['accepted'])
            self.assertEqual(json.loads((folder / 'original-task.json').read_text())['task'], 'Original requirements')
            self.assertEqual(row['wall_budget']['allowance_seconds'], 30)


if __name__ == '__main__':
    unittest.main()
