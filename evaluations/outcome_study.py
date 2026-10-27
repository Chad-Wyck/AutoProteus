"""Outcome/choice observations, separate from named-feature upgrade qualification."""
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

from controller.config import DEFAULTS
from controller.evaluation import candidate_source, freeze_source, run_regressions, run_task, source_identity, tool_use
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store, atomic_json
from controller.submissions import submission_policy
from observations import CallRecorder, read_events
from outcome_tasks import grade_outputs, oracle_controls
from repeatability import repeat_config
from run_budget import BudgetModelClient, GeneratedTokenBudget
from study_support import identity


CATALOG_SCRIPT='''import json,re,sys
sys.path.insert(0,'harness')
from autoproteus.providers import tool_definitions
tools=tool_definitions(True);names=[];valid=True
for item in tools:
 f=item.get('function',{});name=f.get('name','');p=f.get('parameters',{})
 valid=valid and isinstance(name,str) and bool(re.fullmatch('[A-Za-z0-9_-]{1,64}',name)) and name not in names
 valid=valid and p.get('type')=='object' and isinstance(p.get('properties'),dict) and isinstance(p.get('required',[]),list)
 if isinstance(p.get('properties'),dict) and isinstance(p.get('required',[]),list):
  valid=valid and all(isinstance(k,str) and k in p['properties'] for k in p.get('required',[]))
  valid=valid and all(isinstance(v,dict) for v in p['properties'].values())
 names.append(name)
print(json.dumps({'check':'outcome package catalog','passed':bool(valid),'names':names}))
'''


class Scripted:
    def __init__(self,actions):self.actions=iter(actions)
    def complete(self,messages,cancel):return {'content':json.dumps(next(self.actions))}


def package_check(store,source,base_names,deadline):
    """Regression/suite/catalog checks; arbitrary feature semantics unmeasured."""
    frozen=freeze_source(store,source,'Frozen optional outcome extension')
    regressions=run_regressions(Path(__file__).resolve().parents[1],store,frozen,deadline=deadline)
    result={'passed':False,'regressions':regressions,'feature_semantics':'unmeasured'}
    if not regressions['passed'] or time.monotonic()>=deadline:return result
    settings=SimpleNamespace(values={**DEFAULTS,'configured':True,'provider':'demo','terminal':True,'action_limit':True},key=lambda:'')
    client=Scripted([{'action':{'tool':'run_command','arguments':{'command':'python3 harness/seed.py check'}}},
        {'action':{'tool':'run_command','arguments':{'command':'python3 development/package-inspect.py'}}}, {'status':'completed'}])
    root=Path(__file__).resolve().parents[1];agent=IsolatedAgent(root,store,settings,lambda _:client)
    try:
        task={'name':'outcome-package-check','task':'Scripted independent package inspection',
            'fixtures':{'development/package-inspect.py':CATALOG_SCRIPT},'checks':[]}
        run=run_task(agent,store,settings.values,task,frozen,max(0,deadline-time.monotonic()),deadline=deadline)
        session=store.get(run['session']);events=read_events(store.directory(session['id'])/'events.jsonl')
        suite=catalog=None
        for event in events:
            data=event.get('data',{});action=data.get('action',{});output=data.get('result',{})
            if event.get('type')!='action_result' or not data.get('ok') or action.get('tool')!='run_command' or output.get('exit_code')!=0:continue
            for line in output.get('output','').splitlines():
                try:value=json.loads(line)
                except ValueError:continue
                if not isinstance(value,dict):continue
                if value.get('check')=='candidate tests' and value.get('scope')=='full':suite=value
                if value.get('check')=='outcome package catalog':catalog=value
        result.update(run=run,suite=suite,catalog=catalog,
            passed=bool(run['passed'] and suite and suite.get('passed') is True and catalog and catalog.get('passed') is True
                and set(base_names).issubset(catalog['names']) and time.monotonic()<deadline))
        return result
    finally:agent.close()


def phase(folder,task,source,config,plan,base_names,client_factory=None):
    import model_study as ms
    from generalization import wait
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    store=Store(folder/'sessions');settings=SimpleNamespace(values=dict(config),key=lambda:'')
    budget=GeneratedTokenBudget(plan['generated_tokens']);recorder=CallRecorder(folder/'provider-calls.jsonl');clients=[]
    def factory(values):
        if client_factory:return client_factory(values)
        client=BudgetModelClient(values,token_budget=budget,observer=recorder);clients.append(client);return client
    root=Path(__file__).resolve().parents[1];agent=IsolatedAgent(root,store,settings,factory)
    if agent.execution.mode!='vm':raise ValueError('Outcome studies require disposable VMs')
    start=time.monotonic();deadline=start+plan['deadline'];active=source;names=set(base_names)
    row={'task':task['name'],'requested_sampling_seed':config.get('sampling_seed'),'packages':[],
        'activations':0,'scripted':client_factory is not None,'feature_semantics':'unmeasured'}
    atomic_json(folder/'task.json',task)
    try:
        public={**task,'checks':[]}  # The expected answers never enter the model prompt.
        run=run_task(agent,store,config,public,freeze_source(store,source,'Outcome input seed'),
            max(0,deadline-time.monotonic()),deadline=deadline)
        session=store.get(run['session'])
        while True:
            try:candidate=candidate_source(store,session)
            except ValueError as error:
                row['invalid_candidate']=str(error)[:500]
                break
            policy=submission_policy(active,candidate)
            if not policy['changed_files']:break
            entry={'policy':policy,'passed':False};row['packages'].append(entry)
            if (run['status'] not in ('completed','waiting') or run['timed_out'] or time.monotonic()>=deadline
                    or not policy['allowed_files_only'] or not policy['protected_unchanged']
                    or (policy['runtime_changed'] and not policy['new_test_files'])):break
            checked=package_check(store,candidate,names,deadline);entry['checks']=checked;entry['passed']=checked['passed']
            if not checked['passed']:break
            active=candidate;names=set(checked['catalog']['names'])
            if session['status']=='completed':break
            remaining=config['max_steps']-session['steps']
            if remaining<=0 or budget.summary()['exhausted'] or time.monotonic()>=deadline:break
            settings.values={**config,'max_steps':remaining}
            agent.restart_seed(session,handoff='concise',deadline=deadline);row['activations']+=1
            run=wait(agent,session,max(0,deadline-time.monotonic()))
        artifacts=grade_outputs(Artifacts(store,session),task)
        elapsed=time.monotonic()-start
        in_budget=(session['steps']<=config['max_steps'] and budget.summary()['charged_output_tokens']<=plan['generated_tokens'])
        row.update(run=run,artifacts=artifacts,actions=session['steps'],within_budget=in_budget,
            task_outcome_passed=bool(artifacts['passed'] and session['status']=='completed' and not run['timed_out']
                and elapsed<plan['deadline'] and in_budget),
            seed_edit_attempted=bool(row['packages'] or row.get('invalid_candidate')),checked_packages=sum(p['passed'] for p in row['packages']),
            temporary_python_helpers=sorted(n for n in session.get('artifacts',{}) if n.endswith('.py') and not n.startswith('harness/')),
            usage=tool_use(read_events(store.directory(session['id'])/'events.jsonl')),
            continuation_source_sha256=source_identity(active),continuation_tools=sorted(names),
            wall_budget={'allowance_seconds':plan['deadline'],'work_seconds':round(elapsed,3),'deadline_reached':elapsed>=plan['deadline']})
        atomic_json(folder/'continuation-source.json',active)
    finally:
        agent.close()
        row.update(token_budget=budget.summary(),total_seconds=round(time.monotonic()-start,3),**ms.metrics(folder,recorder,clients))
        atomic_json(folder/'result.json',row)
    return row


def calibrate(plan,output):
    controls=oracle_controls(plan['outcome_cases'])
    store=Store(output/'outcome-calibration/sessions')
    result=package_check(store,plan['source'],plan['base_tool_names'],time.monotonic()+180)
    atomic_json(output/'outcome-calibration.json',{'artifact_oracles':controls,'starter_package':result,
        'scope':'Scripted oracles, baseline suite and catalog only. No model inference or arbitrary feature acceptance.'})
    if not result['passed']:raise ValueError('Outcome starter package calibration failed')


def run_plan(plan,output,queue,args):
    import model_study as ms
    from controller.compatibility import model_identity
    rows=[]
    for profile in plan['profiles']:
        config=profile['config'];known=model_identity(config)
        marker=output/(profile['id']+'-identity.json')
        if marker.exists() and json.loads(marker.read_text())!=known:raise ValueError('Inference service identity changed; prepare a fresh plan')
        atomic_json(marker,known)
        def cell(suffix,execute):
            ms.check(plan)
            if model_identity(config)!=known:raise ValueError('Inference service identity changed')
            name=profile['id']+'_'+suffix
            def checked(folder):
                value=execute(folder);ms.check(plan)
                if model_identity(config)!=known:raise ValueError('Inference service identity changed')
                return value
            record=queue.run(name,checked,retry=name in args.retry)
            print('CELL',name,record['state'],flush=True)
            return record
        speed=cell('benchmark_01',lambda folder:ms.benchmark(folder,config,plan))
        for repeat in range(1,plan['repeats']+1):
            seeded=repeat_config(plan,config,repeat)
            for case in plan['outcome_cases']:
                suffix=f'outcome_{repeat:02d}_{case["name"]}'
                reuse_suffix=f'reuse_{repeat:02d}_{case["name"]}'
                if not speed.get('result',{}).get('passed'):
                    queue.skip(profile['id']+'_'+suffix,'Inference screen did not qualify')
                    queue.skip(profile['id']+'_'+reuse_suffix,'Inference screen did not qualify');continue
                first=cell(suffix,lambda folder:phase(folder,case['first'],plan['source'],seeded,plan,plan['base_tool_names']))
                if first['state']!='completed':
                    queue.skip(profile['id']+'_'+reuse_suffix,'No completed first attempt to observe');continue
                original=first['result'];source_path=Path(first['folder'])/'continuation-source.json'
                source=json.loads(source_path.read_text(encoding='utf-8'))
                if source_identity(source)!=original['continuation_source_sha256']:raise ValueError('Continuation source changed')
                later=cell(reuse_suffix,lambda folder:phase(folder,case['reuse'],source,seeded,plan,original['continuation_tools']))
                added=set(original['continuation_tools'])-set(plan['base_tool_names'])
                usage=later.get('result',{}).get('usage',{})
                observed=added & (set(usage.get('direct',[]))|set(usage.get('development',[])))
                rows.append({'profile':profile['id'],'repeat':repeat,'case':case['name'],'starter_solvable':case['starter_solvable'],
                    'case_kind':case['case_kind'],
                    'first_task_outcome_passed':original['task_outcome_passed'],
                    'later_task_outcome_passed':later.get('result',{}).get('task_outcome_passed',False),
                    'first_failure_kind':original.get('run',{}).get('failure_kind') or original.get('run',{}).get('provider_error_category'),
                    'later_failure_kind':later.get('result',{}).get('run',{}).get('failure_kind') or later.get('result',{}).get('run',{}).get('provider_error_category'),
                    'seed_edit_attempted':original['seed_edit_attempted'],'checked_packages':original['checked_packages'],
                    'new_registered_tools':sorted(added),'later_use_observed':sorted(observed),
                    'fresh_session_reuse':True,'feature_semantics':'unmeasured'})
                atomic_json(output/'outcome-results.json',rows)
    def coverage(stage):
        records=[queue.latest(profile['id']+f'_{stage}_{repeat:02d}_'+case['name'])
            for profile in plan['profiles'] for repeat in range(1,plan['repeats']+1) for case in plan['outcome_cases']]
        measured=[r['result'] for r in records if r and r['state']=='completed' and 'task_outcome_passed' in r.get('result',{})]
        return {'scheduled':len(records),'launched':sum(bool(r and r.get('attempt',0)>0) for r in records),
            'recorded_outcomes':len(measured),'passed':sum(r['task_outcome_passed'] is True for r in measured) if measured else None}
    first_coverage,later_coverage=coverage('outcome'),coverage('reuse')
    summary={'mode':'outcomes','protocol':plan.get('protocol','outcome-choice-v1'),'scope':plan['scope'],'queue':queue.summary(),'cases':rows,
        'first_task_outcomes':first_coverage,'later_task_outcomes':later_coverage,
        'first_task_passes':first_coverage['passed'],
        'later_task_passes':later_coverage['passed'],
        'source_extensions_chosen':sum(r['seed_edit_attempted'] for r in rows),
        'extension_use_observed':sum(bool(r['later_use_observed']) for r in rows),
        'scheduled_cases':len(plan['profiles'])*plan['repeats']*len(plan['outcome_cases']),
        'two_task_workflows_passed':sum(r['first_task_outcome_passed'] and r['later_task_outcome_passed'] for r in rows),
        'later_extension_use_with_correct_outcome':sum(bool(r['later_use_observed']) and r['later_task_outcome_passed'] for r in rows),
        'independent_feature_acceptance':'unmeasured',
        'extension_necessity':'unmeasured',
        'status':'needs_attention' if queue.summary()['unresolved_cells'] else 'completed'}
    atomic_json(output/'summary.json',summary);atomic_json(output/'queue-summary.json',queue.summary())
    return summary
