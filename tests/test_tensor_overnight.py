"""Adversarial contract and stop controls, without inference or model execution."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_overnight import fixture,diagnostic_cases,CAPS,TOTAL,OvernightStudy,recovery_grade
from tensor_workspace_code_diagnostic import score
from tensor_workspace_errors import InfrastructureStop,GlobalDeadlineStop,CellAllowanceExceeded
from tensor_workspace_vm import TensorVM
from tensor_workspace_precision import PreciseTensorPolicy
from tensor_workspace_study import Study
from weight_editor_runtime import Deadline,TokenBudget,usage
from lora6k_state import sha
from weight_editor_owned import await_ownership
from lora6k_state import atomic


class ScorerContract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace');self.root=Path(self.temp.name)
        self.case=diagnostic_cases()[2]
        self.p,self.expected,self.requests,self.names,self.fixed=fixture(self.root/'fixture',self.case,faithful=False)

    def tearDown(self):self.temp.cleanup()

    def forward_fixture(self,ids=('dev-0','dev-1'),view='edited'):
        return self.p.handle({'op':'forward','mode':'generate','view':view,'ids':list(ids),'texts':None})

    def grade(self,**kw):
        return score(self.p,self.expected,self.requests,{'error':None},submission_policy=kw.pop('submission_policy','forbidden'),**kw)

    def test_forbidden_required_and_optional_submission(self):
        self.forward_fixture();self.assertTrue(self.grade()['correct'])
        self.assertFalse(self.grade(submission_policy='required')['correct'])
        self.p.handle({'op':'submit'})
        self.assertFalse(self.grade()['correct']);self.assertTrue(self.grade(submission_policy='required')['correct'])
        self.assertTrue(self.grade(submission_policy='optional')['correct'])

    def test_earlier_candidate_does_not_poison_fully_tested_final(self):
        self.forward_fixture();self.fixed(self.names[0],3,.875,'later')
        self.expected={n:self.p.array(n).tobytes() for n in self.names}
        self.assertFalse(self.grade()['correct'])
        self.forward_fixture(('dev-1',));self.assertFalse(self.grade()['correct'])
        self.forward_fixture(('dev-0',));self.assertTrue(self.grade()['correct'])
        self.assertEqual(len(self.p.receipt_ledger),3)

    def test_requests_cannot_forge_receipts(self):
        self.requests.append({'view':'edited','candidate_id':self.p.candidate_state()['candidate_id'],'ids':['dev-0','dev-1']})
        self.assertFalse(self.grade()['correct'])

    def test_split_receipts_are_preserved_and_settings_bound(self):
        self.forward_fixture(('dev-0',));self.forward_fixture(('dev-1',))
        self.assertEqual([r['ids'] for r in self.p.receipt_ledger],[['dev-0'],['dev-1']])
        self.assertTrue(self.p.coverage(['dev-0','dev-1'],'synthetic-v2')['complete'])
        self.assertFalse(self.p.coverage(['dev-0','dev-1'],'different-settings')['complete'])

    def test_original_probe_and_failed_requests_never_credit_generation(self):
        self.forward_fixture(view='original');self.assertFalse(self.grade()['correct'])
        with self.assertRaises(ValueError):self.forward_fixture(('not-an-id',))
        self.p.mark_evaluated('probe',['dev-0','dev-1'],'probe-hash')
        self.assertFalse(self.grade()['correct'])

    def test_transient_write_and_exact_restore_fail_no_write_contract(self):
        self.p.handle({'op':'checkpoint','label':'A'})
        value=self.p.array(self.names[0]);value.flat[3]=.875;raw=value.tobytes()
        h=self.p.handle({'op':'write_start','name':self.names[0],'shape':list(value.shape),'bytes':len(raw)})['handle']
        self.p.handle({'op':'write_chunk','handle':h,'offset':0,'data':base64.b64encode(raw).decode()})
        self.p.handle({'op':'write_finish','handle':h,'sha256':hashlib.sha256(raw).hexdigest()})
        self.p.handle({'op':'restore','label':'A'});self.forward_fixture()
        graded=self.grade(write_policy='forbidden')
        self.assertTrue(graded['numeric_state_correct']);self.assertFalse(graded['operation_compliant']);self.assertFalse(graded['correct'])

    def test_forbidden_attempt_counts_even_without_mutation(self):
        with self.assertRaises(ValueError):self.p.handle({'op':'write_start','name':'missing','shape':[1],'bytes':4})
        self.forward_fixture();self.assertFalse(self.grade(write_policy='forbidden')['correct'])

    def test_base_identity_and_exact_restore(self):
        self.forward_fixture();saved=self.p.candidate_state()['candidate_id'];self.p.handle({'op':'checkpoint','label':'A'})
        self.fixed(self.names[0],3,.875,'later');self.assertFalse(self.p.coverage(['dev-0','dev-1'])['complete'])
        self.p.handle({'op':'restore','label':'A'});self.assertEqual(saved,self.p.candidate_state()['candidate_id'])
        self.assertTrue(self.p.coverage(['dev-0','dev-1'])['complete'])
        self.p.base['sha256']='other-base';self.assertNotEqual(saved,self.p.candidate_state()['candidate_id'])

    def test_recovery_cannot_erase_a_runtime_error_after_valid_effects(self):
        p,expected,requests,names,fixed=fixture(self.root/'recovery',self.case,faithful=False,recovery=True)
        request={'op':'forward','mode':'generate','view':'edited','ids':['dev-0','dev-1'],'texts':None}
        response=p.handle(request)
        self.assertIn('outcomes',response['candidate']);self.assertNotIn('outcomes',response)
        p.handle({'op':'checkpoint','label':'A'});fixed(names[0],5,.9375,'worse');p.handle(request)
        p.handle({'op':'restore','label':'A'});p.handle(request);p.handle({'op':'submit'})
        self.assertTrue(recovery_grade(p,expected,requests,{'error':None},True)['correct'])
        graded=recovery_grade(p,expected,requests,{'error':'KeyError: outcomes'},True)
        self.assertTrue(graded['numeric_state_correct']);self.assertTrue(graded['correct_candidate_test_coverage'])
        self.assertFalse(graded['cell_completed']);self.assertFalse(graded['correct'])

    def test_precise_real_pilot_route_and_budget_arithmetic(self):
        self.assertEqual(sum(CAPS.values())+4096,TOTAL)
        self.assertEqual(CAPS['pilot_confirmation']+CAPS['pilot_preservation'],98304)
        study=object.__new__(Study);study.root=self.root;study.project=self.root;study.deadline=Deadline(10)
        study.state={'arms':{}};study.save=Mock();study.settings_sha256='settings'
        study.plan={'numeric_policy':'precise-v2','models':{'original_target':self.p.base,'unchanged':{'sha256':'editor'}},
            'limits':{'arm_seconds':5,'editor_calls':1,'editor_tokens':8192,'cell_seconds':1},
            'image':{},'tokenizers':{'editor_tokenizer':{'path':'unused'}}}
        study.records=self.p.records;study.cases=[];study.golds={}
        study.inference=Mock(return_value=[{'raw_text':'</think>\n```python\nsubmit()\n```','generated_tokens':10}])
        tokenizer=Mock();tokenizer.encode.return_value=types.SimpleNamespace(ids=[1,2])
        tokenizers=types.SimpleNamespace(Tokenizer=types.SimpleNamespace(from_file=Mock(return_value=tokenizer)))
        vm=Mock()
        def execute(code,policy,seconds):
            self.assertIsInstance(policy,PreciseTensorPolicy)
            policy.handle({'op':'checkpoint','label':'pilot-checkpoint'})
            policy.handle({'op':'submit'});return {'error':None,'output':'submitted'}
        vm.execute.side_effect=execute
        with patch.dict(sys.modules,{'tokenizers':tokenizers}),patch('tensor_workspace_study.TensorVM',return_value=vm):
            study.editor_arm('unchanged',[])
        self.assertTrue(study.policy.submitted);self.assertIn('pilot-checkpoint',study.policy.checkpoints)
        vm.close.assert_called_once()

    def test_partial_upload_not_credited_as_complete_task(self):
        # An unfinished upload cannot be silently submitted by the bounded scorer.
        a=self.p.array(self.names[0])
        self.p.handle({'op':'write_start','name':self.names[0],'shape':list(a.shape),'bytes':a.nbytes})
        self.forward_fixture();graded=self.grade(write_policy='forbidden')
        self.assertFalse(graded['correct'])


class StopClassification(unittest.TestCase):
    def make_vm(self):
        vm=object.__new__(TensorVM);vm.closed=Mock();vm.closed.is_set.return_value=False
        vm.counter=0;vm.deadline=Deadline(5);vm.send=Mock();vm.close=Mock()
        return vm

    def test_startup_stop_is_not_an_exception(self):
        self.assertFalse(issubclass(InfrastructureStop,Exception))

    def test_transport_error_closes_owned_vm_and_stops_study(self):
        vm=self.make_vm();vm.next=Mock(side_effect=RuntimeError('EOF'))
        with self.assertRaises(InfrastructureStop):vm.execute('print(1)',Mock())
        vm.close.assert_called_once()

    def test_send_error_closes_owned_vm(self):
        vm=self.make_vm();vm.send.side_effect=BrokenPipeError('closed')
        with self.assertRaises(InfrastructureStop):vm.execute('print(1)',Mock())
        vm.close.assert_called_once()

    def test_cell_allowance_is_distinct_from_global_deadline(self):
        vm=self.make_vm()
        # Persist the clock patch through the exception handler.
        base=time.monotonic()
        with patch('tensor_workspace_vm.time.monotonic',side_effect=[base,base+2]):
            vm.next=Mock(side_effect=TimeoutError('cell'))
            with self.assertRaises(CellAllowanceExceeded):vm.execute('while True: pass',Mock(),seconds=1)
        vm=self.make_vm();vm.deadline=Deadline(end=base+.5)
        with patch('tensor_workspace_vm.time.monotonic',side_effect=[base,base+1]):
            vm.next=Mock(side_effect=TimeoutError('global'))
            with self.assertRaises(GlobalDeadlineStop):vm.execute('while True: pass',Mock(),seconds=3)

    def test_interrupted_reservation_is_charged(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace') as temp:
            binding={'nonce':'n','request_sha256':'r'};budget=TokenBudget(temp,128,binding)
            budget.before_sample();budget.record('x',1);budget.close()
            measured=usage(temp,binding)
            self.assertEqual(measured['charged_tokens'],64);self.assertFalse(measured['measurement_complete'])

    def test_ownership_handshake_is_bound_and_waits_for_ack(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace') as temp:
            folder=Path(temp);calls=[]
            def deliver(seconds):
                calls.append(seconds);atomic(folder/'OWNERSHIP-ACK.json',{'token':'nonce','pid':123})
            result=await_ownership(folder,'nonce',123,Deadline(1),sleep=deliver)
            self.assertEqual(result['pid'],123);self.assertEqual(len(calls),1)
            with self.assertRaises(ValueError):await_ownership(folder,'other',123,Deadline(1))

    def test_missing_ownership_ack_expires_without_native_load(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace') as temp:
            clock=[0.]
            def tick(seconds):clock[0]+=seconds
            with self.assertRaises(TimeoutError):
                await_ownership(temp,'nonce',123,Deadline(.1,clock=lambda:clock[0]),sleep=tick)


if __name__=='__main__':unittest.main()
