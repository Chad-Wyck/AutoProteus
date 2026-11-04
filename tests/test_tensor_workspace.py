"""Numeric boundary controls; arbitrary editor programs are never run on host."""
import base64
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
import numpy as np
from tensor_workspace_policy import TensorPolicy, selection, uniform_scaling_only
from weight_editor_runtime import Deadline
from lora6k_state import sha


class TensorBoundaryTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace';root.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=root);self.root=Path(self.tmp.name)
        self.base=self.root/'original.bin';self.value=np.arange(1,65,dtype='<f4').reshape(8,8)
        self.base.write_bytes(b'header!!'+self.value.tobytes()+b'tail')
        self.records={'blk.0.ffn_down.weight':{'shape':[8,8],'offset':8,'bytes':256,'editable':True},
            'output.weight':{'shape':[8,8],'offset':8,'bytes':256,'editable':False}}
        self.p=TensorPolicy({'path':str(self.base),'sha256':sha(self.base)},self.records,self.root/'broker',{'layers':1})

    def tearDown(self):self.tmp.cleanup()

    def save(self,value,name='blk.0.ffn_down.weight'):
        raw=value.astype('<f4').tobytes();meta=self.p.handle({'op':'write_start','name':name,'shape':list(value.shape),'bytes':len(raw)})
        self.p.handle({'op':'write_chunk','handle':meta['handle'],'offset':0,'data':base64.b64encode(raw).decode()})
        return self.p.handle({'op':'write_finish','handle':meta['handle'],'sha256':hashlib.sha256(raw).hexdigest()})

    def test_flexible_sparse_edits_and_snapshot(self):
        for variant in ('weight','column','head'):
            value=self.value.copy()
            if variant=='weight':value[3,4]+=1
            if variant=='column':value[:,2]*=.5
            if variant=='head':value[2:4,:]=0
            result=self.save(value);self.assertGreater(result['changed_entries'],0)
            self.assertEqual(sha(self.base),self.p.base['sha256'])
            import unittest.mock
            with unittest.mock.patch('tensor_workspace_policy.shutil.disk_usage',return_value=type('Disk',(),{'free':30*1024**3})()):
                snapshot=self.p.snapshot(self.root/variant,Deadline(5))
            data=Path(snapshot['path']).read_bytes();self.assertEqual(data[:8],b'header!!');self.assertEqual(data[-4:],b'tail')
            np.testing.assert_array_equal(np.frombuffer(data[8:-4],dtype='<f4').reshape(8,8),value)

    def test_protected_unknown_shape_and_nonfinite(self):
        for name in ('output.weight','../../host','blk.999.ffn_down.weight'):
            with self.assertRaises(ValueError):self.save(self.value,name)
        with self.assertRaises(ValueError):self.save(self.value.reshape(4,16))
        for invalid in (np.nan,np.inf,np.float32(3.4e38)):
            value=self.value.copy();value[0,0]=invalid
            with self.assertRaises(ValueError):self.save(value)

    def test_uniform_scaling_noop_and_freeze(self):
        self.assertTrue(uniform_scaling_only(self.value,self.value*.5))
        for value in (self.value,self.value*.5):
            with self.assertRaises(ValueError):self.save(value)
        changed=self.value.copy();changed[0,0]=2;self.save(changed)
        self.p.handle({'op':'submit'})
        for request in ({'op':'undo','name':'blk.0.ffn_down.weight'},
            {'op':'write_start','name':'blk.0.ffn_down.weight','shape':[8,8],'bytes':256}):
            with self.assertRaises(ValueError):self.p.handle(request)

    def test_wire_fields_handles_order_and_quotas(self):
        for request in ({'op':'metadata','path':'C:\\'}, {'op':'exec','code':'print(1)'},
            {'op':'observation_start','handle':'../../original.bin'}, {'op':'read_chunk','handle':'x','offset':0}):
            with self.assertRaises(ValueError):self.p.handle(request)
        meta=self.p.handle({'op':'read_start','name':'blk.0.ffn_down.weight','rows':[0,2],'cols':None,'edited':False})
        with self.assertRaises(ValueError):self.p.handle({'op':'read_chunk','handle':meta['handle'],'offset':4})
        data=self.p.handle({'op':'read_chunk','handle':meta['handle'],'offset':0});self.assertEqual(len(base64.b64decode(data['data'])),64)
        self.p.handle({'op':'read_close','handle':meta['handle']});self.p.max_transfer=self.p.transferred
        with self.assertRaises(ValueError):self.p.handle({'op':'read_start','name':'blk.0.ffn_down.weight','rows':None,'cols':None,'edited':False})

    def test_index_windows_and_mismatched_upload(self):
        np.testing.assert_array_equal(self.p.array('blk.0.ffn_down.weight',rows={'slice':[1,4,2]},cols=[-1,0]),self.value[[1,3]][:,[7,0]])
        for invalid in ([8],[True],{'slice':[None,None,0]},'../x'):
            with self.assertRaises(ValueError):selection(invalid,8)
        meta=self.p.handle({'op':'write_start','name':'blk.0.ffn_down.weight','shape':[8,8],'bytes':256})
        for request in ({'op':'write_chunk','handle':meta['handle'],'offset':1,'data':'AAAA'},
            {'op':'write_finish','handle':meta['handle'],'sha256':'bad'}):
            with self.assertRaises(ValueError):self.p.handle(request)

    def test_candidate_revision_and_evaluation_receipts(self):
        from tensor_workspace_feedback import evaluated_receipt
        changed=self.value.copy();changed[0,0]=2;entry=self.save(changed)
        self.assertEqual(entry['candidate']['revision'],1)
        self.assertFalse(entry['candidate']['current_revision_generated_tested'])
        original=evaluated_receipt(self.p,'original',self.p.base,'generate',['dev-0'],['dev-0'])
        self.assertFalse(original['saved_edits_applied']);self.assertEqual(original['evaluated_revision'],0)
        self.assertIn('NOT applied',original['notice']);self.assertEqual(original['cached_result_ids'],['dev-0'])
        candidate=evaluated_receipt(self.p,'edited',{'sha256':'validated-candidate'},'generate',['dev-0'])
        self.assertTrue(candidate['saved_edits_applied']);self.assertEqual(candidate['evaluated_revision'],1)
        self.assertEqual(candidate['new_inference_ids'],['dev-0'])
        self.p.tested_revision=1;self.assertTrue(self.p.status()['candidate']['current_revision_generated_tested'])
        changed[1,1]+=1;self.save(changed)
        self.assertFalse(self.p.status()['candidate']['current_revision_generated_tested'])
        self.p.handle({'op':'undo','name':'blk.0.ffn_down.weight'})
        empty=evaluated_receipt(self.p,'edited',self.p.base,'generate',['dev-0'])
        self.assertFalse(empty['saved_edits_applied']);self.assertIn('No edits',empty['notice'])

    def test_comparison_actually_tests_candidate_before_original(self):
        from unittest.mock import Mock
        from tensor_workspace_study import Study
        study=object.__new__(Study);study.arm='arm';study.root=self.root;study.policy=self.p;study.worker_deadline=Deadline(5)
        study.state={'arms':{'arm':{'forward_calls':0,'sampled_tokens':0}}}
        study.plan={'limits':{'forward_calls':8,'development_generated_tokens':524288},'models':{'original_target':self.p.base}}
        study.by_id={'dev-0':{'id':'dev-0'}};study.baseline_cache={'dev-0':True};study.save=Mock()
        candidate={'path':'trusted-temporary-candidate','sha256':'candidate-sha'};study.snapshot=Mock(return_value=candidate)
        study.discard_snapshot=Mock();study.inference=Mock(return_value=[{'id':'dev-0','correct':False,'generated_tokens':2,'head':'a'*2000,'tail':'b'*3000}])
        study.baseline=Mock(return_value=[{'id':'dev-0','correct':False,'generated_tokens':3}])
        value=self.value.copy();value[0,0]=2;self.save(value)
        result=study.forward({'ids':['dev-0'],'view':'both','mode':'generate','texts':None})
        self.assertEqual(list(result),['candidate','original'])
        self.assertTrue(result['candidate']['receipt']['saved_edits_applied'])
        self.assertFalse(result['original']['receipt']['saved_edits_applied'])
        self.assertEqual(result['original']['receipt']['cached_result_ids'],['dev-0'])
        self.assertEqual(study.state['arms']['arm']['sampled_tokens'],2)
        study.inference.assert_called_once();study.discard_snapshot.assert_called_once_with(self.p,candidate)
        self.assertEqual(self.p.tested_revision,self.p.revision)
        self.assertEqual(len(result['candidate']['outcomes'][0]['head']),500)
        self.assertEqual(len(result['candidate']['outcomes'][0]['tail']),1000)

    def test_probe_summary_keeps_handles_bounded(self):
        import json
        from tensor_workspace_feedback import observation_summary
        row={'id':'probe-0','top_tokens':[{'id':i,'text':'a'*40,'logit':float(i)} for i in range(12)],
            'activations':{'layer-'+str(i):[3584] for i in range(100)}}
        result=observation_summary(row,'opaque')
        self.assertEqual(result['npz_handle'],'opaque');self.assertEqual(result['activation_count'],100)
        self.assertLess(len(json.dumps([result]*8)),12000)


class EditorCellTests(unittest.TestCase):
    def test_complete_final_code_only(self):
        from tensor_workspace_study import code_cell
        self.assertEqual(code_cell('<think>reasoning code</think>\n```python\nprint(1)\n```')[0],'print(1)\n')
        for raw in ('```python\nprint(1)\n```','<think>```python\nprint(1)\n```',
            '</think>```python\nprint(1)\n```\n```python\nprint(2)\n```','</think>all done'):
            with self.assertRaises(ValueError):code_cell(raw)


if __name__=='__main__':unittest.main()
