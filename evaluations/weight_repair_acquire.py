"""Explicit, pinned public-asset acquisition. Never imports ML or starts inference."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lora6k_state import atomic, inside, read, sha
from weight_repair import assets, locked_assets, MODEL_REVISION, REVISION

DATASET_REVISION = '6e4ed1a2a79af7d8630a6b768ec859cb5af4d3be'


def fetch_json(url):
    with urlopen(Request(url, headers={'User-Agent': 'AutoProteus-weight-repair/1'}), timeout=60) as response:
        raw = response.read(16 * 2**20 + 1)
    if len(raw) > 16 * 2**20: raise ValueError('Excessive metadata response')
    return json.loads(raw)


def get_inventory():
    model = fetch_json(f'https://huggingface.co/api/models/Qwen/Qwen3.5-0.8B/revision/{MODEL_REVISION}?blobs=true')
    dataset = fetch_json(f'https://huggingface.co/api/datasets/HuggingFaceH4/MATH-500/revision/{DATASET_REVISION}?blobs=true')
    if model['sha'] != MODEL_REVISION or dataset['sha'] != DATASET_REVISION:
        raise ValueError('Remote revision changed')
    specs = assets(); github = {}
    prefix = f'https://raw.githubusercontent.com/RikiyaT/lm_understand-logs/{REVISION}/'
    parents = {spec['url'][len(prefix):].rsplit('/', 1)[0] for spec in specs.values()
               if spec.get('url', '').startswith(prefix)}
    for parent in sorted(parents):
        rows = fetch_json(f'https://api.github.com/repos/RikiyaT/lm_understand-logs/contents/{parent}?ref={REVISION}')
        for row in rows:
            if row['type'] == 'file': github[row['path']] = {'size': row['size'], 'blobId': row['sha']}
    result = {}
    for name, spec in specs.items():
        if name.startswith('dataset/'):
            row = next(r for r in dataset['siblings'] if r['rfilename'] == 'test.jsonl')
            result[name] = {**spec, 'revision': DATASET_REVISION,
                'url': f'https://huggingface.co/datasets/HuggingFaceH4/MATH-500/resolve/{DATASET_REVISION}/test.jsonl',
                'remote': row}
        elif spec['url'].startswith(prefix):
            result[name] = {**spec, 'remote': github[spec['url'][len(prefix):]]}
        else:
            filename = spec['url'].rsplit('/', 1)[1]
            row = next(r for r in model['siblings'] if r['rfilename'] == filename)
            result[name] = {**spec, 'remote': row}
    return {'model': model, 'dataset': dataset, 'github': github, 'files': result}


def verify_download(path, remote):
    if path.stat().st_size != remote['size']: raise ValueError('Remote asset length mismatch')
    if remote.get('lfs'):
        digest = sha(path)
        if digest != remote['lfs']['sha256']: raise ValueError('LFS SHA-256 mismatch')
    else:
        digest = hashlib.sha1(b'blob ' + str(remote['size']).encode() + b'\0')
        with path.open('rb') as stream:
            while chunk := stream.read(2**20): digest.update(chunk)
        if digest.hexdigest() != remote['blobId']: raise ValueError('Pinned Git blob identity mismatch')
    return sha(path)


def acquire(output, authorize=False):
    if not authorize: raise ValueError('Explicit --download-pinned-assets required')
    output = Path(output).resolve()
    output.relative_to(HERE.parent / '.data')
    if output.exists(): raise ValueError('Use a new acquisition directory')
    output.mkdir(parents=True)
    atomic(output / 'AUTHORIZATION.json', {'scope': 'Pinned assets and CPU reconstruction/grader only',
        'downloads_authorized': True, 'gpu_authorized': False, 'live_inference_authorized': False})
    inventory = get_inventory(); atomic(output / 'remote-inventory.json', inventory)
    lock, receipts = {}, []
    # Download the large immutable model while callers prepare the separate CPU environment.
    order = sorted(inventory['files'], key=lambda name: name != 'base/model.safetensors')
    for name in order:
        spec = inventory['files'][name]; path = inside(output / 'assets', name)
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(path.suffix + '.partial')
        if shutil.disk_usage(output).free < 20 * 2**30: raise ValueError('Acquisition disk guard')
        expected = spec['remote']['size']; count, start, last = 0, time.monotonic(), 0
        with urlopen(Request(spec['url'], headers={'User-Agent': 'AutoProteus-weight-repair/1'}), timeout=120) as response, partial.open('xb') as stream:
            if int(response.headers.get('Content-Length', expected)) != expected:
                raise ValueError('Unexpected download length')
            while chunk := response.read(2**20):
                stream.write(chunk); count += len(chunk)
                if count > expected: raise ValueError('Download exceeded pinned length')
                if time.monotonic() - start > 2700: raise ValueError('Download watchdog')
                if time.monotonic() - last > 10:
                    atomic(output / 'progress.json', {'file': name, 'bytes': count, 'expected_bytes': expected,
                        'elapsed_seconds': time.monotonic() - start, 'files_complete': len(receipts)})
                    last = time.monotonic()
        digest = verify_download(partial, spec['remote'])
        partial.rename(path)
        lock[name] = {k: v for k, v in spec.items() if k != 'remote'}
        lock[name].update(sha256=digest, bytes=count)
        receipts.append({'name': name, 'sha256': digest, 'bytes': count,
            'elapsed_seconds': time.monotonic() - start, 'verified_remote_git_or_lfs': True})
        atomic(output / 'downloads.json', receipts)
    locked_assets(lock)
    atomic(output / 'asset-lock.json', lock)
    atomic(output / 'COMPLETE.json', {'assets': len(lock), 'bytes': sum(r['bytes'] for r in receipts),
        'asset_lock_sha256': sha(output / 'asset-lock.json'), 'gpu_accessed': False})
    print(json.dumps({'status': 'downloaded_and_verified', 'assets': len(lock), 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--download-pinned-assets', action='store_true')
    args = parser.parse_args()
    acquire(args.output, args.download_pinned_assets)
