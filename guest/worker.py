"""Copied seed runner. VM by default; Linux native transport requires explicit flags."""
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
channel = reader = None
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


def run_verification(boot, source, workspace, native=False):
    # The protected parent keeps the broker fd. Tests run in another process as
    # UID 1000 against root-owned starter tests and the candidate's modules.
    import re
    import signal
    import subprocess
    import tempfile
    if not native:
        os.chmod('/dev/vport0p1', 0o600)
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'PYTHONPATH': str(source),
           'AUTOPROTEUS_GUEST': '1', 'AUTOPROTEUS_TEST_ROOT': str(workspace / 'test-tmp'),
           'PYTHONDONTWRITEBYTECODE': '1'}
    rules = boot.get('behavior_rules')
    if rules is not None:
        # Only the host selects these rules. Generated modules run unprivileged
        # in a fresh guest, never on the host or in the protected parent.
        driver = '''import importlib.util,json,pathlib,sys
rules=json.loads(sys.argv[1]); values=[]
for rule in rules:
 path=pathlib.Path(rule['path']).resolve()
 if not path.is_relative_to(pathlib.Path.cwd()): raise ValueError('Invalid test module path')
 spec=importlib.util.spec_from_file_location('checked_module',path)
 module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
 function=getattr(module,rule['python_function'])
 actual=[function(*case['args']) for case in rule['cases']]
 values.append(actual)
print('AP_CHECK '+json.dumps(values,ensure_ascii=True),flush=True)
'''
        arguments = ['-I', '-c', driver, json.dumps(rules)]
    else:
        arguments = ['-m', 'unittest', 'discover', '-s', str(source / '__verify__'), '-v']
    with tempfile.TemporaryFile(dir=workspace if native else '/run') as output:
        process = subprocess.Popen([sys.executable if native else '/usr/bin/python3', '-B', *arguments],
            cwd=workspace, env=env, stdin=subprocess.DEVNULL, stdout=output,
            stderr=subprocess.STDOUT,
            **({} if native else {'user':1000, 'group':1000, 'extra_groups':[]}),
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
    if rules is not None:
        try:
            frames = [json.loads(line[9:]) for line in log.splitlines() if line.startswith('AP_CHECK ')]
            expected = [[case['equals'] for case in rule['cases']] for rule in rules]
            passed = process.returncode == 0 and not limited and len(frames) == 1 and frames[0] == expected
        except (ValueError, KeyError, TypeError):
            passed = False
        result = {'passed': passed, 'exit_code': process.returncode, 'limited': limited, 'output': log,
                  'checks': [passed] * len(rules)}
        call({'op': 'file', 'path': 'behavior-result.json', 'data': base64.b64encode(json.dumps(result).encode()).decode()})
        call({'op': 'checkpoint', 'paths': ['behavior-result.json']})
        call({'op': 'done'})
        while True:
            time.sleep(1)
    count = re.search(r'Ran (\d+) tests?', log)
    expected = sum(len(re.findall(r'^    def test_', path.read_text(), re.M))
                   for path in (source / '__verify__').glob('test_*.py'))
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


def main(native_root=None):
    send({'op': 'ready', 'protocol': 2})
    boot = receive()
    if boot.get('op') != 'boot':
        raise ValueError('Expected boot message')
    source = native_root / 'seed' if native_root else Path('/seed')
    workspace = native_root / 'task' if native_root else Path('/work/task')
    source.mkdir(exist_ok=True)
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
    state = native_root / 'state' if native_root else Path('/work/state')
    state.mkdir()
    if not native_root:
        os.chown(state, 1000, 1000)
        os.chown(workspace, 1000, 1000)
        for path in workspace.rglob('*'):
            os.chown(path, 1000, 1000)
        Path('/proc/sys/user/max_user_namespaces').write_text('0')
        resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if boot.get('verification'):
        run_verification(boot, source, workspace, native=bool(native_root))
    if not native_root:
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
    activation_notice = None
    human_messages = []
    human_texts = {item['text'] for item in boot['session'].get('feed', []) if item.get('kind') == 'user'}
    for item in boot['session']['messages']:
        if item['role'] == 'user' and (item.get('origin') == 'human' or
                ('origin' not in item and (item['content'] in human_texts or not item['content'].startswith((
                    'ACTION RESULT\n', 'Your response was not accepted:', 'Resume this task. Inspect current files',
                    'Your finish call was deferred', 'A large prior action was omitted.', 'Your edited seed is now active.'))))):
            human_messages.append({'role': 'user', 'content': item['content']})
    if not any(item['content'] == boot['session']['task'] for item in human_messages):
        human_messages.insert(0, {'role': 'user', 'content': boot['session']['task']})

    class Client:
        def complete(self, messages, cancel, progress=None):
            try:
                if boot.get('handoff') == 'concise' and activation_notice:
                    before = len(messages)
                    boundary = next((index for index in range(len(messages) - 1, -1, -1)
                                     if messages[index]['content'] == activation_notice), None)
                    if boundary is not None:
                        messages = ([item for item in messages[:boundary] if item['role'] == 'system'] +
                                    human_messages + messages[boundary:])
                    call({'op': 'event', 'type': 'context_handoff', 'data': {'mode': 'concise',
                          'applied': boundary is not None, 'messages_before': before, 'messages_after': len(messages)}})
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
            self.sent_history = {'messages': [], 'feed': []}

        def sync(self, session):
            manifest = []
            for directory, folders, files in os.walk(workspace, followlinks=False):
                # Prune ignored directories before inspecting transient test files.
                folders[:] = sorted(name for name in folders if not name.startswith('.') and name != '__pycache__')
                for filename in sorted(files):
                    if filename.startswith('.'):
                        continue
                    path = Path(directory) / filename
                    try:
                        # Do not export links/devices or block on a FIFO.
                        info = path.lstat()
                        if not stat.S_ISREG(info.st_mode):
                            continue
                        if info.st_size > 2 * 1024 * 1024:
                            raise ValueError('Export files must be at most 2 MB each')
                        data = path.read_bytes()
                    except FileNotFoundError:
                        # A file may legitimately disappear between walk and read.
                        continue
                    name = path.relative_to(workspace).as_posix()
                    digest = hashlib.sha256(data).hexdigest()
                    if self.exported.get(name) != digest:
                        call({'op': 'file', 'path': name, 'data': base64.b64encode(data).decode()})
                        self.exported[name] = digest
                    manifest.append(name)
            call({'op': 'checkpoint', 'paths': manifest})
            self.exported = {name: self.exported[name] for name in manifest}
            # Transfer changed tails rather than the full growing history on every
            # save. The host reconstructs and validates the complete state as before.
            changes, encoded = {}, {}
            for name in ('messages', 'feed'):
                encoded[name] = [json.dumps(item, sort_keys=True) for item in session[name]]
                previous, current = self.sent_history[name], encoded[name]
                prefix = 0
                while prefix < min(len(previous), len(current)) and previous[prefix] == current[prefix]:
                    prefix += 1
                changes[name] = {'prefix': prefix, 'items': session[name][prefix:]}
            metadata = {name: session[name] for name in ('status', 'activity', 'steps', 'runs', 'todo', 'seed_version', 'seed_sha256') if name in session}
            call({'op': 'state', 'session': metadata, 'changes': changes})
            self.sent_history = encoded

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
    if boot.get('seed_activated') and session['messages']:
        from autoproteus.providers import tool_definitions
        names = ', '.join(item['function']['name'] for item in tool_definitions(config['terminal'])
                          if item['function']['name'] != 'finish')
        notice = ('Your edited seed is now active. Available workspace tools: ' + names + '. '
                  'Call the appropriate supplied tools directly to continue the original task after inspecting saved files. '
                  'The --tool command was for development checks; the activated tools can now be called directly. '
                  'Request another activation only if you make further seed edits.')
        activation_notice = notice
        session['messages'].append({'role': 'user', 'content': notice, 'origin': 'internal'})
        store.feed(session, 'notice', notice)
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


def entrypoint():
    global channel, reader
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-root', type=Path)
    parser.add_argument('--acknowledge-host-access', action='store_true')
    parser.add_argument('--controller-pid', type=int)
    args = parser.parse_args()
    if args.native_root:
        if sys.platform != 'linux' or not args.acknowledge_host_access or not args.controller_pid:
            parser.error('Native worker requires Linux, explicit acknowledgement and a controller PID')
        # Best-effort parent-death cleanup, not an immutable security control.
        import ctypes
        import signal
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'Could not configure parent-death cleanup')
        if os.getppid() != args.controller_pid:
            raise RuntimeError('The controller has already exited')
        channel, reader = sys.stdout.buffer, sys.stdin.buffer
        # Normal prints must not corrupt the protocol stream.
        sys.stdout = sys.stderr
    else:
        if args.acknowledge_host_access or args.controller_pid:
            parser.error('Native flags require --native-root')
        channel = open('/dev/vport0p1', 'r+b', buffering=0)
        reader = io.BufferedReader(channel)
    try:
        main(args.native_root)
    except BaseException as error:
        try:
            send({'op': 'failure', 'message': str(error)[:2000]})
        except BaseException:
            pass
        while True:
            time.sleep(1)


if __name__ == '__main__':
    entrypoint()
