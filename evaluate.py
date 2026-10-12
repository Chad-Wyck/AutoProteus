"""Independent file checks; never execute model-authored verifier code."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from autoproteus.agent import Agent
from autoproteus.config import Settings
from autoproteus.storage import Store, atomic_json


def harness_files(root):
    """Fingerprint runtime and tests without importing or executing the copy."""
    paths = [path for folder in ('autoproteus', 'tests') for path in (root / folder).rglob('*.py')]
    paths.extend((root / 'web').rglob('*'))
    paths.extend(root / name for name in ('app.py', 'evaluate.py', 'Start AutoProteus.cmd', 'launch.ps1'))
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
            if path.is_file() and path.resolve().is_relative_to(root.resolve())}


def harness_changes(workspace, baseline):
    current = harness_files(workspace / 'harness')
    return sorted(name for name in baseline.keys() | current.keys()
                  if baseline.get(name) != current.get(name))


def check(workspace, rule):
    path = (workspace / rule['path']).resolve()
    if not path.is_relative_to(workspace.resolve()):
        return False
    if rule.get('absent'):
        return not path.exists()
    if not path.is_file():
        return False
    content = path.read_text(encoding='utf-8', errors='replace')
    if 'equals' in rule and content != rule['equals']:
        return False
    if 'contains' in rule and rule['contains'] not in content:
        return False
    if 'not_contains' in rule and rule['not_contains'] in content:
        return False
    if 'json' in rule:
        try:
            return json.loads(content) == rule['json']
        except ValueError:
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Use the configured real model (hosted requests may incur charges).')
    parser.add_argument('--task', help='Run one named task from evaluations/tasks.json.')
    parser.add_argument('--model', help='Evaluate another model on the configured service without changing saved preferences.')
    parser.add_argument('--self-improve', action='store_true', help='Let the model choose a feature and edit its harness copy; requires independent review.')
    parser.add_argument('--timeout', type=float, default=900, help='Maximum seconds per task (default: 900).')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    settings = Settings(root / '.data')
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if args.self_improve and (not args.live or args.task):
        parser.error('--self-improve requires --live and cannot be combined with --task')
    if args.model and not args.live:
        parser.error('--model requires --live')
    if args.live:
        if not settings.values['configured'] or settings.values['provider'] == 'demo':
            parser.error('Connect a real model in the app before using --live.')
        if args.model:
            settings.values.update(model=args.model, thinking=None)
        tasks = json.loads((root / 'evaluations' / 'tasks.json').read_text(encoding='utf-8'))
        if args.self_improve:
            tasks = [json.loads((root / 'evaluations' / 'harness-feature.json').read_text(encoding='utf-8'))]
            # An evaluation policy, not a prompt or a saved user preference.
            settings.values = {**settings.values, 'terminal': False}
        if args.task:
            tasks = [task for task in tasks if task['name'] == args.task]
            if not tasks:
                parser.error('Unknown task name')
    else:
        # Override in memory so this plumbing test never changes the user's model.
        settings.values.update(provider='demo', model='scripted-demo', configured=True)
        tasks = [{'name':'scripted-demo','task':'Create a welcome note and verify it.', 'checks':[{'path':'welcome.md','contains':'Hello from AutoProteus'},{'path':'todo.txt','not_contains':'[ ]','contains':'[x]'}]}]
    store = Store(root / '.data' / 'evaluations' / 'sessions')
    agent = Agent(root, store, settings)
    results = []
    try:
        for task in tasks:
            session = store.create(task['task'], settings.values['provider'], settings.values['model'])
            workspace = Path(session['workspace'])
            baseline = harness_files(root) if task.get('review_required') else None
            for name, content in task.get('fixtures', {}).items():
                (workspace / name).parent.mkdir(parents=True, exist_ok=True)
                (workspace / name).write_text(content, encoding='utf-8')
            started = time.monotonic(); agent.start(session)
            while session['status'] in ('running', 'stopping') and time.monotonic() - started < args.timeout:
                time.sleep(0.1)
            if session['status'] in ('running', 'stopping'):
                agent.stop(session['id'])
                agent.workers[session['id']][1].join(timeout=5)
            checks = [check(workspace, rule) for rule in task['checks']]
            changes = harness_changes(workspace, baseline) if baseline is not None else []
            if baseline is not None:
                current = harness_files(workspace / 'harness')
                checks.extend([any(not name.startswith('tests/') and name in current for name in changes),
                               any(name.startswith('tests/') and name in current for name in changes)])
            passed = all(checks) and session['status'] == 'completed'
            review = bool(task.get('review_required'))
            result = {'task':task['name'], 'session':session['id'], 'passed':None if passed and review else passed,
                      'artifact_passed':all(checks), 'review_required':review, 'checks':checks,
                      'status':session['status'], 'seconds':round(time.monotonic()-started,2), 'steps':session['steps'],
                      'seed_sha256':session.get('seed_sha256')}
            if review:
                result['changed_files'] = changes
            results.append(result)
            verdict = 'REVIEW' if passed and review else 'PASS' if passed else 'FAIL'
            print(f"{verdict} {task['name']} ({result['seconds']}s, {session['steps']} steps)", flush=True)
    finally:
        agent.close()
    report = {'provider':settings.values['provider'], 'model':settings.values['model'], 'live':args.live, 'results':results}
    path = root / '.data' / 'evaluations' / ('report-' + str(int(time.time())) + '.json')
    atomic_json(path, report)
    print('Report:', path)
    if any(item['passed'] is False for item in results):
        return 1
    return 2 if any(item['passed'] is None for item in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
