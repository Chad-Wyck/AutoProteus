import base64
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from autoproteus.tools import Workspace
from controller.isolation import seed_files
from controller.evaluation import source_identity
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from source_navigation import source_outline

spec = importlib.util.spec_from_file_location('navigation_study', ROOT / 'evaluations/navigation-study.py')
navigation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(navigation)


class NavigationStudyTests(unittest.TestCase):
    def test_outline_locates_module_registration_with_explicit_character_units(self):
        with temporary_directory() as directory:
            root=Path(directory);text='# é猫\r\nTOOL_SPECS = {\r\n    "one": 1\r\n}\r\n'
            (root/'providers.py').write_bytes(text.encode())
            result=source_outline(Workspace(root),{'path':'providers.py'})
            self.assertIn('not line numbers',result['units'])
            item=result['definitions'][0]
            self.assertEqual(item['name'],'TOOL_SPECS')
            self.assertEqual(text[item['start']:item['start']+item['length']],text[text.index('TOOL_SPECS'):])

    def test_partial_cost_totals_cannot_win_a_matched_success_comparison(self):
        from test_observations import ObservationTests
        from observations import call_metrics
        rows = []
        for variant, usages in [('baseline', [{'prompt_tokens': 100, 'completion_tokens': 10}] * 2),
                                ('outline', [{'prompt_tokens': 100, 'completion_tokens': 10}, {}])]:
            rows.append({'task': 'fixture', 'repeat': 1, 'variant': variant, 'review': {'accepted': True},
                'capture': {'complete': True}, 'calls': call_metrics(ObservationTests.trace(usages)),
                'run': {'seconds': 10}, 'model_task_seconds': 10, 'total_trial_seconds': 12})
        result = navigation.comparison_summary(rows)
        baseline = result['variants']['baseline']
        partial = result['variants']['outline']
        self.assertTrue(baseline['cost_totals_complete'])
        self.assertFalse(partial['cost_totals_complete'])
        self.assertEqual(partial['all_launched_input_tokens'], 100)
        self.assertEqual(partial['measurements']['input_tokens']['status'], 'partial')
        self.assertTrue(partial['measurements']['model_task_seconds']['complete'])
        pair = result['matched_success_pairs'][0]
        self.assertTrue(pair['complete_observations'])
        self.assertFalse(pair['comparable_cost_metrics']['input_tokens'])
        self.assertFalse(pair['comparable_cost_metrics']['output_tokens'])
        self.assertTrue(pair['comparable_cost_metrics']['call_seconds'])
        self.assertFalse(pair['cost_totals_complete'])

    def test_outline_is_read_only_and_offsets_are_characters_with_decorators_unicode_and_crlf(self):
        with temporary_directory() as directory:
            root = Path(directory)
            text = '# café 猫\r\nraise RuntimeError("never import this")\r\n@decorator\r\nclass Example:\r\n    async def method(self):\r\n        return "猫"\r\n'
            (root / 'source.py').write_bytes(text.encode())
            value = source_outline(Workspace(root), {'path': 'source.py'})
            self.assertEqual([item['name'] for item in value['definitions']], ['Example', 'Example.method'])
            self.assertEqual(text[value['definitions'][0]['start']:], text[text.index('@decorator'):])
            item = value['definitions'][1]
            self.assertEqual(text[item['start']:item['start'] + item['length']], text[text.index('    async def'):])
            self.assertEqual((root / 'source.py').read_bytes(), text.encode())

    def test_limits_invalid_source_and_workspace_restriction(self):
        with temporary_directory() as directory:
            root = Path(directory); workspace = Workspace(root)
            (root / 'large.py').write_text('\n'.join(f'def function_{index}(): pass' for index in range(100)))
            result = source_outline(workspace, {'path': 'large.py'})
            self.assertTrue(result['truncated'])
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), 6000)
            (root / 'bad.py').write_text('def invalid(')
            (root / 'oversized.py').write_text('#' * 100001)
            for name in ('bad.py', 'oversized.py', '../outside.py'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    source_outline(workspace, {'path': name})

    def test_variant_does_not_mutate_normal_seed_and_protected_files_are_identical(self):
        baseline = seed_files(ROOT)
        fingerprint = source_identity(baseline)
        variant = navigation.navigation_variant(baseline)
        self.assertEqual(source_identity(seed_files(ROOT)), fingerprint)
        self.assertEqual(source_identity(baseline), fingerprint)
        old, new = ({item['path']: item['data'] for item in items} for items in (baseline, variant))
        self.assertEqual({name for name in old if old[name] != new[name]}, {'autoproteus/tools.py', 'autoproteus/providers.py', 'README.md'})
        self.assertEqual(set(new) - set(old), {'autoproteus/source_navigation.py'})

    def test_efficiency_uses_matched_accepted_pairs_and_keeps_failed_attempt_costs(self):
        rows = []
        for variant, accepted, calls in [('baseline', True, 20), ('outline', False, 2)]:
            rows.append({'task': 'fixture', 'repeat': 1, 'variant': variant, 'review': {'accepted': accepted},
                         'calls': {'wire_requests': calls}, 'run': {'seconds': 10}})
        result = navigation.comparison_summary(rows)
        self.assertEqual(result['matched_success_pairs'], [])
        self.assertEqual(result['variants']['outline']['all_launched_wire_requests'], 2)
        rows[1]['review']['accepted'] = True
        self.assertEqual(len(navigation.comparison_summary(rows)['matched_success_pairs']), 1)
        rows.append({'task': 'interrupted', 'repeat': 1, 'variant': 'outline', 'operator_stop': True,
                     'model_task_seconds': 120, 'calls': {'wire_requests': 3}, 'capture': {'complete': False}})
        summary = navigation.comparison_summary(rows)['variants']['outline']
        self.assertEqual(summary['all_model_task_seconds'], 130)
        self.assertFalse(summary['cost_totals_complete'])

    def test_resume_refuses_a_different_model_without_overwriting_identity_or_unloading_it(self):
        with temporary_directory() as directory:
            root = Path(directory)
            old = {'digest': 'original', 'engine_version': 'fixture'}
            (root / 'results.json').write_text(json.dumps({'trials': [], 'model_identity': old}))
            (root / 'calibration.json').write_text(json.dumps({'passed': True, 'sources': {}, 'trusted_sha256': {}}))
            engine = Mock()
            engine.ensure_service.return_value = 'http://127.0.0.1:11435'
            plan = {'config': navigation.study.profile_configs()['qwen9b'], 'sources': {}, 'trusted_sha256': {}, 'schedule': []}
            with patch.object(navigation, 'private_path', return_value=root), patch.object(navigation, 'load_plan', return_value=(plan, {})), \
                    patch.object(navigation, 'LocalRuntime', return_value=engine), \
                    patch.object(navigation, 'model_identity', return_value={**old, 'digest': 'changed'}), \
                    patch.object(navigation, 'request_json') as unload, self.assertRaisesRegex(RuntimeError, 'identity changed'):
                navigation.run(SimpleNamespace(input='fixture', check_only=False))
            self.assertEqual(json.loads((root / 'results.json').read_text())['model_identity'], old)
            unload.assert_not_called()
            engine.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
