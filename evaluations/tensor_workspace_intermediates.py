"""Qualify saved practice-selected patches; never execute editor code on host."""
import copy
import os
from pathlib import Path
import shutil
import sys
import time

from lora6k_state import atomic, read, sha, identity, exclusive
from weight_editor_runtime import require, check_files, Deadline, usage


def complete_score(row, response):
    return {**row, 'reference_correct': bool(row['correct']),
            'correct': bool(row['correct'] and response['finish_reason'] == 'eos'
                            and '</think>' in response['raw_text']),
            'closed_thinking': '</think>' in response['raw_text']}


def prepare(project, output, remaining_from=None):
    import numpy as np
    from tensor_workspace_policy import TensorPolicy
    from weight_editor_sparse import bf16_round
    project, output = Path(project).resolve(), Path(output).resolve()
    require(not output.exists(), 'Never overwrite a publication')
    prior = project/'.data/tensor-workspace-clarity-pair-20261103'
    plan = copy.deepcopy(read(prior/'manifest.json'))
    require(identity(plan) == (prior/'manifest.sha256').read_text().strip(), 'Prior manifest changed')
    check_files(prior, plan['data']); check_files(plan['baseline_import']['root'], plan['baseline_import']['files'])
    output.mkdir(); (output/'code').mkdir(); (output/'requests').mkdir(); (output/'runs').mkdir()
    for name in plan['code']:
        source = project/'evaluations'/name
        if name == 'windows_job.py': source = project/'controller'/name
        shutil.copyfile(source, output/'code'/name)
    for name in ('tensor_workspace_intermediates.py', 'weight_editor_shared_gpu.py'):
        shutil.copyfile(project/'evaluations'/name, output/'code'/name)
    for name in plan['data']: shutil.copyfile(prior/name, output/name)
    records = read(output/'tensor-catalog.json'); base = plan['models']['original_target']
    require(sha(base['path']) == base['sha256'], 'Original model changed')
    source_a = prior/'unchanged/snapshots/c068efaf660746c1b519bdf4b8ef3179/MANIFEST.json'
    source_b = project/'.data/manual4b-targeted-20261103/comparison/targeted/FROZEN.json'
    a, b = read(source_a), read(source_b)
    candidates = {'five_weights': a['edits'], 'threshold_with_rounding': b['edits']}
    sources = {'five_weights': {'path': str(source_a), 'sha256': sha(source_a)},
               'threshold_with_rounding': {'path': str(source_b), 'sha256': sha(source_b)}}
    # Historical bytes are copied unchanged. The new write policy is NOT applied here.
    for arm, edits in candidates.items():
        (output/arm/'snapshots').mkdir(parents=True); owned = {}
        for name, entry in edits.items():
            require(sha(entry['path']) == entry['sha256'], 'Saved numeric patch changed')
            value = np.fromfile(entry['path'], dtype='<f4')
            require(value.size * 4 == records[name]['bytes'] and np.isfinite(value).all(), 'Invalid saved array')
            path = output/arm/'patch.f32'; shutil.copyfile(entry['path'], path)
            owned[name] = {**entry, 'path': str(path)}
        atomic(output/arm/'FROZEN.json', {'edits': owned, 'authorship': 'Saved local 4B practice candidate; not a submitted final artifact'})
    arm = 'rounding_only'; (output/arm/'snapshots').mkdir(parents=True)
    p = TensorPolicy(base, records, output/arm/'read-policy', {})
    name = 'blk.0.attn_norm.weight'; value = bf16_round(p.array(name, edited=False))
    path = output/arm/'patch.f32'; value.astype('<f4').tofile(path)
    atomic(output/arm/'FROZEN.json', {'edits': {name: {'name': name, 'shape': records[name]['shape'],
        'path': str(path), 'sha256': sha(path)}}, 'authorship': 'Host-created BF16-rounding-only negative attribution control'})
    plan.update(scope='Post-hoc independent qualification of practice-selected intermediate 0.8B patches',
        code={p.name: sha(p) for p in (output/'code').iterdir()}, sources=sources,
        expected_model_hashes={'five_weights': a['model']['sha256'],
            'threshold_with_rounding': 'c5e6287a90ce65d38b53ae7aa5fc22ad249b5b305b65bf400b368113e8b75cdd'},
        new_work={'max_seconds': 14400, 'max_generated_tokens': 786432,
            'shared_gpu': 'Previously authorized League sharing, original memory floors retained',
            'no_new_editor_calls': True, 'same_familiar_qualification_cases': True,
            'selection': 'Two practice-success patches identified before this publication; no hidden-outcome search or promotion'})
    plan.pop('predecessor_completion', None); plan.pop('qualification_continuation', None)
    plan['design']['arms'] = list(candidates) + [arm]
    if remaining_from:
        prior_run=Path(remaining_from).resolve();done=read(prior_run/'RESULT.json')
        require(done['status']=='stopped' and 'SnippingTool.exe' in done['error'] and done['all_owned_workers_closed'], 'Not the identified idle-capture admission stop')
        require(done['results']['five_weights']['checked']==8 and done['results']['threshold_with_rounding']['checked']==0,
            'Continuation would duplicate tested candidates')
        stopped=read(prior_run/'runs/call-005/CLOSED.json')
        require(not stopped.get('launcher_pid') and not (prior_run/'runs/call-005/usage.json').exists(), 'Stopped worker already loaded')
        plan['design']['arms']=['threshold_with_rounding','rounding_only']
        plan['remaining_work']={'prior_root':str(prior_run),'prior_plan':identity(read(prior_run/'manifest.json')),
            'prior_result_sha256':sha(prior_run/'RESULT.json'), 'prior_results_sha256':sha(prior_run/'independent-results.json'),
            'original_end_unix':read(prior_run/'runner.json')['began_unix']+14400,
            'scope':'Only previously unstarted candidates. Completed five-weight results remain unchanged.'}
        plan['new_work']['max_generated_tokens']=524288
    plan['limits']['total_seconds'] = 14400
    for arm in plan['design']['arms']: plan['data'][arm+'/FROZEN.json'] = sha(output/arm/'FROZEN.json')
    atomic(output/'manifest.json', plan); (output/'manifest.sha256').write_text(identity(plan))
    atomic(output/'GPU-AUTHORIZATION.json', {'manifest_sha256': identity(plan), 'explicit_user_authorization': False})
    (output/'run.py').write_text("import sys,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parent\nsys.path.insert(0,json.loads((r/'manifest.json').read_text())['project'])\nsys.path.insert(0,str(r/'code'))\nfrom tensor_workspace_intermediates import execute\nexecute(r)\n", encoding='utf8')
    return {'root': str(output), 'plan': identity(plan), 'candidate_cases': 8*len(plan['design']['arms'])}


def enable_sharing():
    import lora6k_supervisor as supervisor
    import weight_editor_owned as owned
    from weight_editor_shared_gpu import classify_shared_owners, admission
    original = supervisor.check_owners
    supervisor.check_owners = lambda rows, names, compute: classify_shared_owners(rows, names, compute, original)
    owned.admission = admission


def execute(root):
    from tensor_workspace_policy import TensorPolicy
    from tensor_workspace_study import Study
    root = Path(root); plan = read(root/'manifest.json'); sys.path.insert(0, plan['project'])
    with exclusive(root):
        require(not (root/'runner.json').exists(), 'No implicit retries')
        enable_sharing(); study = Study(root); results = {}
        if plan.get('remaining_work'):
            ref=plan['remaining_work'];require(sha(Path(ref['prior_root'])/'RESULT.json')==ref['prior_result_sha256'], 'Prior result changed')
            study.deadline=Deadline(ref['original_end_unix']-time.time());study.worker_deadline=study.deadline
        study.state.update(phase='saved_intermediate_qualification'); study.save()
        cases = [c for c in study.cases if c['split'] != 'dev']
        results['baseline'] = [complete_score(study.baseline_cache[c['id']], read(study.baseline_cache[c['id']]['response_file'])) for c in cases]
        # Recheck exact controls and matching requests; do not trust a historical pass flag alone.
        for c in cases:
            row = study.baseline_cache[c['id']]; response = Path(row['response_file']); run = response.parent
            req = read(run.parents[1]/'requests'/(run.name+'.json'))
            require(req['model'] == plan['models']['original_target'] and c in req['cases'], 'Control case/settings mismatch')
            measured = usage(run, read(run/'usage.json')['binding'])
            require(measured['measurement_complete'] and measured['per_case'][c['id']] == row['generated_tokens'], 'Incomplete baseline usage')
        status = 'running'; error = None
        try:
            for arm in plan['design']['arms']:
                study.arm = arm; study.state['arm'] = arm; study.save()
                p = TensorPolicy(plan['models']['original_target'], study.records, root/arm/'qualification-policy', {})
                p.edits = read(root/arm/'FROZEN.json')['edits']; model = p.snapshot(root/arm/'snapshots/model', study.deadline)
                expected = plan['expected_model_hashes'].get(arm)
                require(expected is None or model['sha256'] == expected, 'Historical reconstruction mismatch')
                atomic(root/arm/'RECONSTRUCTION.json', {'model': model, 'matches_historical_sha': model['sha256'] == expected if expected else None})
                results[arm] = []
                try:
                    for i in range(0, len(cases), 2):
                        spent = sum(r['generated_tokens'] for a, rows in results.items() if a != 'baseline' for r in rows)
                        remaining = plan['new_work']['max_generated_tokens'] - spent
                        rows = study.inference('generate', model, cases[i:i+2], remaining=remaining)
                        results[arm].extend(complete_score(r, read(r['response_file'])) for r in rows)
                        atomic(root/'independent-results.json', results)
                finally: study.discard_snapshot(p, model)
            status = 'completed'
        except BaseException as exc:
            status = 'stopped'; error = type(exc).__name__+': '+str(exc)
        finally:
            study.state.update(status=status, phase='closed', error=error, ended_unix=time.time()); study.save()
            closed = [read(p) for p in (root/'runs').glob('*/CLOSED.json')]
            summary = {'status': status, 'error': error, 'results': {a: {'checked': len(rows), 'correct': sum(r['correct'] for r in rows),
                'reference_correct': sum(r['reference_correct'] for r in rows), 'generated_tokens': sum(r['generated_tokens'] for r in rows)} for a, rows in results.items()},
                'all_owned_workers_closed': all(r['owned_worker_closed'] for r in closed),
                'not_autonomous_retained_upgrades': True, 'familiar_fixed_test_comparison': True}
            atomic(root/'RESULT.json', summary); print(summary, flush=True)


if __name__ == '__main__':
    print(prepare(*sys.argv[2:]) if sys.argv[1] == 'prepare' else execute(sys.argv[2]))
