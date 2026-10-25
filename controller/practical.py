"""Optional practical connection checks, using synthetic inputs in fresh VMs."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import uuid

from .compatibility import PROFILE_FIELDS, model_identity
from .evaluation import artifact_check, freeze_source, source_identity
from .isolation import Artifacts, IsolatedAgent, seed_files
from .storage import Store, atomic_json, now


CASES = [
    {'name':'Exact file and nested path', 'task':'Create notes/greeting.txt containing exactly Hello, AutoProteus! followed by one LF newline. Read it back, verify it, then finish completed.',
     'fixtures':{}, 'checks':[{'path':'notes/greeting.txt','equals':'Hello, AutoProteus!\n'}]},
    {'name':'Follow-up correction', 'task':'In settings.json change only theme to dark. Keep count unchanged, read the result, then ask for my confirmation.',
     'fixtures':{'settings.json':'{"count":7,"theme":"light"}'},
     'checks':[{'path':'settings.json','json':{'count':7,'theme':'dark'}}],
     'followup':'Correction: change theme to blue instead. Keep count unchanged, read settings.json to verify it, and finish completed.',
     'final_checks':[{'path':'settings.json','json':{'count':7,'theme':'blue'}}]},
    {'name':'Missing-file recovery', 'task':'Read incoming.txt. If it is missing, ask me for its contents. Do not invent data or create the file yet.',
     'fixtures':{}, 'checks':[{'path':'incoming.txt','absent':True}], 'requires_read_error':True,
     'followup':'Use exactly Recovered safely. followed by one LF newline as incoming.txt contents. Save it, read it back and finish completed.',
     'final_checks':[{'path':'incoming.txt','equals':'Recovered safely.\n'}]}
]


def selection(config):
    value={name:config[name] for name in PROFILE_FIELDS}
    value['internet']=config['internet']
    value['endpoint_sha256']=hashlib.sha256(config['base_url'].encode()).hexdigest()
    return value


class PracticalCheck:
    seconds_per_case = 180
    actions_per_case = 24
    generated_tokens_per_case = 8192

    def __init__(self, root, data, settings, task_agent, gate):
        self.root, self.data, self.settings, self.task_agent, self.gate = Path(root), Path(data), settings, task_agent, gate
        self.lock=threading.RLock();self.thread=None;self.agent=None;self.cancel=threading.Event();self.report=None
        try:
            self.report=json.loads((self.data/'latest.json').read_text())
            if not isinstance(self.report,dict): self.report=None
            if self.report and self.report.get('status')=='running':
                self.report.update(status='interrupted',message='The previous check was interrupted; completed results are retained.')
        except (OSError,ValueError): pass

    @property
    def busy(self): return bool(self.thread and self.thread.is_alive())

    def public(self):
        with self.lock:
            if not self.report: return {'busy':False,'status':'idle','results':[]}
            value=json.loads(json.dumps(self.report))
            value.update(busy=self.busy, selection_matches=value.get('selection')==selection(self.settings.values))
            value['source_matches']=value.get('source_sha256')==source_identity(seed_files(self.root))
            return value

    def _save(self):
        with self.lock:
            atomic_json(self.data/self.report['id']/'report.json',self.report)
            atomic_json(self.data/'latest.json',self.report)

    def start(self):
        with self.gate:
            if self.busy: raise ValueError('A practical model check is already running')
            if self.task_agent.execution.mode!='vm': raise ValueError('Practical model checks require VM isolation')
            config=dict(self.settings.values)
            if not config['configured'] or config['provider']=='demo': raise ValueError('Connect a real model before running the practical check')
            if any(thread.is_alive() for _,thread in self.task_agent.workers.values()): raise ValueError('Stop the current task before checking the model')
            self.task_agent.appliance.verify();self.task_agent.discard_idle();self.task_agent.warm.close()
            source=seed_files(self.root)
            self.cancel=threading.Event()
            self.report={'id':uuid.uuid4().hex,'status':'running','started':now(),'results':[], 'selection':selection(config),
                'message':'Preparing practical model checks…', 'source_sha256':source_identity(source),
                'checks_sha256':hashlib.sha256(json.dumps(CASES,sort_keys=True).encode()).hexdigest(),
                'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'limits':{'seconds_per_case':self.seconds_per_case,'shared_actions_per_case':self.actions_per_case,
                          'shared_generated_tokens_per_case':self.generated_tokens_per_case},
                'scope':'Synthetic ordinary tasks through the saved production connection in fresh VMs. '
                        'Exact artifacts, corrections, observed recovery and completion are separate; no seed-editing qualification.'}
            self._save()
            self.thread=threading.Thread(target=self._run,args=(config,source,self.settings.key()),daemon=True);self.thread.start()
            return self.public()

    def _case(self, case, index, config, source, key):
        from evaluations.run_budget import BudgetModelClient, GeneratedTokenBudget
        directory=self.data/self.report['id']/str(index)
        store=Store(directory/'sessions');budget=GeneratedTokenBudget(self.generated_tokens_per_case)
        values={**config,'action_limit':True,'max_steps':self.actions_per_case}
        settings=SimpleNamespace(values=values,key=lambda:key)
        agent=self.agent=IsolatedAgent(self.root,store,settings,lambda actual:BudgetModelClient(actual,key,token_budget=budget),self.task_agent.execution)
        session=store.create(case['task'],config['provider'],config['model'])
        for name,text in case['fixtures'].items():
            path=Path(session['workspace'])/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8',newline='')
        deadline=time.monotonic()+self.seconds_per_case;started=time.monotonic()
        def wait():
            worker=agent.workers[session['id']][1]
            while worker.is_alive():
                if self.cancel.is_set() or time.monotonic()>=deadline:
                    agent.stop(session['id']);worker.join(timeout=5);return False
                worker.join(timeout=.1)
            return not self.cancel.is_set() and time.monotonic()<deadline
        row={'name':case['name'],'session':session['id'],'passed':False}
        try:
            if self.cancel.is_set():
                row['status']='cancelled'
                return row
            agent.start(session,candidate=freeze_source(store,source,'Protected starter'),deadline=deadline)
            on_time=wait();files=Artifacts(store,session)
            row['initial_artifacts_correct']=all(artifact_check(files,rule) for rule in case['checks'])
            row['initial_status']=session['status'];row['followup_delivered']=False
            row['asked_for_input']=session['status']=='waiting' if case.get('followup') else None
            if case.get('requires_read_error'):
                events=[json.loads(line) for line in (store.directory(session['id'])/'events.jsonl').read_text(encoding='utf-8').splitlines()]
                row['read_error_observed']=any(event.get('type')=='action_result' and event.get('data',{}).get('ok') is False
                    and event['data'].get('action',{}).get('tool')=='read_file'
                    and event['data']['action'].get('arguments',{}).get('path')=='incoming.txt' for event in events)
            remaining=self.actions_per_case-session['steps']
            if (case.get('followup') and on_time and remaining>0 and session['status'] in ('waiting','completed') and not budget.summary()['exhausted']):
                settings.values={**values,'max_steps':remaining}
                agent.start(session,case['followup'],deadline=deadline);row['followup_delivered']=True;on_time=wait()
            row.update(artifacts_correct=all(artifact_check(files,rule) for rule in case.get('final_checks',case['checks'])),
                       completed=session['status']=='completed',timed_out=time.monotonic()>=deadline,
                       actions=session['steps'],status=session['status'])
            row['passed']=bool(on_time and row['initial_artifacts_correct'] and row['artifacts_correct'] and row['completed']
                and (not case.get('followup') or (row['followup_delivered'] and row['asked_for_input']))
                and (not case.get('requires_read_error') or row.get('read_error_observed')))
        except Exception as error:
            row['error']=str(error)[:500]
        finally:
            agent.close();self.agent=None
            row.update(seconds=round(time.monotonic()-started,2),tokens=budget.summary())
        return row

    def _run(self, config, source, key):
        try:
            before=model_identity(config)
            with self.lock: self.report['model_identity']=before
            for index,case in enumerate(CASES,1):
                if self.cancel.is_set(): break
                with self.lock: self.report['message']=f'Checking {index}/{len(CASES)}: {case["name"]}'
                self._save();row=self._case(case,index,config,source,key)
                with self.lock: self.report['results'].append(row)
                self._save()
            after=model_identity(config)
            with self.lock:
                rows=self.report['results'];same=before==after
                self.report.update(status='cancelled' if self.cancel.is_set() else 'completed',finished=now(),
                    passed=bool(not self.cancel.is_set() and same and len(rows)==len(CASES) and all(row['passed'] for row in rows)),
                    model_identity_after=after,identity_unchanged=same,
                    message='Checks stopped; partial results are saved.' if self.cancel.is_set() else
                        f'{sum(row["passed"] for row in rows)}/{len(CASES)} practical tasks passed.' + ('' if same else ' Model identity changed during the check.'))
        except Exception as error:
            with self.lock: self.report.update(status='error',message=str(error)[:500],passed=False,finished=now())
        finally: self._save()

    def stop(self):
        self.cancel.set()
        if self.agent: self.agent.close()

    def close(self):
        self.stop()
        if self.thread: self.thread.join(timeout=10)
