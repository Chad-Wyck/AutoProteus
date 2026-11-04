"""Ordered standalone-recovery acceptance evidence; no model or VM loading."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_overnight import fixture
from tensor_workspace_fresh_gate import recovery_case
from tensor_workspace_recovery_standalone import RecoveryEvidence,LIMIT,SECONDS


class StandaloneRecoveryControls(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)
        c=recovery_case();self.p,self.expected,self.requests,self.names,self.fixed=fixture(self.root/'fixture',c,faithful=False,recovery=True)
        self.e=RecoveryEvidence(self.p)

    def tearDown(self):self.temp.cleanup()

    def evaluate_ids(self,ids=('dev-0','dev-1')):
        return self.p.handle({'op':'forward','mode':'generate','view':'edited','ids':list(ids),'texts':None})

    def initial(self):
        self.evaluate_ids();self.p.handle({'op':'checkpoint','label':'A'});self.assertTrue(self.e.ready_for_perturbation())
        self.fixed(self.names[0],7,.96875,'harness-worse');self.e.note_perturbation()

    def restore(self):self.p.handle({'op':'restore','label':'A'})

    def grade(self,error=None):return self.e.grade(self.expected,self.requests,{'error':error,'output':''})

    def test_complete_ordered_flow_and_truthful_feedback(self):
        a=self.evaluate_ids();self.assertIs(a['candidate']['outcomes'][0]['correct'],True)
        self.p.handle({'op':'checkpoint','label':'A'});self.assertTrue(self.e.ready_for_perturbation())
        self.fixed(self.names[0],7,.96875,'harness-worse');self.e.note_perturbation()
        b=self.evaluate_ids();self.assertIs(b['candidate']['outcomes'][0]['correct'],False)
        self.restore();self.evaluate_ids();self.p.handle({'op':'submit'})
        result=self.grade();self.assertTrue(result['correct']);self.assertTrue(all(result['milestones'].values()))
        self.assertEqual(LIMIT,4*8192);self.assertEqual(SECONDS,1200)

    def test_initial_both_ids_and_checkpoint_required(self):
        self.evaluate_ids(('dev-0',));self.p.handle({'op':'checkpoint','label':'A'})
        self.assertFalse(self.e.ready_for_perturbation());self.assertFalse(self.grade()['correct'])

    def test_both_worse_ids_must_precede_restoration(self):
        self.initial();self.evaluate_ids(('dev-0',));self.restore();self.evaluate_ids();self.p.handle({'op':'submit'})
        result=self.grade();self.assertTrue(result['numeric_state_correct']);self.assertFalse(result['correct'])
        self.assertFalse(result['milestones']['both_perturbed_ids_measured'])

    def test_old_exact_receipts_cannot_replace_fresh_tests(self):
        self.initial();self.evaluate_ids();self.restore();self.p.handle({'op':'submit'})
        result=self.grade();self.assertTrue(result['correct_candidate_test_coverage']);self.assertFalse(result['correct'])
        self.assertFalse(result['milestones']['fresh_both_ids_after_restoration'])

    def test_testing_after_submission_does_not_repair_order(self):
        self.initial();self.evaluate_ids();self.restore();self.p.handle({'op':'submit'});self.evaluate_ids()
        result=self.grade();self.assertTrue(result['milestones']['fresh_both_ids_after_restoration'])
        self.assertFalse(result['milestones']['submission_after_fresh_tests']);self.assertFalse(result['correct'])

    def test_noop_restore_does_not_poison_valid_fresh_tests(self):
        self.initial();self.evaluate_ids();self.restore();self.evaluate_ids();self.restore();self.p.handle({'op':'submit'})
        self.assertEqual(len(self.e.valid_restores),1);self.assertTrue(self.grade()['correct'])

    def test_runtime_error_still_fails_after_valid_effects(self):
        self.initial();self.evaluate_ids();self.restore();self.evaluate_ids();self.p.handle({'op':'submit'})
        self.assertFalse(self.grade('runtime error')['correct'])


if __name__=='__main__':unittest.main()
