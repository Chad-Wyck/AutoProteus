import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_intermediates import complete_score


class IntermediateGraderTests(unittest.TestCase):
    def test_reference_match_requires_completed_thinking(self):
        for reason, raw, expected in [('eos', '</think>answer', True), ('length', '</think>answer', False), ('eos', 'answer', False)]:
            row = complete_score({'correct': True}, {'finish_reason': reason, 'raw_text': raw})
            self.assertEqual(row['correct'], expected)
            self.assertTrue(row['reference_correct'])
        self.assertFalse(complete_score({'correct': False}, {'finish_reason': 'eos', 'raw_text': '</think>wrong'})['correct'])

    def test_sharing_uses_existing_ownership_boundary(self):
        from unittest.mock import patch
        import lora6k_supervisor as guard
        import weight_editor_owned as owned
        from tensor_workspace_intermediates import enable_sharing
        old, admission = guard.check_owners, owned.admission
        try:
            enable_sharing()
            self.assertEqual(guard.check_owners([], {}, []), [])
            with self.assertRaises(ValueError): guard.check_owners([['123', 'python.exe', '100']], {123: 'python.exe'}, [])
        finally: guard.check_owners, owned.admission = old, admission

    def test_idle_capture_app_does_not_allow_active_compute(self):
        from weight_editor_shared_gpu import classify_shared_owners
        from lora6k_supervisor import check_owners
        rows=[['123','SnippingTool.exe','N/A']];names={123:'SnippingTool.exe'}
        self.assertEqual(len(classify_shared_owners(rows,names,[],check_owners)),1)
        with self.assertRaises(ValueError):
            classify_shared_owners(rows,names,[{'Name':'pid_123_engtype_Compute','UtilizationPercentage':1}],check_owners)
