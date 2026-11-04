"""Four frozen matched responses: supported thinking-on/off template modes."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from lora6k_state import atomic,read,sha,identity,exclusive
from tensor_workspace_overnight import fixture,desktop_lease,admission,AUTHORIZATION
from tensor_workspace_fresh_gate import briefs,explicit_grade
from tensor_workspace_study import Study,code_cell
from tensor_workspace_vm import TensorVM
from tensor_workspace_vm_startup import bound_serial
from tensor_workspace_errors import InfrastructureStop,CellAllowanceExceeded
from weight_editor_runtime import require,Deadline,check_files

LIMIT=32768
SECONDS=1200


def tasks():
    return [
        {'id':'mode-maple-selective','kind':'restore_one','block':4,'index':0,'label':'maple',
         'base_start':.1921,'base_end':1.1023,'initial_values':[.609375,.859375,.734375],
         'task':'Restore only blk.4.attn_norm.weight to its immutable original values. Preserve the saved edits in blk.5.attn_norm.weight and blk.4.attn_qkv.weight exactly. Generate dev-0 and dev-1 using the resulting candidate, then submit().'},
        {'id':'mode-juniper-element','kind':'one_weight','block':20,'index':12301,'edit_value':.296875,'label':'juniper',
         'base_start':.2789,'base_end':1.1456,'initial_values':[.53125,.90625,.71875],
         'task':'In matrix blk.20.attn_qkv.weight, set flattened index 12301 to 0.296875. Preserve every other value of all three tensors exactly. Generate dev-0 and dev-1 using the saved final candidate, then submit().'}]


def render(template,messages,thinking_enabled):
    return template.render(messages=messages,add_generation_prompt=True,enable_thinking=thinking_enabled,tools=None)


def prepare(project,root,infrastructure):
    import jinja2
    from tokenizers import Tokenizer
    project,root,infrastructure=map(lambda x:Path(x).resolve(),(project,root,infrastructure))
    require(not root.exists(),'No overwrite or retry')
    gate=read(infrastructure/'INFRASTRUCTURE-GATE.json')
    require(gate['status']=='passed' and gate['cold_boots']<=3 and gate['investigation_seconds']<=600,'Cold-boot verification required')
    old=read(project/'.data/apwt-fresh-gate-20261104-001/manifest.json')
    template_path=Path(old['tokenizers']['editor_tokenizer']['path'])/'chat_template.jinja'
    check_files(old['tokenizers']['editor_tokenizer']['path'],old['tokenizers']['editor_tokenizer']['files'])
    template=jinja2.Environment().from_string(template_path.read_text(encoding='utf8'))
    tok=Tokenizer.from_file(str(Path(old['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
    brief=briefs(project)['explicit'];variants=tasks()
    for c in variants:c.update(split='mode-comparison',submission_policy='required',write_policy='allowed',display_required=False)
    schedule=[]
    for enabled,index in [(True,0),(False,0),(False,1),(True,1)]:
        c=copy.deepcopy(variants[index]);c['thinking_enabled']=enabled;c['mode']='thinking-on' if enabled else 'thinking-off'
        c['messages']=[{'role':'system','content':brief},{'role':'user','content':c['task']}]
        c['rendered_prompt']=render(template,c['messages'],enabled)
        suffix='<|im_start|>assistant\n<think>\n' if enabled else '<|im_start|>assistant\n<think>\n\n</think>\n\n'
        require(c['rendered_prompt'].endswith(suffix),'Pinned template does not support requested mode')
        c['input_ids']=tok.encode(c['rendered_prompt'],add_special_tokens=False).ids
        c['rng_seed']=int.from_bytes(hashlib.sha256(('apwt-thinking-mode-v1:'+c['id']).encode()).digest()[:4],'little')
        schedule.append(c)
    for name in {c['id'] for c in schedule}:
        pair=[c for c in schedule if c['id']==name]
        require(pair[0]['messages']==pair[1]['messages'] and pair[0]['rng_seed']==pair[1]['rng_seed'],'Unmatched mode pair')
        body0=pair[0]['rendered_prompt'].split('<|im_start|>assistant\n',1)[0]
        body1=pair[1]['rendered_prompt'].split('<|im_start|>assistant\n',1)[0]
        require(body0==body1,'Mode changed system/user content')
    direct='```python\nprint(1)\n```'
    require(code_cell(direct,thinking_enabled=False)[0]=='print(1)\n','Disabled parser requires generated closing tag')
    require(code_cell('reason</think>\n'+direct,thinking_enabled=True)[0]=='print(1)\n','Enabled parser control failed')
    try:code_cell(direct,thinking_enabled=True)
    except ValueError:on_requires_closure=True
    else:on_requires_closure=False
    require(on_requires_closure,'Thinking-enabled contract unexpectedly weakened')
    root.mkdir();(root/'code').mkdir();(root/'runs').mkdir();(root/'requests').mkdir()
    names=set(old['code'])|{'tensor_workspace_vm_startup.py','tensor_workspace_thinking_comparison.py'}
    for name in names:shutil.copyfile(project/('controller' if name=='windows_job.py' else 'evaluations')/name,root/'code'/name)
    atomic(root/'inputs.json',{'cases':variants});atomic(root/'hidden-golds.json',{});atomic(root/'tensor-catalog.json',{})
    atomic(root/'schedule.json',schedule);atomic(root/'brief.json',{'common_brief':brief})
    atomic(root/'PARSER-TEMPLATE-CONTROLS.json',{'status':'passed','template_path':str(template_path),'template_sha256':sha(template_path),
        'jinja2':jinja2.__version__,'disabled_direct_code_without_generated_think_closure':True,'enabled_requires_generated_closure':True,
        'mode_suffixes':{'on':'<think>\n','off':'<think>\n\n</think>\n\n'},'system_user_messages_matched':True,
        'model_loading':False,'sampled_tokens':0})
    atomic(root/'AUTHORIZATION.json',{'explicit_user_authorization':False,'user_instruction':AUTHORIZATION,
        'source_thread_id':'REDACTED-PRIVATE-THREAD','scope':'Proteus-approved Critic follow-up: three cold boots first; four unchanged-editor responses, two fresh tasks paired across supported thinking on/off; no retries or pilot',
        'sampled_tokens':LIMIT,'seconds':SECONDS,'no_pilot':True})
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','models','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol')}
    plan.update(scope='Four-response matched supported thinking-mode comparison',overnight=True,numeric_policy='precise-v2',
        code={p.name:sha(p) for p in (root/'code').iterdir()},controller_files={str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')},
        data={n:sha(root/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json','schedule.json','brief.json','PARSER-TEMPLATE-CONTROLS.json','AUTHORIZATION.json')},
        limits={'total_seconds':SECONDS,'sampled_tokens':LIMIT,'responses':4,'cell_seconds':60},
        design={'vm_preflight_receipt':str(infrastructure/'INFRASTRUCTURE-GATE.json'),
            'vm_preflight_sha256':sha(infrastructure/'INFRASTRUCTURE-GATE.json'),
            'target_output_tokens':8192,'editor_output_tokens':8192,'only_model':'unchanged',
            'editor_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'thinking':'varied only by pinned chat template'},
            'vm_bridge_seconds':gate['bridge_seconds'],'vm_readiness_seconds':gate['readiness_seconds'],
            'no_retries':True,'no_pilot':True,'fixed_order':[(c['mode'],c['id']) for c in schedule],
            'purpose':'Small feasibility comparison; no generalization or unique-cause attribution',
            'template_sha256':sha(template_path),'startup_timeout_adjustments':gate['timeout_adjustments']})
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\np=json.loads((r/'manifest.json').read_text())\nsys.path.insert(0,p['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_thinking_comparison import run\nrun(r)\n",encoding='utf8')
    return {'root':str(root),'plan_identity':identity(plan),'responses':4,'token_ceiling':LIMIT,'seconds':SECONDS}


def run(root):
    root=Path(root).resolve();plan=read(root/'manifest.json');began=time.monotonic()
    with desktop_lease(plan['project']),exclusive(root):
        require(not (root/'runner.json').exists() and not (root/'RESULT.json').exists(),'No model-response retry')
        result={'status':'starting','rows':[]};study=None;vm=None
        try:
            admission(plan['project'],root/'admission');study=Study(root)
            study.deadline=Deadline(end=began+SECONDS);study.worker_deadline=study.deadline
            for number,c in enumerate(read(root/'schedule.json')):
                require(number<4,'Four-response ceiling')
                used=read(root/'usage.json')['charged_tokens'] if (root/'usage.json').exists() else 0
                require(used+8192<=LIMIT,'Sampled-token ceiling')
                study.arm=c['mode'];study.state.update(phase='thinking_mode_comparison',case=c['id'],mode=c['mode']);study.save()
                response=study.inference('editor',plan['models']['unchanged'],[c],remaining=8192)[0]
                folder=root/c['mode']/c['id'];folder.parent.mkdir(exist_ok=True)
                p,expected,requests,n,_=fixture(folder,c);vm=None;outcome={'error':'No executable cell','output':''}
                row={'id':c['id'],'mode':c['mode'],'thinking_enabled_requested':c['thinking_enabled'],
                    'generated_tokens':response['generated_tokens'],'finish_reason':response['finish_reason'],
                    'generated_think_closure_present':'</think>' in response['raw_text']}
                try:
                    require(response['finish_reason']=='eos','Generation truncated; no code executed')
                    code,_=code_cell(response['raw_text'],thinking_enabled=c['thinking_enabled'])
                    try:vm=TensorVM(plan['project'],plan['image'],folder/'vm.json',study.deadline.child(180),
                        debug_console=folder/'serial.log',bridge_seconds=plan['design']['vm_bridge_seconds'],
                        readiness_seconds=plan['design']['vm_readiness_seconds'])
                    except Exception as error:raise InfrastructureStop('VM startup: '+str(error)) from error
                    outcome=vm.execute(code,p,seconds=60)
                except (ValueError,CellAllowanceExceeded) as error:
                    outcome={'error':type(error).__name__+': '+str(error),'output':''}
                    row['failure_stage']='model_cell_allowance' if isinstance(error,CellAllowanceExceeded) else 'model_format'
                finally:
                    if vm:vm.close();vm=None
                    row.update(explicit_grade(p,expected,requests,outcome,c))
                    atomic(folder/'EFFECT.json',{'score':row,'outcome':outcome,'requests':requests,'receipts':p.receipt_ledger,
                        'operations':p.operation_history,'final':p.status(),'serial':bound_serial(folder/'serial.log')})
                result['rows'].append(row);atomic(root/'comparison-results.json',result['rows'])
            result['status']='completed'
        except BaseException as error:result.update(status='stopped',error=type(error).__name__+': '+str(error))
        finally:
            if vm:vm.close()
            measured=read(root/'usage.json') if (root/'usage.json').exists() else {'charged_tokens':0,'phases':{}}
            require(measured['charged_tokens']<=LIMIT,'Aggregate token ceiling exceeded')
            result.update(charged_tokens=measured['charged_tokens'],uncertain_tokens_upper_bound=sum(r['uncertain_tokens_upper_bound'] for r in measured['phases'].values()),
                response_ceiling=4,token_ceiling=LIMIT,deadline_seconds=SECONDS,wall_seconds=time.monotonic()-began,pilot_run=False)
            workers=[read(p) for p in (root/'runs').glob('*/CLOSED.json')];vms=[read(p) for p in root.glob('*/*/vm.json')]
            result['all_owned_workers_closed']=all(r.get('owned_worker_closed') for r in workers)
            result['all_owned_vms_closed']=all(r.get('owned_vm_closed') for r in vms)
            result['unchanged_editor_sha256_after']=sha(plan['models']['unchanged']['path'])
            result['editor_unchanged']=result['unchanged_editor_sha256_after']==plan['models']['unchanged']['sha256']
            if study:study.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));study.save()
            atomic(root/'RESULT.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='run':run(sys.argv[2])
