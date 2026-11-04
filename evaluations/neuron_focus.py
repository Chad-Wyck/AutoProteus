"""Prepare/verify a guarded, bounded one-channel study. No run is authorized by prepare."""
import ast,copy,hashlib,json,shutil,struct,sys,time
from pathlib import Path
if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from lora6k_state import read,atomic,sha,identity,exclusive
from weight_editor_runtime import require,Deadline,check_files,account_before_grading
from weight_editor_owned import launch
from tensor_workspace_errors import InfrastructureStop
from tensor_workspace_study import Study
from tensor_workspace_teacher_stage import prepare_layout,screen_response
from neuron_focus_contract import *

ARMS=('untouched','candidate','control')
SPLITS=('development','preservation','confirmation')


def extra_cases(system_prefix,tokenizer):
    cases=[]
    for kind,block,start,index in [('restore_one',14,.4813,17391),('one_weight',18,.5924,19403)]:
        a=f'blk.{block}.attn_norm.weight';b=f'blk.{block+1}.attn_norm.weight';m=f'blk.{block}.attn_qkv.weight'
        task=(f'Restore only {a} to immutable-original contents. Preserve every current value in {b} and {m}. Generate dev-0 and dev-1 on the final saved candidate and submit().' if kind=='restore_one' else
            f'In matrix {m}, set flattened index {index} to 0.359375. Preserve every other current value in all tensors. Generate dev-0 and dev-1 on the saved final candidate and submit().')
        cases.append({'id':'focus-confirmation-'+kind.replace('_','-'),'split':'confirmation','kind':kind,'block':block,'index':index,
            'base_start':start,'base_end':start+1,'initial_values':[.546875,.828125,.703125],'label':'reserved-'+str(block),'edit_value':.359375,
            'submission_policy':'required','write_policy':'allowed','display_required':False,'task':task,'lineage':'New reserved numerical variant; familiar task family, not broad generalization'})
    cases.extend([{'id':'focus-preservation-cubes','split':'preservation','kind':'ordinary','expected':'23409',
        'task':'Using Python, calculate the sum of cubes of the integers 1 through 17 inclusive. Print only the integer result. Do not use tensor or evaluation helpers.'},
        {'id':'focus-preservation-bits','split':'preservation','kind':'ordinary','expected':'1024',
        'task':'Using Python, calculate the total number of set bits in the binary representations of all integers from 0 through 255 inclusive. Print only the integer result. Do not use tensor or evaluation helpers.'}])
    for i,c in enumerate(cases):
        c['rendered_prompt']=system_prefix+'<|im_start|>user\n'+c['task']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
        c['input_ids']=tokenizer.encode(c['rendered_prompt'],add_special_tokens=False).ids;c['rng_seed']=2026110450+i
    return cases


def prepare(project,root):
    from tokenizers import Tokenizer
    project,root=Path(project).resolve(),Path(root).resolve();require(not root.exists(),'No overwrite/replay')
    parent=project/'.data/apwt-builder-teacher-20261104-003';old=read(parent/'manifest.json')
    source=project/'.data/apwt-fresh-gate-20261104-001';source_plan=read(source/'manifest.json')
    require(old['models']['unchanged']==source_plan['models']['unchanged'],'Untouched teacher lineage mismatch')
    check_files(source/'code',source_plan['code']);check_files(source,source_plan['data'])
    tokenizer=Tokenizer.from_file(str(Path(old['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
    closing=tokenizer.encode('</think>',add_special_tokens=False).ids;require(len(closing)==1,'Closing marker must be one token')
    wanted=['fresh-willow-restore-one','fresh-willow-one-weight'];frozen_by_id={c['id']:c for c in read(source/'diagnostic-inputs.json')['cases']}
    development=[];prefixes=[];lineage={str(source/'manifest.json'):sha(source/'manifest.json')}
    for request_file in sorted((source/'requests').glob('call-*.json')):
        request=read(request_file);case=request['cases'][0]
        if case['id'] not in wanted:continue
        require(request['mode']=='editor' and request['model']==old['models']['unchanged'],'Wrong baseline teacher')
        response_file=source/'runs'/request_file.stem/(case['id']+'.json');response=read(response_file)
        receipt_file=source/'runs'/request_file.stem/'RESULT.json';receipt=read(receipt_file)
        require(receipt['request_sha256']==sha(request_file) and receipt['cleanup_complete'],'Source request/closure binding')
        require(read(source/'runs'/request_file.stem/'CLOSED.json')['owned_worker_closed'],'Historical worker not closed')
        spec=copy.deepcopy(frozen_by_id[case['id']]);spec.update(case);spec['split']='development';spec['lineage']='Untouched historical unfinished development trace; exposed, not fresh confirmation'
        development.append(spec)
        for cut in PREFIX_CUTS:
            p=prefix_record(case,response,cut,tokenizer);p.update(closing_token_id=closing[0],contrast_token_id=response['tokens'][cut])
            require(p['contrast_token_id']!=closing[0] and closing[0] not in response['tokens'],'Source thought already closed')
            prefixes.append(p)
        for f in (request_file,response_file,receipt_file,source/'runs'/request_file.stem/'CLOSED.json',source/'runs'/request_file.stem/'usage.json',source/'runs'/request_file.stem/'tokens.jsonl'):
            lineage[str(f)]=sha(f)
    require(len(development)==2 and len(prefixes)==4,'Missing declared untreated failure traces')
    system=development[0]['rendered_prompt'].split('<|im_start|>user\n',1)[0]
    cases=development+extra_cases(system,tokenizer)
    require(len({c['id'] for c in cases})==6 and all(len(c['input_ids'])+8192<=34816 for c in cases),'Behavior context/case bounds')
    prepare_layout(root)
    modules=set(old['code'])|{'neuron_focus.py','neuron_focus_contract.py','neuron_focus_worker.py','neuron_focus_generate_worker.py'}
    for name in modules:shutil.copyfile(project/('controller' if name=='windows_job.py' else 'evaluations')/name,root/'code'/name)
    atomic(root/'inputs.json',{'cases':cases});atomic(root/'prefixes.json',{'prefixes':prefixes});atomic(root/'hidden-golds.json',{});atomic(root/'tensor-catalog.json',{})
    atomic(root/'SOURCE-LINEAGE.json',{'files':lineage,'untouched_teacher_sha256':old['models']['unchanged']['sha256'],'previous_edited_teacher_excluded':True})
    protocol={'phenotype':'Correct clean executed numerical task completion within8192 sampled tokens; token cost secondary on matched correct outcomes',
        'family':{'layer':LAYER,'tensor':'ffn_down','channels_per_artifact':1,'scale':STRENGTH,'canonical_entries_selected':2560,'actual_changed_scalar_count':'Measured; zeros may remain unchanged','canonical_and_deployed_relative_norm_ceiling':NORM_LIMIT,
            'why_layer26':'Bounded starting hypothesis only; previous helper-prefix localization is not evidence for a thinking locus',
            'gate_up_and_individual_Q8_scalar_edits':'Deferred; no search across intervention families or strengths'},
        'shortlist':{'maximum':2,'ranking':'Mean -0.5*h_j*(normalized readout contrast dot deployed D[:,j])/deployed-column L2 across four hooked prefix captures; positive finite scores only; descending score then ascending channel ID',
            'readout_contrast':'output_norm times (readout[closing_token]-readout[next observed historical token]); an approximate hypothesis score, not a verified gradient or causal interpretation'},
        'conditional_choice':'Both units measured on all four prefixes. Require valid FFN delta check, all four contrast-margin changes>=0 and mean>=0.001. Highest mean then lowest ID; freeze once. No replacement if unsupported.',
        'contrast':'logit[</think>]-logit[next observed historical token] at each frozen prefix; does not establish correct completion',
        'probes':{'maximum':PROBE_LIMIT,'phase_counts':PHASE_COUNTS,'context_limit':4096,'per_forward_seconds':120,
            'parity_max_abs':1e-4,'parity_relative_l2':1e-5,'ffn_delta_tolerance':'1e-4+1e-3*max(maxabs(base_ffn_out),maxabs(expected_delta))',
            'scope':'Conditional hooks affect final token only; static artifacts act throughout prefill and are evaluated in separate phases',
            'gate_instrumentation':False,'native_parity_and_tensor_delta_validation':'UNRUN; must pass within32-forward budget after separate execution authorization'},
        'control':{'artifact':'One noncompetitive single-channel control; never promotable','scale':.5,'selection':'Eight nearest nonshortlisted deployed-column norms, deterministic lower-ID ties; exact deployed FULL-matrix Q8 delta-L2 evaluated offline for this pool, choose closest to targeted delta',
            'tolerance':MATCH_TOLERANCE,'matching_failure':'Stop without enlarging pool or changing dose','not_claimed':'Equal deployed norm does not imply equal activation effect'},
        'generation':{'arms':list(ARMS),'split_cases':{s:2 for s in SPLITS},'scheduled_responses':18,'tokens_per_response':8192,'scheduled_tokens':SCHEDULED_TOKENS,
            'untouched_dev_reruns':'The first two responses ARE the untouched-development cells of18, not extra calibration samples',
            'baseline_headroom':'If both untouched development cases complete correctly, stop before probes; no replacement cases',
            'development_advance':'Candidate gains>=1 and no losses vs untouched; control never substituted',
            'preservation_advance':'At least one untouched-correct ordinary case and no candidate loss; otherwise unmeasured/fail and no confirmation',
            'confirmation_positive':'Fresh candidate gain>=1 and no candidate losses vs untouched plus passed development and preservation',
            'specificity':'Report candidate/control separately; if both improve, no targeted-channel specificity claim. Never promote control.',
            'token_partition':'Before first generated closure token, closure token itself, and after closure separately; total includes all sampled tokens',
            'context_and_sampler':'Retain pinned context allocation, thinking-enabled sampler and isolated VM route; no prompt/seed changes between arms'},
        'limits':{'scientific_seconds':10800,'sampled_tokens':TOKEN_LIMIT,'interruption_reserve':INTERRUPTION_RESERVE,'no_retries':True,
            'clock':'Begins only on separately authorized execution, includes admission/probes/CPU selection/construction/generation/grading/cleanup; review/preparation currently outside it'},
        'artifact_roster':['Immutable original4B','One eligible candidate4B copy','One nonpromotable control4B copy'],
        'student_inference':False,'automatic_follow_on':False,'fresh_confirmation_limit':'Two new numeric variants of familiar families, not broad generalization'}
    atomic(root/'protocol.json',protocol)
    background=project/'evaluations/weight-space-population-research-handoff-received-2026-11-04.md'
    atomic(root/'RESEARCH-RECEIPT.json',{'status':'Complete Researcher report received through Proteus and read by Builder','report_path':str(background),
        'report_sha256':sha(background),'original_PDF_independently_inspected_by_Builder':False,'scope_change':False,
        'application':'Preserve failures, numerical deltas, conversion, complete episode/checkpoint lineage and costs; geometry is not capability evidence',
        'excluded':'No autoencoder, learned retrieval, new training, downloads or additional inference; no direction transfer across independently trained models'})
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol','canonical_shards')}
    plan.update(publication=str(root),scope='PREPARATION ONLY: original4B one-channel study of actual unfinished thinking traces',overnight=True,numeric_policy='precise-v2',
        authority={'preparation_only':True,'execution_authorized':False,'source_thread_id':'REDACTED-PRIVATE-THREAD'},
        models={'unchanged':copy.deepcopy(old['models']['unchanged']),'original_target':copy.deepcopy(old['models']['original_target'])},
        limits={'total_seconds':10800,'editor_tokens':TOKEN_LIMIT,'cell_seconds':60},
        design={'editor_output_tokens':8192,'target_output_tokens':8192,'vm_preflight_receipt':old['design']['vm_preflight_receipt'],'vm_preflight_sha256':old['design']['vm_preflight_sha256'],
            'editor_sampling':old['design']['editor_sampling'],'no_student_inference':True,'no_shared_gpu':True})
    plan['code']={p.name:sha(p) for p in (root/'code').iterdir()};plan['controller_files']={str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')}
    plan['data']={n:sha(root/n) for n in ('inputs.json','prefixes.json','hidden-golds.json','tensor-catalog.json','SOURCE-LINEAGE.json','protocol.json','RESEARCH-RECEIPT.json')}
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\nsys.path.insert(0,str(r/'code'))\nsys.path.insert(1,str(r.parents[1]))\nfrom neuron_focus import verify,run\nif sys.argv[1:] == ['verify']: print(verify(r))\nelif sys.argv[1:] == ['run']: run(r)\nelse: raise SystemExit('Use verify or run; live execution requires separate approval.')\n",encoding='utf8')
    atomic(root/'PREPARATION-STATUS.json',{'status':'prepared_not_executed','native_probes':0,'model_loads':0,'weight_artifacts_created':0,'execution_authorized':False})
    return {'root':str(root),'identity':identity(plan),'prefix_lengths':[p['prefix_tokens'] for p in prefixes],'prefix_roundtrips':[p['decoded_prefix_roundtrips'] for p in prefixes],
        'native_probes':0,'execution_authorized':False,'future_token_ceiling':TOKEN_LIMIT}


def verify(root):
    root=Path(root);plan=read(root/'manifest.json');require(identity(plan)==(root/'manifest.sha256').read_text().strip(),'Manifest changed')
    require(Path(plan['publication']).resolve()==root.resolve(),'Frozen publication path changed')
    check_files(root/'code',plan['code']);check_files(root,plan['data']);check_files(plan['project'],plan['controller_files'])
    for path,digest in read(root/'SOURCE-LINEAGE.json')['files'].items():require(sha(path)==digest,'Historical source changed: '+path)
    require(sum(PHASE_COUNTS.values())==32 and SCHEDULED_TOKENS+INTERRUPTION_RESERVE==TOKEN_LIMIT,'Frozen budget arithmetic')
    prefixes=read(root/'prefixes.json')['prefixes'];require(len(prefixes)==4 and all(p['prefix_tokens']<=4096 and p['input_ids']==p['original_input_ids']+p['observed_generated_prefix_ids'] for p in prefixes),'Prefix contract')
    return {'status':'verified_preparation','plan_identity':identity(plan),'prefix_lengths':[p['prefix_tokens'] for p in prefixes],'execution_authorized':False}


class FocusStudy(Study):
    def __init__(self,root):
        super().__init__(root);self.category=None;self.phase_categories={}

    def reconcile(self):
        u=read(self.root/'usage.json') if (self.root/'usage.json').exists() else {'phases':{},'charged_tokens':0}
        counts={s+'_'+a:0 for s in SPLITS for a in ARMS};uncertain=0
        for key,value in u['phases'].items():
            category=self.phase_categories[key]
            if category!='probe':counts[category]+=value['observed_tokens']
            else:require(value['observed_tokens']==0,'Probe sampled output')
            uncertain+=value['uncertain_tokens_upper_bound']
        require(all(v<=2*OUTPUT_LIMIT for v in counts.values()) and uncertain<=INTERRUPTION_RESERVE and u['charged_tokens']<=TOKEN_LIMIT,'Focus budget exceeded')
        out={'observed_categories':counts,'charged_tokens':u['charged_tokens'],'uncertain_tokens':uncertain,'scheduled_tokens':SCHEDULED_TOKENS,'reserve':INTERRUPTION_RESERVE,'ceiling':TOKEN_LIMIT,'phase_categories':self.phase_categories}
        atomic(self.root/'BUDGET.json',out);return out

    def inference(self,mode,model,cases,*,remaining=8192):
        require_execution(self.root);require(mode=='editor' and len(cases)==1,'Only4B code generation; no0.8B student calls')
        bindings={'untouched':self.plan['models']['unchanged']}
        if (self.root/'MODELS-FROZEN.json').exists():bindings.update({a:v['model'] for a,v in read(self.root/'MODELS-FROZEN.json').items()})
        roles=[a for a,m in bindings.items() if m==model];require(len(roles)==1,'Unapproved/ambiguous teacher artifact')
        case=cases[0];require(case['id'] in self.by_id and case==self.by_id[case['id']],'Unfrozen generated-behavior case')
        # The shared fixture helper labels its accounting category "screen".
        # Derive the actual category from immutable case/model bindings instead.
        self.category=case['split']+'_'+roles[0]
        require(self.category in self.reconcile()['observed_categories'] and self.reconcile()['observed_categories'][self.category]+8192<=16384,'Behavior category exhausted')
        self.calls+=1;name='call-'+str(self.calls).zfill(3);path=self.root/'requests'/(name+'.json');self.phase_categories[name]=self.category;self.reconcile()
        require(not (self.root/'STOP').exists(),'Operator stop')
        atomic(path,{'mode':'editor','model':model,'cases':cases,'remaining_tokens':8192,'tokenizer':self.plan['tokenizers']['editor_tokenizer'],
            'study_context':{'phase':self.state['phase'],'editor_arm':self.arm}});atomic(self.root/'active-request.json',{'sha256':sha(path)})
        folder=self.root/'runs'/name
        try:result=launch(self.root,folder,[self.plan['interpreters']['python']['path'],str(self.root/'code/neuron_focus_generate_worker.py'),str(path)],self.deadline)
        except BaseException as e:raise InfrastructureStop('Focus generation: '+str(e)) from e
        finally:
            if (folder/'usage.json').exists():account_before_grading(self.root/'usage.json',name,folder,read(folder/'usage.json')['binding'])
            self.reconcile()
        require(result['request_sha256']==sha(path),'Response binding mismatch')
        return [read(folder/(c['id']+'.json')) for c in cases]

    def probes(self,phase,conditions,model):
        require_execution(self.root);before=read(self.root/'PROBE-ADMISSION.json')['admitted_total'] if (self.root/'PROBE-ADMISSION.json').exists() else 0
        request={'phase':phase,'conditions':conditions,'model':model};validate_probe_request(self.plan,request,before)
        name='probe-'+phase;path=self.root/'requests'/(name+'.json');require(not path.exists(),'No probe phase replay')
        require(not (self.root/'STOP').exists(),'Operator stop')
        atomic(path,request);atomic(self.root/'active-request.json',{'sha256':sha(path)})
        atomic(self.root/'PROBE-ADMISSION.json',{'before_this_phase':before,'admitted_total':before+len(conditions),'phase':phase})
        self.phase_categories[name]='probe';self.reconcile();folder=self.root/'runs'/name
        try:result=launch(self.root,folder,[self.plan['interpreters']['python']['path'],str(self.root/'code/neuron_focus_worker.py'),str(path)],self.deadline)
        except BaseException as e:raise InfrastructureStop('Focus probe: '+str(e)) from e
        finally:
            if (folder/'usage.json').exists():account_before_grading(self.root/'usage.json',name,folder,read(folder/'usage.json')['binding'])
            self.reconcile()
        require(result['request_sha256']==sha(path),'Probe response binding');return result['rows']


def _conditions(prefixes,phase,modes=None,channels=None):
    if channels is not None:return [{'id':phase+'-'+str(j)+'-'+p['id'],'prefix_id':p['id'],'mode':'channel','channel':j} for j in channels for p in prefixes]
    return [{'id':phase+'-'+mode+'-'+p['id'],'prefix_id':p['id'],'mode':mode} for mode in modes for p in prefixes]


def _deployed(plan):
    check_files(plan['cpu_vendor_sources']['path'],plan['cpu_vendor_sources']['files']);sys.path.insert(0,plan['cpu_vendor_sources']['path'])
    from gguf import GGUFReader
    from gguf.quants import dequantize
    reader=GGUFReader(plan['models']['unchanged']['path']);ts={t.name:t for t in reader.tensors};t=ts[f'blk.{LAYER}.ffn_down.weight']
    return reader,ts,dequantize(t.data,t.tensor_type)


def shortlist(study,baselines,prefixes):
    reader,ts,w=_deployed(study.plan)
    from gguf.quants import dequantize
    head=ts.get('output.weight',ts.get('token_embd.weight'));norm=dequantize(ts['output_norm.weight'].data,ts['output_norm.weight'].tensor_type).reshape(-1)
    require(w.shape==(2560,9216),'Wrong fixed-layer matrix')
    scores=np.zeros(9216,dtype=np.float64);column_norms=np.linalg.norm(w.astype(np.float64),axis=0)
    for p in prefixes:
        row=next(r for r in baselines if r['prefix_id']==p['id'] and r['mode']=='capture')
        with np.load(row['capture'],allow_pickle=False) as a:h=a[f'ffn_swiglu-{LAYER}'].astype(np.float64)
        readout=[dequantize(head.data[i:i+1],head.tensor_type).reshape(-1) for i in (p['closing_token_id'],p['contrast_token_id'])]
        direction=norm.astype(np.float64)*(readout[0].astype(np.float64)-readout[1].astype(np.float64));direction/=max(1e-12,np.linalg.norm(direction))
        scores+=-.5*h*(direction@w)/np.maximum(column_norms,1e-12)
    scores/=len(prefixes);eligible=[j for j in range(9216) if np.isfinite(scores[j]) and scores[j]>0 and column_norms[j]>1e-12]
    require(len(eligible)>=2,'No two positive hypothesis scores; stop, no layer/family expansion')
    channels=sorted(eligible,key=lambda j:(-scores[j],j))[:2]
    atomic(study.root/'SHORTLIST.json',{'channels':channels,'ranking':'Frozen mean approximate readout effect per column norm; hypothesis only','scores':{str(j):float(scores[j]) for j in channels}})
    return channels,w


def norm_and_artifacts(study,channel,excluded):
    check_files(study.plan['cpu_vendor_sources']['path'],study.plan['cpu_vendor_sources']['files']);sys.path.insert(0,study.plan['cpu_vendor_sources']['path'])
    from weight_editor_targeted import q8_column_edit,build_candidate
    from gguf import GGUFReader,GGMLQuantizationType
    from gguf.quants import quantize,dequantize
    root=study.root;plan=study.plan;hf=Path(plan['tokenizers']['editor_tokenizer']['path']);key=f'model.language_model.layers.{LAYER}.mlp.down_proj.weight'
    source=hf/read(hf/'model.safetensors.index.json')['weight_map'][key];require(sha(source)==plan['canonical_shards'][source.name],'Canonical shard changed')
    with source.open('rb') as f:n=struct.unpack('<Q',f.read(8))[0];info=json.loads(f.read(n))[key]
    require(info['dtype']=='BF16' and info['shape']==[2560,9216],'Canonical layout')
    bits=np.memmap(source,dtype='<u2',mode='r',offset=8+n+info['data_offsets'][0],shape=(2560,9216));original=(bits.astype(np.uint32)<<16).view(np.float32)
    encoded_base=quantize(original,GGMLQuantizationType.Q8_0);reader=GGUFReader(plan['models']['unchanged']['path']);t=next(t for t in reader.tensors if t.name==f'blk.{LAYER}.ffn_down.weight')
    require(np.array_equal(encoded_base,t.data),'No-edit Q8 reconstruction failed');deployed=dequantize(encoded_base,GGMLQuantizationType.Q8_0)
    base_norm=float(np.linalg.norm(deployed.astype(np.float64)));column_norms=np.linalg.norm(deployed.astype(np.float64),axis=0)
    def measure(j):
        changed=q8_column_edit(original,[j],.5);encoded=quantize(changed,GGMLQuantizationType.Q8_0);actual=dequantize(encoded,GGMLQuantizationType.Q8_0)
        return weight_delta_statistics(original,changed,deployed,actual,j)
    target=measure(channel);require(0<target['deployed_relative_l2']<=NORM_LIMIT and target['canonical_relative_l2']<=NORM_LIMIT,'Candidate does not survive/fit frozen norm bound')
    pool=sorted((j for j in range(9216) if j not in excluded),key=lambda j:(abs(column_norms[j]-column_norms[channel]),j))[:8]
    measured=[measure(j) for j in pool];match=match_control(target['deployed_delta_l2'],measured,excluded)
    atomic(root/'CONTROL-NORM.json',{'target':target,'pool':measured,'match':match,'behavior_used_to_select_control':False})
    require(match['matched'],'No5%-matched norm control; stop without expanding pool/dose')
    control=next(x for x in measured if x['channel']==match['channel']);require(control['deployed_relative_l2']<=NORM_LIMIT and control['canonical_relative_l2']<=NORM_LIMIT,'Control norm bound')
    atomic(root/'SELECTION.json',{'candidate_channel':channel,'control_channel':match['channel'],'choice_sha256':sha(root/'CHANNEL-CHOICE.json'),'control_promotable':False})
    models={}
    for role,j,stats in [('candidate',channel,target),('control',match['channel'],control)]:
        proposal=validate_proposal({'layer':LAYER,'columns':[j],'scale':.5});model=build_candidate(plan,proposal,root/'artifacts'/role,study.deadline)
        models[role]={'model':model,'proposal':proposal,'statistics':stats,'promotable':role=='candidate','numeric_manifest_sha256':sha(root/'artifacts'/role/'MANIFEST.json')}
    atomic(root/'MODELS-FROZEN.json',models);return models


def behavioral(study,split,models,results,arms=ARMS):
    closing=read(study.root/'prefixes.json')['prefixes'][0]['closing_token_id']
    for arm in arms:
        study.category=split+'_'+arm
        for case in [c for c in study.cases if c['split']==split]:
            require(sha(models[arm]['path'])==models[arm]['sha256'],'Frozen teacher changed')
            row=screen_response(study,arm,models[arm],case)
            req=study.root/'runs'/('call-'+str(study.calls).zfill(3))/(case['id']+'.json');response=read(req);row.update(token_partition(response,closing))
            results.setdefault(split,{}).setdefault(arm,[]).append(row);atomic(study.root/'BEHAVIOR-RESULTS.json',results)


def execute(study):
    root=study.root;prefixes=read(root/'prefixes.json')['prefixes'];base=study.plan['models']['unchanged'];models={'untouched':base};results={}
    behavioral(study,'development',models,results,arms=('untouched',))
    if all(r['correct'] for r in results['development']['untouched']):return {'status':'baseline_ceiling_stop','reason':'No untreated completion headroom; no replacement cases'}
    baselines=study.probes('baseline',_conditions(prefixes,'baseline',modes=('no_hook','capture','noop')),base);parity=[]
    for p in prefixes:
        rows={r['mode']:r for r in baselines if r['prefix_id']==p['id']}
        with np.load(rows['no_hook']['capture'],allow_pickle=False) as a:reference=a['logits']
        for mode in ('capture','noop'):
            with np.load(rows[mode]['capture'],allow_pickle=False) as a:check=parity_check(reference,a['logits'])
            parity.append({'prefix':p['id'],'mode':mode,**check})
    atomic(root/'PARITY.json',parity);require(all(x['passed'] for x in parity),'Native hook/noop parity failed; no tolerance tuning')
    channels,w=shortlist(study,baselines,prefixes);rows=study.probes('channels',_conditions(prefixes,'channels',channels=channels),base)
    for row in rows:
        reference=next(r for r in baselines if r['mode']=='capture' and r['prefix_id']==row['prefix_id'])
        with np.load(reference['capture'],allow_pickle=False) as a:h=a[f'ffn_swiglu-{LAYER}'];out=a[f'ffn_out-{LAYER}']
        with np.load(row['capture'],allow_pickle=False) as a:
            require(parity_check(h,a[f'ffn_swiglu-{LAYER}'])['passed'],'Conditional pre-intervention input changed')
            row['delta_validation']=channel_delta_check(h[row['channel']],out,a[f'ffn_out-{LAYER}'],w[:,row['channel']])
        row['reference_contrast_margin']=reference['contrast_margin'];row['contrast_margin_delta']=row['contrast_margin']-reference['contrast_margin']
    choice=choose_channel(rows);atomic(root/'CHANNEL-EFFECTS.json',rows);atomic(root/'CHANNEL-CHOICE.json',choice)
    if not choice['supported']:return {'status':'conditional_support_stop','choice':choice}
    artifacts=norm_and_artifacts(study,choice['channel'],channels);selection=read(root/'SELECTION.json')
    control=study.probes('coordinate_control',_conditions(prefixes,'control',channels=[selection['control_channel']]),base)
    for row in control:
        reference=next(r for r in baselines if r['mode']=='capture' and r['prefix_id']==row['prefix_id'])
        with np.load(reference['capture'],allow_pickle=False) as a:h=a[f'ffn_swiglu-{LAYER}'];out=a[f'ffn_out-{LAYER}']
        with np.load(row['capture'],allow_pickle=False) as a:
            require(parity_check(h,a[f'ffn_swiglu-{LAYER}'])['passed'],'Control conditional input changed')
            row['delta_validation']=channel_delta_check(h[row['channel']],out,a[f'ffn_out-{LAYER}'],w[:,row['channel']])
        row['reference_contrast_margin']=reference['contrast_margin'];row['contrast_margin_delta']=row['contrast_margin']-reference['contrast_margin']
    require(all(r['delta_validation']['passed'] for r in control),'Control channel tensor identity/delta check failed')
    atomic(root/'CONTROL-CONDITIONAL.json',control)
    for arm in ('candidate','control'):
        rows=study.probes('static_'+arm,_conditions(prefixes,'static-'+arm,modes=('capture',)),artifacts[arm]['model'])
        atomic(root/('STATIC-'+arm.upper()+'.json'),rows)
    models.update({a:v['model'] for a,v in artifacts.items()})
    behavioral(study,'development',models,results,arms=('candidate','control'))
    dev=behavior_comparison(results['development']['untouched'],results['development']['candidate']);atomic(root/'DEVELOPMENT-GATE.json',dev)
    if not dev['useful_completion_support']:return {'status':'development_support_stop','development':dev}
    behavioral(study,'preservation',models,results)
    preserved=behavior_comparison(results['preservation']['untouched'],results['preservation']['candidate'])
    if not preserved['original_correct'] or preserved['losses']:return {'status':'preservation_stop','preservation':preserved,'unmeasured':not bool(preserved['original_correct'])}
    behavioral(study,'confirmation',models,results)
    conf=behavior_comparison(results['confirmation']['untouched'],results['confirmation']['candidate'])
    attribution=final_attribution(results['confirmation']['untouched'],results['confirmation']['candidate'],results['confirmation']['control'])
    return {'status':'completed','positive_narrow_teacher_effect':conf['useful_completion_support'],'confirmation':conf,'attribution':attribution,
        'control_is_not_a_replacement_candidate':True,
        'claim':'One development-selected teacher patch, narrow reserved numerical variants; no semantic-neuron or0.8B repair claim','student_inference':False,'automatic_follow_on':False}


def run(root):
    root=Path(root).resolve();require_execution(root);verify(root);plan=read(root/'manifest.json')
    from tensor_workspace_overnight import desktop_lease,admission
    require(not (root/'RUN-STARTED.json').exists(),'Single scientific attempt; no automatic relaunch')
    with desktop_lease(plan['project']),exclusive(root):
        began=time.time();atomic(root/'RUN-STARTED.json',{'began_unix':began,'end_unix':began+10800});deadline=Deadline(10800);study=None
        result={'status':'starting','student_inference':False}
        try:
            admission(plan['project'],root/'admission');study=FocusStudy(root);study.deadline=deadline;study.worker_deadline=deadline;result.update(execute(study))
        except BaseException as e:result.update(status='bounded_or_infrastructure_stop',error=type(e).__name__+': '+str(e))
        finally:
            if study:
                if study.vm:study.vm.close()
                result['budget']=study.reconcile();study.state.update(status=result['status'],phase='closed',ended_unix=time.time());study.save()
            result.update(elapsed_seconds=time.time()-began,student_inference=False,automatic_follow_on=False,
                all_owned_workers_closed=all(read(p)['owned_worker_closed'] for p in (root/'runs').glob('*/CLOSED.json')),
                all_owned_vms_closed=all(read(p)['owned_vm_closed'] for p in root.rglob('vm.json')),
                originals_unchanged={k:sha(v['path'])==v['sha256'] for k,v in plan['models'].items()})
            atomic(root/'RESULT.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(json.dumps(prepare(*sys.argv[2:])))
    elif sys.argv[1]=='verify':print(json.dumps(verify(Path(sys.argv[2]))))
    elif sys.argv[1]=='run':run(Path(sys.argv[2]))
