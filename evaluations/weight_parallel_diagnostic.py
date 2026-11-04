"""Separate bounded parallel-runtime diagnostic; no change to scored studies."""
import json
import os
from pathlib import Path
import shutil
import sys
import time

from lora6k_state import atomic,identity,read,sha,exclusive
from weight_editor_runtime import Deadline,TokenBudget,check_files,require


def compare(a,b):
    import numpy as np
    a,b=np.asarray(a,dtype=np.float32),np.asarray(b,dtype=np.float32)
    require(a.shape==b.shape and a.ndim==1 and len(a)>1 and np.isfinite(a).all() and np.isfinite(b).all(),'Invalid logit vectors')
    difference=np.abs(a-b);pa=np.exp(a.astype(np.float64)-float(a.max()));pa/=pa.sum()
    pb=np.exp(b.astype(np.float64)-float(b.max()));pb/=pb.sum();tv=float(np.abs(pa-pb).sum()/2)
    return {'max_abs':float(difference.max()),'max_abs_token':int(difference.argmax()),'tv':tv,
        'argmax_equal':int(a.argmax())==int(b.argmax()),'passed':bool(np.all(difference<=.001+.001*np.abs(a))) and tv<=.001}


def prepare(project,output):
    project,output=Path(project).resolve(),Path(output).resolve();require(not output.exists(),'Never overwrite a diagnostic publication')
    old=read(project/'.data/weight-repair-4b-editor-20261102/throughput4-plan.json')
    model=old['models'][0];require(sha(model['path'])==model['sha256'],'Pinned published-repair model changed')
    output.mkdir();(output/'code').mkdir()
    modules=['weight_parallel_diagnostic.py','weight_editor_native.py','weight_editor_runtime.py','weight_editor_owned.py','lora6k_state.py','lora6k_supervisor.py']
    for name in modules:shutil.copyfile(project/'evaluations'/name,output/'code'/name)
    shutil.copyfile(project/'controller/windows_job.py',output/'code/windows_job.py')
    plan={'scope':'Full-vector solo-repeat / two-slot / four-slot isolation and short throughput diagnostic only',
        'model':model,'engine':old['engine'],'engine_files':old['engine_files'],'prompts':old['prompts'],'forced_tokens':old['forced_tokens'],
        'code':{p.name:sha(p) for p in (output/'code').iterdir()},'python':str(Path(sys.executable).resolve()),
        'require_closed_study':str(project/'.data/tensor-workspace-clarity-pair-20261103'),
        'numeric_runs':[{'slots':1,'order':[0,1,2,3],'label':'solo-first'}, {'slots':1,'order':[0,1,2,3],'label':'solo-repeat'},
            {'slots':2,'order':[0,1,2,3],'label':'two-normal'},{'slots':2,'order':[3,1,0,2],'label':'two-swapped'},
            {'slots':4,'order':[0,1,2,3],'label':'four-normal'},{'slots':4,'order':[3,1,0,2],'label':'four-swapped'}],
        'throughput_order':[1,2,4,4,2,1],'decode_steps':256,'context_per_slot':34816,
        'limits':{'seconds':600,'sampled_tokens':4096,'numeric_atol':.001,'numeric_rtol':.001,'total_variation_limit':.001},
        'constraints':'No weights edited; no scored math/RSI trials, downloads or automatic promotion; preserve failed numerical checks and current two-slot settings.'}
    atomic(output/'manifest.json',plan);(output/'manifest.sha256').write_text(identity(plan))
    atomic(output/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(plan),'explicit_user_authorization':False})
    return {'plan_sha256':identity(plan),'prepared_root':str(output),'run_after_closed_study':plan['require_closed_study']}


def worker(arguments):
    root,folder,token,end=arguments;root,folder=Path(root),Path(folder);plan=read(root/'manifest.json');deadline=Deadline(end=float(end))
    require(identity(plan)==(root/'manifest.sha256').read_text().strip(),'Parallel diagnostic manifest changed')
    require(read(root/'GPU-AUTHORIZATION.json')=={'manifest_sha256':identity(plan),'explicit_user_authorization':True},'Diagnostic not authorized')
    check_files(root/'code',plan['code']);check_files(plan['engine'],plan['engine_files']);require(sha(plan['model']['path'])==plan['model']['sha256'],'Model changed')
    from weight_editor_native import BatchAPI
    import numpy as np
    class ParallelAPI(BatchAPI):
        def context_slots(self,model,slots):
            if slots in (1,2):return super().context_slots(model,slots)
            require(slots==4,'Only fixed diagnostic slot counts')
            p=self.lib.llama_context_default_params();p.n_ctx=34816*4;p.n_batch=128;p.n_ubatch=64;p.n_seq_max=4;p.n_rs_seq=0
            p.n_threads=p.n_threads_batch=2;p.type_k=p.type_v=1;p.flash_attn_type=1;p.offload_kqv=True;p.no_perf=False
            ctx=self.lib.llama_init_from_model(model,p);require(bool(ctx),'Four-slot context allocation failed')
            require(self.lib.llama_n_ctx_seq(ctx)>=34816,'Diagnostic per-slot context underflow');return ctx
    budget=TokenBudget(folder,plan['limits']['sampled_tokens'],{'nonce':token,'manifest_sha256':identity(plan)})
    progress={'pid':os.getpid(),'token':token,'gpu_loaded':False,'request_deadlines':{}}
    def event(kind,**data):progress.update(event=kind,**data);atomic(folder/'progress.json',progress)
    api=model=ctx=None;samplers=[];result={'status':'failed','token':token,'cleanup_complete':False,'numeric':[],'throughput':[]}
    try:
        event('loading');api=ParallelAPI(plan['engine']);require(api.penalty_control()['generated_unique_presence_only'],'Sampler control failed')
        model=api.load(plan['model']['path']);progress['gpu_loaded']=True
        for p in plan['prompts']:require(api.encode(model,p['text'])==p['ids'],'Diagnostic tokenizer mismatch')
        prompts,forced=plan['prompts'],plan['forced_tokens'];reference=None
        for spec in plan['numeric_runs']:
            event('numeric',configuration=spec,request_deadlines={spec['label']:min(deadline.end,time.monotonic()+120)})
            values={};positions=len(forced[0])+1
            for start in range(0,4,spec['slots']):
                group=spec['order'][start:start+spec['slots']];deadline.remaining();ctx=api.context_slots(model,spec['slots'])
                for seq,i in enumerate(group):
                    api.prefill(ctx,prompts[i]['ids'],seq,check=deadline.remaining);values[i]=[api.logits(ctx)]
                for position in range(positions-1):
                    deadline.remaining();api.batch(ctx,[(forced[i][position],len(prompts[i]['ids'])+position,seq,True) for seq,i in enumerate(group)])
                    for row,i in enumerate(group):values[i].append(api.logits(ctx,row))
                api.lib.llama_free(ctx);ctx=None
            array=np.asarray([values[i] for i in range(4)],dtype='<f4');path=folder/(spec['label']+'.npy');np.save(path,array,allow_pickle=False)
            require(np.isfinite(array).all(),'Nonfinite saved logits')
            if reference is None:reference=array.copy()
            else:
                checks=[{'prompt':i,'position':j,**compare(reference[i,j],array[i,j])} for i in range(4) for j in range(positions)]
                result['numeric'].append({'configuration':spec,'raw_logits_file':path.name,'raw_logits_sha256':sha(path),'checks':checks,
                    'passed':all(c['passed'] for c in checks)})
            atomic(folder/'numeric-results.json',result['numeric'])
        def sample(sampler,index,case):
            deadline.remaining();budget.before_sample();value=api.lib.llama_sampler_sample(sampler,ctx,index)
            require(type(value) is int and 0<=value<248320,'Invalid diagnostic sampled token');budget.record(case,value);return value
        for number,slots in enumerate(plan['throughput_order']):
            label='throughput-'+str(number);event('throughput',slots=slots,request_deadlines={label:min(deadline.end,time.monotonic()+120)})
            ctx=api.context_slots(model,slots);current=[];samplers=[]
            for seq in range(slots):
                api.prefill(ctx,prompts[seq]['ids'],seq,check=deadline.remaining);sampler=api.sampler(model,20261103+seq);samplers.append(sampler)
                current.append(sample(sampler,-1,label+'-'+str(seq)))
            started=time.monotonic()
            for step in range(plan['decode_steps']):
                deadline.remaining();api.batch(ctx,[(current[seq],len(prompts[seq]['ids'])+step,seq,True) for seq in range(slots)])
                current=[sample(s,seq,label+'-'+str(seq)) for seq,s in enumerate(samplers)]
            seconds=time.monotonic()-started;result['throughput'].append({'slots':slots,'seconds':seconds,'measured_tokens':slots*plan['decode_steps'],
                'aggregate_tps':slots*plan['decode_steps']/seconds,'sampled_tokens_including_warmups':slots*(plan['decode_steps']+1)})
            atomic(folder/'throughput-results.json',result['throughput'])
            for s in samplers:api.lib.llama_sampler_free(s)
            samplers=[];api.lib.llama_free(ctx);ctx=None
        budget.settle();result.update(status='completed',sampled_tokens=budget.state['emitted'],full_logits_saved=True,
            short_four_slot_numeric_passed=all(x['passed'] for x in result['numeric'] if x['configuration']['slots']==4),
            long_context_or_math_quality_qualified=False)
    finally:
        if api:
            for s in samplers:api.lib.llama_sampler_free(s)
            if ctx:api.lib.llama_free(ctx)
            if model:api.lib.llama_model_free(model)
            api.close()
        budget.close();result['cleanup_complete']=True;event('closed',gpu_loaded=False,request_deadlines={});atomic(folder/'RESULT.json',result)


def run(root):
    from weight_editor_owned import launch
    root=Path(root).resolve();plan=read(root/'manifest.json');study=Path(plan['require_closed_study'])
    require(read(study/'runner.json')['status']=='completed' and read(study/'CLOSED-REPORT.json')['all_owned_native_workers_closed'],'Current scored study must close first')
    require(all(read(study/a/'vm.json')['owned_vm_closed'] for a in ('unchanged','manual')),'Current editing VMs must close first')
    with exclusive(root):return launch(root,root/'run',[plan['python'],str(root/'code/weight_parallel_diagnostic.py'),'worker'],Deadline(plan['limits']['seconds']))


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='run':print(run(sys.argv[2]))
    elif sys.argv[1]=='worker':worker(sys.argv[2:])
    else:raise ValueError('Unknown diagnostic command')
