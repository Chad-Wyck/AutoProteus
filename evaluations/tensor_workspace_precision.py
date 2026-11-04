"""Opt-in research broker: exact untouched values and explicit candidate saves.

No inference or candidate selection is automatic. Checkpoints reference committed
numeric blobs; guest labels cannot name host paths. The starter seed is unchanged.
"""
import copy
import re
from lora6k_state import atomic, sha, identity
from tensor_workspace_policy import TensorPolicy
from weight_editor_runtime import require
from weight_editor_sparse import bf16_round


class PreciseTensorPolicy(TensorPolicy):
    def __init__(self,*args,**kwargs):
        self.checkpoints = {}; self.evaluations = {}; self.receipt_ledger = []
        self.operation_history = []; self.task_start = 0; self.evaluation_context = {}
        super().__init__(*args,**kwargs)

    def prepare_value(self,name,raw):
        import numpy as np
        current = self.array(name)
        changed = raw.view(np.uint32) != current.view(np.uint32)
        value = current.copy()
        value[changed] = bf16_round(raw[changed])
        return value

    def mark_evaluated(self,mode,ids,model_sha,*,view='edited',context=None):
        key = self.candidate_state()['candidate_id']
        row = {'receipt_index':len(self.receipt_ledger),'ids':list(ids),'model_sha256':model_sha,
            'revision':self.revision,'candidate_id':key if view=='edited' else None,
            'mode':mode,'view':view,'completed':True,**copy.deepcopy(context or self.evaluation_context)}
        self.receipt_ledger.append(row)
        if view=='edited':self.evaluations.setdefault(key,{})[mode] = copy.deepcopy(row)
        self.event('evaluation_receipt',row)
        atomic(self.directory/'evaluation-ledger.json',self.receipt_ledger)
        return copy.deepcopy(row)

    def coverage(self,required_ids,settings_sha256=None):
        current=self.candidate_state()['candidate_id']
        rows=[r for r in self.receipt_ledger if r['candidate_id']==current and r['view']=='edited'
            and r['mode']=='generate' and r['completed']
            and (settings_sha256 is None or r.get('settings_sha256')==settings_sha256)]
        covered={i for r in rows for i in r['ids']}
        return {'required_ids':list(required_ids),'covered_ids':sorted(covered),
            'complete':bool(required_ids) and set(required_ids)<=covered,'receipt_indexes':[r['receipt_index'] for r in rows]}

    def candidate_state(self):
        state = super().candidate_state()
        state['candidate_id']=identity({'base_sha256':self.base['sha256'],'tensor_catalog':self.records,
            'policy':'precise-changed-only-bf16-v2','patch_id':state['candidate_id']})
        evidence = self.evaluations.get(state['candidate_id'],{})
        state.update(current_revision_generated_tested='generate' in evidence,
            some_generation_occurred='generate' in evidence,
            receipt_ledger=copy.deepcopy([r for r in self.receipt_ledger if r['candidate_id']==state['candidate_id']]),
            evaluation_evidence=copy.deepcopy(evidence),
            generated_test_means='Measured this exact candidate content; does not imply a correct answer')
        return state

    def status(self):
        state = super().status()
        state['checkpoints'] = [{'label': name, 'candidate_id': row['candidate_id'], 'revision_at_save': row['revision']}
            for name,row in self.checkpoints.items()]
        return state

    def handle(self,r):
        op=r.get('op') if isinstance(r,dict) else None
        row={'op':op,'name':r.get('name') if isinstance(r,dict) else None,'applied':False}
        self.operation_history.append(row)
        if op in ('write_start','write_chunk','write_finish','undo','restore','submit'):
            self.event('operation_attempt',row)
        try:
            result=self._handle(r)
        except BaseException as error:
            row['error']=type(error).__name__+': '+str(error)
            raise
        else:
            row['applied']=True
            return result

    def _handle(self,r):
        if isinstance(r,dict) and r.get('op') in ('checkpoint','restore'):
            self.frames += 1
            require(self.frames<=20000 and not self.submitted, 'Workspace limit or frozen candidate')
            require(set(r)=={'op','label'} and isinstance(r['label'],str)
                and re.fullmatch(r'[A-Za-z0-9_-]{1,48}',r['label']), 'Use a short checkpoint label, not a path')
            require(self.upload is None, 'Finish the pending upload first')
            label=r['label']
            if r['op']=='checkpoint':
                require(label not in self.checkpoints and len(self.checkpoints)<32, 'Checkpoint exists or limit reached')
                state=self.candidate_state()
                self.checkpoints[label]={'edits':copy.deepcopy(self.edits), 'candidate_id':state['candidate_id'],'revision':self.revision}
            else:
                require(label in self.checkpoints, 'Unknown checkpoint')
                saved=self.checkpoints[label]
                # Validate every entry before changing any current state.
                for entry in saved['edits'].values(): require(sha(entry['path'])==entry['sha256'],'Checkpoint blob changed')
                if saved['candidate_id'] != self.candidate_state()['candidate_id']:
                    self.edits=copy.deepcopy(saved['edits']);self.revision+=1
            self.event(r['op'],{'label':label,'candidate':self.candidate_state()})
            atomic(self.directory/'edits.json',self.edits)
            atomic(self.directory/'checkpoints.json',self.checkpoints)
            return {'label':label,'candidate':self.candidate_state()}
        if isinstance(r,dict) and r.get('op')=='forward' and r.get('mode')=='probe':
            require(not any(isinstance(t,str) and re.fullmatch(r'dev-\d+',t.strip()) for t in (r.get('texts') or [])),
                'Development IDs are not prompt text. Use test_candidate([development_id]) to generate answers.')
        result=super().handle(r)
        if isinstance(r,dict) and r.get('op')=='undo':atomic(self.directory/'edits.json',self.edits)
        return result


GUIDANCE = '''Experimental workspace additions:
model_info(), edit_status(), list_tensors(), and submit() take NO arguments. submit() freezes the current candidate; print any explanatory message separately.
list_tensors() returns a LIST OF DICTS, e.g. [{'name':'blk.0.attn_norm.weight','shape':[1024],'dtype':'float32','editable':True}].
load_tensor(..., edited=True) reads the CURRENT candidate. edited=False reads the IMMUTABLE ORIGINAL. undo_edit(name) restores one original tensor.
Returned arrays have the stored shape. Inspect array.shape; a flattened index addresses array.flat[index], not necessarily array[index].
save_edit(name,array) still replaces one complete tensor. Only values changed from the current candidate are rounded to BF16; all untouched float32 bits are preserved exactly.
save_checkpoint('label') saves the current candidate's numeric state. restore_checkpoint('label') restores that exact state, including removing later edits. Neither operation runs inference or chooses a winner for you. Checkpoints do not restore Python variables.
edit_status() shows current candidate fingerprint, checkpoint labels and exact-content test receipts. A test receipt identifies what was measured; it is not evidence that an answer was correct.
test_candidate(['dev-0']) generates an answer. inspect_candidate([exact_prompt_text]) only inspects last-token logits/activations; a development ID is not a prompt.
Generation return structure: test_candidate(ids) returns {'candidate': {'receipt': {...}, 'outcomes': [{'id': ..., 'correct': ..., ...}, ...]}}. Read result['candidate']['outcomes'], not result['outcomes']. compare_with_original(ids) returns both 'candidate' and 'original' entries with the same structure. Printing the complete result is sufficient; parsing it is optional.
'''
