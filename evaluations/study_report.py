"""Read closed study exports as data; never recover sessions or run candidates."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]

from controller.storage import atomic_json
from activation_use import PROTOCOL
from repeatability import sampling_record
from study_support import task_observations


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


def failure_kind(attempt, result, cleanup):
    """Use receipts first; a downstream connection error is not model evidence."""
    reason = cleanup.get('reason') or result.get('resource_reason') or attempt.get('detail') or ''
    category = cleanup.get('failure_category') or result.get('failure_category')
    # Recognize the exact legacy guard wording without modifying old records.
    if category == 'resource' or any(text in reason for text in (
            'Memory floor reached; owned inference stopped',
            'Insufficient memory headroom for owned inference startup',
            'Sustained host memory pressure')):
        return 'resource', reason
    if attempt['state'] == 'interrupted' or category == 'operator_interruption':
        return 'interrupted', reason
    if attempt['state'] == 'error' or category or result.get('infrastructure_failure'):
        return 'infrastructure', reason or result.get('infrastructure_failure', '')
    return None, reason


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
            cleanup = {}
            if attempt.get('attempt', 0)>0:
                path = (attempt_folder(queue_root,cell,attempt['attempt'])/'runtime/cleanup.json').resolve()
                if not path.is_relative_to(queue_root.resolve()):
                    raise ValueError('Runtime receipt escapes study')
                if path.exists(): cleanup=read_json(path)
            kind, stop_reason = failure_kind(attempt, result, cleanup)
            case=schedule.get(cell,{})
            profile=next((p['id'] for p in sorted(plan.get('profiles',[]), key=lambda p: len(p['id']), reverse=True)
                          if cell.startswith(p['id']+'_')),'local-model')
            suffix = cell[len(profile)+1:] if cell.startswith(profile+'_') else cell
            phase = ('second' if result.get('earlier') else 'first' if result.get('added') else
                     'reuse' if result.get('reuse') else 'ordinary' if result.get('run') else 'inference')
            if not result:
                phase=('second' if suffix.startswith('growth_') else 'first' if suffix.startswith('first_') or case.get('feature') else
                       'ordinary' if suffix.startswith('basic_') else 'inference' if suffix.startswith('benchmark_') else 'unmeasured')
            outcome = task_observations(result.get('run', {})) if phase == 'ordinary' else {}
            first_use = result.get('first_use') or {}
            if phase == 'first':
                outcome = {'artifacts_correct': first_use.get('artifacts_correct'),
                           'explicit_completion': first_use.get('completed'),
                           'capability_used': first_use.get('capability_used')}
            elif phase == 'second':
                outcome = {'artifacts_correct': result.get('final_artifacts_correct'),
                           'explicit_completion': result.get('stages', {}).get('explicit_finish'),
                           'capability_used': result.get('scores', {}).get('capabilities_used')}
            if attempt['state'] != 'completed' or kind:
                outcome = {}  # Partial result bytes are not completed observations.
            labels, failed=failure_labels(result)
            if kind:
                # Partial checks remain in the raw record. They do not explain
                # a completed capability verdict when execution was disrupted.
                labels = [{'resource':'resource_stop', 'interrupted':'interrupted',
                           'infrastructure':'infrastructure_error'}[kind]]
                failed = []
            if phase == 'ordinary' and outcome.get('explicit_completion') is False:
                labels.append('explicit_completion_missing')
            if phase == 'ordinary' and outcome.get('artifacts_correct') is False:
                labels.append('task_artifacts')
            captured=result.get('capture',{}).get('complete') and not result.get('capture',{}).get('observer_failed')
            measurements={name:{**value,'complete':bool(captured and value.get('complete'))}
                for name,value in result.get('calls',{}).get('measurements',{}).items()}
            rows.append({'cell':cell,'attempt':attempt.get('attempt',0),'state':attempt['state'],
                'profile':profile,'arm':case.get('arm',
                    ('public-verifier-feedback' + ('+task-reminder' if plan.get('activation_reminder') else ''))
                    if plan.get('public_verifier_feedback') else 'task-reminder' if plan.get('activation_reminder') else result.get('treatment','baseline')),'phase':phase,
                'activation_reminder':result.get('activation_reminder'),
                'public_verifier':result.get('public_verifier'),
                'outcome': outcome, 'sampling': result.get('sampling'),
                'failure_kind':kind, 'resource_reason':stop_reason if kind else None,
                'runtime': {key: result['runtime_observation'][key] for key in
                    ('fresh_server', 'initial_server_seed', 'request_seed', 'reported_seed_matches', 'reported_context_matches', 'load_seconds')
                    if key in result['runtime_observation']} if result.get('runtime_observation') else None,
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
                'reason':stop_reason or attempt.get('reason') or attempt.get('detail')})
    groups={}
    for row in rows:
        key=row['profile']+'/'+row['arm']
        group=groups.setdefault(key,{'launched':0,'finished':0,'first_attempts':0,'first_packages':0,'first_use_attempts':0,'first_use_passed':0,
            'ordinary_evaluated':0,'first_evaluated':0,'second_evaluated':0,
            'resource_stops':0,'infrastructure_errors':0,'interruptions':0,
            'public_verifier_stages':0,'public_passed_without_feedback':0,'public_corrections':0,'public_passed_after_feedback':0,
            'second_attempts':0,'second_verified':0,'second_use_passed':0,'complete_chains':0 if chain_measured else None,'diagnostic_second':0,
            'ordinary_attempts':0,'ordinary_checks':0,'ordinary_artifacts_correct':0,
            'ordinary_completion_observations':0,'ordinary_explicit_completion':0,'ordinary_passed':0,
            'not_run':{'ordinary':0,'first':0,'second':0,'inference':0,'unmeasured':0}})
        if row['state'] == 'not_run':
            group['not_run'][row['phase']] = group['not_run'].get(row['phase'], 0) + 1
        group['ordinary_attempts'] += row['phase'] == 'ordinary' and row['attempt'] > 0
        group['launched']+=row['attempt']>0
        group['finished']+=row['state']=='completed'
        group['first_attempts']+=row['phase']=='first' and row['attempt']>0
        group['second_attempts']+=row['phase']=='second' and row['attempt']>0
        if row['failure_kind']:
            group[{'resource':'resource_stops','interrupted':'interruptions','infrastructure':'infrastructure_errors'}[row['failure_kind']]]+=1
        if row['state']!='completed' or row['failure_kind']: continue  # Partial results cannot earn credit.
        if row['public_verifier']:
            feedback = row['public_verifier']
            group['public_verifier_stages'] += 1
            group['public_passed_without_feedback'] += feedback.get('passed_without_feedback') is True
            group['public_corrections'] += feedback.get('corrections', 0)
            group['public_passed_after_feedback'] += feedback.get('passed_after_feedback') is True
        if row['phase'] in ('ordinary','first','second'): group[row['phase']+'_evaluated']+=1
        group['first_use_attempts']+=bool(row['first_use'] and row['first_use'].get('attempted'))
        if row['phase'] == 'ordinary':
            group['ordinary_checks'] += type(row['outcome'].get('artifacts_correct')) is bool
            group['ordinary_artifacts_correct'] += row['outcome'].get('artifacts_correct') is True
            group['ordinary_completion_observations'] += type(row['outcome'].get('explicit_completion')) is bool
            group['ordinary_explicit_completion'] += row['outcome'].get('explicit_completion') is True
            group['ordinary_passed'] += row['outcome'].get('task_passed') is True
        group['first_packages']+=row['phase']=='first' and row['package_accepted'] is True
        group['first_use_passed']+=bool(row['first_use'] and row['first_use'].get('passed'))
        group['second_verified']+=row['phase']=='second' and row['package_verified'] is True
        group['second_use_passed']+=row['second_task_passed'] is True
        group['diagnostic_second']+=row['diagnostic_second'] is True
        if chain_measured: group['complete_chains']+=row['complete_chain_passed'] is True
    public_profiles=[{'id':p.get('id'),'config':{key:value for key,value in p.get('config',{}).items() if key in
        ('provider','model','protocol','context_tokens','response_tokens','temperature','thinking','max_steps','request_timeout','terminal','internet','action_limit',
         'sampling_seed','sampling_seed_mode','server_initial_seed')}, 'sampling': p.get('sampling', sampling_record(p.get('config', {})))}
        for p in plan.get('profiles',[])]
    return {'protocol':plan.get('protocol','legacy'),'source_sha256':plan.get('source_sha256',plan.get('sources')),
        'activation_reminder':plan.get('activation_reminder',False),
        'public_verifier_feedback':plan.get('public_verifier_feedback',False),
        'profiles':public_profiles,'groups':groups,'rows':rows,
        'scope':'Read-only report. Saved records are unchanged. Score fractions cover fully evaluated attempts only; '
                'all launched attempts, resource stops, infrastructure errors and interruptions remain visible separately. '
                'Correct artifacts, explicit completion and actual capability use are separate observations. '
                'Not-run cells are untested, not failed attempts. Artifact counts cover recorded checks (including behavior checks), not arbitrary feature correctness. '
                'Legacy first autonomous use and complete chains are unmeasured, not zero. Labels are overlapping observations, not proven causes.',
        'cost_scope':'Known sums retain completeness flags. Token enforcement charges are not measured generation. No efficiency ranking is made here.'}


def markdown(value):
    def fraction(passed, total):
        return f'{passed}/{total}' if total else 'unmeasured'
    text=['# Study outcome report','',value['scope'],'',value['cost_scope'],'',
        '## Basic tasks','',
        '| Profile / arm | Correct checked artifacts | Explicit completion | Strict task passes / evaluated | Basic not run |',
        '| --- | ---: | ---: | ---: | ---: |']
    for key, row in value['groups'].items():
        text.append(f"| {key.replace('|','/')} | {fraction(row['ordinary_artifacts_correct'], row['ordinary_checks'])} | "
                    f"{fraction(row['ordinary_explicit_completion'], row['ordinary_completion_observations'])} | "
                    f"{fraction(row['ordinary_passed'], row['ordinary_evaluated'])} | {row['not_run']['ordinary']} |")
    text += ['', '## Extensions and use', '',
        '| Profile / arm | First packages | First use | Second verified | Second use | Complete chains | Diagnostic second-stage attempts |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for key,row in value['groups'].items():
        first_use=fraction(row['first_use_passed'],row['first_use_attempts']) if value['protocol']==PROTOCOL else 'unmeasured'
        chains=row['complete_chains'] if row['complete_chains'] is not None and row['first_evaluated'] else 'unmeasured'
        text.append(f"| {key.replace('|','/')} | {fraction(row['first_packages'],row['first_evaluated'])} | {first_use} | {fraction(row['second_verified'],row['second_evaluated'])} | {fraction(row['second_use_passed'],row['second_evaluated'])} | {chains} | {row['diagnostic_second']} |")
    if value.get('public_verifier_feedback'):
        text += ['', '## Experimental public verifier', '',
                 'These checks were disclosed before inference. They are separate from hidden qualification; extension/use scores above include any automatic correction. Public success alone does not establish a complete workflow.', '',
                 '| Profile / arm | Public stages checked | Passed before feedback | Corrections | Passed after feedback |',
                 '| --- | ---: | ---: | ---: | ---: |']
        for key, row in value['groups'].items():
            text.append(f"| {key.replace('|','/')} | {row['public_verifier_stages']} | {row['public_passed_without_feedback']} | {row['public_corrections']} | {row['public_passed_after_feedback']} |")
    text += ['', '## Execution accounting', '',
             '| Profile / arm | Launched | Finished | Resource stops | Other infrastructure errors | Interrupted |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for key,row in value['groups'].items():
        text.append(f"| {key.replace('|','/')} | {row['launched']} | {row['finished']} | {row['resource_stops']} | {row['infrastructure_errors']} | {row['interruptions']} |")
    text += ['', '## Cells not run', '', '| Profile / arm | Basic | First extension | Second extension | Inference |',
             '| --- | ---: | ---: | ---: | ---: |']
    for key, row in value['groups'].items():
        skipped = row['not_run']
        text.append(f"| {key.replace('|','/')} | {skipped['ordinary']} | {skipped['first']} | {skipped['second']} | {skipped['inference']} |")
    text += ['', '## Sampling', '']
    for profile in value['profiles']:
        sampling = profile['sampling']
        text.append(f"- {profile['id']}: {sampling['mode']}; initial request seed {sampling['request_seed']}; "
                    f"declared initial server seed {sampling['declared_server_initial_seed']}. Server initialization is unverified by this report.")
    if any(row.get('runtime') for row in value['rows']):
        text += ['', '## Runtime receipts', '',
            'Load time is recorded separately from trial time. Reported seed matches are not proof of RNG determinism.', '',
            '| Cell | Fresh owned service | Initial server seed | Reported seed matches | Load seconds |',
            '| --- | --- | --- | --- | --- |']
        for row in value['rows']:
            runtime = row.get('runtime')
            if not runtime: continue
            text.append('| ' + ' | '.join(str(item).replace('|', '/') for item in (
                row['cell'], runtime.get('fresh_server', 'unmeasured'), runtime.get('initial_server_seed', 'unmeasured'),
                runtime.get('reported_seed_matches', 'unmeasured'), runtime.get('load_seconds', 'unmeasured'))) + ' |')
    text+=['','## Attempt details','','| Cell | State | Phase | Artifacts | Explicit completion | Capability used | Failures / checks |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    for row in value['rows']:
        detail=', '.join(row['failure_labels']+row['failed_feature_checks']) or row['reason'] or 'No recorded failure label'
        if row.get('resource_reason'): detail += ': ' + str(row['resource_reason'])
        if row['state'] == 'not_run': detail = 'Not run: ' + (row['reason'] or 'No reason recorded')
        def verdict(key):
            observed = row['outcome'].get(key)
            return 'yes' if observed is True else 'no' if observed is False else 'unmeasured'
        text.append('| '+ ' | '.join(str(v).replace('|','/').replace('\n',' ') for v in
            (row['cell'],row['state'],row['phase'],verdict('artifacts_correct'),verdict('explicit_completion'),verdict('capability_used'),detail))+' |')
    return '\n'.join(text)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();value=report(args.input);path=Path(args.output)
    atomic_json(path.with_suffix('.json'),value);path.with_suffix('.md').write_text(markdown(value),encoding='utf-8')
    print('Saved closed-study report:',path.with_suffix('.md'))
