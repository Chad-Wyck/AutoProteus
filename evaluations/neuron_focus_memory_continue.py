"""User-approved memory-only resource amendment; retain all scientific ledgers."""
import copy,json,shutil,sys,time
from pathlib import Path
if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lora6k_state import atomic,read,sha,identity,exclusive
from weight_editor_runtime import require,Deadline,check_files
from neuron_focus import verify,FocusStudy,execute
from neuron_focus_contract import require_execution,TOKEN_LIMIT
from memory_availability_policy import NAME,FLOORS,config


def carry_state(carry,now):
    start=carry['original_start'];usage=carry['usage'];budget=carry['budget']
    require(start['end_unix']-start['began_unix']==10800,'Original scientific clock changed')
    require(now<start['end_unix'],'Original scientific deadline expired; no continuation')
    require(carry['attempted_calls']==2 and carry['completed_responses']==0,'Only the declared two interruptions can continue')
    require(set(usage['phases'])=={'call-001','call-002'} and set(budget['phase_categories'])=={'call-001','call-002'},'Carry phase mismatch')
    for name,p in usage['phases'].items():
        require(p['observed_tokens']==0 and p['charged_tokens']==64 and p['uncertain_tokens_upper_bound']==64
            and usage['charged_tokens']==128 and not p['measurement_complete'],'Interrupted usage changed')
        require(budget['phase_categories'][name]=='development_untouched','Carry category changed')
    return {'remaining_seconds':start['end_unix']-now,'initial_calls':2,'initial_charged_tokens':128,
        'total_token_ceiling':TOKEN_LIMIT,'maximum_completed_scheduled_responses':18,
        'historical_interrupted_calls':2,'additional_interrupted_calls_allowed':0}


def prepare(source,root):
    source,root=Path(source).resolve(),Path(root).resolve();require(not root.exists(),'No continuation overwrite')
    verify(source);old=read(source/'manifest.json');result=read(source/'RESULT.json');audit=read(source/'POST-STOP-AUDIT.json')
    require(result['status']=='bounded_or_infrastructure_stop' and audit['completed_responses']==0
        and audit['dedicated_probes']==0 and audit['weight_artifacts']==0
        and audit['owned_workers_closed'] and audit['lease_released'],'Unsupported predecessor stage')
    carry={'source':str(source),'source_identity':identity(old),'original_start':read(source/'RUN-STARTED.json'),
        'usage':read(source/'usage.json'),'budget':read(source/'BUDGET.json'),'attempted_calls':2,'completed_responses':0,
        'reason':'Explicit user resource-availability preference; prospective resource amendment and continuation, original clock retained',
        'completion_accounting':'18 scheduled completed responses plus two historical interrupted calls charged to existing reserve; no new retry allowance'}
    carry_state(carry,time.time())
    root.mkdir();(root/'code').mkdir();(root/'requests').mkdir();(root/'runs').mkdir();(root/'artifacts').mkdir();(root/'teacher-screen').mkdir()
    for name in old['data']:shutil.copyfile(source/name,root/name)
    for name in old['code']:shutil.copyfile(source/'code'/name,root/'code'/name)
    for name in ('weight_editor_owned.py','tensor_workspace_overnight.py','memory_availability_policy.py','neuron_focus_memory_continue.py'):
        shutil.copyfile(Path(old['project'])/'evaluations'/name,root/'code'/name)
    for name in ('usage.json','RUN-STARTED.json'):shutil.copyfile(source/name,root/name)
    for name in ('call-001','call-002'):
        shutil.copyfile(source/'requests'/(name+'.json'),root/'requests'/(name+'.json'))
        shutil.copytree(source/'runs'/name,root/'runs'/name)
    atomic(root/'MEMORY-CARRY-IN.json',carry)
    parent_files={n:sha(source/n) for n in ('manifest.json','manifest.sha256','RUN-STARTED.json','RESULT.json','POST-STOP-AUDIT.json','BUDGET.json','usage.json','requests/call-001.json','requests/call-002.json')}
    parent_files.update({str(p.relative_to(source)):sha(p) for p in (source/'runs').rglob('*') if p.is_file()})
    plan=copy.deepcopy(old);plan.update(publication=str(root),scope='Explicit memory-availability resource amendment; original focused study science, clock and aggregate budget',
        predecessor_completion={'root':str(source),'files':parent_files},continuation={'source_identity':identity(old),'carry_in_sha256':sha(root/'MEMORY-CARRY-IN.json')},
        resource_policy={'name':NAME,'floors':copy.deepcopy(FLOORS),'background_utilization_is_advisory':True,
            'gpu_uuid':'GPU-cfcf4329-16bb-69b3-4980-96dc7d8168f9','gpu_pci_bus_id':'00000000:01:00.0',
            'timing':'Shared background activity; no idle-machine throughput or slowdown-bound claim',
            'supersedes_zero_background_compute_policy':True})
    plan['design']['no_shared_gpu']=False
    plan['code']={p.name:sha(p) for p in (root/'code').iterdir() if p.is_file()}
    plan['data'].update({'MEMORY-CARRY-IN.json':sha(root/'MEMORY-CARRY-IN.json')})
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan),encoding='utf8')
    (root/'run.py').write_text("import sys\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\nsys.path.insert(0,str(r/'code'))\nsys.path.insert(1,str(r.parents[1]))\nfrom neuron_focus_memory_continue import verify_continuation,run\nif sys.argv[1:]==['verify']: print(verify_continuation(r))\nelif sys.argv[1:]==['run']:run(r)\nelse:raise SystemExit('Use verify or run')\n",encoding='utf8')
    return verify_continuation(root)


def verify_continuation(root):
    root=Path(root);verify(root);plan=read(root/'manifest.json');source=Path(plan['predecessor_completion']['root'])
    check_files(source,plan['predecessor_completion']['files']);old=read(source/'manifest.json');carry=read(root/'MEMORY-CARRY-IN.json')
    require(carry['source_identity']==identity(old)==plan['continuation']['source_identity'],'Parent identity changed')
    require(sha(root/'MEMORY-CARRY-IN.json')==plan['continuation']['carry_in_sha256'],'Carry changed')
    require(read(root/'RUN-STARTED.json')==carry['original_start'],'Clock reset forbidden')
    for key in old:
        if key not in ('publication','scope','code','data','continuation','predecessor_completion','design'):require(plan[key]==old[key],'Scientific protocol changed: '+key)
    expected=copy.deepcopy(old['design']);expected['no_shared_gpu']=False;require(plan['design']==expected,'Sampler/context design changed')
    require(all(plan['data'].get(n)==v for n,v in old['data'].items()) and set(plan['data'])-set(old['data'])=={'MEMORY-CARRY-IN.json'},'Frozen scientific inputs changed')
    require(set(plan['code'])-set(old['code'])=={'memory_availability_policy.py','neuron_focus_memory_continue.py'},'Unexpected new runtime module')
    allowed={'weight_editor_owned.py','tensor_workspace_overnight.py'}
    require({n for n in old['code'] if old['code'][n]!=plan['code'][n]}==allowed,'Unexpected runtime edits')
    config(root)
    return {'status':'verified_continuation','plan_identity':identity(plan),'resource_policy':NAME,**carry_state(carry,time.time())}


def run(root):
    root=Path(root).resolve();require_execution(root);verify_continuation(root);plan=read(root/'manifest.json');carry=read(root/'MEMORY-CARRY-IN.json')
    require(not (root/'CONTINUATION-STARTED.json').exists(),'One authorized continuation only; no automatic relaunch')
    require(read(root/'usage.json')==carry['usage'],'Usage carry must be exact before start')
    from tensor_workspace_overnight import desktop_lease,admission
    with desktop_lease(plan['project']),exclusive(root):
        entered=time.time();state=carry_state(carry,entered);deadline=Deadline(state['remaining_seconds']);study=None
        atomic(root/'CONTINUATION-STARTED.json',{'entered_unix':entered,'original_start':carry['original_start'],'carried_charged_tokens':128})
        result={'status':'starting','student_inference':False,'source':carry['source'],'original_start':carry['original_start'],'budget':copy.deepcopy(carry['budget'])}
        try:
            deadline.remaining(reserve=60)
            admission(plan['project'],root/'admission');deadline.remaining()
            study=FocusStudy(root);study.calls=2;study.phase_categories=copy.deepcopy(carry['budget']['phase_categories'])
            study.deadline=deadline;study.worker_deadline=deadline;study.state.update(began_unix=carry['original_start']['began_unix'],historical_interrupted_calls=2)
            study.reconcile();result.update(execute(study))
        except BaseException as error:result.update(status='bounded_or_infrastructure_stop',error=type(error).__name__+': '+str(error))
        finally:
            if study:
                if study.vm:study.vm.close()
                result['budget']=study.reconcile();study.state.update(status=result['status'],phase='closed',ended_unix=time.time(),inference_calls=study.calls);study.save()
            result.update(elapsed_seconds=time.time()-carry['original_start']['began_unix'],continuation_seconds=time.time()-entered,
                student_inference=False,automatic_follow_on=False,
                all_owned_workers_closed=all(read(p)['owned_worker_closed'] for p in (root/'runs').glob('*/CLOSED.json')),
                all_owned_vms_closed=all(read(p)['owned_vm_closed'] for p in root.rglob('vm.json')),
                originals_unchanged={k:sha(v['path'])==v['sha256'] for k,v in plan['models'].items()})
            atomic(root/'RESULT.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(json.dumps(prepare(*sys.argv[2:])))
    elif sys.argv[1]=='verify':print(json.dumps(verify_continuation(Path(sys.argv[2]))))
    elif sys.argv[1]=='run':run(Path(sys.argv[2]))
