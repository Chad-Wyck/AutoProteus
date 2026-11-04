"""Fresh gate controls; no model inference."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_fresh_gate import fresh_cases,recovery_case,briefs,CAPS,TOTAL,explicit_grade,FreshStudy,fresh_recovery_grade
from tensor_workspace_overnight import fixture,recovery_grade,OvernightStudy
from tensor_workspace_schema_comparison import readonly_fixture
from tensor_workspace_errors import InfrastructureStop
from weight_editor_runtime import Deadline
from lora6k_state import atomic


class FreshGateControls(unittest.TestCase):
    def setUp(self):
        self.project=Path(__file__).resolve().parents[1];parent=self.project/'.data/test-tensor-workspace';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def forward(self,p,ids=('dev-0','dev-1')):
        return p.handle({'op':'forward','mode':'generate','view':'edited','ids':list(ids),'texts':None})

    def test_eight_new_instances_and_budget(self):
        cases=fresh_cases();self.assertEqual(len(cases),8);self.assertEqual(len({c['id'] for c in cases}),8)
        self.assertEqual({k:sum(c['kind']==k for c in cases) for k in {c['kind'] for c in cases}},
            {'restore_one':2,'restore_checkpoint':2,'test_saved':2,'one_weight':2})
        self.assertEqual(CAPS['diagnostic_cells']+CAPS['diagnostic_recovery'],98304)
        self.assertEqual(sum(v for k,v in CAPS.items() if k.startswith('pilot_'))+4096,200704)
        self.assertEqual(sum(CAPS.values())+4096,TOTAL);self.assertEqual(TOTAL,299008)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'.data/apwt-overnight-20261104-002/code/tensor_workspace_precision.py').is_file(), 'Private historical frozen brief is not distributed')
    def test_accurate_briefs_do_not_confuse_feedback_with_stubs(self):
        b=briefs(self.project)
        self.assertIn("correct=None",b['explicit']);self.assertIn('correct is a Boolean',b['recovery'])
        self.assertNotIn("outcomes have status='protocol_stub' and correct=None",b['recovery'])
        self.assertIn("result['candidate']['outcomes']",b['explicit']);self.assertIn("result['candidate']['outcomes']",b['recovery'])

    def test_fresh_numerical_content_differs_and_stubs_are_null(self):
        case=fresh_cases()[2]
        p,expected,requests,n,_=fixture(self.root/'fresh',case,faithful=False)
        old=dict(case,base_start=.1001,base_end=1.0999,initial_values=[.5,.75,.625])
        q,_,_,_,_=fixture(self.root/'old-template',old,faithful=False)
        self.assertNotEqual(p.array(n[0]).tobytes(),q.array(n[0]).tobytes())
        result=self.forward(p);self.assertTrue(all(o['correct'] is None for o in result['candidate']['outcomes']))
        grade=explicit_grade(p,expected,requests,{'output':str(result),'error':None},case)
        self.assertTrue(grade['correct'])

    def test_new_readonly_task_rejects_submission_and_requires_display(self):
        case=fresh_cases()[2];p,expected,requests,n,attempts=readonly_fixture(self.root/'read-only',case,faithful=False)
        result=self.forward(p)
        self.assertFalse(explicit_grade(p,expected,requests,{'output':'','error':None},case,attempts)['correct'])
        with self.assertRaises(ValueError):p.handle({'op':'submit'})
        grade=explicit_grade(p,expected,requests,{'output':str(result),'error':None},case,attempts)
        self.assertTrue(grade['numeric_state_correct']);self.assertFalse(grade['correct'])

    def test_boolean_recovery_and_runtime_error_remain_separate(self):
        case=recovery_case();case['perturb_index']=7
        p,expected,requests,n,fixed=fixture(self.root/'recovery',case,faithful=False,recovery=True)
        a=self.forward(p);self.assertTrue(a['candidate']['outcomes'][0]['correct']);p.handle({'op':'checkpoint','label':'A'})
        fixed(n[0],case['perturb_index'],case['perturb_value'],'worse')
        b=self.forward(p);self.assertFalse(b['candidate']['outcomes'][0]['correct'])
        p.handle({'op':'restore','label':'A'});self.forward(p);p.handle({'op':'submit'})
        self.assertTrue(recovery_grade(p,expected,requests,{'error':None},True)['correct'])
        self.assertFalse(recovery_grade(p,expected,requests,{'error':'runtime'},True)['correct'])

    def test_category_ceiling_blocks_before_physical_inference(self):
        study=object.__new__(FreshStudy);study.budget_category='diagnostic_cells';study.calls=0;study.categories={}
        study.reconcile=Mock(return_value={'categories':{**{k:0 for k in CAPS},'diagnostic_cells':65536}})
        with patch('tensor_workspace_fresh_gate.Study.inference') as physical:
            with self.assertRaises(ValueError):study.inference('editor',{},[{'id':'new'}])
            physical.assert_not_called()

    def test_recovery_requires_new_testing_after_exact_restore(self):
        case=recovery_case();p,expected,requests,n,fixed=fixture(self.root/'new-tests',case,faithful=False,recovery=True)
        self.forward(p);p.handle({'op':'checkpoint','label':'A'});fixed(n[0],7,.96875,'worse');self.forward(p)
        p.handle({'op':'restore','label':'A'});p.handle({'op':'submit'})
        self.assertTrue(p.coverage(['dev-0','dev-1'])['complete'])
        result=fresh_recovery_grade(p,expected,requests,{'error':None},True)
        self.assertTrue(result['both_worse_cases_measured']);self.assertFalse(result['final_revision_retested']);self.assertFalse(result['correct'])

    def test_pilot_deadline_keeps_reserved_hour(self):
        study=object.__new__(OvernightStudy);study.deadline=Deadline(9999);study.state={};study.save=Mock();study.root=self.root
        study.plan={'design':{'entry':'frozen entry'}}
        baseline=[{'correct':True,'id':'dev-0'},{'correct':True,'id':'dev-1'}];study.baseline=Mock(return_value=baseline)
        end=time.monotonic()+5300;result=study.pilot('unchanged',deadline=Deadline(end=end))
        self.assertEqual(result['status'],'baseline_gate_stopped');self.assertEqual(study.deadline.end,end)
        self.assertLessEqual(study.development_deadline.end,end-3600)

    def test_unclosed_eos_baseline_is_not_useful_signal(self):
        study=object.__new__(OvernightStudy);study.state={};study.save=Mock();study.root=self.root
        study.plan={'design':{'entry':'complete nonempty EOS'}};study.editor_arm=Mock()
        response=self.root/'response.json';atomic(response,{'text':'unfinished reasoning'})
        study.baseline=Mock(return_value=[{'id':'dev-0','correct':False,'finish_reason':'eos','closed_thinking':False,'response_file':str(response)},
            {'id':'dev-1','correct':False,'finish_reason':'length','closed_thinking':False,'response_file':str(response)}])
        result=study.pilot('unchanged');self.assertEqual(result['status'],'baseline_gate_stopped');study.editor_arm.assert_not_called()


if __name__=='__main__':unittest.main()
