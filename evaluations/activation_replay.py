"""Replay accepted capabilities on fresh inputs; never import candidate code on host."""
import argparse
import base64
import copy
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'evaluations')]
from controller.evaluation import freeze_source, source_identity, run_regressions
from controller.isolation import Broker, IsolatedAgent, VMLease
from controller.storage import Store, atomic_json, now
from controller.compatibility import qualify_profile
from activation_use import activate, oracle_controls
from model_plan import prepare as prepare_base, check, private
from owned_runtime import RuntimeOwner, memory, GIB
from run_budget import BudgetModelClient, GeneratedTokenBudget
from observations import CallRecorder
from study_support import StudyQueue, identity
from study_report import failure_kind
import generalization
import model_study

ARMS=('baseline','task-reminder')
MARKER='REMAINING USER TASK (verbatim from the original request):\n'


def read_parent(directory):
    directory=private(directory)
    result=json.loads((directory/'result.json').read_text())
    if result.get('first_package_accepted') is not True:
        raise ValueError('Replay requires an independently accepted first package')
    source=json.loads((directory/'review/candidate-source.json').read_text())
    digest=source_identity(source)
    if digest != result.get('first_use',{}).get('source_sha256'):
        raise ValueError('Accepted source identity does not match first-use evidence')
    for item in source: base64.b64decode(item['data'],validate=True)
    task=json.loads((directory/'original-task.json').read_text())
    spec=task['first_use']
    if spec['instruction'] not in task['task']:
        raise ValueError('Reminder must already be present verbatim in the original request')
    return {'feature':spec['feature'],'source':source,'source_sha256':digest,
            'task':task['task'],'spec':spec,'origin':str(directory),
            'scope':'Fresh activation-only reconstruction from accepted source and original human task. '
                    'No development transcript, model todo, failed-use output or human repair is supplied.'}


def broker_type(arm, instruction):
    if arm not in ARMS: raise ValueError('Unknown activation replay arm')
    class ReplayBroker(Broker):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            if arm=='task-reminder' and self.activation_context:
                self.activation_context+='\n'+MARKER+instruction
    return ReplayBroker


def prepare(args):
    output=private(args.output)
    parents=[read_parent(path) for path in args.parent]
    if len({p['feature'] for p in parents})!=len(parents): raise ValueError('Parent features must be distinct')
    prepare_base(SimpleNamespace(mode='basic',profiles=args.profiles,output=str(output),repeats=1,
        timeout=args.timeout,output_token_budget=args.tokens,case_pack=None))
    plan=json.loads((output/'plan.json').read_text())
    if len(plan['profiles'])!=1 or not plan['profiles'][0].get('runtime'):
        raise ValueError('Supply one pinned owned-runtime profile')
    plan.update(experiment='activation-handoff-replay-v1',parents=parents,arms=list(ARMS),
        sampling_seeds=[104729,130363,155921],
        interpretation='Exploratory activation-only reuse, not new extension or complete growth-chain evidence. '
            'Both arms use identical frozen candidates, original task, inputs and limits. Only host activation '
            'state gets a verbatim existing requirement reminder. No expected outputs or corrective coaching.',
        primary='Independent first-use grade; artifacts, actual capability/default use, inspection, source preservation and completion separately.')
    plan['schedule']=[]
    for repeat, seed in enumerate(plan['sampling_seeds'],1):
        for parent in parents:
            for arm in ARMS if repeat%2 else reversed(ARMS):
                plan['schedule'].append({'id':f'replay_{repeat:02d}_{parent["feature"]}_{arm}',
                    'feature':parent['feature'],'arm':arm,'seed':seed})
    atomic_json(output/'plan.json',plan)
    (output/'plan.sha256').write_text(identity(plan))


def trial(folder,parent,config,plan,arm):
    store=Store(folder/'sessions')
    session=freeze_source(store,parent['source'],'Accepted activation replay')
    session.update(task=parent['task'],status='waiting',steps=0,runs=0,
        messages=[{'role':'user','origin':'human','content':parent['task']}])
    store.save(session)
    recorder=CallRecorder(folder/'provider-calls.jsonl')
    budget=GeneratedTokenBudget(plan['generated_tokens'])
    clients=[]
    def factory(values):
        client=BudgetModelClient(values,token_budget=budget,observer=recorder)
        clients.append(client)
        return client
    settings=SimpleNamespace(values=dict(config),key=lambda:'')
    agent=IsolatedAgent(ROOT,store,settings,factory)
    if agent.execution.mode!='vm': raise ValueError('Activation replay requires a disposable VM')
    started=time.monotonic()
    try:
        with patch('controller.isolation.Broker',broker_type(arm,parent['spec']['instruction'])):
            result=activate(agent,store,session,settings,config,parent['spec'],budget,
                            started+plan['deadline'],generalization.wait)
    finally:
        agent.close()
    row={'arm':arm,'feature':parent['feature'],'grade':result,'source_sha256':parent['source_sha256'],
         'total_seconds':time.monotonic()-started,'token_budget':budget.summary(),
         **model_study.metrics(folder,recorder,clients)}
    atomic_json(folder/'result.json',row)
    return row


def summarize(queue,plan):
    groups={arm:{'scheduled':sum(c['arm']==arm for c in plan['schedule']),
            'evaluated':0,'passed':0,'artifacts':0,'capability_used':0,'completed':0,
            'source_unchanged':0,'resource_stops':0,'infrastructure_errors':0,'interrupted':0} for arm in ARMS}
    schedule={c['id']:c for c in plan['schedule']}
    for cell,attempts in queue.data['cells'].items():
        if cell not in schedule: continue
        group=groups[schedule[cell]['arm']]
        for attempt in attempts:
            if attempt['state']!='completed':
                cleanup=Path(attempt['folder'])/'runtime/cleanup.json'
                receipt=json.loads(cleanup.read_text()) if cleanup.exists() else {}
                kind,_=failure_kind(attempt,attempt.get('result',{}),receipt)
                group[{'resource':'resource_stops','interrupted':'interrupted'}.get(kind,'infrastructure_errors')]+=1
                continue
            grade=attempt['result']['grade'];group['evaluated']+=1
            for name,field in (('passed','passed'),('artifacts','artifacts_correct'),
                    ('capability_used','capability_used'),('completed','completed'),('source_unchanged','source_unchanged')):
                group[name]+=grade.get(field) is True
    return {'updated':now(),'arms':groups,'queue':queue.summary(),'scope':plan['interpretation']}


def run(args):
    output=private(args.input)
    plan=json.loads((output/'plan.json').read_text())
    if identity(plan)!=(output/'plan.sha256').read_text().strip(): raise ValueError('Frozen replay plan changed')
    check(plan)
    lease=VMLease(output)
    lease.acquire(threading.Event(),time.monotonic()+1)
    queue=StudyQueue(output,identity(plan))
    try:
        calibration=output/'calibration.json'
        if not calibration.exists():
            controls=oracle_controls({p['feature']:p['spec'] for p in plan['parents']})
            checks=[]
            store=Store(output/'calibration/sessions')
            for parent in plan['parents']:
                frozen=freeze_source(store,parent['source'],'Replay parent verification')
                deadline=time.monotonic()+240
                regression=run_regressions(ROOT,store,frozen,deadline=deadline)
                feature=generalization.verify_feature(store,frozen,parent['feature'],deadline=deadline)
                checks.append({'feature':parent['feature'],'regressions':regression,'feature_checks':feature})
                if not regression.get('passed') or not feature.get('passed'):
                    raise ValueError('Replay parent did not pass independent recalibration')
            atomic_json(calibration,{'passed':True,'plan_sha256':identity(plan),'controls':controls,'parents':checks})
        else:
            saved=json.loads(calibration.read_text())
            if not saved.get('passed') or saved.get('plan_sha256')!=identity(plan): raise ValueError('Calibration identity changed')
        profile=plan['profiles'][0]
        owner=RuntimeOwner(profile)
        config=profile['config']
        def execute(folder,selected,call):
            check(plan)
            with owner.attempt(folder,selected,plan['deadline']) as runtime:
                if memory()['available_physical']<4*GIB: raise RuntimeError('Less than 4 GiB before AP guest')
                value=call()
                runtime.guard();check(plan)
            value['runtime_observation']=runtime.record
            atomic_json(folder/'result.json',value)
            return value
        for cell in plan['schedule']:
            if (output/'STOP').exists(): raise KeyboardInterrupt('Operator stop file')
            selected={**config,'sampling_seed':cell['seed'],'server_initial_seed':cell['seed']}
            parent=next(p for p in plan['parents'] if p['feature']==cell['feature'])
            print('START',cell['id'],flush=True)
            queue.run(cell['id'],lambda folder:execute(folder,selected,
                lambda:trial(folder,parent,selected,plan,cell['arm'])))
            atomic_json(output/'summary.json',summarize(queue,plan))
            print('DONE',cell['id'],flush=True)
    finally:
        atomic_json(output/'summary.json',summarize(queue,plan))
        lease.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--profiles',required=True);p.add_argument('--output',required=True)
    p.add_argument('--parent',action='append',required=True);p.add_argument('--timeout',type=int,default=1200)
    p.add_argument('--tokens',type=int,default=16384)
    r=commands.add_parser('run');r.add_argument('--input',required=True)
    args=parser.parse_args()
    (prepare if args.command=='prepare' else run)(args)
