"""Fresh clarified unchanged-editor gate; conditional reviewed 8K target pilot."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from lora6k_state import atomic,read,sha,identity,exclusive
from tensor_workspace_overnight import OvernightStudy,fixture,recovery_grade,desktop_lease,admission,AUTHORIZATION
from tensor_workspace_schema_comparison import readonly_fixture,frozen_brief
from tensor_workspace_code_diagnostic import score
from tensor_workspace_study import Study,code_cell
from tensor_workspace_vm import TensorVM
from tensor_workspace_errors import InfrastructureStop,CellAllowanceExceeded
from weight_editor_runtime import require,Deadline,check_files

CAPS={'diagnostic_cells':65536,'diagnostic_recovery':32768,'pilot_editor':49152,
      'pilot_feedback':32768,'pilot_baseline':16384,'pilot_confirmation':65536,'pilot_preservation':32768}
TOTAL=299008
SCHEMA="""Return structure: test_candidate(ids) returns {'candidate': {'receipt': {...}, 'outcomes': [{'id': ..., 'status': ..., 'correct': ..., 'generated_tokens': ...}, ...]}}. Read result['candidate']['outcomes']; there is no top-level 'outcomes', 'outcome_id' or 'status'. Each outcome's ID field is 'id'. compare_with_original(ids) returns both 'candidate' and 'original' entries of that same structure. Printing the complete returned result is valid; parsing is optional.
"""
STUB="In these eight explicit tasks, outcomes have status='protocol_stub' and correct=None. They establish routing and measured candidate identity only, not mathematical correctness. No target-model inference occurs.\n"
FEEDBACK="In this recovery episode, outcomes have status='synthetic_feedback' and correct is a Boolean: True exactly for the starting saved numeric content and False otherwise. This is deterministic synthetic objective feedback, not a math answer or a protocol-stub correctness claim. No target-model inference occurs.\n"


def fresh_cases():
    result=[]
    for variant,block,start,end,values,bad,index,value,label in [
        ('willow',2,.2345,.9843,[.5625,.8125,.6875],[.90625,.34375],3081,.3125,'willow-kept'),
        ('aspen',10,.3456,1.3452,[.4375,.9375,.53125],[.84375,.28125],8203,.4375,'aspen-kept')]:
        a=f'blk.{block}.attn_norm.weight';b=f'blk.{block+1}.attn_norm.weight';m=f'blk.{block}.attn_qkv.weight'
        tasks={
            'restore_one':f'Restore only {a} to its immutable original values. Preserve the saved numerical content in {b} and {m} exactly. Generate dev-0 and dev-1 with the resulting candidate, then submit().',
            'restore_checkpoint':f'Checkpoint {label!r} contains the candidate to retain before later changes in two tensors. Restore that complete checkpoint. Generate dev-0 and dev-1 with that final content and submit(). Do not substitute the original model.',
            'test_saved':f'The saved {variant} candidate contains three tensor edits. Generate dev-0 and dev-1 using all current saved edits, and display the returned results. Preserve every numerical value exactly. Do not write, undo, restore, checkpoint or submit.',
            'one_weight':f'In matrix {m}, set flattened index {index} to {value}. Preserve all other values of all three tensors exactly. Generate dev-0 and dev-1 using the saved final candidate, then submit().'}
        for kind,task in tasks.items():
            result.append({'id':'fresh-'+variant+'-'+kind.replace('_','-'),'kind':kind,'split':'fresh-confirmation',
                'block':block,'index':index,'edit_value':value,'label':label,'base_start':start,'base_end':end,
                'initial_values':values,'bad_values':bad,'task':task,
                'submission_policy':'forbidden' if kind=='test_saved' else 'required',
                'write_policy':'forbidden' if kind=='test_saved' else 'allowed','display_required':kind=='test_saved'})
    return result


def recovery_case():
    return {'id':'fresh-recovery','kind':'test_saved','block':16,'index':0,'label':'recovery',
        'base_start':.4567,'base_end':1.2345,'initial_values':[.59375,.78125,.71875],
        'perturb_index':19,'perturb_value':.96875,
        'task':"This is one synthetic recovery episode with at most four Python cells. First measure the current saved candidate on dev-0 and dev-1 and save a named checkpoint. The harness will then introduce a later numerical perturbation. Measure that later state on both IDs, use the Boolean feedback to select the better measured candidate, recover its exact contents, generate both IDs again after recovery, and submit(). Do not propose a new repair. The starting saved contents are the synthetic objective's preferred state."}


def briefs(project):
    base=frozen_brief(Path(project)/'.data/apwt-overnight-20261104-002/code')
    base=base.replace('Test helpers record the requested candidate and development IDs and return protocol-stub outcomes, without generating math. Do not assert answer correctness from these stubs.',
        'This is a synthetic numerical diagnostic. Evaluation semantics are specified below; no helper runs target math inference.')
    base=base.replace("test_candidate(['dev-0']) generates an answer.","test_candidate(['dev-0']) requests the configured synthetic fixture evaluation.")
    return {'explicit':base+SCHEMA+STUB,'recovery':base+SCHEMA+FEEDBACK}


def explicit_grade(p,expected,requests,outcome,case,attempts=()):
    result=score(p,expected,requests,outcome,submission_policy=case['submission_policy'],write_policy=case['write_policy'])
    text=outcome.get('output','');displayed=all(i in text for i in ('dev-0','dev-1')) and 'protocol_stub' in text
    result.update(display_completed=displayed,display_required=case['display_required'],forbidden_operation_count=len(attempts))
    result['correct']=bool(result['correct'] and not attempts and (displayed or not case['display_required']))
    return result


def fresh_recovery_grade(p,expected,requests,outcome,perturbed):
    result=recovery_grade(p,expected,requests,outcome,perturbed)
    current=p.candidate_state()['candidate_id']
    final_ids={i for r in p.receipt_ledger if r['view']=='edited' and r['mode']=='generate'
        and r['candidate_id']==current and r['revision']==p.revision for i in r['ids']}
    worse_ids={o['id'] for r in p.receipt_ledger if r['view']=='edited' and r['mode']=='generate'
        for o in r.get('outcomes',[]) if o.get('correct') is False}
    result.update(final_revision_retested={'dev-0','dev-1'}<=final_ids,both_worse_cases_measured={'dev-0','dev-1'}<=worse_ids)
    result['correct']=bool(result['correct'] and result['final_revision_retested'] and result['both_worse_cases_measured'])
    return result


def positive(case,names):
    op={'restore_one':f'undo_edit({names[0]!r})',
        'restore_checkpoint':f'restore_checkpoint({case["label"]!r})','test_saved':'',
        'one_weight':f'w=load_tensor({names[2]!r})\nw.flat[{case["index"]}]={case["edit_value"]}\nsave_edit({names[2]!r},w)'}[case['kind']]
    return op+"\nprint(test_candidate(['dev-0','dev-1']))"+('\nsubmit()' if case['submission_policy']=='required' else '')


def calibrate(project,root):
    root=Path(root);root.mkdir(exist_ok=False);image=read(Path(project)/'.data/apwt-schema-20261104-001/manifest.json')['image']
    vm=None;rows=[]
    try:
        vm=TensorVM(project,image,root/'vm.json',Deadline(600))
        for case in fresh_cases():
            if case['kind']=='test_saved':p,expected,requests,n,attempts=readonly_fixture(root/case['id'],case)
            else:p,expected,requests,n,_=fixture(root/case['id'],case);attempts=[]
            outcome=vm.execute(positive(case,n),p);graded=explicit_grade(p,expected,requests,outcome,case,attempts)
            require(graded['correct'],'Fresh explicit calibration failed: '+case['id']);rows.append({'id':case['id'],**graded})
            require(all(o['correct'] is None for r in p.receipt_ledger for o in r['outcomes']),'Explicit task returned non-null correctness')
        case=recovery_case();p,expected,requests,n,fixed=fixture(root/'recovery',case,recovery=True)
        first=vm.execute("print(test_candidate(['dev-0','dev-1']))\nsave_checkpoint('retained')",p);require(not first['error'],'Recovery setup failed')
        fixed(n[0],case['perturb_index'],case['perturb_value'],'harness-perturbation')
        outcome=vm.execute("print(test_candidate(['dev-0','dev-1']))\nrestore_checkpoint('retained')\nprint(test_candidate(['dev-0','dev-1']))\nsubmit()",p)
        graded=fresh_recovery_grade(p,expected,requests,outcome,True)
        require(graded['correct'] and all(type(o['correct']) is bool for r in p.receipt_ledger for o in r['outcomes']),
            'Recovery calibration failed or returned non-Boolean feedback');rows.append({'id':'recovery',**graded})
    finally:
        if vm:vm.close()
    require(read(root/'vm.json')['owned_vm_closed'],'Calibration VM remained alive')
    atomic(root/'RESULT.json',{'status':'passed','controls':rows,'model_inference':False,'owned_vm_closed':True})


def prepare(project,root,calibration):
    from tokenizers import Tokenizer
    project,root,calibration=map(lambda x:Path(x).resolve(),(project,root,calibration))
    require(not root.exists(),'No replay or overwrite');require(read(calibration/'RESULT.json')['status']=='passed','Fresh calibration required')
    prior=project/'.data/apwt-overnight-20261104-002';old=read(prior/'manifest.json');audit=read(prior/'POST-RUN-AUDIT.json')
    require(audit['pilot_run'] is False and all(read(prior/'BUDGET.json')['categories'][k]==0 for k in CAPS if k.startswith('pilot_')),
        'Previously sealed pilot cases have been used')
    check_files(prior,old['data']);root.mkdir();(root/'code').mkdir();(root/'runs').mkdir();(root/'requests').mkdir()
    for name in set(old['code'])|{'tensor_workspace_schema_comparison.py','tensor_workspace_fresh_gate.py'}:
        shutil.copyfile(project/('controller' if name=='windows_job.py' else 'evaluations')/name,root/'code'/name)
    for name in ('inputs.json','hidden-golds.json','tensor-catalog.json'):shutil.copyfile(prior/name,root/name)
    prompt_briefs=briefs(project);cases=fresh_cases();tok=Tokenizer.from_file(str(Path(old['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
    for case in cases:
        case['rendered_prompt']='<|im_start|>system\n'+prompt_briefs['explicit']+'<|im_end|>\n<|im_start|>user\n'+case['task']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
        case['input_ids']=tok.encode(case['rendered_prompt'],add_special_tokens=False).ids
        case['rng_seed']=int.from_bytes(hashlib.sha256(('apwt-fresh-clarified-v1:'+case['id']).encode()).digest()[:4],'little')
    atomic(root/'diagnostic-inputs.json',{'cases':cases});atomic(root/'recovery-input.json',recovery_case());atomic(root/'briefs.json',prompt_briefs)
    atomic(root/'AUTHORIZATION.json',{'user_instruction':AUTHORIZATION,'explicit_user_authorization':False,
        'source_thread_id':'REDACTED-PRIVATE-THREAD',
        'scope':'Proteus-approved Critic continuation: eight fresh unchanged-editor tasks plus four-turn recovery; conditional reviewed 8K pilot only after all pass',
        'diagnostic_tokens':98304,'diagnostic_seconds':3600,'pilot_tokens':200704,'pilot_seconds':5400,'combined_tokens':TOTAL,
        'no_retries':True,'no_prompt_tuning':True,'no_manual_editor_weight_patch':True})
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','models','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol')}
    plan.update(scope='Fresh clarified unchanged-editor gate and conditional reviewed 8K pilot',overnight=True,numeric_policy='precise-v2',
        code={p.name:sha(p) for p in (root/'code').iterdir()},controller_files={str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')},
        data={n:sha(root/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json','diagnostic-inputs.json','recovery-input.json','briefs.json','AUTHORIZATION.json')},
        budget_categories=CAPS,combined_sampled_token_ceiling=TOTAL,interruption_reserve=4096,
        limits=copy.deepcopy(old['limits']),design=copy.deepcopy(old['design']))
    plan['limits']['total_seconds']=3600
    plan['design'].update(arms=['unchanged'],diagnostic_seconds=3600,pilot_seconds=5400,
        vm_preflight_receipt=str(calibration/'RESULT.json'),vm_preflight_sha256=sha(calibration/'RESULT.json'),
        pilot_selection='Only eight new explicit successes plus the new recovery success qualify; no historical pass credit',
        no_retries=True,no_prompt_tuning=True,fresh_instance_values=True)
    plan['sealed_pilot_provenance']={'root':str(prior),'files':{n:sha(prior/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json','POST-RUN-AUDIT.json','BUDGET.json')},
        'policy':'Same previously reviewed eight-question pilot; never exposed to an editor or target inference. No historical model performance reused.'}
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\np=json.loads((r/'manifest.json').read_text())\nsys.path.insert(0,p['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_fresh_gate import run\nrun(r)\n",encoding='utf8')
    return {'root':str(root),'plan_identity':identity(plan),'diagnostic_tokens':98304,'combined_tokens':TOTAL}


class FreshStudy(OvernightStudy):
    def __init__(self,root):
        super().__init__(root)
        source=self.plan['sealed_pilot_provenance'];check_files(source['root'],source['files'])
        self.brief+='\nIn this real-target pilot only, test_candidate performs actual 0.8B generation; outcomes contain independently graded Boolean correctness, not synthetic stubs. The nested candidate/outcomes structure is unchanged.\n'

    def reconcile(self):
        u=read(self.root/'usage.json') if (self.root/'usage.json').exists() else {'phases':{},'charged_tokens':0}
        counts={k:0 for k in CAPS}
        for phase,row in u['phases'].items():counts[self.categories[phase]]+=row['charged_tokens']
        require(all(counts[k]<=CAPS[k] for k in CAPS) and u['charged_tokens']<=TOTAL,'Fresh study token ceiling exceeded')
        result={'categories':counts,'phase_categories':self.categories,'charged_tokens':u['charged_tokens'],'ceiling':TOTAL,
            'uncertain_tokens_upper_bound':sum(r['uncertain_tokens_upper_bound'] for r in u['phases'].values()),
            'historical_inference_or_passes_reused':False,'cached_baselines_charged_again':False}
        atomic(self.root/'BUDGET.json',result);return result

    def inference(self,mode,model,cases,*,remaining=1048576):
        category=self.budget_category;require(category in CAPS,'Missing stage budget')
        allowance=len(cases)*8192 if mode!='probe' else 0
        require(self.reconcile()['categories'][category]+allowance<=CAPS[category],'Stage allowance exhausted')
        phase='call-'+str(self.calls+1).zfill(3);self.categories[phase]=category;self.reconcile()
        try:rows=Study.inference(self,mode,model,cases,remaining=allowance)
        finally:self.reconcile()
        if mode=='generate':
            for row in rows:
                raw=read(row['response_file']);row['reference_correct']=row['correct'];row['closed_thinking']='</think>' in raw['raw_text']
                row['correct']=bool(row['correct'] and row['finish_reason']=='eos' and row['closed_thinking'])
            if rows:atomic(Path(rows[0]['response_file']).parent/'checked.json',rows)
        return rows

    def diagnostic(self):
        rows=[];self.arm='unchanged'
        for case in read(self.root/'diagnostic-inputs.json')['cases']:
            self.state.update(phase='fresh_clarified_diagnostic',case=case['id'],arm='unchanged');self.save();self.budget_category='diagnostic_cells'
            response=self.inference('editor',self.plan['models']['unchanged'],[case])[0]
            folder=self.root/'fresh-diagnostic'/case['id'];folder.parent.mkdir(exist_ok=True)
            if case['kind']=='test_saved':p,expected,requests,n,attempts=readonly_fixture(folder,case)
            else:p,expected,requests,n,_=fixture(folder,case);attempts=[]
            outcome={'error':'No executable cell','output':''};vm=None
            row={'id':case['id'],'kind':case['kind'],'generated_tokens':response['generated_tokens'],'finish_reason':response['finish_reason']}
            try:
                require(response['finish_reason']=='eos','Editor response truncated; no code executed');code,_=code_cell(response['raw_text'])
                try:vm=TensorVM(self.project,self.plan['image'],folder/'vm.json',self.deadline.child(180))
                except Exception as error:raise InfrastructureStop('VM startup: '+str(error)) from error
                outcome=vm.execute(code,p)
            except (ValueError,CellAllowanceExceeded) as error:outcome={'error':type(error).__name__+': '+str(error),'output':''}
            finally:
                if vm:vm.close()
                row.update(explicit_grade(p,expected,requests,outcome,case,attempts))
                atomic(folder/'EFFECT.json',{'score':row,'outcome':outcome,'requests':requests,'receipts':p.receipt_ledger,'operations':p.operation_history,'final':p.status()})
            rows.append(row);atomic(self.root/'fresh-diagnostic-results.json',rows)
        episode=self.recovery('unchanged');gate=bool(len(rows)==8 and all(r['correct'] for r in rows) and episode['correct'])
        atomic(self.root/'DIAGNOSTIC-GATE.json',{'passed':gate,'explicit_correct':sum(r['correct'] for r in rows),
            'explicit_checked':8,'recovery_correct':episode['correct'],'historical_passes_used':0})
        return gate

    def recovery(self,arm):
        from tokenizers import Tokenizer
        case=read(self.root/'recovery-input.json');folder=self.root/'fresh-recovery'
        p,expected,requests,n,fixed=fixture(folder,case,recovery=True)
        prompt_brief=read(self.root/'briefs.json')['recovery'];messages=[{'role':'user','content':case['task']}]
        tok=Tokenizer.from_file(str(Path(self.plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
        vm=None;perturbed=False;outcome={'error':'No completed recovery cell','output':''};result={'correct':False,'turns':0}
        try:
            try:vm=TensorVM(self.project,self.plan['image'],folder/'vm.json',self.deadline.child(900))
            except Exception as error:raise InfrastructureStop('Recovery VM startup: '+str(error)) from error
            for turn in range(4):
                text='<|im_start|>system\n'+prompt_brief+'<|im_end|>\n'+''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n' for m in messages)+'<|im_start|>assistant\n<think>\n'
                request={'id':'fresh-recovery-turn-'+str(turn),'rendered_prompt':text,'input_ids':tok.encode(text,add_special_tokens=False).ids,'rng_seed':2026110451+turn}
                self.budget_category='diagnostic_recovery';self.state.update(phase='fresh_recovery',turn=turn);self.save()
                response=self.inference('editor',self.plan['models']['unchanged'],[request])[0];result['turns']=turn+1
                require(response['finish_reason']=='eos','Recovery response truncated; no code executed');code,final=code_cell(response['raw_text'])
                outcome=vm.execute(code,p);atomic(folder/('turn-'+str(turn)+'.json'),{'code':code,'outcome':outcome})
                messages.extend([{'role':'assistant','content':final},{'role':'user','content':json.dumps(outcome)}])
                if outcome['error'] or p.submitted:break
                if not perturbed and p.checkpoints and p.coverage(['dev-0','dev-1'])['complete']:
                    fixed(n[0],case['perturb_index'],case['perturb_value'],'harness-later-candidate');perturbed=True
                    messages.append({'role':'user','content':'The declared harness perturbation is now applied. Measure the current later state before choosing, use the Boolean feedback, recover the preferred checkpoint, retest both IDs, then submit.'})
            result.update(fresh_recovery_grade(p,expected,requests,outcome,perturbed),receipts=p.receipt_ledger,operations=p.operation_history)
        except (ValueError,CellAllowanceExceeded) as error:result.update(correct=False,error=type(error).__name__+': '+str(error))
        finally:
            if vm:vm.close()
            atomic(folder/'RESULT.json',result)
        return result


def run(root):
    root=Path(root).resolve();plan=read(root/'manifest.json');began=time.monotonic()
    with desktop_lease(plan['project']),exclusive(root):
        require(not (root/'runner.json').exists() and not (root/'RESULT.json').exists(),'No retries or implicit replay')
        result={'status':'starting','pilot_run':False};study=None;pilot_entered=False;gate_passed=False
        try:
            admission(plan['project'],root/'initial-admission');study=FreshStudy(root)
            study.deadline=Deadline(end=began+3600);study.worker_deadline=study.deadline
            gate_passed=study.diagnostic()
            if gate_passed:
                pilot_deadline=Deadline(5400);admission(plan['project'],root/'pilot-admission')
                pilot_entered=True
                result=study.pilot('unchanged',deadline=pilot_deadline);result['pilot_run']=True
            else:result={'status':'diagnostic_gate_stopped','pilot_run':False,'reason':'New all-eight-plus-recovery gate failed'}
        except BaseException as error:result.update(status='stopped',error=type(error).__name__+': '+str(error))
        finally:
            if study and study.vm:study.vm.close();study.vm=None
            result['budget']=study.reconcile() if study else {'charged_tokens':0,'ceiling':TOTAL}
            result['pilot_run']=pilot_entered;result['fresh_diagnostic_gate_passed']=gate_passed
            result['wall_seconds']=time.monotonic()-began
            workers=[read(p) for p in (root/'runs').glob('*/CLOSED.json')];vms=[read(p) for p in root.glob('**/vm.json')]
            result['all_owned_workers_closed']=all(r.get('owned_worker_closed') for r in workers)
            result['all_owned_vms_closed']=all(r.get('owned_vm_closed') for r in vms)
            result['model_hashes_after']={k:sha(plan['models'][k]['path']) for k in ('original_target','unchanged')}
            result['original_models_unchanged']=all(result['model_hashes_after'][k]==plan['models'][k]['sha256'] for k in result['model_hashes_after'])
            if study:study.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));study.save()
            atomic(root/'RESULT.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='calibrate':
        project,root=sys.argv[2:4]
        with desktop_lease(project):admission(project,Path(str(root)+'-admission'));calibrate(project,root)
    elif sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='run':run(sys.argv[2])
