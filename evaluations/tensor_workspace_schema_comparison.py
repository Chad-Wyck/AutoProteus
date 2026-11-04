"""Four-response, read-only fixture comparison of a documented return schema."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from lora6k_state import atomic,read,sha,identity,exclusive
from tensor_workspace_study import Study,code_cell
from tensor_workspace_code_diagnostic import score
from tensor_workspace_overnight import fixture,desktop_lease,admission,AUTHORIZATION
from tensor_workspace_vm import TensorVM
from tensor_workspace_errors import InfrastructureStop,CellAllowanceExceeded
from weight_editor_runtime import require,Deadline,check_files

LIMIT=32768
SECONDS=1200
FORBIDDEN=frozenset(('write_start','write_chunk','write_finish','undo','restore','checkpoint','submit'))
SCHEMA="""Generation return schema: test_candidate(ids) returns {'candidate': {'receipt': {...}, 'outcomes': [{'id': ..., 'status': ..., 'correct': ..., 'generated_tokens': ...}, ...]}}. Access the outcomes at result['candidate']['outcomes']; there is no top-level result['outcomes']. compare_with_original(ids) returns 'candidate' and 'original' entries with that same receipt/outcomes structure. These fixture outcomes have status='protocol_stub' and correct=None, not real math answers.
"""


def frozen_brief(source):
    source=Path(source)
    def assigned(path,name):
        return next(n.value for n in ast.parse(path.read_text(encoding='utf8')).body
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    guidance=ast.literal_eval(assigned(source/'tensor_workspace_precision.py','GUIDANCE'))
    brief=assigned(source/'tensor_workspace_code_diagnostic.py','BRIEF')
    require(isinstance(brief,ast.BinOp) and isinstance(brief.op,ast.Add) and isinstance(brief.right,ast.Name)
        and brief.right.id=='GUIDANCE','Unexpected historical brief expression')
    return ast.literal_eval(brief.left)+guidance


def variants():
    return [
        {'id':'schema-cedar','kind':'test_saved','split':'documentation-comparison','block':12,'index':0,'label':'cedar',
         'task':'Saved candidate Cedar already contains three tensor edits. Generate dev-0 and dev-1 with the currently saved candidate. Display each returned outcome ID and status. Preserve every numerical value exactly. Do not write, undo, restore, checkpoint or submit. These fixture outcomes do not establish math correctness.'},
        {'id':'schema-birch','kind':'test_saved','split':'documentation-comparison','block':18,'index':0,'label':'birch',
         'task':'For saved candidate Birch, generate dev-1 and dev-0 in separate test_candidate calls. Display the returned outcome ID and status from each call. Keep all saved numerical content exactly unchanged. Do not write, undo, restore, checkpoint or submit. Do not claim these protocol stubs solved math.'}]


def readonly_fixture(folder,case,*,faithful=True):
    p,expected,requests,names,_=fixture(folder,case,faithful=faithful)
    original=p.handle;attempts=[]
    def handle(r):
        op=r.get('op') if isinstance(r,dict) else None
        if op in FORBIDDEN:
            row={'op':op,'applied':False,'denied':True,'reason':'Read-only documentation-comparison task'}
            attempts.append(row);p.operation_history.append(row);p.event('forbidden_operation',row)
            raise ValueError('This task forbids mutation, checkpointing and submission')
        return original(r)
    p.handle=handle
    return p,expected,requests,names,attempts


def grade(p,expected,requests,outcome,attempts,case):
    measured=score(p,expected,requests,outcome,submission_policy='forbidden',write_policy='forbidden')
    text=outcome.get('output','')
    displayed=all(i in text for i in ('dev-0','dev-1')) and text.count('protocol_stub')>=2
    route_ok=case['id']!='schema-birch' or [r['ids'] for r in requests if r['view'] in ('edited','both')]==[['dev-1'],['dev-0']]
    return {**measured,'numerical_preservation':measured['numeric_state_correct'],
        'execution_completed':measured['cell_completed'],'display_completed':displayed,'requested_call_structure':route_ok,
        'forbidden_operation_count':len(attempts),'forbidden_operations':copy.deepcopy(attempts),
        'task_completed':bool(measured['correct'] and displayed and route_ok and not attempts)}


def calibrate(project,root):
    root=Path(root);root.mkdir(exist_ok=False);vm=None;rows=[]
    image=read(Path(project)/'.data/apwt-overnight-20261104-002/manifest.json')['image']
    try:
        vm=TensorVM(project,image,root/'vm.json',Deadline(240))
        for case in variants():
            p,expected,requests,names,attempts=readonly_fixture(root/case['id'],case)
            code="print(test_candidate(['dev-0','dev-1']))" if case['id']=='schema-cedar' else "print(test_candidate(['dev-1']))\nprint(test_candidate(['dev-0']))"
            outcome=vm.execute(code,p);result=grade(p,expected,requests,outcome,attempts,case)
            require(result['task_completed'],'Read-only VM positive control failed');rows.append(result)
        case=variants()[0];p,expected,requests,names,attempts=readonly_fixture(root/'forbidden',case)
        code=f"try:\n undo_edit({names[0]!r})\nexcept ValueError:\n print('denied')\nprint(test_candidate(['dev-0','dev-1']))"
        result=grade(p,expected,requests,vm.execute(code,p),attempts,case)
        require(result['numerical_preservation'] and result['correct_candidate_test_coverage'] and not result['task_completed']
            and result['forbidden_operation_count']==1,'Forbidden-operation control failed');rows.append(result)
    finally:
        if vm:vm.close()
    require(read(root/'vm.json')['owned_vm_closed'],'Read-only calibration VM not closed')
    atomic(root/'RESULT.json',{'status':'passed','controls':rows,'model_inference':False,'owned_vm_closed':True})


def prepare(project,root,calibration):
    from tokenizers import Tokenizer
    project,root,calibration=map(lambda x:Path(x).resolve(),(project,root,calibration))
    require(not root.exists(),'Never overwrite or retry a documentation comparison')
    prior=project/'.data/apwt-overnight-20261104-002';old=read(prior/'manifest.json')
    check_files(prior/'code',old['code']);require(read(calibration/'RESULT.json')['status']=='passed','Actual VM calibration required')
    brief=frozen_brief(prior/'code');briefs={'frozen':brief,'clarified':brief+SCHEMA}
    rows=variants();tok=Tokenizer.from_file(str(Path(old['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
    schedule=[]
    # Each variant sees both briefs; reverse arm order for the second variant.
    for arm,number in [('frozen',0),('clarified',0),('clarified',1),('frozen',1)]:
        case=copy.deepcopy(rows[number]);case['arm']=arm
        case['rendered_prompt']='<|im_start|>system\n'+briefs[arm]+'<|im_end|>\n<|im_start|>user\n'+case['task']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
        case['input_ids']=tok.encode(case['rendered_prompt'],add_special_tokens=False).ids
        case['rng_seed']=int.from_bytes(hashlib.sha256(('apwt-return-schema:'+case['id']).encode()).digest()[:4],'little')
        schedule.append(case)
    root.mkdir();(root/'code').mkdir();(root/'runs').mkdir();(root/'requests').mkdir()
    for name in set(old['code'])|{'tensor_workspace_schema_comparison.py'}:
        source=project/('controller' if name=='windows_job.py' else 'evaluations')/name
        shutil.copyfile(source,root/'code'/name)
    atomic(root/'inputs.json',{'cases':rows});atomic(root/'hidden-golds.json',{});atomic(root/'tensor-catalog.json',{})
    atomic(root/'schedule.json',schedule);atomic(root/'briefs.json',briefs)
    atomic(root/'AUTHORIZATION.json',{'user_instruction':AUTHORIZATION,'explicit_user_authorization':False,
        'source_thread_id':'REDACTED-PRIVATE-THREAD','scope':'Critic-reviewed follow-up: unchanged 4B, two fresh variants under two briefs, four responses, no retries or weight changes',
        'sampled_tokens':LIMIT,'seconds':SECONDS,'failed_pilot_gate_remains_closed':True})
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','models','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol')}
    plan.update(scope='Four-response read-only nested return-schema documentation comparison',overnight=True,numeric_policy='precise-v2',
        code={p.name:sha(p) for p in (root/'code').iterdir()},controller_files=copy.deepcopy(old['controller_files']),
        data={n:sha(root/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json','schedule.json','briefs.json','AUTHORIZATION.json')},
        limits={'total_seconds':SECONDS,'sampled_tokens':LIMIT,'responses':4,'cell_seconds':60},
        design={'vm_preflight_receipt':str(calibration/'RESULT.json'),'vm_preflight_sha256':sha(calibration/'RESULT.json'),
            'target_output_tokens':8192,'editor_output_tokens':8192,'editor_sampling':copy.deepcopy(old['design']['editor_sampling']),
            'arms':['frozen','clarified'],'only_model':'unchanged','case_pairing':'identical task, seed, fixture and tools within variant; brief alone differs',
            'fixed_order':[(c['arm'],c['id']) for c in schedule],'no_retries':True,'no_pilot':True,
            'completion_rule':'EOS, valid single cell, no runtime error, both IDs/statuses displayed, required final-candidate coverage, exact numeric preservation, required call structure, no forbidden operations',
            'historical_brief_source':str(prior/'code'),'historical_brief_sha256':hashlib.sha256(brief.encode()).hexdigest(),
            'new_brief_delta':SCHEMA,'not_a_generalization_or_repair_test':True})
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\np=json.loads((r/'manifest.json').read_text())\nsys.path.insert(0,p['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_schema_comparison import run\nrun(r)\n",encoding='utf8')
    return {'root':str(root),'manifest_sha256':identity(plan),'responses':4,'sampled_token_ceiling':LIMIT,'seconds':SECONDS}


def run(root):
    root=Path(root).resolve();plan=read(root/'manifest.json');began=time.monotonic()
    with desktop_lease(plan['project']),exclusive(root):
        require(not (root/'runner.json').exists() and not (root/'RESULT.json').exists(),'No retry or implicit replay')
        result={'status':'starting','rows':[]};study=None;vm=None
        try:
            require(read(root/'AUTHORIZATION.json')['explicit_user_authorization'],'Authorization missing')
            admission(plan['project'],root/'admission')
            study=Study(root);study.deadline=Deadline(end=began+SECONDS);study.worker_deadline=study.deadline
            for number,case in enumerate(read(root/'schedule.json')):
                require(number<4,'Response ceiling');study.arm=case['arm'];study.state.update(phase='return_schema_comparison',case=case['id'],arm=case['arm']);study.save()
                used=read(root/'usage.json')['charged_tokens'] if (root/'usage.json').exists() else 0
                require(used+8192<=LIMIT,'Sampled-token ceiling')
                response=study.inference('editor',plan['models']['unchanged'],[case],remaining=8192)[0]
                folder=root/case['arm']/case['id'];folder.parent.mkdir(exist_ok=True)
                p,expected,requests,names,attempts=readonly_fixture(folder,case)
                before=p.candidate_state()['candidate_id'];outcome={'error':'No executable cell','output':''}
                row={'arm':case['arm'],'id':case['id'],'generated_tokens':response['generated_tokens'],'finish_reason':response['finish_reason']}
                try:
                    require(response['finish_reason']=='eos','Generation truncated; no code executed')
                    code,_=code_cell(response['raw_text'])
                    try:vm=TensorVM(plan['project'],plan['image'],folder/'vm.json',study.deadline.child(180))
                    except Exception as exc:raise InfrastructureStop('VM startup: '+str(exc)) from exc
                    outcome=vm.execute(code,p,seconds=60)
                except (ValueError,CellAllowanceExceeded) as error:
                    outcome={'error':type(error).__name__+': '+str(error),'output':''}
                    row['failure_stage']='model_cell_allowance' if isinstance(error,CellAllowanceExceeded) else 'model_format'
                finally:
                    if vm:vm.close();vm=None
                    row.update(grade(p,expected,requests,outcome,attempts,case));row['candidate_identity_preserved']=before==p.candidate_state()['candidate_id']
                    atomic(folder/'EFFECT.json',{'score':row,'outcome':outcome,'requests':requests,'receipts':p.receipt_ledger,'operations':p.operation_history})
                result['rows'].append(row);atomic(root/'comparison-results.json',result['rows'])
            result['status']='completed'
        except BaseException as error:result.update(status='stopped',error=type(error).__name__+': '+str(error))
        finally:
            if vm:vm.close()
            usage=read(root/'usage.json') if (root/'usage.json').exists() else {'charged_tokens':0,'phases':{}}
            require(usage['charged_tokens']<=LIMIT,'Aggregate token ceiling exceeded')
            result.update(charged_tokens=usage['charged_tokens'],uncertain_tokens_upper_bound=sum(r['uncertain_tokens_upper_bound'] for r in usage['phases'].values()),
                response_ceiling=4,token_ceiling=LIMIT,deadline_seconds=SECONDS,wall_seconds=time.monotonic()-began,
                unchanged_editor_sha256_after=sha(plan['models']['unchanged']['path']),pilot_run=False,no_generalization_claim=True)
            closures=[read(p) for p in (root/'runs').glob('*/CLOSED.json')];vms=[read(p) for p in root.glob('*/*/vm.json')]
            result['all_owned_workers_closed']=bool(closures) and all(r.get('owned_worker_closed') for r in closures)
            result['all_owned_vms_closed']=all(r.get('owned_vm_closed') for r in vms)
            result['editor_unchanged']=result['unchanged_editor_sha256_after']==plan['models']['unchanged']['sha256']
            if study:study.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));study.save()
            atomic(root/'RESULT.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='calibrate':
        project,root=sys.argv[2:4]
        with desktop_lease(project):
            admission(project,Path(str(root)+'-admission'));calibrate(project,root)
    elif sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='run':run(sys.argv[2])
