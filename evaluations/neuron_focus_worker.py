"""Future native probe child; explicit live authorization checked before loading."""
import os,sys,time
from pathlib import Path
from lora6k_state import read,atomic,sha,identity
from neuron_focus_contract import require_execution,validate_probe_request,LAYER
from weight_editor_runtime import require,Deadline,TokenBudget,check_files


def probe_condition(api,model,condition,prefix,deadline):
    mode=condition['mode'];op=None
    if mode=='noop':op={'kind':'scale','name':f'ffn_swiglu-{LAYER}','scale':1.}
    if mode=='channel':op={'kind':'columns','name':f'ffn_swiglu-{LAYER}','columns':[condition['channel']],'scale':.5}
    return api.forward(model,prefix['input_ids'],deadline,hook=mode!='no_hook',capture=mode!='no_hook',intervention=op)


def main(args):
    request_path,root,folder,token,end=args;root,folder,request_path=map(Path,(root,folder,request_path));deadline=Deadline(end=float(end))
    require_execution(root)
    plan=read(root/'manifest.json');require(identity(plan)==(root/'manifest.sha256').read_text().strip(),'Frozen focus plan changed')
    check_files(root/'code',plan['code']);check_files(root,plan['data']);check_files(plan['engine'],plan['engine_files'])
    require(request_path.resolve().is_relative_to(root/'requests') and read(root/'active-request.json')['sha256']==sha(request_path),'Probe request binding')
    request=read(request_path);admitted=read(root/'PROBE-ADMISSION.json');validate_probe_request(plan,request,admitted['before_this_phase'])
    phase=request['phase'];expected=plan['models']['unchanged']
    if phase.startswith('static_'):
        models=read(root/'MODELS-FROZEN.json');expected=models[phase.removeprefix('static_')]['model']
    require(request['model']==expected and sha(expected['path'])==expected['sha256'],'Wrong probe model/artifact')
    prefixes={p['id']:p for p in read(root/'prefixes.json')['prefixes']}
    budget=TokenBudget(folder,0,{'nonce':token,'request_sha256':sha(request_path)})
    progress={'token':token,'pid':os.getpid(),'gpu_loaded':False,'request_deadlines':{}}
    def event(kind,**kw):progress.update(event=kind,**kw);atomic(folder/'progress.json',progress)
    api=model=None;result={'status':'failed','token':token,'request_sha256':sha(request_path),'rows':[],'cleanup_complete':False}
    try:
        from weight_editor_owned import await_ownership
        event('awaiting_ownership');await_ownership(folder,token,os.getpid(),deadline)
        from weight_editor_trace import TraceAPI
        import numpy as np
        event('loading');api=TraceAPI(plan['engine']);model=api.load(expected['path']);progress['gpu_loaded']=True
        for c in request['conditions']:
            prefix=prefixes[c['prefix_id']]
            require(api.encode(model,prefix['original_rendered_prompt'])==prefix['original_input_ids'],'Original tokenizer/engine parity failed')
            require(prefix['input_ids']==prefix['original_input_ids']+prefix['observed_generated_prefix_ids'] and len(prefix['input_ids'])<=4096,'Saved prefix ID boundary changed')
            end_request=min(deadline.end,time.monotonic()+120);event('probe',request_deadlines={c['id']:end_request})
            logits,values=probe_condition(api,model,c,prefix,Deadline(end=end_request))
            require(logits.shape==(248320,) and np.isfinite(logits).all(),'Probe logits layout/finite check')
            if c['mode']!='no_hook':
                for name,shape in [(f'ffn_swiglu-{LAYER}',(9216,)),(f'ffn_out-{LAYER}',(2560,)),(f'attn_residual-{LAYER}',(2560,))]:
                    require(name in values and values[name].shape==shape and np.isfinite(values[name]).all(),'Required named capture missing or wrong shape: '+name)
            path=folder/(c['id']+'.npz');np.savez_compressed(path,logits=logits,**values)
            margin=float(np.float64(logits[prefix['closing_token_id']])-np.float64(logits[prefix['contrast_token_id']]))
            require(np.isfinite(margin),'Nonfinite probe contrast margin')
            row={**c,'capture':str(path),'capture_sha256':sha(path),'closing_logit':float(logits[prefix['closing_token_id']]),
                'contrast_margin':margin,
                'effect_scope':'full-prefix static weights' if phase.startswith('static_') else 'final-token conditional hook only; prefill unmodified'}
            result['rows'].append(row);atomic(folder/'partial.json',result['rows'])
        budget.settle();result.update(status='completed',generated_tokens=0)
    finally:
        if model:api.lib.llama_model_free(model)
        if api:api.close()
        budget.close();event('closed',gpu_loaded=False,request_deadlines={});result['cleanup_complete']=True;atomic(folder/'RESULT.json',result)


if __name__=='__main__':main(sys.argv[1:])
