"""Explicit continuation of an admission-stopped, deterministic guest prefix.

Replays only closed CPU cells inside a fresh diskless VM. Completed native
observations are reused. Every prompt, cell outcome and final numeric patch
must match before the first new model request. No new instruction is inserted.
"""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

from lora6k_state import atomic,read,sha,identity,exclusive
from weight_editor_runtime import Deadline,require,check_files
if __name__=='__main__' and len(sys.argv)>2:
    project=Path(sys.argv[2]) if sys.argv[1]=='prepare' else Path(read(Path(sys.argv[2])/'manifest.json')['project'])
    sys.path.insert(0,str(project.resolve()))
from tensor_workspace_study import Study,code_cell
from tensor_workspace_policy import TensorPolicy
from tensor_workspace_vm import TensorVM


def check_prompt(case,prompt,ids,turn):
    require(case['id']=='editor-'+str(turn) and case['rendered_prompt']==prompt and case['input_ids']==ids
            and case['rng_seed']==2026110310+turn,'Reconstructed editor context differs from original request')


def prepare(project,source,root,allow_league_client=False,share_league_game=False):
    project,source,root=map(lambda p:Path(p).resolve(),(project,source,root))
    require(not root.exists(),'Never overwrite a continuation')
    old=read(source/'manifest.json');require(identity(old)==(source/'manifest.sha256').read_text().strip(),'Source plan changed')
    check_files(source/'code',old['code']);check_files(source,old['data'])
    result=read(source/'RESULT.json')
    allowed_error=('Active GPU compute engine' in result.get('error','') or
        (allow_league_client and 'GPU compute/unknown owner detected: LeagueClientUxRender.exe' in result.get('error','')) or
        (share_league_game and any('GPU compute/unknown owner detected: '+name in result.get('error','') for name in
            ('League of Legends.exe','GameBar.exe','XboxGameBarWidgets.exe','GameBarFTServer.exe','GameBarPresenceWriter.exe'))))
    require(result['status']=='stopped' and allowed_error,'Only the explicitly coordinated admission stop is supported')
    require(read(source/'CLOSED-REPORT.json')['all_owned_native_workers_closed'],'Source workers remain active')
    arm=old['design']['arms'][0];require(old['design']['arms']==[arm] and read(source/arm/'vm.json')['owned_vm_closed'],'Source VM not closed')
    turns=sorted((source/arm).glob('turn-*.json'),key=lambda p:int(p.stem.split('-')[-1]))
    require([p.stem for p in turns]==['turn-'+str(i) for i in range(len(turns))],'Guest prefix is incomplete')
    require(len(turns) in (14,21,23),'Only the audited fourteen/twenty-one/twenty-three-cell prefixes are supported')
    for p in turns:
        code=read(p)['code']
        require(not re.search(r'\b(random|uuid|time)\b|\b(open|exec|eval)\s*\(|np\.save',code),'Nondeterministic/unreviewed replay prefix')
    events=[json.loads(line) for line in (source/arm/'policy/events.jsonl').read_text('utf8').splitlines()]
    own_events=[e for e in events if e['kind']=='forward']
    inherited=old.get('resume_prefix',{})
    requests=copy.deepcopy(inherited.get('editor_requests',[]));own_forward_requests=[];blocked=None
    for p in sorted((source/'requests').glob('*.json')):
        req=read(p)
        if req['study_context']['editor_arm']!=arm:continue
        run=source/'runs'/p.stem
        if req['mode']=='editor':
            turn=int(req['cases'][0]['id'].split('-')[-1])
            if turn<len(turns):
                require(read(run/'CLOSED.json')['status']=='completed','Prefix editor call not complete')
                requests.append({'turn':turn,'request':str(p),'response':str(run/(req['cases'][0]['id']+'.json'))})
            elif turn==len(turns):
                require(not (run/'RESULT.json').exists() and not (run/'usage.json').exists()
                        and read(run/'CLOSED.json')['owned_worker_closed'],'Blocked call actually started')
                blocked=str(p)
        elif req['mode'] in ('probe','generate'):
            require(read(run/'CLOSED.json')['status']=='completed','Prefix target inference not complete')
            own_forward_requests.append({'request':str(p),'run':str(run)})
    forward_events=[];forward_requests=[];new_iter=iter(own_forward_requests)
    for event in events:
        if event['kind']=='reused_closed_forward':
            receipt=event['result']['candidate']['receipt']
            forward_events.append({'kind':'forward','call':event['original_call'],'mode':receipt['mode'],
                'views':['edited'],'result':event['result']})
            forward_requests.append(event['source'])
        elif event['kind']=='forward':
            forward_events.append(event);forward_requests.append(next(new_iter))
    requests.sort(key=lambda r:r['turn'])
    require([r['turn'] for r in requests]==list(range(len(turns))) and len(forward_requests)==len(forward_events)
            ==read(source/arm/'FROZEN.json')['state']['forward_calls'] and blocked,'Missing complete prefix or blocked next request')
    # Bind every surviving source file. Deleted temporary GGUFs are represented
    # by their existing model-removal receipts and numerical patch manifests.
    files={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file() and p.name!='runner.lock'}
    root.mkdir();(root/'code').mkdir();(root/'requests').mkdir();(root/'runs').mkdir()
    for name in old['code']:shutil.copyfile(source/'code'/name,root/'code'/name)
    shutil.copyfile(project/'evaluations/tensor_workspace_resume.py',root/'code/tensor_workspace_resume.py')
    if share_league_game:shutil.copyfile(project/'evaluations/weight_editor_shared_gpu.py',root/'code/weight_editor_shared_gpu.py')
    for name in old['data']:shutil.copyfile(source/name,root/name)
    new=copy.deepcopy(old)
    if inherited:
        total_end=inherited['original_total_end_unix'];arm_end=inherited['conservative_original_arm_end_unix']
    else:
        outer=read(source.parent/'runner.json');total_end=outer['began_unix']+21600
        arm_end=read(source/'runner.json')['began_unix']+7200
    external={}
    for item in requests:
        for field in ('request','response'):external[item[field]]=sha(item[field])
    for item in forward_requests:
        external[item['request']]=sha(item['request']);run=Path(item['run']);req=read(item['request'])
        for name in ('RESULT.json','CLOSED.json','usage.json','tokens.jsonl','checked.json'):
            if (run/name).exists():external[str(run/name)]=sha(run/name)
        for case in req['cases']:
            for suffix in ('.json','.npz'):
                path=run/(case['id']+suffix)
                if path.exists():external[str(path)]=sha(path)
    new.update(scope='Explicit never-started-call continuation after isolated admission stop; exact deterministic VM prefix restoration',
        code={p.name:sha(p) for p in (root/'code').iterdir()},
        resume_prefix={'root':str(source),'files':files,'arm':arm,'turns':len(turns),'editor_requests':requests,
            'blocked_request':blocked,'forward_requests':forward_requests,'forward_events':forward_events,
            'external_closed_files':external,
            'original_total_end_unix':total_end,
            'conservative_original_arm_end_unix':arm_end,
            'no_extra_inference_calls_or_allowance':True,'no_prompt_additions':True,
            'reason':('User explicitly asked to continue with League client open; allow only its idle renderer as a WDDM desktop context. '
                'Actual game, active compute, unknown owners, RAM/VRAM/shared-memory and time rules remain enforced.' if allow_league_client else
                'Original guard stop preserved; three subsequent read-only samples found no active compute. One explicit continuation of unstarted work, same guards, no new candidates.')})
    if allow_league_client:
        new['approved_idle_renderer_names']=['LeagueClientUxRender.exe']
        new['owner_exception_authorization']='User asked to run tests while League client stays open; client-only desktop classification, not active gameplay or compute admission'
    if share_league_game:
        new.pop('approved_idle_renderer_names',None)
        new['gpu_sharing']={'approved_process_names':['League of Legends.exe','LeagueClientUxRender.exe'],
            'idle_overlay_process_names':['GameBar.exe','XboxGameBarWidgets.exe','GameBarFTServer.exe','GameBarPresenceWriter.exe'],
            'maximum_aggregate_known_desktop_compute_percent':5,
            'authorization':'User explicitly selected Run alongside; FPS drops and slower tests are OK',
            'memory_floors_unchanged':True,'unrelated_compute_owners_still_blocked':True,
            'idle_utilization_requirement_removed':True,'timing_comparable_to_idle_control':False}
        new['resume_prefix']['reason']='Explicit user-approved League shared-GPU continuation; same source/context/weights/allowances, memory floors and original deadlines. Preserve every prior admission stop.'
    atomic(root/'manifest.json',new);(root/'manifest.sha256').write_text(identity(new))
    atomic(root/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(new),'explicit_user_authorization':False})
    return {'root':str(root),'plan_sha256':identity(new),'closed_cells_reused':len(turns)}


class ResumedStudy(Study):
    def editor_arm(self,arm,initial):
        from tokenizers import Tokenizer
        resume=self.plan['resume_prefix'];source=Path(resume['root']);check_files(source,resume['files'])
        for path,digest in resume.get('external_closed_files',{}).items():require(sha(path)==digest,'External closed observation changed')
        folder=self.root/arm;folder.mkdir();(folder/'snapshots').mkdir();self.arm=arm
        self.worker_deadline=Deadline(end=min(self.deadline.end,time.monotonic()+resume['conservative_original_arm_end_unix']-time.time()))
        self.worker_deadline.remaining()
        state={'status':'restoring_closed_prefix','calls':0,'forward_calls':0,'sampled_tokens':0,'editor_tokens':0}
        self.state['arms'][arm]=state;self.state['phase']='restoring_guest_prefix';self.save()
        metadata={'architecture':'Qwen3.5 0.8B','active_layers':24,'hidden_size':1024,'ffn_size':3584,'attention':'Hybrid Gated DeltaNet / full attention; inspect tensor names/shapes',
            'target':'Original unmodified BF16 weights represented as F32 GGUF; saved edits are BF16-rounded','limits':self.plan['limits']}
        self.policy=TensorPolicy(self.plan['models']['original_target'],self.records,folder/'policy',metadata,forward=None)
        events=resume['forward_events'];pending=list(zip(events,resume['forward_requests']))
        for event,binding in pending:
            req=read(binding['request']);run=Path(binding['run'])
            if event['mode']=='probe':
                for obs in event['result']['candidate']['observations']:
                    path=run/(obs['id']+'.npz');require(path.is_file(),'Missing frozen observation')
                    require(sha(path)==read(run/(obs['id']+'.json'))['npz_sha256'],'Observation changed')
                    self.policy.observations[obs['npz_handle']]=path
        def cached_forward(request):
            require(pending,'Guest requested extra inference during replay')
            event,binding=pending.pop(0);req=read(binding['request']);receipt=event['result']['candidate']['receipt']
            require(request['view']=='edited' and request['mode']==event['mode']==req['mode'],'Replay view/mode mismatch')
            if req['mode']=='probe':
                require(request['texts']==[c['rendered_prompt'] for c in req['cases']] and request['ids'] is None,'Replay probe text mismatch')
                self.policy.inspected_revision=self.policy.revision
            else:
                require(request['ids']==[c['id'] for c in req['cases']] and request['texts'] is None,'Replay generation IDs mismatch')
                self.policy.tested_revision=self.policy.revision
                state['sampled_tokens']+=sum(r['generated_tokens'] for r in event['result']['candidate']['outcomes'])
            require(self.policy.candidate_state()['candidate_id']==receipt['candidate_id'] and self.policy.revision==receipt['evaluated_revision'],'Replay numerical candidate mismatch')
            state['forward_calls']+=1
            self.policy.event('reused_closed_forward',{'original_call':event['call'],'source':binding,'result':event['result']})
            return copy.deepcopy(event['result'])
        self.policy.forward=cached_forward
        visible=[{'id':c['id'],'problem':c['problem'],'answer':self.golds[c['id']]} for c in self.cases if c['split']=='dev']
        messages=[{'role':'user','content':json.dumps({'development':visible,'shared_initial_baseline':self.public(initial)},ensure_ascii=True)}]
        tokenizer=Tokenizer.from_file(str(Path(self.plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
        self.vm=None
        try:
            self.vm=TensorVM(self.project,self.plan['image'],folder/'vm.json',self.worker_deadline)
            for item in resume['editor_requests']:
                turn=item['turn'];req=read(item['request']);response=read(item['response'])
                prompt,ids=self.render(messages,tokenizer);check_prompt(req['cases'][0],prompt,ids,turn)
                code,final=code_cell(response['raw_text']);old=read(source/arm/('turn-'+str(turn)+'.json'))
                require(code==old['code'],'Source code differs from saved reply')
                outcome=self.vm.execute(code,self.policy,seconds=self.plan['limits']['cell_seconds'])
                require(outcome==old['outcome'],'Guest reconstruction differs at turn '+str(turn))
                messages.extend([{'role':'assistant','content':final},{'role':'user','content':json.dumps(outcome,ensure_ascii=True)}])
                atomic(folder/('turn-'+str(turn)+'.json'),{'code':code,'outcome':outcome,'reused_closed_prefix':True})
                self.policy.event('cell_source',{'turn':turn,'code':code,'reused_closed_prefix':True})
                state['calls']=turn+1;state['editor_tokens']+=response['generated_tokens'];self.save()
            require(not pending,'Not all closed observations were reused')
            frozen=read(source/arm/'FROZEN.json')
            actual={n:{k:v for k,v in e.items() if k!='path'} for n,e in self.policy.edits.items()}
            expected={n:{k:v for k,v in e.items() if k!='path'} for n,e in frozen['edits'].items()}
            require(actual==expected,'Reconstructed final numerical patch differs')
            for key in ('editor_tokens','forward_calls','sampled_tokens'):require(state[key]==frozen['state'][key],'Restored allowance differs: '+key)
            prompt,ids=self.render(messages,tokenizer);blocked=read(resume['blocked_request'])
            check_prompt(blocked['cases'][0],prompt,ids,resume['turns'])
            atomic(self.root/'RESTORE-VERIFIED.json',{'all_closed_prompts_equal':True,'all_closed_cell_outcomes_equal':True,
                'all_numeric_patches_equal':True,'next_blocked_prompt_equal':True,'closed_native_observations_reused':len(events),
                'new_inference_before_verification':0,'physical_prefix_generated_tokens_reused':state['editor_tokens']+state['sampled_tokens'],
                'remaining_turns':self.plan['limits']['editor_calls']-state['calls'],'remaining_forward_calls':self.plan['limits']['forward_calls']-state['forward_calls'],
                'arm_deadline_not_extended':True})
            state['status']='running';self.state['phase']=arm;self.policy.forward=self.forward;self.save()
            for turn in range(resume['turns'],self.plan['limits']['editor_calls']):
                self.worker_deadline.remaining();state['calls']=turn+1;prompt,ids=self.render(messages,tokenizer)
                require(state['editor_tokens']+8192<=self.plan['limits']['editor_tokens'],'Editor allowance exhausted')
                case={'id':'editor-'+str(turn),'rendered_prompt':prompt,'input_ids':ids,'rng_seed':2026110310+turn}
                response=self.inference('editor',self.plan['models'][arm],[case],remaining=min(8192,self.plan['limits']['editor_tokens']-state['editor_tokens']))[0]
                state['editor_tokens']+=response['generated_tokens']
                try:code,final=code_cell(response['raw_text'])
                except ValueError as error:
                    messages.extend([{'role':'assistant','content':response['raw_text'].rsplit('</think>',1)[-1][-8000:]},
                        {'role':'user','content':str(error)+'. No code executed. Return one complete Python cell.'}])
                    self.policy.event('format_rejected',{'turn':turn,'error':str(error)})
                else:
                    self.policy.event('cell_source',{'turn':turn,'code':code})
                    outcome=self.vm.execute(code,self.policy,seconds=self.plan['limits']['cell_seconds'])
                    messages.extend([{'role':'assistant','content':final},{'role':'user','content':json.dumps(outcome,ensure_ascii=True)}])
                    atomic(folder/('turn-'+str(turn)+'.json'),{'code':code,'outcome':outcome})
                self.save()
                if self.policy.submitted:break
            state.update(status='completed',submitted=self.policy.submitted,patch=self.policy.status())
        except (TimeoutError,ValueError) as error:
            state.update(status='bounded_stop',error=type(error).__name__+': '+str(error),patch=self.policy.status())
            # A failed reconstruction must never continue to independent checks.
            if not (self.root/'RESTORE-VERIFIED.json').exists():raise
        finally:
            if self.vm:self.vm.close();self.vm=None
            atomic(folder/'FROZEN.json',{'state':state,'edits':self.policy.edits,'base':self.policy.base});self.save()

    def run(self):
        result={'status':'running'}
        try:
            initial=self.baseline(self.plan['design']['shared_initial_baseline_ids'])
            self.editor_arm(self.plan['resume_prefix']['arm'],initial)
            checked=self.qualification();result={'status':'completed','independent':checked,'arms':self.state['arms']}
        except BaseException as error:
            result={'status':'stopped','error':type(error).__name__+': '+str(error),'arms':self.state['arms']}
        finally:
            if self.vm:self.vm.close();self.vm=None
            self.state.update(status=result['status'],phase='closed',ended_unix=time.time(),error=result.get('error'));self.save()
            atomic(self.root/'RESULT.json',result)
            from tensor_workspace_report import report
            report(self.root)


def main(root):
    root=Path(root).resolve();plan=read(root/'manifest.json');sys.path.insert(0,plan['project'])
    with exclusive(root):
        require(not (root/'runner.json').exists(),'Never restart a continuation implicitly')
        if plan.get('gpu_sharing'):
            require(plan['gpu_sharing']['approved_process_names']==['League of Legends.exe','LeagueClientUxRender.exe'],'Unapproved shared owner policy')
            import lora6k_supervisor as guards
            import weight_editor_owned as owned
            from weight_editor_shared_gpu import admission,classify_shared_owners
            original=guards.check_owners
            def observed_shared_owners(rows,names,compute):
                sample={'unix':time.time(),'rows':rows,'process_names':{str(pid):names.get(pid) for pid in
                    [int(r[0]) for r in rows if r and r[0].strip().isdigit()]},'active_compute':compute,'profile':plan['gpu_sharing']}
                atomic(root/'OWNERSHIP-LATEST.json',sample)
                try:return classify_shared_owners(rows,names,compute,original)
                except BaseException as error:
                    atomic(root/'OWNERSHIP-REJECTED.json',{**sample,'error':str(error)});raise
            guards.check_owners=observed_shared_owners;owned.admission=admission
        elif plan.get('approved_idle_renderer_names'):
            require(plan['approved_idle_renderer_names']==['LeagueClientUxRender.exe'],'Unapproved owner exception')
            import lora6k_supervisor as guards
            guards.DESKTOP_GPU_PROCESSES=guards.DESKTOP_GPU_PROCESSES|frozenset(n.lower() for n in plan['approved_idle_renderer_names'])
            original=guards.check_owners
            def observed_owners(rows,names,compute):
                sample={'unix':time.time(),'rows':rows,'process_names':{str(pid):names.get(pid) for pid in
                    [int(r[0]) for r in rows if r and r[0].strip().isdigit()]},'active_compute':compute,
                    'approved_idle_renderer_names':plan['approved_idle_renderer_names']}
                atomic(root/'OWNERSHIP-LATEST.json',sample)
                try:return original(rows,names,compute)
                except BaseException as error:
                    atomic(root/'OWNERSHIP-REJECTED.json',{**sample,'error':str(error)});raise
            guards.check_owners=observed_owners
        study=ResumedStudy(root)
        end=time.monotonic()+plan['resume_prefix']['original_total_end_unix']-time.time()
        study.deadline=Deadline(end=end);study.worker_deadline=study.deadline;study.run()


if __name__=='__main__':
    if sys.argv[1]=='prepare':print(prepare(*sys.argv[2:5],allow_league_client='--allow-league-client' in sys.argv[5:],share_league_game='--share-league-game' in sys.argv[5:]))
    elif sys.argv[1]=='run':main(sys.argv[2])
