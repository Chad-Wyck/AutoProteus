"""Numeric effects, transactional restore and provenance at the research boundary."""
import base64
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
import numpy as np
from lora6k_state import sha
from tensor_workspace_precision import PreciseTensorPolicy


class PrecisionTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent); self.root=Path(self.temp.name)
        self.value=np.linspace(.1001,1.0999,16,dtype='<f4').reshape(4,4)
        self.base=self.root/'base'; self.value.tofile(self.base)
        self.p=PreciseTensorPolicy({'path':str(self.base),'sha256':sha(self.base)},
            {'blk.0.weight':{'shape':[4,4],'offset':0,'bytes':64,'editable':True}},self.root/'policy',{})

    def tearDown(self): self.temp.cleanup()

    def save(self,value):
        raw=value.astype('<f4').tobytes(); handle=self.p.handle({'op':'write_start','name':'blk.0.weight','shape':[4,4],'bytes':64})['handle']
        self.p.handle({'op':'write_chunk','handle':handle,'offset':0,'data':base64.b64encode(raw).decode()})
        return self.p.handle({'op':'write_finish','handle':handle,'sha256':hashlib.sha256(raw).hexdigest()})

    def test_untouched_float_bits_preserved_across_multiple_saves(self):
        value=self.value.copy(); value[0,0]=.5; self.save(value)
        actual=self.p.array('blk.0.weight'); self.assertEqual(np.count_nonzero(actual.view('u4')!=self.value.view('u4')),1)
        value=actual.copy();value[1,1]=.75;self.save(value)
        self.assertEqual(np.count_nonzero(self.p.array('blk.0.weight').view('u4')!=self.value.view('u4')),2)
        self.assertEqual(sha(self.base),self.p.base['sha256'])

    def test_restore_exact_state_and_content_bound_test_evidence(self):
        p=self.p; p.handle({'op':'checkpoint','label':'original'})
        value=self.value.copy(); value[0,0]=.5;self.save(value)
        p.mark_evaluated('generate',['dev-0'],'measured-hash'); saved=p.candidate_state()['candidate_id']
        p.handle({'op':'checkpoint','label':'useful'})
        value[1,1]=.75;self.save(value);self.assertFalse(p.candidate_state()['current_revision_generated_tested'])
        result=p.handle({'op':'restore','label':'useful'})
        self.assertEqual(result['candidate']['candidate_id'],saved)
        self.assertTrue(result['candidate']['current_revision_generated_tested'])
        self.assertEqual(result['candidate']['evaluation_evidence']['generate']['ids'],['dev-0'])
        p.handle({'op':'restore','label':'original'});self.assertFalse(p.edits)

    def test_corrupt_checkpoint_cannot_partially_restore_and_labels_cannot_be_paths(self):
        value=self.value.copy();value[0,0]=.5;self.save(value)
        self.p.handle({'op':'checkpoint','label':'saved'})
        entry=next(iter(self.p.edits.values()));Path(entry['path']).write_bytes(b'bad')
        self.p.handle({'op':'undo','name':'blk.0.weight'}); before=self.p.candidate_state()
        with self.assertRaises(ValueError): self.p.handle({'op':'restore','label':'saved'})
        self.assertEqual(self.p.candidate_state(),before)
        for label in ('../host','C:\\host','',True):
            with self.assertRaises(ValueError): self.p.handle({'op':'checkpoint','label':label})
        self.p.handle({'op':'submit'})
        with self.assertRaises(ValueError): self.p.handle({'op':'restore','label':'saved'})

    def test_development_ids_are_not_accepted_as_probe_text(self):
        with self.assertRaisesRegex(ValueError,'test_candidate'):
            self.p.handle({'op':'forward','mode':'probe','texts':['dev-0'],'ids':None,'view':'edited'})
