"""Owned, zero-sampling localization child for one frozen Builder intervention."""
import os
from pathlib import Path
import sys,time
from lora6k_state import read,atomic,sha,identity
from weight_editor_runtime import Deadline,TokenBudget,check_files,require


def main(args):
    request_path,root,folder,token,end=args;root,folder,request_path=map(Path,(root,folder,request_path));deadline=Deadline(end=float(end))
    plan=read(root/'manifest.json');require(identity(plan)==(root/'manifest.sha256').read_text().strip(),'Plan changed')
    check_files(root/'code',plan['code']);check_files(plan['engine'],plan['engine_files'])
    require(request_path.resolve().is_relative_to((root/'requests').resolve()),'Request outside publication')
    require(read(root/'active-request.json')['sha256']==sha(request_path),'Request binding mismatch')
    request=read(request_path);require(request['model']==plan['models']['unchanged'] and sha(request['model']['path'])==request['model']['sha256'],'Original teacher changed')
    require(1<=len(request['conditions'])<=32,'Localization condition count')
    used=read(root/'LOCALIZATION-ADMISSION.json');require(used['admitted_conditions']<=32,'Global localization limit')
    budget=TokenBudget(folder,0,{'nonce':token,'request_sha256':sha(request_path)})
    progress={'token':token,'pid':os.getpid(),'gpu_loaded':False,'request_deadlines':{}}
    def event(kind,**kw):progress.update(event=kind,**kw);atomic(folder/'progress.json',progress)
    api=model=None;result={'status':'failed','token':token,'request_sha256':sha(request_path),'rows':[],'cleanup_complete':False}
    try:
        from weight_editor_owned import await_ownership
        event('awaiting_ownership');await_ownership(folder,token,os.getpid(),deadline)
        from weight_editor_trace import TraceAPI
        import numpy as np
        api=TraceAPI(plan['engine']);event('loading');model=api.load(request['model']['path']);progress['gpu_loaded']=True
        for condition in request['conditions']:
            require(len(condition['input_ids'])<=4096 and api.encode(model,condition['rendered_prompt'])==condition['input_ids'],'Localization tokenizer/context mismatch')
            op=condition.get('intervention');layer=condition.get('layer')
            if op:
                require(layer in list(range(26,32)) and op['scale']==.5 and (
                    (op['kind']=='scale' and op['name']==f'ffn_out-{layer}') or
                    (op['kind']=='columns' and op['name']==f'ffn_swiglu-{layer}' and len(op['columns'])==16)), 'Outside frozen intervention family')
            end_request=min(deadline.end,time.monotonic()+120)
            event('localization',request_deadlines={condition['id']:end_request})
            logits,values=api.forward(model,condition['input_ids'],Deadline(end=end_request),capture=bool(condition.get('capture')),intervention=op)
            margin=float(logits[condition['good_token']]-logits[condition['bad_token']])
            np.savez_compressed(folder/(condition['id']+'.npz'),logits=logits,**values)
            result['rows'].append({'id':condition['id'],'margin':margin,'good_token':condition['good_token'],'bad_token':condition['bad_token'],
                'capture':str(folder/(condition['id']+'.npz')),'intervention':op,'layer':layer})
            atomic(folder/'partial.json',result['rows'])
        budget.settle();result.update(status='completed',generated_tokens=0)
    finally:
        if model:api.lib.llama_model_free(model)
        if api:api.close()
        budget.close();progress['gpu_loaded']=False;event('closed',request_deadlines={})
        result['cleanup_complete']=True;atomic(folder/'RESULT.json',result)


if __name__=='__main__':main(sys.argv[1:])
