"""Separate first-use observation reassessment of closed, hash-checked exports.

Never recovers a Store, executes candidate code, alters original results or
regrades independent implementation reviews and second-task verdicts.
"""
import argparse
import base64
import hashlib
from pathlib import Path
import re
import sys

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from controller.artifacts import MAX_FILE, relative_name, safe_path
from controller.evaluation import source_identity
from controller.storage import atomic_json, now
from activation_use import PROTOCOL, grade
from observations import read_events
from study_report import attempt_folder, load_closed, read_json


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EvidenceError(RuntimeError):
    """Corrupt evidence must stop reassessment, not become a model failure."""


class FrozenFiles:
    def __init__(self,directory,session):self.directory,self.session=directory,session
    def read(self,name):
        relative_name(name)
        item=self.session.get('artifacts',{}).get(name,{})
        value=item.get('sha256','')
        if not re.fullmatch('[a-f0-9]{64}',value):raise ValueError('Missing saved artifact')
        path=safe_path(self.directory/'quarantine',value+'.blob')
        if path.stat().st_size>MAX_FILE:raise EvidenceError('Artifact too large')
        raw=path.read_bytes()
        if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=value:raise EvidenceError('Artifact identity mismatch')
        return raw


def reassess(directory):
    directory,queue_root,plan,queue=load_closed(directory)
    if plan.get('protocol')!=PROTOCOL:raise ValueError('This reassessment requires activation-use-v2')
    rows=[];first={};second=[]
    for cell,attempts in queue['cells'].items():
        for attempt in attempts:
            if attempt['state']!='completed':continue
            if not attempt.get('result',{}).get('added'):continue
            folder=attempt_folder(queue_root,cell,attempt['attempt'])
            result_path=folder/'result.json';row=read_json(result_path)
            if row.get('earlier'):
                second.append((cell,row));continue
            if not row.get('added'):continue
            original=row.get('first_use',{})
            entry={'cell':cell,'attempt':attempt['attempt'],'treatment':row.get('treatment','baseline'),
                'package_accepted':row.get('first_package_accepted'),
                'raw_first_use_passed':original.get('passed',False),'reassessed_first_use_passed':False,
                'result_sha256':digest(result_path),'reassessed':False}
            if original.get('activated'):
                sid=row['run']['session']
                if not isinstance(sid,str) or not re.fullmatch('[a-f0-9]{32}',sid):raise ValueError('Invalid session identity')
                session_dir=safe_path(folder,'sessions/'+sid)
                session_path=safe_path(session_dir,'session.json');session=read_json(session_path)
                if session['id']!=sid:raise ValueError('Session identity mismatch')
                files=FrozenFiles(session_dir,session)
                source=[{'path':name[8:],'data':base64.b64encode(files.read(name)).decode()}
                    for name in sorted(session['artifacts']) if name.startswith('harness/')]
                unchanged=source_identity(source)==original['source_sha256']
                events_path=safe_path(session_dir,'events.jsonl')
                if events_path.stat().st_size>128*1024*1024:raise ValueError('Trace too large')
                events=read_events(events_path)
                boundaries=[i for i,e in enumerate(events) if e.get('type')=='run_started']
                if len(boundaries)<2:raise ValueError('No recorded first activation boundary')
                spec=read_json(folder/'task.json')['first_use']
                budget=row['token_budget'];config=next(p['config'] for p in plan['profiles'] if cell.startswith(p['id']+'_'))
                result=grade(files,spec,events[boundaries[-1]:],source_unchanged=unchanged,
                    completed=original.get('run',{}).get('status')=='completed',
                    on_time=not row['wall_budget']['deadline_reached'] and not original['run'].get('timed_out'),
                    within_budget=original['shared_actions_used']<=config['max_steps'] and budget['charged_output_tokens']<=budget['limit'])
                entry.update(reassessed=True,reassessed_first_use_passed=result['passed'],checks=result,
                    events_sha256=digest(events_path),session_sha256=digest(session_path),
                    task_sha256=digest(folder/'task.json'),current_candidate_sha256=source_identity(source))
            rows.append(entry);first[cell]=entry
    chains=[]
    for cell,row in second:
        parent=first.get(cell.replace('_growth_','_first_',1))
        if not parent:raise ValueError('Missing first-task parent evidence')
        second_passed=row.get('scores',{}).get('functional_growth') is True
        chains.append({'cell':cell,'treatment':row.get('treatment','baseline'),
            'raw_complete_chain_passed':row['chain']['complete_chain_passed'],
            'second_task_passed_unchanged':second_passed,
            'reassessed_complete_chain_passed':parent['reassessed_first_use_passed'] and second_passed})
    return {'created':now(),'study':str(directory),'protocol':PROTOCOL,
        'scope':'First-use observation reassessment only. Independent reviews and second-task verdicts unchanged; original primary results are preserved. No candidate replay or host execution.',
        'plan_sha256':digest(directory/'plan.json'),'queue_sha256':digest(queue_root/'queue.json'),
        'observer_sha256':digest(Path(__file__).resolve().parents[1]/'controller/tool_evidence.py'),
        'first':rows,'chains':chains}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();value=reassess(args.input);atomic_json(Path(args.output),value)
    print({'first_raw':sum(r['raw_first_use_passed'] for r in value['first']),
        'first_reassessed':sum(r['reassessed_first_use_passed'] for r in value['first']),
        'chains_raw':sum(r['raw_complete_chain_passed'] for r in value['chains']),
        'chains_reassessed':sum(r['reassessed_complete_chain_passed'] for r in value['chains'])})
