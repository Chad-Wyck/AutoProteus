"""Opt-in bounded research coordinator. Preparation never calls this entry point."""
import json
from pathlib import Path
import sys

from lora6k_state import atomic, exclusive, identity, read, sha
from weight_editor_artifacts import build, proposal
from weight_editor_owned import inference_phase
from weight_editor_runtime import Deadline, DuplicateArtifact, InsufficientCalibration, calibration_split, check_files, completed_phases, require, unique_artifact, verdict
from weight_repair_protocol import grade
from weight_editor_format import render_feedback


def check_coordinator_environment(plan):
    """Fail before calibration if the parent cannot prepare editor turns/edits."""
    from importlib import metadata, util
    expected = plan['interpreters']['python']
    require(Path(sys.executable).resolve() == Path(expected['path']).resolve()
            and sha(sys.executable) == expected['sha256'], 'Start the coordinator with the pinned ML Python interpreter')
    for name in ('tokenizers', 'numpy'):
        require(util.find_spec(name) is not None, 'Missing coordinator dependency: ' + name)
        require(metadata.version(name) == plan['preparation_environment']['packages'][name], 'Coordinator dependency version changed: ' + name)


def experiment(plan, cases, diagnostics, infer, make_candidate, save):
    """Pure orchestration boundary, also exercised with scripted CPU controls."""
    by_id = {case['id']: case for case in cases}
    baseline, control = [plan['models'][key] for key in ('repaired_target', 'fixed_control')]
    calibrated = infer('calibration', baseline, [c for c in cases if c['split'] == 'calibration'])
    try:
        split = calibration_split(calibrated)
    except InsufficientCalibration:
        return {'status': 'completed', 'outcome': 'calibration_pool_not_informative', 'editor_calls': 0,
                'heldout_untested': 18, 'no_pool_expansion': True}
    save('CALIBRATION-SPLIT.json', split)
    dev = [by_id[name] for name in split['development']]
    confirm = [by_id[name] for name in split['confirmation']]
    base_dev = [r for r in calibrated if r['id'] in split['development']]
    base_confirm = [r for r in calibrated if r['id'] in split['confirmation']]
    fixed_dev = infer('control-development', control, dev)
    feedback = {'development': base_dev, 'development_cases': dev, 'fixed_control': fixed_dev,
                'weight_diagnostics': diagnostics, 'trials': []}
    candidates, existing = [], {baseline['sha256'], control['sha256']}
    calls = 0
    while calls < 4 and len(candidates) < 2:
        calls += 1
        reply = infer('editor-' + str(calls), plan['models']['editor_model'], feedback, editor=True)
        try:
            chosen = proposal(reply)
            if chosen is None:
                break
        except (ValueError, json.JSONDecodeError) as error:
            feedback['trials'].append({'rejected': str(error)})
            continue
        try:
            artifact = make_candidate('candidate-' + str(calls), chosen, existing)
            unique_artifact(artifact['sha256'], existing)
        except DuplicateArtifact as error:
            feedback['trials'].append({'rejected': str(error)})
            continue
        existing.add(artifact['sha256'])
        name = 'candidate-' + str(calls)
        rows = infer(name + '-development', artifact, dev)
        evaluated = {'name': name, 'artifact': artifact, 'proposal': chosen, 'rows': rows, 'verdict': verdict(base_dev, rows)}
        candidates.append(evaluated)
        feedback['trials'].append({'proposal': chosen, 'results': rows})
        save(name + '-VERDICT.json', evaluated)
    eligible = [c for c in candidates if c['verdict']['qualified_quality_gain']]
    if not eligible:
        return {'status': 'completed', 'outcome': 'no_development_quality_gain', 'editor_calls': calls, 'heldout_untested': 18}
    chosen = min(eligible, key=lambda c: sum(r['generated_tokens'] for r in c['rows']))
    save('FROZEN-CANDIDATE.json', chosen)
    fixed_confirm = infer('control-confirmation', control, confirm)
    checked = infer('selected-confirmation', chosen['artifact'], confirm)
    confirmed = verdict(base_confirm, checked)
    save('CONFIRMATION.json', {'selected': confirmed, 'fixed_control': verdict(base_confirm, fixed_confirm)})
    if not confirmed['qualified_quality_gain']:
        return {'status': 'completed', 'outcome': 'independent_confirmation_failed', 'editor_calls': calls, 'heldout_untested': 18}
    heldout = [c for c in cases if c['split'] == 'heldout']
    outcomes = {}
    for label, model in [('baseline', baseline), ('control', control), ('selected', chosen['artifact'])]:
        outcomes[label] = infer(label + '-heldout', model, heldout)
    return {'status': 'completed', 'outcome': 'fresh_local_heldout_observed', 'editor_calls': calls,
            'heldout_rows': outcomes, 'selected_vs_baseline': verdict(outcomes['baseline'], outcomes['selected']),
            'selected_vs_fixed_control': verdict(outcomes['control'], outcomes['selected']), 'heldout_untested': 0}


class Study:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.plan = read(self.root / 'manifest.json')
        require(identity(self.plan) == (self.root / 'manifest.sha256').read_text().strip(), 'Plan changed')
        require(read(self.root / 'GPU-AUTHORIZATION.json') == {'manifest_sha256': identity(self.plan), 'explicit_user_authorization': True}, 'GPU work not authorized')
        qualified = read(self.root / 'RUNTIME-QUALIFIED.json')
        require(qualified.get('manifest_sha256') == identity(self.plan) and qualified.get('passed') is True,
                'New runtime GPU preflight is still pending')
        require(bool(qualified.get('evidence_files')), 'Missing runtime qualification evidence')
        check_files(self.root, qualified['evidence_files'])
        check_files(self.root / 'code', self.plan['code'])
        check_files(self.root, self.plan['data'])
        check_coordinator_environment(self.plan)
        require(not (self.root / 'study').exists(), 'No implicit study replay')
        (self.root / 'study').mkdir()
        (self.root / 'artifacts').mkdir()
        self.deadline = Deadline(self.plan['limits']['seconds'])
        self.started, self.editor_calls, self.phases = 0, 0, []
        self.golds = read(self.root / 'hidden-golds.json')

    def infer(self, name, model, cases, *, editor=False):
        self.deadline.remaining()
        tokenizer_key = 'editor_tokenizer' if editor else 'target_tokenizer'
        if editor:
            require(self.editor_calls < 4, 'Editor call cap')
            self.editor_calls += 1
            from tokenizers import Tokenizer
            # Only selected development examples and their local results arrive here.
            # IDs/prompts are bounded host data; confirmation/heldout never enter cases.
            system = ('You are AutoProteus.\nChoose strength15 and strength19 in [0.7,1.3] for the supplied existing repair. '
                      'Return one JSON object with those two numbers and optional rationale, or {"stop":true}. '
                      'Preserve correct development answers and solve the incorrect example. '
                      'Weight statistics are descriptive, not neuron semantics. No code, paths, new coordinates or directions.')
            prompt = render_feedback(system, cases, self.golds)
            tokenizer = Tokenizer.from_file(str(Path(self.plan['tokenizers'][tokenizer_key]['path']) / 'tokenizer.json'))
            ids = tokenizer.encode(prompt, add_special_tokens=False).ids
            require(len(ids) + 4096 <= 34816, 'Editor context exceeded; no trimming')
            cases = [{'id': name, 'rendered_prompt': prompt, 'input_ids': ids, 'rng_seed': 2026110202+self.editor_calls}]
        else:
            require(self.started + len(cases) <= 36, 'Target request cap')
            self.started += len(cases)
        ledger = read(self.root / 'study/usage.json') if (self.root / 'study/usage.json').exists() else {'phases': {}}
        charged = sum(row['charged_tokens'] for key, row in ledger['phases'].items() if not key.startswith('editor-'))
        remaining = 4096 if editor else self.plan['limits']['target_generated_tokens'] - charged
        require(remaining > 0, 'No generated-token allowance left')
        tokenizer = self.plan['tokenizers'][tokenizer_key]
        payload = {'kind': 'editor' if editor else 'target', 'model': model['path'], 'model_sha256': model['sha256'],
                   'cases': cases, 'slots': 1 if editor else 2, 'output_tokens': 4096 if editor else 32768,
                   'stop_token_ids': [248044, 248046], 'request_seconds': 2700, 'remaining_tokens': remaining,
                   'tokenizer': tokenizer['path'], 'tokenizer_files': tokenizer['files']}
        request = self.root / 'study' / (name + '-request.json')
        atomic(request, payload)
        folder = self.root / 'study' / name
        self.phases.append(name)
        command = [self.plan['interpreters']['python']['path'], '-X', 'utf8', '-B', '-u', str(self.root / 'code/weight_editor_worker.py'), str(request)]
        def check(case, response, timeout):
            if editor:
                return response
            result = grade(self.plan['interpreters']['cpu_python']['path'], response['text'], self.golds[case['id']], timeout=timeout)
            require(result['status'] == 'ok', 'Independent grader infrastructure failure')
            return {'id': case['id'], **result, 'generated_tokens': response['generated_tokens'],
                    'finish_reason': response['finish_reason'], 'response_tail': response['text'][-1200:]}
        rows = inference_phase(self.root, folder, command, self.deadline, request, self.root/'study/usage.json', name, check)
        atomic(folder / 'GRADES.json', rows)
        return rows[0]['text'] if editor else rows

    def run(self):
        outcome = {'status': 'failed', 'outcome': 'infrastructure_failure'}
        try:
            cases = read(self.root / 'inputs.json')['cases']
            def make(name, chosen, existing):
                return build(self.plan, self.root/'artifacts'/name, chosen, existing, self.deadline)
            outcome = experiment(self.plan, cases, read(self.root/'weight-diagnostics.json'), self.infer, make,
                                 lambda name, value: atomic(self.root/'study'/name, value))
            completed_phases(self.root / 'study', self.phases)
        except BaseException as error:
            outcome.update(status='stopped', error=type(error).__name__ + ': ' + str(error))
            raise
        finally:
            ledger = read(self.root/'study/usage.json') if (self.root/'study/usage.json').exists() else {'phases': {}}
            generated_cases = sum(len(row['per_case']) for name, row in ledger['phases'].items() if not name.startswith('editor-'))
            complete_cases = 0
            for name in self.phases:
                if not name.startswith('editor-'):
                    payload = read(self.root/'study'/(name+'-request.json'))
                    complete_cases += sum((self.root/'study'/name/(case['id']+'.json')).exists() for case in payload['cases'])
            outcome.update(target_request_slots_reserved=self.started, target_cases_with_generated_tokens=generated_cases,
                           target_responses_completed=complete_cases, expected_worker_phases=self.phases,
                           seconds=self.plan['limits']['seconds']-self.deadline.end+self.deadline.clock(),
                           target_requests_upper_bound=36, no_4b_weight_edit=True, no_persistent_promotion=True)
            atomic(self.root / 'study/FINAL.json', outcome)
        return outcome


if __name__ == '__main__':
    require(len(sys.argv) == 3 and sys.argv[1] == '--execute', 'Explicit --execute RUN required')
    with exclusive(Path(sys.argv[2])):
        print(json.dumps(Study(sys.argv[2]).run(), indent=2))
