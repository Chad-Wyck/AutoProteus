"""Prepare and inspect the optional p50c reproduction. No downloads or GPU entry point."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lora6k_state import atomic, identity, inside, read, sha
from weight_repair_artifacts import TensorFile, rebuild_sparse, text_mapping
from weight_repair_protocol import PROTOCOL, NUMERICAL_CONTROLS, GRADER_CASES, check_grader, offline_environment, validate_protocol
from weight_repair_state import GUARDS, Receipts, summarize

ROOT = HERE.parent
REVISION = '4d09ba6d6a7e891dd8063974dfe81b3d78e3494f'
MODEL_REVISION = '2fc06364715b967f1860aea9cf38778875588b17'
TARGETS = {f'model.language_model.layers.{layer}.mlp.down_proj.weight': {
    'shape': [1024, 3584], 'base_sha256': base, 'edited_sha256': edited}
    for layer, base, edited in (
        (15, 'ef60d2c687bab19464dca9c8bfd7777e46ad226df0c9e25643b0bab04b5a1cca',
             '82e2d733ea64feaeb4af93a1e065641d3df98b494a8b7576ef2f52e90fe2ee53'),
        (19, '638eedeb701b94aa861f4438e615c07ec6c60ee703db1bfee2de577bb6498c3e',
             '8ef3c61bc36af113ad58e89dbb0a4a14dcba5a45cb750c15ab515c82ddd12eb2'))}
MODULES = ('weight_repair.py', 'weight_repair_artifacts.py', 'weight_repair_protocol.py',
           'weight_repair_state.py', 'weight_repair_acquire.py', 'lora6k_state.py')
PACKAGES = ('torch', 'transformers', 'numpy', 'safetensors', 'math-verify',
            'latex2sympy2_extended', 'antlr4-python3-runtime', 'sympy')


def assets():
    result = {}
    upstream = ('README.md', 'runs/p50c/final_answer.md', 'runs/p50c/edit/manifest.json',
        'runs/p50c/edit/edit.npz', 'code/apply_edit.py', 'code/st_numpy.py', 'code/evaluate.py',
        'code/profiles.py', 'code/mathqa.py', 'eval/unedited/merged.json', 'eval/p50c/merged.json',
        'base_model/Qwen3.5-0.8B-text/config.json')
    for name in upstream:
        result['upstream/' + name] = {'url': f'https://raw.githubusercontent.com/RikiyaT/lm_understand-logs/{REVISION}/exp8_math/{name}',
                                     'revision': REVISION, 'sha256': None, 'bytes': None}
    for name in ('model.safetensors', 'model.safetensors.index.json', 'config.json', 'tokenizer.json',
                 'tokenizer_config.json', 'chat_template.jinja', 'merges.txt', 'vocab.json', 'LICENSE', 'README.md'):
        remote = 'model.safetensors-00001-of-00001.safetensors' if name == 'model.safetensors' else name
        result['base/' + name] = {'url': f'https://huggingface.co/Qwen/Qwen3.5-0.8B/resolve/{MODEL_REVISION}/{remote}',
                                 'revision': MODEL_REVISION, 'sha256': None, 'bytes': None}
    result['base/generation_config.json'] = {'url': f'https://raw.githubusercontent.com/RikiyaT/lm_understand-logs/{REVISION}/exp8_math/base_model/Qwen3.5-0.8B-text/generation_config.json',
                                            'revision': REVISION, 'sha256': None, 'bytes': None}
    result['upstream/base_model/Qwen3.5-0.8B-text/tokenizer_config.json'] = {
        'url': f'https://raw.githubusercontent.com/RikiyaT/lm_understand-logs/{REVISION}/exp8_math/base_model/Qwen3.5-0.8B-text/tokenizer_config.json',
        'revision': REVISION, 'sha256': None, 'bytes': None}
    result['dataset/math500.jsonl'] = {'repository': 'HuggingFaceH4/MATH-500', 'revision': None,
        'sha256': None, 'bytes': None, 'rows': 500, 'status': 'resolve immutable dataset revision before acquisition'}
    return result


def metadata(python):
    """Read distribution metadata/source bytes only, never import an ML package."""
    code = '''import hashlib,json,sys
from importlib import metadata
out={}
for name in PACKAGES:
    try: out[name]=metadata.version(name)
    except metadata.PackageNotFoundError: out[name]=None
sources={}
try:
    d=metadata.distribution('transformers')
    for name in ('transformers/models/qwen3_5/modeling_qwen3_5.py', 'transformers/generation/logits_process.py'):
        p=d.locate_file(name)
        sources[name]=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
except metadata.PackageNotFoundError: pass
print(json.dumps({'packages':out,'python':sys.version,'sources':sources,
                  'ml_imports':[n for n in ('torch','transformers','numpy') if n in sys.modules]}))
'''.replace('PACKAGES', repr(PACKAGES))
    value = json.loads(subprocess.check_output([str(python), '-I', '-X', 'utf8', '-c', code],
        text=True, encoding='utf-8', env=offline_environment(), timeout=30))
    if value['ml_imports']: raise ValueError('Metadata collection imported an ML package')
    return {'path': str(Path(python).resolve()), 'sha256': sha(python), **value}


def schedule(seed=20261102):
    selected = random.Random(seed).sample(range(500), 16)
    slots = []
    for index, rank in enumerate(selected):
        rng = int.from_bytes(hashlib.sha256(f'p50c:pilot:{seed}:{rank}:0'.encode()).digest()[:4], 'little')
        for arm in (('base', 'edited') if index % 2 == 0 else ('edited', 'base')):
            slots.append({'id': f'pilot-{index:02d}-{arm}', 'arm': arm, 'problem_rank': rank,
                          'sample': 0, 'rng_seed': rng})
    return {'selection_seed': seed, 'selection_rule': 'Ranks in lexicographically sorted unique MATH-500 IDs',
            'selected_ranks': selected, 'dataset_ids_bound': False, 'slots': slots}


def bind_dataset(rows, selection):
    if (len(rows) != 500 or any(not isinstance(r.get('id'), str) or not r['id'] for r in rows)
            or len({r['id'] for r in rows}) != 500
            or any(not isinstance(r.get(k), str) for r in rows for k in ('problem', 'answer'))):
        raise ValueError('Expected all 500 unique benchmark rows')
    ordered = sorted(rows, key=lambda r: r['id'])
    return [{**slot, 'problem_id': ordered[slot['problem_rank']]['id'],
             'problem_sha256': identity(ordered[slot['problem_rank']])} for slot in selection['slots']]


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True, encoding='utf-8').rstrip('\r\n')


def locked_assets(lock):
    """Accept already reviewed local checksums, never fetch or invent them."""
    expected = assets()
    if set(lock) != set(expected): raise ValueError('Asset lock has a different file set')
    for name, spec in lock.items():
        original = expected[name]
        if (not re.fullmatch(r'[0-9a-f]{64}', spec.get('sha256', ''))
                or type(spec.get('bytes')) is not int or spec['bytes'] <= 0
                or not re.fullmatch(r'[0-9a-f]{40}', spec.get('revision', ''))
                or any(spec.get(k) != original[k] for k in ('url', 'repository') if k in original)
                or (original.get('revision') and spec['revision'] != original['revision'])):
            raise ValueError('Wrong revision, length, URL or hash in asset lock: ' + name)
    return lock


def prepare(output, *, root=ROOT, python=sys.executable, asset_lock=None, asset_directory=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.relative_to(root / '.data')
    if output.exists(): raise ValueError('Use a new run directory; existing evidence is immutable')
    sources = {name: HERE / name for name in MODULES}
    sources['windows_job.py'] = ROOT / 'controller/windows_job.py'
    sources['reproduction-plan.md'] = ROOT / 'evaluations/weight-space-repair-reproduction-plan-2026-11-02.md'
    environment = metadata(python)
    asset_records = locked_assets(read(asset_lock)) if asset_lock else assets()
    if asset_directory:
        if not asset_lock: raise ValueError('A shared asset directory requires a reviewed lock')
        asset_directory = Path(asset_directory).resolve()
        asset_directory.relative_to(root / '.data')
        if not asset_directory.is_dir(): raise ValueError('Asset directory missing')
    state = git(root, 'status', '--porcelain', '--untracked-files=normal')
    dirty = {}
    for line in state.splitlines():
        name = line[3:]
        path = root / name
        if path.is_file() and name.endswith('.py') and name.startswith(('controller/', 'evaluations/')):
            dirty[name] = sha(path)
    output.mkdir(parents=True); (output / 'code').mkdir()
    for name, path in sources.items(): shutil.copyfile(path, output / 'code' / name)
    plan = {'schema': 1, 'experiment': 'published-p50c-reconstruction',
        'project_root': str(root), 'git': {'branch': git(root, 'branch', '--show-current'),
            'head': git(root, 'rev-parse', 'HEAD'), 'dirty_code_sha256': dirty},
        'code': {name: sha(output / 'code' / name) for name in sources},
        'original_research': 'https://rikiyat.github.io/blog/weight-space-programming/',
        'upstream_revision': REVISION, 'model': 'Qwen/Qwen3.5-0.8B', 'model_revision': MODEL_REVISION,
        'assets': asset_records, 'asset_lock_sha256': sha(asset_lock) if asset_lock else None,
        'asset_directory': str(asset_directory) if asset_directory else None,
        'targets': TARGETS, 'changed_entries': 130188,
        'touched_entries': 131072, 'changed_columns_per_tensor': 64,
        'protocol': PROTOCOL, 'selection': schedule(), 'guards': GUARDS,
        'metadata_environment': environment, 'dependencies_locked_for_inference': False,
        'required_grader_packages': {'math-verify': '0.9.0', 'latex2sympy2_extended': '1.11.0',
                                    'antlr4-python3-runtime': '4.13.2'},
        'numerical_controls_required': list(NUMERICAL_CONTROLS),
        'grader_cases': list(GRADER_CASES),
        'numerical_tolerance': {'atol': 1e-5, 'rtol': 1e-4, 'dtype': 'float32'},
        'runtime': {'candidate': 'native Windows Transformers FP32', 'trust_remote_code': False,
            'batch_size': 1, 'cache': True, 'output_last_logits_only': True,
            'attention': 'must qualify SDPA/eager and linear-attention fallback',
            'sampler': 'pure reference only; pinned vLLM ordering parity pending'},
        'execution': {'downloads_authorized': False, 'gpu_authorized': False,
            'editing_agent_authorized': False, 'scheduler_created': False,
            'live_backend_implemented': False, 'automatic_phase_escalation': False},
        'phase_limits': {'readiness': 7200, 'pilot': 28800, 'full_replication': None},
        'scope': 'Offline preparation only. Missing assets and hardware checks are blockers, never passed controls.'}
    atomic(output / 'manifest.json', plan)
    (output / 'manifest.sha256').write_text(identity(plan) + '\n', encoding='ascii')
    result = verify(output)
    atomic(output / 'PREPARED.json', result)
    return result


def checked_plan(run):
    run = Path(run).resolve(); plan = read(run / 'manifest.json')
    if identity(plan) != (run / 'manifest.sha256').read_text().strip(): raise ValueError('Frozen manifest changed')
    for name, digest in plan['code'].items():
        if sha(inside(run / 'code', name)) != digest: raise ValueError('Frozen source changed: ' + name)
    validate_protocol(plan['protocol'])
    if (plan['targets'] != TARGETS or plan['model_revision'] != MODEL_REVISION or plan['upstream_revision'] != REVISION
            or plan['selection'] != schedule(plan['selection']['selection_seed']) or plan['guards'] != GUARDS):
        raise ValueError('Pinned experiment identity changed')
    if plan.get('asset_lock_sha256'):
        locked_assets(plan['assets'])
    elif plan['assets'] != assets():
        raise ValueError('Asset identities changed without a reviewed lock')
    return plan


def verify(run):
    run = Path(run).resolve(); plan = checked_plan(run)
    missing, unpinned, present = [], [], []
    for name, spec in plan['assets'].items():
        path = inside(Path(plan.get('asset_directory') or run / 'assets'), name)
        if not spec.get('sha256') or not spec.get('revision') or type(spec.get('bytes')) is not int:
            unpinned.append(name)
        if not path.is_file():
            missing.append(name); continue
        if name in unpinned: raise ValueError('Unpinned asset appeared; prepare a newly reviewed asset lock')
        if path.stat().st_size != spec['bytes'] or sha(path) != spec['sha256']:
            raise ValueError('Wrong or incomplete asset: ' + name)
        if path.suffix == '.safetensors': TensorFile(path)
        present.append(name)
    environment = plan['metadata_environment']
    if sha(environment['path']) != environment['sha256'] or metadata(environment['path']) != environment:
        raise ValueError('Metadata interpreter/dependencies changed')
    return {'status': 'prepared_offline_not_execution_ready', 'manifest_sha256': identity(plan),
        'frozen_sources_verified': True, 'missing_assets': missing, 'unpinned_assets': unpinned,
        'present_assets': present, 'scheduled_pilot_requests': len(plan['selection']['slots']),
        'gpu_accessed': False, 'model_loaded': False, 'downloads_started': bool(present),
        'blockers': (['Acquire and hash pinned assets under new authorization'] if missing or unpinned else []) + [
            'Freeze resolved dataset IDs and isolated inference dependency lock',
            'Run exact checkpoint and text/tied-head mapping audits',
            'Qualify actual math equivalence grader, sampler parity and FP32 numerical controls',
            'Implement/qualify live inference backend and external five-second resource supervisor']}


def rebuild(run):
    # This command cannot acquire assets, relax identity checks or import ML.
    status = verify(run)
    if status['missing_assets'] or status['unpinned_assets']:
        raise ValueError('Rebuild blocked: pinned assets have not been acquired; no download attempted')
    run = Path(run); plan = read(run / 'manifest.json')
    asset_root = Path(plan.get('asset_directory') or run / 'assets')
    result = rebuild_sparse(asset_root / 'base/model.safetensors', asset_root / 'upstream/runs/p50c/edit/edit.npz',
        run / 'artifacts/p50c.safetensors', plan['targets'], changed_entries=plan['changed_entries'],
        columns=plan['changed_columns_per_tensor'], touched_entries=plan['touched_entries'])
    receipt = {**result, 'manifest_sha256': identity(plan),
        'base_file_sha256': plan['assets']['base/model.safetensors']['sha256'],
        'artifact': 'artifacts/p50c.safetensors', 'artifact_sha256': sha(run / 'artifacts/p50c.safetensors'),
        'gpu_accessed': False, 'model_loaded': False}
    atomic(run / 'REBUILT.json', receipt)
    return receipt


def report(run):
    run = Path(run); plan = checked_plan(run)
    records = Receipts(run, identity(plan), plan['selection']['slots']).records()
    rebuilt = read(run / 'REBUILT.json') if (run / 'REBUILT.json').exists() else None
    if rebuilt and (rebuilt.get('manifest_sha256') != identity(plan)
            or sha(inside(run, rebuilt['artifact'])) != rebuilt.get('artifact_sha256')
            or rebuilt.get('changed_entries') != 130188
            or set(rebuilt.get('changed_tensors', [])) != set(TARGETS)):
        raise ValueError('Reconstruction receipt or artifact changed')
    return {'manifest_sha256': identity(plan), 'status': 'no_live_observations' if not records else 'recorded_observations',
        **summarize(plan['selection']['slots'], records), 'exact_patch_reproduced': bool(rebuilt),
        'hardware_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--output', required=True)
    p.add_argument('--metadata-python', default=sys.executable)
    p.add_argument('--asset-lock', help='Optional reviewed local immutable asset metadata; never downloads files')
    p.add_argument('--asset-directory', help='Read verified assets in this private directory without copying weights')
    for name in ('verify', 'rebuild', 'report', 'check-grader', 'acquire', 'preflight', 'run', 'resume'):
        p = commands.add_parser(name); p.add_argument('--input', required=True)
    args = parser.parse_args()
    if args.command == 'prepare': value = prepare(args.output, python=args.metadata_python,
        asset_lock=args.asset_lock, asset_directory=args.asset_directory)
    elif args.command == 'verify': value = verify(args.input)
    elif args.command == 'report': value = report(args.input)
    elif args.command == 'rebuild': value = rebuild(args.input)
    elif args.command == 'check-grader':
        verify(args.input)
        environment = read(Path(args.input) / 'manifest.json')['metadata_environment']
        value = check_grader(environment['path'], environment['packages'])
    else:
        parser.error('Execution hold: acquisition/live operations are not implemented or authorized in this offline preparation. No work started.')
    print(json.dumps(value, indent=2, allow_nan=False))
    if args.command == 'check-grader' and not value['passed']: raise SystemExit(2)


if __name__ == '__main__': main()
