import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
spec = importlib.util.spec_from_file_location('growth_study', ROOT / 'evaluations/growth-study.py')
growth = importlib.util.module_from_spec(spec); spec.loader.exec_module(growth)


class GrowthStudyTests(unittest.TestCase):
    def test_arms_share_invoker_inputs_and_contract_only_procedure_is_added(self):
        plan = {'invoke_tool': 'same invoker', 'procedure': 'early read-back procedure'}
        baseline = growth.task(plan, {'arm': 'baseline'})
        treatment = growth.task(plan, {'arm': 'procedure'})
        self.assertEqual({k: v for k, v in treatment['fixtures'].items() if k != 'experience/upgrade.md'}, baseline['fixtures'])
        self.assertTrue(treatment['task'].startswith(baseline['task']))
        self.assertEqual(treatment['fixtures']['experience/upgrade.md'], plan['procedure'])

    def test_verified_extensions_and_incomplete_attempts_do_not_claim_cumulative_success(self):
        rows = [{'id': '1-baseline', 'repeat': 1, 'arm': 'baseline', 'verified_extension': True},
                {'id': '1-procedure', 'repeat': 1, 'arm': 'procedure', 'verified_extension': True}]
        result = growth.summarize(rows)
        self.assertEqual(result['matched_functional_successes'], [])
        self.assertEqual(result['arms']['baseline']['verified_extensions'], 1)
        self.assertEqual(result['arms']['baseline']['functional_growth'], 0)
        self.assertEqual(result['arms']['baseline']['finished'], 0)
        for row in rows:
            row.update(scores={'functional_growth': True}, calls={}, seconds=1, capture={})
        self.assertEqual(len(growth.summarize(rows)['matched_functional_successes']), 1)


if __name__ == '__main__':
    unittest.main()
