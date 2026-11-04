"""Generate real cells and grade their numeric effects in disposable VMs.

Small synthetic tensors reproduce the observed rollback/routing mistakes. This
measures executable decisions, not 0.8B mathematics or autonomous discovery.
"""
import copy
import hashlib
from pathlib import Path
import shutil
import sys
import time

from lora6k_state import atomic, read, sha, identity, exclusive
from tensor_workspace_precision import PreciseTensorPolicy, GUIDANCE
from weight_editor_runtime import Deadline, require, check_files


BRIEF='''You are AutoProteus.
This diagnostic uses small numerical fixtures. Test helpers record the requested candidate and development IDs and return protocol-stub outcomes, without generating math. Do not assert answer correctness from these stubs.
Return one complete fenced Python cell. It executes in an isolated persistent NumPy workspace. Helpers are load_tensor, save_edit, undo_edit, list_tensors, edit_status, model_info, test_candidate, compare_with_original, inspect_candidate, save_checkpoint, restore_checkpoint, submit. Print results or put a helper call as the final expression. Do only the requested operation; do not invent additional repairs. No gradients, optimizers, internet or host commands.
'''+GUIDANCE


def fixture(folder,case):
    import numpy as np
    folder=Path(folder); folder.mkdir(exist_ok=False)
    original=np.linspace(.1001,1.0999,64,dtype='<f4').reshape(8,8)
    source=folder/'source.bin';source.write_bytes(original.tobytes()*2)
    names=[f"blk.{case['block']}.attn_norm.weight",f"blk.{case['block']+1}.attn_norm.weight"]
    records={n:{'shape':[8,8],'offset':i*256,'bytes':256,'editable':True} for i,n in enumerate(names)}
    requests=[]
    def forward(r):
        require(r['mode']=='generate' and r['view'] in ('edited','original','both') and r['texts'] is None
            and isinstance(r['ids'],list) and 1<=len(r['ids'])<=2 and len(set(r['ids']))==len(r['ids'])
            and set(r['ids'])<={'dev-0','dev-1'}, 'Generate with the current candidate on development IDs')
        from tensor_workspace_feedback import evaluated_receipt
        current=p.candidate_state()['candidate_id']
        requests.append({**copy.deepcopy(r),'candidate_id':current})
        results={}
        for view in (['edited','original'] if r['view']=='both' else [r['view']]):
            results['candidate' if view=='edited' else 'original']={'receipt':evaluated_receipt(p,view,
                {'sha256':hashlib.sha256(b''.join(p.array(n,edited=view=='edited').tobytes() for n in names)).hexdigest()},'generate',r['ids']),
                'fixture_only':True,'no_target_inference':True,
                'outcomes':[{'id':i,'status':'protocol_stub','correct':None,'generated_tokens':0} for i in r['ids']]}
        return results
    p=PreciseTensorPolicy({'path':str(source),'sha256':sha(source)},records,folder/'policy',{'diagnostic_fixture':True},forward=forward)
    # Committed fixture patches use trusted fixed numbers, not model-generated host code.
    def set_value(name,index,value,label):
        a=p.array(name);a.flat[index]=value;path=folder/(label+'.f32');a.astype('<f4').tofile(path)
        p.edits[name]={'name':name,'path':str(path),'sha256':sha(path),'shape':[8,8]};p.revision+=1
    set_value(names[0],0,.5,'good-a');set_value(names[1],1,.75,'good-b')
    expected={n:p.array(n).tobytes() for n in names}
    if case['kind']=='restore_one':
        expected[names[0]]=original.tobytes()
    elif case['kind']=='restore_checkpoint':
        p.handle({'op':'checkpoint','label':case['label']})
        set_value(names[0],2,.875,'bad-a');set_value(names[1],3,.625,'bad-b')
    elif case['kind']=='one_weight':
        a=p.array(names[0]);a.flat[case['index']]=.25;expected[names[0]]=a.tobytes()
    return p,expected,requests,names


def score(p,expected,requests,outcome,*,require_submit=None,submission_policy=None,write_policy='allowed'):
    submission_policy=submission_policy or ('required' if require_submit else 'forbidden')
    require(submission_policy in ('required','forbidden','optional'),'Invalid submission policy')
    require(write_policy in ('allowed','forbidden'),'Invalid write policy')
    exact=all(p.array(n).tobytes()==raw for n,raw in expected.items())
    coverage=p.coverage(['dev-0','dev-1'])
    tested=coverage['complete']
    writes=[r for r in p.operation_history[p.task_start:] if r['op'] in ('write_start','write_chunk','write_finish','undo','restore')]
    compliant=write_policy=='allowed' or not writes
    submitted_ok=submission_policy=='optional' or p.submitted==(submission_policy=='required')
    complete=not outcome.get('error') and p.upload is None and p.download is None
    return {'numeric_state_correct':exact,'correct_candidate_test_coverage':tested,'test_calls':len(requests),
        'coverage':coverage,'operation_compliant':compliant,'submission_policy':submission_policy,
        'submission_compliant':submitted_ok,'cell_completed':bool(complete),
        'submitted':p.submitted,'cell_error':outcome.get('error'),
        'correct':bool(exact and tested and compliant and submitted_ok and complete)}


def cases():
    result=[]
    for split,block,label,index in [('dev',0,'useful',7),('confirmation',6,'retained',11)]:
        for kind in ('restore_one','restore_checkpoint','test_saved','one_weight'):
            a=f'blk.{block}.attn_norm.weight';b=f'blk.{block+1}.attn_norm.weight'
            task={
                'restore_one':f"The last rollback of {a} reloaded edited=True and saved it, leaving the same bad fingerprint. Restore ONLY {a} to the immutable original. Keep the useful edit in {b} exactly. Then generate candidate answers for dev-0 and dev-1 and submit.",
                'restore_checkpoint':f"Checkpoint '{label}' contains the measured candidate we want to keep. Later changes made the current candidate worse in both tensors. Restore the complete saved candidate, generate answers for dev-0 and dev-1, then submit. Do not restore the original model instead.",
                'test_saved':"There are two saved tensor edits. The previous inspect_candidate(['dev-0']) call only inspected literal ID text. Generate answers for dev-0 and dev-1 using the current saved edits. Display the result. Do not change any weights or submit.",
                'one_weight':f"In {a}, set flattened index {index} to 0.25. Keep every other value of both tensors exactly as currently saved. Generate answers for dev-0 and dev-1 and submit."}[kind]
            c={'id':split+'-'+kind.replace('_','-'),'split':split,'kind':kind,'block':block,'label':label,'index':index,
                'task':task,'require_submit':kind!='test_saved'}
            c['rendered_prompt']='<|im_start|>system\n'+BRIEF+'<|im_end|>\n<|im_start|>user\n'+task+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
            c['rng_seed']=int.from_bytes(hashlib.sha256(c['id'].encode()).digest()[:4],'little');result.append(c)
    return result


def prepare(project,output):
    sys.path.insert(0,str(Path(project).resolve()))
    from tokenizers import Tokenizer
    from tensor_workspace_image import build, WHEEL
    project,output=Path(project).resolve(),Path(output).resolve();require(not output.exists(),'Never overwrite diagnostic')
    old=read(project/'.data/manual4b-targeted-shared-gpu-20261103-v4/manifest.json')
    output.mkdir();(output/'code').mkdir();(output/'requests').mkdir();(output/'runs').mkdir()
    names=set(old['code'])|{'tensor_workspace_code_diagnostic.py','tensor_workspace_precision.py','tensor_workspace_intermediates.py'}
    for name in names:
        path=project/'evaluations'/name
        if name=='windows_job.py':path=project/'controller'/name
        shutil.copyfile(path,output/'code'/name)
    image=build(project,output/'image',project/'.data/tensor-workspace-20261103/dependencies'/WHEEL)
    tok=Tokenizer.from_file(str(Path(old['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
    rows=cases()
    for c in rows:c['input_ids']=tok.encode(c['rendered_prompt'],add_special_tokens=False).ids
    atomic(output/'inputs.json',{'cases':rows});atomic(output/'hidden-golds.json',{})
    atomic(output/'tensor-catalog.json',{})
    plan=copy.deepcopy(old);plan.update(scope='Executable code-effect diagnostic; both editors use the same new workspace',image=image,
        code={p.name:sha(p) for p in (output/'code').iterdir()},data={n:sha(output/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json')},
        diagnostic={'seconds':5400,'generated_tokens':131072,'cases_per_arm':8,
            'models':['unchanged','targeted'],'not_a_math_or_growth_qualification':True,
            'manual_edit_gate':'No further manual patch unless non-ceiling generated code decisions and a causally localized actual behavior gain are established; choice margins alone do not qualify'})
    plan['limits']['total_seconds']=5400
    for key in ('baseline_import','predecessor_completion','qualification_continuation','qualification_resume','resume'):
        plan.pop(key,None)
    plan['design']['vm_preflight_receipt']=str(output/'calibration/RESULT.json')
    plan['design'].pop('vm_preflight_sha256',None)
    atomic(output/'manifest.json',plan);(output/'manifest.sha256').write_text(identity(plan))
    atomic(output/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(plan),'explicit_user_authorization':False,
        'notice':'Preparation cannot supply permission; bind the actual user instruction before execution.'})
    (output/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\nsys.path.insert(0,json.loads((r/'manifest.json').read_text())['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_code_diagnostic import execute\nexecute(r)\n",encoding='utf8')
    return {'root':str(output),'plan':identity(plan)}


def calibrate(project,root):
    sys.path.insert(0,str(Path(project).resolve()))
    from tensor_workspace_vm import TensorVM
    root=Path(root);plan=read(root/'manifest.json');folder=root/'calibration';folder.mkdir(exist_ok=False)
    vm=None;rows=[]
    try:
        vm=TensorVM(project,plan['image'],folder/'vm.json',Deadline(240))
        positive={
            'restore_one':lambda c,n:f"undo_edit({n[0]!r})\nprint(test_candidate(['dev-0','dev-1']))\nsubmit()",
            'restore_checkpoint':lambda c,n:f"restore_checkpoint({c['label']!r})\nprint(test_candidate(['dev-0','dev-1']))\nsubmit()",
            'test_saved':lambda c,n:"print(test_candidate(['dev-0','dev-1']))",
            'one_weight':lambda c,n:f"w=load_tensor({n[0]!r})\nw.flat[{c['index']}]=.25\nsave_edit({n[0]!r},w)\nprint(test_candidate(['dev-0','dev-1']))\nsubmit()"}
        for c in cases()[:4]:
            p,expected,requests,n=fixture(folder/(c['id']+'-positive'),c)
            outcome=vm.execute(positive[c['kind']](c,n),p)
            graded=score(p,expected,requests,outcome,require_submit=c['require_submit'])
            require(graded['correct'],'Positive control failed: '+str(graded));rows.append({'id':c['id'],'positive':graded})
            p,expected,requests,n=fixture(folder/(c['id']+'-negative'),c)
            bad=f"print(load_tensor({n[0]!r}).shape)" # plausible inspection without the requested effect
            outcome=vm.execute(bad,p);negative=score(p,expected,requests,outcome,require_submit=c['require_submit'])
            require(not negative['correct'],'No-op negative accepted');rows[-1]['negative']=negative
        # Explicit historical failure controls: re-saving current state and probing IDs.
        c=cases()[0];p,expected,requests,n=fixture(folder/'false-rollback',c)
        outcome=vm.execute(f"w=load_tensor({n[0]!r},edited=True)\nsave_edit({n[0]!r},w)\nprint(test_candidate(['dev-0','dev-1']))\nsubmit()",p)
        require(not score(p,expected,requests,outcome,require_submit=True)['correct'],'False rollback accepted')
        outcome=vm.execute("inspect_candidate(['dev-0'])",p)
        require(outcome['error'] and 'test_candidate' in outcome['error'],'Ambiguous probe ID accepted')
        c=cases()[2];p,expected,requests,n=fixture(folder/'split-tests',c)
        outcome=vm.execute("print(test_candidate(['dev-1']))\nprint(test_candidate(['dev-0']))",p)
        require(score(p,expected,requests,outcome,require_submit=False)['correct'],'Valid split/reordered tests rejected')
        p,expected,requests,n=fixture(folder/'comparison-route',c)
        outcome=vm.execute("print(compare_with_original(['dev-1','dev-0']))",p)
        require(score(p,expected,requests,outcome,require_submit=False)['correct'],'Valid candidate-plus-original comparison rejected')
        p,expected,requests,n=fixture(folder/'original-only',c)
        outcome=vm.execute("print(__import__('tensor_kernel').forward(['dev-0','dev-1'],view='original'))",p)
        require(not score(p,expected,requests,outcome,require_submit=False)['correct'],'Original-only request credited as candidate test')
        atomic(folder/'RESULT.json',{'status':'passed','cases':rows,'historical_failure_controls_rejected':True,'real_vm':True,'no_gpu':True})
    finally:
        if vm:vm.close()


def execute(root):
    from tensor_workspace_intermediates import enable_sharing
    from tensor_workspace_study import Study, code_cell
    from tensor_workspace_vm import TensorVM
    root=Path(root);plan=read(root/'manifest.json')
    with exclusive(root):
        require(not (root/'runner.json').exists(),'No implicit retries');enable_sharing();study=Study(root)
        output={};status='running';error=None
        try:
            for arm in plan['diagnostic']['models']:
                study.arm=arm;study.state.update(phase='generate_real_cells',arm=arm);study.save()
                responses=study.inference('editor',plan['models'][arm],study.cases,remaining=65536)
                output[arm]=[]
                for c,response in zip(study.cases,responses):
                    directory=root/arm/c['id'];directory.parent.mkdir(exist_ok=True);p,expected,requests,n=fixture(directory,c)
                    vm=None
                    try:
                        require(response['finish_reason']=='eos','Generation did not finish')
                        code,_=code_cell(response['raw_text'])
                        try:vm=TensorVM(plan['project'],plan['image'],directory/'vm.json',study.deadline.child(180))
                        except Exception as exc:raise __import__('tensor_workspace_study').InfrastructureStop('Diagnostic VM startup: '+str(exc)) from exc
                        outcome=vm.execute(code,p);graded=score(p,expected,requests,outcome,require_submit=c['require_submit'])
                    except Exception as exc:
                        outcome={'error':type(exc).__name__+': '+str(exc)};graded={'correct':False,'error':outcome['error'],
                            'failure_stage':'cell_execution_or_resource' if vm is not None else 'model_response_format'}
                    finally:
                        if vm:vm.close()
                    row={'id':c['id'],'split':c['split'],'generated_tokens':response['generated_tokens'],**graded}
                    atomic(directory/'EFFECT.json',{'score':row,'outcome':outcome,'requests':requests,'final':p.status()})
                    output[arm].append(row);atomic(root/'code-results.json',output)
            status='completed'
        except BaseException as exc:status='stopped';error=type(exc).__name__+': '+str(exc)
        finally:
            study.state.update(status=status,error=error,phase='closed',ended_unix=time.time());study.save()
            closed=[read(p) for p in (root/'runs').glob('*/CLOSED.json')]
            result={'status':status,'error':error,'results':{a:{'correct':sum(r['correct'] for r in v),'checked':len(v)} for a,v in output.items()},
                'all_owned_workers_closed':all(c['owned_worker_closed'] for c in closed),
                'all_owned_vms_closed':all(read(p)['owned_vm_closed'] for p in root.glob('*/*/vm.json')),
                'manual_patch_not_automatically_qualified':True}
            atomic(root/'RESULT.json',result);print(result,flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='calibrate':calibrate(*sys.argv[2:])
    else:execute(sys.argv[2])
