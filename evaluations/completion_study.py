"""Frozen, outcome-first final-use comparisons. Preparation starts no models."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'evaluations')]
from controller.evaluation import artifact_check, candidate_source, freeze_source, run_regressions, run_task, source_identity
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store, atomic_json, now
from controller.compatibility import model_identity
from model_plan import trusted_files, environment
from research_limits import research_config, resource_limits
from run_budget import BudgetModelClient, GeneratedTokenBudget
from observations import CallRecorder, call_metrics, read_events
from study_support import identity
from workflow_variants import variant


def tasks():
    passage = ('é猫0123456789\n'*110)
    return [
        {'name':'section-default-after-short-example', 'fixtures':{'sources/manual.txt':passage},
         'task':'First inspect sources/manual.txt using read_section with length 7 as a disposable preview. '
                'Then use the declared default section length for the same file and save that complete section to delivery/excerpt.txt. '
                'The earlier seven-character preview applies only to the first inspection. Preserve the source, inspect the saved output and finish.',
         'final_task':'Save the default read_section result for sources/manual.txt to delivery/excerpt.txt; use the current default length, '
                      'not the earlier preview override. Preserve the input and inspect the saved file before finishing.',
         'checks':[{'path':'delivery/excerpt.txt','equals':passage[:1000]}, {'path':'sources/manual.txt','equals':passage}],
         'call':{'tool':'read_section','match':{'path':'sources/manual.txt'},'optional':['length']},
         'control':{'delivery/excerpt.txt':passage[:1000]}, 'fault':{'delivery/excerpt.txt':passage[:7]}},
        {'name':'workspace-search-after-folder-example',
         'fixtures':{'regional/a.txt':'AP_COMPLETION_MARKER\n','regional/nested/b.txt':'AP_COMPLETION_MARKER\n','outside.txt':'AP_COMPLETION_MARKER\n'},
         'task':'First search regional/ for AP_COMPLETION_MARKER as a folder-specific example. '
                'For the final result search using the default workspace scope, and save a sorted JSON array of all matching file paths to delivery/matches.json. '
                'Do not retain the earlier regional/ scope. Preserve all inputs, inspect the saved JSON and finish.',
         'final_task':'Search AP_COMPLETION_MARKER across the default workspace scope. Save all matching paths, sorted, '
                      'to delivery/matches.json. The earlier folder-specific example is not the final scope. Preserve inputs and inspect the result.',
         'checks':[{'path':'delivery/matches.json','json':['outside.txt','regional/a.txt','regional/nested/b.txt']}],
         'call':{'tool':'search_files','match':{'query':'AP_COMPLETION_MARKER'},'optional':['path']},
         'control':{'delivery/matches.json':'["outside.txt","regional/a.txt","regional/nested/b.txt"]'},
         'fault':{'delivery/matches.json':'["regional/a.txt","regional/nested/b.txt"]'}},
        {'name':'root-listing-after-archive-example',
         'fixtures':{'alpha.txt':'one','βeta.txt':'two','archive/old.txt':'old','root.json':'{}'},
         'task':'First list archive/ as an example. Then list the default directory and save a Python-string-sorted JSON array '
                'of only the top-level .txt file names to delivery/names.json. The final directory is the default, not archive/. '
                'Preserve input files, inspect the saved JSON and finish.',
         'final_task':'List the default directory and save only its top-level .txt file names, Python-string-sorted, '
                      'to delivery/names.json. Ignore the earlier archive/ override. Preserve inputs and inspect the result.',
         'checks':[{'path':'delivery/names.json','json':['alpha.txt','βeta.txt']}],
         'call':{'tool':'list_files','match':{},'optional':['path']},
         'control':{'delivery/names.json':'["alpha.txt","βeta.txt"]'}, 'fault':{'delivery/names.json':'["old.txt"]'}}]


def private(value):
    path = (ROOT/value).resolve()
    if not path.is_relative_to(ROOT/'.data'): raise ValueError('Use a private .data output directory')
    return path


def prepare(args):
    output = private(args.output)
    if output.exists(): raise ValueError('Use a new directory; previous evidence is preserved')
    profile = json.loads(Path(args.profile).read_text(encoding='utf-8'))
    config = research_config({**profile['config'], 'configured':True, 'internet':False})
    if config.get('api_key'): raise ValueError('Keep provider keys in AUTOPROTEUS_API_KEY, not study plans')
    source = json.loads(Path(args.source).read_text()) if getattr(args,'source',None) else seed_files(ROOT)
    source_identity(source)
    if args.comparison not in ('final-contract','short-guidance') or not 1 <= args.repeats <= 10:
        raise ValueError('Choose one comparison and 1–10 repeats')
    sources = {'baseline':source, args.comparison:variant(source,args.comparison)}
    plan = {'created':now(), 'config':config, 'comparison':args.comparison, 'repeats':args.repeats,
            'starter_sha256':source_identity(seed_files(ROOT)), 'sources':sources,
            'source_hashes':{name:source_identity(value) for name,value in sources.items()},
            'trusted':trusted_files(), 'environment':environment(), 'tasks':tasks(), 'schedule':[], 'assets':profile.get('assets',{}),
            'resource_limits':resource_limits(config,args.timeout,args.output_token_budget),
            'scope':'Final-use requirement retention on controlled earlier overrides; no new upgrade or autonomous-growth credit. '
                    'Supplied sources are inert frozen bytes. No hidden answer feedback or automatic promotion.'}
    for repeat in range(1,args.repeats+1):
        for index,task in enumerate(plan['tasks']):
            arms = ('baseline',args.comparison) if (repeat+index)%2 else (args.comparison,'baseline')
            for arm in arms: plan['schedule'].append({'id':f'{repeat}-{task["name"]}-{arm}', 'repeat':repeat, 'task':task['name'], 'arm':arm})
    output.mkdir(parents=True)
    atomic_json(output/'plan.json',plan); (output/'plan.sha256').write_text(identity(plan))
    for name in plan['trusted']:
        target=output/'trusted-runner'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    command=f'"{ROOT / ".runtime/python/python.exe"}" -X utf8 "{Path(__file__).resolve()}" run --input "{output}"'
    (output/'Run comparison.cmd').write_text('@echo off\ncd /d "'+str(ROOT)+'"\n'+command+' --check-only\nif errorlevel 1 exit /b 1\n'+command+'\npause\n')
    print(f'Prepared {len(plan["schedule"])} attempts; no model calls started.')
    return plan


def validate(plan):
    if (plan['trusted'] != trusted_files() or plan['environment'] != environment()
            or plan['starter_sha256'] != source_identity(seed_files(ROOT))
            or any(source_identity(source) != plan['source_hashes'][name] for name,source in plan['sources'].items())):
        raise ValueError('Frozen source, runner or environment changed; prepare a new study')


def assess(store, session, task, run, source):
    files=Artifacts(store,session)
    artifacts = all(artifact_check(files,rule) for rule in task['checks'])
    try: preserved = all(files.read(path) == value.encode('utf-8') for path,value in task['fixtures'].items())
    except (OSError,ValueError): preserved=False
    events=read_events(store.directory(session['id'])/'events.jsonl')
    calls=[e['data']['action'] for e in events if e.get('type')=='action_result' and e.get('data',{}).get('ok')]
    contract=task['call']
    matching=[call for call in calls if call.get('tool')==contract['tool'] and all(call.get('arguments',{}).get(k)==v for k,v in contract['match'].items())]
    omitted=bool(matching and any(not set(contract['optional']) & set(call.get('arguments',{})) for call in matching))
    try: unchanged=source_identity(candidate_source(store,session))==source_identity(source)
    except (OSError,ValueError): unchanged=False
    return {'artifacts_correct':artifacts, 'inputs_preserved':preserved, 'source_unchanged':unchanged,
            'required_tool_observed':bool(matching), 'default_arguments_omitted':omitted,
            'completed':run.get('status')=='completed' and not run.get('timed_out'),
            'complete_workflow':bool(artifacts and preserved and unchanged and matching and run.get('status')=='completed' and not run.get('timed_out'))}


def run(args):
    output=private(args.input);plan=json.loads((output/'plan.json').read_text())
    if identity(plan)!=(output/'plan.sha256').read_text(): raise ValueError('Plan identity changed')
    validate(plan)
    if args.check_only:
        checks={}
        for name,source in plan['sources'].items():
            store=Store(output/'calibration'/name/'sessions')
            checks[name]=run_regressions(ROOT,store,freeze_source(store,source,'Frozen comparison input'))
        # Actual guest writes feed the same artifact oracle used in live trials.
        import generalization as study
        for task in plan['tasks']:
            for label,values,expected in (('positive',task['control'],True),('stale_override',task['fault'],False)):
                folder=output/'calibration'/task['name']/label;store=Store(folder/'sessions')
                actions=[{'action':{'tool':task['call']['tool'],'arguments':task['call']['match']}}]
                actions += [{'action':{'tool':'write_file','arguments':{'path':path,'content':text}}} for path,text in values.items()]+[{'status':'completed'}]
                settings=SimpleNamespace(values={**plan['config'],'provider':'demo'},key=lambda:'')
                agent=IsolatedAgent(ROOT,store,settings,lambda _:study.benchmark.ScriptedClient(actions))
                try:
                    row=run_task(agent,store,settings.values,{**task,'task':'Scripted grader calibration'},freeze_source(store,plan['sources']['baseline'],'Calibration source'),120)
                    verdict=assess(store,store.get(row['session']),task,row,plan['sources']['baseline'])
                    checks[task['name']+'/'+label]={'passed':verdict['complete_workflow'] is expected,'observed':verdict,'expected':expected}
                finally: agent.close()
        if not all(row.get('passed') for row in checks.values()):
            atomic_json(output/'calibration-failure.json',checks);raise ValueError('Completion grader calibration failed')
        atomic_json(output/'calibration.json',{'plan':identity(plan),'passed':True,'checks':checks})
        return
    receipt=json.loads((output/'calibration.json').read_text())
    if receipt.get('plan')!=identity(plan) or not receipt.get('passed'): raise ValueError('Calibrate the exact plan before live inference')
    from study_support import file_identity
    for path,digest in plan['assets'].items():
        if file_identity(path)!=digest: raise ValueError('Inference asset identity changed: '+path)
    results=json.loads((output/'results.json').read_text()) if (output/'results.json').exists() else {'trials':[],'interrupted_cells':[]}
    done={row['id'] for row in results['trials']} | {row['id'] for row in results['interrupted_cells']}
    for cell in plan['schedule']:
        if cell['id'] in done: continue
        validate(plan);folder=output/'trials'/cell['id']
        if folder.exists():
            results['interrupted_cells'].append({**cell,'reason':'Unfinished evidence directory retained; no automatic retry.'})
            atomic_json(output/'results.json',results);continue
        folder.mkdir(parents=True)
        task=copy.deepcopy(next(task for task in plan['tasks'] if task['name']==cell['task']))
        if cell['arm']=='final-contract': task['task']+='\nCURRENT FINAL TASK\n'+task['final_task']
        store=Store(folder/'sessions');budget=GeneratedTokenBudget(plan['resource_limits']['generated_tokens'])
        recorder=CallRecorder(folder/'provider-calls.jsonl');settings=SimpleNamespace(values=dict(plan['config']),key=lambda:__import__('os').environ.get('AUTOPROTEUS_API_KEY',''))
        clients=[]
        def client_factory(config):
            client=BudgetModelClient(config,settings.key(),token_budget=budget,observer=recorder)
            clients.append(client)
            return client
        agent=IsolatedAgent(ROOT,store,settings,client_factory)
        source=plan['sources'][cell['arm']];before=model_identity(settings.values)
        try:
            seconds=plan['resource_limits']['wall_seconds'];deadline=time.monotonic()+seconds
            trial=run_task(agent,store,settings.values,task,freeze_source(store,source,'Frozen comparison input'),seconds,deadline=deadline)
            verdict=assess(store,store.get(trial['session']),task,trial,source)
            row={**cell,'run':trial,'verdict':verdict,'tokens':budget.summary(),'calls':call_metrics(read_events(recorder.path)),
                 'capture':recorder.summary(),'identity_before':before,'identity_after':model_identity(settings.values)}
            row['capture']['observer_failed']=any(client.observation_failed for client in clients)
            if row['identity_after']!=before: row['infrastructure_error']='Inference identity changed';row['verdict']['complete_workflow']=False
            results['trials'].append(row);atomic_json(output/'results.json',results)
        except BaseException as error:
            results['interrupted_cells'].append({**cell,'reason':type(error).__name__,'detail':str(error)[:300]})
            atomic_json(output/'results.json',results)
            raise
        finally: agent.close()
    results['summary']={arm:{'attempts':sum(row['arm']==arm for row in results['trials']),
        'complete_workflows':sum(row['arm']==arm and row['verdict']['complete_workflow'] for row in results['trials'])} for arm in plan['sources']}
    results['scope']=plan['scope'];atomic_json(output/'results.json',results)
    matched=[]
    for repeat in range(1,plan['repeats']+1):
        for task in plan['tasks']:
            rows=[row for row in results['trials'] if row['repeat']==repeat and row['task']==task['name']]
            if len(rows)==2 and all(row['verdict']['complete_workflow'] for row in rows):
                matched.append({'repeat':repeat,'task':task['name'],'cells':[row['id'] for row in rows]})
    results['matched_successful_pairs']=matched
    results['scheduled']=len(plan['schedule']);atomic_json(output/'results.json',results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--profile',required=True);p.add_argument('--source');p.add_argument('--output',required=True)
    p.add_argument('--comparison',choices=['final-contract','short-guidance'],default='final-contract');p.add_argument('--repeats',type=int,default=1)
    p.add_argument('--timeout',type=int,default=3600);p.add_argument('--output-token-budget',type=int,default=65536)
    p=commands.add_parser('run');p.add_argument('--input',required=True);p.add_argument('--check-only',action='store_true')
    args=parser.parse_args();{'prepare':prepare,'run':run}[args.command](args)
