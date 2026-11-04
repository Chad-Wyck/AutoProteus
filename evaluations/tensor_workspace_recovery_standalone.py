"""One frozen, thinking-enabled synthetic recovery episode; no downstream pilot."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from lora6k_state import atomic,read,sha,identity,exclusive
from tensor_workspace_overnight import fixture,desktop_lease,admission,AUTHORIZATION
from tensor_workspace_study import Study,code_cell
from tensor_workspace_code_diagnostic import score
from tensor_workspace_vm import TensorVM
from tensor_workspace_vm_startup import bound_serial
from tensor_workspace_errors import InfrastructureStop,CellAllowanceExceeded
from weight_editor_runtime import require,Deadline,check_files

LIMIT=32768
SECONDS=1200
IDS={'dev-0','dev-1'}
NOTICE='The declared harness perturbation is now applied. Measure the current later state before choosing, use the Boolean feedback, recover the preferred checkpoint, retest both IDs, then submit.'


class RecoveryEvidence:
    """Host-owned ordered evidence; editor-visible helper results are unchanged."""
    def __init__(self,p):
        self.p=p;self.initial_id=p.candidate_state()['candidate_id'];self.worse_id=None
        self.initial_checkpoints=[];self.events=[];self.valid_restores=[];self.valid_submissions=[]
        self.mutation_attempts=[];self.original=p.handle;p.handle=self.handle

    def measured(self,candidate,correct,*,after=0,revision=None):
        return {o['id'] for r in self.p.receipt_ledger if r['receipt_index']>=after and r['completed']
            and r['view']=='edited' and r['mode']=='generate' and r['candidate_id']==candidate
            and (revision is None or r['revision']==revision)
            for o in r.get('outcomes',[]) if o.get('correct') is correct}

    def ready_for_perturbation(self):
        labels=[name for name,row in self.p.checkpoints.items() if row['candidate_id']==self.initial_id]
        return bool(labels and self.p.candidate_state()['candidate_id']==self.initial_id
            and IDS<=self.measured(self.initial_id,True))

    def note_perturbation(self):
        self.initial_checkpoints=[name for name,row in self.p.checkpoints.items() if row['candidate_id']==self.initial_id]
        self.worse_id=self.p.candidate_state()['candidate_id']
        require(self.worse_id!=self.initial_id,'Harness perturbation must change candidate content')
        self.events.append({'kind':'harness_perturbation','candidate_id':self.worse_id,
            'initial_candidate_id':self.initial_id,'checkpoint_labels':self.initial_checkpoints,
            'receipt_boundary':len(self.p.receipt_ledger),'authorship':'trusted harness, not local editor'})

    def final_fresh_ids(self):
        if not self.valid_restores:return set()
        restored=self.valid_restores[-1]
        return self.measured(self.initial_id,True,after=restored['receipt_boundary'],revision=restored['revision'])

    def handle(self,r):
        op=r.get('op') if isinstance(r,dict) else None
        before_id=self.p.candidate_state()['candidate_id']
        if op in ('write_start','write_chunk','write_finish','undo'):
            self.mutation_attempts.append({'op':op,'name':r.get('name')})
        worse_before=bool(self.worse_id and IDS<=self.measured(self.worse_id,False))
        submit_ready=bool(self.valid_restores and IDS<=self.final_fresh_ids()
            and self.p.candidate_state()['candidate_id']==self.initial_id)
        result=self.original(r)
        if op=='checkpoint':self.events.append({'kind':'checkpoint','label':r['label'],
            'candidate_id':self.p.candidate_state()['candidate_id'],'receipt_boundary':len(self.p.receipt_ledger)})
        if op=='restore':
            event={'kind':'restore','label':r['label'],'candidate_id':self.p.candidate_state()['candidate_id'],
                'previous_candidate_id':before_id,'revision':self.p.revision,'receipt_boundary':len(self.p.receipt_ledger),
                'both_worse_ids_measured_before_restore':worse_before}
            self.events.append(event)
            if worse_before and before_id!=self.initial_id and r['label'] in self.initial_checkpoints and event['candidate_id']==self.initial_id:
                self.valid_restores.append(event)
        if op=='submit':
            event={'kind':'submit','candidate_id':self.p.candidate_state()['candidate_id'],
                'receipt_boundary':len(self.p.receipt_ledger),'fresh_tests_preceded_submission':submit_ready}
            self.events.append(event)
            if submit_ready:self.valid_submissions.append(event)
        return result

    def grade(self,expected,requests,outcome):
        result=score(self.p,expected,requests,outcome,submission_policy='required')
        milestones={'initial_both_ids_measured':IDS<=self.measured(self.initial_id,True),
            'initial_checkpoint_before_perturbation':bool(self.initial_checkpoints),'harness_perturbation_applied':self.worse_id is not None,
            'both_perturbed_ids_measured':bool(self.worse_id and IDS<=self.measured(self.worse_id,False)),
            'exact_checkpoint_restoration_after_worse_tests':bool(self.valid_restores),
            'fresh_both_ids_after_restoration':IDS<=self.final_fresh_ids(),
            'submission_after_fresh_tests':bool(self.valid_submissions),
            'no_unrequested_weight_operations':not self.mutation_attempts}
        result.update(milestones=milestones,correct=bool(result['correct'] and all(milestones.values())),
            initial_candidate_id=self.initial_id,perturbed_candidate_id=self.worse_id,
            final_candidate_id=self.p.candidate_state()['candidate_id'],events=copy.deepcopy(self.events),
            mutation_attempts=copy.deepcopy(self.mutation_attempts))
        return result


def prepare(project,root):
    project,root=Path(project).resolve(),Path(root).resolve();require(not root.exists(),'No overwrite/replay')
    previous=project/'.data/apwt-fresh-gate-20261104-001';old=read(previous/'manifest.json')
    check_files(previous,old['data'])
    require(read(previous/'fresh-recovery/RESULT.json')['turns']==0
        and read(previous/'BUDGET.json')['categories']['diagnostic_recovery']==0,'Prior episode must be genuinely unrun')
    require(read(previous/'POST-RUN-AUDIT.json')['recovery']['status']=='UNRUN_INFRASTRUCTURE','Unrun evidence required')
    case=read(previous/'recovery-input.json');brief=read(previous/'briefs.json')['recovery']
    require('correct is a Boolean' in brief and "result['candidate']['outcomes']" in brief,'Truthful Boolean nested feedback contract required')
    infra=project/'.data/apwt-vm-startup-20261104-001/INFRASTRUCTURE-GATE.json'
    require(read(infra)['status']=='passed','Previously verified pinned infrastructure required')
    root.mkdir();(root/'code').mkdir();(root/'requests').mkdir();(root/'runs').mkdir()
    for name in set(old['code'])|{'tensor_workspace_vm_startup.py','tensor_workspace_recovery_standalone.py'}:
        shutil.copyfile(project/('controller' if name=='windows_job.py' else 'evaluations')/name,root/'code'/name)
    atomic(root/'inputs.json',{'cases':[case]});atomic(root/'hidden-golds.json',{});atomic(root/'tensor-catalog.json',{})
    atomic(root/'protocol.json',{'system_brief':brief,'initial_task':case['task'],'perturbation_notice':NOTICE,
        'seed_sequence':[2026110451+n for n in range(4)],'thinking_enabled':True,'feedback_reply':'JSON of the actual VM cell outcome',
        'stop_on_any_model_error_or_truncation':True,'no_human_prompt_changes':True})
    atomic(root/'AUTHORIZATION.json',{'explicit_user_authorization':False,'user_instruction':AUTHORIZATION,
        'source_thread_id':'REDACTED-PRIVATE-THREAD',
        'scope':'Critic-reviewed, Proteus-approved standalone previously unrun recovery; unchanged 4B thinking-enabled, four turns, no retries, prompt changes, weight patches or pilot',
        'sampled_tokens':LIMIT,'seconds':SECONDS,'cannot_change_prior_failed_gate':True})
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','models','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol')}
    plan.update(scope='Standalone established Boolean-feedback recovery; no prior-gate or pilot credit',overnight=True,numeric_policy='precise-v2',
        code={p.name:sha(p) for p in (root/'code').iterdir()},controller_files={str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')},
        data={n:sha(root/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json','protocol.json','AUTHORIZATION.json')},
        limits={'total_seconds':SECONDS,'sampled_tokens':LIMIT,'editor_calls':4,'cell_seconds':60},
        design={'vm_preflight_receipt':str(infra),'vm_preflight_sha256':sha(infra),'editor_output_tokens':8192,'target_output_tokens':8192,
            'editor_sampling':{'temperature':.6,'top_p':.95,'top_k':20,'thinking':True},'vm_bridge_seconds':15,'vm_readiness_seconds':60,
            'only_model':'unchanged','no_retries':True,'no_pilot':True,'standalone_only':True,
            'acceptance':'Both initial IDs measured true plus matching checkpoint before harness perturbation; both exact perturbed IDs measured false; checkpoint restored after those tests; both IDs freshly measured true after restore, then submit; no runtime error or unrequested numeric writes',
            'prior_gate_unchanged':True},
        predecessor_unrun={'root':str(previous),'files':{n:sha(previous/n) for n in ('recovery-input.json','briefs.json','POST-RUN-AUDIT.json','BUDGET.json','fresh-recovery/RESULT.json')}})
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\np=json.loads((r/'manifest.json').read_text())\nsys.path.insert(0,p['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_recovery_standalone import run\nrun(r)\n",encoding='utf8')
    return {'root':str(root),'plan_identity':identity(plan),'turns':4,'token_ceiling':LIMIT,'seconds':SECONDS}


def run(root):
    from tokenizers import Tokenizer
    root=Path(root).resolve();plan=read(root/'manifest.json');began=time.monotonic()
    with desktop_lease(plan['project']),exclusive(root):
        require(not (root/'runner.json').exists() and not (root/'RESULT.json').exists(),'No retry or implicit replay')
        result={'status':'starting','model_score':None,'model_turns_started':0,'model_turns_completed':0,'pilot_run':False,
            'standalone_only':True,'prior_failed_gate_unchanged':True};study=None;vm=None;p=None;tracker=None
        outcome={'error':'No completed model cell','output':''}
        try:
            admission(plan['project'],root/'admission');study=Study(root);study.deadline=Deadline(end=began+SECONDS);study.worker_deadline=study.deadline
            source=plan['predecessor_unrun'];check_files(source['root'],source['files'])
            case=read(root/'inputs.json')['cases'][0];protocol=read(root/'protocol.json')
            p,expected,requests,names,fixed=fixture(root/'workspace',case,recovery=True);tracker=RecoveryEvidence(p)
            initial_hashes={n:hashlib.sha256(p.array(n).tobytes()).hexdigest() for n in names}
            atomic(root/'INITIAL-CANDIDATE.json',{'fixture_only':True,'candidate':p.candidate_state(),'tensor_hashes':initial_hashes})
            try:vm=TensorVM(plan['project'],plan['image'],root/'workspace/vm.json',study.deadline,
                debug_console=root/'workspace/serial.log',bridge_seconds=15,readiness_seconds=60)
            except Exception as error:raise InfrastructureStop('Recovery VM startup: '+str(error)) from error
            tok=Tokenizer.from_file(str(Path(plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
            messages=[{'role':'user','content':protocol['initial_task']}]
            study.arm='unchanged';study.state['phase']='standalone_recovery';study.save()
            for turn in range(4):
                used=read(root/'usage.json')['charged_tokens'] if (root/'usage.json').exists() else 0
                require(used+8192<=LIMIT,'Recovery sampled-token ceiling')
                text='<|im_start|>system\n'+protocol['system_brief']+'<|im_end|>\n'+''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n' for m in messages)+'<|im_start|>assistant\n<think>\n'
                request={'id':'standalone-recovery-'+str(turn),'rendered_prompt':text,'input_ids':tok.encode(text,add_special_tokens=False).ids,
                    'rng_seed':protocol['seed_sequence'][turn]}
                result['model_turns_started']=turn+1;study.state.update(turn=turn);study.save()
                response=study.inference('editor',plan['models']['unchanged'],[request],remaining=8192)[0]
                result['model_turns_completed']=turn+1
                require(response['finish_reason']=='eos','Recovery response truncated; no code executed')
                code,final=code_cell(response['raw_text'],thinking_enabled=True)
                outcome=vm.execute(code,p,seconds=60)
                atomic(root/('turn-'+str(turn)+'.json'),{'code':code,'outcome':outcome,'candidate':p.status(),
                    'receipts':p.receipt_ledger,'ordered_events':tracker.events})
                messages.extend([{'role':'assistant','content':final},{'role':'user','content':json.dumps(outcome)}])
                if outcome['error'] or p.submitted:break
                if tracker.worse_id is None and tracker.ready_for_perturbation():
                    fixed(names[0],case['perturb_index'],case['perturb_value'],'harness-perturbation')
                    tracker.note_perturbation();atomic(root/'PERTURBATION.json',{'tensor':names[0],'index':case['perturb_index'],
                        'value':case['perturb_value'],'events':tracker.events,'candidate':p.status(),'authorship':'trusted harness'})
                    messages.append({'role':'user','content':protocol['perturbation_notice']})
            grade=tracker.grade(expected,requests,outcome);result.update(model_score=grade['correct'],score=grade,
                status='completed_passed' if grade['correct'] else 'completed_task_failed')
        except (ValueError,CellAllowanceExceeded) as error:
            result.update(status='model_incomplete' if result['model_turns_started'] else 'unrun_infrastructure',
                model_score=False if result['model_turns_started'] else None,error=type(error).__name__+': '+str(error))
        except BaseException as error:
            result.update(status='infrastructure_stopped' if result['model_turns_started'] else 'unrun_infrastructure',
                model_score=None,error=type(error).__name__+': '+str(error))
        finally:
            if vm:vm.close()
            measured=read(root/'usage.json') if (root/'usage.json').exists() else {'charged_tokens':0,'phases':{}}
            require(measured['charged_tokens']<=LIMIT,'Recovery aggregate token ceiling exceeded')
            result.update(charged_tokens=measured['charged_tokens'],uncertain_tokens_upper_bound=sum(r['uncertain_tokens_upper_bound'] for r in measured['phases'].values()),
                token_ceiling=LIMIT,wall_seconds=time.monotonic()-began,deadline_seconds=SECONDS)
            if p:
                atomic(root/'FINAL-CANDIDATE.json',{'fixture_only':True,'candidate':p.status(),'tensor_hashes':{
                    n:hashlib.sha256(p.array(n).tobytes()).hexdigest() for n in p.records},'ordered_events':tracker.events if tracker else [],
                    'receipts':p.receipt_ledger,'operations':p.operation_history})
                result['final_fixture_matches_initial']=all(p.array(n).tobytes()==expected[n] for n in expected)
            workers=[read(x) for x in (root/'runs').glob('*/CLOSED.json')]
            result['all_owned_workers_closed']=all(r.get('owned_worker_closed') for r in workers)
            result['owned_vm_closed']=read(root/'workspace/vm.json')['owned_vm_closed'] if (root/'workspace/vm.json').exists() else True
            result['serial']=bound_serial(root/'workspace/serial.log')
            result['unchanged_editor_sha256_after']=sha(plan['models']['unchanged']['path'])
            result['editor_unchanged']=result['unchanged_editor_sha256_after']==plan['models']['unchanged']['sha256']
            if study:study.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));study.save()
            atomic(root/'RESULT.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='run':run(sys.argv[2])
