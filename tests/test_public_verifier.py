import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from controller.config import DEFAULTS
from controller.isolation import Artifacts
from controller.storage import Store, atomic_json
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import model_study
from public_verifier import announcement, inspect, repair, specification


class PublicVerifierTests(unittest.TestCase):
    def test_growth_use_spans_public_correction_but_excludes_development(self):
        def action(tool):
            return {'type': 'action_result', 'data': {'ok': True,
                'action': {'tool': tool, 'arguments': {'path': 'sample.txt'}}, 'result': {}}}
        events = [{'type': 'run_started'}, action('development_only'), action('csv_preview')]
        boundary = len(events)
        events += [{'type': 'run_started'}, action('sha256_file'),
                   {'type': 'run_finished'}, {'type': 'run_started'}, action('csv_preview')]
        # A correction can reuse a valid hash while fixing only the preview.
        self.assertEqual(model_study.activation_tool_use(events, boundary),
                         {'direct': ['csv_preview', 'sha256_file'], 'development': []})
        self.assertEqual(model_study.activation_tool_use(events, len(events)), {'direct': [], 'development': []})
        for invalid in (-1, len(events) + 1, True):
            with self.assertRaises(ValueError): model_study.activation_tool_use(events, invalid)

    @unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Scripted VM check requires opt in')
    def test_real_vm_public_correction_precedes_independent_first_use_grading(self):
        import activation_use as use
        from activation_comparison import add_hash_reference
        from controller.evaluation import freeze_source
        from controller.isolation import IsolatedAgent, seed_files
        spec = use.contract('sha256_file', 'public-feedback-scripted')
        task = {'task': spec['instruction'], 'first_use': spec}
        public = specification(task, 'sha256_file')
        _, correct = use.expected(spec)
        wrong = {**correct, 'bytes': 0}
        config = {**DEFAULTS, 'configured': True, 'provider': 'demo', 'terminal': True,
                  'action_limit': True, 'max_steps': 12}
        budget = SimpleNamespace(summary=lambda: {'exhausted': False, 'charged_output_tokens': 0, 'limit': 100000})
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            settings = SimpleNamespace(values=config, key=lambda: '')
            client = Mock()
            actions = [
                {'action': {'tool': 'sha256_file', 'arguments': {'path': spec['input']}}},
                {'action': {'tool': 'write_file', 'arguments': {'path': spec['output'], 'content': json.dumps(wrong)}}},
                {'status': 'completed'},
                {'action': {'tool': 'sha256_file', 'arguments': {'path': spec['input']}}},
                {'action': {'tool': 'write_file', 'arguments': {'path': spec['output'], 'content': json.dumps(correct)}}},
                {'action': {'tool': 'read_file', 'arguments': {'path': spec['output']}}},
                {'status': 'completed'}]
            client.complete.side_effect = [{'content': json.dumps(a)} for a in actions]
            agent = IsolatedAgent(ROOT, store, settings, lambda _: client)
            order = []
            original_grade = use.grade
            try:
                session = freeze_source(store, add_hash_reference(seed_files(ROOT)), 'Public feedback')
                session['task'] = task['task'] + announcement(public)
                deadline = time.monotonic() + 90
                def feedback(run):
                    order.append('public')
                    return repair(agent, store, session, settings, config, public, spec['fixtures'][spec['input']],
                                  budget, deadline, model_study.study.wait, run)
                def hidden(*args, **kwargs):
                    order.append('independent')
                    return original_grade(*args, **kwargs)
                with patch.object(use, 'grade', side_effect=hidden):
                    result = use.activate(agent, store, session, settings, config, spec, budget, deadline,
                                          model_study.study.wait, feedback=feedback)
                self.assertTrue(result['passed'], result)
                self.assertEqual(order, ['public', 'independent'])
                self.assertFalse(result['public_verifier']['passed_without_feedback'])
                self.assertTrue(result['public_verifier']['passed_after_feedback'])
                self.assertEqual(result['actions'], 5)
                self.assertTrue(result['source_unchanged'])
            finally:
                agent.close()

    def task(self):
        return {'task': 'Development example uses limit 2. FINAL: Use the default CSV preview and hash sample.txt; save audit.json.',
                'final_task': 'Use the default CSV preview and hash sample.txt; save audit.json.'}

    def test_public_rules_detect_wrong_preview_without_using_hidden_grading_or_candidate_code(self):
        text = 'id,value\r\n1,"café, 猫"\r\n2,"two\r\nlines"\r\n'
        spec = specification(self.task(), 'sha256_file', 'csv_preview')
        self.assertIn(self.task()['final_task'], announcement(spec))
        raw = text.encode()
        rows = list(csv.reader(io.StringIO(text, newline='')))
        audit = {'path': 'sample.txt', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                 'rows': rows[:2], 'truncated': True}
        files = Mock()
        files.read.side_effect = lambda name: raw if name == 'sample.txt' else json.dumps(audit).encode()
        with patch('activation_use.grade', side_effect=AssertionError('Hidden checks must not supply feedback')):
            before = inspect(files, spec, text)
            self.assertFalse(before['passed'])
            self.assertEqual({m['check'] for m in before['mismatches']}, {'rows', 'truncated'})
            self.assertEqual(next(m for m in before['mismatches'] if m['check'] == 'rows')['expected_records'], 3)
            audit.update(rows=rows, truncated=False)
            self.assertTrue(inspect(files, spec, text)['passed'])
            audit['truncated'] = 0
            self.assertFalse(inspect(files, spec, text)['passed'])
        missing = Mock(); missing.read.side_effect = ValueError('Missing')
        self.assertFalse(inspect(missing, spec, text)['passed'])
        with self.assertRaises(ValueError): specification({**self.task(), 'task': 'Different request'}, 'sha256_file', 'csv_preview')

    def test_one_correction_uses_remaining_allowances_and_keeps_initial_evidence(self):
        spec = specification(self.task(), 'sha256_file', 'csv_preview')
        text = 'a,b\n1,2\n'
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Public requirements', 'demo', 'fixture')
            session.update(status='completed', steps=7)
            files = Artifacts(store, session)
            files.put('sample.txt', base64.b64encode(text.encode()).decode()); files.checkpoint(['sample.txt'])
            settings = SimpleNamespace(values={**DEFAULTS, 'max_steps': 10})
            budget = SimpleNamespace(summary=lambda: {'exhausted': False})
            agent = Mock()
            initial = {'status': 'completed', 'steps': 7, 'timed_out': False}
            def wait(*args):
                audit = {'path': 'sample.txt', 'bytes': len(text.encode()), 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                         'rows': [['a', 'b'], ['1', '2']], 'truncated': False}
                files.put('audit.json', base64.b64encode(json.dumps(audit).encode()).decode())
                files.checkpoint(['sample.txt', 'audit.json'])
                session.update(status='completed', steps=9)
                return {'status': 'completed', 'steps': 9, 'timed_out': False}
            deadline = time.monotonic() + 30
            records = []
            def record(value): records.append(json.loads(json.dumps(value)))
            run, receipt = repair(agent, store, session, settings, {'max_steps': 10}, spec, text, budget, deadline, wait, initial, record=record)
            self.assertFalse(records[0]['initial']['passed'])
            self.assertNotIn('final', records[0])
            self.assertEqual(records[1]['corrections'], 1)
            self.assertTrue(records[-1]['final']['passed'])
            self.assertEqual(settings.values['max_steps'], 3)
            self.assertEqual(agent.start.call_args.kwargs['deadline'], deadline)
            self.assertEqual(agent.start.call_count, 1)
            self.assertEqual(receipt['initial_run'], initial)
            self.assertFalse(receipt['initial']['passed'])
            self.assertTrue(receipt['final']['passed'])
            self.assertFalse(receipt['passed_without_feedback'])
            self.assertTrue(receipt['passed_after_feedback'])
            self.assertNotIn('independently_verified', receipt)
            self.assertIn('AUTOMATIC PUBLIC', receipt['feedback'])

    def test_no_correction_after_limits_or_when_asking_a_real_question(self):
        spec = specification(self.task(), 'sha256_file', 'csv_preview')
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Task', 'demo', 'fixture')
            for status, steps, exhausted, late, timed_out in [('waiting', 0, False, False, False), ('completed', 10, False, False, False),
                    ('completed', 0, True, False, False), ('completed', 0, False, True, False), ('completed', 0, False, False, True)]:
                session.update(status=status, steps=steps)
                agent = Mock()
                repair(agent, store, session, SimpleNamespace(values={}), {'max_steps': 10}, spec, 'a,b\n',
                       SimpleNamespace(summary=lambda: {'exhausted': exhausted}),
                       time.monotonic() + (-1 if late else 30), Mock(), {'timed_out': timed_out})
                agent.start.assert_not_called()

    def test_prepare_is_opt_in_and_report_labels_public_feedback_separately(self):
        from model_plan import prepare
        from study_report import report, markdown
        with temporary_directory() as directory:
            root = Path(directory)
            profiles = root / 'profiles.json'
            atomic_json(profiles, [{'id': 'fixture', 'config': {'provider': 'hosted', 'base_url': 'http://127.0.0.1:8080/v1', 'model': 'fixture'}}])
            args = SimpleNamespace(output=str(root / 'study'), profiles=str(profiles), mode='full', repeats=1,
                                   timeout=3600, output_token_budget=65536, public_verifier_feedback=True)
            prepare(args)
            plan = json.loads((root / 'study/plan.json').read_text())
            self.assertTrue(plan['public_verifier_feedback'])
            self.assertIn('evaluations/public_verifier.py', plan['trusted_sha256'])
            # No hidden verdict exists in this synthetic report. Public success
            # must not manufacture an independently qualified complete chain.
            from study_support import StudyQueue, identity
            queue = StudyQueue(root / 'study', identity(plan))
            queue.run('fixture_growth_01_sha256_file', lambda _: {'public_verifier': {
                'passed_without_feedback': False, 'passed_after_feedback': True, 'corrections': 1}})
            result = report(root / 'study')
            group = result['groups']['fixture/public-verifier-feedback']
            self.assertEqual(group['public_passed_after_feedback'], 1)
            self.assertEqual(group['second_use_passed'], 0)
            self.assertIn('separate from hidden qualification', markdown(result))
            args.output = str(root / 'default'); args.public_verifier_feedback = False
            prepare(args)
            self.assertFalse(json.loads((root / 'default/plan.json').read_text())['public_verifier_feedback'])
            args.mode = 'screen'; args.public_verifier_feedback = True
            with self.assertRaisesRegex(ValueError, 'separate full'): prepare(args)
