"""Protected task checks. Candidate bytes are executed exclusively by IsolatedAgent."""
from __future__ import annotations

import base64
import difflib
import hashlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import uuid

from .errors import Cancelled, IsolationError
from .isolation import Artifacts, IsolatedAgent, relative_name, safe_path, seed_files
from .storage import Store, atomic_json, now


def source_identity(source):
    return hashlib.sha256(json.dumps(sorted(
        (item['path'], hashlib.sha256(base64.b64decode(item['data'], validate=True)).hexdigest())
        for item in source), separators=(',', ':')).encode()).hexdigest()


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
    started = time.monotonic()
    timed_out = False
    try:
        agent.start(session, candidate=source)
        worker = agent.workers[session['id']][1]
        while worker.is_alive():
            worker.join(timeout=.1)
            if cancel.is_set() or time.monotonic() - started > timeout:
                timed_out = not cancel.is_set()
                agent.stop(session['id'])
                worker.join(timeout=10)
                if worker.is_alive():
                    raise IsolationError('The evaluation VM did not terminate')
                break
        if cancel.is_set():
            raise Cancelled()
        artifacts = Artifacts(store, session)
        checks = [{'path': rule['path'], 'passed': artifact_check(artifacts, rule)} for rule in task['checks']]
        format_repairs, action_errors = 0, 0
        with (store.directory(session['id']) / 'events.jsonl').open(encoding='utf-8') as journal:
            for line in journal:
                event = json.loads(line)
                format_repairs += event['type'] == 'invalid_response'
                if event['type'] == 'action_result':
                    data = event['data']
                    action_errors += not isinstance(data, dict) or not data.get('ok')
        return {'task': task['name'], 'session': session['id'], 'status': session['status'],
                'passed': all(item['passed'] for item in checks) and session['status'] == 'completed' and not timed_out,
                'checks': checks, 'steps': session['steps'], 'seconds': round(time.monotonic() - started, 2),
                'model_requests': session.get('model_requests', 0),
                'timed_out': timed_out, 'format_repairs': format_repairs,
                'action_errors': action_errors,
                'detail': session['activity'][:1000] if session['status'] != 'completed' else ''}
    except Cancelled:
        raise
    except Exception as error:
        return {'task': task['name'], 'session': session['id'], 'status': 'error', 'passed': False,
                'checks': [], 'steps': session.get('steps', 0), 'seconds': round(time.monotonic() - started, 2),
                'timed_out': timed_out, 'format_repairs': 0, 'action_errors': 0, 'detail': str(error)[:1000]}


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


def run_regressions(root, store, source, cancel=None):
    """A protected guest driver runs the unchanged starter tests, without inference."""
    from .config import DEFAULTS
    settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo',
                                      'model': 'guest regression driver'}, key=lambda: '')
    agent = IsolatedAgent(root, store, settings)
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
        result['suite_sha256'] = hashlib.sha256((Path(root) / 'tests/test_seed.py').read_bytes()).hexdigest()
        return result
    except Cancelled:
        raise
    except Exception as error:
        return {'passed': False, 'tests': 0, 'session': session['id'], 'output': str(error)[:2000]}
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
                           'message': 'Starting a comparison in fresh VMs…', 'model': config['model'],
                           'configuration': public_config, 'repeats': repeats, 'total': len(tasks)*repeats*2,
                           'results': [], 'summary': {}, 'regressions': {}, 'changes': source_changes(starter, candidate),
                           'starter_sha256': source_identity(starter), 'edited_sha256': source_identity(candidate),
                           'task_sha256': hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest(),
                           'runtime_sha256': hashlib.sha256((self.task_agent.appliance.directory / 'installed.json').read_bytes()).hexdigest()
                               if (self.task_agent.appliance.directory / 'installed.json').exists() else None,
                           'scope': 'Host checks of the existing task suite; new features still need independent review.'}
            session['evaluation_check'] = report_id
            self.task_agent.store.save(session)
            self.cancel = threading.Event()
            fixed_settings = SimpleNamespace(values=config, key=lambda key=self.settings.key(): key)
            self.agent = IsolatedAgent(self.root, store, fixed_settings)
            self._save()
            self.thread = threading.Thread(target=self._run, args=(store, tasks, frozen), daemon=True)
            self.thread.start()
            return self.public()

    def _run(self, store, tasks, frozen):
        try:
            for version in ('starter', 'edited'):
                with self.gate:
                    self.report['message'] = f'Running the protected guest regression suite: {version}'
                    self._save()
                result = run_regressions(self.root, store, frozen[version], self.cancel)
                with self.gate:
                    self.report['regressions'][version] = result
                    self._save()
            if not self.report['regressions']['starter']['passed']:
                with self.gate:
                    self.report.update(status='error', message='The starter failed its protected guest checks. Task comparison did not run.')
                return
            if not self.report['regressions']['edited']['passed']:
                with self.gate:
                    self.report.update(status='rejected', message='The edited seed failed the protected guest checks. Task comparison did not run.')
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
