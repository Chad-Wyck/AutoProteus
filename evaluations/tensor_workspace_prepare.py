"""Freeze a separate matched tensor-workspace pilot; preparation is CPU-only."""
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys

from lora6k_state import atomic,read,sha,identity
from weight_editor_prepare import normalized
from weight_editor_runtime import require,check_files
from weight_repair_protocol import PROTOCOL,extract_answer

MODULES=['tensor_workspace_worker.py','tensor_workspace_policy.py','tensor_workspace_vm.py','tensor_workspace_study.py','tensor_workspace_report.py','tensor_workspace_feedback.py',
    'weight_editor_native.py','weight_editor_trace.py','weight_editor_worker.py','weight_editor_owned.py',
    'weight_editor_sparse.py','weight_editor_runtime.py','lora6k_state.py','lora6k_supervisor.py','weight_repair_protocol.py']


def prepare(project,folder):
    import pyarrow.parquet as pq
    from tokenizers import Tokenizer
    project,folder=Path(project).resolve(),Path(folder).resolve();require(not folder.exists(),'Never overwrite a frozen pilot')
    old=read(project/'.data/manual4b-localprojection-pair-20261103/manifest.json');assets=project/'.data/weight-repair-20261102'
    train_path=assets/'gpu-readiness-001/math-train.parquet';bench_path=assets/'acquisition-001/assets/dataset/math500.jsonl'
    require(sha(train_path)==old['dataset_sources']['train_sha256'] and sha(bench_path)==old['dataset_sources']['benchmark_sha256'],'Pinned data changed')
    train=pq.read_table(train_path).to_pylist();bench=[json.loads(line) for line in bench_path.read_text(encoding='utf8').splitlines()]
    bench_keys={normalized(r['problem']) for r in bench};prior=set()
    def collect(v):
        if isinstance(v,dict):
            if isinstance(v.get('problem'),str):prior.add(normalized(v['problem']))
            if isinstance(v.get('rendered_prompt'),str) and '<|im_start|>user\n' in v['rendered_prompt']:
                problem=v['rendered_prompt'].split('<|im_start|>user\n',1)[1].split('<|im_end|>',1)[0].removesuffix('\n'+PROTOCOL['instruction'])
                prior.add(normalized(problem))
            for child in v.values():collect(child)
        elif isinstance(v,list):
            for child in v:collect(child)
    for pattern in ('weight-*/**/*inputs*.json','manual4b-*/**/*inputs*.json','host-closing-*/**/*inputs*.json'):
        for p in (project/'.data').glob(pattern):
            if p.stat().st_size<=5*1024**2:
                try:collect(read(p))
                except (ValueError,KeyError):pass
    eligible={}
    for i,row in enumerate(train):
        key=normalized(row['problem'])
        if key not in bench_keys and key not in prior and extract_answer(row['solution']):eligible.setdefault(key,(i,row))
    selected=random.Random(2026110308).sample(list(eligible.values()),12)
    hidden=random.Random(2026110309).sample([r for r in sorted(bench,key=lambda r:r['unique_id']) if normalized(r['problem']) not in prior],4)
    tokenizer=Tokenizer.from_file(str(Path(old['tokenizers']['target_tokenizer']['path'])/'tokenizer.json'))
    cases=[];golds={}
    for split,items in [('dev',selected[:8]),('confirmation',selected[8:]),('heldout',[(r['unique_id'],r) for r in hidden])]:
        for number,(index,row) in enumerate(items):
            name=split+'-'+str(number);prompt='<|im_start|>user\n'+row['problem']+'\n'+PROTOCOL['instruction']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
            ids=tokenizer.encode(prompt,add_special_tokens=False).ids;require(len(ids)+32768<=34816,'No context trimming allowed')
            cases.append({'id':name,'split':split,'source_id':index,'problem':row['problem'],'rendered_prompt':prompt,'input_ids':ids,
                'rng_seed':int.from_bytes(hashlib.sha256(('tensor-workspace:'+name).encode()).digest()[:4],'little')})
            golds[name]=row['answer'] if split=='heldout' else extract_answer(row['solution'])
    folder.mkdir();(folder/'code').mkdir();(folder/'requests').mkdir();(folder/'runs').mkdir()
    for name in MODULES:shutil.copyfile(project/'evaluations'/name,folder/'code'/name)
    shutil.copyfile(project/'controller/windows_job.py',folder/'code/windows_job.py')
    from tensor_workspace_policy import catalog
    check_files(old['cpu_vendor_sources']['path'],old['cpu_vendor_sources']['files']);sys.path.insert(0,old['cpu_vendor_sources']['path'])
    records=catalog(old['models']['original_target']['path'],24)
    models={'original_target':old['models']['original_target'],'unchanged':old['models']['editor_model'],
        'manual':{'path':str(project/'.data/manual4b-boost-20261103/artifacts/layer29/model-q8.gguf'),
            'sha256':'5bc81347e574a2fc1bc7755f148d42dd480d6f2344ebc3a923dc6ed250f886ea'}}
    for row in models.values():require(sha(row['path'])==row['sha256'],'Pinned model changed')
    atomic(folder/'inputs.json',{'cases':cases});atomic(folder/'hidden-golds.json',golds);atomic(folder/'tensor-catalog.json',records)
    image=read(project/'.data/tensor-workspace-20261103/image/image.json')
    plan={'schema':1,'scope':'Matched arbitrary tensor editing of original 0.8B by unchanged versus manually boosted 4B Q8',
        'project':str(project),'code':{p.name:sha(p) for p in (folder/'code').iterdir()},
        'controller_files':{str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')},
        'data':{n:sha(folder/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json')},
        'models':models,'image':image,'tokenizers':old['tokenizers'],'engine':old['engine'],'engine_files':old['engine_files'],
        'interpreters':old['interpreters'],'cpu_vendor_sources':old['cpu_vendor_sources'],'target_protocol':PROTOCOL,
        'limits':{'total_seconds':28800,'arm_seconds':7200,'editor_calls':48,'forward_calls':8,'editor_tokens':196608,
            'development_generated_tokens':524288,'qualification_generated_tokens':1048576,'cell_seconds':60,'tensor_bytes':67108864,
            'patch_bytes':536870912,'transfer_bytes':2147483648},
        'design':{'arms':['unchanged','manual'],'development_cases':8,'confirmation_cases':4,'heldout_cases':4,
            'fresh_original_each_arm':True,'shared_initial_baseline_ids':['dev-0','dev-1'],
            'initial_baseline_frozen_before_edits':True,'confirmation_and_heldout_hidden':True,'prior_inputs_excluded':True,
            'selection_seed':2026110308,'hidden_seed':2026110309,'target_output_tokens':32768,'editor_output_tokens':8192,
            'editor_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'thinking':True},
            'target_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'generated_only_presence':1.5},
            'no_gradients_training_or_optimizers':True,'no_published_repair_or_preset_directions':True,
            'numeric_host_broker_only':True,'vm_preflight_receipt':str(project/'.data/tensor-workspace-20261103/preflight-008/RESULT.json'),
            'promotion_rule':'No deployment. Report development and independent correctness/preservation separately; small pilot, no broad capability claim.'}}
    atomic(folder/'manifest.json',plan);(folder/'manifest.sha256').write_text(identity(plan));atomic(folder/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(plan),'explicit_user_authorization':False})
    return {'manifest_sha256':identity(plan),'tensors':len(records),'cases':len(cases),'excluded_prior_problems':len(prior)}


def prepare_followup(project,prior,folder,image_directory,preflight):
    """Same frozen cases/models/limits; new common interface, verified shared controls."""
    import copy
    from weight_editor_runtime import usage
    project,prior,folder,image_directory,preflight=map(lambda p:Path(p).resolve(),(project,prior,folder,image_directory,preflight))
    old=read(prior/'manifest.json');require(identity(old)==(prior/'manifest.sha256').read_text().strip(),'Prior plan changed')
    require(read(prior/'runner.json')['status']=='completed' and read(prior/'RESULT.json')['status']=='completed','Prior study must finish before follow-up publication')
    require((prior/'CLOSED-REPORT.json').is_file() and read(prior/'CLOSED-REPORT.json')['all_owned_native_workers_closed'],'Prior native workers not closed')
    require(all(read(prior/a/'vm.json')['owned_vm_closed'] for a in old['design']['arms']),'Prior VM not closed')
    require(read(preflight)['status']=='passed' and read(preflight)['vm_closed'],'Revised actual-VM controls required')
    require(not folder.exists(),'Never overwrite a publication');check_files(prior,old['data'])
    for name in ('tensor_workspace_worker.py','weight_editor_native.py','weight_editor_worker.py','weight_repair_protocol.py'):
        require(sha(project/'evaluations'/name)==old['code'][name],'Sampling or grading changed; not an interface-only comparison')
    baseline=read(prior/'baseline-results.json');cases={c['id']:c for c in read(prior/'inputs.json')['cases']}
    control_root=Path(old.get('qualification_continuation',{}).get('root',str(prior))).resolve()
    control_plan=read(control_root/'manifest.json')
    require(control_plan['models']==old['models'] and control_plan['data']==old['data'],'Original-control source differs from completed qualification')
    required=set(old['design']['shared_initial_baseline_ids'])|{i for i,c in cases.items() if c['split']!='dev'}
    require(required<=set(baseline),'Missing prior original control coverage')
    evidence={};checked_phases={}
    def pin(path):
        p=Path(path).resolve();require(p.is_relative_to(control_root),'Control evidence outside original-control publication')
        evidence[str(p.relative_to(control_root))]=sha(p)
    for name in ('manifest.json','baseline-results.json','CLOSED-REPORT.json'):pin(control_root/name)
    for name in sorted(required):
        row=baseline[name];response_path=Path(row['response_file']).resolve();require(response_path.is_relative_to(control_root/'runs'),'Unexpected control response path')
        run=response_path.parent;call=run.name;request_path=control_root/'requests'/(call+'.json');request=read(request_path)
        require(request['mode']=='generate' and request['model']==old['models']['original_target'],'Not an original target control')
        require(next(c for c in request['cases'] if c['id']==name)==cases[name],'Control prompt/seed mismatch')
        if call not in checked_phases:
            closed,result,ledger=read(run/'CLOSED.json'),read(run/'RESULT.json'),read(run/'usage.json')
            require(closed['status']=='completed' and closed['owned_worker_closed'] and not closed['guard']
                and result['status']=='completed' and result['cleanup_complete'] and result['request_sha256']==sha(request_path)
                and result['token']==closed['token']==ledger['binding']['nonce'],'Incomplete original inference closure')
            measured=usage(run,ledger['binding']);require(measured['measurement_complete'],'Partial original control usage')
            checked_phases[call]=measured
            for path in (request_path,run/'CLOSED.json',run/'RESULT.json',run/'usage.json',run/'tokens.jsonl',run/'checked.json'):pin(path)
        response=read(response_path);require(response['status']=='completed' and response['generated_tokens']==checked_phases[call]['per_case'][name]
            and response['finish_reason']==row['finish_reason'],'Original response/usage mismatch');pin(response_path)
    folder.mkdir();(folder/'code').mkdir();(folder/'requests').mkdir();(folder/'runs').mkdir()
    for name in MODULES:shutil.copyfile(project/'evaluations'/name,folder/'code'/name)
    shutil.copyfile(project/'controller/windows_job.py',folder/'code/windows_job.py')
    for name in old['data']:shutil.copyfile(prior/name,folder/name)
    plan=copy.deepcopy(old);plan.update(scope='Interface-only follow-up: explicit candidate testing, evaluated-weight receipts and guest final-expression display',
        code={p.name:sha(p) for p in (folder/'code').iterdir()},image=read(image_directory/'image.json'))
    plan.pop('qualification_continuation',None)
    plan['predecessor_completion']={'root':str(prior),'files':{n:sha(prior/n) for n in ('manifest.json','RESULT.json','CLOSED-REPORT.json')}}
    plan['design'].update(vm_preflight_receipt=str(preflight),vm_preflight_sha256=sha(preflight),
        prior_plan_sha256=identity(old),interface_changes=['Explicit test_candidate / inspect_candidate / compare_with_original helpers',
        'Final expression displayed inside guest','Host-owned weight/revision/cache receipts'])
    plan['baseline_import']={'root':str(control_root),'files':evidence,'ids':sorted(required),
        'policy':'Exact same original weights, prompts, seeds, tokenizer, sampler and qualified runtime; complete raw responses/usage/closure pinned. No candidate results or hidden outcomes enter editor feedback.'}
    require(plan['models']==old['models'] and plan['limits']==old['limits'] and plan['data']==old['data'],'Matched controls changed')
    atomic(folder/'manifest.json',plan);(folder/'manifest.sha256').write_text(identity(plan))
    atomic(folder/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(plan),'explicit_user_authorization':False})
    return {'manifest_sha256':identity(plan),'shared_original_control_cases':len(required)}


if __name__=='__main__':print(prepare(*sys.argv[1:]))
