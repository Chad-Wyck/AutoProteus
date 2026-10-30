"""Offline pilot inputs and transactional state. No ML imports or GPU calls."""
from collections import defaultdict
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
import uuid


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inside(root, name):
    root = Path(root).resolve(); path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root: raise ValueError('Path escapes owned directory')
    return path


@contextmanager
def exclusive(directory):
    """OS-held lock releases after a crash; never guesses ownership from a PID."""
    path = Path(directory) / 'runner.lock'
    with path.open('a+b') as stream:
        if stream.tell() == 0: stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError: raise ValueError('This training run already has an active supervisor') from None
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream, fcntl.LOCK_UN)


def checked_rows(dataset, pilot):
    """Pin original local-Qwen targets and exact, completion-only serialized masks."""
    dataset = Path(dataset); manifest = read(dataset / 'manifest.json')
    if sha(dataset / 'manifest.json') != pilot['dataset_manifest_sha256']: raise ValueError('Dataset manifest changed')
    if manifest.get('sol_excluded') is not True or manifest.get('workflow_and_generated_source_groups_disjoint') is not True:
        raise ValueError('Dataset provenance/split review is absent')
    for name, digest in pilot['dataset_files'].items():
        if sha(inside(dataset, name)) != digest or manifest['files'].get(name) != digest:
            raise ValueError('Dataset file changed: ' + name)
    ledger = {r['id']: r for r in read(dataset / 'review-ledger.json')}
    splits = {}; groups = {}
    for split, count in (('train', 93), ('validation', 27)):
        originals = [json.loads(line) for line in (dataset / (split + '.jsonl')).read_text(encoding='utf-8').splitlines()]
        tokens = [json.loads(line) for line in (dataset / (split + '-tokens.jsonl')).read_text(encoding='utf-8').splitlines()]
        metadata = {r['metadata']['id']: r['metadata'] for r in originals}
        if len(metadata) != count or len(tokens) != count or len({r['id'] for r in tokens}) != count:
            raise ValueError('Unexpected or duplicate examples')
        for row in tokens:
            meta = metadata[row['id']]; teacher = meta['teacher']; review = ledger[row['id']]
            if not (teacher.get('adapter') is False and teacher.get('endpoint') == 'loopback'
                    and teacher.get('weights_sha256') == [pilot['model']['teacher_weights_sha256']]
                    and teacher.get('license_revision') == pilot['model']['hf_revision']
                    and review.get('original_quality_rechecked') is True and review['split'] == split
                    and review['lineage_group'] == meta['lineage_group']):
                raise ValueError('Nonlocal, adapted or unreviewed teacher')
            ids, labels, mask = (row[k] for k in ('input_ids', 'labels', 'attention_mask'))
            n = row['total_tokens']; targets = row['completion_tokens']; start = n - targets
            if not (type(n) is int and type(targets) is int and 1 <= start < n <= 6144
                    and len(ids) == len(labels) == len(mask) == n
                    and all(type(x) is int and x >= 0 for x in ids)
                    and all(type(x) is int for x in labels + mask)
                    and mask == [1] * n and labels[:start] == [-100] * start and labels[start:] == ids[start:]):
                raise ValueError('Invalid or truncated completion mask')
            row['bucket'] = meta['bucket']; row['group'] = meta['lineage_group']
        splits[split] = tokens
        groups[split] = {r['group'] for r in tokens}
    if groups['train'] & groups['validation']: raise ValueError('Source-lineage split leakage')
    order = pilot['epoch_order']; by_id = {r['id']: r for r in splits['train']}
    if len(order) != len(by_id) or set(order) != set(by_id): raise ValueError('Epoch order changed')
    splits['train'] = [by_id[key] for key in order]
    return splits


def learning_rate(completed, total, config):
    if type(completed) is not int or not 0 <= completed < total: raise ValueError('No next update')
    step = completed + 1; warmup = config['warmup_updates']; peak = config['learning_rate']
    return peak * (step / warmup if step <= warmup else 1 - .9 * (step - warmup) / (total - warmup))


def summarize_validation(records):
    if not records: raise ValueError('No validation measurements')
    buckets, groups = defaultdict(list), defaultdict(list)
    for row in records:
        if not math.isfinite(row['nll']) or row['nll'] < 0 or row['targets'] < 1: raise ValueError('Invalid validation loss')
        buckets[row['bucket']].append(row); groups[row['group']].append(row)
    def weighted(rows): return sum(r['nll'] * r['targets'] for r in rows) / sum(r['targets'] for r in rows)
    per_bucket = {key: weighted(rows) for key, rows in buckets.items()}
    workflow = [per_bucket[k] for k in ('activation', 'capability_use', 'save_output', 'completion') if k in per_bucket]
    return {'token_weighted_nll': weighted(records), 'supervised_tokens': sum(r['targets'] for r in records),
        'examples': len(records), 'per_bucket_nll': per_bucket, 'per_group_nll': {k: weighted(v) for k, v in groups.items()},
        'workflow_macro_nll': sum(workflow) / len(workflow) if workflow else None,
        'lineage_macro_nll': sum(weighted(v) for v in groups.values()) / len(groups)}


class Checkpoints:
    """Only a hashed COMMITTED.json makes a checkpoint resumable. Keep the newest two."""
    def __init__(self, root, binding):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True); self.binding = binding

    def verify(self, path):
        path = inside(self.root, Path(path).name)
        manifest = read(path / 'COMMITTED.json')
        if manifest.get('binding') != self.binding: raise ValueError('Checkpoint belongs to different inputs/code')
        if not manifest.get('files'): raise ValueError('Empty checkpoint')
        for name, digest in manifest['files'].items():
            if sha(inside(path, name)) != digest: raise ValueError('Corrupt checkpoint: ' + name)
        if 'progress.json' not in manifest['files']: raise ValueError('Checkpoint progress missing')
        progress = read(path / 'progress.json')
        if type(progress['completed_updates']) is not int or progress['completed_updates'] < 0:
            raise ValueError('Invalid checkpoint cursor')
        if path.name != 'step-%04d' % progress['completed_updates']: raise ValueError('Checkpoint cursor mismatch')
        return {'path': path, 'manifest_sha256': sha(path / 'COMMITTED.json'), 'progress': progress}

    def latest(self):
        # A commit can survive a crash before LATEST.json replacement. Recover it,
        # but never silently fall back when a committed checkpoint is corrupt.
        candidates = sorted(p for p in self.root.glob('step-*') if p.is_dir() and (p / 'COMMITTED.json').exists())
        if not candidates: return None
        return self.verify(candidates[-1])

    def commit(self, progress, save_backend):
        step = progress['completed_updates']; final = self.root / ('step-%04d' % step)
        if final.exists(): raise ValueError('Refusing to overwrite committed checkpoint')
        staging = self.root / ('.staging-' + uuid.uuid4().hex); staging.mkdir()
        # Leave an interrupted staging directory for diagnosis; it is never resumed.
        save_backend(staging)
        atomic(staging / 'progress.json', progress)
        for path in staging.rglob('*'):
            if path.is_file():
                with path.open('r+b') as stream: os.fsync(stream.fileno())
        files = {p.relative_to(staging).as_posix(): sha(p) for p in staging.rglob('*') if p.is_file()}
        atomic(staging / 'COMMITTED.json', {'schema': 1, 'binding': self.binding, 'files': files})
        os.replace(staging, final)
        atomic(self.root / 'LATEST.json', {'checkpoint': final.name, 'manifest_sha256': sha(final / 'COMMITTED.json')})
        result = self.verify(final)
        previous = sorted(p for p in self.root.glob('step-*') if p.is_dir() and (p / 'COMMITTED.json').exists())
        for old in previous[:-2]:
            self.verify(old)  # Only remove our complete, correctly bound checkpoints.
            shutil.rmtree(inside(self.root, old.name))
        return result


def validate(backend, rows, path, checkpoint, event, stop):
    """Resume validation only against the exact same adapter checkpoint."""
    path = Path(path); digest = checkpoint['manifest_sha256']
    prior = read(path) if path.exists() else {'checkpoint_sha256': digest, 'records': [], 'records_sha256': identity([])}
    if prior.get('checkpoint_sha256') != digest: raise ValueError('Validation belongs to another checkpoint')
    records = prior['records']
    if identity(records) != prior.get('records_sha256'): raise ValueError('Validation record checksum changed')
    if len(records) > len(rows) or [r['id'] for r in records] != [r['id'] for r in rows[:len(records)]]:
        raise ValueError('Validation cursor/order changed')
    if any(record['targets'] != row['completion_tokens'] or record['bucket'] != row['bucket'] or record['group'] != row['group']
           for record, row in zip(records, rows)):
        raise ValueError('Validation metadata changed')
    for row in rows[len(records):]:
        if stop(): return None
        event('validation_example_started', id=row['id'])
        nll = float(backend.evaluate(row))
        if not math.isfinite(nll) or nll < 0: raise ValueError('Nonfinite validation loss')
        records.append({'id': row['id'], 'bucket': row['bucket'], 'group': row['group'],
                        'targets': row['completion_tokens'], 'nll': nll})
        atomic(path, {'checkpoint_sha256': digest, 'records': records, 'records_sha256': identity(records)})
        event('validation_example_complete', id=row['id'], nll=nll, targets=row['completion_tokens'])
    result = summarize_validation(records)
    atomic(path, {'checkpoint_sha256': digest, 'records': records, 'records_sha256': identity(records), 'summary': result, 'completed': True})
    return result


def execute(backend, plan, rows, output, event, stop=lambda: False):
    """One epoch only. A crash discards uncommitted work, never skips an example."""
    output = Path(output); binding = identity(plan)
    checkpoints = Checkpoints(output / 'checkpoints', binding)
    current = checkpoints.latest()
    if current:
        event('restore_started', checkpoint=current['path'].name)
        backend.restore(current['path'])
        event('restore_complete', completed_updates=current['progress']['completed_updates'])
    else:
        event('checkpoint_started', completed_updates=0)
        current = checkpoints.commit({'completed_updates': 0, 'baseline': None, 'last_update': None}, backend.save)
        event('checkpoint_complete', completed_updates=0)
    cursor = current['progress']['completed_updates']; total = len(rows['train'])
    if cursor > total: raise ValueError('Checkpoint extends past the frozen single epoch')
    baseline = current['progress']['baseline']
    if baseline is None:
        baseline = validate(backend, rows['validation'], output / 'baseline-validation.json', current, event, stop)
        if baseline is None: return {'status': 'paused', 'completed_updates': cursor}
    for number in range(cursor, total):
        if stop(): return {'status': 'paused', 'completed_updates': number}
        row = rows['train'][number]; rate = learning_rate(number, total, plan['pilot']['configuration'])
        event('update_started', update=number + 1, id=row['id'], learning_rate=rate)
        measured = backend.update(row, rate)
        if not math.isfinite(float(measured['loss'])) or not math.isfinite(float(measured['gradient_norm'])):
            raise ValueError('Nonfinite training result; checkpoint not advanced')
        event('checkpoint_started', completed_updates=number + 1)
        current = checkpoints.commit({'completed_updates': number + 1, 'baseline': baseline,
            'last_update': {'id': row['id'], 'learning_rate': rate, **measured}}, backend.save)
        event('update_committed', update=number + 1, id=row['id'], **measured)
    final = validate(backend, rows['validation'], output / 'candidate-validation.json', current, event, stop)
    if final is None: return {'status': 'paused', 'completed_updates': total}
    initial = baseline['token_weighted_nll']; improved = final['token_weighted_nll'] <= .99 * initial
    macro = baseline['workflow_macro_nll']; retained = macro is not None and final['workflow_macro_nll'] <= 1.10 * macro
    result = {'status': 'completed_one_epoch', 'completed_updates': total, 'baseline': baseline, 'candidate': final,
        'candidate_checkpoint': current['path'].name, 'candidate_checkpoint_sha256': current['manifest_sha256'],
        'validation_gate_passed': bool(improved and retained), 'capability_improvement_established': False,
        'adapter_exported_for_inference': False, 'generation_started': False,
        'scope': 'Validation permits consideration of a separately authorized generation study, never automatic promotion.'}
    atomic(output / 'training-result.json', result)
    return result
