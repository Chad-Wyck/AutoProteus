"""Recorded candidates are immutable data, never host-imported modules."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluations'))
from grader_regressions import cases, load_case


class GraderFixtureTests(unittest.TestCase):
    def test_all_fixtures_are_present_and_have_verified_source_identities(self):
        examples = cases()
        self.assertEqual(len(examples), 4)
        self.assertEqual(sum(case['expected_pass'] for case in examples), 1)
        self.assertEqual(len({case['source_sha256'] for case in examples}), len(examples))
        for case in examples:
            source = load_case(case)
            self.assertIn('autoproteus/tools.py', {item['path'] for item in source})

    def test_corrupt_identity_and_escaping_fixture_path_are_rejected(self):
        original = cases()[0]
        for field, value in [('gzip_sha256', '0' * 64), ('source_sha256', '0' * 64), ('file', '../outside.json.gz')]:
            case = copy.deepcopy(original)
            case[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): load_case(case)


if __name__ == '__main__': unittest.main()
