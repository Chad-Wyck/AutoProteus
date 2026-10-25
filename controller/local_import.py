"""Import discovered local GGUF data through Ollama, without model execution."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from .storage import atomic_json


def local_files(root):
    root = Path(root).resolve()
    found = []
    paths = list(root.glob('*.gguf'))
    # Include historical experiment caches, but skip session content, source
    # checkouts and environments. Bound traversal; never walk another drive.
    skip = {'sessions', 'quarantine', 'inference', 'slot-cache', 'test-tmp', 'conversion-source',
            'node_modules', 'site-packages', '__pycache__', '.git', '.venv', 'venv'}
    for cache in (root / '.data', root / '.runtime/models'):
        if cache.is_symlink() or not cache.resolve().is_relative_to(root):
            continue
        for index, (directory, folders, names) in enumerate(os.walk(cache, followlinks=False)):
            folders[:] = sorted(name for name in folders if name not in skip
                                and not (Path(directory) / name).is_symlink()
                                and (Path(directory) / name).resolve().is_relative_to(root))
            paths.extend(Path(directory) / name for name in names if name.lower().endswith('.gguf'))
            if index >= 10000:
                break
    for path in sorted(set(paths))[:512]:
        try:
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                continue
            with path.open('rb') as stream:
                header = stream.read(65536)
                if len(header) <= 24 or header[:4] != b'GGUF' or struct.unpack('<Q', header[8:16])[0] == 0:
                    continue
                if b'general.type' + struct.pack('<IQ', 8, 7) + b'adapter' in header:
                    continue
            found.append({'name': path.name, 'path': path.relative_to(root).as_posix(),
                          'bytes': path.stat().st_size, 'status': 'local_file'})
        except OSError:
            continue
    return found


def import_file(root, base, relative, update, closed):
    root = Path(root).resolve()
    parsed = urllib.parse.urlparse(base)
    if parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Local model files can only be imported into a local engine.')
    base = base.rstrip('/')
    selected = next((item for item in local_files(root) if item['path'] == relative), None)
    if selected is None:
        raise ValueError('This local model file is no longer available. Refresh the model list.')
    source = root / relative
    if re.search(r'-\d{5}-of-\d{5}\.gguf$', source.name, re.I):
        raise ValueError('This is a split GGUF model. Import all its shards through Ollama first.')
    update(phase='import', message='Checking the local model file…', progress=0)
    digest = hashlib.sha256()
    original = source.stat()
    size = original.st_size
    with source.open('rb') as stream:
        done = 0
        while chunk := stream.read(8 * 1024 * 1024):
            if closed.is_set():
                raise ValueError('The app is closing')
            digest.update(chunk); done += len(chunk)
            update(progress=min(45, round(done * 45 / max(1, size))))
    current = source.stat()
    if (current.st_size, current.st_mtime_ns, current.st_ino) != (size, original.st_mtime_ns, original.st_ino):
        raise ValueError('The model file changed during import. Retry after its download finishes.')
    sha = digest.hexdigest()
    slug = re.sub(r'[^a-z0-9]+', '-', source.stem.lower()).strip('-')[:85] or 'model'
    name = 'autoproteus-local/' + slug + ':' + sha[:12]
    blob_url = base + '/api/blobs/sha256:' + sha
    blobs = root / '.data/models/blobs'
    if not blobs.resolve().is_relative_to(root):
        raise ValueError('The model cache must stay inside this project.')
    blobs.mkdir(parents=True, exist_ok=True)
    blob = blobs / ('sha256-' + sha)
    linked = False
    if not blob.exists():
        try:
            os.link(source, blob)
            linked = True
        except OSError:
            pass  # A different filesystem may require a local upload instead.
    elif blob.is_symlink() or not blob.is_file() or blob.stat().st_size != size:
        raise ValueError('An existing model cache file is invalid. Repair the cache before retrying.')
    try:
        with urllib.request.urlopen(urllib.request.Request(blob_url, method='HEAD'), timeout=5):
            present = True
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise ValueError('The local engine could not check its model cache.') from None
        present = False
    if not present:
        if linked:
            blob.unlink()  # Only the link this import created, never the source.
        if shutil.disk_usage(root).free < size + 1024**3:
            raise ValueError('There is not enough free space to copy this model into the local engine.')
        update(message='Copying the existing model into the local engine…', progress=50)
        with source.open('rb') as stream:
            request = urllib.request.Request(blob_url, data=stream, method='POST',
                headers={'Content-Type':'application/octet-stream', 'Content-Length':str(size)})
            with urllib.request.urlopen(request, timeout=600):
                pass
    # https://docs.ollama.com/api/create — files map names to blob digests.
    body = {'model': name, 'files': {source.name: 'sha256:' + sha}, 'stream': True}
    request = urllib.request.Request(base + '/api/create', data=json.dumps(body).encode(),
                                     headers={'Content-Type':'application/json'})
    update(message='Registering the local model…', progress=80)
    success = False
    with urllib.request.urlopen(request, timeout=600) as response:
        for raw in response:
            if closed.is_set():
                raise ValueError('The app is closing')
            item = json.loads(raw)
            if item.get('error'):
                raise ValueError('The local engine could not import this GGUF: ' + str(item['error'])[:300])
            success = item.get('status') == 'success' or success
    if not success:
        raise ValueError('The local model import was interrupted. The original file is unchanged.')
    receipt_path = root / '.data/local-model-imports.json'
    try:
        receipts = json.loads(receipt_path.read_text())
    except (OSError, ValueError):
        receipts = {}
    if not isinstance(receipts, dict):
        receipts = {}
    receipts[relative] = {'model': name, 'sha256': sha, 'bytes': size, 'imported': time.time()}
    atomic_json(receipt_path, receipts)
    return name
