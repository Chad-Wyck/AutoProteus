"""Prepare an opt-in local weight-editor follow-up. No download or GPU launcher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
import unicodedata

from lora6k_state import atomic, identity, read, sha
from weight_editor_drift import analyze
from weight_editor_runtime import check_files, require
from weight_repair_protocol import PROTOCOL, extract_answer

HERE = Path(__file__).resolve().parent
MODULES = ['weight_editor_prepare.py', 'weight_editor_runtime.py', 'weight_editor_owned.py',
           'weight_editor_worker.py', 'weight_editor_native.py', 'weight_editor_drift.py',
           'weight_editor_artifacts.py', 'weight_editor_study.py',
           'weight_editor_format.py',
           'weight_editor_reuse.py',
           'lora6k_state.py', 'lora6k_supervisor.py', 'weight_repair_protocol.py']


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).lower().split())


def select_data(train, benchmark, previous, old_rows, *, seed=2026110202):
    """Fixed bounded calibration pool and fresh local heldout; no scores used."""
    require(len(benchmark) == 500 and len({row['id'] for row in benchmark}) == 500, 'Expected full pinned MATH-500')
    benchmark_text = {normalized(row['problem']) for row in benchmark}
    train_unique = {}
    for index, row in enumerate(train):
        key = normalized(row['problem'])
        if key not in benchmark_text and key not in previous and index not in old_rows and extract_answer(row['solution']):
            train_unique.setdefault(key, (index, row))
    pool = random.Random(seed).sample(list(train_unique.values()), 8)
    eligible = [row for row in sorted(benchmark, key=lambda row: row['id']) if normalized(row['problem']) not in previous]
    require(len(eligible) >= 6, 'Insufficient unused local heldout')
    heldout = random.Random(seed+1).sample(eligible, 6)
    return pool, heldout


def weight_diagnostics(original, repaired, tensors):
    # CPU data inspection only. No torch, transformers, native inference or CUDA.
    import numpy as np
    from gguf import GGUFReader
    a = {t.name: t for t in GGUFReader(original).tensors}
    b = {t.name: t for t in GGUFReader(repaired).tensors}
    result = []
    for name in tensors:
        x, y = a[name].data, b[name].data
        require(x.dtype == y.dtype == np.float32 and x.shape == y.shape and x.ndim == 2, 'Unexpected diagnostic tensor')
        mask = x.view(np.uint32) != y.view(np.uint32)
        delta = y.astype(np.float64)-x.astype(np.float64)
        columns = np.flatnonzero(mask.any(axis=0))
        groups = []
        for number, group in enumerate(np.array_split(columns, 4)):
            groups.append({'group': number, 'storage_columns': group.tolist(), 'changed_entries': int(mask[:, group].sum()),
                           'delta_l2': float(np.linalg.norm(delta[:, group])),
                           'maximum_absolute_delta': float(np.abs(delta[:, group]).max()) if len(group) else 0})
        result.append({'tensor': name, 'stored_shape': list(x.shape), 'changed_entries': int(mask.sum()),
                       'original_l2': float(np.linalg.norm(x.astype(np.float64))), 'delta_l2': float(np.linalg.norm(delta)),
                       'maximum_absolute_delta': float(np.abs(delta).max()), 'storage_column_groups': groups})
    return {'scope': 'Descriptive weight/delta statistics; no claimed neuron semantics or direction discovery',
            'matrices': result, 'cpu_only': True}


def prepare(project, prior, assets, output):
    project, prior, assets, output = [Path(p).resolve() for p in (project, prior, assets, output)]
    require(output.is_relative_to(project / '.data') and output != project / '.data', 'Output must be inside project .data')
    require(not output.exists(), 'Never overwrite existing experiment evidence')
    old_plan, old_design = read(prior / 'pilot-run-plan.json'), read(prior / 'pilot-design.json')
    fixed_control = read(prior / 'candidates/control/MANIFEST.json')
    require(sha(fixed_control['model']) == fixed_control['sha256'], 'Fixed numeric control changed')
    require(identity(old_plan) == (prior / 'pilot-run-plan.sha256').read_text().strip(), 'Prior frozen plan changed')
    require(identity(old_design) == old_plan['design_sha256'], 'Prior design changed')
    require(read(prior / 'CONTINUATION.json')['status'] == 'completed', 'Prior work must be closed')
    for key, field in [('editor_model', 'editor_model_sha256'), ('original_target', 'target_original_sha256'), ('repaired_target', 'target_repaired_sha256')]:
        require(sha(old_design[key]) == old_design[field], 'Pinned model changed: ' + key)
    require(sha(assets / 'gpu-readiness-001/math-train.parquet') == old_design['training_source_sha256'], 'Training data changed')
    benchmark_path = assets / 'acquisition-001/assets/dataset/math500.jsonl'
    acquired = read(assets / 'acquisition-001/asset-lock.json')
    require(sha(benchmark_path) == acquired['dataset/math500.jsonl']['sha256'], 'Benchmark changed')
    check_files(old_plan['engine'], old_plan['engine_files'])
    from tokenizers import Tokenizer
    import pyarrow.parquet as pq
    train = pq.read_table(assets / 'gpu-readiness-001/math-train.parquet').to_pylist()
    benchmark = [json.loads(line) for line in benchmark_path.read_text(encoding='utf8').splitlines()]
    benchmark = [{**row, 'id': row['unique_id']} for row in benchmark]
    old_inputs = read(prior / 'target-inputs.json')['cases']
    earlier = read(assets / 'gguf-survival-003/inputs.json')['cases']
    previous = set()
    for row in old_inputs + earlier:
        text = row['rendered_prompt'].split('<|im_start|>user\n', 1)[1].split('<|im_end|>', 1)[0]
        previous.add(normalized(text.removesuffix('\n' + PROTOCOL['instruction'])))
    old_rows = {4640, 543} | {row['row_index'] for row in old_inputs if 'row_index' in row}
    pool, heldout = select_data(train, benchmark, previous, old_rows)
    tokenizer = Tokenizer.from_file(str(Path(old_design['target_tokenizer']) / 'tokenizer.json'))
    cases, golds = [], {}
    for split, values in [('calibration', pool), ('heldout', list(enumerate(heldout)))]:
        for position, (index, row) in enumerate(values):
            name = split + '-' + str(position)
            prompt = '<|im_start|>user\n' + row['problem'] + '\n' + PROTOCOL['instruction'] + '<|im_end|>\n<|im_start|>assistant\n<think>\n'
            ids = tokenizer.encode(prompt, add_special_tokens=False).ids
            require(len(ids) + 32768 <= 34816, 'Input exceeds frozen context; no trimming')
            cases.append({'id': name, 'split': split, 'source_id': row.get('id', index), 'problem_sha256': identity(normalized(row['problem'])),
                          'rendered_prompt': prompt, 'input_ids': ids,
                          'rng_seed': int.from_bytes(hashlib.sha256(('editor-v2:' + name).encode()).digest()[:4], 'little')})
            golds[name] = extract_answer(row['solution']) if split == 'calibration' else row['answer']
    source = read(assets / 'gguf-survival-001/source-receipt.json')
    vendor = Path(source['path']) / 'gguf-py'
    vendor_files = {str(p.relative_to(vendor)): sha(p) for p in vendor.rglob('*.py')}
    check_files(vendor, vendor_files)
    sys.path.insert(0, str(vendor))
    diagnostics = weight_diagnostics(old_design['original_target'], old_design['repaired_target'], old_design['operators']['tensors'])
    require('torch' not in sys.modules and 'transformers' not in sys.modules, 'Unexpected heavyweight/GPU-capable ML import')
    output.mkdir()
    (output / 'code').mkdir()
    for name in MODULES:
        shutil.copyfile(HERE / name, output / 'code' / name)
    shutil.copyfile(project / 'controller/windows_job.py', output / 'code/windows_job.py')
    atomic(output / 'inputs.json', {'cases': cases})
    atomic(output / 'hidden-golds.json', golds)
    atomic(output / 'weight-diagnostics.json', diagnostics)
    drift = analyze(read(prior / 'throughput4/RESULT.json'))
    atomic(output / 'four-slot-offline-analysis.json', drift)
    tokenizer_files = {}
    for key in ('target_tokenizer', 'editor_tokenizer'):
        base = Path(old_design[key])
        tokenizer_files[key] = {'path': str(base), 'files': {p.name: sha(p) for p in base.iterdir() if p.suffix in ('.json', '.jinja', '.txt') and p.is_file()}}
    from importlib.metadata import version
    plan = {'schema': 2, 'scope': 'Unchanged local 4B Q8 chooses two strengths for the already repaired 0.8B F32',
        'code': {p.name: sha(p) for p in (output / 'code').iterdir()},
        'data': {name: sha(output / name) for name in ('inputs.json', 'hidden-golds.json', 'weight-diagnostics.json', 'four-slot-offline-analysis.json')},
        'prior_plan_sha256': identity(old_plan), 'prior_result_sha256': sha(prior / 'COMBINED-CLOSED-AUDIT-v2.json'),
        'models': {key: {'path': old_design[key], 'sha256': old_design[field]} for key, field in
                   [('editor_model', 'editor_model_sha256'), ('original_target', 'target_original_sha256'), ('repaired_target', 'target_repaired_sha256')]},
        'engine': old_plan['engine'], 'engine_files': old_plan['engine_files'], 'tokenizers': tokenizer_files,
        'interpreters': {key: {'path': old_plan[key], 'sha256': sha(old_plan[key])} for key in ('python', 'cpu_python')},
        'preparation_environment': {'python_version': sys.version, 'packages': {name: version(name) for name in ('numpy', 'tokenizers', 'pyarrow')}},
        'cpu_vendor_sources': {'path': str(vendor), 'files': vendor_files},
        'dataset_sources': {'train_sha256': old_design['training_source_sha256'], 'benchmark_sha256': sha(benchmark_path),
                           'exclude_prior_declared_inputs': True, 'exclude_exact_normalized_train_benchmark_overlap': True},
        'target_protocol': PROTOCOL, 'target_slots': 2, 'editor_slots': 1,
        'editing_interface': {'strength15': [0.7, 1.3], 'strength19': [0.7, 1.3], 'optional_rationale': True,
                              'operation': old_design['operators'], 'groups_are_diagnostics_only': True,
                              'no_new_coordinates_or_directions': True},
        'calibration': {'cases': 8, 'selection_seed': 2026110202, 'split': 'First two correct and two incorrect IDs in lexical order; first pair development, second pair hidden confirmation',
                        'stop_without_resampling_if_insufficient': True, 'baseline_stratified_not_population_accuracy': True},
        'gates': {'development': 'Retain baseline correct case and add the incorrect case',
                  'confirmation': 'Independent confirmation-only correctness gain, with nonempty retention; no combined-development carryover',
                  'heldout': '6 fresh local cases; compare baseline, selected and fixed control, and report correctness/preservation/efficiency separately'},
        'editor_feedback': ['Selected development questions and golds', 'Development checked outcomes and bounded response excerpts', 'Weight diagnostics'],
        'hidden_from_editor': ['Unused calibration questions/outcomes', 'Confirmation questions/golds/outcomes', 'Heldout questions/golds/outcomes'],
        'limits': {'seconds': 14400, 'target_starts': 36, 'target_generated_tokens': 900000, 'editor_calls': 4,
                   'distinct_model_artifacts': 2, 'target_output_tokens': 32768, 'editor_output_tokens': 4096,
                   'request_seconds': 2700, 'reservation_block': 64, 'emergency_cleanup_seconds_outside_work_deadline': 25},
        'runtime_qualification': 'New supervisor/worker integration still requires an actual authorized GPU preflight; old two-slot numerical evidence is retained separately',
        'execution': {'gpu_authorized': False, 'downloads': False, 'paid_calls': False, 'training': False,
                      'four_slots_scored': False, 'persistent_promotion': False, '4b_weight_edit': False,
                      'self_edit': False, 'commit_or_push': False, 'automatic_retries': False}}
    plan['models']['fixed_control'] = {'path': fixed_control['model'], 'sha256': fixed_control['sha256']}
    atomic(output / 'manifest.json', plan)
    (output / 'manifest.sha256').write_text(identity(plan) + '\n', encoding='ascii')
    return verify(output)


def verify(output):
    output = Path(output)
    plan = read(output / 'manifest.json')
    require(identity(plan) == (output / 'manifest.sha256').read_text().strip(), 'Frozen manifest mismatch')
    check_files(output / 'code', plan['code'])
    check_files(output, plan['data'])
    cases = read(output / 'inputs.json')['cases']
    require(len(cases) == len({row['id'] for row in cases}) == 14, 'Fixed input coverage changed')
    require(sum(row['split'] == 'calibration' for row in cases) == 8 and sum(row['split'] == 'heldout' for row in cases) == 6, 'Wrong split sizes')
    require(plan['target_slots'] == 2 and plan['execution']['gpu_authorized'] is False
            and plan['execution']['four_slots_scored'] is False, 'Execution policy changed')
    for info in plan['tokenizers'].values():
        check_files(info['path'], info['files'])
    require(not (output / 'GPU-AUTHORIZATION.json').exists(), 'Preparation must not authorize execution')
    return {'status': 'prepared_offline', 'manifest_sha256': identity(plan), 'cases': 14,
            'gpu_started': False, 'hardware_qualification_pending': True, 'automatic_execution': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=str(HERE.parent))
    parser.add_argument('--prior', required=True)
    parser.add_argument('--assets', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prepare(args.project, args.prior, args.assets, args.output)
    atomic(Path(args.output) / 'PREPARED.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
