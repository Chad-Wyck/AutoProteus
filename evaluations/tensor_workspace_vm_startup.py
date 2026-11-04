"""At most three sequential cold VM boots in ten minutes; zero model inference."""
import json
from pathlib import Path
import sys
import time
import traceback

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from lora6k_state import atomic,read,sha,exclusive
from tensor_workspace_overnight import desktop_lease,admission
from tensor_workspace_vm import TensorVM
from weight_editor_runtime import Deadline,require


def bound_serial(path):
    path=Path(path)
    if not path.exists():return {'original_bytes':0,'retained_bytes':0,'exists':False}
    size=path.stat().st_size
    with path.open('rb') as stream:
        if size<=65536:data=stream.read(65536)
        else:
            head=stream.read(32700);stream.seek(max(0,size-32700));data=head+b'\n[bounded serial capture: middle omitted]\n'+stream.read(32700)
    require(len(data)<=65536,'Serial bound exceeded')
    if size>65536:
        bounded=path.with_name('serial-bounded.log');bounded.write_bytes(data)
        path=bounded
    return {'original_bytes':size,'retained_bytes':len(data),'sha256':sha(path),'exists':True}


def boot(project,root,bridge_seconds=15):
    project,root=Path(project).resolve(),Path(root).resolve();bridge_seconds=int(bridge_seconds)
    root.mkdir(exist_ok=True)
    with desktop_lease(project),exclusive(root):
        state=read(root/'STATE.json') if (root/'STATE.json').exists() else {'began_unix':time.time(),'began_monotonic':time.monotonic(),'attempts':[],'timeout_adjustments':0}
        require(len(state['attempts'])<3,'Three cold-boot ceiling reached')
        end=state['began_monotonic']+600;require(time.monotonic()<end,'Ten-minute infrastructure deadline exhausted')
        require(bridge_seconds in (15,30),'Only baseline 15s or one bounded 30s adjustment')
        if bridge_seconds==30 and not state['timeout_adjustments']:
            evidence=root/'TIMEOUT-ADJUSTMENT-EVIDENCE.json'
            require(evidence.exists() and read(evidence).get('healthy_late_boot_evidence'),'Late-boot evidence required before adjustment')
            state['timeout_adjustments']=1;state['adjustment_evidence_sha256']=sha(evidence)
        if state['timeout_adjustments']:require(bridge_seconds==30,'Do not retune the timeout again')
        number=len(state['attempts'])+1;folder=root/('boot-'+str(number));folder.mkdir(exist_ok=False)
        state['attempts'].append({'number':number,'status':'starting','bridge_seconds':bridge_seconds});atomic(root/'STATE.json',state)
        result={'number':number,'status':'starting','bridge_seconds':bridge_seconds,'model_loading':False,'sampled_tokens':0};vm=None
        image=read(project/'.data/apwt-fresh-gate-20261104-001/manifest.json')['image']
        atomic(root/'PINNED-IMAGE.json',image)
        try:
            admission(project,folder/'admission');deadline=Deadline(end=min(end,time.monotonic()+120))
            vm=TensorVM(project,image,folder/'vm.json',deadline,debug_console=folder/'serial.log',bridge_seconds=bridge_seconds)
            outcome=vm.execute("print('startup-ready')",None,seconds=2)
            require(outcome['error'] is None and outcome['output'].strip()=='startup-ready','Ready VM failed trusted responsiveness cell')
            result.update(status='passed',outcome=outcome)
        except BaseException as error:
            result.update(status='failed',error=type(error).__name__+': '+str(error),traceback=traceback.format_exc()[-16000:])
        finally:
            if vm:vm.close()
            result['serial']=bound_serial(folder/'serial.log')
            record=read(folder/'vm.json') if (folder/'vm.json').exists() else {}
            result['startup_trace']=record.get('startup_trace',[]);result['owned_vm_closed']=record.get('owned_vm_closed',True)
            result['elapsed_since_investigation_start']=time.monotonic()-state['began_monotonic']
            atomic(folder/'RESULT.json',result);state['attempts'][-1]=result;atomic(root/'STATE.json',state)
            print(json.dumps({k:v for k,v in result.items() if k not in ('traceback','startup_trace')}),flush=True)
        return result


if __name__=='__main__':boot(*sys.argv[1:])
