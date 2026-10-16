"""Protected VM policy and narrow broker. No seed modules are imported here."""
from __future__ import annotations

import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import threading
import time

from .appliance import Appliance
from .errors import Cancelled, IsolationError
from .execution import ExecutionPolicy, NativeEnvironment
from .providers import DemoClient, ModelClient, ProviderError, ERROR_MESSAGES
from .storage import atomic_json

PREFIX = b'AP1 '
MAX_FRAME = 4 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024
MAX_FILES = 500
MAX_EXPORT = 32 * 1024 * 1024
MAX_WIRE = 100 * 1024 * 1024
MAX_JOURNAL = 64 * 1024 * 1024
MAX_SECONDS = 3600
SEED_TESTS = ('tests/test_seed.py', 'tests/test_text_helpers.py')
RESPONSE_RETRIES = 2


class VMLease:
    """Serialize app, evaluator and test VMs across host processes."""
    def __init__(self, directory):
        self.path = safe_path(directory, 'active-vm.lock')
        self.stream = None

    def acquire(self, cancel, deadline):
        self.stream = self.path.open('a+b')
        if not self.path.stat().st_size:
            self.stream.write(b'0'); self.stream.flush()
        while True:
            if cancel.is_set():
                raise Cancelled()
            if time.monotonic() > deadline:
                raise IsolationError('Timed out waiting for the isolated environment')
            try:
                self.stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                cancel.wait(.1)

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None


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
    for name in ('seed.py', 'SEED.md', *SEED_TESTS):
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


def vm_command(appliance, bridge_port=0):
    """Fixed policy: no disk, NIC, monitor, UI, USB, sharing, or accelerator fallback."""
    runtime = appliance.directory
    linux = appliance.linux
    result = [str(appliance.binary()),
            '-no-user-config', '-nodefaults', '-machine', 'q35', '-accel', 'kvm' if linux else 'whpx',
            '-m', '2048', '-smp', '2', '-display', 'none', '-monitor', 'none',
            '-nic', 'none', '-serial', 'none', '-no-reboot',
            '-device', 'virtio-serial-pci', '-chardev', f'socket,id=bridge,host=127.0.0.1,port={bridge_port},server=off,nodelay=on',
            '-device', 'virtserialport,chardev=bridge,name=org.autoproteus.bridge',
            '-kernel', str(runtime / 'vmlinuz'), '-initrd', str(runtime / 'initrd.gz'),
            '-append', 'console=ttyS0 quiet panic=1 rdinit=/init']
    if linux:
        result.extend(['-sandbox', 'on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny'])
    return result


class WorkerTransport:
    """Bounded pipe protocol shared by VM and opt-in native workers."""
    def __init__(self):
        self.job, self.process = None, None
        self.frames = queue.Queue(maxsize=8)
        self.stderr = bytearray()
        self.output_bytes = 0
        self.closed = threading.Event()
        self.close_lock = threading.Lock()

    def start_readers(self):
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._errors, daemon=True).start()

    def _errors(self):
        while chunk := self.process.stderr.read1(4096):
            if len(self.stderr) < 64000:
                self.stderr.extend(chunk[:64000 - len(self.stderr)])

    def _read(self):
        try:
            while not self.closed.is_set():
                raw = self.process.stdout.readline(MAX_FRAME + 1)
                if not raw:
                    raise IsolationError('The VM closed: ' + self.stderr.decode(errors='replace')[-2000:])
                self.output_bytes += len(raw)
                if len(raw) > MAX_FRAME or self.output_bytes > MAX_WIRE:
                    raise IsolationError('Guest output quota exceeded')
                if raw.startswith(PREFIX):
                    value = json.loads(raw[len(PREFIX):])
                    while not self.closed.is_set():
                        try:
                            self.frames.put(value, timeout=0.1)
                            break
                        except queue.Full:
                            pass
        except Exception as error:
            try:
                self.frames.put(error, timeout=0.1)
            except queue.Full:
                self.close()

    def send(self, value):
        raw = PREFIX + json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode() + b'\n'
        if len(raw) > MAX_FRAME:
            raise IsolationError('Host transfer is too large')
        view = memoryview(raw)
        while view and not self.closed.is_set():
            count = self.process.stdin.write(view)
            if not count:
                raise IsolationError('VM transport closed')
            view = view[count:]
        self.process.stdin.flush()

    def next(self, cancel, deadline):
        while True:
            if cancel.is_set():
                raise Cancelled()
            if time.monotonic() > deadline:
                raise IsolationError('The isolated run reached its time limit')
            try:
                value = self.frames.get(timeout=0.1)
                if isinstance(value, Exception):
                    raise value
                if not isinstance(value, dict):
                    raise IsolationError('Invalid guest message')
                return value
            except queue.Empty:
                if self.process.poll() is not None:
                    raise IsolationError('The VM could not start: ' + self.stderr.decode(errors='replace')[-2000:])

    def close(self):
        with self.close_lock:
            if self.closed.is_set():
                return
            self.closed.set()
            if self.job:
                self.job.close()
            if self.process:
                self.kill()
                self.process.wait(timeout=5)
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if stream is not None:
                        stream.close()
            self.cleanup()

    def kill(self):
        if self.process.poll() is None:
            self.process.kill()

    def cleanup(self):
        pass


class VM(WorkerTransport):
    def __init__(self, appliance):
        super().__init__()
        self.bridge = None
        linux = appliance.linux
        if linux:
            from .linux_process import Job, command
        else:
            from .windows_job import Job
        self.job = Job()
        try:
            # No provider credentials or user-selected environment is inherited.
            environment = ({'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'} if linux else
                           {key: value for key, value in os.environ.items()
                            if key.upper() in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')})
            # Windows QEMU stdio can drop input bytes. A private loopback
            # socket carries the same broker frames; the VM still has no NIC.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                if not linux:
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                listener.bind(('127.0.0.1', 0))
                listener.listen(1)
                listener.settimeout(10)
                arguments = vm_command(appliance, listener.getsockname()[1])
                if linux:
                    arguments = command(arguments[0], arguments[1:], 'vm')
                self.process = subprocess.Popen(arguments,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    cwd=appliance.directory, env=environment,
                    **({'start_new_session': True} if linux else
                       {'creationflags': subprocess.CREATE_NO_WINDOW | 0x4}))
                self.job.attach_and_resume(self.process)
                self.bridge, _ = listener.accept()
            self.bridge.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.process.stdin = self.bridge.makefile('wb', buffering=0)
            self.process.stdout = self.bridge.makefile('rb')
            self.start_readers()
        except Exception:
            self.close()
            raise

    def cleanup(self):
        if self.bridge:
            self.bridge.close()


class Broker:
    def __init__(self, store, session, client, config, cancel):
        self.store, self.session, self.client, self.cancel = store, session, client, cancel
        self.artifacts = Artifacts(store, session)
        self.requests, self.frames = 0, 0
        # Each action response and the free final response can need two repairs.
        # This ceiling stays host-owned even if an edited seed ignores its policy.
        self.request_limit = (min(config['max_steps'], 200) + 1) * (RESPONSE_RETRIES + 1)
        self.finished = False
        self.last_status = 'running'
        if isinstance(client, ModelClient) and client.observer is not None:
            client.observation_context = self.inference_context

    def inference_context(self, messages):
        """Host snapshot comparisons describe omissions, not the seed's reasons."""
        def signature(item):
            return json.dumps({key: item[key] for key in ('role', 'content')}, ensure_ascii=False, sort_keys=True)
        history = Counter(signature(item) for item in self.session.get('messages', []))
        selected = Counter(signature(item) for item in messages)
        return {'session': self.session['id'], 'seed_sha256': self.session.get('seed_sha256'),
                'seed_version': self.session.get('seed_version'), 'request_index': self.requests,
                'host_history_messages': sum(history.values()),
                'host_history_messages_omitted': sum((history - selected).values()),
                'neutral_message_count': len(messages), 'neutral_messages_sha256':
                    hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}

    def handle(self, frame):
        if self.cancel.is_set():
            raise Cancelled()
        self.frames += 1
        if self.frames > 10000:
            raise IsolationError('Guest message quota exceeded')
        op = frame.get('op')
        if op == 'infer' and set(frame) in ({'op', 'messages'}, {'op', 'messages', 'tools'}):
            messages = frame['messages']
            if (not isinstance(messages, list) or not 1 <= len(messages) <= 400 or
                    any(not isinstance(m, dict) or set(m) != {'role', 'content'} or
                        m['role'] not in ('system', 'user', 'assistant') or not isinstance(m['content'], str)
                        for m in messages) or len(json.dumps(messages).encode()) > 1500000):
                raise IsolationError('Invalid model request')
            self.requests += 1
            if self.requests > self.request_limit:
                raise IsolationError('Model request quota exceeded')
            tools = frame.get('tools')
            if tools is not None:
                if (not isinstance(tools, list) or not 1 <= len(tools) <= 64 or len(json.dumps(tools).encode()) > 150000
                        or any(not isinstance(t, dict) or t.get('type') != 'function' or not isinstance(t.get('function'), dict)
                               or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', str(t['function'].get('name', '')))
                               or not isinstance(t['function'].get('parameters'), dict) for t in tools)):
                    raise IsolationError('Invalid guest tool descriptions')
            try:
                if isinstance(self.client, ModelClient):
                    # Schemas are data for the model, never host-executable capabilities.
                    return self.client.complete(messages, self.cancel, tools=tools)
                return self.client.complete(messages, self.cancel)
            except Cancelled:
                raise
            except ProviderError as error:
                if error.category == 'cutoff':
                    # Discard partial text/calls. Only a fixed marker crosses the
                    # boundary; the seed can spend its bounded format retries.
                    self.store.event(self.session, 'provider_cutoff', {'partial_action_executed': False})
                    return {'content': '', 'provider_error': 'cutoff'}
                self.session['error_category'] = error.category
                raise IsolationError(ERROR_MESSAGES[error.category]) from None
            except Exception:
                # Provider errors can echo headers or credentials. Keep them on the host.
                raise IsolationError('The configured model service could not complete this request. Check the host connection.') from None
        if op == 'file' and set(frame) == {'op', 'path', 'data'}:
            self.artifacts.put(frame['path'], frame['data'])
        elif op == 'checkpoint' and set(frame) == {'op', 'paths'}:
            self.artifacts.checkpoint(frame['paths'])
        elif op == 'state' and set(frame) in ({'op', 'session'}, {'op', 'session', 'changes'}):
            value = frame['session']
            if 'changes' in frame:
                changes = frame['changes']
                if (not isinstance(value, dict) or {'messages', 'feed'} & value.keys() or
                        not isinstance(changes, dict) or set(changes) != {'messages', 'feed'}):
                    raise IsolationError('Invalid history changes')
                value = dict(value)
                for name in ('messages', 'feed'):
                    change = changes[name]
                    previous = self.session.get(name, [])
                    if (not isinstance(change, dict) or set(change) != {'prefix', 'items'} or
                            type(change['prefix']) is not int or not 0 <= change['prefix'] <= len(previous) or
                            not isinstance(change['items'], list) or change['prefix'] + len(change['items']) > 2000):
                        raise IsolationError('Invalid history changes')
                    value[name] = previous[:change['prefix']] + change['items']
            if not isinstance(value, dict) or len(json.dumps(value).encode()) > 1500000:
                raise IsolationError('Session state too large')
            fields = {'status', 'activity', 'messages', 'feed', 'steps', 'runs', 'todo', 'seed_version', 'seed_sha256'}
            if value.get('status') not in ('ready', 'running', 'stopping', 'paused', 'interrupted', 'completed', 'waiting', 'error'):
                raise IsolationError('Invalid session status')
            for name in ('activity', 'todo'):
                if not isinstance(value.get(name, ''), str) or len(value.get(name, '')) > 12000:
                    raise IsolationError('Invalid session text')
            for name in ('messages', 'feed'):
                if not isinstance(value.get(name), list) or len(value[name]) > 2000:
                    raise IsolationError('Invalid session history')
            for item in value['messages']:
                if not isinstance(item, dict) or item.get('role') not in ('system', 'user', 'assistant') or not isinstance(item.get('content'), str):
                    raise IsolationError('Invalid history message')
            for item in value['feed']:
                if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or len(item['id']) > 64
                        or item.get('kind') not in ('user', 'assistant', 'notice', 'action', 'result', 'error')
                        or not isinstance(item.get('text'), str)):
                    raise IsolationError('Invalid display message')
            if len({item['id'] for item in value['feed']}) != len(value['feed']):
                raise IsolationError('Duplicate display message IDs')
            for name in ('steps', 'runs'):
                if type(value.get(name)) is not int or not 0 <= value[name] <= 100000:
                    raise IsolationError('Invalid session counter')
            for name in ('seed_version', 'seed_sha256'):
                if name in value and (not isinstance(value[name], str) or len(value[name]) > 100):
                    raise IsolationError('Invalid seed metadata')
            self.last_status = value['status']
            # Stop stays visible until the host has ended the VM.
            fields.remove('status')
            self.session.update({key: value[key] for key in fields if key in value})
            self.session['status'] = 'running'
            self.store.save(self.session)
        elif op == 'event' and set(frame) == {'op', 'type', 'data'}:
            if not isinstance(frame['type'], str) or len(frame['type']) > 60 or len(json.dumps(frame['data']).encode()) > 1500000:
                raise IsolationError('Invalid journal event')
            journal = self.store.directory(self.session['id']) / 'events.jsonl'
            if journal.stat().st_size + len(json.dumps(frame).encode()) > MAX_JOURNAL:
                raise IsolationError('Session journal quota exceeded')
            self.store.event(self.session, frame['type'], frame['data'])
        elif op == 'done' and set(frame) == {'op'}:
            self.finished = True
        elif op == 'failure' and set(frame) == {'op', 'message'}:
            raise IsolationError('Guest stopped: ' + str(frame['message'])[:2000])
        else:
            raise IsolationError('Guest requested an unsupported host operation')
        return None


class IsolatedAgent:
    def __init__(self, root, store, settings, client_factory=None, execution=None):
        self.root, self.store, self.settings = Path(root).resolve(), store, settings
        self.execution = execution or ExecutionPolicy()
        self.appliance = NativeEnvironment(self.root) if self.execution.mode == 'native' else Appliance(self.root)
        self.client_factory = client_factory
        self.workers, self.vms = {}, {}
        self.lock = threading.RLock()

    def start(self, session, message=None, candidate=None, verification=False, handoff='full'):
        if handoff not in ('full', 'concise'):
            raise ValueError('Choose full or concise activation context')
        with self.lock:
            if any(thread.is_alive() for _, thread in self.workers.values()):
                raise IsolationError('Stop the current task before starting another isolated run')
            self.appliance.verify()
            config = dict(self.settings.values)
            if not config['configured']:
                raise ValueError('Connect a model first')
            client = self.client_factory(config) if self.client_factory else (DemoClient() if config['provider'] == 'demo' else ModelClient(config, self.settings.key()))
            inputs = Artifacts(self.store, session).pack() if 'artifacts' in session else packed_files(session['workspace'])
            source = seed_files(self.root)
            if candidate:
                source = [{'path': item['path'][8:], 'data': item['data']} for item in Artifacts(self.store, candidate).pack() if item['path'].startswith('harness/')]
                if not {'seed.py', 'autoproteus/agent.py'}.issubset({item['path'] for item in source}):
                    raise IsolationError('This candidate is missing seed.py or autoproteus/agent.py')
            elif session.get('candidate_from'):
                source = json.loads((self.store.directory(session['id']) / 'candidate.json').read_text(encoding='utf-8'))
            if verification:
                source = [item for item in source if not item['path'].startswith('__verify__/')]
                for name in SEED_TESTS:
                    source.append({'path': '__verify__/' + Path(name).name, 'data': base64.b64encode(
                        (self.root / name).read_bytes()).decode()})
            guest_config = {key: value for key, value in config.items() if key not in ('base_url', 'api_key')}
            guest_config['response_retries'] = RESPONSE_RETRIES
            boot = {'op': 'boot', 'seed': source, 'files': inputs, 'session': dict(session),
                    'config': guest_config, 'message': message, 'seed_activated': candidate is session,
                    'handoff': handoff}
            boot['verification'] = bool(verification)
            if isinstance(verification, dict):
                boot['behavior_rules'] = verification['rules']
            # Do not send host directories, credentials, or quarantine metadata.
            boot['session'].pop('artifacts', None)
            boot['session']['workspace'] = '/work/task'
            boot['session']['execution_mode'] = self.execution.mode
            boot['session'].pop('isolation', None)
            if len(json.dumps({key: value for key, value in boot.items() if key not in ('seed', 'files')}).encode()) > MAX_FRAME - 100:
                raise IsolationError('Session history exceeds the restore limit')
            if candidate:
                # Freeze only after input validation; candidate bytes never run here.
                atomic_json(self.store.directory(session['id']) / 'candidate.json', source)
            session.update(status='running', activity='Starting the virtual machine…' if self.execution.mode == 'vm'
                           else 'Starting without AutoProteus VM protection…',
                           isolation=self.execution.mode == 'vm', execution_mode=self.execution.mode)
            history = session.setdefault('execution_history', [])
            history.append({'mode': self.execution.mode, 'isolated': session['isolation']})
            del history[:-200]
            self.store.save(session)
            self.store.event(session, 'execution_started', self.execution.public())
            cancel = threading.Event()
            thread = threading.Thread(target=self._run, args=(session, boot, client, config, cancel), daemon=True)
            self.workers[session['id']] = cancel, thread
            thread.start()

    def restart_seed(self, session, handoff='full'):
        """Explicit controller action: activate this checkpoint in the same task."""
        with self.lock:
            previous = session.get('candidate_from')
            session['candidate_from'] = session['id']
            try:
                self.start(session, candidate=session, handoff=handoff)
            except Exception:
                if previous is None:
                    session.pop('candidate_from', None)
                else:
                    session['candidate_from'] = previous
                raise

    def _run(self, session, boot, client, config, cancel):
        vm, broker = None, Broker(self.store, session, client, config, cancel)
        lease = None
        # Host deadline covers boot, inference, commands and all guest code.
        deadline = time.monotonic() + MAX_SECONDS
        try:
            lease = VMLease(self.appliance.directory)
            lease.acquire(cancel, deadline)
            if self.execution.mode == 'native':
                from .native import NativeWorker
                vm = NativeWorker(self.root, self.execution)
            else:
                vm = VM(self.appliance)
            with self.lock:
                self.vms[session['id']] = vm
                if cancel.is_set():
                    raise Cancelled()
            ready = vm.next(cancel, min(deadline, time.monotonic() + 90))
            if ready != {'op': 'ready', 'protocol': 2}:
                raise IsolationError('Guest handshake failed')
            # A blocked guest reader cannot stall the external watchdog or Stop.
            threading.Thread(target=lambda: self._watchdog(vm, cancel, deadline), daemon=True).start()
            vm.send({key: value for key, value in boot.items() if key not in ('seed', 'files')})
            if vm.next(cancel, deadline) != {'op': 'input_ready'}:
                raise IsolationError('Guest did not accept the boot request')
            for area, files in (('seed', boot['seed']), ('workspace', boot['files'])):
                for item in files:
                    checksum = hashlib.sha256(base64.b64decode(item['data'], validate=True)).hexdigest()
                    vm.send({'op': 'input', 'area': area, **item, 'sha256': checksum})
                    reply = vm.next(cancel, deadline)
                    if reply != {'op': 'input_saved'}:
                        raise IsolationError('Guest input transfer failed: ' + str(reply)[:1500])
            vm.send({'op': 'inputs_done'})
            while not broker.finished:
                frame = vm.next(cancel, deadline)
                value = broker.handle(frame)
                vm.send({'op': 'reply', 'value': value})
            if broker.last_status in ('running', 'stopping', 'ready'):
                raise IsolationError('The guest exited without a final session status')
            session['status'] = broker.last_status
        except Cancelled:
            session.update(status='paused', activity='Stopped. The last saved checkpoint is ready to resume.')
        except Exception as error:
            if cancel.is_set():
                session.update(status='paused', activity='Stopped. Your saved checkpoint is ready to resume.')
            else:
                session.update(status='error', activity='The isolated run stopped')
                self.store.feed(session, 'notice', str(error)[:3000])
        finally:
            try:
                if vm:
                    vm.close()
            finally:
                if lease:
                    lease.close()
            with self.lock:
                self.vms.pop(session['id'], None)
            broker.artifacts.pending = {}
            broker.artifacts.cleanup()
            session['model_requests'] = broker.requests
            self.store.save(session)

    def _watchdog(self, vm, cancel, deadline):
        while not vm.closed.wait(0.1):
            if cancel.is_set() or time.monotonic() > deadline:
                vm.close()
                return

    def stop(self, session_id):
        with self.lock:
            worker = self.workers.get(session_id)
            if worker and worker[1].is_alive():
                worker[0].set()
                vm = self.vms.get(session_id)
                if vm:
                    vm.close()

    def export_for_checks(self, session):
        """Trusted evaluator reads bytes only; it never runs exported verifier code."""
        artifacts = Artifacts(self.store, session)
        for name in session.get('artifacts', {}):
            path = safe_path(session['workspace'], name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(artifacts.read(name))

    def close(self):
        for session_id in list(self.workers):
            self.stop(session_id)
        for _, thread in list(self.workers.values()):
            thread.join(timeout=5)
