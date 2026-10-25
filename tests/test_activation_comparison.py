"""Study preparation preserves the control and defines independently checkable tasks."""
import base64
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from activation_comparison import variant, tasks, add_hash_reference
from controller.artifacts import seed_files
from controller.evaluation import source_identity


class ActivationComparisonTests(unittest.TestCase):
    def test_only_copied_context_changes_and_original_is_preserved(self):
        source = seed_files(ROOT)
        before = source_identity(source)
        baseline, changed = variant(source, 'baseline'), variant(source, 'activation-history')
        a, b = ({item['path']: item['data'] for item in pack} for pack in (baseline, changed))
        self.assertEqual({name for name in a if a[name] != b[name]}, {'autoproteus/context.py'})
        self.assertEqual(source_identity(source), before)
        self.assertEqual(source_identity(seed_files(ROOT)), before)
        compile(base64.b64decode(b['autoproteus/context.py']), 'context.py', 'exec')
        with self.assertRaises(ValueError): variant(source, 'unknown')

    def test_task_outcomes_are_derived_from_fixtures_and_reuse_both_tools(self):
        for repeat in (1, 2, 3):
            pair = tasks(repeat)
            first, second = pair['first'], pair['second']
            self.assertEqual(second['required_tools'], ['inventory_files', 'sha256_file'])
            self.assertFalse(set(first['fixtures']) & set(second['fixtures']))
            expected = first['final_checks'][0]['json']
            self.assertEqual(expected['sha256'], hashlib.sha256(first['fixtures'][expected['path']].encode()).hexdigest())
            listing, audit = (rule['json'] for rule in second['final_checks'])
            self.assertEqual(len(listing['files']), 2)
            self.assertEqual([row['path'] for row in listing['files']], sorted(row['path'] for row in listing['files']))
            for row in audit['files']:
                raw = second['fixtures'][row['path']].encode()
                self.assertEqual((row['bytes'], row['sha256']), (len(raw), hashlib.sha256(raw).hexdigest()))
            self.assertNotIn('sha256_file', second['fixtures'])

    def test_hash_controls_remain_inert_source_and_preserve_existing_tests(self):
        source = seed_files(ROOT)
        before = {item['path']: item['data'] for item in source}
        for fault in (None, 'absent', 'exact-boundary', 'false-digest', 'required-schema'):
            after = {item['path']: item['data'] for item in add_hash_reference(source, fault)}
            self.assertTrue(all(after[name] == value for name, value in before.items() if name.startswith('tests/')))
            for name in ('autoproteus/tools.py', 'autoproteus/providers.py'):
                compile(base64.b64decode(after[name]), name, 'exec')


if __name__ == '__main__': unittest.main()
