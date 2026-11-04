"""CPU-only safetensors and sparse BF16 repair checks. No ML or NumPy imports."""
import ast
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import uuid
import zipfile


WIDTHS = {'BF16': 2, 'F16': 2, 'F32': 4, 'F64': 8, 'I64': 8, 'I32': 4,
          'I16': 2, 'I8': 1, 'U8': 1, 'U16': 2, 'U32': 4, 'U64': 8, 'BOOL': 1}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate header key: ' + key)
        result[key] = value
    return result


class TensorFile:
    def __init__(self, path):
        self.path = Path(path)
        size = self.path.stat().st_size
        with self.path.open('rb') as stream:
            length = stream.read(8)
            if len(length) != 8:
                raise ValueError('Truncated safetensors length')
            n, = struct.unpack('<Q', length)
            if not 2 <= n <= min(16 * 2**20, size - 8):
                raise ValueError('Invalid safetensors header size')
            header = json.loads(stream.read(n), object_pairs_hook=unique_object)
        if not isinstance(header, dict):
            raise ValueError('Expected tensor header object')
        self.start = 8 + n
        self.tensors = {key: value for key, value in header.items() if key != '__metadata__'}
        if not self.tensors:
            raise ValueError('Empty tensor file')
        ranges = []
        for name, item in self.tensors.items():
            if not isinstance(item, dict) or set(item) != {'dtype', 'shape', 'data_offsets'}:
                raise ValueError('Invalid tensor header: ' + name)
            shape, offsets, dtype = item['shape'], item['data_offsets'], item['dtype']
            if (dtype not in WIDTHS or not isinstance(shape, list) or len(shape) > 16
                    or any(type(d) is not int or not 0 <= d < 2**32 for d in shape)
                    or not isinstance(offsets, list) or len(offsets) != 2
                    or any(type(d) is not int or d < 0 for d in offsets)
                    or offsets[1] - offsets[0] != math.prod(shape) * WIDTHS[dtype]):
                raise ValueError('Invalid tensor size or dtype: ' + name)
            ranges.append((*offsets, name))
        end = 0
        for a, b, name in sorted(ranges):
            if a != end or b < a:
                raise ValueError('Overlapping or non-contiguous tensor: ' + name)
            end = b
        if self.start + end != size:
            raise ValueError('Truncated tensor data or trailing bytes')

    def chunks(self, name):
        a, b = self.tensors[name]['data_offsets']
        with self.path.open('rb') as stream:
            stream.seek(self.start + a)
            while a < b:
                raw = stream.read(min(2**20, b - a))
                if not raw:
                    raise ValueError('Tensor shortened during inspection')
                a += len(raw)
                yield raw

    def digest(self, name, *, promoted=False):
        dtype = self.tensors[name]['dtype']
        if promoted and dtype != 'BF16':
            raise ValueError('Only canonical BF16 promotion is supported')
        digest = hashlib.sha256()
        for chunk in self.chunks(name):
            if dtype == 'BF16':
                bits = array('H', chunk)
                if sys.byteorder != 'little': bits.byteswap()
                if any(b & 0x7f80 == 0x7f80 for b in bits):
                    raise ValueError('Nonfinite BF16 tensor: ' + name)
                if promoted:
                    out = bytearray(2 * len(chunk))
                    out[2::4], out[3::4] = chunk[::2], chunk[1::2]
                    chunk = out
            elif dtype in ('F16', 'F32', 'F64'):
                fmt = {'F16': 'e', 'F32': 'f', 'F64': 'd'}[dtype]
                if any(not math.isfinite(value) for value, in struct.iter_unpack('<' + fmt, chunk)):
                    raise ValueError('Nonfinite floating tensor: ' + name)
            digest.update(chunk)
        return digest.hexdigest()

    def inventory(self):
        return {name: {'shape': item['shape'], 'dtype': item['dtype'], 'sha256': self.digest(name)}
                for name, item in sorted(self.tensors.items())}


def audit_pair(base, edited, targets, *, changed_entries, columns):
    base, edited = TensorFile(base), TensorFile(edited)
    before, after = base.inventory(), edited.inventory()
    if set(before) != set(after): raise ValueError('Tensor set changed')
    for name in before:
        if any(before[name][key] != after[name][key] for key in ('shape', 'dtype')):
            raise ValueError('Tensor metadata changed: ' + name)
    changed = {name for name in before if before[name]['sha256'] != after[name]['sha256']}
    if changed != set(targets): raise ValueError('Unexpected changed tensors')
    differences, counts = 0, {}
    for name, target in targets.items():
        if (before[name]['dtype'] != 'BF16' or before[name]['shape'] != target['shape']
                or before[name]['sha256'] != target['base_sha256']
                or after[name]['sha256'] != target['edited_sha256']):
            raise ValueError('Wrong base or edited tensor: ' + name)
        width = target['shape'][1]; count, changed_columns, offset = 0, set(), 0
        for left, right in zip(base.chunks(name), edited.chunks(name), strict=True):
            for index, ((a,), (b,)) in enumerate(zip(struct.iter_unpack('<H', left), struct.iter_unpack('<H', right), strict=True)):
                if a != b:
                    count += 1
                    changed_columns.add((offset + index) % width)
            offset += len(left) // 2
        if len(changed_columns) != columns: raise ValueError('Wrong edited column count')
        differences += count
        counts[name] = {'changed_entries': count, 'changed_columns': len(changed_columns),
                        'promoted_fp32_sha256': edited.digest(name, promoted=True)}
    if differences != changed_entries: raise ValueError('Wrong BF16 bit-difference count')
    return {'canonical_hashes_match': True, 'unchanged_tensor_audit': True,
            'changed_tensors': sorted(changed), 'changed_entries': differences, 'tensors': counts,
            'behavior_measured': False}


def npy_vector(raw):
    """Read only the small numeric vectors used by the released sparse edit."""
    if raw[:6] != b'\x93NUMPY' or raw[6:8] not in (b'\x01\x00', b'\x02\x00'):
        raise ValueError('Unsupported NPY header')
    width = 2 if raw[6] == 1 else 4
    if len(raw) < 8 + width: raise ValueError('Truncated NPY length')
    n = int.from_bytes(raw[8:8 + width], 'little'); start = 8 + width + n
    if n > 65536 or start > len(raw): raise ValueError('Invalid NPY header length')
    header = ast.literal_eval(raw[8 + width:start].decode('ascii'))
    if not isinstance(header, dict) or set(header) != {'descr', 'fortran_order', 'shape'}:
        raise ValueError('Invalid NPY header')
    fmt = {'<i8': 'q', '<i4': 'i', '<u2': 'H'}.get(header['descr'])
    shape = header['shape']
    if (not fmt or header['fortran_order'] is not False or not isinstance(shape, tuple)
            or len(shape) != 1 or type(shape[0]) is not int or shape[0] < 0
            or len(raw) - start != shape[0] * struct.calcsize(fmt)):
        raise ValueError('Unsupported sparse vector format')
    return header['descr'], [value for value, in struct.iter_unpack('<' + fmt, raw[start:])]


def rebuild_sparse(base, patch, output, targets, *, changed_entries, columns, touched_entries):
    """Apply p50c's sparse BF16 assignments to a new file, then audit before publish.

    This ports the sparse branch of upstream apply_edit.rebuild. No downloaded
    scripts are executed. Production callers must verify the pinned asset lock.
    """
    base, output = TensorFile(base), Path(output)
    if output.resolve() == base.path.resolve() or output.exists():
        raise ValueError('Refusing to overwrite a checkpoint')
    output.parent.mkdir(parents=True, exist_ok=True)
    replacements = []
    with zipfile.ZipFile(patch) as archive:
        expected = {f't{i}_{part}.npy' for i in range(len(targets)) for part in ('idx', 'val')}
        names = archive.namelist()
        if len(names) != len(expected) or set(names) != expected:
            raise ValueError('Unexpected or duplicate sparse patch members')
        for item in archive.infolist():
            if item.file_size > 16 * 2**20: raise ValueError('Patch member too large')
        touched = 0
        for i, (name, target) in enumerate(targets.items()):
            tensor = base.tensors.get(name)
            if (not tensor or tensor['dtype'] != 'BF16' or tensor['shape'] != target['shape']
                    or base.digest(name) != target['base_sha256']):
                raise ValueError('Wrong patch base')
            itype, indices = npy_vector(archive.read(f't{i}_idx.npy'))
            vtype, values = npy_vector(archive.read(f't{i}_val.npy'))
            size = math.prod(target['shape']); width = target['shape'][1]
            if (itype not in ('<i8', '<i4') or vtype != '<u2' or len(indices) != len(values)
                    or len(set(indices)) != len(indices) or any(not 0 <= n < size for n in indices)
                    or any(value & 0x7f80 == 0x7f80 for value in values)
                    or len({n % width for n in indices}) != columns):
                raise ValueError('Invalid sparse assignments')
            replacements.append((tensor['data_offsets'][0], indices, values)); touched += len(indices)
    # The published sparse export stores only BF16 bit differences, omitting
    # targeted entries which rounded back to the base value. Logical targeted
    # columns and serialized assignments are deliberately separate quantities.
    targeted = sum(target['shape'][0] * columns for target in targets.values())
    if targeted != touched_entries or touched > targeted:
        raise ValueError('Wrong targeted-entry count')
    staging = output.with_name('.' + output.name + '.' + uuid.uuid4().hex + '.staging')
    shutil.copyfile(base.path, staging)
    # Failed stages are intentionally preserved, never adopted as canonical.
    with staging.open('r+b') as stream:
        for offset, indices, values in replacements:
            for index, value in zip(indices, values, strict=True):
                stream.seek(base.start + offset + index * 2)
                stream.write(struct.pack('<H', value))
        stream.flush()
        os.fsync(stream.fileno())
    receipt = audit_pair(base.path, staging, targets, changed_entries=changed_entries, columns=columns)
    receipt.update(stored_patch_assignments=touched, targeted_entries=targeted)
    # Exclusive creation avoids replacing a file created after the initial check.
    if os.name == 'nt':
        os.rename(staging, output)  # Windows rename refuses an existing destination.
    else:
        os.link(staging, output)  # POSIX rename would overwrite an existing file.
        staging.unlink()
    return receipt


def text_mapping(inventory, *, tied_embeddings):
    result = {}
    for name in inventory:
        if name.startswith('model.language_model.'):
            result[name] = 'model.' + name.removeprefix('model.language_model.')
        elif name == 'lm_head.weight':
            result[name] = name
    embed = 'model.language_model.embed_tokens.weight'
    if embed not in result: raise ValueError('Text embeddings missing')
    if not tied_embeddings and 'lm_head.weight' not in result: raise ValueError('Untied output head missing')
    if tied_embeddings and 'lm_head.weight' in result:
        if inventory[embed] != inventory['lm_head.weight']: raise ValueError('Declared tied weights differ')
    if len(set(result.values())) != len(result): raise ValueError('Runtime tensor mapping collision')
    return {'mapping': result, 'tied_embeddings': tied_embeddings,
            'omitted_non_text_tensors': sorted(set(inventory) - set(result)),
            'runtime_loaded': False}
