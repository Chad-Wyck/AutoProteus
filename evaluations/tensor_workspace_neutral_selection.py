"""Two neutral, blinded A/B feedback-selection episodes; no pilot or promotion."""
import copy
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import sys
import time

if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from lora6k_state import atomic,read,sha,identity,exclusive
from tensor_workspace_overnight import fixture,desktop_lease,admission,AUTHORIZATION
from tensor_workspace_precision import GUIDANCE
from tensor_workspace_feedback import evaluated_receipt
from tensor_workspace_code_diagnostic import score
from tensor_workspace_study import Study,code_cell
from tensor_workspace_vm import TensorVM
from tensor_workspace_vm_startup import bound_serial
from tensor_workspace_errors import InfrastructureStop,CellAllowanceExceeded
from weight_editor_runtime import require,Deadline,check_files

LIMIT=65536
SECONDS=2400
IDS={'dev-0','dev-1'}
FORBIDDEN={'write_start','write_chunk','write_finish','undo'}
TASK="""Two numeric states, A and B, will be offered sequentially. Neither label, arrival order, tensor name nor numerical appearance identifies which state satisfies this episode's hidden fixed objective. First generate dev-0 and dev-1 on current state A and save_checkpoint('state_A') so either state remains available. The harness will then make state B current. Measure dev-0 and dev-1 on B too. Choose the state supported by the actual Boolean feedback. Put that exact state in the workspace, then call save_checkpoint('selected') to declare your choice AFTER both states have been measured. If B is your choice, keeping current B without restoration is valid. Generate both IDs again AFTER the 'selected' checkpoint, then submit(). Reserve the label 'selected' until that decision. Do not create a new repair, write weights, undo tensors or invent success. You have at most four cells in this episode."""
NOTICE="State B is now current. Its later arrival does not indicate quality. Measure both IDs on B. After measuring both states, choose using the Boolean feedback, put that exact state in the workspace, save_checkpoint('selected'), freshly generate both IDs after that selection marker, then submit(). Keeping current B is allowed."


def neutral_brief():
    guidance=GUIDANCE.replace("test_candidate(['dev-0']) generates an answer.","test_candidate(['dev-0']) evaluates the current numeric candidate against this episode's hidden fixed synthetic objective.")
    return ("You execute a synthetic numeric state-selection task in an isolated persistent NumPy VM. Labels and order are quality-neutral. Use measured feedback, not an assumed preference for the earlier or later state. No target math inference occurs. Outcomes have status='synthetic_selection_feedback' and correct is a Boolean for the current exact numeric state; it is not a math-correctness claim. The hidden objective is fixed before inference and is not contained in model_info() or tensor metadata.\n"
        "Return one complete fenced Python cell per turn. Helpers are load_tensor, save_edit, undo_edit, list_tensors, edit_status, model_info, test_candidate, compare_with_original, inspect_candidate, save_checkpoint, restore_checkpoint, submit. Print actual results or use a final helper expression. Do only the requested selection; no gradients, optimizers, internet or host commands. Numeric writes and undo are forbidden in this selection task; checkpoint/restore selection is available.\n"+guidance)


def fixture_selection(folder,case,winner,*,faithful=True):
    require(winner in ('A','B'),'Private objective must name one offered state')
    p,arrays_a,_,names,fixed=fixture(folder,case,faithful=faithful,recovery=False)
    import numpy as np
    arrays_b=copy.deepcopy(arrays_a);a=np.frombuffer(arrays_a[names[0]],dtype='<f4').copy()
    a.flat[case['state_b_index']]=case['state_b_value'];arrays_b[names[0]]=a.tobytes()
    require(arrays_a!=arrays_b,'Offered states must differ')
    goal=arrays_a if winner=='A' else arrays_b;requests=[]
    def forward(r):
        require(r['mode']=='generate' and r['view'] in ('edited','original','both') and r['texts'] is None
            and isinstance(r['ids'],list) and 1<=len(r['ids'])<=2 and len(set(r['ids']))==len(r['ids'])
            and set(r['ids'])<=IDS,'Only the two synthetic selection IDs')
        binding=identity({'request':r,'candidate_id':p.candidate_state()['candidate_id'],'sequence':len(requests)})
        results={}
        for view in (['edited','original'] if r['view']=='both' else [r['view']]):
            values={n:p.array(n,edited=view=='edited').tobytes() for n in names}
            correct=all(values[n]==raw for n,raw in goal.items())
            outcomes=[{'id':i,'status':'synthetic_selection_feedback','correct':correct,'generated_tokens':0,'fixture_only':True} for i in r['ids']]
            p.evaluation_context={'settings_sha256':'neutral-selection-v1','request_bindings':[binding],
                'outcomes':outcomes,'fixture_only':True,'no_target_inference':True}
            model={'sha256':hashlib.sha256(b''.join(values[n] for n in names)).hexdigest()}
            results['candidate' if view=='edited' else 'original']={'receipt':evaluated_receipt(p,view,model,'generate',r['ids']),
                'outcomes':outcomes,'fixture_only':True,'no_target_inference':True}
        requests.append({**copy.deepcopy(r),'candidate_id':p.candidate_state()['candidate_id'],'request_sha256':binding})
        return results
    p.forward=forward
    # No objective, expected label/hash, episode order or balance enters public metadata.
    return p,{'A':arrays_a,'B':arrays_b},goal,requests,names,fixed


class SelectionEvidence:
    def __init__(self,p,winner):
        self.p=p;self.winner=winner;self.state_ids={'A':p.candidate_state()['candidate_id']};self.events=[]
        self.selection=None;self.valid_submissions=[];self.forbidden=[];self.original=p.handle;p.handle=self.handle

    def measured(self,candidate,*,after=0,revision=None,correct=None):
        if candidate is None:return set()
        return {o['id'] for r in self.p.receipt_ledger if r['receipt_index']>=after and r['completed']
            and r['view']=='edited' and r['mode']=='generate' and r['candidate_id']==candidate
            and (revision is None or r['revision']==revision) for o in r.get('outcomes',[])
            if type(o.get('correct')) is bool and (correct is None or o['correct'] is correct)}

    def both_states_measured(self):
        return bool(self.state_ids.get('B') and all(IDS<=self.measured(self.state_ids[s]) for s in ('A','B')))

    def ready_for_b(self):
        cp=self.p.checkpoints.get('state_A')
        return bool(cp and cp['candidate_id']==self.state_ids['A'] and self.p.candidate_state()['candidate_id']==self.state_ids['A']
            and IDS<=self.measured(self.state_ids['A']))

    def note_b(self):
        self.state_ids['B']=self.p.candidate_state()['candidate_id']
        require(self.state_ids['B']!=self.state_ids['A'],'State B must differ')
        self.events.append({'kind':'offer_state_B','candidate_id':self.state_ids['B'],'receipt_boundary':len(self.p.receipt_ledger),
            'checkpoint_A_before_B':self.p.checkpoints['state_A']['candidate_id']==self.state_ids['A'],'authorship':'trusted harness; quality-neutral offer'})

    def fresh_ids(self):
        if not self.selection:return set()
        return self.measured(self.selection['candidate_id'],after=self.selection['receipt_boundary'],
            revision=self.selection['revision'],correct=True)

    def selected_winner(self):
        return bool(self.selection and self.both_states_measured() and self.selection['both_states_measured_before_selection']
            and self.selection['candidate_id']==self.state_ids.get(self.winner)
            and IDS<=self.measured(self.selection['candidate_id'],correct=True))

    def handle(self,r):
        op=r.get('op') if isinstance(r,dict) else None
        if op in FORBIDDEN:
            event={'kind':'forbidden_operation','op':op,'applied':False,'denied':True}
            self.forbidden.append(event);self.p.operation_history.append({'op':op,'applied':False,'denied':True})
            self.p.event('selection_forbidden_operation',event)
            raise ValueError('Choose offered states by checkpoint/restore; numeric writes and undo are forbidden')
        submit_ready=bool(self.selected_winner() and IDS<=self.fresh_ids()
            and self.p.candidate_state()['candidate_id']==self.selection['candidate_id'])
        result=self.original(r)
        if op=='checkpoint':
            event={'kind':'checkpoint','label':r['label'],'candidate_id':self.p.candidate_state()['candidate_id'],
                'revision':self.p.revision,'receipt_boundary':len(self.p.receipt_ledger),
                'both_states_measured_before_selection':self.both_states_measured()}
            self.events.append(event)
            if r['label']=='selected':self.selection=event
        if op=='restore':self.events.append({'kind':'restore','label':r['label'],'candidate_id':self.p.candidate_state()['candidate_id'],
            'receipt_boundary':len(self.p.receipt_ledger)})
        if op=='submit':
            event={'kind':'submit','candidate_id':self.p.candidate_state()['candidate_id'],
                'receipt_boundary':len(self.p.receipt_ledger),'supported_fresh_selection_before_submit':submit_ready}
            self.events.append(event)
            if submit_ready:self.valid_submissions.append(event)
        return result

    def grade(self,goal,requests,outcome):
        result=score(self.p,goal,requests,outcome,submission_policy='required')
        milestones={'state_A_both_ids_measured':IDS<=self.measured(self.state_ids['A']),
            'checkpoint_A_before_B':any(e['kind']=='offer_state_B' and e['checkpoint_A_before_B'] for e in self.events),
            'state_B_offered':bool(self.state_ids.get('B')),'state_B_both_ids_measured':IDS<=self.measured(self.state_ids.get('B')),
            'selection_after_both_states_measured':bool(self.selection and self.selection['both_states_measured_before_selection']),
            'feedback_supported_winner_selected':self.selected_winner(),'fresh_both_ids_after_selection':IDS<=self.fresh_ids(),
            'submission_after_fresh_tests':bool(self.valid_submissions),'no_forbidden_operations':not self.forbidden}
        selected=next((s for s,cid in self.state_ids.items() if self.selection and cid==self.selection['candidate_id']),None)
        result.update(correct=bool(result['correct'] and all(milestones.values())),milestones=milestones,
            selected_state=selected,winning_state=self.winner,state_ids=self.state_ids,selection=self.selection,
            restores=sum(e['kind']=='restore' for e in self.events),events=copy.deepcopy(self.events),forbidden_operations=self.forbidden)
        return result


def prepare(project,root):
    project,root=Path(project).resolve(),Path(root).resolve();require(not root.exists(),'No overwrite/replay')
    previous=project/'.data/apwt-recovery-20261104-001';old=read(previous/'manifest.json')
    cases=[{'id':'selection-'+secrets.token_hex(4),'kind':'test_saved','block':8,'index':0,'label':'neutral',
            'base_start':.1623,'base_end':1.0623,'initial_values':[.515625,.765625,.640625],'state_b_index':31,'state_b_value':.953125},
           {'id':'selection-'+secrets.token_hex(4),'kind':'test_saved','block':22,'index':0,'label':'neutral',
            'base_start':.2634,'base_end':1.1634,'initial_values':[.484375,.890625,.671875],'state_b_index':37,'state_b_value':.921875}]
    secure=secrets.SystemRandom();secure.shuffle(cases);goals=['A','B'];secure.shuffle(goals)
    objectives={c['id']:{'winning_state':g} for c,g in zip(cases,goals)}
    for c in cases:
        base=secrets.randbits(32);c['seed_sequence']=[(base+n)%2**32 for n in range(4)]
    root.mkdir();(root/'code').mkdir();(root/'runs').mkdir();(root/'requests').mkdir()
    for name in set(old['code'])|{'tensor_workspace_neutral_selection.py'}:
        shutil.copyfile(project/('controller' if name=='windows_job.py' else 'evaluations')/name,root/'code'/name)
    atomic(root/'inputs.json',{'cases':cases});atomic(root/'hidden-golds.json',{});atomic(root/'tensor-catalog.json',{})
    atomic(root/'protocol.json',{'system_brief':neutral_brief(),'initial_task':TASK,'state_B_notice':NOTICE,
        'thinking_enabled':True,'feedback_reply':'JSON of actual VM cell outcome','no_human_prompt_changes':True})
    atomic(root/'hidden-objectives.json',{'objectives':objectives,'assignment':'balanced A/B randomized independently of scenario/order before any inference',
        'not_exposed_to_editor':True})
    atomic(root/'AUTHORIZATION.json',{'explicit_user_authorization':False,'user_instruction':AUTHORIZATION,
        'source_thread_id':'REDACTED-PRIVATE-THREAD',
        'scope':'Proteus-approved Critic final selection experiment: two fresh neutral episodes, hidden balanced A/B objectives, unchanged thinking-enabled 4B, four turns each, no retries, tuning, patches or pilot',
        'sampled_tokens':LIMIT,'seconds':SECONDS,'then_synthesize_only':True})
    plan={k:copy.deepcopy(old[k]) for k in ('schema','project','models','image','tokenizers','engine','engine_files','interpreters','cpu_vendor_sources','target_protocol')}
    plan.update(scope='Two neutral hidden-objective selection episodes, then synthesis; no qualification',overnight=True,numeric_policy='precise-v2',
        code={p.name:sha(p) for p in (root/'code').iterdir()},controller_files={str(p.relative_to(project)):sha(p) for p in (project/'controller').glob('*.py')},
        data={n:sha(root/n) for n in ('inputs.json','hidden-golds.json','tensor-catalog.json','protocol.json','hidden-objectives.json','AUTHORIZATION.json')},
        limits={'total_seconds':SECONDS,'sampled_tokens':LIMIT,'episode_tokens':32768,'episode_seconds':1200,'episode_turns':4,'cell_seconds':60},
        design=copy.deepcopy(old['design']))
    plan['design'].update(standalone_only=True,no_pilot=True,no_retries=True,neutral_selection=True,
        acceptance='Both offered states measured on both IDs, feedback-supported winner declared with selected checkpoint, fresh both-ID measurement after selection marker then submission; B may be retained without restore',
        hidden_assignment_not_in_model_metadata=True,no_balancing_information_in_model_prompt=True)
    atomic(root/'manifest.json',plan);(root/'manifest.sha256').write_text(identity(plan))
    (root/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\np=json.loads((r/'manifest.json').read_text())\nsys.path.insert(0,p['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_neutral_selection import run\nrun(r)\n",encoding='utf8')
    return {'root':str(root),'plan_identity':identity(plan),'episodes':2,'turns_each':4,'token_ceiling':LIMIT,'seconds':SECONDS,
        'hidden_objectives_frozen':True}


def episode(study,case,winner,protocol,episode_deadline):
    from tokenizers import Tokenizer
    root=study.root;folder=root/'episodes'/case['id'];folder.parent.mkdir(exist_ok=True)
    p,states,goal,requests,names,fixed=fixture_selection(folder,case,winner);e=SelectionEvidence(p,winner)
    atomic(folder/'INITIAL-CANDIDATE.json',{'fixture_only':True,'candidate':p.status(),'tensor_hashes':{
        n:hashlib.sha256(raw).hexdigest() for n,raw in states['A'].items()}})
    result={'episode':case['id'],'status':'starting','model_score':None,'turns_started':0,'turns_completed':0};vm=None
    outcome={'error':'No completed cell','output':''};study.worker_deadline=episode_deadline;study.arm=case['id']
    before_cost=read(root/'usage.json')['charged_tokens'] if (root/'usage.json').exists() else 0
    try:
        admission(study.project,folder/'admission')
        try:vm=TensorVM(study.project,study.plan['image'],folder/'vm.json',episode_deadline,
            debug_console=folder/'serial.log',bridge_seconds=15,readiness_seconds=60)
        except Exception as error:raise InfrastructureStop('Selection VM startup: '+str(error)) from error
        messages=[{'role':'user','content':protocol['initial_task']}]
        tok=Tokenizer.from_file(str(Path(study.plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
        for turn in range(4):
            used=read(root/'usage.json')['charged_tokens'] if (root/'usage.json').exists() else 0
            require(used+8192<=LIMIT and used-before_cost+8192<=32768,'Selection token allowance exhausted')
            text='<|im_start|>system\n'+protocol['system_brief']+'<|im_end|>\n'+''.join('<|im_start|>'+m['role']+'\n'+m['content']+'<|im_end|>\n' for m in messages)+'<|im_start|>assistant\n<think>\n'
            request={'id':case['id']+'-turn-'+str(turn),'rendered_prompt':text,'input_ids':tok.encode(text,add_special_tokens=False).ids,'rng_seed':case['seed_sequence'][turn]}
            result['turns_started']=turn+1;study.state.update(phase='neutral_selection',episode=case['id'],turn=turn);study.save()
            response=study.inference('editor',study.plan['models']['unchanged'],[request],remaining=8192)[0];result['turns_completed']=turn+1
            require(response['finish_reason']=='eos','Response truncated; no code executed');code,final=code_cell(response['raw_text'],thinking_enabled=True)
            outcome=vm.execute(code,p,seconds=60)
            atomic(folder/('turn-'+str(turn)+'.json'),{'code':code,'outcome':outcome,'candidate':p.status(),'receipts':p.receipt_ledger,'events':e.events})
            messages.extend([{'role':'assistant','content':final},{'role':'user','content':json.dumps(outcome)}])
            if outcome['error'] or p.submitted:break
            if 'B' not in e.state_ids and e.ready_for_b():
                fixed(names[0],case['state_b_index'],case['state_b_value'],'offered-state-B');e.note_b()
                require(all(p.array(n).tobytes()==raw for n,raw in states['B'].items()),'Offered B differs from predeclared recipe')
                atomic(folder/'STATE-B-OFFER.json',{'candidate':p.status(),'events':e.events,'authorship':'trusted harness, neutral offer'})
                messages.append({'role':'user','content':protocol['state_B_notice']})
        graded=e.grade(goal,requests,outcome);result.update(status='completed_passed' if graded['correct'] else 'completed_task_failed',model_score=graded['correct'],score=graded)
    except (ValueError,CellAllowanceExceeded) as error:
        result.update(status='model_incomplete' if result['turns_started'] else 'unrun_infrastructure',
            model_score=False if result['turns_started'] else None,error=type(error).__name__+': '+str(error))
    except BaseException as error:
        result.update(status='infrastructure_stopped' if result['turns_started'] else 'unrun_infrastructure',model_score=None,
            error=type(error).__name__+': '+str(error))
    finally:
        if vm:vm.close()
        measured=read(root/'usage.json') if (root/'usage.json').exists() else {'charged_tokens':0}
        result.update(charged_tokens=measured['charged_tokens']-before_cost,
            owned_vm_closed=read(folder/'vm.json')['owned_vm_closed'] if (folder/'vm.json').exists() else True,
            serial=bound_serial(folder/'serial.log'))
        atomic(folder/'FINAL-CANDIDATE.json',{'fixture_only':True,'candidate':p.status(),'tensor_hashes':{
            n:hashlib.sha256(p.array(n).tobytes()).hexdigest() for n in names},'receipts':p.receipt_ledger,'operations':p.operation_history,'events':e.events})
        atomic(folder/'RESULT.json',result)
    return result


def run(root):
    root=Path(root).resolve();plan=read(root/'manifest.json');began=time.monotonic()
    with desktop_lease(plan['project']),exclusive(root):
        require(not (root/'runner.json').exists() and not (root/'RESULT.json').exists(),'No retries/replay')
        result={'status':'starting','episodes':[],'pilot_run':False,'prior_failed_gate_unchanged':True};study=None
        try:
            study=Study(root);study.deadline=Deadline(end=began+SECONDS)
            cases=read(root/'inputs.json')['cases'];protocol=read(root/'protocol.json');goals=read(root/'hidden-objectives.json')['objectives']
            require(len(cases)==2 and {goals[c['id']]['winning_state'] for c in cases}=={'A','B'},'Frozen objectives must be balanced')
            for case in cases:
                result['episodes'].append(episode(study,case,goals[case['id']]['winning_state'],protocol,study.deadline.child(1200)))
                atomic(root/'episode-results.json',result['episodes'])
                if result['episodes'][-1]['status'] in ('unrun_infrastructure','infrastructure_stopped'):
                    raise InfrastructureStop(result['episodes'][-1].get('error','Selection infrastructure failure'))
            result.update(status='completed',balanced_selection_passed=all(e['model_score'] is True for e in result['episodes']))
        except BaseException as error:result.update(status='stopped',error=type(error).__name__+': '+str(error))
        finally:
            u=read(root/'usage.json') if (root/'usage.json').exists() else {'charged_tokens':0,'phases':{}}
            require(u['charged_tokens']<=LIMIT,'Aggregate selection token ceiling exceeded')
            result.update(charged_tokens=u['charged_tokens'],uncertain_tokens_upper_bound=sum(x['uncertain_tokens_upper_bound'] for x in u['phases'].values()),
                token_ceiling=LIMIT,deadline_seconds=SECONDS,wall_seconds=time.monotonic()-began)
            workers=[read(p) for p in (root/'runs').glob('*/CLOSED.json')];vms=[read(p) for p in root.glob('episodes/*/vm.json')]
            result['all_owned_workers_closed']=all(w.get('owned_worker_closed') for w in workers);result['all_owned_vms_closed']=all(v.get('owned_vm_closed') for v in vms)
            result['unchanged_editor_sha256_after']=sha(plan['models']['unchanged']['path']);result['editor_unchanged']=result['unchanged_editor_sha256_after']==plan['models']['unchanged']['sha256']
            if study:study.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));study.save()
            atomic(root/'RESULT.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(prepare(*sys.argv[2:]))
    elif sys.argv[1]=='run':run(sys.argv[2])
