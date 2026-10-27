"""Read closed study exports as data; never recover sessions or run candidates."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]

from controller.storage import atomic_json
from activation_use import PROTOCOL


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 128*1024*1024: raise ValueError('Study record exceeds 128 MiB')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_closed(directory):
    directory = Path(directory).resolve()
    plan = read_json(directory/'plan.json')
    queue_root = directory if (directory/'queue.json').exists() else directory/'live'
    queue = read_json(queue_root/'queue.json')
    if any(row.get('state')=='running' for attempts in queue['cells'].values() for row in attempts):
        raise ValueError('Use closed study exports; this queue still has running work')
    return directory, queue_root, plan, queue


def attempt_folder(queue_root, cell, attempt):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,160}',cell) or type(attempt) is not int or attempt<1:
        raise ValueError('Invalid attempt identity')
    # Reconstruct portable paths rather than following absolute paths from an export.
    root = Path(queue_root).resolve()
    path = (root/'trials'/cell/f'attempt-{attempt:03d}').resolve()
    if not path.is_relative_to(root): raise ValueError('Evidence path escapes study')
    return path


def failure_labels(row):
    review = row.get('review',{})
    run = row.get('run',{})
    feature = review.get('feature') or {}
    probe = feature.get('probe',{})
    failed = [name for name,value in probe.get('checks',{}).items() if value is not True]
    labels = []
    if review.get('allowed_files_only') is False or review.get('protected_unchanged') is False:
        labels.append('submission_scope')
    if review.get('new_test_files')==[]: labels.append('missing_candidate_tests')
    if review.get('regressions',{}).get('passed') is False: labels.append('protected_regressions')
    if any('schema' in name or name=='registered' for name in failed): labels.append('tool_interface')
    if any('schema' not in name and name!='registered' for name in failed): labels.append('implementation')
    if probe.get('suite',{}).get('exit_code') not in (None,0): labels.append('candidate_tests')
    if (review.get('public') or {}).get('passed') is False: labels.append('fresh_public_invocation')
    if row.get('calls',{}).get('error_categories'): labels.append('provider_or_format')
    if run.get('timed_out') or row.get('wall_budget',{}).get('deadline_reached'): labels.append('wall_allowance')
    if row.get('token_budget',{}).get('exhausted'): labels.append('token_allowance')
    if run.get('status')=='paused' and not run.get('timed_out'): labels.append('paused_or_action_allowance')
    first = row.get('first_use')
    if first and first.get('attempted') and not first.get('passed'): labels.append('first_use')
    if row.get('stage_order_preserved') is False:
        labels.append('final_input_changed_before_activation')
    if row.get('stages',{}).get('activated') and row.get('scores',{}).get('functional_growth') is False:
        labels.append('second_use')
    if review and review.get('completed') is False and run.get('status') not in ('waiting','completed'):
        labels.append('development_not_completed')
    return labels, failed


def report(directory):
    directory, queue_root, plan, queue = load_closed(directory)
    if plan.get('mode')=='outcomes':
        raise ValueError('Outcome-only studies use their runner summary.json and outcome-results.json; no named-feature upgrade score applies')
    prospective = plan.get('protocol')==PROTOCOL
    chain_measured = prospective and not plan.get('parent') and plan.get('growth_enabled',True)
    schedule = {row['id']:row for row in plan.get('schedule',[]) if 'id' in row}
    rows=[]
    for cell, attempts in queue['cells'].items():
        for attempt in attempts:
            result = attempt.get('result',{})
            if not result and attempt.get('attempt',0)>0:
                path=attempt_folder(queue_root,cell,attempt['attempt'])/'result.json'
                if path.exists(): result=read_json(path)
            case=schedule.get(cell,{})
            profile=next((p['id'] for p in plan.get('profiles',[]) if cell.startswith(p['id']+'_')),'local-model')
            phase = ('second' if result.get('earlier') else 'first' if result.get('added') else
                     'reuse' if result.get('reuse') else 'ordinary' if result.get('run') else 'inference')
            if not result:
                phase=('first' if '_first_' in cell or case.get('feature') else 'second' if '_growth_' in cell else 'unmeasured')
            labels, failed=failure_labels(result)
            captured=result.get('capture',{}).get('complete') and not result.get('capture',{}).get('observer_failed')
            measurements={name:{**value,'complete':bool(captured and value.get('complete'))}
                for name,value in result.get('calls',{}).get('measurements',{}).items()}
            rows.append({'cell':cell,'attempt':attempt.get('attempt',0),'state':attempt['state'],
                'profile':profile,'arm':case.get('arm',result.get('treatment','baseline')),'phase':phase,
                'feature':result.get('added'),'package_verified':result.get('review',{}).get('verified_upgrade'),
                'package_accepted':result.get('first_package_accepted') if prospective and phase=='first'
                    else result.get('review',{}).get('accepted'),
                'first_use':result.get('first_use'), 'second_task_passed':result.get('scores',{}).get('functional_growth'),
                'complete_chain_passed':result.get('chain',{}).get('complete_chain_passed'),
                'diagnostic_second':result.get('chain',{}).get('diagnostic_only'),
                'failure_labels':labels,'failed_feature_checks':failed,
                'feature_checks_not_run_reason':(result.get('review',{}).get('feature') or {}).get('reason'),
                'unexpected_files':result.get('review',{}).get('unexpected_files',[]),
                'protected_changes':result.get('review',{}).get('protected_changes',[]),
                'seconds':result.get('total_seconds'),'measurements':measurements,
                'token_enforcement':result.get('token_budget'),
                'reason':attempt.get('reason') or attempt.get('detail')})
    groups={}
    for row in rows:
        key=row['profile']+'/'+row['arm']
        group=groups.setdefault(key,{'launched':0,'finished':0,'first_attempts':0,'first_packages':0,'first_use_attempts':0,'first_use_passed':0,
            'second_attempts':0,'second_verified':0,'second_use_passed':0,'complete_chains':0 if chain_measured else None,'diagnostic_second':0})
        group['launched']+=row['attempt']>0
        group['finished']+=row['state']=='completed'
        group['first_attempts']+=row['phase']=='first' and row['attempt']>0
        group['first_use_attempts']+=bool(row['first_use'] and row['first_use'].get('attempted'))
        group['second_attempts']+=row['phase']=='second' and row['attempt']>0
        if row['state']!='completed': continue  # Partial result bytes cannot earn credit.
        group['first_packages']+=row['phase']=='first' and row['package_accepted'] is True
        group['first_use_passed']+=bool(row['first_use'] and row['first_use'].get('passed'))
        group['second_verified']+=row['phase']=='second' and row['package_verified'] is True
        group['second_use_passed']+=row['second_task_passed'] is True
        group['diagnostic_second']+=row['diagnostic_second'] is True
        if chain_measured: group['complete_chains']+=row['complete_chain_passed'] is True
    public_profiles=[{'id':p.get('id'),'config':{key:value for key,value in p.get('config',{}).items() if key in
        ('provider','model','protocol','context_tokens','response_tokens','temperature','thinking','max_steps','request_timeout','terminal','internet','action_limit')}}
        for p in plan.get('profiles',[])]
    return {'protocol':plan.get('protocol','legacy'),'source_sha256':plan.get('source_sha256',plan.get('sources')),
        'profiles':public_profiles,'groups':groups,'rows':rows,
        'scope':'Read-only report. Historical scores are unchanged. Legacy first autonomous use and complete chains are unmeasured, not zero. Labels are overlapping observations, not proven causes.',
        'cost_scope':'Known sums retain completeness flags. Token enforcement charges are not measured generation. No efficiency ranking is made here.'}


def markdown(value):
    text=['# Study outcome report','',value['scope'],'',value['cost_scope'],'',
        '| Profile / arm | First packages | First use | Second verified | Second use | Complete chains | Diagnostic second-stage attempts |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for key,row in value['groups'].items():
        first_use=f"{row['first_use_passed']}/{row['first_use_attempts']}" if value['protocol']==PROTOCOL else 'unmeasured'
        text.append(f"| {key.replace('|','/')} | {row['first_packages']}/{row['first_attempts']} | {first_use} | {row['second_verified']}/{row['second_attempts']} | {row['second_use_passed']}/{row['second_attempts']} | {row['complete_chains'] if row['complete_chains'] is not None else 'unmeasured'} | {row['diagnostic_second']} |")
    text+=['','## Attempt details','','| Cell | State | Phase | Failures / checks |','| --- | --- | --- | --- |']
    for row in value['rows']:
        detail=', '.join(row['failure_labels']+row['failed_feature_checks']) or row['reason'] or 'No recorded failure label'
        text.append('| '+ ' | '.join(str(v).replace('|','/').replace('\n',' ') for v in
            (row['cell'],row['state'],row['phase'],detail))+' |')
    return '\n'.join(text)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();value=report(args.input);path=Path(args.output)
    atomic_json(path.with_suffix('.json'),value);path.with_suffix('.md').write_text(markdown(value),encoding='utf-8')
    print('Saved closed-study report:',path.with_suffix('.md'))
