"""Publish unstarted frozen-candidate qualification after explicit resumption."""
from pathlib import Path
import shutil
import sys
import time

from lora6k_state import atomic,identity,read,sha
from weight_editor_runtime import require,check_files


RUNNER='''import sys,time,os
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent.parent));sys.path.insert(0,str(root/'code'))
from lora6k_state import read,atomic,identity,exclusive
from tensor_workspace_study import Study
from tensor_workspace_report import report
from weight_editor_runtime import Deadline,require,check_files
with exclusive(root):
    require(not (root/'runner.json').exists(),'Never restart a continuation implicitly')
    plan=read(root/'manifest.json')
    require(identity(plan)==(root/'manifest.sha256').read_text().strip(),'Continuation manifest changed')
    check_files(root/'code',plan['code']);check_files(root,plan['data'])
    source=plan['qualification_continuation'];check_files(source['root'],source['files'])
    require(read(root/'GPU-AUTHORIZATION.json')=={'manifest_sha256':identity(plan),'explicit_user_authorization':True},'Explicit continuation authorization required')
    left=source['original_shared_end_unix']-time.time();require(left>0,'Original shared allowance expired')
    study=object.__new__(Study);study.root=root;study.plan=plan;study.project=Path(plan['project'])
    study.deadline=Deadline(left);study.worker_deadline=study.deadline;study.cases=read(root/'inputs.json')['cases']
    study.golds=read(root/'hidden-golds.json');study.records=read(root/'tensor-catalog.json')
    study.by_id={c['id']:c for c in study.cases};study.calls=0;study.arm=None;study.vm=None
    study.baseline_cache=read(root/'baseline-results.json')
    study.state={'status':'running','pid':os.getpid(),'began_unix':time.time(),'phase':'independent_qualification',
        'arms':{a:read(root/a/'FROZEN.json')['state'] for a in plan['design']['arms']},'inference_calls':0,
        'scope':'Unstarted qualification only; no editor response or original control is regenerated'}
    study.save();result={}
    try:
        results=study.qualification();result={'status':'completed','independent':results,'arms':study.state['arms']}
    except BaseException as error:result={'status':'stopped','error':type(error).__name__+': '+str(error),'arms':study.state['arms']}
    finally:
        study.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));study.save()
        atomic(root/'RESULT.json',result);summary=report(root)
        atomic(root/'COMPLETION.json',{'status':result['status'],'source_plan_sha256':source['source_plan_sha256'],
            'report_sha256':__import__('hashlib').sha256((root/'CLOSED-REPORT.json').read_bytes()).hexdigest(),
            'independent_checked':{a:len(result.get('independent',{}).get(a,[])) for a in plan['design']['arms']},
            'original_record_unchanged':True,'no_new_editing':True,'all_owned_native_workers_closed':summary['all_owned_native_workers_closed']})
'''


def prepare(project,prior,output):
    project,prior,output=map(lambda p:Path(p).resolve(),(project,prior,output));plan=read(prior/'manifest.json')
    require(identity(plan)==(prior/'manifest.sha256').read_text().strip(),'Original plan changed')
    require(not output.exists(),'Never overwrite qualification evidence');check_files(prior,plan['data']);check_files(prior/'code',plan['code'])
    stopped=read(prior/'runner.json');result=read(prior/'RESULT.json');closed=read(prior/'CLOSED-REPORT.json')
    require(stopped['status']=='stopped' and 'Active GPU compute engine detected' in result['error'],'Continuation requires the identified admission stop')
    attempt=prior/'runs'/stopped['current_call'];failure=read(attempt/'CLOSED.json')
    require(failure['owned_worker_closed'] and not failure.get('launcher_pid') and not (attempt/'usage.json').exists(),'Stopped attempt already loaded a worker')
    require(closed['all_owned_native_workers_closed'] and all(read(prior/a/'vm.json')['owned_vm_closed'] for a in plan['design']['arms']),'Prior owned work is not closed')
    require(all(closed['arms'][a]['independent_checked']==0 for a in plan['design']['arms']),'Cannot repeat previously tested candidate cases')
    baselines=read(prior/'baseline-results.json');cases=read(prior/'inputs.json')['cases'];required={c['id'] for c in cases if c['split']!='dev'}
    require(required<=set(baselines),'Original independent controls incomplete')
    files={}
    def pin(p):
        p=Path(p).resolve();require(p.is_relative_to(prior),'Source evidence escapes original run');files[str(p.relative_to(prior))]=sha(p)
    for name in ('manifest.json','runner.json','RESULT.json','CLOSED-REPORT.json','baseline-results.json'):pin(prior/name)
    for arm in plan['design']['arms']:
        pin(prior/arm/'FROZEN.json');pin(prior/arm/'vm.json')
        for e in read(prior/arm/'FROZEN.json')['edits'].values():
            require(sha(e['path'])==e['sha256'],'Frozen candidate tensor changed');pin(e['path'])
    output.mkdir();(output/'code').mkdir();(output/'requests').mkdir();(output/'runs').mkdir()
    for file in (prior/'code').iterdir():
        if file.is_file():shutil.copyfile(file,output/'code'/file.name)
    for name in plan['data']:shutil.copyfile(prior/name,output/name)
    shutil.copyfile(prior/'baseline-results.json',output/'baseline-results.json')
    for arm in plan['design']['arms']:
        (output/arm/'snapshots').mkdir(parents=True)
        for name in ('FROZEN.json','vm.json'):shutil.copyfile(prior/arm/name,output/arm/name)
    plan['qualification_continuation']={'root':str(prior),'source_plan_sha256':identity(read(prior/'manifest.json')),
        'files':files,'original_shared_end_unix':stopped['began_unix']+plan['limits']['total_seconds'],
        'authorization':'User explicitly authorized continuing the unstarted checks after GPU admission stop',
        'scope':'16 previously unstarted candidate cases only, original 8 independent controls reused; no new editing or repeats'}
    atomic(output/'manifest.json',plan);(output/'manifest.sha256').write_text(identity(plan))
    atomic(output/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(plan),'explicit_user_authorization':False})
    (output/'run.py').write_text(RUNNER,encoding='utf8');return {'root':str(output),'manifest_sha256':identity(plan)}


if __name__=='__main__':print(prepare(*sys.argv[1:]))
