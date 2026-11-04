"""Validate historical target observations before reusing a reference result."""
from pathlib import Path
import json

from lora6k_state import read, sha
from weight_editor_runtime import require, usage


NATIVE_SOURCES = ('weight_editor_worker.py', 'weight_editor_native.py', 'weight_editor_owned.py',
                  'weight_editor_runtime.py', 'weight_repair_protocol.py', 'lora6k_state.py',
                  'lora6k_supervisor.py', 'windows_job.py')


def compatible_runtime(previous, current):
    for name in NATIVE_SOURCES:
        require(previous['code'][name] == current['code'][name], 'Reference runtime changed: '+name)
    for key in ('engine_files', 'target_protocol', 'target_slots'):
        require(previous[key] == current[key], 'Reference conditions changed: '+key)
    for name in ('repaired_target', 'fixed_control'):
        require(previous['models'][name]['sha256'] == current['models'][name]['sha256'], 'Reference model changed')
    require(previous['tokenizers']['target_tokenizer'] == current['tokenizers']['target_tokenizer'], 'Reference tokenizer changed')


def target_reference(folder, request_path, model, cases, tokenizer):
    """Only complete, independently graded, exact-condition target cells qualify.

    Closure is historical evidence: an old PID can since have been reused by an
    unrelated process. The caller also binds the source run's terminal inventory.
    This function never executes inference, recovers a store or modifies records.
    """
    folder, request_path = Path(folder), Path(request_path)
    payload = read(request_path)
    require(payload['kind'] == 'target' and payload['slots'] == 2 and payload['output_tokens'] == 32768
            and payload['request_seconds'] == 2700 and payload['stop_token_ids'] == [248044,248046], 'Reference protocol mismatch')
    require(payload['model_sha256'] == model['sha256'] and payload['cases'] == cases, 'Reference model/cases/seed mismatch')
    require(payload['tokenizer'] == tokenizer['path'] and payload['tokenizer_files'] == tokenizer['files'], 'Reference tokenizer mismatch')
    closed, result = read(folder/'CLOSED.json'), read(folder/'RESULT.json')
    require(closed['status'] == 'completed' and closed['owned_worker_closed'] is True and closed['returncode'] == 0
            and not closed.get('guard'), 'Reference worker closure incomplete')
    require(result['status'] == 'completed' and result['cleanup_complete'] is True and result['token'] == closed['token']
            and result['request_sha256'] == sha(request_path), 'Reference result binding mismatch')
    require(set(result['responses']) == {c['id'] for c in cases} and len(result['responses']) == len(cases), 'Reference response coverage mismatch')
    measured = usage(folder, {'nonce': closed['token'], 'request_sha256': sha(request_path)})
    require(measured['measurement_complete'] and measured['charged_tokens'] == result['generated_tokens'], 'Reference usage incomplete')
    grades = read(folder/'GRADES.json')
    require(len(grades) == len(cases) and {r['id'] for r in grades} == {c['id'] for c in cases}, 'Reference grade coverage mismatch')
    journal = {}
    for line in (folder/'tokens.jsonl').read_text().splitlines():
        row = json.loads(line); journal.setdefault(row['case'], []).append(row['token_id'])
    require(set(journal) == {c['id'] for c in cases}, 'Reference journal coverage mismatch')
    for case in cases:
        response = read(folder/(case['id']+'.json'))
        grade = next(r for r in grades if r['id'] == case['id'])
        require(grade['status'] == 'ok' and type(grade['correct']) is bool, 'Reference not independently graded')
        require(response['tokens'] == journal[case['id']] and response['generated_tokens'] == grade['generated_tokens'] == len(response['tokens']), 'Reference token count mismatch')
        require(response['rng_seed'] == case['rng_seed'] and response['input_tokens'] == len(case['input_ids']), 'Reference input/seed mismatch')
        require(response['context_per_slot'] >= 34816 and response['slots'] == 2, 'Reference context/slots mismatch')
        finish = 'eos' if response['tokens'][-1] in payload['stop_token_ids'] else 'length'
        require(response['finish_reason'] == grade['finish_reason'] == finish, 'Reference finish mismatch')
        require(finish == 'eos' or len(response['tokens']) == 32768, 'Reference cutoff mismatch')
    return {'rows': grades, 'usage': measured, 'request_sha256': sha(request_path),
            'files': {p.name:sha(p) for p in folder.iterdir() if p.is_file()},
            'cases': len(cases), 'seconds': closed['seconds'], 'historical_closure_verified': True}
