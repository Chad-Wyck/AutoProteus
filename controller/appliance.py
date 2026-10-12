"""Build a pinned, diskless Linux appliance. Only trusted release files enter it."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
import threading
import urllib.request
from pathlib import Path

from .errors import IsolationError
from .storage import atomic_json


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(stream.read()).hexdigest()


def cpio(entries):
    """newc archive in memory; Linux links/devices are never extracted on Windows."""
    result = bytearray()
    for number, (name, (mode, data)) in enumerate(list(sorted(entries.items())) + [('TRAILER!!!', (0, b''))], 1):
        filename = name.encode() + b'\0'
        fields = (number, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(filename), 0)
        result.extend(b'070701' + ''.join(f'{value:08x}' for value in fields).encode() + filename)
        result.extend(b'\0' * (-len(result) % 4))
        result.extend(data)
        result.extend(b'\0' * (-len(result) % 4))
    return bytes(result)


INIT = b'''#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts /run /work /seed
mount -t devpts devpts /dev/pts
ip link set lo up
mount -t tmpfs -o size=512m,nosuid,nodev tmpfs /work
mount -t tmpfs -o size=64m,nosuid,nodev tmpfs /run
while [ ! -e /dev/vport0p1 ]; do sleep 0.05; done
exec /usr/bin/python3 -u /guest.py >/dev/null 2>/dev/null
'''


def build_initrd(root, cache, destination):
    entries = {}
    for path in [cache / 'rootfs.tar.gz', *sorted(cache.glob('*.apk'))]:
        raw = gzip.decompress(path.read_bytes())
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:', ignore_zeros=True) as archive:
            links = []
            for item in archive:
                name = item.name.removeprefix('./').rstrip('/')
                if not name or name.startswith('.'):
                    continue
                if path.name == 'linux-virt.apk' and name != 'boot/vmlinuz-virt':
                    continue
                if name.startswith('/') or '..' in name.split('/'):
                    raise IsolationError('Unsafe release archive')
                if item.isfile():
                    entries[name] = (stat.S_IFREG | item.mode, archive.extractfile(item).read())
                elif item.isdir():
                    entries[name] = (stat.S_IFDIR | item.mode, b'')
                elif item.issym():
                    entries[name] = (stat.S_IFLNK | item.mode, item.linkname.encode())
                elif item.islnk():
                    links.append((name, item.linkname.removeprefix('./')))
            for name, target in links:
                entries[name] = entries[target]
    for folder in ('proc', 'sys', 'dev', 'work', 'run', 'seed'):
        entries[folder] = (stat.S_IFDIR | 0o755, b'')
    entries['init'] = (stat.S_IFREG | 0o755, INIT)
    entries['guest.py'] = (stat.S_IFREG | 0o644, (root / 'guest/worker.py').read_bytes())
    # Use the exact kernel corresponding to the bundled modules.
    if 'boot/vmlinuz-virt' in entries:
        (destination.parent / 'vmlinuz').write_bytes(entries['boot/vmlinuz-virt'][1])
    destination.write_bytes(gzip.compress(cpio(entries), compresslevel=6, mtime=0))


def hypervisor_available():
    if os.name != 'nt':
        return False
    import ctypes
    try:
        dll = ctypes.WinDLL('WinHvPlatform.dll')
        fn = dll.WHvGetCapability
        fn.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        fn.restype = ctypes.c_long
        value, written = ctypes.c_uint64(), ctypes.c_uint32()
        return fn(0, ctypes.byref(value), 8, ctypes.byref(written)) == 0 and bool(value.value)
    except OSError:
        return False


class Appliance:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / '.runtime/isolation'
        self.cache = self.root / '.runtime/isolation-downloads'
        self.lock = threading.Lock()
        self.busy, self.message, self.error = False, '', ''

    def public(self):
        available = hypervisor_available()
        installed = (self.directory / 'installed.json').exists()
        if installed:
            try:
                record = json.loads((self.directory / 'installed.json').read_text(encoding='utf-8'))
                installed = record.get('guest_sha256') == digest(self.root / 'guest/worker.py') and record.get('lock_sha256') == digest(self.root / 'controller/runtime-lock.json')
            except (ValueError, OSError):
                installed = False
        return {'ready': available and installed and not self.busy, 'available': available,
                'installed': installed, 'busy': self.busy, 'message': self.message or (
                    'Isolation is ready' if available and installed else
                    'Prepare the isolated environment' if available else
                    'Enable Windows Hypervisor Platform in Windows Features, restart, then reopen AutoProteus.'),
                'error': self.error, 'backend': 'QEMU / Windows Hypervisor Platform',
                'memory_mb': 2048, 'cpus': 2, 'workspace_mb': 512, 'network': False}

    def prepare(self):
        with self.lock:
            if self.busy:
                return
            if not hypervisor_available():
                raise IsolationError(self.public()['message'])
            self.busy, self.error = True, ''
        threading.Thread(target=self._prepare, daemon=True).start()

    def _prepare(self):
        try:
            self.install()
            self.message = 'Isolation is ready'
        except Exception as error:
            self.error = str(error)
            self.message = 'Isolation setup needs attention'
        finally:
            self.busy = False

    def install(self):
        self.cache.mkdir(parents=True, exist_ok=True)
        self.directory.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((self.root / 'controller/runtime-lock.json').read_text(encoding='utf-8'))
        for index, item in enumerate(manifest['sources']):
            self.message = f"Preparing the isolated environment ({index + 1}/{len(manifest['sources'])})…"
            target = self.cache / item['name']
            if not target.exists() or digest(target) != item['sha256']:
                temporary = target.with_suffix('.download')
                with urllib.request.urlopen(item['url'], timeout=60) as response, temporary.open('wb') as output:
                    total = 0
                    while chunk := response.read(1048576):
                        total += len(chunk)
                        if total > 250000000:
                            raise IsolationError('Runtime download exceeded its size limit')
                        output.write(chunk)
                if digest(temporary) != item['sha256']:
                    temporary.unlink(missing_ok=True)
                    raise IsolationError('Runtime download failed its integrity check')
                temporary.replace(target)
        seven = self.directory / '7zip'
        qemu = self.directory / 'qemu'
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        subprocess.run([str(self.cache / '7zr.exe'), 'x', '-y', '-o' + str(seven),
                        str(self.cache / '7z-x64.exe'), '7z.exe', '7z.dll'],
                       check=True, stdout=subprocess.DEVNULL, creationflags=flags)
        subprocess.run([str(seven / '7z.exe'), 'x', '-y', '-o' + str(qemu), str(self.cache / 'qemu.exe'),
                        'qemu-system-x86_64.exe', '*.dll', 'share/*', 'COPYING*'],
                       check=True, stdout=subprocess.DEVNULL, creationflags=flags)
        (self.directory / 'vmlinuz').write_bytes((self.cache / 'vmlinuz-virt').read_bytes())
        build_initrd(self.root, self.cache, self.directory / 'initrd.gz')
        files = [self.directory / 'vmlinuz', self.directory / 'initrd.gz', *qemu.rglob('*')]
        atomic_json(self.directory / 'installed.json', {
            'lock_sha256': digest(self.root / 'controller/runtime-lock.json'),
            'guest_sha256': digest(self.root / 'guest/worker.py'),
            'files': {p.relative_to(self.directory).as_posix(): digest(p) for p in files if p.is_file()}})

    def verify(self):
        if not hypervisor_available():
            raise IsolationError(self.public()['message'])
        try:
            record = json.loads((self.directory / 'installed.json').read_text(encoding='utf-8'))
            if record['lock_sha256'] != digest(self.root / 'controller/runtime-lock.json') or record['guest_sha256'] != digest(self.root / 'guest/worker.py'):
                raise IsolationError('Prepare isolation again to update the guest runtime')
            for name, expected in record['files'].items():
                path = (self.directory / name).resolve()
                if not path.is_relative_to(self.directory) or digest(path) != expected:
                    raise IsolationError('The isolated runtime failed its integrity check. Prepare it again.')
        except (OSError, KeyError, ValueError) as error:
            raise IsolationError('Prepare the isolated environment before starting a task. ' + str(error)) from None

    def rebuild_guest(self):
        """Development helper: rebuild trusted guest bootstrap, never candidate code."""
        build_initrd(self.root, self.cache, self.directory / 'initrd.gz')
        record = json.loads((self.directory / 'installed.json').read_text(encoding='utf-8'))
        record['guest_sha256'] = digest(self.root / 'guest/worker.py')
        for name in ('vmlinuz', 'initrd.gz'):
            record['files'][name] = digest(self.directory / name)
        atomic_json(self.directory / 'installed.json', record)
