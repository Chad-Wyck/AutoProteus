"""Protected file transfers and inert artifacts; never executes guest source."""
import base64
import hashlib
import os
from pathlib import Path
import re

from .errors import IsolationError

MAX_FILE = 2 * 1024 * 1024
MAX_FILES = 500
MAX_EXPORT = 32 * 1024 * 1024
SEED_TESTS = ('tests/test_seed.py', 'tests/test_text_helpers.py')


def relative_name(name):
    if not isinstance(name, str) or not name or len(name) > 400:
        raise IsolationError('Invalid export path')
    parts = name.split('/')
    for part in parts:
        if (not part or part in ('.', '..') or len(part) > 120 or part.endswith((' ', '.'))
                or re.search(r'[\x00-\x1f<>:"\\|?*]', part)
                or part.split('.')[0].rstrip(' ').upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(10)), *('LPT'+str(i) for i in range(10)),
                                                             'COM¹', 'COM²', 'COM³', 'LPT¹', 'LPT²', 'LPT³'}):
            raise IsolationError('Invalid export path')
    return name


def safe_path(root, name):
    name = relative_name(name)
    root = Path(root).absolute()
    path = root / name
    for part in [root, *path.parents, path]:
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) & 0x400):
            raise IsolationError('Links are not permitted in host export storage')
    if not path.resolve().is_relative_to(root.resolve()):
        raise IsolationError('Invalid export location')
    return path


def packed_files(root, prefix=''):
    root = Path(root).absolute()
    safe_path(root, 'input-check')
    root = root.resolve()
    total, result = 0, []
    if not root.exists():
        return result
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = [n for n in names if not n.startswith('.') and n != '__pycache__']
        for name in sorted(files):
            path = Path(directory) / name
            if name.startswith('.') or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            path = safe_path(root, relative)
            if not path.is_file() or path.stat().st_size > MAX_FILE:
                raise IsolationError('Input files must be ordinary files of at most 2 MB')
            data = path.read_bytes()
            total += len(data)
            if total > MAX_EXPORT or len(result) >= MAX_FILES:
                raise IsolationError('Input workspace exceeds the transfer limit')
            result.append({'path': prefix + relative, 'data': base64.b64encode(data).decode()})
    return result


def seed_files(root):
    result = []
    for name in ('autoproteus',):
        result.extend(packed_files(Path(root) / name, name + '/'))
    for name in ('seed.py', 'SEED.md', 'examples/test_web_extension.py', 'examples/test_text_extension.py', *SEED_TESTS):
        data = (Path(root) / name).read_bytes()
        result.append({'path': 'README.md' if name == 'SEED.md' else name, 'data': base64.b64encode(data).decode()})
    return result


class Artifacts:
    """Names are metadata; guest bytes are stored under host-computed hash names."""
    def __init__(self, store, session):
        self.store, self.session = store, session
        self.root = safe_path(store.directory(session['id']), 'quarantine')
        self.root.mkdir(exist_ok=True)
        self.pending = {}
        self.sent_bytes = 0

    def put(self, name, encoded):
        relative_name(name)
        if not isinstance(encoded, str) or len(encoded) > (MAX_FILE * 4 // 3 + 8):
            raise IsolationError('Export file too large')
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise IsolationError('Invalid export encoding') from None
        self.sent_bytes += len(data)
        if len(data) > MAX_FILE or self.sent_bytes > MAX_EXPORT or len(self.pending) >= MAX_FILES:
            raise IsolationError('Export quota exceeded')
        digest = hashlib.sha256(data).hexdigest()
        path = safe_path(self.root, digest + '.blob')
        if not path.exists():
            path.write_bytes(data)
        self.pending[name] = {'sha256': digest, 'bytes': len(data)}

    def checkpoint(self, paths):
        if not isinstance(paths, list) or len(paths) > MAX_FILES or len(set(paths)) != len(paths):
            raise IsolationError('Invalid file manifest')
        available = {**self.session.get('artifacts', {}), **self.pending}
        manifest = {}
        for name in paths:
            relative_name(name)
            if name not in available:
                raise IsolationError('Manifest references an unsaved file')
            manifest[name] = available[name]
        if sum(item['bytes'] for item in manifest.values()) > MAX_EXPORT:
            raise IsolationError('Workspace export exceeds 32 MB')
        self.session['artifacts'] = manifest
        self.store.save(self.session)
        self.pending = {}
        self.cleanup()

    def cleanup(self):
        keep = {item['sha256'] + '.blob' for item in self.session.get('artifacts', {}).values()}
        keep.update(item['sha256'] + '.blob' for item in self.pending.values())
        for path in self.root.glob('*.blob'):
            if path.name not in keep and not path.is_symlink():
                path.unlink()

    def read(self, name):
        relative_name(name)
        item = self.session.get('artifacts', {}).get(name)
        if not item or not re.fullmatch('[a-f0-9]{64}', item['sha256']):
            raise ValueError('File not found')
        data = safe_path(self.root, item['sha256'] + '.blob').read_bytes()
        if len(data) > MAX_FILE or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise IsolationError('Saved file failed its integrity check')
        return data

    def pack(self):
        return [{'path': name, 'data': base64.b64encode(self.read(name)).decode()}
                for name in sorted(self.session.get('artifacts', {}))]
