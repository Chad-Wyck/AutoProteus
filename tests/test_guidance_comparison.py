"""Preparation and examples are checked without starting inference."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from controller.evaluation import source_identity
from controller.isolation import seed_files
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import guidance_comparison as comparison


class GuidancePreparationTests(unittest.TestCase):
    def test_frozen_preparation_has_identical_tasks_budgets_and_no_inference(self):
        before = source_identity(seed_files(ROOT))
        with temporary_directory() as directory, \
                patch.object(comparison, 'IsolatedAgent', side_effect=AssertionError('No VM in prepare')), \
                patch.object(comparison, 'Store', side_effect=AssertionError('No task launch')):
            output = Path(directory) / 'study'
            plan = comparison.prepare(output)
            self.assertFalse(plan['internet'])
            self.assertEqual(len(plan['tasks']), 3)
            self.assertEqual(plan['allowance']['actions'], 128)
            self.assertTrue(plan['allowance']['shared_across_stages'])
            packs = {name: json.loads((output / arm['file']).read_text()) for name, arm in plan['arms'].items()}
            for name, pack in packs.items():
                self.assertEqual(source_identity(pack), plan['arms'][name]['sha256'])
            base, short = ({item['path']: item['data'] for item in packs[name]}
                           for name in ('baseline', 'short-guidance'))
            self.assertEqual({name for name in base if base[name] != short[name]}, {'README.md', 'autoproteus/protocol.py'})
            self.assertEqual(source_identity(seed_files(ROOT)), before)
            for task in plan['tasks']:
                expected = task['final_checks'][0]['json']
                self.assertEqual(len(expected['files']), 2)
                self.assertTrue(all('/archive/' not in item['path'] for item in expected['files']))
            with self.assertRaises(ValueError):
                comparison.prepare(output)

    def test_changed_arm_is_rejected_before_any_vm_check(self):
        with temporary_directory() as directory:
            output = Path(directory) / 'study'
            plan = comparison.prepare(output)
            (output / plan['arms']['baseline']['file']).write_text('[]')
            with patch.object(comparison, 'IsolatedAgent', side_effect=AssertionError('Must reject before VM')):
                with self.assertRaisesRegex(ValueError, 'Frozen arm changed'):
                    comparison.calibrate(output)

    def test_oversize_control_guide_is_rejected_before_creating_a_plan(self):
        source = seed_files(ROOT)
        for row in source:
            if row['path'] == 'README.md':
                row['data'] = base64.b64encode(b'x' * 12001).decode()
        with temporary_directory() as directory, patch.object(comparison, 'seed_files', return_value=source):
            output = Path(directory) / 'study'
            with self.assertRaisesRegex(ValueError, 'whole-file read limit'):
                comparison.prepare(output)
            self.assertFalse(output.exists())

    def test_offline_example_runs_and_is_shipped_without_host_code(self):
        source = {item['path']: item['data'] for item in seed_files(ROOT)}
        self.assertIn('examples/test_web_extension.py', source)
        self.assertLessEqual(len(base64.b64decode(source['README.md']).decode('utf-8')), 12000)
        self.assertFalse(any(name.startswith('controller/') for name in source))
        with temporary_directory() as directory:
            run = subprocess.run([sys.executable, '-B', str(ROOT / 'examples/test_web_extension.py')],
                                 cwd=directory, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(b'Ran 1 test', run.stderr)

    def test_reference_and_fault_sources_are_inert_and_keep_protected_tests(self):
        original = seed_files(ROOT)
        before = {row['path']: row['data'] for row in original}
        for fault in (None, 'absent', 'recursive-default', 'character-count', 'follow-links', 'escaping-path',
                      'exact-boundary', 'schema-required'):
            pack = comparison.reference(original, fault)
            after = {row['path']: row['data'] for row in pack}
            self.assertTrue(all(after[name] == value for name, value in before.items() if name.startswith('tests/')))
            for name in ('autoproteus/tools.py', 'autoproteus/providers.py'):
                compile(base64.b64decode(after[name]), name, 'exec')
        self.assertEqual(original, seed_files(ROOT))


if __name__ == '__main__':
    unittest.main()
