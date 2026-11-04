"""One Builder teacher intervention, screened before one symmetric student pair.

Research-only. Separate prepare/calibrate/screen/pair commands prevent implicit
qualification or relaunch. Primary completion and secondary endpoint quality differ.
"""
import copy,hashlib,json,random,secrets,shutil,sys,time
from pathlib import Path
if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lora6k_state import read,atomic,sha,identity,exclusive
from weight_editor_runtime import require,Deadline,check_files,account_before_grading
from tensor_workspace_errors import InfrastructureStop,CellAllowanceExceeded
from tensor_workspace_study import Study,code_cell
from tensor_workspace_overnight import desktop_lease,admission,fixture
from tensor_workspace_fresh_gate import positive as positive_cell
from tensor_workspace_fresh_gate import explicit_grade
from tensor_workspace_schema_comparison import readonly_fixture
from tensor_workspace_code_diagnostic import score,BRIEF as FIXTURE_BRIEF
from tensor_workspace_vm import TensorVM
from tensor_workspace_contract import pilot_brief,development_gate,qualify_target_outcome
from weight_editor_owned import launch

SCREEN=131072
PAIR=327680
RESERVE=8192
TOTAL=466944
PAIR_CATEGORIES={'editor_unchanged':49152,'editor_edited':49152,'feedback_unchanged':32768,'feedback_edited':32768,
    'shared_dev_baseline':16384,'shared_hidden_baseline':49152,'endpoint_unchanged':49152,'endpoint_edited':49152}


def teacher_cases():
    cases=[]
    for split,block,start in [('development',10,.1731),('confirmation',20,.2842)]:
        kinds=['restore_one','restore_checkpoint','test_saved','one_weight'] if split=='development' else ['restore_one','one_weight']
        for i,kind in enumerate(kinds):
            a=f'blk.{block}.attn_norm.weight';m=f'blk.{block}.attn_qkv.weight';label='retained_'+str(block)
            task={'restore_one':f'Restore only {a} to immutable-original contents, preserving all other saved edits exactly. Generate dev-0 and dev-1 with final contents, then submit().',
                'restore_checkpoint':f'Restore checkpoint {label!r} completely, removing later changes. Generate dev-0 and dev-1, then submit().',
                'test_saved':'Generate dev-0 and dev-1 using all current saved edits and print the actual results. Preserve every numeric value. Do not write, undo, restore, checkpoint or submit.',
                'one_weight':f'Change ONLY flat index 7169 of {m} to 0.28125, preserving every other current value. Generate dev-0 and dev-1 and submit().'}[kind]
            cases.append({'id':split+'-'+kind.replace('_','-'),'split':split,'kind':kind,'block':block,'index':7169,
                'label':label,'base_start':start+i*.013,'base_end':start+1+i*.013,'initial_values':[.453125,.796875,.609375],
                'bad_values':[.96875,.34375],'edit_value':.28125,'submission_policy':'forbidden' if kind=='test_saved' else 'required','task':task})
            cases[-1].update(write_policy='forbidden' if kind=='test_saved' else 'allowed',display_required=kind=='test_saved')
    cases.extend([{'id':'preservation-squares','split':'preservation','kind':'ordinary','expected':'22140',
        'task':'Using Python, calculate the sum of squares of the integers 1 through 40 inclusive. Print only the integer result. Do not use any tensor or evaluation helpers.'},
        {'id':'preservation-primes','split':'preservation','kind':'ordinary','expected':'25',
        'task':'Using Python, count the prime integers from 2 through 100 inclusive. Print only the integer result. Do not use any tensor or evaluation helpers.'}])
    return cases


def localization_prompts(tokenizer):
    scenarios=[('A tested True on both IDs, B tested False on both. Checkpoint state_A exists; B is current. Choose measured A before retesting.', 'restore_checkpoint','model_info'),
        ('A tested False on both IDs, current B tested True on both. Both states measured. Declare current B with checkpoint selected; no restoration is necessary.', 'save_checkpoint','restore_checkpoint'),
        ('Only blk.10.attn_norm.weight must return to the immutable original; preserve other saved tensors. The helper undo_edit(name) does exactly this.', 'undo_edit','load_tensor'),
        ('Current nonempty edit has just been tested on both IDs with a gain and no loss. No more changes or measurements are requested. Finish by freezing it.', 'submit','save_edit')]
    result=[]
    for i,(task,good,bad) in enumerate(scenarios):
        prompt='<|im_start|>system\nComplete the next Python helper operation in the stated synthetic editing state. No mathematical repair is requested.\n<|im_end|>\n<|im_start|>user\n'+task+'\n<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n```python\n'
        g=tokenizer.encode(good,add_special_tokens=False).ids[0];b=tokenizer.encode(bad,add_special_tokens=False).ids[0]
        require(g!=b,'Localization contrast shares initial token')
        result.append({'id':'loc-'+str(i),'rendered_prompt':prompt,'input_ids':tokenizer.encode(prompt,add_special_tokens=False).ids,
            'good_token':g,'bad_token':b,'good_prefix':good,'bad_prefix':bad})
    return result


def screen_support(base,edited,split):
    b={r['id']:r for r in base if r['split']==split};e={r['id']:r for r in edited if r['split']==split}
    require(set(b)==set(e) and b,'Incomplete matched screen')
    gains=[i for i in b if not b[i]['correct'] and e[i]['correct']]
    losses=[i for i in b if b[i]['correct'] and not e[i]['correct']]
    return {'gains':gains,'losses':losses,'base_correct':sum(r['correct'] for r in b.values()),'edited_correct':sum(r['correct'] for r in e.values())}


def prepare_layout(root):
    """Create disk-admission parents before a candidate builder is called."""
    root=Path(root);root.mkdir()
    for name in ('code','runs','requests','artifacts'):(root/name).mkdir()


def prepare(project,root,calibration):
    from tokenizers import Tokenizer
    import pyarrow.parquet as pq
    from weight_editor_prepare import normalized
    from weight_repair_protocol import extract_answer
    project,root,calibration=map(lambda p:Path(p).resolve(),(project,root,calibration));require(not root.exists(),'No replay/overwrite')
    require(read(calibration/'RESULT.json')['status']=='passed','Current actual VM calibration required')
    old=read(project/'.data/apwt-neutral-selection-20261104-001/manifest.json')
    prepare_layout(root)
    modules=set(old['code'])|{'tensor_workspace_contract.py','tensor_workspace_teacher_stage.py','tensor_workspace_teacher_localize.py','weight_editor_targeted.py'}
    for n in modules:shutil.copyfile(project/('controller' if n=='windows_job.py' else 'evaluations')/n,root/'code'/n)
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol')}
    plan['models']={k:copy.deepcopy(old['models'][k]) for k in ('original_target','unchanged')}
    plan.update(scope='One new Builder-authored manual4B intervention and conditional symmetric original0.8B teacher pair',overnight=True,numeric_policy='precise-v2',
        canonical_shards=read(project/'.data/manual4b-targeted-20261103/manifest.json')['canonical_shards'],
        limits={'total_seconds':28800,'arm_seconds':1800,'editor_calls':8,'forward_calls':4,'editor_tokens':49152,
            'development_generated_tokens':32768,'qualification_generated_tokens':147456,'cell_seconds':60,'tensor_bytes':67108864,'patch_bytes':536870912,'transfer_bytes':2147483648},
        design={'arms':['unchanged','edited'],'explicit_contract':True,'target_output_tokens':8192,'editor_output_tokens':8192,
            'editor_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'thinking':True},
            'editor_seed_sequence':[2026110420+n for n in range(8)],
            'target_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'generated_only_presence':1.5},
            'shared_initial_baseline_ids':['dev-0','dev-1'],'shared_gpu_activation':False,'no_second_assignment':True,
            'primary':'Clean submitted nonempty fully measured development gain without loss, then fresh confirmation gain, no independent loss and at least one baseline-correct preservation opportunity',
            'secondary':'Independently evaluate each numerically valid frozen endpoint, including unsubmitted; unchanged is baseline-equivalent; infrastructure-unrun is missing',
            'advancement_for_proposal_only':'Edited primary accepted and greater number of accepted gains than unchanged teacher; a tie is not teacher benefit. Any second assignment needs separate commitment.',
            'vm_preflight_receipt':str(calibration/'RESULT.json'),
            'vm_preflight_sha256':sha(calibration/'RESULT.json')},
        intervention={'family':'One canonical BF16 FFN down-projection, layers26..31; exactly16 columns attenuated by0.5 then exact Q8 conversion',
            'layers':list(range(26,32)),'columns':16,'scale':.5,'relative_canonical_delta_norm_max':.035,
            'localization_forwards_max':32,'per_forward_seconds':120,'context_tokens_max':4096,'localization_seconds':1800,
            'selection':'Four baseline captures + six whole-FFN half-strength conditions on four dev prefixes =28; choose greatest mean next-token margin improvement (smallest layer tie). Rank columns by harmful readout proxy; four final column-condition probes =32. Require positive mean column margin change; no second patch.',
            'predicted_effect':'Reduce unproductive repeated inspection and improve exact restoration/finishing; logit proxy alone is not behavioral support',
            'specificity_control':'No shuffled arm fits this budget; no column-specific causal semantics claim'},
        screens={'development':'Four executed tasks per teacher; edited must gain at least one and lose none',
            'confirmation':'Two separate executed tasks per teacher after patch freeze; no loss and at least one edited correct',
            'preservation':'Two ordinary executable-code tasks per teacher; no loss and at least one original-correct opportunity',
            'responses_max':16,'screen_tokens':SCREEN,'screen_seconds':7200,'pair_seconds':10800,'pair_tokens':PAIR,'interruption_reserve':RESERVE,'total_tokens':TOTAL})
    plan['target_protocol']['max_new_tokens']=8192
    et=Tokenizer.from_file(str(Path(plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
    st=Tokenizer.from_file(str(Path(plan['tokenizers']['target_tokenizer']['path'])/'tokenizer.json'))
    # Exclude prepared as well as exposed prior question packs, conservatively.
    prior=set();inventory={}
    def collect(v):
        if isinstance(v,dict):
            if isinstance(v.get('problem'),str):prior.add(normalized(v['problem']))
            for x in v.values():collect(x)
        elif isinstance(v,list):
            for x in v:collect(x)
    for path in (project/'.data').rglob('*inputs*.json'):
        if path.is_file() and path.stat().st_size<=5*1024**2:
            collect(read(path));inventory[str(path.relative_to(project))]=sha(path)
    assets=project/'.data/weight-repair-20261102';train_path=assets/'gpu-readiness-001/math-train.parquet';bench_path=assets/'acquisition-001/assets/dataset/math500.jsonl'
    ds=read(project/'.data/manual4b-localprojection-pair-20261103/manifest.json')['dataset_sources']
    require(sha(train_path)==ds['train_sha256'] and sha(bench_path)==ds['benchmark_sha256'],'Dataset changed')
    bench=[json.loads(x) for x in bench_path.read_text(encoding='utf8').splitlines()];benchkeys={normalized(r['problem']) for r in bench}
    eligible={}
    for i,r in enumerate(pq.read_table(train_path).to_pylist()):
        key=normalized(r['problem'])
        if key not in prior and key not in benchkeys and extract_answer(r['solution']):eligible.setdefault(key,(i,r))
    selection_seed=secrets.randbits(64);rng=random.Random(selection_seed);chosen=rng.sample(list(eligible.values()),6)
    preservation=rng.sample([r for r in bench if normalized(r['problem']) not in prior],2)
    cases=[];golds={}
    for split,items in [('dev',chosen[:2]),('confirmation',chosen[2:]),('preservation',[(r['unique_id'],r) for r in preservation])]:
        for n,(sid,row) in enumerate(items):
            name=split+'-'+str(n);prompt='<|im_start|>user\n'+row['problem']+'\n'+plan['target_protocol']['instruction']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
            ids=st.encode(prompt,add_special_tokens=False).ids;require(len(ids)+8192<=34816,'Target context too long')
            cases.append({'id':name,'split':split,'source_id':sid,'problem':row['problem'],'rendered_prompt':prompt,'input_ids':ids,'rng_seed':rng.randrange(2**32)})
            golds[name]=row['answer'] if split=='preservation' else extract_answer(row['solution'])
    atomic(root/'inputs.json',{'cases':cases});atomic(root/'hidden-golds.json',golds)
    shutil.copyfile(project/'.data/manual4b-targeted-shared-gpu-20261103-v4/tensor-catalog.json',root/'tensor-catalog.json')
    screens=teacher_cases()
    fixture_brief=FIXTURE_BRIEF.replace("test_candidate(['dev-0']) generates an answer.","test_candidate(['dev-0']) requests a synthetic protocol stub with correct=None, not a math answer.")
    for c in screens:
        c['rendered_prompt']='<|im_start|>system\n'+fixture_brief+'<|im_end|>\n<|im_start|>user\n'+c['task']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
        c['input_ids']=et.encode(c['rendered_prompt'],add_special_tokens=False).ids;c['rng_seed']=rng.randrange(2**32)
    atomic(root/'teacher-inputs.json',{'cases':screens,'feedback':'protocol_stub correct=None for tensors; no real student inference'})
    atomic(root/'localization-inputs.json',{'cases':localization_prompts(et)})
    atomic(root/'exclusion-inventory.json',{'selection_seed':selection_seed,'prior_files':inventory,'excluded_problem_count':len(prior),'dataset_sources':ds})
    atomic(root/'protocol.json',{'pilot_brief':pilot_brief(plan),'order':['unchanged','edited'],'both_endpoints_freeze_before_hidden':True,
        'editor_seed_sequence':[2026110420+n for n in range(8)],'second_assignment':'not committed; no automatic launch'})
    atomic(root/'AUTHORIZATION.json',{'source_thread_id':'REDACTED-PRIVATE-THREAD','explicit_user_authorization':False,
        'user_words':'Yeah this sounds good, you can proceed with this plan.','scope':'One new Builder teacher patch and one conditional symmetric original0.8B assignment; reviewed first stage only',
        'sampled_tokens':TOTAL,'scientific_seconds':28800,'engineering_review_before_clock':True,'second_assignment_authorized':False})
    plan['code']={p.name:sha(p) for p in (root/'code').iterdir()};plan['controller_files']={str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')}
    plan['data']={n:sha(root/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json','teacher-inputs.json','localization-inputs.json','exclusion-inventory.json','protocol.json','AUTHORIZATION.json')}
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\nsys.path.insert(0,str(r/'code'))\nsys.path.insert(1,str(r.parents[1]))\nfrom tensor_workspace_teacher_stage import dispatch\ndispatch(sys.argv[1],r)\n",encoding='utf8')
    return {'root':str(root),'plan_identity':identity(plan),'sampled_token_ceiling':TOTAL,'second_assignment':False}


def prepare_continuation(project,prior,root):
    project,prior,root=map(lambda p:Path(p).resolve(),(project,prior,root))
    require(not root.exists(),'No continuation overwrite')
    old=read(prior/'manifest.json');require(identity(old)==(prior/'manifest.sha256').read_text().strip(),'Ancestor identity mismatch')
    check_files(prior/'code',old['code']);check_files(prior,old['data'])
    stopped=read(prior/'SCREEN-RESULT.json');before=read(prior/'STAGE-BUDGET.json');clock=read(prior/'SCIENTIFIC-START.json')
    require(stopped['status']=='infrastructure_or_budget_stopped' and 'FileNotFoundError' in stopped['error'],'Not the reviewed directory stop')
    require(not (prior/'PATCH-MODEL.json').exists() and not (prior/'artifacts').exists() and not list((prior/'runs').glob('call-*')),'Construction/screen already attempted')
    require(read(prior/'LOCALIZATION-ADMISSION.json')['admitted_conditions']==32 and before['charged_tokens']==0,'Unexpected ancestor consumption')
    require(all(stopped['original_models_unchanged'].values()) and stopped['all_owned_workers_closed'],'Ancestor not closed')
    require(clock['began_unix']+7200>time.time() and clock['end_unix']>time.time(),'Original scientific/screen deadline expired')
    prepare_layout(root)
    for n in old['code']:shutil.copyfile(project/('controller' if n=='windows_job.py' else 'evaluations')/n,root/'code'/n)
    for n in old['data']:shutil.copyfile(prior/n,root/n)
    for n in ('FROZEN-INTERVENTION.json','SCIENTIFIC-START.json'):shutil.copyfile(prior/n,root/n)
    files={str(p.relative_to(prior)):sha(p) for p in prior.rglob('*') if p.is_file() and p.name not in ('run.lock',)}
    # Full ancestor inventory is immutable from this point, including its stop.
    plan=copy.deepcopy(old);plan['scope']='Explicit continuation of sole frozen teacher recipe after directory fix; no localization replay'
    plan['predecessor_completion']={'root':str(prior),'files':files}
    plan['continuation']={'root':str(prior),'plan_identity':identity(old),'localization_conditions_consumed':32,
        'original_screen_end_unix':clock['began_unix']+7200,'original_scientific_end_unix':clock['end_unix'],
        'intervention_sha256':sha(prior/'FROZEN-INTERVENTION.json'),'screen_responses_replayed':0}
    atomic(root/'CONTINUATION-AUTHORIZATION.json',{'source_thread_id':'REDACTED-PRIVATE-THREAD','explicit_user_authorization':False,
        'instruction':'Continue the user-approved stage from the already frozen layer-26 recipe after independently verified directory fix. Do not repeat localization, reset original clock/budget or alter historical stop evidence. Construct and validate sole artifact; predeclared screen then conditional independently reviewed pair.',
        'overall_ceiling_unchanged':TOTAL,'second_assignment_authorized':False})
    plan['code']={p.name:sha(p) for p in (root/'code').iterdir()}
    plan['data'].update({n:sha(root/n) for n in ('FROZEN-INTERVENTION.json','SCIENTIFIC-START.json','CONTINUATION-AUTHORIZATION.json')})
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    usage=read(prior/'usage.json');usage['phases']={'prior:'+k:v for k,v in usage['phases'].items()};atomic(root/'usage.json',usage)
    before['phase_categories']={'prior:'+k:v for k,v in before['phase_categories'].items()};atomic(root/'STAGE-BUDGET.json',before)
    shutil.copyfile(prior/'run.py',root/'run.py')
    return {'root':str(root),'plan_identity':identity(plan),'localization_disabled':True,'remaining_screen_seconds':clock['began_unix']+7200-time.time(),'total_token_ceiling':TOTAL}


class TeacherStudy(Study):
    def __init__(self,root):
        super().__init__(root);self.brief=read(self.root/'protocol.json')['pilot_brief'];self.category='screen';self.phase_categories={}
        self.generation_calls=0;self.probe_calls=0
        previous=read(self.root/'STAGE-BUDGET.json') if (self.root/'STAGE-BUDGET.json').exists() else {}
        self.phase_categories=previous.get('phase_categories',{})
        self.calls=max([int(p.stem.split('-')[1]) for p in (self.root/'requests').glob('call-*.json')]+[0])
        if (self.root/'baseline-results.json').exists():self.baseline_cache=read(self.root/'baseline-results.json')

    def reconcile(self):
        u=read(self.root/'usage.json') if (self.root/'usage.json').exists() else {'phases':{},'charged_tokens':0}
        caps={'screen':SCREEN,**PAIR_CATEGORIES,'localization':0};observed={k:0 for k in caps};uncertain=0
        for phase,m in u['phases'].items():
            cat=self.phase_categories[phase];observed[cat]+=m['observed_tokens'];uncertain+=m['uncertain_tokens_upper_bound']
        require(all(observed[k]<=caps[k] for k in caps),'Scheduled category ceiling exceeded')
        require(uncertain<=RESERVE and u['charged_tokens']<=TOTAL,'Shared interruption/aggregate ceiling exceeded')
        report={'charged_tokens':u['charged_tokens'],'observed_categories':observed,'uncertain_tokens':uncertain,
            'phase_categories':self.phase_categories,'scheduled_screen':SCREEN,'scheduled_pair':PAIR,'interruption_reserve':RESERVE,'total_ceiling':TOTAL}
        atomic(self.root/'STAGE-BUDGET.json',report);return report

    def inference(self,mode,model,cases,*,remaining=1048576):
        cap=SCREEN if self.category=='screen' else PAIR_CATEGORIES[self.category]
        budget=self.reconcile();available=cap-budget['observed_categories'][self.category]
        allowance=min(remaining,len(cases)*8192,available) if mode!='probe' else 0
        require(mode=='probe' or allowance>=len(cases)*8192,'Not enough category capacity for full admitted responses')
        phase='call-'+str(self.calls+1).zfill(3);self.phase_categories[phase]=self.category;self.reconcile()
        try:rows=super().inference(mode,model,cases,remaining=allowance)
        finally:self.reconcile()
        if mode=='generate':
            rows=[qualify_target_outcome(row,read(row['response_file'])) for row in rows]
            if rows:atomic(Path(rows[0]['response_file']).parent/'checked.json',rows)
        return rows

    def forward(self,request):
        if request['mode']=='generate':
            require(self.generation_calls<2,'Two candidate-generation requests exhausted');self.generation_calls+=1
            require(request['view'] in ('edited','both') and set(request.get('ids') or [])<={'dev-0','dev-1'},'Only two frozen dev IDs')
        else:
            require(self.probe_calls<2,'Two single-text probes exhausted');self.probe_calls+=1
            require(request['view']=='edited' and len(request.get('texts') or [])==1,'Only current-candidate single-text probes')
        self.category='feedback_'+self.arm
        try:return super().forward(request)
        finally:self.category='editor_'+self.arm

    def localize(self,conditions):
        require(not self.plan.get('continuation'),'Localization is disabled in this continuation;32 forwards already consumed')
        previous=read(self.root/'LOCALIZATION-ADMISSION.json') if (self.root/'LOCALIZATION-ADMISSION.json').exists() else {'admitted_conditions':0,'requests':0}
        require(previous['admitted_conditions']+len(conditions)<=32,'Localization forward cap')
        name='local-'+str(previous['requests']+1).zfill(3);path=self.root/'requests'/(name+'.json')
        require(not (self.root/'STOP').exists(),'Operator stop')
        atomic(path,{'model':self.plan['models']['unchanged'],'conditions':conditions});atomic(self.root/'active-request.json',{'sha256':sha(path)})
        atomic(self.root/'LOCALIZATION-ADMISSION.json',{'admitted_conditions':previous['admitted_conditions']+len(conditions),'requests':previous['requests']+1})
        self.phase_categories[name]='localization';self.reconcile();folder=self.root/'runs'/name
        try:result=launch(self.root,folder,[self.plan['interpreters']['python']['path'],str(self.root/'code/tensor_workspace_teacher_localize.py'),str(path)],self.worker_deadline)
        except BaseException as error:raise InfrastructureStop('Localization: '+str(error)) from error
        finally:
            if (folder/'usage.json').exists():account_before_grading(self.root/'usage.json',name,folder,read(folder/'usage.json')['binding'])
            self.reconcile()
        require(result['request_sha256']==sha(path),'Localization binding mismatch');return result['rows']


def localize_and_build(study):
    import numpy as np
    from weight_editor_targeted import build_candidate
    root=study.root;cases=read(root/'localization-inputs.json')['cases'];end=min(study.deadline.end,time.monotonic()+1800);study.worker_deadline=Deadline(end=end)
    conditions=[{**c,'id':'base-'+str(i),'capture':True} for i,c in enumerate(cases)]
    for layer in range(26,32):
        conditions.extend({**c,'id':f'layer-{layer}-{i}','layer':layer,'intervention':{'kind':'scale','name':f'ffn_out-{layer}','scale':.5}} for i,c in enumerate(cases))
    rows=study.localize(conditions);base=rows[:4];groups={layer:rows[4+(layer-26)*4:8+(layer-26)*4] for layer in range(26,32)}
    changes={layer:float(np.mean([r['margin']-b['margin'] for r,b in zip(groups[layer],base)])) for layer in groups}
    layer=min(changes,key=lambda k:(-changes[k],k));atomic(root/'LOCALIZATION-LAYERS.json',{'rows':rows,'mean_margin_changes':changes,'selected_layer':layer,'proxy_only':True})
    if changes[layer]<=0:return {'passed':False,'reason':'No positive localization margin condition; no patch built'}
    check_files(study.plan['cpu_vendor_sources']['path'],study.plan['cpu_vendor_sources']['files']);sys.path.insert(0,study.plan['cpu_vendor_sources']['path'])
    from gguf import GGUFReader
    from gguf.quants import dequantize
    reader=GGUFReader(study.plan['models']['unchanged']['path']);tensors={t.name:t for t in reader.tensors}
    head=tensors.get('output.weight',tensors.get('token_embd.weight'));norm=dequantize(tensors['output_norm.weight'].data,tensors['output_norm.weight'].tensor_type).reshape(-1)
    t=tensors[f'blk.{layer}.ffn_down.weight'];w=dequantize(t.data,t.tensor_type);require(w.shape==(2560,9216),'4B matrix layout')
    harmful=np.zeros(9216,dtype=np.float64)
    for c,b in zip(cases,base):
        study.worker_deadline.remaining()
        good=dequantize(head.data[c['good_token']:c['good_token']+1],head.tensor_type).reshape(-1)
        bad=dequantize(head.data[c['bad_token']:c['bad_token']+1],head.tensor_type).reshape(-1)
        direction=norm.astype(np.float64)*(good.astype(np.float64)-bad.astype(np.float64));direction/=max(1e-12,np.linalg.norm(direction))
        with np.load(b['capture'],allow_pickle=False) as capture:x=capture[f'ffn_swiglu-{layer}'].astype(np.float64)
        harmful-=x*(direction@w)
    columns=sorted(map(int,np.argsort(-harmful,kind='stable')[:16]));np.savez_compressed(root/'COLUMN-LOCALIZATION.npz',harmful_score=harmful,columns=columns)
    del reader,tensors,head,w
    final=study.localize([{**c,'id':'columns-'+str(i),'layer':layer,'intervention':{'kind':'columns','name':f'ffn_swiglu-{layer}','columns':columns,'scale':.5}} for i,c in enumerate(cases)])
    change=float(np.mean([r['margin']-b['margin'] for r,b in zip(final,base)]))
    proposal={'layer':layer,'columns':columns,'scale':.5}
    frozen={'proposal':proposal,'mean_column_margin_change':change,'rows':final,'authorship':'Builder-authored frozen development-only readout/probe procedure; no local-teacher weight proposal','proxy_only':True}
    atomic(root/'FROZEN-INTERVENTION.json',frozen)
    if change<=0:return {'passed':False,'reason':'Column condition lacks positive margin support; no replacement patch'}
    return build_frozen_intervention(study,proposal)


def build_frozen_intervention(study,proposal):
    import numpy as np
    from weight_editor_targeted import build_candidate
    check_files(study.plan['cpu_vendor_sources']['path'],study.plan['cpu_vendor_sources']['files']);sys.path.insert(0,study.plan['cpu_vendor_sources']['path'])
    from gguf import GGUFReader
    from gguf.quants import dequantize
    root=study.root;layer=proposal['layer'];columns=proposal['columns']
    require(26<=layer<=31 and len(columns)==16 and len(set(columns))==16 and proposal['scale']==.5,'Outside frozen intervention bounds')
    model=build_candidate(study.plan,proposal,root/'artifacts/edited-teacher',study.deadline)
    evidence=read(root/'artifacts/edited-teacher/MANIFEST.json')
    require(evidence['relative_canonical_delta_norm']<=.035,'Patch exceeded frozen norm bound')
    # Quantization neighbors are measured separately from intended BF16 columns.
    readers=[GGUFReader(study.plan['models']['unchanged']['path']),GGUFReader(model['path'])]
    tensors=[next(t for t in reader.tensors if t.name==f'blk.{layer}.ffn_down.weight') for reader in readers]
    before,after=[dequantize(t.data,t.tensor_type) for t in tensors];delta=after.astype(np.float64)-before.astype(np.float64)
    mask=np.zeros(9216,dtype=bool);mask[columns]=True
    numeric={'base_no_edit_reconstruction_exact':True,'outside_selected_Q8_blocks_verified':True,
        'selected_deployed_changed_entries':int(np.count_nonzero(delta[:,mask])),
        'neighbor_deployed_changed_entries':int(np.count_nonzero(delta[:,~mask])),
        'selected_deployed_delta_l2':float(np.linalg.norm(delta[:,mask])),
        'neighbor_deployed_delta_l2':float(np.linalg.norm(delta[:,~mask])),
        'actual_deployed_relative_delta_l2':float(np.linalg.norm(delta)/np.linalg.norm(before.astype(np.float64))),
        'canonical_relative_delta_l2':evidence['relative_canonical_delta_norm'],'changed_q8_blocks':evidence['changed_q8_blocks'],
        'base_sha256':study.plan['models']['unchanged']['sha256'],'edited_sha256':model['sha256']}
    atomic(root/'artifacts/edited-teacher/DEPLOYED-DELTA.json',numeric)
    del readers,tensors,before,after,delta
    atomic(root/'PATCH-MODEL.json',{'model':model,'intervention_sha256':sha(root/'FROZEN-INTERVENTION.json'),
        'numeric_manifest_sha256':sha(root/'artifacts/edited-teacher/MANIFEST.json'),'deployed_delta_sha256':sha(root/'artifacts/edited-teacher/DEPLOYED-DELTA.json'),
        'frozen_before_any_screen_sampling':True})
    return {'passed':True,'model':model,'proposal':proposal}


def resume_frozen_intervention(study):
    binding=study.plan['continuation'];require(sha(study.root/'FROZEN-INTERVENTION.json')==binding['intervention_sha256'],'Frozen recipe changed')
    require(binding['localization_conditions_consumed']==32,'Consumed forwards not retained')
    frozen=read(study.root/'FROZEN-INTERVENTION.json');require(frozen['mean_column_margin_change']>0,'No prior proxy support')
    require(not (study.root/'artifacts/edited-teacher').exists(),'No duplicate artifact construction')
    return build_frozen_intervention(study,frozen['proposal'])


def screen_fixture(folder,case,*,faithful=True):
    if case['kind']=='test_saved':return readonly_fixture(folder,case,faithful=faithful)
    p,expected,requests,n,_=fixture(folder,teacher_cases()[0] if case['kind']=='ordinary' else case,faithful=faithful)
    if case['kind']=='ordinary':expected={name:p.array(name).tobytes() for name in n}
    return p,expected,requests,n,[]


def grade_teacher_case(p,expected,requests,n,attempts,case,outcome):
    if case['kind']=='ordinary':
        unchanged=all(p.array(name).tobytes()==raw for name,raw in expected.items())
        return {'correct':bool(not outcome['error'] and outcome['output'].strip()==case['expected'] and not p.operation_history and unchanged),
            'numeric_preservation':unchanged,'cell_error':outcome['error'],'actual_output':outcome['output']}
    return explicit_grade(p,expected,requests,outcome,case,attempts)


def screen_response(study,arm,model,case):
    from tensor_workspace_vm_startup import bound_serial
    folder=study.root/'teacher-screen'/arm/case['id'];folder.parent.mkdir(parents=True,exist_ok=True)
    study.category='screen';study.arm='screen-'+arm;study.state.update(phase='teacher_screen',screen_arm=arm,case=case['id']);study.save()
    response=study.inference('editor',model,[case],remaining=8192)[0]
    p,expected,requests,n,attempts=screen_fixture(folder,case)
    outcome={'error':'No executable cell','output':''};vm=None
    try:
        require(response['finish_reason']=='eos','Truncated; no code executed');code,_=code_cell(response['raw_text'])
        vm=TensorVM(study.project,study.plan['image'],folder/'vm.json',study.deadline,debug_console=folder/'serial.log')
        outcome=vm.execute(code,p,seconds=60)
    except (ValueError,CellAllowanceExceeded) as error:outcome={'error':type(error).__name__+': '+str(error),'output':''}
    except Exception as error:raise InfrastructureStop('Screen VM: '+str(error)) from error
    finally:
        if vm:vm.close()
        bound_serial(folder/'serial.log')
        graded=grade_teacher_case(p,expected,requests,n,attempts,case,outcome)
        result={'id':case['id'],'split':case['split'],'teacher':arm,'generated_tokens':response['generated_tokens'],'finish_reason':response['finish_reason'],**graded}
        atomic(folder/'EFFECT.json',{'score':result,'outcome':outcome,'receipts':p.receipt_ledger,'operations':p.operation_history,'final':p.status()})
    return result


def freeze_endpoint(study,arm,initial):
    p=study.policy;state=study.state['arms'][arm];gate=development_gate(p,state,initial,study.settings_sha256)
    if p.upload is not None or p.download is not None:
        result={'teacher':arm,'numerically_valid':False,'candidate':p.candidate_state(),'development_gate':gate,
            'primary_procedural_completion':False,'submitted':p.submitted,'baseline_equivalent':not bool(p.edits),
            'secondary_status':'unmeasured_invalid_endpoint','reason':'Incomplete tensor transfer'}
        atomic(study.root/arm/'ENDPOINT.json',result);return result
    model=study.snapshot(p,study.root/arm/'snapshots/final-endpoint')
    result={'teacher':arm,'numerically_valid':True,'model':model,'candidate':p.candidate_state(),'edits':p.edits,'development_gate':gate,
        'primary_procedural_completion':bool(state['clean_terminal'] and p.submitted),'submitted':p.submitted,
        'selection':'Exact terminal workspace, not operator-chosen intermediate','baseline_equivalent':not bool(p.edits)}
    atomic(study.root/arm/'ENDPOINT.json',result);return result


def endpoint_outcomes(base,rows,endpoint):
    b={r['id']:r for r in base};e={r['id']:r for r in rows};require(set(b)==set(e),'Incomplete secondary endpoint measurements')
    gains=[i for i in b if i.startswith('confirmation-') and not b[i]['correct'] and e[i]['correct']]
    losses=[i for i in b if b[i]['correct'] and not e[i]['correct']]
    preservation=[i for i in b if i.startswith('preservation-') and b[i]['correct']]
    primary=bool(endpoint['development_gate']['passed'] and gains and not losses and preservation and not endpoint['baseline_equivalent'])
    return {'primary_accepted_student_improvement':primary,'confirmation_gains':gains,'independent_losses':losses,
        'baseline_correct_preservation':preservation,'preservation_measured':bool(preservation),
        'secondary_correct':sum(r['correct'] for r in rows),'baseline_equivalent':endpoint['baseline_equivalent'],
        'clean_submission':endpoint['primary_procedural_completion'],'claim':'One exploratory teacher editing attempt; questions are not independent teacher trials'}


def paired_assignment(study):
    root=study.root;patch=read(root/'PATCH-MODEL.json');require(sha(patch['model']['path'])==patch['model']['sha256'],'Frozen teacher changed')
    require(read(root/'SCREEN-GATE.json')['passed'],'Teacher screen did not support spending')
    study.worker_deadline=study.deadline.child(1800);study.category='shared_dev_baseline';study.arm=None
    initial=study.baseline(['dev-0','dev-1']);atomic(root/'PAIR-ENTRY.json',{'all_baselines_correct':all(r['correct'] for r in initial),'valid_capped_baselines_allowed':True})
    if all(r['correct'] for r in initial):return {'status':'all_development_correct_stop','pair_run':False}
    # New models binding in an append-only artifact; original study manifest is immutable.
    endpoints={};teachers={'unchanged':study.plan['models']['unchanged'],'edited':patch['model']}
    study.teacher_models=teachers
    for arm in read(root/'protocol.json')['order']:
        require(sha(teachers[arm]['path'])==teachers[arm]['sha256'],'Teacher weights changed')
        study.generation_calls=0;study.probe_calls=0;study.category='editor_'+arm
        study.development_deadline=Deadline(end=min(study.deadline.end-3600,time.monotonic()+1800));study.worker_deadline=study.development_deadline
        study.editor_arm(arm,initial)
        # Artifact freezing is host accounting, not another editor opportunity.
        # Preserve valid terminal bytes even when the development deadline expired.
        study.worker_deadline=study.deadline.child(300)
        endpoints[arm]=freeze_endpoint(study,arm,initial)
    atomic(root/'BOTH-ENDPOINTS-FROZEN.json',{'endpoints':endpoints,'frozen_unix':time.time(),'before_hidden_inference':True})
    study.worker_deadline=study.deadline;results={'original':[],'unchanged':[],'edited':[]}
    hidden=[c for c in study.cases if c['split']!='dev']
    for view in ('original','unchanged','edited'):
        if view!='original' and not endpoints[view]['numerically_valid']:continue
        if view=='original' and not any(e['numerically_valid'] for e in endpoints.values()):continue
        require((root/'BOTH-ENDPOINTS-FROZEN.json').exists(),'Both endpoints must freeze before hidden requests')
        model=study.plan['models']['original_target'] if view=='original' else endpoints[view]['model']
        require(sha(model['path'])==model['sha256'],'Endpoint changed')
        study.category='shared_hidden_baseline' if view=='original' else 'endpoint_'+view;study.arm=None;study.state.update(phase='independent_'+view);study.save()
        for start in range(0,len(hidden),2):
            results[view].extend(study.inference('generate',model,hidden[start:start+2]));atomic(root/'PAIR-INDEPENDENT-RESULTS.json',results)
    outcomes={a:(endpoint_outcomes(results['original'],results[a],endpoints[a]) if endpoints[a]['numerically_valid'] else
        {'primary_accepted_student_improvement':False,'secondary_status':'unmeasured_invalid_endpoint','confirmation_gains':[]}) for a in endpoints}
    edited_advantage=outcomes['edited']['primary_accepted_student_improvement'] and (
        not outcomes['unchanged']['primary_accepted_student_improvement'] or len(outcomes['edited']['confirmation_gains'])>len(outcomes['unchanged']['confirmation_gains']))
    return {'status':'completed','pair_run':True,'outcomes':outcomes,'edited_teacher_observed_advantage':bool(edited_advantage),
        'second_assignment_run':False,'second_assignment_authorized':False,'advancement_is_proposal_only':True}


def science_deadline(root,stage):
    path=root/'SCIENTIFIC-START.json'
    if stage=='screen':
        if read(root/'manifest.json').get('continuation'):
            require(path.exists(),'Continuation must retain original clock')
        else:
            require(not path.exists(),'No scientific relaunch');atomic(path,{'began_unix':time.time(),'end_unix':time.time()+28800,'engineering_and_review_excluded':True})
    start=read(path);left=start['end_unix']-time.time();require(left>0,'Eight-hour scientific ceiling expired')
    if stage=='screen':
        screen_left=start['began_unix']+7200-time.time();require(screen_left>0,'Original screen deadline expired')
        return Deadline(min(left,screen_left))
    return Deadline(min(left,10800))


def run_stage(root,stage):
    root=Path(root).resolve();plan=read(root/'manifest.json');check_files(root/'code',plan['code']);check_files(root,plan['data'])
    require(stage in ('screen','pair'),'Explicit stage required');marker=root/(stage.upper()+'-STARTED.json')
    require(not marker.exists(),'No stage replay or automatic retries')
    review=read(root/('ENGINEERING-REVIEW.json' if stage=='screen' else 'PAIR-REVIEW.json'))
    require(review['approved'] is True and review['plan_identity']==identity(plan),'Independent review required for this exact plan')
    if stage=='pair':
        required={'PATCH-MODEL.json','SCREEN-GATE.json','TEACHER-SCREEN-RESULTS.json','artifacts/edited-teacher/DEPLOYED-DELTA.json'}
        require(required<=set(review.get('artifacts',{})),'Pair review must bind chosen teacher and screen evidence')
        check_files(root,review['artifacts'])
    with desktop_lease(plan['project']),exclusive(root):
        atomic(marker,{'started_unix':time.time(),'review_sha256':sha(root/('ENGINEERING-REVIEW.json' if stage=='screen' else 'PAIR-REVIEW.json'))})
        study=None;result={'status':'starting','stage':stage,'pair_run':False}
        try:
            deadline=science_deadline(root,stage)
            admission(plan['project'],root/(stage+'-admission'))
            study=TeacherStudy(root);study.deadline=deadline;study.worker_deadline=deadline
            if stage=='screen':
                build=resume_frozen_intervention(study) if plan.get('continuation') else localize_and_build(study);result['build']=build
                if not build['passed']:result.update(status='localization_stopped')
                else:
                    study.worker_deadline=study.deadline;cases=read(root/'teacher-inputs.json')['cases'];all_rows={'unchanged':[],'edited':[]}
                    for split in ('development','confirmation','preservation'):
                        for arm,model in [('unchanged',plan['models']['unchanged']),('edited',build['model'])]:
                            for case in [c for c in cases if c['split']==split]:
                                all_rows[arm].append(screen_response(study,arm,model,case));atomic(root/'TEACHER-SCREEN-RESULTS.json',all_rows)
                        support=screen_support(all_rows['unchanged'],all_rows['edited'],split)
                        passed=not support['losses'] and (bool(support['gains']) if split=='development' else support['edited_correct']>=1 if split=='confirmation' else support['base_correct']>=1)
                        atomic(root/('SCREEN-'+split.upper()+'.json'),{'passed':passed,**support})
                        if not passed:
                            result.update(status='screen_support_stopped',failed_split=split);break
                    else:result.update(status='screen_passed')
                    atomic(root/'SCREEN-GATE.json',{'passed':result['status']=='screen_passed','patch_sha256':build['model']['sha256'],'no_replacement_patch':True})
            else:result.update(paired_assignment(study))
        except BaseException as error:result.update(status='infrastructure_or_budget_stopped',error=type(error).__name__+': '+str(error))
        finally:
            if study:
                if study.vm:study.vm.close();study.vm=None
                result['budget']=study.reconcile();study.state.update(status=result['status'],phase='closed',ended_unix=time.time());study.save()
            workers=[read(p) for p in (root/'runs').glob('*/CLOSED.json')];vms=[read(p) for p in root.rglob('vm.json')]
            result.update(all_owned_workers_closed=all(w.get('owned_worker_closed') for w in workers),all_owned_vms_closed=all(v.get('owned_vm_closed') for v in vms),
                original_models_unchanged={k:sha(v['path'])==v['sha256'] for k,v in plan['models'].items() if k in ('unchanged','original_target')},second_assignment_run=False)
            if stage=='pair':
                result['endpoint_artifacts_present']={a:(root/a/'ENDPOINT.json').exists() for a in ('unchanged','edited')}
                result['infrastructure_unrun_is_missing_not_teacher_failure']=result['status']=='infrastructure_or_budget_stopped'
            atomic(root/(stage.upper()+'-RESULT.json'),result);print(json.dumps(result),flush=True)


def calibrate(project,root):
    """Actual guest execution of positive programs, including clean terminal checks."""
    project,root=Path(project).resolve(),Path(root).resolve();require(not root.exists(),'No calibration overwrite');root.mkdir()
    plan=read(project/'.data/apwt-neutral-selection-20261104-001/manifest.json');results=[]
    with desktop_lease(project):
        admission(project,root/'admission')
        for c in teacher_cases():
            ordinary=c['kind']=='ordinary';p,expected,requests,n,attempts=screen_fixture(root/c['id'],c)
            vm=None
            try:
                vm=TensorVM(project,plan['image'],root/c['id']/'vm.json',Deadline(180))
                code=('print('+c['expected']+')') if ordinary else positive_cell(c,n)
                outcome=vm.execute(code,p)
                passed=grade_teacher_case(p,expected,requests,n,attempts,c,outcome)['correct']
                results.append({'id':c['id'],'passed':bool(passed)});require(passed,'Positive calibration failed: '+c['id'])
            finally:
                if vm:vm.close()
        # Actual guest submission then exception must remain observable.
        p,_,_,_,_=fixture(root/'submit-error',teacher_cases()[0]);vm=None
        try:
            vm=TensorVM(project,plan['image'],root/'submit-error/vm.json',Deadline(180));out=vm.execute("submit()\nraise ValueError('after submit')",p)
            require(p.submitted and out['error'],'VM lost post-submission error');results.append({'id':'submission-error-preserved','passed':True})
        finally:
            if vm:vm.close()
        readonly=next(c for c in teacher_cases() if c['kind']=='test_saved')
        for label,code in [('readonly-checkpoint',"try:\n save_checkpoint('forbidden')\nexcept ValueError:\n pass\nprint(test_candidate(['dev-0','dev-1']))"),
            ('readonly-undisplayed',"r=test_candidate(['dev-0','dev-1'])")]:
            p,expected,requests,n,attempts=screen_fixture(root/label,readonly);vm=None
            try:
                vm=TensorVM(project,plan['image'],root/label/'vm.json',Deadline(180));out=vm.execute(code,p)
                measured=grade_teacher_case(p,expected,requests,n,attempts,readonly,out)
                require(not measured['correct'] and measured['correct_candidate_test_coverage'],'Read-only negative calibration failed')
                results.append({'id':label,'passed':True})
            finally:
                if vm:vm.close()
    atomic(root/'RESULT.json',{'status':'passed','controls':results,'model_tokens':0,
        'source_hashes':{n:sha(project/'evaluations'/n) for n in ('tensor_workspace_teacher_stage.py','tensor_workspace_study.py','tensor_workspace_contract.py')},
        'all_owned_vms_closed':all(read(p)['owned_vm_closed'] for p in root.rglob('vm.json'))})
    print(json.dumps({'status':'passed','controls':len(results),'model_tokens':0}))


def dispatch(command,root):
    if command in ('screen','pair'):run_stage(root,command)
    else:raise ValueError('Only explicit screen or pair stages')


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(json.dumps(prepare(*sys.argv[2:])))
    elif sys.argv[1]=='continue':print(json.dumps(prepare_continuation(*sys.argv[2:])))
    elif sys.argv[1]=='calibrate':calibrate(*sys.argv[2:])
