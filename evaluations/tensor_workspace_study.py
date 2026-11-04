"""Bounded matched persistent-kernel study; never runs editor Python on host."""
import json
from pathlib import Path
import re
import sys
import time
import uuid

from lora6k_state import atomic,read,sha,identity,exclusive
from tensor_workspace_policy import TensorPolicy
from tensor_workspace_precision import PreciseTensorPolicy, GUIDANCE
from tensor_workspace_errors import InfrastructureStop, GlobalDeadlineStop, CellAllowanceExceeded
from tensor_workspace_vm import TensorVM
from tensor_workspace_feedback import evaluated_receipt,observation_summary
from weight_editor_owned import launch
from weight_editor_runtime import Deadline,require,check_files,account_before_grading
from weight_repair_protocol import grade

BRIEF='''You are AutoProteus.
You are investigating a frozen local 0.8B language model that often loops or fails math. Improve its weights using a persistent CPU Python/NumPy workspace. You choose which permitted tensors, individual weights, neurons, columns or attention heads to change. No predefined layer/direction/scale menu is supplied. Merely multiplying an entire tensor by a constant is forbidden. Embeddings, output head, final normalization, and inactive MTP tensors are protected. Keep shapes unchanged; saved floats are rounded to BF16, with nonfinite values rejected. Do not use gradients, training, optimizers, external tools or internet. Do not implement an optimizer yourself.
Return one complete ```python ... ``` cell per turn. The cell runs inside your isolated VM; variables and /work files persist. Host inference runs only through the explicit evaluation helpers below. Print observations or leave a helper call as the cell's final expression; its result is displayed automatically. Only bounded output is returned. Finish with submit() after saving the chosen edits. A correct-looking explanation does not change weights.
Available helpers:
list_tensors() -> names, stored NumPy shapes, editable flags (matrices use output rows/input columns).
model_info(), edit_status().
load_tensor(name, rows=None, cols=None, edited=True) -> float32 NumPy array. Use slices/index lists for large tensors, especially protected embeddings. At most 64MiB per transfer.
save_edit(name, array) -> replace ONE COMPLETE tensor, preserving its original shape. For a column edit, first load its full editable matrix, modify selected columns, then save the full matrix. Edits accumulate. undo_edit(name) restores that tensor's original value.
test_candidate(['dev-0']) -> generate answers using ALL currently saved edits. This is the usual call after save_edit. At most two development IDs per call. Results show the tested candidate revision and weight hash, independently checked correctness and bounded response excerpts. Samples have 32K output allowance; unfinished or empty output is not correctness.
compare_with_original(['dev-0']) -> evaluate the CURRENT CANDIDATE and show the IMMUTABLE ORIGINAL BASELINE side by side. Original results never include saved edits and may be cached. Both views are explicitly labelled. compare_with_original(texts=[exact_prompt_string,...]) compares original/candidate logits and activations instead of generating answers. Saving another edit creates a new revision that needs another candidate test; reading an old baseline is not a candidate test.
inspect_candidate([exact_prompt_string,...]) -> last-token logits/top tokens and activations using ALL saved edits. At most four texts, at most 4096 input tokens each. For math/continuation probes include chat markers and assistant continuation yourself. This does not generate answers or establish task correctness. Returned npz handles can be inspected using load_observation(handle), which yields a dict of NumPy arrays. Captures include last-token per-layer MLP activations/outputs and residuals; these are observations, not suggested edit directions.
No host paths, arbitrary host commands or Python execution are available. The VM has no internet, host mounts or credentials. Whole weights are NOT placed in your language context; read the arrays you need through the kernel.
You have 48 editor turns, 8 forward calls, 524288 sampled development tokens and two hours total. Each code cell has 60 CPU-wall seconds excluding controlled inference, and the VM has 2GiB RAM. Forward failures still count. The initial shared baseline below is free for both arms. Use development feedback to choose a final edit; unseen checks are withheld until both arms freeze. Preserve baseline-correct behavior; improve incorrect behavior, or solve correctly with fewer tokens. Do not infer that an edit helped without measuring it.
'''


def code_cell(raw,*,thinking_enabled=True):
    require(type(thinking_enabled) is bool,'Explicit Boolean thinking mode required')
    if thinking_enabled:
        require('</think>' in raw,'Thinking did not finish; no code executed')
        final=raw.rsplit('</think>',1)[1]
    else:
        final=raw.lstrip()
        if final.startswith('<think>'):
            require('</think>' in final,'Unexpected unclosed generated thinking wrapper')
            final=final.split('</think>',1)[1]
        elif final.startswith('</think>'):final=final[len('</think>'):]
    for marker in ('<|im_end|>','<|endoftext|>'):final=final.replace(marker,'')
    cells=re.findall(r'```(?:python|py)\s*\n(.*?)```',final,re.S)
    require(len(cells)==1 and len(cells[0].encode())<=64000,'Return exactly one complete fenced Python cell')
    return cells[0],final.strip()


class Study:
    def __init__(self,root):
        self.root=Path(root).resolve();self.plan=read(self.root/'manifest.json');self.project=Path(self.plan['project'])
        require(identity(self.plan)==(self.root/'manifest.sha256').read_text().strip(),'Frozen manifest changed')
        check_files(self.root/'code',self.plan['code']);check_files(self.root,self.plan['data']);check_files(self.project,self.plan['controller_files'])
        if self.plan.get('predecessor_completion'):
            source=self.plan['predecessor_completion'];check_files(source['root'],source['files'])
        require(read(self.plan['design']['vm_preflight_receipt'])['status']=='passed','VM preflight required')
        if self.plan['design'].get('vm_preflight_sha256'):
            require(sha(self.plan['design']['vm_preflight_receipt'])==self.plan['design']['vm_preflight_sha256'],'Preflight evidence changed')
        self.deadline=Deadline(self.plan['limits']['total_seconds']);self.cases=read(self.root/'inputs.json')['cases'];self.golds=read(self.root/'hidden-golds.json')
        self.records=read(self.root/'tensor-catalog.json');self.by_id={c['id']:c for c in self.cases};self.calls=0
        self.worker_deadline=self.deadline;self.baseline_cache={};self.arm=None;self.vm=None
        self.settings_sha256=identity({'protocol':self.plan['target_protocol'],'design':self.plan['design'],
            'engine_files':self.plan['engine_files']})
        if self.plan.get('baseline_import'):
            source=self.plan['baseline_import'];check_files(source['root'],source['files'])
            original=read(Path(source['root'])/'baseline-results.json')
            self.baseline_cache={i:dict(original[i],measurement_origin='Verified shared original control from prior frozen run') for i in source['ids']}
            atomic(self.root/'baseline-results.json',self.baseline_cache)
        self.state={'status':'running','pid':__import__('os').getpid(),'began_unix':time.time(),'phase':'initializing','arms':{},'inference_calls':0}
        self.save()

    def save(self):atomic(self.root/'runner.json',self.state)

    def inference(self,mode,model,cases,*,remaining=1048576):
        self.calls+=1;name='call-'+str(self.calls).zfill(3);path=self.root/'requests'/(name+'.json')
        require(not (self.root/'STOP').exists(),'Operator stop')
        r={'mode':mode,'model':model,'cases':cases,'remaining_tokens':remaining,
            'study_context':{'phase':self.state['phase'],'editor_arm':self.arm},
            'tokenizer':self.plan['tokenizers']['editor_tokenizer' if mode=='editor' else 'target_tokenizer']}
        atomic(path,r);atomic(self.root/'active-request.json',{'sha256':sha(path)})
        folder=self.root/'runs'/name;self.state.update(inference_calls=self.calls,current_call=name);self.save()
        try:
            result=launch(self.root,folder,[self.plan['interpreters']['python']['path'],str(self.root/'code/tensor_workspace_worker.py'),str(path)],self.worker_deadline)
        except BaseException as error:raise InfrastructureStop(type(error).__name__+': '+str(error)) from error
        finally:
            if (folder/'usage.json').exists():
                binding=read(folder/'usage.json')['binding'];account_before_grading(self.root/'usage.json',name,folder,binding)
        require(result['request_sha256']==sha(path),'Inference/request binding mismatch')
        if mode=='probe':return [{'id':c['id'],**read(folder/(c['id']+'.json')),'observation_path':str(folder/(c['id']+'.npz'))} for c in cases]
        rows=[]
        for case in cases:
            response=read(folder/(case['id']+'.json'))
            if mode=='editor':rows.append(response);continue
            self.worker_deadline.remaining();checked=grade(self.plan['interpreters']['cpu_python']['path'],response['text'],self.golds[case['id']],timeout=min(10,self.worker_deadline.remaining()))
            rows.append({'id':case['id'],**checked,'finish_reason':response['finish_reason'],'generated_tokens':response['generated_tokens'],
                'request_sha256':sha(path),'settings_sha256':self.settings_sha256,
                'wall_seconds':response['wall_seconds'],'head':response['raw_text'][:1000],'tail':response['raw_text'][-2200:],
                'response_file':str(folder/(case['id']+'.json'))})
        atomic(folder/'checked.json',rows);return rows

    def baseline(self,ids):
        missing=[self.by_id[i] for i in ids if i not in self.baseline_cache]
        if missing:
            rows=self.inference('generate',self.plan['models']['original_target'],missing)
            self.baseline_cache.update({r['id']:r for r in rows});atomic(self.root/'baseline-results.json',self.baseline_cache)
        return [self.baseline_cache[i] for i in ids]

    def public(self,rows):
        return [{k:(v[:500] if k=='head' else v[-1000:] if k=='tail' else v) for k,v in r.items() if k!='response_file'} for r in rows]

    def snapshot(self,policy,folder):return policy.snapshot(folder,self.worker_deadline)

    def discard_snapshot(self,policy,model):
        # Numeric patches and manifests persist; disposable full copies do not accumulate.
        p=Path(model['path']).resolve();base=Path(self.plan['models']['original_target']['path']).resolve()
        if p!=base:
            require(p.is_relative_to(self.root) and p.name=='model-f32.gguf','Refusing cleanup outside owned candidate directory')
            require(sha(p)==model['sha256'],'Candidate changed before cleanup');p.unlink()
            atomic(p.parent/'MODEL-REMOVED.json',{'sha256':model['sha256'],'reason':'Temporary inference copy; validated tensor patches retained'})
            policy.snapshot_cache={k:v for k,v in policy.snapshot_cache.items() if v['path']!=str(p)}

    def forward(self,request):
        state=self.state['arms'][self.arm];require(state['forward_calls']<self.plan['limits']['forward_calls'],'Forward-call allowance exhausted')
        state['forward_calls']+=1;self.save();view=request['view'];mode=request['mode']
        require(view in ('original','edited','both') and mode in ('generate','probe'),'Unsupported view/mode')
        views=['edited','original'] if view=='both' else [view];policy=self.policy
        if mode=='generate':
            require(request['texts'] is None and isinstance(request['ids'],list) and 1<=len(request['ids'])<=2
                and len(set(request['ids']))==len(request['ids']) and all(i in {'dev-'+str(n) for n in range(8)} for i in request['ids']),'Only development IDs, at most two')
            cases=[self.by_id[i] for i in request['ids']]
        else:
            require(request['ids'] is None and isinstance(request['texts'],list) and 1<=len(request['texts'])<=4
                and all(isinstance(t,str) and 0<len(t)<=32000 for t in request['texts']),'Probe text limits')
            from tokenizers import Tokenizer
            tokenizer=Tokenizer.from_file(str(Path(self.plan['tokenizers']['target_tokenizer']['path'])/'tokenizer.json'))
            cases=[{'id':'probe-'+str(n),'rendered_prompt':t,'input_ids':tokenizer.encode(t,add_special_tokens=False).ids} for n,t in enumerate(request['texts'])]
            require(all(0<len(c['input_ids'])<=4096 for c in cases),'Probe input token limit')
        results={}
        for selected in views:
            self.worker_deadline.remaining();model=self.plan['models']['original_target'] if selected=='original' else self.snapshot(policy,self.root/self.arm/'snapshots'/uuid.uuid4().hex)
            try:
                if mode=='generate':
                    before=self.arm_target_cost();remaining=self.plan['limits']['development_generated_tokens']-before
                    new_cases=cases if selected=='edited' else [c for c in cases if c['id'] not in self.baseline_cache]
                    require(remaining>=len(new_cases)*self.plan.get('design',{}).get('target_output_tokens',32768),'Not enough remaining sampled tokens for this batch')
                    cached_ids=[i for i in request['ids'] if i in self.baseline_cache] if selected=='original' else []
                    rows=self.baseline(request['ids']) if selected=='original' else self.inference(mode,model,cases,remaining=remaining)
                    state['sampled_tokens']+=sum(r['generated_tokens'] for r in rows if r['id'] not in cached_ids)
                    policy.evaluation_context={'settings_sha256':getattr(self,'settings_sha256',None),
                        'request_bindings':sorted({r.get('request_sha256','legacy-unbound') for r in rows}),
                        'outcomes':self.public(rows),'cached_ids':cached_ids}
                    results['candidate' if selected=='edited' else 'original']={
                        'receipt':evaluated_receipt(policy,selected,model,mode,request['ids'],cached_ids),'outcomes':self.public(rows)}
                    if selected=='edited':policy.tested_revision=policy.revision
                else:
                    rows=self.inference(mode,model,cases,remaining=0)
                    policy.evaluation_context={'settings_sha256':self.settings_sha256,'probe_only':True}
                    results['candidate' if selected=='edited' else 'original']={
                        'receipt':evaluated_receipt(policy,selected,model,mode,[c['id'] for c in cases]),
                        'observations':[observation_summary(r,policy.observation(r['observation_path'])) for r in rows]}
                    if selected=='edited':policy.inspected_revision=policy.revision
            finally:
                if selected=='edited':self.discard_snapshot(policy,model)
        policy.event('forward',{'call':state['forward_calls'],'mode':mode,'views':views,'result':results});self.save();return results

    def arm_target_cost(self):return self.state['arms'][self.arm]['sampled_tokens']

    def render(self,messages,tokenizer):
        removed=0
        def text():return '<|im_start|>system\n'+getattr(self,'brief',BRIEF)+'<|im_end|>\n'+''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n' for m in messages)+'<|im_start|>assistant\n<think>\n'
        rendered=text();ids=tokenizer.encode(rendered,add_special_tokens=False).ids
        while len(ids)>24576 and len(messages)>3:
            removed+=len(messages[1]['content'])+len(messages[2]['content']);del messages[1:3]
            rendered=text();ids=tokenizer.encode(rendered,add_special_tokens=False).ids
        require(len(ids)<=24576,'Editor context allowance exceeded; no instruction trimming')
        if removed:self.policy.event('context_omission',{'removed_characters':removed,'kernel_state_preserved':True})
        return rendered,ids

    def editor_arm(self,arm,initial):
        from tokenizers import Tokenizer
        folder=self.root/arm;folder.mkdir();(folder/'snapshots').mkdir();self.arm=arm
        state={'status':'running','calls':0,'forward_calls':0,'sampled_tokens':0,'editor_tokens':0,
            'clean_terminal':False,'terminal_cell_error':None,'recoverable_errors':[]};self.state['arms'][arm]=state;self.state['phase']=arm;self.save()
        self.worker_deadline=self.deadline.child(self.plan['limits']['arm_seconds'])
        if hasattr(self,'development_deadline'):
            self.worker_deadline=Deadline(end=min(self.worker_deadline.end,self.development_deadline.end))
        metadata={'architecture':'Qwen3.5 0.8B','active_layers':24,'hidden_size':1024,'ffn_size':3584,'attention':'Hybrid Gated DeltaNet / full attention; inspect tensor names/shapes',
            'target':'Original unmodified BF16 weights represented as F32 GGUF; saved edits are BF16-rounded','limits':self.plan['limits']}
        broker=PreciseTensorPolicy if self.plan.get('numeric_policy')=='precise-v2' else TensorPolicy
        self.policy=broker(self.plan['models']['original_target'],self.records,folder/'policy',metadata,forward=self.forward)
        visible=[{'id':c['id'],'problem':c['problem'],'answer':self.golds[c['id']]} for c in self.cases if c['split']=='dev']
        messages=[{'role':'user','content':json.dumps({'development':visible,'shared_initial_baseline':self.public(initial)},ensure_ascii=True)}]
        contract=self.plan.get('design',{}).get('explicit_contract',False)
        if contract:
            from tensor_workspace_contract import resource_feedback
            messages.append({'role':'user','content':json.dumps({'remaining_resources':resource_feedback(self,state)})})
        tokenizer=Tokenizer.from_file(str(Path(self.plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'));self.vm=None
        try:
            self.vm=TensorVM(self.project,self.plan['image'],folder/'vm.json',self.worker_deadline)
            for turn in range(self.plan['limits']['editor_calls']):
                self.worker_deadline.remaining();state['calls']=turn+1;prompt,ids=self.render(messages,tokenizer)
                require(state['editor_tokens']+8192<=self.plan['limits']['editor_tokens'],'Editor sampled-token allowance exhausted')
                seeds=self.plan.get('design',{}).get('editor_seed_sequence')
                case={'id':'editor-'+str(turn),'rendered_prompt':prompt,'input_ids':ids,'rng_seed':seeds[turn] if seeds is not None else 2026110310+turn}
                response=self.inference('editor',getattr(self,'teacher_models',self.plan['models'])[arm],[case],remaining=min(8192,self.plan['limits']['editor_tokens']-state['editor_tokens']))[0]
                state['editor_tokens']+=response['generated_tokens']
                try:
                    if contract:require(response['finish_reason']=='eos','Response truncated; no code executed')
                    code,final=code_cell(response['raw_text'])
                except ValueError as error:
                    messages.extend([{'role':'assistant','content':response['raw_text'].rsplit('</think>',1)[-1][-8000:]},
                        {'role':'user','content':str(error)+'. No code executed. Return one complete Python cell.'}])
                    self.policy.event('format_rejected',{'turn':turn,'error':str(error)})
                    state['recoverable_errors'].append({'turn':turn,'kind':'format_or_truncation','error':str(error)})
                    state['terminal_cell_error']=str(error)
                else:
                    self.policy.event('cell_source',{'turn':turn,'code':code})
                    try:outcome=self.vm.execute(code,self.policy,seconds=self.plan['limits']['cell_seconds'])
                    except CellAllowanceExceeded as error:
                        state.update(status='model_cell_allowance',error=str(error),terminal_cell_error=str(error),patch=self.policy.status());break
                    state['terminal_cell_error']=outcome.get('error')
                    if outcome.get('error'):state['recoverable_errors'].append({'turn':turn,'kind':'cell','error':outcome['error']})
                    messages.extend([{'role':'assistant','content':final},{'role':'user','content':json.dumps(outcome,ensure_ascii=True)}])
                    atomic(folder/('turn-'+str(turn)+'.json'),{'code':code,'outcome':outcome})
                if contract:messages.append({'role':'user','content':json.dumps({'remaining_resources':resource_feedback(self,state)})})
                self.save()
                if self.policy.submitted:
                    state.update(status='clean_submitted' if not state['terminal_cell_error'] else 'submission_cell_error',
                        clean_terminal=not bool(state['terminal_cell_error']))
                    break
            if state['status']=='running':state['status']='turn_allowance_exhausted'
            state.update(submitted=self.policy.submitted,patch=self.policy.status())
        except (TimeoutError,ValueError) as error:
            state.update(status='bounded_stop',error=type(error).__name__+': '+str(error),patch=self.policy.status())
        finally:
            if self.vm:self.vm.close();self.vm=None
            atomic(folder/'FROZEN.json',{'state':state,'edits':self.policy.edits,'base':self.policy.base})
            self.save()

    def qualification(self):
        self.state['phase']='independent_qualification';self.worker_deadline=self.deadline;self.save()
        hidden=[c for c in self.cases if c['split']!='dev'];baseline=[]
        results={'baseline':baseline}
        for start in range(0,len(hidden),2):
            baseline.extend(self.baseline([c['id'] for c in hidden[start:start+2]]));atomic(self.root/'independent-results.json',results)
        for arm in self.plan['design']['arms']:
            frozen=read(self.root/arm/'FROZEN.json');policy=TensorPolicy(self.plan['models']['original_target'],self.records,self.root/arm/'qualification-policy',{},forward=None)
            policy.edits=frozen['edits'];rows=[];results[arm]=rows;model=self.snapshot(policy,self.root/arm/'snapshots'/uuid.uuid4().hex)
            try:
                for start in range(0,len(hidden),2):
                    remaining=self.plan['limits']['qualification_generated_tokens']-sum(r['generated_tokens'] for v in results.values() for r in v)-sum(r['generated_tokens'] for r in rows)
                    require(remaining>=len(hidden[start:start+2])*self.plan['design'].get('target_output_tokens',32768),'Qualification token budget exhausted')
                    rows.extend(self.inference('generate',model,hidden[start:start+2],remaining=remaining))
                    atomic(self.root/'independent-results.json',results)
            finally:self.discard_snapshot(policy,model)
            results[arm]=rows;atomic(self.root/'independent-results.json',results)
        return results

    def run(self):
        result={'status':'running'}
        try:
            # Minimal trusted native preflight: raw-logit observation plus a one-step editor cell.
            target_case={'id':'probe-0','rendered_prompt':'Hello','input_ids':None}
            from tokenizers import Tokenizer
            tok=Tokenizer.from_file(str(Path(self.plan['tokenizers']['target_tokenizer']['path'])/'tokenizer.json'))
            target_case['input_ids']=tok.encode('Hello',add_special_tokens=False).ids
            self.state['phase']='native_preflight';self.save();self.inference('probe',self.plan['models']['original_target'],[target_case],remaining=0)
            initial=self.baseline(self.plan['design']['shared_initial_baseline_ids'])
            for arm in self.plan['design']['arms']:self.editor_arm(arm,initial)
            checked=self.qualification();result={'status':'completed','independent':checked,'arms':self.state['arms']}
        except BaseException as error:
            result={'status':'stopped','error':type(error).__name__+': '+str(error),'arms':self.state['arms']}
        finally:
            if self.vm:self.vm.close();self.vm=None
            self.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));self.save()
            atomic(self.root/'RESULT.json',result)
            from tensor_workspace_report import report
            report(self.root)


def main(root):
    root=Path(root).resolve()
    with exclusive(root):
        require(not (root/'runner.json').exists(),'Never restart a published run implicitly')
        Study(root).run()


if __name__=='__main__':main(sys.argv[1])
