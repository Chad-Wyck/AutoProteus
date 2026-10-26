"""Offline timeline audit of closed model trials; never opens a recovering Store."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]

from controller.storage import atomic_json
from observations import navigation_metrics, read_events
from study_report import attempt_folder, load_closed


def audit_events(events):
    start=next((e['time'] for e in events if e.get('type')=='run_started'),None)
    def seconds(event):
        return round((datetime.fromisoformat(event['time'])-datetime.fromisoformat(start)).total_seconds(),3) if start else None
    reads=[];first_edit=first_test=first_full=last_full=finish=None
    seen=Counter();paths=Counter();after=Counter()
    for event in events:
        if event.get('type')=='run_finished': finish=seconds(event)
        data=event.get('data',{});action=data.get('action',{});args=action.get('arguments',{})
        if event.get('type')!='action_result' or not data.get('ok'): continue
        tool=action.get('tool');path=args.get('path','');result=data.get('result',{})
        if tool in ('write_file','edit_file','delete_file') and path.startswith('harness/'):
            if path.startswith('harness/tests/'):
                if first_test is None:first_test=seconds(event)
            elif path.endswith('.py') and first_edit is None:first_edit=seconds(event)
        if tool=='run_command' and result.get('exit_code')==0:
            for line in result.get('output','').splitlines():
                try:value=json.loads(line)
                except ValueError:continue
                if isinstance(value,dict) and value.get('check')=='candidate tests' and value.get('scope')=='full' and value.get('passed') and value.get('tests',0)>0:
                    if first_full is None:first_full=seconds(event)
                    last_full=seconds(event)
        if tool not in ('read_file','read_section') or not isinstance(result,dict) or not isinstance(result.get('content'),str):continue
        content=result['content'];offset=result.get('start',0)
        if type(offset) is not int:continue
        signature=(path,offset,hashlib.sha256(content.encode()).hexdigest())
        prior=seen[signature]>0;seen[signature]+=1;paths[path]+=1
        phase='before_first_edit' if first_edit is None else 'after_first_full_check' if first_full is not None else 'editing_before_full_check'
        if first_full is not None:after[path]+=1
        reads.append({'seconds':seconds(event),'path':path,'start':offset,'characters':len(content),
            'requested_length':args.get('length'),'phase':phase,'same_observed_content_before':prior})
    return {'navigation':navigation_metrics(events),'first_source_edit_seconds':first_edit,'first_test_edit_seconds':first_test,
        'first_full_check_seconds':first_full,'last_full_check_seconds':last_full,'finish_seconds':finish,
        'successful_read_actions':len(reads),'reads_by_path':dict(paths),'reads_after_first_full_check_by_path':dict(after),
        'same_content_repeat_reads':sum(row['same_observed_content_before'] for row in reads),
        'tiny_reads_after_full_check':sum(row['phase']=='after_first_full_check' and row['characters']<=100 for row in reads),
        'phases':dict(Counter(row['phase'] for row in reads)),'reads':reads,
        'interpretation':'Repeated content and post-check reads are observations, not proof of waste. Full development checks are not independent acceptance. Wrong offset units remain a hypothesis.'}


def audit(directory):
    directory,queue_root,plan,queue=load_closed(directory)
    rows=[]
    for cell,attempts in queue['cells'].items():
        for attempt in attempts:
            result=attempt.get('result',{});run=result.get('run',{});session=run.get('session')
            if not session:continue
            if not isinstance(session,str) or len(session)!=32 or any(c not in '0123456789abcdef' for c in session):raise ValueError('Invalid session identity')
            folder=attempt_folder(queue_root,cell,attempt['attempt'])
            path=(folder/'sessions'/session/'events.jsonl').resolve()
            if not path.is_relative_to(folder.resolve()):raise ValueError('Trace escapes closed evidence directory')
            if not path.exists():
                rows.append({'cell':cell,'attempt':attempt['attempt'],'available':False});continue
            if path.stat().st_size>128*1024*1024:raise ValueError('Trace exceeds audit limit')
            rows.append({'cell':cell,'attempt':attempt['attempt'],'available':True,
                'accepted':result.get('first_package_accepted',result.get('review',{}).get('accepted')),
                'trace_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**audit_events(read_events(path))})
    return {'scope':'Closed exports only; source data, no candidate imports or replay. Original outcomes unchanged.','trials':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();atomic_json(Path(args.output),audit(args.input));print('Saved offline trace audit:',args.output)
