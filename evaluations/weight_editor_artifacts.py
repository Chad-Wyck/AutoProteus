"""Trusted numeric application of the existing two-coefficient research operator."""
import json
import math
from pathlib import Path
import shutil
import sys

from lora6k_state import atomic, sha
from weight_editor_runtime import check_files, require, unique_artifact, verify_unchanged_bytes


def proposal(text):
    body = text.rsplit('</think>', 1)[-1].strip()
    lines = body.splitlines()
    if len(lines) >= 3 and lines[0].casefold() in ('```json', '```') and lines[-1] == '```':
        body = '\n'.join(lines[1:-1])
    value = json.loads(body)
    if isinstance(value, dict) and set(value) == {'stop'} and value['stop'] is True:
        return None
    require(isinstance(value, dict) and not set(value)-{'strength15', 'strength19', 'rationale'}
            and {'strength15', 'strength19'} <= set(value), 'Only two strengths and optional rationale are accepted')
    pair = [value['strength15'], value['strength19']]
    require(all(type(x) in (int, float) and math.isfinite(x) and .7 <= x <= 1.3 for x in pair), 'Finite strengths in [0.7,1.3] required')
    return {'strengths': list(map(float, pair)), 'rationale': str(value.get('rationale', ''))[:2000]}


def build(plan, folder, chosen, existing, deadline):
    """Never execute model text. Keep a rejected duplicate artifact for audit."""
    import numpy as np
    vendor = plan['cpu_vendor_sources']
    check_files(vendor['path'], vendor['files'])
    sys.path.insert(0, vendor['path'])
    from gguf import GGUFReader
    folder = Path(folder)
    require(not folder.exists(), 'Never overwrite candidate evidence')
    deadline.remaining()
    require(shutil.disk_usage(folder.parent).free >= 20 * 2**30, 'Candidate build disk admission floor')
    original, repaired = [plan['models'][key] for key in ('original_target', 'repaired_target')]
    for item in (original, repaired):
        require(sha(item['path']) == item['sha256'], 'Candidate source changed')
    folder.mkdir()
    output = folder / 'model-f32.gguf'
    shutil.copyfile(repaired['path'], output)
    arrays = [{t.name: t for t in GGUFReader(path).tensors} for path in (original['path'], repaired['path'], output)]
    a, b, c = arrays
    targets = plan['editing_interface']['operation']['tensors']
    patch, changes = {}, []
    for i, name in enumerate(targets):
        deadline.remaining()
        x, y = a[name].data, b[name].data
        require(x.dtype == y.dtype == np.float32 and x.shape == y.shape, 'Tensor format mismatch')
        value = x + np.float32(chosen['strengths'][i]) * (y-x)
        bits = value.view(np.uint32)
        rounded = ((bits + np.uint32(0x7fff) + ((bits >> 16) & 1)) >> 16).astype(np.uint16)
        allowed = x.view(np.uint32) != y.view(np.uint32)
        value = np.where(allowed, (rounded.astype(np.uint32) << 16).view(np.float32), y)
        require(np.isfinite(value).all(), 'Nonfinite candidate')
        view = np.memmap(output, mode='r+', dtype=np.float32, offset=c[name].data_offset, shape=y.shape)
        view[:] = value; view.flush(); del view
        indices = np.flatnonzero(value.reshape(-1).view(np.uint32) != y.reshape(-1).view(np.uint32)).astype(np.uint32)
        patch['positions'+str(i)] = indices
        patch['bf16_values'+str(i)] = (value.reshape(-1).view(np.uint32)[indices] >> 16).astype(np.uint16)
        changes.append({'tensor': name, 'entries': len(indices)})
    byte_check = verify_unchanged_bytes(repaired['path'], output,
        [(int(b[name].data_offset), int(b[name].data.nbytes)) for name in targets], deadline)
    np.savez_compressed(folder / 'sparse-patch.npz', **patch)
    with np.load(folder / 'sparse-patch.npz', allow_pickle=False) as saved:
        for i, name in enumerate(targets):
            rebuilt = b[name].data.copy().reshape(-1)
            rebuilt[saved['positions'+str(i)]] = (saved['bf16_values'+str(i)].astype(np.uint32) << 16).view(np.float32)
            require(np.array_equal(rebuilt.view(np.uint32), c[name].data.reshape(-1).view(np.uint32)), 'Sparse roundtrip failed')
    digest = sha(output)
    manifest = {'model': str(output), 'sha256': digest, 'proposal': chosen, 'changes': changes,
                'sparse_roundtrip_exact': True, 'other_tensors_unchanged': True, 'byte_comparison': byte_check,
                'authorship': 'Local unchanged 4B chooses two strengths; published directions supplied by host'}
    atomic(folder / 'MANIFEST.json', manifest)
    try:
        unique_artifact(digest, existing)
    except ValueError:
        atomic(folder / 'REJECTED-DUPLICATE.json', {'sha256': digest, 'new_candidate': False})
        raise
    deadline.remaining()
    return {'path': str(output), 'sha256': digest}
