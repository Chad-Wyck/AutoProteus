import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import discovery_study as discovery
from discovery_probe import arguments, expected
from controller.isolation import seed_files


class DiscoveryTests(unittest.TestCase):
    def test_missing_or_reverse_mapped_submission_is_reported_without_crashing(self):
        starter = seed_files(ROOT); source = discovery.calibration_source(starter)
        class Files:
            def __init__(self, values): self.values = values
            def read(self, path):
                if path not in self.values: raise ValueError('File not found')
                return self.values[path]
        reverse = json.dumps({'tool': 'stock_reference', 'arguments':
                              {'@INPUT_A': 'a.tsv', '@INPUT_B': 'b.tsv', '@OUTPUT': 'summary.json'}})
        for values, reason in [({'development/capability.json': reverse}, 'missing_root_declaration'),
                               ({'capability.json': reverse}, 'invalid_declaration'),
                               ({'capability.json': '{broken'}, 'invalid_json')]:
            selected, status = discovery.submitted_declaration(Files(values), source, starter)
            self.assertIsNone(selected); self.assertFalse(status['valid']); self.assertEqual(status['reason'], reason)
        good = json.dumps({'tool': 'stock_reference', 'arguments':
                          {'sources': ['@INPUT_A', '@INPUT_B'], 'output': '@OUTPUT'}})
        selected, status = discovery.submitted_declaration(Files({'capability.json': good}), source, starter)
        self.assertTrue(status['valid']); self.assertEqual(selected['tool'], 'stock_reference')

    def test_model_selected_interface_must_be_new_and_paths_caller_selectable(self):
        starter = seed_files(ROOT); source = discovery.calibration_source(starter)
        value = {'tool': 'stock_reference', 'arguments': {'sources': ['@INPUT_A', '@INPUT_B'], 'output': '@OUTPUT'}}
        self.assertEqual(discovery.declaration(value, source, starter), value)
        for wrong in ({**value, 'tool': 'read_file'}, {**value, 'arguments': {'hardcoded': 'east.tsv'}},
                      {**value, 'tool': '../escape'}, {**value, 'extra': True}):
            with self.assertRaises(ValueError): discovery.declaration(wrong, source, starter)
        actual = arguments(value['arguments'], {'@INPUT_A': 'a.tsv', '@INPUT_B': 'b.tsv', '@OUTPUT': 'out.json'})
        self.assertEqual(actual, {'sources': ['a.tsv', 'b.tsv'], 'output': 'out.json'})
        self.assertEqual(value['arguments']['output'], '@OUTPUT')

    def test_outcome_oracle_combines_duplicates_and_empty_inputs(self):
        self.assertEqual(expected('sku\tunits\n猫\t2\n猫\t1\n', 'sku\tunits\n'),
                         {'items': [{'sku': '猫', 'units': 3}], 'total_units': 3})
        self.assertNotIn('stock_reference', discovery.TASK['task'])
        self.assertNotIn('sha256_file', discovery.TASK['task'])
