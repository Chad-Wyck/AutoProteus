"""Documentation-comparison contract controls; no model inference."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_schema_comparison import readonly_fixture,variants,grade,frozen_brief,SCHEMA,LIMIT,SECONDS


class SchemaControls(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)
        self.case=variants()[0];self.p,self.expected,self.requests,self.names,self.attempts=readonly_fixture(self.root/'fixture',self.case,faithful=False)

    def tearDown(self):self.temp.cleanup()

    def forward(self,ids):
        return self.p.handle({'op':'forward','mode':'generate','view':'edited','ids':ids,'texts':None})

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'.data/apwt-overnight-20261104-002/code/tensor_workspace_precision.py').is_file(), 'Private historical frozen brief is not distributed')
    def test_frozen_brief_has_no_schema_and_only_append_changes(self):
        root=Path(__file__).resolve().parents[1]/'.data/apwt-overnight-20261104-002/code'
        brief=frozen_brief(root);self.assertNotIn("result['candidate']['outcomes']",brief)
        clarified=brief+SCHEMA;self.assertTrue(clarified.startswith(brief));self.assertEqual(clarified[len(brief):],SCHEMA)
        self.assertEqual(LIMIT,4*8192);self.assertEqual(SECONDS,1200)

    def test_complete_printed_results_pass_separate_measures(self):
        result=self.forward(['dev-0','dev-1'])
        row=grade(self.p,self.expected,self.requests,{'output':str(result),'error':None},self.attempts,self.case)
        for key in ('numerical_preservation','correct_candidate_test_coverage','execution_completed','display_completed','task_completed'):
            self.assertTrue(row[key],key)
        self.assertEqual(row['forbidden_operation_count'],0)

    def test_no_display_and_runtime_error_cannot_pass(self):
        result=self.forward(['dev-0','dev-1'])
        missing=grade(self.p,self.expected,self.requests,{'output':'','error':None},self.attempts,self.case)
        self.assertTrue(missing['execution_completed']);self.assertFalse(missing['task_completed'])
        failed=grade(self.p,self.expected,self.requests,{'output':str(result),'error':'KeyError: outcomes'},self.attempts,self.case)
        self.assertTrue(failed['correct_candidate_test_coverage']);self.assertFalse(failed['execution_completed']);self.assertFalse(failed['task_completed'])

    def test_forbidden_operations_are_denied_without_changing_candidate(self):
        before=self.p.candidate_state()['candidate_id']
        for r in ({'op':'undo','name':self.names[0]},{'op':'submit'},{'op':'checkpoint','label':'extra'}):
            with self.assertRaises(ValueError):self.p.handle(r)
        result=self.forward(['dev-0','dev-1'])
        row=grade(self.p,self.expected,self.requests,{'output':str(result),'error':None},self.attempts,self.case)
        self.assertEqual(before,self.p.candidate_state()['candidate_id']);self.assertTrue(row['numerical_preservation'])
        self.assertEqual(row['forbidden_operation_count'],3);self.assertFalse(row['task_completed']);self.assertFalse(self.p.submitted)

    def test_separate_reversed_requests_and_complete_display(self):
        p,expected,requests,names,attempts=readonly_fixture(self.root/'birch',variants()[1],faithful=False)
        result=[]
        for ids in (['dev-1'],['dev-0']):result.append(p.handle({'op':'forward','mode':'generate','view':'edited','ids':ids,'texts':None}))
        row=grade(p,expected,requests,{'output':str(result),'error':None},attempts,variants()[1])
        self.assertTrue(row['task_completed']);self.assertTrue(row['requested_call_structure'])


if __name__=='__main__':unittest.main()
