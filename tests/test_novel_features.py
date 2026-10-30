"""Trusted oracles and research integration; no candidate imports or inference."""
import ast
import base64
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shlex
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from controller.evaluation import source_identity
from controller.isolation import seed_files
from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import activation_use as use
import generalization
import model_plan
import model_study
import novel_features as novel


class Files:
    def __init__(self, values): self.values = values
    def read(self, path):
        if path not in self.values: raise ValueError('Missing artifact')
        return self.values[path]


class NovelFeatureTests(unittest.TestCase):
    def fixture(self, feature):
        spec = novel.contract(feature, 'fixed')
        final, receipt = novel.expected(spec)
        files = Files({spec['input']: final, spec['output']: json.dumps(receipt).encode()})
        event = {'type': 'action_result', 'data': {'ok': True,
            'action': {'tool': feature, 'arguments': {'path': spec['input']}}, 'result': receipt}}
        return spec, files, event

    def test_oracles_preserve_unicode_order_bytes_and_bound_output_before_mutation(self):
        path = 'sample'
        raw = ('[DEFAULT]\nx=1\n[猫]\na=café\n[API]\nx=2\n').encode()
        self.assertEqual(novel.oracle('ini_sections', path, raw), (raw, {'path': path, 'sections': ['猫', 'API']}))
        exact = ('[猫]\nx=' + 'é' * (100000 - len('[猫]\nx='))).encode()
        self.assertGreater(len(exact), 100000)
        self.assertEqual(novel.oracle('ini_sections', path, exact)[1]['sections'], ['猫'])
        with self.assertRaises(ValueError): novel.oracle('ini_sections', path, exact + b'x')
        final, receipt = novel.oracle('normalize_newlines', path, 'é\r\n猫\rx\n'.encode())
        self.assertEqual(final, 'é\n猫\nx\n'.encode())
        self.assertIs(receipt['changed'], True)
        with self.assertRaises(ValueError):
            novel.oracle('normalize_newlines', path, ('é' * 99999 + '\n').encode(), {'newline': 'crlf'})
        with self.assertRaises(ValueError): novel.oracle('unsupported', path, b'')

    def test_exact_receipts_actual_omission_and_every_shared_limit_are_required(self):
        for feature in novel.FEATURES:
            spec, files, event = self.fixture(feature)
            options = {'source_unchanged': True, 'completed': True}
            self.assertTrue(use.grade(files, spec, [event], **options)['passed'])
            for key in ('source_unchanged', 'completed', 'on_time', 'within_budget'):
                self.assertFalse(use.grade(files, spec, [event], **{**options, key: False})['passed'])
            self.assertFalse(use.grade(files, spec, [], **options)['passed'])
            extra = copy.deepcopy(event)
            extra['data']['result']['extra'] = True
            self.assertFalse(use.grade(files, spec, [extra], **options)['passed'])
            if feature == 'normalize_newlines':
                explicit = copy.deepcopy(event)
                explicit['data']['action']['arguments']['newline'] = 'lf'
                self.assertFalse(use.grade(files, spec, [explicit], **options)['passed'])
                wrong_type = copy.deepcopy(event['data']['result']); wrong_type['changed'] = 1
                files.values[spec['output']] = json.dumps(wrong_type).encode()
                self.assertFalse(use.grade(files, spec, [event], **options)['passed'])

    def test_verified_development_routes_count_but_explicit_defaults_or_plain_prints_do_not(self):
        spec, files, event = self.fixture('normalize_newlines')
        receipt = event['data']['result']
        for explicit in (False, True):
            args = {'path': spec['input'], **({'newline': 'lf'} if explicit else {})}
            programs = [
                ('python3 harness/seed.py invoke --tool normalize_newlines --arguments ' + shlex.quote(json.dumps(args)),
                 json.dumps({'check': 'candidate tool invocation', 'tool': 'normalize_newlines', 'passed': True, 'result': receipt})),
                ('python3 experience/invoke_tool.py normalize_newlines ' + shlex.quote(json.dumps(args)),
                 json.dumps({'check': 'development tool invocation', 'tool': 'normalize_newlines', 'passed': True, 'result': receipt})),
                ('PYTHONPATH=harness python3 -c ' + shlex.quote('from autoproteus.tools import Workspace\n'
                    'from pathlib import Path\nimport json\nw=Workspace(Path("."))\nr=w.execute("normalize_newlines", ' + repr(args) + ')\nprint(json.dumps(r))'), json.dumps(receipt))]
            for command, output in programs:
                development = {'type': 'action_result', 'data': {'ok': True, 'action': {'tool': 'run_command',
                    'arguments': {'command': command}}, 'result': {'exit_code': 0, 'output': output}}}
                grade = use.grade(files, spec, [development], source_unchanged=True, completed=True)
                self.assertEqual(grade['passed'], not explicit, (command, grade))
                self.assertNotIn('normalize_newlines', grade['usage']['direct'])
        fake = copy.deepcopy(development)
        fake['data']['action']['arguments']['command'] = 'python3 -c ' + shlex.quote('print(' + repr(receipt) + ')')
        self.assertFalse(use.grade(files, spec, [fake], source_unchanged=True, completed=True)['passed'])

    def test_cumulative_use_needs_both_fresh_calls_and_preserved_first_outputs(self):
        first, first_files, _ = self.fixture('ini_sections')
        preserved = novel.saved_outputs(first_files, first)
        _, task = novel.growth_task('ini_sections', {'recipe': generalization.RECIPE}, first, preserved)
        spec = task['first_use']
        self.assertTrue(all(path not in task['fixtures'] for path in spec['fixtures']))
        self.assertIn(spec['instruction'], task['task'])
        values = dict(first_files.values)
        events = []
        for item in novel.items(spec):
            final, receipt = novel.expected(item)
            values.update({item['input']: final, item['output']: json.dumps(receipt).encode()})
            events.append({'type': 'action_result', 'data': {'ok': True,
                'action': {'tool': item['feature'], 'arguments': {'path': item['input']}}, 'result': receipt}})
        files = Files(values)
        options = {'source_unchanged': True, 'completed': True}
        self.assertTrue(use.grade(files, spec, events, **options)['passed'])
        self.assertFalse(use.grade(files, spec, events[:1], **options)['passed'])
        files.values[first['output']] = b'{}'
        self.assertFalse(use.grade(files, spec, events, **options)['passed'])

    def test_familiar_pack_also_preserves_first_files_and_requires_actual_csv_default(self):
        spec = novel.strict_contract(use.contract('csv_preview', 'csv-parent'))
        self.assertIn('omit limit', spec['instruction'])
        final, receipt = use.expected(spec)
        files = Files({spec['input']: final, spec['output']: json.dumps(receipt).encode()})
        event = {'type': 'action_result', 'data': {'ok': True, 'action': {'tool': 'csv_preview',
            'arguments': {'path': spec['input']}}, 'result': receipt}}
        self.assertTrue(use.grade(files, spec, [event], source_unchanged=True, completed=True)['passed'])
        event['data']['action']['arguments']['limit'] = 5
        self.assertFalse(use.grade(files, spec, [event], source_unchanged=True, completed=True)['passed'])
        added, task = novel.growth_task('csv_preview', {'recipe': generalization.RECIPE,
            'contracts': generalization.CONTRACTS}, spec, novel.saved_outputs(files, spec))
        self.assertEqual(added, 'sha256_file')
        self.assertEqual(set(task['fixtures']), {spec['input'], spec['output']})
        self.assertEqual(task['first_use']['also_use'][0]['required_omitted_arguments'], ['limit'])

    def test_reserved_reuse_receipt_cannot_be_created_during_development(self):
        import time
        first, files, _ = self.fixture('ini_sections')
        _, task = novel.growth_task('ini_sections', {'recipe': generalization.RECIPE}, first, novel.saved_outputs(files, first))
        spec = task['first_use']
        session = {'steps': 0, 'artifacts': {spec['also_use'][0]['output']: {}}}
        budget = SimpleNamespace(summary=lambda: {'exhausted': False})
        result = use.activate(None, None, session, None, {'max_steps': 5}, spec, budget, time.monotonic() + 30, None)
        self.assertFalse(result['attempted'])
        self.assertEqual(result['reason'], 'reserved_first_use_files_created_before_activation')

    def test_unknown_graders_fail_before_vm_or_model_construction(self):
        with patch.object(generalization, 'IsolatedAgent') as agent:
            for callback in (generalization.verify_feature, generalization.verify_public):
                with self.assertRaises(ValueError): callback(None, None, 'unrecognized')
            agent.assert_not_called()

    def test_reference_controls_are_inert_valid_source_not_syntax_failures(self):
        source = seed_files(ROOT)
        before = source_identity(source)
        for fault in (None, 'byte-limit', 'path-bypass', 'sorted-sections', 'missing-write', 'wrong-default', 'false-changed', 'late-validation'):
            candidate = novel.reference(source, fault)
            for item in candidate:
                if item['path'].endswith('.py'): ast.parse(base64.b64decode(item['data']))
        self.assertEqual(source_identity(source), before)

    def test_opt_in_plan_is_frozen_inert_and_default_families_remain_unchanged(self):
        with temporary_directory() as directory:
            root = Path(directory)
            profiles = root / 'profiles.json'
            atomic_json(profiles, [{'id': 'fixture', 'config': {'provider': 'hosted',
                'base_url': 'http://127.0.0.1:1/v1', 'model': 'offline'}}])
            args = SimpleNamespace(output=str(root / 'plan'), profiles=str(profiles), mode='full', repeats=1,
                timeout=3600, output_token_budget=65536, extension_pack=novel.PACK, activation_reminder=True)
            with patch('controller.providers.request_json', side_effect=AssertionError('No inference')), contextlib.redirect_stdout(io.StringIO()):
                model_plan.prepare(args)
            plan = json.loads((root / 'plan/plan.json').read_text())
            self.assertEqual(len(plan['upgrade_tasks']), 5)
            self.assertEqual(set(generalization.CONTRACTS), {'sha256_file', 'csv_preview', 'format_json'})
            self.assertEqual(len(plan['first_use_contracts']), 5)
            self.assertTrue(use.oracle_controls(plan['first_use_contracts'])['passed'])
            self.assertEqual(plan['first_use_contracts']['1-csv_preview']['required_omitted_arguments'], ['limit'])
            args.output = str(root / 'invalid'); args.public_verifier_feedback = True
            with self.assertRaisesRegex(ValueError, 'unassisted'): model_plan.prepare(args)

    def test_pack_skips_growth_after_failed_first_use_without_starting_a_model(self):
        with temporary_directory() as directory:
            root = Path(directory)
            profiles = root / 'profiles.json'
            atomic_json(profiles, [{'id': 'fixture', 'config': {'provider': 'hosted',
                'base_url': 'http://127.0.0.1:1/v1', 'model': 'offline'}}])
            args = SimpleNamespace(output=str(root / 'plan'), profiles=str(profiles), mode='full', repeats=1,
                timeout=3600, output_token_budget=65536, extension_pack=novel.PACK, activation_reminder=True)
            calls = []
            def attempt(folder, task, source, config, plan, feature=None, earlier=None):
                calls.append((feature, earlier))
                self.assertIsNone(earlier)
                if feature:
                    return {'first_package_accepted': True, 'review': {'accepted': True}, 'first_use': {'passed': False}}
                return {'run': {'passed': True}}
            with contextlib.redirect_stdout(io.StringIO()):
                model_plan.prepare(args)
                with patch.object(model_study, 'calibrate'), patch.object(model_study, 'Appliance'), \
                    patch.object(model_study, 'model_identity', return_value={'model': 'scripted'}), \
                    patch.object(model_study, 'benchmark', return_value={'passed': True}), \
                    patch.object(model_study, 'trial', side_effect=attempt), \
                    patch('controller.providers.request_json', side_effect=AssertionError('No inference')):
                    model_study._run(SimpleNamespace(input=args.output, retry=[]))
            queue = json.loads((root / 'plan/queue.json').read_text())
            growth = [rows for key, rows in queue['cells'].items() if '_growth_' in key]
            self.assertEqual(len(growth), 5)
            self.assertTrue(all(rows[-1]['state'] == 'not_run' and rows[-1]['attempt'] == 0 for rows in growth))
            self.assertEqual(sum(feature is not None for feature, _ in calls), 5)


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Real VM controls require explicit opt in')
class NovelVMTests(unittest.TestCase):
    def test_novel_calibration_and_both_scripted_growth_chains(self):
        from novel_calibration import calibrate
        with temporary_directory() as directory:
            result = calibrate(Path(directory) / 'calibration', seed_files(ROOT))
            self.assertTrue(result['passed'])
            self.assertTrue(result['integration_run'])
            self.assertEqual(set(result['integration']), {*novel.FEATURES, 'csv_preview'})


if __name__ == '__main__': unittest.main()
