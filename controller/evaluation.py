"""Protected task checks. Candidate bytes are executed exclusively by IsolatedAgent."""
from __future__ import annotations

import base64
import ast
import difflib
import hashlib
import json
import shlex
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import uuid

from .errors import Cancelled, IsolationError
from .isolation import Artifacts, IsolatedAgent, SEED_TESTS, relative_name, safe_path, seed_files
from .storage import Store, atomic_json, now
from .compatibility import model_identity


def tool_use(events):
    """Observed invocation routes, not a security proof about hostile candidates."""
    native, development = set(), set()
    for event in events:
        data = event.get('data', {})
        if event.get('type') != 'action_result' or not isinstance(data, dict) or not data.get('ok'):
            continue
        action = data.get('action', {})
        name = action.get('tool')
        if name != 'run_command':
            native.add(name)
            continue
        try:
            args = shlex.split(action.get('arguments', {}).get('command', ''))
            if data.get('result', {}).get('exit_code') != 0:
                continue
            # Recognize the other observed development route without executing
            # submitted Python on the host. Only unconditional top-level calls
            # through the imported Workspace class count as diagnostic evidence.
            if len(args) == 3 and args[:2] == ['python3', '-c']:
                tree = ast.parse(args[2])
                imported = any(isinstance(node, ast.ImportFrom) and node.module == 'autoproteus.tools' and
                               any(alias.name == 'Workspace' and not alias.asname for alias in node.names)
                               for node in tree.body)
                for node in tree.body if imported else []:
                    value = node.value if isinstance(node, (ast.Assign, ast.Expr)) else None
                    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and
                            value.func.attr == 'execute' and isinstance(value.func.value, ast.Call) and
                            isinstance(value.func.value.func, ast.Name) and value.func.value.func.id == 'Workspace' and
                            value.args and isinstance(value.args[0], ast.Constant) and isinstance(value.args[0].value, str)):
                        development.add(value.args[0].value)
                continue
            helper = len(args) == 4 and args[:2] == ['python3', 'experience/invoke_tool.py']
            checker = (len(args) == 7 and args[:4] == ['python3', 'harness/seed.py', 'check', '--tool'] and
                       args[5] == '--arguments')
            if not (helper or checker):
                continue
            expected_check = 'development tool invocation' if helper else 'candidate tool invocation'
            expected_tool = args[2] if helper else args[4]
            for line in data['result'].get('output', '').splitlines():
                try:
                    record = json.loads(line)
                    if (isinstance(record, dict) and record.get('check') == expected_check and
                            record.get('passed') is True and record.get('tool') == expected_tool):
                        development.add(expected_tool)
                except ValueError:
                    pass
        except (ValueError, TypeError, SyntaxError):
            continue
    return {'direct': sorted(name for name in native if isinstance(name, str)),
            'development': sorted(development)}


def growth_scores(extension_verified, prior_preserved, completed, artifacts_correct, usage, required):
    direct = set(required).issubset(usage['direct'])
    used = set(required).issubset(set(usage['direct']) | set(usage['development']))
    functional = bool(extension_verified and prior_preserved and completed and artifacts_correct and used)
    return {'capability_added': bool(extension_verified), 'earlier_behavior_preserved': bool(prior_preserved),
            'task_completed_correctly': bool(completed and artifacts_correct), 'capabilities_used': used,
            'functional_growth': functional, 'direct_tool_use': direct,
            'strict_route_success': functional and direct}


def source_identity(source):
    return hashlib.sha256(json.dumps(sorted(
        (item['path'], hashlib.sha256(base64.b64decode(item['data'], validate=True)).hexdigest())
        for item in source), separators=(',', ':')).encode()).hexdigest()


def upgrade_review(store, session, starter, candidate):
    """Assemble review evidence on the host; guest claims remain diagnostic."""
    commands = []
    journal = store.directory(session['id']) / 'events.jsonl'
    if journal.exists():
        for line in journal.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            data = event.get('data', {})
            if not isinstance(data, dict):
                continue
            action = data.get('action', {})
            if event.get('type') == 'action_result' and isinstance(action, dict) and action.get('tool') == 'run_command':
                arguments = action.get('arguments', {})
                commands.append({'command': arguments.get('command', '') if isinstance(arguments, dict) else None,
                                 'result': data.get('result'), 'ok': data.get('ok')})
    explanation = next((item['text'] for item in reversed(session.get('feed', []))
                        if item.get('kind') == 'assistant'), '')
    return {'session': session['id'], 'status': session['status'], 'candidate_available': bool(candidate), 'model_explanation': explanation,
            'starter_sha256': source_identity(starter), 'candidate_sha256': source_identity(candidate),
            'files': {item['path']: hashlib.sha256(base64.b64decode(item['data'], validate=True)).hexdigest() for item in candidate},
            'changes': source_changes(starter, candidate), 'commands': commands,
            'verification': 'Recorded guest commands are development feedback; independent checks are required.'}


def candidate_source(store, session):
    source = [{'path': item['path'][8:], 'data': item['data']}
              for item in Artifacts(store, session).pack() if item['path'].startswith('harness/')]
    if not {'seed.py', 'autoproteus/agent.py'}.issubset({item['path'] for item in source}):
        raise ValueError('This session has no complete editable seed. Start a task to create one.')
    return source


def source_changes(starter, candidate):
    old = {item['path']: base64.b64decode(item['data'], validate=True) for item in starter}
    new = {item['path']: base64.b64decode(item['data'], validate=True) for item in candidate}
    changes, remaining = [], 60000
    for name in sorted(old.keys() | new.keys()):
        a, b = old.get(name, b''), new.get(name, b'')
        if name in old and name in new and a == b:
            continue
        diff = ''
        if max(len(a), len(b)) <= 100000 and remaining:
            try:
                diff = ''.join(difflib.unified_diff(a.decode('utf-8').splitlines(True),
                    b.decode('utf-8').splitlines(True), fromfile='starter/' + name,
                    tofile='edited/' + name))[:min(12000, remaining)]
            except UnicodeError:
                pass
        remaining -= len(diff)
        changes.append({'path': name, 'kind': 'added' if name not in old else 'deleted' if name not in new else 'changed',
                        'before_bytes': len(a), 'after_bytes': len(b), 'diff': diff})
    return changes


def artifact_check(artifacts, rule):
    if 'python_function' in rule:
        raise ValueError('Behavior checks require a fresh isolated verifier')
    name = relative_name(rule['path'])
    present = name in artifacts.session.get('artifacts', {})
    if rule.get('absent'):
        return not present
    if not present:
        return False
    try:
        content = artifacts.read(name).decode('utf-8')
        if 'equals' in rule and content != rule['equals']:
            return False
        if 'contains' in rule and rule['contains'] not in content:
            return False
        if 'not_contains' in rule and rule['not_contains'] in content:
            return False
        if 'json' in rule and json.loads(content) != rule['json']:
            return False
        return True
    except (UnicodeError, ValueError):
        return False


def freeze_source(store, source, label):
    session = store.create(label, 'demo', 'source snapshot')
    artifacts = Artifacts(store, session)
    for item in source:
        artifacts.put('harness/' + item['path'], item['data'])
    artifacts.checkpoint(['harness/' + item['path'] for item in source])
    return session


def run_task(agent, store, config, task, source, timeout=180, cancel=None):
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled()
    session = store.create(task['task'], config['provider'], config['model'])
    for name, content in task.get('fixtures', {}).items():
        path = safe_path(session['workspace'], name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf-8'))
    for name, generator in task.get('fixture_generators', {}).items():
        content = generator['line'] * generator['count'] + generator.get('tail', '')
        path = safe_path(session['workspace'], name); path.parent.mkdir(parents=True, exist_ok=True)
        if len(content.encode()) > 2 * 1024 * 1024:
            raise ValueError('Generated fixture is too large')
        path.write_text(content, encoding='utf-8', newline='')
    started = time.monotonic()
    timed_out = False
    try:
        agent.start(session, candidate=source)
        worker = agent.workers[session['id']][1]
        interrupted = False
        while worker.is_alive():
            worker.join(timeout=.1)
            if task.get('interrupt_after_steps') and not interrupted and session['steps'] >= task['interrupt_after_steps']:
                agent.stop(session['id']); worker.join(timeout=10)
                if worker.is_alive(): raise IsolationError('The interrupted task did not stop')
                interrupted = True
                agent.start(session, 'Continue from your saved checkpoint. Verify the current files before editing.')
                worker = agent.workers[session['id']][1]
            if cancel.is_set() or time.monotonic() - started > timeout:
                timed_out = not cancel.is_set()
                agent.stop(session['id'])
                worker.join(timeout=10)
                if worker.is_alive():
                    raise IsolationError('The evaluation VM did not terminate')
                break
        for followup in task.get('followups', []) if not timed_out and session['status'] in ('completed', 'waiting', 'paused') else []:
            if cancel.is_set():
                raise Cancelled()
            if timed_out:
                break
            agent.start(session, followup)
            worker = agent.workers[session['id']][1]
            while worker.is_alive():
                worker.join(timeout=.1)
                if cancel.is_set() or time.monotonic() - started > timeout:
                    agent.stop(session['id']); worker.join(timeout=10)
                    if worker.is_alive():
                        raise IsolationError('The evaluation VM did not terminate')
                    timed_out = not cancel.is_set(); break
        if cancel.is_set():
            raise Cancelled()
        artifacts = Artifacts(store, session)
        rules = [rule for rule in task['checks'] if 'python_function' in rule]
        behavior = verify_behavior(agent, store, session, rules, cancel) if rules and not timed_out else {'passed': False}
        checks = [{'path': rule['path'], 'passed': behavior['passed'] if 'python_function' in rule else artifact_check(artifacts, rule)} for rule in task['checks']]
        format_repairs, action_errors, reads, repeated_reads = 0, 0, 0, 0
        previous_read = None
        with (store.directory(session['id']) / 'events.jsonl').open(encoding='utf-8') as journal:
            for line in journal:
                event = json.loads(line)
                format_repairs += event['type'] == 'invalid_response'
                if event['type'] == 'action_result':
                    data = event['data']
                    action_errors += not isinstance(data, dict) or not data.get('ok')
                    if data.get('action', {}).get('tool') in ('read_file', 'read_section', 'search_files'):
                        reads += 1
                        signature = json.dumps({'action': data['action'], 'result': data.get('result')}, sort_keys=True)
                        repeated_reads += signature == previous_read
                        previous_read = signature
                    else:
                        previous_read = None
        return {'task': task['name'], 'session': session['id'], 'status': session['status'],
                'execution_mode': agent.execution.mode, 'isolated': agent.execution.mode == 'vm',
                'passed': all(item['passed'] for item in checks) and session['status'] == 'completed' and not timed_out and (not task.get('interrupt_after_steps') or interrupted),
                'checks': checks, 'steps': session['steps'], 'seconds': round(time.monotonic() - started, 2),
                'model_requests': session.get('model_requests', 0),
                'timed_out': timed_out, 'format_repairs': format_repairs,
                'action_errors': action_errors,
                'read_actions': reads, 'repeated_reads': repeated_reads, 'interrupted': interrupted,
                'failure_kind': session.get('error_category') or ('compatibility' if format_repairs > 2 and session['status'] == 'error' else 'timeout' if timed_out else 'task' if not all(i['passed'] for i in checks) else None),
                'detail': session['activity'][:1000] if session['status'] != 'completed' else ''}
    except Cancelled:
        raise
    except Exception as error:
        return {'task': task['name'], 'session': session['id'], 'status': 'error', 'passed': False,
                'execution_mode': agent.execution.mode, 'isolated': agent.execution.mode == 'vm',
                'checks': [], 'steps': session.get('steps', 0), 'seconds': round(time.monotonic() - started, 2),
                'timed_out': timed_out, 'format_repairs': 0, 'action_errors': 0, 'detail': str(error)[:1000]}


def verify_behavior(agent, store, session, rules, cancel=None):
    """Copy only selected artifact bytes into another guest and check actual returns."""
    probe = store.create('Independently verify artifact behavior', 'demo', 'protected verifier')
    files = Artifacts(store, probe)
    original = Artifacts(store, session)
    for rule in rules:
        if not isinstance(rule.get('python_function'), str) or not rule['python_function'].isidentifier() or not isinstance(rule.get('cases'), list) or not 1 <= len(rule['cases']) <= 20:
            raise ValueError('Invalid behavioral check')
        name = relative_name(rule['path'])
        files.put(name, base64.b64encode(original.read(name)).decode())
    files.checkpoint(list(dict.fromkeys(rule['path'] for rule in rules)))
    from .config import DEFAULTS
    settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo'}, key=lambda: '')
    verifier = IsolatedAgent(agent.root, store, settings, execution=agent.execution)
    cancel = cancel or threading.Event()
    try:
        verifier.start(probe, verification={'rules': rules})
        worker = verifier.workers[probe['id']][1]
        deadline = time.monotonic() + 90
        while worker.is_alive():
            worker.join(timeout=.1)
            if cancel.is_set() or time.monotonic() > deadline:
                verifier.stop(probe['id']); worker.join(timeout=10)
                if cancel.is_set(): raise Cancelled()
                return {'passed': False, 'output': 'Behavior check timed out'}
        return json.loads(Artifacts(store, probe).read('behavior-result.json'))
    finally:
        verifier.close()


def summarize(results):
    summary = {}
    for version in sorted({item['version'] for item in results}):
        cases = [item for item in results if item['version'] == version]
        summary[version] = {'passed': sum(item['passed'] for item in cases), 'total': len(cases),
                            'seconds': round(sum(item['seconds'] for item in cases), 2),
                            'steps': sum(item['steps'] for item in cases),
                            'model_requests': sum(item.get('model_requests', 0) for item in cases),
                            'format_repairs': sum(item['format_repairs'] for item in cases)}
    return summary


def run_regressions(root, store, source, cancel=None, execution=None):
    """A protected guest driver runs the unchanged starter tests, without inference."""
    from .config import DEFAULTS
    settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo',
                                      'model': 'guest regression driver'}, key=lambda: '')
    agent = IsolatedAgent(root, store, settings, execution=execution)
    session = store.create('Run the protected seed regression suite', 'demo', 'guest regression driver')
    cancel = cancel or threading.Event()
    try:
        agent.start(session, candidate=source, verification=True)
        worker = agent.workers[session['id']][1]
        deadline = time.monotonic() + 120
        while worker.is_alive():
            worker.join(timeout=.1)
            if cancel.is_set() or time.monotonic() > deadline:
                agent.stop(session['id']); worker.join(timeout=10)
                if cancel.is_set():
                    raise Cancelled()
                raise IsolationError('Guest regression checks timed out')
        result = json.loads(Artifacts(store, session).read('regression-result.json'))
        result['session'] = session['id']
        result['suite_files'] = {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest()
                                for name in SEED_TESTS}
        result['suite_sha256'] = hashlib.sha256(json.dumps(result['suite_files'], sort_keys=True).encode()).hexdigest()
        result.update(execution_mode=agent.execution.mode, isolated=agent.execution.mode == 'vm',
                      checks_protected=agent.execution.mode == 'vm')
        return result
    except Cancelled:
        raise
    except Exception as error:
        return {'passed': False, 'tests': 0, 'session': session['id'], 'output': str(error)[:2000],
                'execution_mode': agent.execution.mode, 'isolated': agent.execution.mode == 'vm',
                'checks_protected': agent.execution.mode == 'vm'}
    finally:
        agent.close()


class EvaluationService:
    """One cancellable comparison at a time, outside the user's task store."""
    def __init__(self, root, data, settings, task_agent):
        self.root, self.data, self.settings, self.task_agent = Path(root), Path(data), settings, task_agent
        self.gate = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.report = None
        self.agent = None

    @property
    def busy(self):
        return bool(self.thread and self.thread.is_alive())

    def public(self):
        with self.gate:
            if not self.report:
                return {'busy': False}
            return {**json.loads(json.dumps(self.report)), 'busy': self.busy}

    def _save(self):
        atomic_json(self.data / 'checks' / self.report['id'] / 'report.json', self.report)

    def load(self, report_id):
        # Report identifiers never select a guest-supplied filesystem path.
        if not isinstance(report_id, str) or len(report_id) != 32 or any(c not in '0123456789abcdef' for c in report_id):
            raise ValueError('Unknown check report')
        value = json.loads((self.data / 'checks' / report_id / 'report.json').read_text(encoding='utf-8'))
        if value['status'] == 'running' and (not self.report or value['id'] != self.report['id']):
            value.update(status='interrupted', message='The checks were interrupted. Run them again to complete the comparison.')
        return value

    def start(self, session, repeats=2):
        with self.gate:
            if self.busy or any(thread.is_alive() for _, thread in self.task_agent.workers.values()):
                raise ValueError('Stop the current task or checks before starting a seed comparison')
            if type(repeats) is not int or not 1 <= repeats <= 3:
                raise ValueError('Repeat each task between one and three times')
            config = dict(self.settings.values)
            if not config['configured'] or config['provider'] == 'demo':
                raise ValueError('Connect a real model before checking an edited seed')
            self.task_agent.appliance.verify()
            candidate = candidate_source(self.task_agent.store, session)
            starter = seed_files(self.root)
            tasks = json.loads((self.root / 'evaluations/tasks.json').read_text(encoding='utf-8'))
            report_id = uuid.uuid4().hex
            directory = self.data / 'checks' / report_id
            store = Store(directory / 'sessions')
            frozen = {name: freeze_source(store, source, name) for name, source in [('starter', starter), ('edited', candidate)]}
            atomic_json(directory / 'sources.json', {'starter': starter, 'edited': candidate})
            # Never save credentials or provider addresses in comparison reports.
            public_config = {key: value for key, value in config.items() if key not in ('base_url', 'api_key')}
            self.report = {'id': report_id, 'session': session['id'], 'status': 'running', 'created': now(),
                           'message': 'Starting a comparison in fresh VMs…' if self.task_agent.execution.mode == 'vm'
                               else 'Starting native functional checks without VM protection…', 'model': config['model'],
                           'execution_mode': self.task_agent.execution.mode,
                           'isolated': self.task_agent.execution.mode == 'vm',
                           'warning': self.task_agent.execution.public()['warning'],
                           'checks_protected': self.task_agent.execution.mode == 'vm',
                           'configuration': public_config, 'repeats': repeats, 'total': len(tasks)*repeats*2,
                           'model_identity': model_identity(config),
                           'results': [], 'summary': {}, 'regressions': {}, 'changes': source_changes(starter, candidate),
                           'starter_sha256': source_identity(starter), 'edited_sha256': source_identity(candidate),
                           'task_sha256': hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest(),
                           'runtime_sha256': hashlib.sha256(self.task_agent.appliance.record_path.read_bytes()).hexdigest()
                               if self.task_agent.execution.mode == 'vm' and
                                   self.task_agent.appliance.record_path.exists() else None,
                           'scope': 'Host checks of the existing task suite; new features still need independent review.'
                               if self.task_agent.execution.mode == 'vm' else
                               'Native functional checks only. Code has this account\'s access; the controller, tests and reports are not protected from it. New features need independent review.'}
            session['evaluation_check'] = report_id
            self.task_agent.store.save(session)
            self.cancel = threading.Event()
            fixed_settings = SimpleNamespace(values=config, key=lambda key=self.settings.key(): key)
            self.agent = IsolatedAgent(self.root, store, fixed_settings, execution=self.task_agent.execution)
            self._save()
            self.thread = threading.Thread(target=self._run, args=(store, tasks, frozen), daemon=True)
            self.thread.start()
            return self.public()

    def _run(self, store, tasks, frozen):
        try:
            for version in ('starter', 'edited'):
                with self.gate:
                    kind = 'protected guest' if self.task_agent.execution.mode == 'vm' else 'native functional'
                    self.report['message'] = f'Running the {kind} regression suite: {version}'
                    self._save()
                result = run_regressions(self.root, store, frozen[version], self.cancel,
                                         execution=self.task_agent.execution)
                with self.gate:
                    self.report['regressions'][version] = result
                    self._save()
            if not self.report['regressions']['starter']['passed']:
                with self.gate:
                    self.report.update(status='error', message='The starter failed its regression checks. Task comparison did not run.')
                return
            if not self.report['regressions']['edited']['passed']:
                with self.gate:
                    self.report.update(status='rejected', message='The edited seed failed the regression checks. Task comparison did not run.')
                return
            for repeat in range(1, self.report['repeats'] + 1):
                for task in tasks:
                    # Alternate which version goes first to reduce warm-up/order bias.
                    order = ('starter', 'edited') if repeat % 2 else ('edited', 'starter')
                    for version in order:
                        with self.gate:
                            self.report['message'] = f"Checking {version}: {task['name']} · repeat {repeat}"
                            self._save()
                        result = run_task(self.agent, store, self.agent.settings.values, task, frozen[version], cancel=self.cancel)
                        with self.gate:
                            self.report['results'].append({**result, 'version': version, 'repeat': repeat})
                            self.report['summary'] = summarize(self.report['results'])
                            self._save()
            with self.gate:
                self.report.update(status='completed', message='Comparison complete. Review the checked results before trying this seed.')
        except Cancelled:
            with self.gate:
                self.report.update(status='cancelled', message='Checks stopped. Partial results are saved; the comparison is incomplete.')
        except Exception as error:
            with self.gate:
                self.report.update(status='error', message=str(error)[:1000])
        finally:
            self.agent.close()
            with self.gate:
                self.report['completed'] = now()
                self._save()

    def stop(self):
        self.cancel.set()
        if self.agent:
            self.agent.close()

    def close(self):
        self.stop()
        if self.thread:
            self.thread.join(timeout=10)
