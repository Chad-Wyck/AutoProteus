import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_code_diagnostic import fixture,cases,score


class CodeEffectGraderTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.p,self.expected,self.requests,_=fixture(Path(self.temp.name)/'fixture',cases()[2])

    def tearDown(self):self.temp.cleanup()

    def call(self,view,ids):
        return self.p.handle({'op':'forward','ids':ids,'view':view,'mode':'generate','texts':None})

    def graded(self):return score(self.p,self.expected,self.requests,{'error':None},require_submit=False)

    def test_original_control_alone_never_credits_saved_candidate(self):
        result=self.call('original',['dev-0','dev-1'])
        self.assertIn('original',result);self.assertNotIn('candidate',result)
        self.assertEqual(len(self.requests),1)
        self.assertFalse(self.graded()['correct_candidate_test_coverage'])
        self.assertFalse(self.graded()['correct'])

    def test_split_reordered_and_comparison_are_valid(self):
        self.call('edited',['dev-1']);self.call('both',['dev-0'])
        self.assertTrue(self.graded()['correct'])
        self.assertEqual(self.graded()['test_calls'],2)

    def test_correct_prose_or_unmeasured_weights_cannot_pass(self):
        self.assertFalse(self.graded()['correct'])
        self.call('both',['dev-0','dev-1'])
        self.p.handle({'op':'undo','name':next(iter(self.p.edits))})
        self.assertFalse(self.graded()['correct'])
