"""Reviewed AP W&T overnight study. Frozen, single-use, no shared-GPU opt-in.

All model-authored Python executes through TensorVM, never in this host process.
"""
import copy
import ctypes
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from lora6k_state import atomic, read, sha, identity, exclusive
from tensor_workspace_code_diagnostic import score, BRIEF as DIAGNOSTIC_BRIEF
from tensor_workspace_precision import PreciseTensorPolicy, GUIDANCE
from tensor_workspace_study import Study, BRIEF, code_cell
from tensor_workspace_vm import TensorVM
from tensor_workspace_errors import InfrastructureStop, GlobalDeadlineStop, CellAllowanceExceeded
from weight_editor_runtime import Deadline, require, check_files

CAPS={'diagnostic_cells':131072,'diagnostic_recovery':65536,'pilot_editor':49152,
      'pilot_feedback':32768,'pilot_baseline':16384,'pilot_confirmation':65536,'pilot_preservation':32768}
TOTAL=397312
AUTHORIZATION="PUBLIC ARCHIVE: no execution permission is conveyed; create a new owner-approved protocol."


@contextmanager
def desktop_lease(project):
    """Cross-directory file lease plus a Windows named research-GPU mutex."""
    folder=Path(project)/'.data/apwt-desktop-lease';folder.mkdir(exist_ok=True)
    handle=None;dll=None
    with exclusive(folder):
        if os.name=='nt':
            from ctypes import wintypes as w
            dll=ctypes.WinDLL('kernel32',use_last_error=True)
            dll.CreateMutexW.argtypes=[ctypes.c_void_p,w.BOOL,w.LPCWSTR];dll.CreateMutexW.restype=w.HANDLE
            dll.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];dll.WaitForSingleObject.restype=w.DWORD
            dll.ReleaseMutex.argtypes=[w.HANDLE];dll.CloseHandle.argtypes=[w.HANDLE]
            handle=dll.CreateMutexW(None,False,'Local\\Proteus-Research-GPU-0')
            require(bool(handle),'Cannot create desktop research lease')
            wait=dll.WaitForSingleObject(handle,0)
            if wait not in (0,128):
                dll.CloseHandle(handle);raise ValueError('Desktop research GPU already leased')
        try:
            atomic(folder/'owner.json',{'pid':os.getpid(),'computer':os.environ.get('COMPUTERNAME'),
                'status':'held','scope':'W&T research desktop','started_unix':time.time()})
            yield
        finally:
            atomic(folder/'owner.json',{'pid':os.getpid(),'status':'released','ended_unix':time.time()})
            if handle:dll.ReleaseMutex(handle);dll.CloseHandle(handle)


def admission(project,folder):
    from lora6k_supervisor import ownership,snapshot
    from weight_editor_owned import admission as admit
    folder=Path(folder);folder.mkdir(exist_ok=True)
    from memory_availability_policy import config as memory_config,observe as memory_observe
    memory_policy=memory_config(folder.parent) if (folder.parent/'manifest.json').exists() else None
    samples=[]
    deadline=Deadline(60)
    def observe(timeout):
        if memory_policy:
            row=memory_observe(folder.parent,folder,deadline.remaining,stage='admission',context={'phase':'initial_study_admission'})
            samples.append(row);atomic(folder/'admission.json',samples);return row
        owners=ownership(remaining=deadline.remaining,
            evidence=lambda row:atomic(folder/'ownership'/(row['observation_id']+'-'+row['stage']+'.json'),row),
            context={'phase':'initial_study_admission'})
        host=snapshot(timeout=min(20,deadline.remaining()))
        raw=subprocess.check_output(['nvidia-smi','--id=0','--query-gpu=memory.free,utilization.gpu',
            '--format=csv,noheader,nounits'],text=True,timeout=timeout)
        free,util=[int(x.strip()) for x in raw.split(',')]
        row={**host,'free_vram_mib':free,'utilization':util,'disk_bytes':shutil.disk_usage(project).free,'ownership':owners}
        samples.append(row);atomic(folder/'admission.json',samples);return row
    admit(observe,deadline,availability_only=bool(memory_policy))
    return samples


def diagnostic_cases():
    rows=[]
    for split,block,index,label in [('dev',0,2055,'measured'),('confirmation',6,6151,'retained')]:
        a=f'blk.{block}.attn_norm.weight';b=f'blk.{block+1}.attn_norm.weight';m=f'blk.{block}.attn_qkv.weight'
        tasks={
            'restore_one':f'Restore ONLY {a} to the immutable original. Preserve the saved edits in {b} and {m} exactly. Generate dev-0 and dev-1 with the final candidate and submit().',
            'restore_checkpoint':f'Restore the complete checkpoint {label!r}, which predates later bad changes. Generate dev-0 and dev-1 with the restored candidate and submit().',
            'test_saved':'Generate dev-0 and dev-1 with all currently saved edits and display the results. Do not write, undo, restore, or submit. Do not infer answer correctness from fixture stubs.',
            'one_weight':f'In matrix {m}, set flattened index {index} to 0.25. Preserve all other values of all tensors exactly. Generate dev-0 and dev-1 with the final candidate, then submit().'}
        for kind,task in tasks.items():
            rows.append({'id':split+'-'+kind.replace('_','-'),'split':split,'kind':kind,'block':block,'index':index,'label':label,
                'task':task,'submission_policy':'forbidden' if kind=='test_saved' else 'required',
                'write_policy':'forbidden' if kind=='test_saved' else 'allowed'})
    return rows


def fixture(folder,case,*,faithful=True,recovery=False):
    import numpy as np
    folder=Path(folder);folder.mkdir(exist_ok=False)
    block=case['block'];names=[f'blk.{block}.attn_norm.weight',f'blk.{block+1}.attn_norm.weight',f'blk.{block}.attn_qkv.weight']
    shapes=[[1024],[1024],[6144,1024]] if faithful else [[16],[16],[16,8]]
    arrays=[np.linspace(case.get('base_start',.1001),case.get('base_end',1.0999),int(np.prod(s)),dtype='<f4').reshape(s) for s in shapes]
    source=folder/'source.bin';records={};offset=0
    with source.open('wb') as out:
        for n,a,s in zip(names,arrays,shapes):
            out.write(a.tobytes());records[n]={'shape':s,'offset':offset,'bytes':a.nbytes,'editable':True};offset+=a.nbytes
    requests=[];p=None;good=None
    def forward(r):
        require(r['mode']=='generate' and r['view'] in ('edited','original','both') and r['texts'] is None
            and isinstance(r['ids'],list) and 1<=len(r['ids'])<=2 and len(set(r['ids']))==len(r['ids'])
            and set(r['ids'])<={'dev-0','dev-1'},'Only fixture development generation IDs')
        from tensor_workspace_feedback import evaluated_receipt
        binding=identity({'request':r,'candidate_id':p.candidate_state()['candidate_id'],'sequence':len(requests)})
        request={**copy.deepcopy(r),'candidate_id':p.candidate_state()['candidate_id'],'request_sha256':binding}
        result={}
        for view in (['edited','original'] if r['view']=='both' else [r['view']]):
            exact=all(p.array(n,edited=view=='edited').tobytes()==raw for n,raw in good.items()) if good else None
            outcomes=[{'id':i,'status':'synthetic_feedback' if recovery else 'protocol_stub','correct':exact if recovery else None,
                'generated_tokens':0,'fixture_only':True} for i in r['ids']]
            p.evaluation_context={'settings_sha256':'synthetic-v2','request_bindings':[binding],'outcomes':outcomes,
                'fixture_only':True,'no_target_inference':True}
            model={'sha256':hashlib.sha256(b''.join(p.array(n,edited=view=='edited').tobytes() for n in names)).hexdigest()}
            result['candidate' if view=='edited' else 'original']={'receipt':evaluated_receipt(p,view,model,'generate',r['ids']),
                'outcomes':outcomes,'fixture_only':True,'no_target_inference':True}
        requests.append(request);return result
    p=PreciseTensorPolicy({'path':str(source),'sha256':sha(source)},records,folder/'policy',
        {'fixture_only':True,'shapes':shapes,'required_ids':['dev-0','dev-1']},forward=forward)
    def fixed(name,index,value,label):
        a=p.array(name);a.flat[index]=value;path=folder/(label+'.f32');a.tofile(path)
        p.edits[name]={'name':name,'path':str(path),'sha256':sha(path),'shape':list(a.shape)};p.revision+=1
    initial=case.get('initial_values',[.5,.75,.625])
    fixed(names[0],0,initial[0],'saved-a');fixed(names[1],1,initial[1],'saved-b');fixed(names[2],2,initial[2],'saved-m')
    expected={n:p.array(n).tobytes() for n in names};good=copy.deepcopy(expected)
    if case['kind']=='restore_one':expected[names[0]]=arrays[0].tobytes()
    elif case['kind']=='restore_checkpoint':
        bad=case.get('bad_values',[.875,.375])
        p.handle({'op':'checkpoint','label':case['label']});fixed(names[0],3,bad[0],'later-a');fixed(names[2],4,bad[1],'later-m')
    elif case['kind']=='one_weight':
        a=p.array(names[2]);a.flat[case['index']]=case.get('edit_value',.25);expected[names[2]]=a.tobytes()
    p.task_start=len(p.operation_history)
    return p,expected,requests,names,fixed


def positive_cell(c,n):
    operation={'restore_one':f'undo_edit({n[0]!r})',
        'restore_checkpoint':f'restore_checkpoint({c["label"]!r})','test_saved':'',
        'one_weight':f'w=load_tensor({n[2]!r})\nw.flat[{c["index"]}]=.25\nsave_edit({n[2]!r},w)'}[c['kind']]
    return operation+"\nprint(test_candidate(['dev-0']))\nprint(test_candidate(['dev-1']))"+('\nsubmit()' if c['submission_policy']=='required' else '')


def recovery_grade(p,expected,requests,outcome,perturbed):
    graded=score(p,expected,requests,outcome,submission_policy='required')
    observed_worse=any(any(o.get('correct') is False for o in r.get('outcomes',[]))
        for r in p.receipt_ledger if r['view']=='edited')
    return {**graded,'correct':bool(graded['correct'] and perturbed and observed_worse),
        'harness_introduced_worse_candidate':perturbed,'worse_candidate_measured':observed_worse}


def calibrate(project,folder,image):
    folder=Path(folder);folder.mkdir(exist_ok=False);rows=[];vm=None
    try:
        vm=TensorVM(project,image,folder/'vm.json',Deadline(600))
        isolation=vm.execute("import os\nfrom pathlib import Path\nassert os.getuid()==1000\nassert sorted(p.name for p in Path('/sys/class/net').iterdir())==['lo']\nassert not Path('/mnt/host').exists()\nassert not any(k.lower().endswith('api_key') for k in os.environ)\nprint('isolated')",None)
        require(isolation['error'] is None,'VM isolation control failed');rows.append({'id':'isolation','outcome':isolation})
        for c in diagnostic_cases()[:4]:
            p,expected,requests,n,_=fixture(folder/c['id'],c)
            outcome=vm.execute(positive_cell(c,n),p)
            result=score(p,expected,requests,outcome,submission_policy=c['submission_policy'],write_policy=c['write_policy'])
            require(result['correct'],'VM positive failed: '+str(result));rows.append({'id':c['id'],**result})
        # The precise broker used by Study.editor_arm is exercised through this VM.
        c=diagnostic_cases()[2];p,expected,requests,n,fixed=fixture(folder/'recovery',c,recovery=True)
        a=vm.execute("print(test_candidate(['dev-0','dev-1']))\nsave_checkpoint('A')",p)
        require(not a['error'],'Recovery checkpoint control failed');fixed(n[0],5,.9375,'harness-worse')
        b=vm.execute("print(test_candidate(['dev-0','dev-1']))\nrestore_checkpoint('A')\nprint(test_candidate(['dev-0','dev-1']))\nsubmit()",p)
        result=score(p,expected,requests,b,submission_policy='required')
        require(result['correct'] and len(p.receipt_ledger)==3,'Recovery/ledger control failed')
        rows.append({'id':'feedback-recovery','score':result,'harness_introduced_worse_candidate':True})
        try:vm.execute('while True: pass',p,seconds=1)
        except CellAllowanceExceeded:rows.append({'id':'cell-allowance','classified':True})
        else:raise ValueError('Cell allowance was not enforced')
        require(read(folder/'vm.json')['owned_vm_closed'],'Calibration VM did not close')
        vm=TensorVM(project,image,folder/'global-vm.json',Deadline(120))
        vm.deadline=Deadline(.25)
        try:vm.execute('while True: pass',p,seconds=20)
        except GlobalDeadlineStop:rows.append({'id':'global-deadline','classified':True})
        else:raise ValueError('Global deadline was not classified')
        require(read(folder/'global-vm.json')['owned_vm_closed'],'Global-stop VM did not close')
        vm=TensorVM(project,image,folder/'transport-vm.json',Deadline(120));vm.process.kill();vm.process.wait(timeout=5)
        try:vm.execute('print(1)',p)
        except InfrastructureStop:rows.append({'id':'transport-failure','classified':True})
        else:raise ValueError('Transport failure was not classified')
        require(read(folder/'transport-vm.json')['owned_vm_closed'],'Transport-stop VM did not close')
        atomic(folder/'RESULT.json',{'status':'passed','controls':rows,'no_model_inference':True,'vm_closed':True,
            'real_pilot_policy':'PreciseTensorPolicy','historical_artifacts_unchanged':True})
    finally:
        if vm:vm.close()


def prepare(project,root,calibration):
    from tokenizers import Tokenizer
    import pyarrow.parquet as pq
    from weight_editor_prepare import normalized
    from weight_repair_protocol import extract_answer
    project,root,calibration=map(lambda x:Path(x).resolve(),(project,root,calibration))
    require(not root.exists(),'Never replay an overnight publication')
    old=read(project/'.data/tensor-code-diagnostic-20261104-v5/manifest.json')
    require(read(calibration/'RESULT.json')['status']=='passed','Calibration required before freeze')
    root.mkdir();(root/'code').mkdir();(root/'requests').mkdir();(root/'runs').mkdir()
    modules=set(old['code'])|{'tensor_workspace_errors.py','tensor_workspace_overnight.py'}
    for name in modules:
        source=project/('controller' if name=='windows_job.py' else 'evaluations')/name
        shutil.copyfile(source,root/'code'/name)
    prior=set();exclusions={}
    def collect(v):
        if isinstance(v,dict):
            if isinstance(v.get('problem'),str):prior.add(normalized(v['problem']))
            for x in v.values():collect(x)
        elif isinstance(v,list):
            for x in v:collect(x)
    for p in (project/'.data').rglob('*inputs*.json'):
        if p.is_file() and p.stat().st_size<=5*1024**2:
            collect(read(p));exclusions[str(p.relative_to(project))]=sha(p)
    assets=project/'.data/weight-repair-20261102'
    train_path=assets/'gpu-readiness-001/math-train.parquet';bench_path=assets/'acquisition-001/assets/dataset/math500.jsonl'
    source_plan=read(project/'.data/manual4b-localprojection-pair-20261103/manifest.json')['dataset_sources']
    require(sha(train_path)==source_plan['train_sha256'] and sha(bench_path)==source_plan['benchmark_sha256'],'Dataset checksum changed')
    bench=[json.loads(x) for x in bench_path.read_text(encoding='utf8').splitlines()]
    bench_keys={normalized(r['problem']) for r in bench}
    eligible={}
    for i,r in enumerate(pq.read_table(train_path).to_pylist()):
        key=normalized(r['problem'])
        if key not in prior and key not in bench_keys and extract_answer(r['solution']):eligible.setdefault(key,(i,r))
    selected=random.Random(2026110401).sample(list(eligible.values()),6)
    preservation=random.Random(2026110402).sample([r for r in bench if normalized(r['problem']) not in prior],2)
    tok=Tokenizer.from_file(str(Path(old['tokenizers']['target_tokenizer']['path'])/'tokenizer.json'))
    cases=[];golds={}
    for split,items in [('dev',selected[:2]),('confirmation',selected[2:]),('preservation',[(r['unique_id'],r) for r in preservation])]:
        for number,(source_id,row) in enumerate(items):
            name=split+'-'+str(number);prompt='<|im_start|>user\n'+row['problem']+'\n'+old['target_protocol']['instruction']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
            ids=tok.encode(prompt,add_special_tokens=False).ids;require(len(ids)+8192<=34816,'Frozen context exceeded')
            cases.append({'id':name,'split':split,'source_id':source_id,'problem':row['problem'],'rendered_prompt':prompt,'input_ids':ids,
                'rng_seed':int.from_bytes(hashlib.sha256(('apwt-overnight:'+name).encode()).digest()[:4],'little')})
            golds[name]=row['answer'] if split=='preservation' else extract_answer(row['solution'])
    editor_tok=Tokenizer.from_file(str(Path(old['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
    diagnostics=diagnostic_cases()
    for c in diagnostics:
        c['rendered_prompt']='<|im_start|>system\n'+DIAGNOSTIC_BRIEF+'<|im_end|>\n<|im_start|>user\n'+c['task']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
        c['input_ids']=editor_tok.encode(c['rendered_prompt'],add_special_tokens=False).ids
        c['rng_seed']=int.from_bytes(hashlib.sha256(('apwt-faithful:'+c['id']).encode()).digest()[:4],'little')
    atomic(root/'inputs.json',{'cases':cases});atomic(root/'hidden-golds.json',golds)
    shutil.copyfile(project/'.data/manual4b-targeted-shared-gpu-20261103-v4/tensor-catalog.json',root/'tensor-catalog.json')
    atomic(root/'diagnostic-inputs.json',{'cases':diagnostics});atomic(root/'prior-exposure-inventory.json',exclusions)
    atomic(root/'AUTHORIZATION.json',{'user_instruction':AUTHORIZATION,'source_thread_id':'REDACTED-PRIVATE-THREAD',
        'review':'Critic approved bounded overnight repairs, paired diagnostic and conditional single-editor 8K pilot',
        'explicit_user_authorization':False,'combined_sampled_token_ceiling':TOTAL,'new_training':False})
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','models','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol')}
    plan.update(scope='Reviewed bounded diagnostic and conditional single-editor 8K feasibility pilot',overnight=True,numeric_policy='precise-v2',
        code={p.name:sha(p) for p in (root/'code').iterdir()},controller_files={str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')},
        data={name:sha(root/name) for name in ('inputs.json','hidden-golds.json','tensor-catalog.json','diagnostic-inputs.json','prior-exposure-inventory.json','AUTHORIZATION.json')},
        budget_categories=CAPS,combined_sampled_token_ceiling=TOTAL,interruption_reserve=4096,
        limits={'total_seconds':5400,'arm_seconds':1800,'editor_calls':6,'forward_calls':4,'editor_tokens':49152,
            'development_generated_tokens':32768,'qualification_generated_tokens':98304,'cell_seconds':60,
            'tensor_bytes':67108864,'patch_bytes':536870912,'transfer_bytes':2147483648},
        design={'arms':['unchanged','targeted'],'shared_initial_baseline_ids':['dev-0','dev-1'],'target_output_tokens':8192,'editor_output_tokens':8192,
            'vm_preflight_receipt':str(calibration/'RESULT.json'),'vm_preflight_sha256':sha(calibration/'RESULT.json'),
            'editor_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'thinking':True},
            'target_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'generated_only_presence':1.5},
            'diagnostic_seconds':5400,'pilot_seconds':5400,'pilot_development_seconds':1800,'reserved_confirmation_seconds':3600,
            'pilot_selection':'unchanged if all eight tasks and recovery pass; otherwise targeted if it passes; otherwise stop',
            'entry':'baseline not both correct; at least one complete nonempty EOS response; candidate submitted, fully tested, development gain and no loss',
            'positive':'confirmation gain with no confirmation/preservation loss and at least one baseline-correct preservation case',
            'researcher_full_report_received':False,'shared_gpu_activation':False})
    plan['target_protocol']['max_new_tokens']=8192
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\np=json.loads((r/'manifest.json').read_text())\nsys.path.insert(0,p['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_overnight import main\nmain(r)\n",encoding='utf8')
    return {'root':str(root),'manifest_sha256':identity(plan)}


class OvernightStudy(Study):
    def __init__(self,root):
        super().__init__(root)
        self.categories={};self.budget_category=None;self.generation_calls=0;self.probe_calls=0
        if self.plan.get('continuation'):
            prior=Path(self.plan['continuation']['root']);check_files(prior,self.plan['continuation']['files'])
            remaining=self.plan['continuation']['original_diagnostic_deadline_unix']-time.time()
            require(remaining>0,'Original diagnostic deadline exhausted')
            self.deadline=Deadline(remaining);self.worker_deadline=self.deadline
            inherited=read(prior/'usage.json');previous=read(prior/'BUDGET.json')
            atomic(self.root/'usage.json',{'phases':{'prior:'+k:v for k,v in inherited['phases'].items()},
                'charged_tokens':inherited['charged_tokens'],'measurement_complete':inherited['measurement_complete']})
            self.categories={'prior:'+k:v for k,v in previous['phase_categories'].items()}
            atomic(self.root/'diagnostic-results.json',read(prior/'diagnostic-results.json'))
        self.brief=BRIEF.replace('32K output allowance','8192-token output allowance').replace(
            'You have 48 editor turns, 8 forward calls, 524288 sampled development tokens and two hours total.',
            'You have 6 editor turns, 2 candidate-generation calls (at most 4 answers total), 2 single-text candidate probes, 32768 sampled development tokens and 30 minutes total.')+GUIDANCE

    def reconcile(self):
        usage=read(self.root/'usage.json') if (self.root/'usage.json').exists() else {'phases':{},'charged_tokens':0}
        charged={k:0 for k in CAPS}
        for name,row in usage['phases'].items():charged[self.categories[name]]+=row['charged_tokens']
        require(all(charged[k]<=CAPS[k] for k in CAPS) and usage['charged_tokens']<=TOTAL,'Reviewed token ceiling exceeded')
        result={'categories':charged,'phase_categories':self.categories,'charged_tokens':usage['charged_tokens'],
            'ceiling':TOTAL,'uncertain_tokens_upper_bound':sum(r['uncertain_tokens_upper_bound'] for r in usage['phases'].values()),
            'cached_baselines_charged_again':False}
        atomic(self.root/'BUDGET.json',result);return result

    def inference(self,mode,model,cases,*,remaining=1048576):
        category=self.budget_category;require(category in CAPS,'Missing physical inference budget category')
        output=8192;allowance=len(cases)*output if mode!='probe' else 0
        charged=self.reconcile()['categories'][category]
        require(charged+allowance<=CAPS[category],'Stage sampled-token allowance exhausted')
        phase='call-'+str(self.calls+1).zfill(3);self.categories[phase]=category;self.reconcile()
        try:rows=super().inference(mode,model,cases,remaining=allowance)
        finally:self.reconcile()
        if mode=='generate':
            for row in rows:
                response=read(row['response_file']);row['reference_correct']=row['correct']
                row['closed_thinking']='</think>' in response['raw_text']
                row['correct']=bool(row['correct'] and row['finish_reason']=='eos' and row['closed_thinking'])
            if rows:atomic(Path(rows[0]['response_file']).parent/'checked.json',rows)
        return rows

    def forward(self,request):
        require(request['view'] in ('edited','both'),'Use the supplied immutable baseline, not additional original-only calls')
        if request['mode']=='generate':
            require(self.generation_calls<2,'Two candidate-generation calls exhausted');self.generation_calls+=1
            require(set(request.get('ids') or [])<={'dev-0','dev-1'},'Only the two frozen development IDs')
        else:
            require(self.probe_calls<2 and request['view']=='edited' and len(request.get('texts') or [])==1,'Two single-text candidate probes maximum')
            self.probe_calls+=1
        previous=self.budget_category;self.budget_category='pilot_feedback'
        try:return super().forward(request)
        finally:self.budget_category=previous

    def diagnostic(self):
        cases=read(self.root/'diagnostic-inputs.json')['cases']
        results=read(self.root/'diagnostic-results.json') if self.plan.get('continuation') else {}
        for arm in self.plan['design']['arms']:
            self.arm=arm;results.setdefault(arm,[])
            completed_ids={r['id'] for r in results[arm]}
            for c in cases:
                if c['id'] in completed_ids:continue
                self.state.update(phase='diagnostic_'+c['split'],arm=arm,case=c['id']);self.save()
                self.budget_category='diagnostic_cells'
                response=self.inference('editor',self.plan['models'][arm],[c])[0]
                directory=self.root/('diagnostic-'+arm)/c['id'];directory.parent.mkdir(exist_ok=True)
                p,expected,requests,n,_=fixture(directory,c);vm=None;row={'id':c['id'],'split':c['split'],'generated_tokens':response['generated_tokens']}
                try:
                    require(response['finish_reason']=='eos','Editor generation truncated; no code executed')
                    code,_=code_cell(response['raw_text'])
                    try:vm=TensorVM(self.project,self.plan['image'],directory/'vm.json',self.deadline.child(180))
                    except Exception as exc:raise InfrastructureStop('VM startup: '+str(exc)) from exc
                    outcome=vm.execute(code,p)
                    row.update(score(p,expected,requests,outcome,submission_policy=c['submission_policy'],write_policy=c['write_policy']))
                except (ValueError,CellAllowanceExceeded) as error:
                    row.update(correct=False,error=type(error).__name__+': '+str(error),failure_stage='model_cell_allowance' if isinstance(error,CellAllowanceExceeded) else 'model_format')
                except InfrastructureStop as error:
                    row.update(correct=None,error=type(error).__name__+': '+str(error),failure_stage='infrastructure_stop');raise
                finally:
                    if vm:vm.close()
                    atomic(directory/'EFFECT.json',{'score':row,'requests':requests,'receipts':p.receipt_ledger,'operations':p.operation_history,'final':p.status()})
                results[arm].append(row);atomic(self.root/'diagnostic-results.json',results)
            if 'recovery' not in completed_ids:
                recovery=self.recovery(arm);atomic(self.root/('recovery-'+arm)/'RESULT.json',recovery)
                results[arm].append({'id':'recovery',**recovery});atomic(self.root/'diagnostic-results.json',results)
        eligible=[a for a in self.plan['design']['arms'] if len(results[a])==9 and all(r.get('correct') for r in results[a])]
        selected='unchanged' if 'unchanged' in eligible else 'targeted' if 'targeted' in eligible else None
        atomic(self.root/'DIAGNOSTIC-GATE.json',{'eligible':eligible,'selected':selected,'rule':self.plan['design']['pilot_selection']})
        return selected

    def recovery(self,arm):
        from tokenizers import Tokenizer
        c=diagnostic_cases()[2];directory=self.root/('recovery-'+arm)
        p,expected,requests,n,fixed=fixture(directory,c,recovery=True);vm=None;messages=[];perturbed=False
        task=("This is a four-turn synthetic feedback/state-management episode, not real math. Test the current candidate on dev-0 and dev-1 and save a named checkpoint. "
            "The harness will then introduce a later perturbation. Use the returned feedback to retain the best measured state, verify it and submit within four cells. "
            "The fixture objective returns correct=True only for the starting numeric state; no new repair is requested.")
        messages.append({'role':'user','content':task});tok=Tokenizer.from_file(str(Path(self.plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
        result={'correct':False,'harness_introduced_worse_candidate':False,'turns':0}
        outcome={'error':'No completed cell'}
        try:
            try:vm=TensorVM(self.project,self.plan['image'],directory/'vm.json',self.deadline.child(600))
            except Exception as exc:raise InfrastructureStop('Recovery VM startup: '+str(exc)) from exc
            for turn in range(4):
                prompt='<|im_start|>system\n'+DIAGNOSTIC_BRIEF+'<|im_end|>\n'+''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n' for m in messages)+'<|im_start|>assistant\n<think>\n'
                case={'id':'recovery-'+arm+'-'+str(turn),'rendered_prompt':prompt,'input_ids':tok.encode(prompt,add_special_tokens=False).ids,'rng_seed':2026110410+turn}
                self.budget_category='diagnostic_recovery';self.state.update(phase='diagnostic_recovery',arm=arm);self.save()
                response=self.inference('editor',self.plan['models'][arm],[case])[0];result['turns']=turn+1
                require(response['finish_reason']=='eos','Recovery editor truncated');code,final=code_cell(response['raw_text'])
                outcome=vm.execute(code,p);atomic(directory/('turn-'+str(turn)+'.json'),{'code':code,'outcome':outcome})
                messages.extend([{'role':'assistant','content':final},{'role':'user','content':json.dumps(outcome)}])
                if outcome['error']:break
                if p.submitted:break
                if not perturbed and p.checkpoints and p.coverage(['dev-0','dev-1'])['complete']:
                    fixed(n[0],5,.9375,'harness-worse');perturbed=True
                    messages.append({'role':'user','content':'The declared harness perturbation has now been applied. Measure the later state, select using feedback, recover the preferred checkpoint, retest and submit.'})
            result.update(recovery_grade(p,expected,requests,outcome,perturbed),receipts=p.receipt_ledger,operations=p.operation_history)
        except (ValueError,CellAllowanceExceeded) as error:result['error']=type(error).__name__+': '+str(error)
        finally:
            if vm:vm.close()
            atomic(directory/'RESULT.json',result)
        return result

    def pilot(self,arm,*,deadline=None):
        self.deadline=deadline or Deadline(5400)
        self.worker_deadline=Deadline(end=min(self.deadline.end-3600,time.monotonic()+1800))
        self.development_deadline=self.worker_deadline
        self.state.update(phase='pilot_baseline',arm=arm);self.save();self.budget_category='pilot_baseline'
        initial=self.baseline(['dev-0','dev-1'])
        useful=not all(r['correct'] for r in initial) and any(r['finish_reason']=='eos' and r.get('closed_thinking',False)
            and bool(read(r['response_file'])['text'].strip()) for r in initial)
        atomic(self.root/'PILOT-ENTRY.json',{'useful_baseline_signal':useful,'baseline':initial,'frozen_rule':self.plan['design']['entry']})
        if not useful:return {'status':'baseline_gate_stopped','baseline':initial}
        self.budget_category='pilot_editor';self.editor_arm(arm,initial)
        p=self.policy;coverage=p.coverage(['dev-0','dev-1'],self.settings_sha256)
        receipts=[r for r in p.receipt_ledger if r['receipt_index'] in coverage['receipt_indexes']]
        final={o['id']:o for r in receipts for o in r.get('outcomes',[])}
        gains=[r['id'] for r in initial if not r['correct'] and final.get(r['id'],{}).get('correct')]
        losses=[r['id'] for r in initial if r['correct'] and not final.get(r['id'],{}).get('correct')]
        passed=p.submitted and bool(p.edits) and coverage['complete'] and bool(gains) and not losses
        gate={'passed':passed,'submitted':p.submitted,'candidate':p.candidate_state(),'coverage':coverage,'gains':gains,'losses':losses}
        atomic(self.root/'PILOT-DEVELOPMENT-GATE.json',gate)
        if not passed:return {'status':'development_gate_stopped','gate':gate}
        model=self.snapshot(p,self.root/arm/'snapshots/final-submitted')
        frozen={'model':model,'candidate':p.candidate_state(),'edits':p.edits,'selection':'Local-editor submit; development only','settings_sha256':self.settings_sha256}
        atomic(self.root/'FINAL-CANDIDATE.json',frozen)
        # Development cannot consume the reserved hour. No further editor calls.
        self.worker_deadline=self.deadline;results={'baseline':[],'candidate':[]}
        for split,category in [('confirmation','pilot_confirmation'),('preservation','pilot_preservation')]:
            self.budget_category=category;self.state.update(phase=category);self.save()
            cases=[c for c in self.cases if c['split']==split]
            for view,weights in [('baseline',self.plan['models']['original_target']),('candidate',model)]:
                for start in range(0,len(cases),2):
                    require(sha(model['path'])==model['sha256'],'Frozen submitted artifact changed')
                    results[view].extend(self.inference('generate',weights,cases[start:start+2]))
                    atomic(self.root/'pilot-independent-results.json',results)
        base={r['id']:r for r in results['baseline']};edited={r['id']:r for r in results['candidate']}
        gain=[i for i in base if i.startswith('confirmation-') and not base[i]['correct'] and edited[i]['correct']]
        loss=[i for i in base if base[i]['correct'] and not edited[i]['correct']]
        preserved=[i for i in base if i.startswith('preservation-') and base[i]['correct']]
        return {'status':'completed','positive_feasibility_result':bool(gain and not loss and preserved),
            'confirmation_gains':gain,'all_losses':loss,'baseline_correct_preservation':preserved,
            'claim':'Single-attempt 8K-output feasibility only; no broad capability or editor-superiority claim','candidate':frozen,'results':results}

    def run_overnight(self):
        result={'status':'running'}
        try:
            selected=self.diagnostic()
            if selected:
                admission(self.project,self.root/'pilot-admission');result=self.pilot(selected)
            else:result={'status':'diagnostic_gate_stopped','pilot_run':False,'reason':'Neither editor passed every task and recovery episode'}
        except BaseException as error:
            result={'status':'stopped','error':type(error).__name__+': '+str(error),'pilot_run':bool(self.state['arms'])}
        finally:
            if self.vm:self.vm.close();self.vm=None
            result['budget']=self.reconcile()
            recorded=read(self.root/'diagnostic-results.json') if (self.root/'diagnostic-results.json').exists() else {}
            result['diagnostic_schedule']=[{'arm':a,'id':name,'result':next((r for r in recorded.get(a,[]) if r['id']==name),
                {'status':'unexecuted','reason':'Study stopped before this scheduled item'})}
                for a in self.plan['design']['arms'] for name in [c['id'] for c in diagnostic_cases()]+['recovery']]
            closures=[read(p) for p in (self.root/'runs').glob('*/CLOSED.json')]
            vms=[read(p) for p in self.root.glob('**/vm.json')]
            result['all_owned_workers_closed']=bool(closures) and all(r.get('owned_worker_closed') for r in closures)
            result['all_owned_vms_closed']=bool(vms) and all(r.get('owned_vm_closed') for r in vms)
            result['model_hashes_after']={k:sha(self.plan['models'][k]['path']) for k in ('original_target','unchanged','targeted')}
            result['original_models_unchanged']=all(result['model_hashes_after'][k]==self.plan['models'][k]['sha256'] for k in result['model_hashes_after'])
            self.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));self.save()
            atomic(self.root/'RESULT.json',result);print(json.dumps(result),flush=True)


def main(root):
    root=Path(root).resolve();plan=read(root/'manifest.json')
    with desktop_lease(plan['project']),exclusive(root):
        require(not (root/'runner.json').exists(),'No study replay or implicit retry')
        require(read(root/'AUTHORIZATION.json')['explicit_user_authorization'],'Explicit overnight instruction required')
        try:admission(plan['project'],root/'initial-admission')
        except BaseException as error:
            atomic(root/'RESULT.json',{'status':'admission_stopped','error':type(error).__name__+': '+str(error),
                'model_inference_started':False,'sampled_tokens':0,'no_automatic_retry':True});raise
        OvernightStudy(root).run_overnight()


def prepare_continuation(project,prior,root,handshake_control):
    """One reviewed harness-defect correction; no completed model response can replay."""
    project,prior,root,handshake_control=map(lambda x:Path(x).resolve(),(project,prior,root,handshake_control))
    old=read(prior/'manifest.json');result=read(prior/'RESULT.json')
    require(not old.get('continuation') and not root.exists(),'Only one correction cycle; never overwrite a run')
    require(result['status']=='stopped' and result['all_owned_workers_closed'] and result['all_owned_vms_closed'],'Predecessor must be closed')
    require(read(handshake_control)['status']=='passed','Actual owned-worker handshake control required')
    stopped=prior/'runs/call-012';usage=read(stopped/'usage.json');progress=read(stopped/'progress.json')
    require(usage['reserved']==usage['emitted']==0 and (stopped/'tokens.jsonl').stat().st_size==0,
        'A sampled case cannot restart under this continuation')
    require(progress['event']=='loading' and not progress['gpu_loaded'] and not (stopped/'RESULT.json').exists(),
        'Stopped call must be pre-inference model loading')
    require(not (stopped/'dev-restore-one.json').exists(),'No existing response may be replayed')
    remaining=read(prior/'runner.json')['began_unix']+5400-time.time()
    require(remaining>60,'Original diagnostic deadline exhausted')
    root.mkdir();(root/'code').mkdir();(root/'requests').mkdir();(root/'runs').mkdir()
    for name in old['code']:
        source=project/('controller' if name=='windows_job.py' else 'evaluations')/name
        shutil.copyfile(source,root/'code'/name)
    for name in old['data']:shutil.copyfile(prior/name,root/name)
    evidence={str(p.relative_to(prior)):sha(p) for p in prior.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.py','.sha256')}
    plan=copy.deepcopy(old);plan['code']={p.name:sha(p) for p in (root/'code').iterdir()}
    plan['limits']['total_seconds']=remaining
    plan['continuation']={'root':str(prior),'files':evidence,'one_correction_cycle_used':True,
        'reason':'venv child PID publication race before native model load; no model generation in stopped call',
        'original_diagnostic_deadline_unix':read(prior/'runner.json')['began_unix']+5400,
        'worker_handshake_control':str(handshake_control),'worker_handshake_control_sha256':sha(handshake_control),
        'reuse':'All completed unchanged-editor cases and recovery remain unchanged; only previously unstarted modified-editor arm proceeds'}
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    shutil.copyfile(prior/'run.py',root/'run.py')
    return {'root':str(root),'manifest_sha256':identity(plan),'remaining_original_diagnostic_seconds':remaining,
        'prior_charged_tokens':result['budget']['charged_tokens']}


if __name__=='__main__':
    if sys.argv[1]=='calibrate':
        project,folder=sys.argv[2:4]
        with desktop_lease(project):
            admission(project,Path(str(folder)+'-admission'))
            calibrate(project,folder,read(Path(project)/'.data/tensor-code-diagnostic-20261104-v5/manifest.json')['image'])
    elif sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='continue-prepare':print(prepare_continuation(*sys.argv[2:]))
    elif sys.argv[1]=='run':main(sys.argv[2])
