"""Prepare/inspect the local-Qwen 6K pilot. Training requires an explicit start command."""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lora6k_state import atomic, checked_rows, identity, inside, read, sha

PACKAGES = ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate', 'safetensors')
MODULES = ('lora6k.py', 'lora6k_state.py', 'lora6k_worker.py', 'lora6k_supervisor.py')


def offline():
    return {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
        'TOKENIZERS_PARALLELISM': 'false', 'WANDB_DISABLED': 'true', 'PYTHONDONTWRITEBYTECODE': '1',
        'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2'}


def versions(python):
    # Metadata only: no torch/transformers imports, GPU checks or network requests.
    code = 'import json;from importlib.metadata import version;print(json.dumps({p:version(p) for p in ' + repr(PACKAGES) + '}))'
    return json.loads(subprocess.check_output([str(python), '-X', 'utf8', '-c', code], text=True, env=offline(), timeout=30))


def verify(run, *, full_checkpoint=False):
    run = Path(run).resolve(); plan = read(run / 'run-plan.json')
    if identity(plan) != (run / 'run-plan.sha256').read_text().strip(): raise ValueError('Run plan changed')
    for name, digest in plan['code'].items():
        if sha(inside(run / 'code', name)) != digest: raise ValueError('Frozen runner/helper changed: ' + name)
    root = Path(plan['project_root']); pilot_path = inside(root, plan['pilot_path'])
    if sha(pilot_path) != plan['pilot_sha256'] or read(pilot_path) != plan['pilot']: raise ValueError('Pilot plan changed')
    pilot = plan['pilot']; dataset = inside(root, plan['dataset'])
    rows = checked_rows(dataset, pilot)
    if pilot.get('max_epochs') != 1 or pilot['configuration'].get('max_sequence_tokens') != 6144:
        raise ValueError('This runner permits the reviewed one-epoch 6K pilot only')
    lock_path = inside(root, pilot['model']['checkpoint_lock'])
    if sha(lock_path) != pilot['model']['checkpoint_lock_sha256']: raise ValueError('Checkpoint lock changed')
    lock = read(lock_path); checkpoint = Path(lock['checkpoint']).resolve()
    if lock.get('trust_remote_code') is not False: raise ValueError('Remote checkpoint code is forbidden')
    for name, receipt in lock['files'].items():
        path = inside(checkpoint, name)
        if not path.is_file() or path.stat().st_size != receipt['bytes']: raise ValueError('Base checkpoint asset changed: ' + name)
        if full_checkpoint and sha(path) != receipt['sha256']: raise ValueError('Base checkpoint checksum changed: ' + name)
    evaluation = inside(root, plan['evaluation'])
    if sha(evaluation / 'manifest.json') != pilot['evaluation_manifest_sha256']: raise ValueError('Evaluation manifest changed')
    for name, digest in read(evaluation / 'manifest.json')['files'].items():
        if sha(inside(evaluation, name)) != digest: raise ValueError('Evaluation input changed: ' + name)
    study_plan = read(evaluation / 'base-study/plan.json')
    calibration = read(evaluation / 'manifest.json')['calibration']
    if sha(calibration['path']) != calibration['sha256']: raise ValueError('VM calibration evidence changed')
    for name, digest in study_plan['trusted_sha256'].items():
        if sha(inside(root, name)) != digest: raise ValueError('Evaluation runner changed; requalify before training: ' + name)
    if sha(plan['python']) != plan['python_sha256'] or versions(plan['python']) != plan['packages']:
        raise ValueError('Training interpreter/packages changed')
    if shutil.disk_usage(run).free < plan['minimum_free_disk_bytes']:
        raise ValueError('Insufficient disk headroom for transactional checkpoints')
    return plan, rows


def prepare(args):
    root = Path(args.project_root).resolve(); pilot_path = Path(args.pilot).resolve()
    pilot_path.relative_to(root / '.data')
    output = Path(args.output).resolve(); output.relative_to(root / '.data')
    if output.exists(): raise ValueError('Prepare into a new directory; existing runs are preserved')
    pilot = read(pilot_path); dataset = pilot_path.parent / 'dataset'
    checked_rows(dataset, pilot)
    if pilot['max_epochs'] != 1: raise ValueError('Only the frozen one-epoch pilot is supported')
    python = Path(args.python).resolve()
    previous = read(root / '.data/qwen-workflow-20261021/training/20261021T192833Z/plan.json')
    packages = versions(python)
    if packages != previous['packages']: raise ValueError('Training packages differ from the successful 6K probe')
    sources = {name: HERE / name for name in MODULES}
    sources.update({name: root / '.data/qwen-workflow-20261021' / name
        for name in ('sdpa_compat.py', 'checkpoint_offload.py', 'practical_math.py')})
    sources.update({name: root / '.data/lora-context-20261029/backward-chunked-001/source' / name
        for name in ('chunked_loss.py', 'chunked_math_control.py')})
    sources['windows_job.py'] = root / 'controller/windows_job.py'
    output.mkdir(parents=True); (output / 'code').mkdir()
    for name, source in sources.items(): shutil.copyfile(source, output / 'code' / name)
    plan = {'schema': 1, 'project_root': str(root), 'pilot_path': pilot_path.relative_to(root).as_posix(),
        'pilot_sha256': sha(pilot_path), 'pilot': pilot, 'dataset': dataset.relative_to(root).as_posix(),
        'evaluation': (pilot_path.parent / pilot['evaluation_directory']).relative_to(root).as_posix(),
        'python': str(python), 'python_sha256': sha(python), 'packages': packages,
        'code': {name: sha(output / 'code' / name) for name in sources}, 'minimum_free_disk_bytes': 3 * 1024**3,
        'training_started': False, 'automatic_generation': False,
        'optimizer': {'name': 'AdamW', 'betas': [.9, .999], 'eps': 1e-8, 'weight_decay': .01},
        'adapter': {'parameters': 21639168, 'gradient_tensors': 496, 'layers': list(range(32))},
        'checkpoints': {'interval_updates': 1, 'retained_commits': 2, 'save_rng_optimizer_cursor': True},
        'supervision': 'Original local-Qwen completion labels only; no padding/truncation/oversampling/relabeling.',
        'budget_scope': 'Four-hour cumulative supervised worker time across resumes, including loading/validation/checkpoints. '
            'Offline input checks occur before worker launch; preparation and paused downtime do not consume it.'}
    atomic(output / 'run-plan.json', plan)
    (output / 'run-plan.sha256').write_text(identity(plan), encoding='ascii')
    verify(output)
    atomic(output / 'PREPARED.json', {'status': 'prepared_not_started', 'plan_sha256': identity(plan),
        'training_started': False, 'gpu_accessed': False, 'model_loaded': False,
        'train_examples': 93, 'validation_examples': 27})
    print(json.dumps({'status': 'prepared_not_started', 'output': str(output), 'training_started': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--project-root', default=str(HERE.parent))
    p.add_argument('--pilot', required=True); p.add_argument('--python', required=True); p.add_argument('--output', required=True)
    p = commands.add_parser('verify'); p.add_argument('--input', required=True)
    p.add_argument('--full-checkpoint-hashes', action='store_true', help='CPU file hashing only; never loads a model')
    p = commands.add_parser('start')
    p.add_argument('--input', required=True); p.add_argument('--start-training', action='store_true', required=True)
    p.add_argument('--confirm-gpu-idle', action='store_true', required=True)
    p.add_argument('--resume', action='store_true'); p.add_argument('--clear-stop', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args)
    elif args.command == 'verify':
        plan, rows = verify(args.input, full_checkpoint=args.full_checkpoint_hashes)
        print(json.dumps({'status': 'verified_inputs', 'plan_sha256': identity(plan),
            'train_examples': len(rows['train']), 'validation_examples': len(rows['validation']), 'gpu_accessed': False}))
    else:
        # Explicit future invocation only. No imports of this path during prepare/verify.
        from lora6k_supervisor import start
        start(args)


if __name__ == '__main__': main()
