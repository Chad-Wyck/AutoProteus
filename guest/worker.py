"""Runs inside the VM only. Every byte sent back is untrusted by the host."""
import base64
import hashlib
import io
import json
import os
import resource
from pathlib import Path
import stat
import sys
import threading
import time

PREFIX = b'AP1 '
MAX_FRAME = 4 * 1024 * 1024
channel = open('/dev/vport0p1', 'r+b', buffering=0)
reader = io.BufferedReader(channel)
lock = threading.RLock()


def send(value):
    raw = PREFIX + json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode() + b'\n'
    if len(raw) > MAX_FRAME:
        raise ValueError('Guest frame too large')
    view = memoryview(raw)
    while view:
        written = channel.write(view)
        if not written:
            raise RuntimeError('Host channel closed')
        view = view[written:]


def receive():
    raw = reader.readline(MAX_FRAME + 1)
    if not raw or len(raw) > MAX_FRAME:
        raise ValueError('Host frame too large or closed')
    if not raw.startswith(PREFIX):
        raise ValueError('Invalid host frame')
    return json.loads(raw[len(PREFIX):])


def call(value):
    with lock:
        send(value)
        reply = receive()
        if reply.get('op') != 'reply':
            raise ValueError('Invalid host reply')
        if reply.get('error'):
            raise ValueError(reply['error'])
        return reply.get('value')


def unpack(files, root):
    for item in files:
        path = (root / item['path']).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError('Invalid input path')
        data = base64.b64decode(item['data'], validate=True)
        if hashlib.sha256(data).hexdigest() != item.get('sha256'):
            raise ValueError('Input integrity check failed: ' + item['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def run_verification(boot, source, workspace):
    # The protected parent keeps the broker fd. Tests run in another process as
    # UID 1000 against root-owned starter tests and the candidate's modules.
    import re
    import signal
    import subprocess
    import tempfile
    os.chmod('/dev/vport0p1', 0o600)
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'PYTHONPATH': str(source),
           'AUTOPROTEUS_GUEST': '1', 'AUTOPROTEUS_TEST_ROOT': str(workspace / 'test-tmp')}
    with tempfile.TemporaryFile(dir='/run') as output:
        process = subprocess.Popen(['/usr/bin/python3', '-m', 'unittest', 'discover',
                                    '-s', str(source / '__verify__'), '-v'],
            cwd=workspace, env=env, stdin=subprocess.DEVNULL, stdout=output,
            stderr=subprocess.STDOUT, user=1000, group=1000, extra_groups=[],
            close_fds=True, start_new_session=True)
        deadline = time.monotonic() + 60
        limited = False
        while process.poll() is None:
            if time.monotonic() > deadline or os.fstat(output.fileno()).st_size > 256000:
                limited = True
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(.05)
        process.wait(timeout=5)
        output.seek(0)
        log = output.read(32000).decode('utf-8', errors='replace')
    count = re.search(r'Ran (\d+) tests?', log)
    expected = len(re.findall(r'^    def test_', (source / '__verify__/test_seed.py').read_text(), re.M))
    result = {'passed': process.returncode == 0 and not limited and bool(count)
                       and int(count[1]) == expected and bool(re.search(r'^OK', log, re.M)),
              'tests': int(count[1]) if count else 0, 'expected': expected,
              'exit_code': process.returncode, 'limited': limited, 'output': log}
    call({'op':'file', 'path':'regression-result.json',
          'data':base64.b64encode(json.dumps(result).encode()).decode()})
    call({'op':'checkpoint', 'paths':['regression-result.json']})
    session = boot['session']
    session.update(status='completed', activity='Guest regression checks finished', runs=1)
    call({'op':'state', 'session':session})
    call({'op':'done'})
    while True:
        time.sleep(1)


def main():
    send({'op': 'ready', 'protocol': 2})
    boot = receive()
    if boot.get('op') != 'boot':
        raise ValueError('Expected boot message')
    source, workspace = Path('/seed'), Path('/work/task')
    workspace.mkdir()
    send({'op': 'input_ready'})
    while True:
        item = receive()
        if item.get('op') == 'inputs_done':
            break
        if item.get('op') != 'input' or item.get('area') not in ('seed', 'workspace'):
            raise ValueError('Invalid input message')
        unpack([item], source if item['area'] == 'seed' else workspace)
        send({'op': 'input_saved'})
    state = Path('/work/state')
    state.mkdir()
    os.chown(state, 1000, 1000)
    os.chown(workspace, 1000, 1000)
    for path in workspace.rglob('*'):
        os.chown(path, 1000, 1000)
    Path('/proc/sys/user/max_user_namespaces').write_text('0')
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if boot.get('verification'):
        run_verification(boot, source, workspace)
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)
    os.environ['AUTOPROTEUS_GUEST'] = '1'
    sys.path.insert(0, str(source))
    os.chdir(workspace)
    # No provider address, key or host path enters the guest.
    config = boot['config']
    config['base_url'] = 'http://unavailable.invalid'
    from autoproteus.storage import Store
    from autoproteus.providers import ProviderError
    from types import SimpleNamespace

    class Client:
        def complete(self, messages, cancel, progress=None):
            try:
                request = {'op': 'infer', 'messages': messages}
                if config['provider'] != 'demo' and config.get('protocol', 'native') == 'native':
                    from autoproteus.providers import tool_definitions
                    request['tools'] = tool_definitions(config['terminal'])
                return call(request)
            except ValueError as error:
                raise ProviderError(str(error)) from None

    class BridgeStore(Store):
        def __init__(self):
            super().__init__(state)
            self.exported = {}

        def sync(self, session):
            manifest = []
            for path in sorted(workspace.rglob('*')):
                # Do not block on FIFOs/devices or export links. The host also validates.
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or any(part.startswith('.') or part == '__pycache__' for part in path.relative_to(workspace).parts):
                    continue
                name = path.relative_to(workspace).as_posix()
                if info.st_size > 2 * 1024 * 1024:
                    raise ValueError('Export files must be at most 2 MB each')
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if self.exported.get(name) != digest:
                    call({'op': 'file', 'path': name, 'data': base64.b64encode(data).decode()})
                    self.exported[name] = digest
                manifest.append(name)
            call({'op': 'checkpoint', 'paths': manifest})
            call({'op': 'state', 'session': session})

        def save(self, session):
            super().save(session)
            self.sync(session)

        def event(self, session, kind, data):
            event = super().event(session, kind, data)
            call({'op': 'event', 'type': kind, 'data': data})
            return event

    store = BridgeStore()
    session = boot['session']
    session['workspace'] = str(workspace)
    store.directory(session['id']).mkdir(parents=True, exist_ok=True)
    store.sessions[session['id']] = session
    settings = SimpleNamespace(values=config, key=lambda: '')
    import seed
    agent = seed.run(source, store, settings, lambda _: Client(), session, boot.get('message'))
    worker = agent.workers[session['id']][1]
    worker.join()
    store.sync(session)
    call({'op': 'done'})
    # The host terminates the VM after the final checkpoint.
    while True:
        time.sleep(1)


try:
    main()
except BaseException as error:
    try:
        send({'op': 'failure', 'message': str(error)[:2000]})
    except BaseException:
        pass
    while True:
        time.sleep(1)
