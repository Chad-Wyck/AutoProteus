import base64
import copy
import itertools
import json
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from controller.config import DEFAULTS
from controller.evaluation import EvaluationService, freeze_source, source_identity, artifact_check, run_task
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store, atomic_json
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import model_study as runner
import generalization
from grader_faults import controls
from workflow_support import edit_feedback, mask_observations
from workflow_variants import variant, TREATMENTS, DEVELOPMENT_FOCUS, USE_FOCUS


class WorkflowTests(unittest.TestCase):
    def test_preview_is_bounded_unicode_accurate_and_covers_deletions(self):
        receipt = {'replacements': 1}
        for new in ('猫\r\n', '', 'é' * 2000):
            text = 'a' * 200 + new + 'z' * 1000
            value = edit_feedback(receipt, Path('test.py'), text, 200, len(new), 'edit-feedback')
            section = value['edited_section']
            self.assertEqual(section['content'], text[section['start']:section['end']])
            self.assertLessEqual(len(section['content']), 1000)
            self.assertEqual(section['changed_end'], 200 + len(new))
            self.assertEqual(section['change_truncated'], len(new) > 680)
        self.assertEqual(receipt, {'replacements': 1})

    def test_syntax_is_advisory_and_never_executes_python(self):
        for text, valid in [('raise RuntimeError("must not execute")', True), ('def invalid(', False), ('return 1', False)]:
            result = edit_feedback({'written': True}, Path('test.py'), text, 0, len(text), 'syntax-feedback')
            self.assertEqual(result['syntax']['valid'], valid)
            self.assertTrue(result['written'])
        self.assertNotIn('syntax', edit_feedback({}, Path('test.txt'), 'invalid(', 0, 8, 'syntax-feedback'))

    def test_mask_preserves_envelopes_recent_results_and_human_provenance(self):
        history = []
        for index in range(12):
            history += [{'role': 'assistant', 'content': json.dumps({'action': {'tool': 'run_command', 'arguments': {'command': 'echo ' + str(index)}}})},
                        {'role': 'user', 'origin': 'tool', 'content': 'ACTION RESULT\n' + json.dumps({
                            'tool': 'run_command', 'ok': index != 0, 'result': {'exit_code': index, 'output': '猫' * 3000}})}]
        human = {'role': 'user', 'content': 'ACTION RESULT\n' + 'human correction ' * 200}
        history.insert(0, human)
        original = copy.deepcopy(history)
        result = mask_observations(history, keep=2, is_human=lambda row: row == human)
        self.assertEqual(history, original)
        self.assertEqual(result[0], human)
        self.assertEqual(result[-4:], history[-4:])
        envelope = json.loads(result[2]['content'].split('\n', 1)[1])
        self.assertFalse(envelope['ok'])
        self.assertTrue(envelope['result']['observation_omitted'])
        self.assertEqual(envelope['result']['recorded_outcome']['exit_code'], 0)
        self.assertEqual(result[1], history[1])
        for settings in ({'keep': 0}, {'threshold': True}):
            with self.assertRaises(ValueError): mask_observations(history, **settings)

    def test_masked_observations_keep_valid_native_call_result_ids(self):
        from controller.providers import wire_messages
        history = []
        for index in range(10):
            history += [{'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': str(index)}}})},
                        {'role': 'user', 'origin': 'tool', 'content': 'ACTION RESULT\n' + json.dumps({
                            'tool': 'read_file', 'ok': True, 'result': {'content': 'x' * 1000}})}]
        masked = mask_observations(history, keep=2)
        for ollama in (False, True):
            wire = wire_messages(masked, ollama)
            self.assertEqual(len(wire), len(history))
            for index in range(0, len(wire), 2):
                self.assertEqual(wire[index+1]['role'], 'tool')
                if not ollama:
                    self.assertEqual(wire[index]['tool_calls'][0]['id'], wire[index+1]['tool_call_id'])
                else: self.assertEqual(wire[index+1]['tool_name'], 'read_file')

    def test_generated_checkpoint_sequences_match_committed_bytes_after_interruptions(self):
        import random
        for seed in range(4):
            with self.subTest(seed=seed), temporary_directory() as directory:
                root = Path(directory) / 'sessions'
                store = Store(root)
                session = store.create('Checkpoint sequence', 'demo', 'fixture')
                files = Artifacts(store, session)
                committed, staged = {}, {}
                randomizer = random.Random(seed)
                for step in range(40):
                    operation = randomizer.choice(('write', 'write', 'delete', 'checkpoint', 'interrupt'))
                    name = 'file-' + str(randomizer.randrange(3)) + '.txt'
                    if operation == 'write':
                        raw = ('猫-' + str(step)).encode()
                        files.put(name, base64.b64encode(raw).decode())
                        staged[name] = raw
                    elif operation == 'delete': staged.pop(name, None)
                    elif operation == 'checkpoint':
                        files.checkpoint(list(staged))
                        committed = dict(staged)
                    else:
                        store = Store(root)
                        session = store.get(session['id'])
                        files = Artifacts(store, session)
                        staged = dict(committed)
                    self.assertEqual(set(session.get('artifacts', {})), set(committed))
                    self.assertTrue(all(files.read(path) == raw for path, raw in committed.items()))

    def test_variants_preserve_default_source_and_all_existing_tests(self):
        source = seed_files(ROOT)
        fingerprint = source_identity(source)
        for name in TREATMENTS:
            changed = variant(source, name)
            before, after = ({row['path']: row['data'] for row in pack} for pack in (source, changed))
            self.assertTrue(all(after[key] == value for key, value in before.items() if key.startswith('tests/')))
            if name in ('phases', 'staged-inputs', 'submission-feedback', 'edit-context', 'verified-lesson', 'final-contract'): self.assertEqual(changed, source)
            else: self.assertIn('autoproteus/workflow_support.py', after)
        self.assertEqual(source_identity(seed_files(ROOT)), fingerprint)
        self.assertEqual(source_identity(source), fingerprint)

    def test_preparation_is_inert_freezes_both_arms_and_rejects_uncontrolled_phases(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            profiles = folder / 'profiles.json'
            profiles.write_text(json.dumps([{'id': 'qwen9b', 'config': {**DEFAULTS, 'provider': 'ollama'}}]))
            args = SimpleNamespace(output=str(folder / 'study'), profiles=str(profiles), mode='full', repeats=1,
                timeout=1800, output_token_budget=65536, experiment='masked-history', mask_keep=4, mask_threshold=1000)
            with patch.object(runner, 'model_identity', side_effect=AssertionError('No network during prepare')):
                runner.prepare(args)
            plan = json.loads((folder / 'study/plan.json').read_text())
            self.assertEqual(set(plan['variants']), {'baseline', 'masked-history'})
            self.assertEqual(plan['mask_settings']['keep'], 4)
            self.assertIn('evaluations/grader_faults.py', plan['trusted_sha256'])
            args.output, args.experiment = str(folder / 'bad'), 'phases'
            with self.assertRaisesRegex(ValueError, 'supplied parent'): runner.prepare(args)

    def test_calibration_only_mode_never_contacts_a_model_or_launches_a_trial(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            profiles = folder / 'profiles.json'
            profiles.write_text(json.dumps([{'id': 'fixture', 'config': {**DEFAULTS, 'provider': 'ollama'}}]))
            args = SimpleNamespace(output=str(folder / 'study'), profiles=str(profiles), mode='benchmark', repeats=1,
                timeout=1800, output_token_budget=65536)
            runner.prepare(args)
            with patch.object(runner, 'model_identity', side_effect=AssertionError('No inference service contact')), \
                    patch.object(runner, 'trial', side_effect=AssertionError('No model trials')):
                runner.run(SimpleNamespace(input=args.output, retry=[], check_only=True))
            self.assertTrue(json.loads((folder / 'study/check-only.json').read_text())['passed'])
            self.assertEqual(json.loads((folder / 'study/queue.json').read_text())['cells'], {})

    def test_partial_costs_and_retries_cannot_win_a_matched_comparison(self):
        queue = SimpleNamespace(data={'cells': {}})
        for name, complete in [('baseline', True), ('edit-feedback', False)]:
            row = {'review': {'accepted': True}, 'capture': {'complete': True}, 'total_seconds': 1,
                   'calls': {'measurements': {key: {'known_sum': 10, 'complete': complete} for key in
                       ('input_tokens', 'output_tokens', 'call_seconds')}}}
            queue.data['cells']['q_first_01_sha256_file_' + name] = [
                {'attempt': 1, 'state': 'completed', 'result': row}, {'attempt': 2, 'state': 'interrupted'}]
        summary = runner.comparison(queue, {'variants': {'baseline': [], 'edit-feedback': []}})
        self.assertEqual(len(summary['matched_original_successes']), 1)
        self.assertFalse(summary['matched_original_successes'][0]['comparable']['input_tokens'])
        self.assertEqual(summary['variants']['baseline']['launched'], 2)
        self.assertEqual(summary['variants']['baseline']['measurements']['input_tokens']['known_sum'], 10)
        self.assertFalse(summary['variants']['baseline']['measurements']['input_tokens']['complete'])

    def test_unchanged_source_reuse_is_never_counted_as_a_new_upgrade(self):
        row = {'reuse': {'passed': True}, 'capture': {'complete': True}, 'total_seconds': 1,
               'calls': {'measurements': {key: {'known_sum': 10, 'complete': True} for key in
                   ('input_tokens', 'output_tokens', 'call_seconds')}}}
        cells = {'q_reuse_01_format_json_' + name: [{'cell': 'q_reuse_01_format_json_' + name,
            'attempt': 1, 'state': 'completed', 'result': row}] for name in ('baseline', 'phases')}
        queue = SimpleNamespace(data={'cells': cells}, summary=lambda: {})
        plan = {'profiles': [{'id': 'q'}], 'mode': 'full', 'scope': 'reuse only', 'upgrade_tasks': [], 'repeats': 1,
                'experiment': 'phases', 'parent': {'sha256': 'fixture'}, 'reuse_task': {'name': 'reuse'},
                'variants': {'baseline': [], 'phases': []}}
        result = runner.summarize(queue, plan)
        self.assertEqual(result['profiles']['q']['first_accepted'], 0)
        self.assertEqual(result['profiles']['q']['second_verified'], 0)
        self.assertEqual(result['profiles']['q']['reuse_passed'], 2)
        self.assertEqual(result['comparison']['kind'], 'unchanged_capability_reuse')

    def test_error_attempt_preserves_measured_expense_without_success_credit(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            atomic_json(folder / 'result.json', {'review': {'accepted': True}, 'capture': {'complete': False},
                'calls': {'measurements': {'input_tokens': {'known_sum': 100, 'complete': True}}}})
            queue = SimpleNamespace(data={'cells': {'q_first_01_csv_preview_baseline': [
                {'attempt': 1, 'state': 'error', 'folder': str(folder)}]}})
            result = runner.comparison(queue, {'variants': {'baseline': [], 'phases': []}})
            self.assertEqual(result['variants']['baseline']['successes'], 0)
            cost = result['variants']['baseline']['measurements']['input_tokens']
            self.assertEqual(cost['known_sum'], 100)
            self.assertEqual(cost['status'], 'partial')

    def test_paired_queue_alternates_arms_and_resume_does_not_repeat_inference(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            profiles = folder / 'profiles.json'
            profiles.write_text(json.dumps([{'id': 'qwen9b', 'config': {**DEFAULTS, 'provider': 'ollama'}}]))
            args = SimpleNamespace(output=str(folder / 'study'), profiles=str(profiles), mode='full', repeats=1,
                timeout=1800, output_token_budget=65536, experiment='edit-feedback')
            runner.prepare(args)
            calls = []
            def calibration(folder, source): atomic_json(folder / 'calibration.json', {'passed': True})
            def attempt(folder, task, source, config, plan, feature=None, earlier=None):
                if feature:
                    calls.append((feature, plan['treatment']))
                    return {'review': {'accepted': False}}
                return {'run': {'passed': True}}
            with patch.object(runner, 'Appliance'), patch.object(runner, 'model_identity', return_value={'name': 'fixture'}), \
                    patch.object(runner.study, 'self_check', side_effect=calibration), \
                    patch.object(runner, 'run_regressions', return_value={'passed': True}), \
                    patch.object(runner, 'benchmark', return_value={'passed': True}), \
                    patch.object(runner, 'trial', side_effect=attempt), \
                    patch.object(runner, 'ResultCache', side_effect=lambda path: __import__('study_support').ResultCache(folder / 'cache')):
                run_args = SimpleNamespace(input=str(folder / 'study'), retry=[])
                runner.run(run_args)
                self.assertEqual(len(calls), 6)
                runner.run(run_args)
                self.assertEqual(len(calls), 6)
            self.assertEqual(calls[:2], [('sha256_file', 'baseline'), ('sha256_file', 'edit-feedback')])
            self.assertEqual(calls[2:4], [('csv_preview', 'edit-feedback'), ('csv_preview', 'baseline')])

    def test_phase_activation_retains_original_task_and_shares_wall_action_and_token_budgets(self):
        for treatment, status, early_use in itertools.product(('baseline', 'phases', 'staged-inputs'), ('waiting', 'completed'), (False, True)):
            with self.subTest(treatment=treatment, status=status, early_use=early_use), temporary_directory() as directory:
                folder = Path(directory)
                folder.mkdir(exist_ok=True)
                source = seed_files(ROOT)
                fixture = '{"z":1,"a":"猫"}'
                task = {'name': 'second-extension-audit', 'task': 'Original contract, focused tests, activate and audit.',
                        'fixtures': {'inventory.json': fixture}, 'checks': []}
                config = {**DEFAULTS, 'max_steps': 4}
                plan = {'experiment': 'phases', 'treatment': treatment, 'deadline': 30,
                        'generated_tokens': 17, 'ordinary_generated_tokens': 5,
                        'trusted_sha256': {}, 'environment': {}}
                agent = Mock(execution=SimpleNamespace(mode='vm'))
                settings_seen = []
                sessions = []
                def make_agent(root, store, settings, factory):
                    settings_seen.append(settings)
                    return agent
                def develop(agent, store, config, actual_task, frozen, timeout, deadline=None):
                    session = freeze_source(store, source, 'Edited seed fixture')
                    session.update(status=status, steps=3)
                    artifacts = Artifacts(store, session)
                    if treatment == 'staged-inputs':
                        self.assertNotIn('inventory.json', actual_task['fixtures'])
                        self.assertIn('development/example.json', actual_task['fixtures'])
                        self.assertIn('withholding inventory.json', actual_task['task'])
                    if treatment != 'staged-inputs' or early_use:
                        artifacts.put('inventory.json', base64.b64encode((fixture + ('\n' if early_use else '')).encode()).decode())
                        artifacts.checkpoint(list(session['artifacts']) + ['inventory.json'])
                    sessions.append((store, session))
                    self.assertGreater(timeout, 0)
                    self.assertLessEqual(timeout, 30)
                    self.assertIsNotNone(deadline)
                    self.assertTrue(actual_task['task'].startswith(task['task']))
                    return {'session': session['id'], 'timed_out': False, 'status': status}
                def use(agent, session, timeout):
                    self.assertLess(timeout, 30)
                    self.assertEqual(settings_seen[0].values['max_steps'], 1)
                    if treatment == 'staged-inputs':
                        self.assertEqual(Artifacts(sessions[0][0], session).read('inventory.json'), fixture.encode())
                    raw = (json.dumps(json.loads(fixture), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
                    files = Artifacts(sessions[0][0], session)
                    import hashlib
                    for name, value in [('inventory.json', raw), ('audit.json', json.dumps({
                        'path': 'inventory.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}).encode())]:
                        files.put(name, base64.b64encode(value).decode())
                    files.checkpoint(list(session['artifacts']) + ['audit.json'])
                    session['status'] = 'completed'
                    return {'timed_out': False}
                checks = Mock(receipts=[])
                checks.assess.return_value = {'runtime_changed': True, 'new_test_files': ['tests/test_new.py'],
                    'protected_unchanged': True, 'allowed_files_only': True,
                    **{key: {'passed': True} for key in ('regressions', 'feature', 'public')}}
                checks.feature.return_value = checks.public.return_value = {'passed': True}
                with patch.object(runner, 'IsolatedAgent', side_effect=make_agent), patch.object(runner, 'run_task', side_effect=develop), \
                        patch.object(runner, 'Checks', return_value=checks), patch.object(runner.study, 'journal', return_value=[]), \
                        patch.object(runner.study, 'wait', side_effect=use):
                    result = runner.trial(folder, task, source, config, plan, 'sha256_file', 'format_json')
                self.assertEqual(result['stage_order_preserved'], not early_use)
                self.assertEqual(result['stages']['activated'], not early_use)
                if early_use:
                    agent.start.assert_not_called()
                    agent.restart_seed.assert_not_called()
                    continue
                self.assertTrue(result['final_artifacts_correct'])
                self.assertEqual(result['token_budget']['limit'], 17)
                self.assertEqual(json.loads((folder / 'original-task.json').read_text())['task'], task['task'])
                if treatment == 'phases':
                    self.assertIn(DEVELOPMENT_FOCUS, json.loads((folder / 'task.json').read_text())['task'])
                    self.assertEqual(agent.start.call_args.args[1], USE_FOCUS)
                    self.assertEqual(agent.start.call_args.kwargs['handoff'], 'concise')
                elif treatment == 'staged-inputs':
                    self.assertTrue(result['withheld_input']['delivered'])
                    self.assertEqual(agent.start.call_args.kwargs['candidate'], sessions[0][1])
                    self.assertEqual(agent.start.call_args.kwargs['handoff'], 'concise')
                else:
                    agent.restart_seed.assert_called_once()

    def test_fault_controls_are_distinct_inert_bundles_with_named_oracles(self):
        source = seed_files(ROOT)
        specs = {name: ('Calibration file tool.', {'path': {'type': 'string'},
            **({'limit': {'type': 'integer'}} if name == 'csv_preview' else {})}, ['path']) for name in generalization.CONTRACTS}
        positive = copy.deepcopy(source)
        for item in positive:
            if item['path'] in ('autoproteus/tools.py', 'autoproteus/providers.py'):
                text = base64.b64decode(item['data']).decode()
                if item['path'].endswith('/tools.py'):
                    text = text.replace('        if tool == "list_files":', generalization.REFERENCE + '        if tool == "list_files":')
                else: text = text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr(specs) + ' | {')
                item['data'] = base64.b64encode(text.encode()).decode()
        mutants = list(controls(positive, generalization.REFERENCE))
        self.assertEqual(len(mutants), 8)
        self.assertEqual(len({source_identity(pack) for _, _, _, pack in mutants}), 8)
        self.assertTrue(all(cases for _, _, cases, _ in mutants))
        self.assertEqual(seed_files(ROOT), source)

    def test_offline_task_artifact_oracles_reject_claims_and_wrong_totals(self):
        tasks = json.loads((ROOT / 'evaluations/offline-tasks.json').read_text())
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Scripted oracle check', 'demo', 'fixture')
            artifacts = Artifacts(store, session)
            for task in tasks:
                for rule in task['checks']:
                    raw = rule.get('equals', json.dumps(rule.get('json'))).encode()
                    artifacts.put(rule['path'], base64.b64encode(raw).decode())
                    artifacts.checkpoint(list(session.get('artifacts', {})) + [rule['path']])
                    self.assertTrue(artifact_check(artifacts, rule))
                    artifacts.put(rule['path'], base64.b64encode(b'claimed success').decode())
                    artifacts.checkpoint(list(session['artifacts']))
                    self.assertFalse(artifact_check(artifacts, rule))


class VerificationLabelTests(unittest.TestCase):
    def test_only_matching_complete_host_report_can_show_passed_and_scope_is_explicit(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = freeze_source(store, seed_files(ROOT), 'Candidate')
            service = EvaluationService(ROOT, Path(directory), None, SimpleNamespace(store=store))
            self.assertEqual(service.status_for(session)['state'], 'unchecked')
            session['evaluation_check'] = 'a' * 32
            report = {'id': session['evaluation_check'], 'session': session['id'], 'status': 'completed',
                'edited_sha256': source_identity(seed_files(ROOT)), 'total': 2, 'regressions': {'edited': {'passed': True}},
                'results': [{'version': 'edited', 'passed': True}], 'checks_protected': True, 'execution_mode': 'vm'}
            service.report = report
            checked = service.status_for(session)
            self.assertEqual(checked['state'], 'passed')
            self.assertIn('not every file', checked['scope'])
            report['execution_mode'] = 'native'
            self.assertIn('unprotected', service.status_for(session)['label'])
            report['execution_mode'] = 'unknown'
            self.assertIn('unconfirmed', service.status_for(session)['label'])
            report['status'] = 'cancelled'
            self.assertNotEqual(service.status_for(session)['state'], 'passed')
            report['status'], report['total'] = 'completed', 4
            self.assertNotEqual(service.status_for(session)['state'], 'passed')
            report['edited_sha256'] = 'different'
            self.assertEqual(service.status_for(session)['state'], 'stale')
            report['session'] = 'b' * 32
            self.assertEqual(service.status_for(session)['state'], 'unchecked')


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Enable real VM checks explicitly')
class WorkflowVMTests(unittest.TestCase):
    def test_copied_seed_feedback_and_history_variants_execute_only_inside_vms(self):
        script = '''import json
from pathlib import Path
from autoproteus.tools import Workspace
from autoproteus.workflow_support import mask_observations
w = Workspace(Path('.'))
w.execute('write_file', {'path':'example.py', 'content':'name = "猫"\\r\\n'})
r = w.execute('edit_file', {'path':'example.py', 'old_text':'name = "猫"', 'new_text':'def invalid('})
text = Path('example.py').read_bytes().decode()
assert text == 'def invalid(\\r\\n'
if MODE == 'edit-feedback': assert r['edited_section']['content'] == text
if MODE == 'syntax-feedback': assert r['syntax']['valid'] is False
h = [{'role':'user', 'origin':'tool', 'content':'ACTION RESULT\\n' + json.dumps({'tool':'read_file','ok':True,'result':{'content':'x'*2000}})}]*4
assert 'observation_omitted' in mask_observations(h, keep=1)[0]['content']
Path('proof.json').write_text(json.dumps({'passed':True}))
'''
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            config = {**DEFAULTS, 'provider': 'demo', 'configured': True, 'terminal': True}
            for name in ('edit-feedback', 'syntax-feedback', 'masked-history'):
                probe = "MODE = " + repr(name) + '\n' + script
                client = lambda _: generalization.benchmark.ScriptedClient([
                    {'action': {'tool': 'run_command', 'arguments': {'command': 'PYTHONPATH=harness python3 probe.py'}}}, {'status': 'completed'}])
                agent = IsolatedAgent(ROOT, store, SimpleNamespace(values=config, key=lambda: ''), client)
                try:
                    result = run_task(agent, store, config, {'name': name, 'task': 'Run the fixture.',
                        'fixtures': {'probe.py': probe}, 'checks': [{'path': 'proof.json', 'json': {'passed': True}}]},
                        freeze_source(store, variant(seed_files(ROOT), name), name), 120)
                    self.assertTrue(result['passed'], result)
                finally: agent.close()
