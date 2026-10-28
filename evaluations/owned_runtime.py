"""Opt-in, host-owned inference lifecycle for studies. Never executes guest code."""
from contextlib import contextmanager
import ctypes
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from controller.storage import atomic_json, now
from study_support import file_identity

GIB = 1024**3
ROOT = Path(__file__).resolve().parents[1]


def memory():
    if os.name == 'nt':
        class Status(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ('total_physical', 'available_physical',
                    'total_commit', 'available_commit', 'total_virtual', 'available_virtual', 'extended')]
        value = Status(); value.length = ctypes.sizeof(value)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            raise OSError('Could not read Windows memory headroom')
        return {name: getattr(value, name) for name in ('available_physical', 'available_commit')}
    values = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, _, text = line.partition(':')
        values[key] = int(text.strip().split()[0]) * 1024
    # Linux commit accounting has different overcommit semantics. Do not
    # present CommitLimit-Committed_AS as available physical memory.
    return {'available_physical': values['MemAvailable'], 'available_commit': None}


def validate(spec, config, assets):
    allowed = {'command', 'cwd', 'health_path', 'metadata_path', 'reported_seed_path',
               'reported_context_path', 'startup_seconds', 'minimum_start_bytes', 'memory_floor_bytes', 'initial_seed'}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ValueError('Invalid owned-runtime settings')
    command = spec.get('command')
    if (not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg or '\x00' in arg for arg in command)
            or not Path(command[0]).is_absolute() or not Path(command[0]).is_file()):
        raise ValueError('Runtime command needs an existing absolute executable and separate arguments; no shell')
    if not any(Path(path).resolve() == Path(command[0]).resolve() for path in assets):
        raise ValueError('Pin the runtime executable in profile assets')
    if sum(arg.count('{seed}') for arg in command) != 1 or sum(arg.count('{port}') for arg in command) != 1:
        raise ValueError('Runtime command needs exactly one {seed} and one {port} placeholder')
    endpoint = urlsplit(config['base_url'])
    if endpoint.scheme != 'http' or endpoint.hostname not in ('127.0.0.1', '::1') or not endpoint.port or endpoint.username or endpoint.password:
        raise ValueError('Owned runtimes require an explicit numeric loopback HTTP endpoint and port')
    if spec.get('cwd') and (not Path(spec['cwd']).is_absolute() or not Path(spec['cwd']).is_dir()):
        raise ValueError('Runtime cwd must be an existing absolute directory')
    for key, default in (('health_path', '/health'), ('metadata_path', '/props')):
        path = spec.get(key, default)
        if path is not None and (not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path):
            raise ValueError('Runtime probe paths must stay on the dedicated loopback endpoint')
    if spec.get('health_path', '/health') is None:
        raise ValueError('Runtime health path is required')
    for key in ('reported_seed_path', 'reported_context_path'):
        if key in spec and (not isinstance(spec[key], str) or not spec[key] or spec.get('metadata_path', '/props') is None):
            raise ValueError('Reported runtime settings need a metadata path and dotted field name')
    for key, default in (('startup_seconds', 300), ('minimum_start_bytes', 4*GIB), ('memory_floor_bytes', 2*GIB)):
        value = spec.get(key, default)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Runtime limits must be finite positive numbers')
    if spec.get('minimum_start_bytes', 4*GIB) < spec.get('memory_floor_bytes', 2*GIB):
        raise ValueError('Starting memory headroom must cover the running floor')
    seed = spec.get('initial_seed', 1729)
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError('Invalid initial runtime seed')


class AssetPins:
    """Hash once per study invocation; watch sizes/timestamps during attempts."""
    def __init__(self, assets):
        self.assets, self.stats = dict(assets), {}
        for path, digest in self.assets.items():
            if file_identity(path) != digest:
                raise ValueError('Runtime asset failed verification: ' + path)
            info = Path(path).stat()
            self.stats[path] = (info.st_size, info.st_mtime_ns)
        self.verified = now()

    def guard(self):
        for path, expected in self.stats.items():
            info = Path(path).stat()
            if (info.st_size, info.st_mtime_ns) != expected:
                raise RuntimeError('Pinned runtime asset changed: ' + path)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ValueError('Runtime probes do not follow redirects')


class OwnedRuntime:
    def __init__(self, folder, spec, config, pins, task_seconds, memory_reader=memory):
        validate(spec, config, pins.assets)
        self.folder, self.spec, self.config, self.pins = Path(folder), dict(spec), dict(config), pins
        self.read_memory = memory_reader
        self.process = self.job = self.monitor = None
        self.logs = []
        self.done = threading.Event(); self.stop_lock = threading.Lock()
        self.reason = None; self.record = {}; self.closed = False; self.created = False
        self.startup = spec.get('startup_seconds', 300)
        if type(task_seconds) not in (int, float) or not math.isfinite(task_seconds) or task_seconds <= 0:
            raise ValueError('Owned runtime needs a positive task allowance')
        self.lifetime = self.startup + task_seconds + 30
        endpoint = urlsplit(config['base_url'])
        self.host, self.port = endpoint.hostname, endpoint.port
        self.base = f'http://[{self.host}]:{self.port}' if ':' in self.host else f'http://{self.host}:{self.port}'
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def read(self, path):
        with self.http.open(self.base + path, timeout=1) as response:
            raw = response.read(1024*1024+1)
            if len(raw) > 1024*1024: raise ValueError('Runtime metadata exceeds 1 MiB')
            return json.loads(raw)

    def guard(self):
        if self.reason: raise RuntimeError(self.reason)
        self.pins.guard()
        if self.process and self.process.poll() is not None:
            raise RuntimeError('Owned inference service exited')

    def _stop(self):
        with self.stop_lock:
            if self.job:
                job, self.job = self.job, None
                job.close()
            if self.process and self.process.poll() is None:
                if os.name != 'nt':
                    import signal
                    os.killpg(self.process.pid, signal.SIGKILL)
                else:
                    self.process.kill()
            if self.process:
                self.process.wait(timeout=10)

    def watch(self):
        with (self.folder/'memory.jsonl').open('w', encoding='utf-8') as stream:
            while not self.done.wait(.5):
                try:
                    sample = {'time': now(), **self.read_memory()}
                    stream.write(json.dumps(sample)+'\n'); stream.flush()
                    self.guard()
                    if min(value for key, value in sample.items() if key.startswith('available_') and value is not None) < self.spec.get('memory_floor_bytes', 2*GIB):
                        raise RuntimeError('Memory floor reached; owned inference stopped')
                    if time.monotonic()-self.began >= self.lifetime:
                        raise RuntimeError('Owned inference lifetime expired')
                except Exception as error:
                    if self.done.is_set(): return  # Normal cleanup is not a resource failure.
                    self.reason = self.reason or str(error)
                    self._stop()
                    return

    def start(self):
        self.folder.mkdir(parents=True, exist_ok=False)
        self.created = True
        self.began = time.monotonic()
        seed = self.config.get('server_initial_seed', self.config.get('sampling_seed'))
        if seed is None: seed = self.spec.get('initial_seed', 1729)
        if type(seed) is not int or not 0 <= seed <= 2147483647:
            self.reason = 'Invalid initial runtime seed'
            self.close()
            raise ValueError(self.reason)
        values = {'{seed}': str(seed), '{port}': str(self.port), '{context_tokens}': str(self.config['context_tokens'])}
        command = list(self.spec['command'])
        for marker, value in values.items(): command = [arg.replace(marker, value) for arg in command]
        self.record = {'started': now(), 'command': command, 'cwd': self.spec.get('cwd', str(ROOT)),
            'fresh_server': False, 'initial_server_seed': seed, 'reported_seed_matches': None,
            'request_seed': self.config.get('sampling_seed'), 'assets': self.pins.assets, 'assets_verified': self.pins.verified,
            'scope': 'Owned launch and optional reported settings; neither proves RNG determinism or provider honoring. '
                     'Startup is outside the task allowance. During-run asset checks use sizes/timestamps.'}
        atomic_json(self.folder/'launch.json', self.record)
        try:
            self.pins.guard()
            before = self.read_memory(); atomic_json(self.folder/'before-load.json', before)
            if min(value for value in before.values() if value is not None) < self.spec.get('minimum_start_bytes', 4*GIB):
                raise RuntimeError('Insufficient memory headroom for owned inference startup')
            family = socket.AF_INET6 if ':' in self.host else socket.AF_INET
            with socket.socket(family) as probe:
                probe.settimeout(1)
                if probe.connect_ex((self.host, self.port)) == 0:
                    raise RuntimeError('Dedicated inference port is already occupied; existing service left alone')
            if os.name == 'nt':
                from controller.windows_job import Job
                self.job = Job(vm_limits=False)
                arguments, options = command, {'creationflags': subprocess.CREATE_NO_WINDOW | 0x4}
            else:
                from controller.linux_process import Job, command as supervised
                self.job = Job()
                arguments, options = supervised(command[0], command[1:], 'engine'), {'start_new_session': True}
            self.logs = [(self.folder/name).open('wb') for name in ('stdout.log', 'stderr.log')]
            self.process = subprocess.Popen(arguments, cwd=self.record['cwd'], stdout=self.logs[0], stderr=self.logs[1], **options)
            self.job.attach_and_resume(self.process)
            self.record['pid'] = self.process.pid
            self.record['fresh_server'] = True
            atomic_json(self.folder/'launch.json', self.record)
            self.monitor = threading.Thread(target=self.watch, daemon=True); self.monitor.start()
            while time.monotonic()-self.began < self.startup:
                self.guard()
                try:
                    health = self.read(self.spec.get('health_path', '/health'))
                    if health.get('status') == 'ok': break
                except (OSError, ValueError, urllib.error.URLError): pass
                self.done.wait(.2)
            else: raise RuntimeError('Owned inference startup timed out')
            metadata = self.read(self.spec.get('metadata_path', '/props')) if self.spec.get('metadata_path', '/props') else None
            for setting, expected in (('seed', seed), ('context', self.config['context_tokens'])):
                path = self.spec.get('reported_'+setting+'_path')
                if path:
                    actual = metadata
                    for part in path.split('.'): actual = actual.get(part) if isinstance(actual, dict) else None
                    self.record['reported_'+setting+'_matches'] = type(actual) is int and actual == expected
                    if not self.record['reported_'+setting+'_matches']:
                        raise RuntimeError('Runtime did not report the requested '+setting)
            self.guard()
            self.record['load_seconds'] = round(time.monotonic()-self.began, 6)
            atomic_json(self.folder/'ready.json', {**self.record, 'health': health, 'metadata': metadata})
            return self
        except BaseException as error:
            self.reason = self.reason or str(error)
            self.close()
            raise

    def close(self):
        if self.closed: return
        if not self.created:
            self.closed = True
            return
        self.done.set()
        try:
            self._stop()
        finally:
            if self.monitor and self.monitor is not threading.current_thread(): self.monitor.join(timeout=3)
            for log in self.logs: log.close()
            self.closed = True
            atomic_json(self.folder/'cleanup.json', {'finished': now(), 'reason': self.reason,
                'owned_process_stopped': self.process is None or self.process.poll() is not None})


class RuntimeOwner:
    def __init__(self, profile):
        self.spec = profile['runtime']
        validate(self.spec, profile['config'], profile.get('assets', {}))
        self.pins = AssetPins(profile.get('assets', {}))

    @contextmanager
    def attempt(self, folder, config, seconds):
        runtime = OwnedRuntime(Path(folder)/'runtime', self.spec, config, self.pins, seconds)
        try:
            runtime.start()
            yield runtime
            runtime.guard()
        finally:
            runtime.close()
