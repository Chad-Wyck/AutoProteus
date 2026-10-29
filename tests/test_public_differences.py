import csv
from pathlib import Path
import sys
import io
import json
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluations"))
from public_verifier import first_difference, inspect, specification


class PublicDifferenceTests(unittest.TestCase):
    def test_equal_record_counts_still_identify_the_observed_crlf_error(self):
        instruction = 'Use csv_preview with its default limit and save exactly path, rows and truncated.'
        task = {'task': instruction, 'first_use': {'instruction': instruction,
                'input': 'input.csv', 'output': 'receipt.json'}}
        spec = specification(task, 'csv_preview')
        text = 'name,value\r\n"café, 猫",1\r\n"line\r\nbreak",2\r\n'
        rows = list(csv.reader(io.StringIO(text, newline='')))
        receipt = {'path': 'input.csv', 'rows': [row[:] for row in rows], 'truncated': False}
        receipt['rows'][2][0] = 'line\nbreak'
        files = Mock(); files.read.side_effect = lambda path: text.encode() if path == 'input.csv' else json.dumps(receipt).encode()
        result = inspect(files, spec, text)
        self.assertFalse(result['passed'])
        mismatch = result['mismatches'][0]
        self.assertEqual(mismatch['expected_records'], mismatch['actual_records'])
        self.assertEqual(mismatch['difference']['location'], '/rows/2/0')
        self.assertEqual(mismatch['difference']['character'], 4)
        self.assertEqual(mismatch['difference']['expected_character'], '\r')
        self.assertEqual(mismatch['difference']['actual_character'], '\n')
        self.assertNotIn('line\r\nbreak', json.dumps(mismatch))
        receipt['rows'] = rows
        self.assertTrue(inspect(files, spec, text)['passed'])

    def test_types_lengths_missing_keys_and_json_pointer_locations(self):
        self.assertEqual(first_difference(False, 0)['kind'], 'type')
        self.assertEqual(first_difference(['a', 'b'], ['a'])['kind'], 'length')
        self.assertEqual(first_difference({'a/b~c': 1}, {})['location'], '/a~1b~0c')
        self.assertEqual(first_difference([['猫\r\nx']], [['猫\nx']], '/rows')['location'], '/rows/0/0')
        self.assertIsNone(first_difference([['a', '猫\r\nb']], [['a', '猫\r\nb']]))

    def test_large_values_do_not_expand_diagnostic_packets(self):
        value = first_difference('猫' * 100000, '猫' * 99999 + '犬', '/rows/0/0')
        self.assertEqual(value['character'], 99999)
        self.assertLess(len(json.dumps(value)), 600)
        value = first_difference(['same'] * 10000, ['same'] * 9999 + ['different'])
        self.assertEqual(value['kind'], 'diagnostic_limit')
        self.assertLess(len(json.dumps(value)), 600)
        wanted = found = 0
        for _ in range(20):
            wanted, found = [wanted], [found]
        value = first_difference(wanted, found)
        self.assertEqual(value['kind'], 'diagnostic_limit')
        self.assertLess(len(json.dumps(value)), 600)


if __name__ == '__main__':
    unittest.main()
