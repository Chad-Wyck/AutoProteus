"""Trusted installed-runtime manifests; generated only after pinned extraction."""
import hashlib
import json
from pathlib import Path

from .storage import atomic_json

RECORD = 'installed-runtime.json'


def inventory(directory):
    directory = Path(directory)
    root = directory.resolve()
    if directory.is_symlink() or getattr(directory.lstat(), 'st_file_attributes', 0) & 0x400:
        raise ValueError('Managed runtime directories cannot be links')
    files = {}
    for path in directory.rglob('*'):
        if path == directory / RECORD:
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError('A managed runtime file escapes its directory')
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(stream.read()).hexdigest()
            files[path.relative_to(directory).as_posix()] = digest
    return files


def record_runtime(directory, pin):
    files = inventory(directory)
    if not files:
        raise ValueError('The managed runtime is empty')
    atomic_json(Path(directory) / RECORD, {'version': pin['version'], 'archive_sha256': pin['sha256'], 'files': files})


def verify_runtime(directory, pin):
    try:
        record = json.loads((Path(directory) / RECORD).read_text(encoding='utf-8'))
        if record['version'] != pin['version'] or record['archive_sha256'] != pin['sha256'] or record['files'] != inventory(directory):
            raise ValueError('The managed runtime changed')
        return record
    except (OSError, KeyError, ValueError):
        raise ValueError('The managed engine needs verified setup. Use Prepare local model to repair it.') from None
