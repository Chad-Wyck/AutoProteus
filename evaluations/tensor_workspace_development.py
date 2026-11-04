"""Durable one-follow-up orchestration; no repeated assistant polling needed."""
from pathlib import Path
import shutil
import sys
import time

from lora6k_state import atomic,read,sha,exclusive
from tensor_workspace_image import build,WHEEL
from tensor_workspace_preflight import run as vm_preflight
from tensor_workspace_prepare import prepare_followup,MODULES
from weight_editor_runtime import require,check_files


def main(project,directory):
    project,directory=Path(project).resolve(),Path(directory).resolve()
    continuation=read(directory/'CONTINUATION.json');prior=Path(continuation['current_run']);next_run=Path(continuation['prepared_followup_root'])
    pinned=read(directory/'prepared-source-pins.json');state={'status':'running','phase':'waiting_for_original','pid':__import__('os').getpid(),'began_unix':time.time()}
    def save():atomic(directory/'development-runner.json',state)
    def source_check():check_files(project,pinned['files'])
    with exclusive(directory):
        require(not (directory/'development-runner.json').exists(),'Never duplicate/replay a development runner');save()
        try:
            source_check();plan=read(prior/'manifest.json')
            while True:
                old=read(prior/'runner.json');state['original_phase']=old['phase'];save()
                if (directory/'STOP').exists():
                    (prior/'STOP').touch();raise ValueError('Operator stop; original runner requested to close')
                if old['status']!='running':break
                require(time.time()<old['began_unix']+plan['limits']['total_seconds']+120,'Original runner exceeded its bounded closure allowance')
                time.sleep(60)
            require(old['status']=='completed','Original trial stopped; no automatic follow-up after a failed/resource-stopped run')
            # The original final report is written immediately after its final runner receipt.
            for _ in range(10):
                if (prior/'CLOSED-REPORT.json').exists() and (prior/'FINDINGS.md').exists():break
                time.sleep(1)
            require(read(prior/'CLOSED-REPORT.json')['all_owned_native_workers_closed'],'Original native worker cleanup incomplete')
            require(all(read(prior/a/'vm.json')['owned_vm_closed'] for a in plan['design']['arms']),'Original VM cleanup incomplete')
            routing={}
            editing_source=Path(plan.get('qualification_continuation',{}).get('root',str(prior)))
            for arm in plan['design']['arms']:
                rows=[__import__('json').loads(line) for line in (editing_source/arm/'policy/events.jsonl').read_text(encoding='utf8').splitlines()]
                calls=[row for row in rows if row['kind']=='forward']
                routing[arm]={'successful_forward_calls':len(calls),'original_only_calls':sum(row['views']==['original'] for row in calls),
                    'candidate_calls':sum('edited' in row['views'] for row in calls),
                    'generated_outcomes':[{'view':view,**{k:r.get(k) for k in ('id','correct','finish_reason','generated_tokens')}}
                        for row in calls if row['mode']=='generate' for view,items in row['result'].items() for r in items]}
            atomic(directory/'original-routing-audit.json',{'prior_report_sha256':sha(prior/'CLOSED-REPORT.json'),'routing':routing,
                'note':'Reads model-written code/evidence as inert text only. Original results are preserved separately.'})
            shutil.copyfile(prior/'FINDINGS.md',project/'evaluations/tensor-workspace-original-findings-2026-11-03.md')
            state.update(phase='revised_vm_preflight');save();source_check()
            if continuation.get('validated_image_directory'):
                image_directory=Path(continuation['validated_image_directory']);preflight=Path(continuation['validated_preflight'])
                image=read(image_directory/'image.json')
                require(sha(image['image'])==image['image_sha256'] and sha(project/'evaluations/tensor_workspace_guest.py')==image['guest_sha256'],
                    'Previously validated VM image/source changed')
                require(read(preflight)['status']=='passed' and read(preflight)['vm_closed'],'Prior revised VM controls incomplete')
            else:
                image_directory=directory/'image';preflight=directory/'preflight-001/RESULT.json'
                image=build(project,image_directory,project/'.data/tensor-workspace-20261103/dependencies'/WHEEL)
                vm_preflight(project,preflight.parent,image_directory)
            require(not (directory/'STOP').exists(),'Operator stopped before next publication');source_check()
            state.update(phase='publishing_followup');save()
            publication=prepare_followup(project,prior,next_run,image_directory,preflight)
            continuation.update(phase='matched follow-up',next_run=str(next_run),next_plan_sha256=publication['manifest_sha256'])
            atomic(directory/'CONTINUATION.json',continuation);state.update(phase='followup_running',next_run=str(next_run));save()
            # Execute the trusted frozen coordinator, never local-model cell source.
            import subprocess
            command=[str(sys.executable),'-X','utf8','-c',
                "import sys;sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2]);from tensor_workspace_study import main;main(sys.argv[3])",
                str(project),str(next_run/'code'),str(next_run)]
            from controller.windows_job import Job
            job=Job(vm_limits=False);child=None
            try:
                with (next_run/'stdout.log').open('w',encoding='utf8') as out,(next_run/'stderr.log').open('w',encoding='utf8') as err:
                    child=subprocess.Popen(command,cwd=project,stdout=out,stderr=err,creationflags=0x4|0x08000000)
                    job.attach_and_resume(child);state['followup_launcher_pid']=child.pid;save()
                    end=time.monotonic()+plan['limits']['total_seconds']+120
                    while child.poll() is None:
                        if (directory/'STOP').exists():(next_run/'STOP').touch()
                        require(time.monotonic()<end,'Follow-up exceeded bounded closure allowance')
                        time.sleep(10)
                    require(child.returncode==0,'Follow-up coordinator failed; no automatic restart')
            finally:
                job.close()
                if child:
                    if child.poll() is None:child.kill()
                    child.wait(timeout=20)
            require(read(next_run/'runner.json')['status']=='completed','Follow-up stopped; audit evidence without retry')
            shutil.copyfile(next_run/'FINDINGS.md',project/'evaluations/tensor-workspace-clarity-findings-2026-11-03.md')
            state.update(status='completed',phase='awaiting_final_evidence_audit')
            continuation.update(phase='both durable runs finished; final agent audit pending')
        except BaseException as error:
            state.update(status='stopped',error=type(error).__name__+': '+str(error))
            continuation.update(phase='development runner stopped; preserve evidence, no silent retry',development_error=state['error'])
        finally:
            state['ended_unix']=time.time();save();atomic(directory/'CONTINUATION.json',continuation)


if __name__=='__main__':main(*sys.argv[1:])
