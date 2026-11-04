"""Explicit research-VM controls; does not load inference models."""
import json
from pathlib import Path
import sys
import uuid

from lora6k_state import atomic,read,sha
from tensor_workspace_policy import TensorPolicy
from tensor_workspace_vm import TensorVM
from weight_editor_runtime import Deadline,require


def run(project,folder,image_directory=None):
    import numpy as np
    project,folder=Path(project).resolve(),Path(folder).resolve();folder.mkdir(exist_ok=False)
    token=uuid.uuid4().hex;canary=folder/'host-canary.txt';canary.write_text(token)
    source=folder/'source.bin';a=np.arange(1,65,dtype='<f4').reshape(8,8);source.write_bytes(a.tobytes())
    records={'blk.0.ffn_down.weight':{'shape':[8,8],'offset':0,'bytes':256,'editable':True},
        'output.weight':{'shape':[8,8],'offset':0,'bytes':256,'editable':False}}
    requests=[]
    def inspect_request(request):
        requests.append(request)
        return {'protocol_control_only':True,'requested_view':request['view'],'mode':request['mode'],
            'candidate':policy.candidate_state()}
    policy=TensorPolicy({'path':str(source),'sha256':sha(source)},records,folder/'policy',{'layers':1},forward=inspect_request)
    vm=None;results=[]
    try:
        vm=TensorVM(project,read(Path(image_directory or folder.parent/'image')/'image.json'),folder/'vm.json',Deadline(180),debug_console=folder/'boot.log')
        cells=["import os, socket\nfrom pathlib import Path\nx=41\nassert os.getuid()==1000\nassert sorted(p.name for p in Path('/sys/class/net').iterdir())==['lo']\nassert not Path("+repr(str(canary))+ ").exists()\nassert not any(k.lower().endswith('api_key') for k in os.environ)\nassert not Path('/mnt/host').exists()\nprint(np.linalg.norm(np.eye(4)), 'isolated')",
            "assert x+1==42\nw=load_tensor('blk.0.ffn_down.weight')\nw[1,2]+=1\nprint(save_edit('blk.0.ffn_down.weight',w))\nassert load_tensor('blk.0.ffn_down.weight')[1,2]==12\nprint('persistent, numeric roundtrip')",
            "try:\n save_edit('output.weight',w)\nexcept ValueError: print('protected')\nelse: raise AssertionError('protected tensor allowed')\nprint('X'*20000)",
            "assert 'forward' not in globals()\ntest_candidate(['dev-0'])",
            "compare_with_original(['dev-0'])",
            "inspect_candidate(['hello'])",
            "40 + 2",
            "compare_with_original(texts=['hello'])"]
        for code in cells:
            row=vm.execute(code,policy);require(row['error'] is None,'VM control failed: '+str(row));results.append(row)
        require(results[2]['output'].endswith('[output truncated]'),'Output truncation control failed')
        require('protocol_control_only' in results[3]['output'] and "'requested_view': 'edited'" in results[3]['output'],
            'Candidate helper result was not displayed')
        require([(r['view'],r['mode']) for r in requests]==[('edited','generate'),('both','generate'),('edited','probe'),('both','probe')],
            'Candidate/comparison helper routing mismatch')
        require(results[6]['output'].strip()=='42','Final expression was not displayed automatically')
        try:vm.execute('while True: pass',policy,seconds=2)
        except Exception as error:results.append({'timeout':type(error).__name__,'closed':vm.closed.is_set()})
        else:raise ValueError('Timeout control failed')
        require(vm.closed.is_set() and read(folder/'vm.json')['owned_vm_closed'],'VM timeout did not close owned process')
        require(canary.read_text()==token and sha(source)==policy.base['sha256'],'Host canary/source changed')
        atomic(folder/'RESULT.json',{'status':'passed','controls':results,'source_unchanged':True,'vm_closed':True,
            'rpc_routing_controls':requests,'forward_controls_are_stubs_not_inference':True})
    finally:
        if vm:vm.close()


if __name__=='__main__':run(*sys.argv[1:])
