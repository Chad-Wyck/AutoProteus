"""Trusted inference child. No model-authored program enters this process."""
import os
from pathlib import Path
import sys
import time

from lora6k_state import read,atomic,sha,identity
from weight_editor_runtime import Deadline,TokenBudget,check_files,require


def main(arguments):
    request_path,root,folder,token,end=arguments;root,folder,request_path=map(Path,(root,folder,request_path));deadline=Deadline(end=float(end))
    plan=read(root/'manifest.json');require(identity(plan)==(root/'manifest.sha256').read_text().strip(),'Frozen plan changed')
    check_files(root/'code',plan['code']);check_files(plan['engine'],plan['engine_files'])
    require(request_path.resolve().is_relative_to((root/'requests').resolve()),'Request outside owned inventory')
    require(read(root/'active-request.json')['sha256']==sha(request_path),'Request authorization mismatch')
    r=read(request_path);require(r['mode'] in ('editor','generate','probe') and r['remaining_tokens']<=1048576,'Invalid inference mode/budget')
    require(sha(r['model']['path'])==r['model']['sha256'],'Model changed');check_files(r['tokenizer']['path'],r['tokenizer']['files'])
    require(len(r['cases']) in range(1,9) and all(c['id'].replace('-','').isalnum() for c in r['cases']),'Case bounds')
    binding={'nonce':token,'request_sha256':sha(request_path)};budget=TokenBudget(folder,r['remaining_tokens'],binding)
    progress={'token':token,'pid':os.getpid(),'gpu_loaded':False,'request_deadlines':{}};last=0
    def event(kind,**data):
        nonlocal last
        now=time.monotonic();changed=progress.get('event')!=kind or progress.get('request_deadlines')!=data.get('request_deadlines')
        progress.update(event=kind,**data)
        if changed or now-last>=1:atomic(folder/'progress.json',progress);last=now
    api=model=None;result={'status':'failed','token':token,'request_sha256':sha(request_path),'cleanup_complete':False}
    try:
        if plan.get('overnight'):
            from weight_editor_owned import await_ownership
            event('awaiting_ownership')
            await_ownership(folder,token,os.getpid(),deadline)
        from tokenizers import Tokenizer
        import weight_editor_worker as generation
        from weight_editor_native import BatchAPI
        from weight_editor_trace import TraceAPI
        import numpy as np
        event('loading');api=(TraceAPI if r['mode']=='probe' else BatchAPI)(plan['engine']);model=api.load(r['model']['path']);progress['gpu_loaded']=True
        tokenizer=Tokenizer.from_file(str(Path(r['tokenizer']['path'])/'tokenizer.json'))
        require(all(api.encode(model,c['rendered_prompt'])==c['input_ids'] for c in r['cases']),'Tokenizer/engine mismatch')
        if r['mode']=='probe':
            result['responses']=[]
            for c in r['cases']:
                require(len(c['input_ids'])<=4096,'Probe context limit');event('probe',request_deadlines={c['id']:min(deadline.end,time.monotonic()+120)})
                logits,values=api.forward(model,c['input_ids'],deadline.child(120),capture=True)
                np.savez_compressed(folder/(c['id']+'.npz'),logits=np.asarray(logits,dtype='<f4'),**values)
                order=np.argsort(logits)[-12:][::-1]
                atomic(folder/(c['id']+'.json'),{'id':c['id'],'top_tokens':[{'id':int(i),'text':tokenizer.decode([int(i)]),'logit':float(logits[i])} for i in order],
                    'activations':{k:list(v.shape) for k,v in values.items()},'npz_sha256':sha(folder/(c['id']+'.npz'))})
                result['responses'].append(c['id'])
        else:
            target=r['mode']=='generate';output=plan['design'].get('target_output_tokens',32768) if target else plan['design'].get('editor_output_tokens',8192)
            require(output in ((8192,32768) if target else (8192,)),'Unsupported frozen output allowance')
            require(all(len(c['input_ids'])+output<=34816 for c in r['cases']),'Context exceeds frozen allowance')
            if not target:
                def sampler(native,seed):
                    p=native.lib.llama_sampler_chain_default_params();chain=native.lib.llama_sampler_chain_init(p)
                    require(bool(chain),'Sampler allocation failed')
                    for child in (native.lib.llama_sampler_init_temp(.6),native.lib.llama_sampler_init_top_k(20),
                        native.lib.llama_sampler_init_top_p(.95,1),native.lib.llama_sampler_init_dist(seed)):
                        require(bool(child),'Sampler child failed');native.lib.llama_sampler_chain_add(chain,child)
                    return chain
                generation.editor_sampler=sampler
            else:require(api.penalty_control()['generated_unique_presence_only'],'Target sampler qualification failed')
            payload={'kind':'target' if target else 'editor','cases':r['cases'],'slots':min(2,len(r['cases'])) if target else 1,
                'output_tokens':output,'request_seconds':1800 if target else 600,'stop_token_ids':[248044,248046]}
            result['responses']=generation.generate(api,model,payload,folder,tokenizer,budget,deadline,event)
        budget.settle();result.update(status='completed',generated_tokens=budget.state['emitted'])
    finally:
        try:
            if model:api.lib.llama_model_free(model)
            if api:api.close()
            budget.close();result['cleanup_complete']=True
        finally:
            progress['gpu_loaded']=False;event('closed',request_deadlines={});atomic(folder/'RESULT.json',result)


if __name__=='__main__':main(sys.argv[1:])
