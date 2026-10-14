"""Run independently checked tasks in VMs without changing saved preferences."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from controller.config import Settings
from controller.evaluation import candidate_source, freeze_source, run_task, run_regressions, source_changes, source_identity, summarize
from controller.isolation import IsolatedAgent, seed_files
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json
from controller.execution import add_execution_arguments, execution_from_args
import sys


def harness_files(root):
    paths = [path for folder in ('autoproteus', 'tests') for path in (root / folder).rglob('*.py')]
    paths.extend(root / name for name in ('seed.py', 'README.md'))
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.is_file() and path.resolve().is_relative_to(root.resolve())}


def harness_changes(workspace, baseline):
    current = harness_files(workspace / 'harness')
    return sorted(name for name in baseline.keys() | current.keys() if baseline.get(name) != current.get(name))


def check(workspace, rule):
    if 'python_function' in rule:
        raise ValueError('Behavior checks require the protected guest verifier')
    path = (workspace / rule['path']).resolve()
    if not path.is_relative_to(workspace.resolve()):
        return False
    if rule.get('absent'):
        return not path.exists()
    if not path.is_file():
        return False
    try:
        content = path.read_bytes().decode('utf-8')
        return (('equals' not in rule or content == rule['equals']) and
                ('contains' not in rule or rule['contains'] in content) and
                ('not_contains' not in rule or rule['not_contains'] not in content) and
                ('json' not in rule or json.loads(content) == rule['json']))
    except (ValueError, UnicodeError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--model', help='Use a cached local model even if the app is in demo mode.')
    parser.add_argument('--task', help='Run one named evaluation task.')
    parser.add_argument('--repeat', type=int, default=1, help='Repeat each task (1–3).')
    parser.add_argument('--candidate', help='Compare this saved session’s editable source with the starter.')
    parser.add_argument('--self-improve', action='store_true', help='Run one feature trial, with Linux commands enabled inside the VM.')
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--max-steps', type=int)
    parser.add_argument('--protocol', choices=('native', 'json'))
    parser.add_argument('--context-tokens', type=int)
    parser.add_argument('--response-tokens', type=int)
    parser.add_argument('--task-file', help='A human-supplied local task definition; never a guest capability.')
    add_execution_arguments(parser)
    args = parser.parse_args()
    execution = execution_from_args(parser, args)
    if execution.mode == 'native':
        print('WARNING: ' + execution.public()['warning'], file=sys.stderr, flush=True)
    if not 1 <= args.repeat <= 3 or not 0 < args.timeout <= 3600:
        parser.error('Use 1–3 repeats and a positive timeout of at most 3600 seconds.')
    if (args.model or args.candidate or args.self_improve) and not args.live:
        parser.error('Model, candidate and self-improvement runs require --live.')
    if args.self_improve and (args.task or args.candidate):
        parser.error('A self-improvement trial cannot also select a task or compare a candidate.')
    root = Path(__file__).resolve().parent
    settings = Settings(root / '.data')
    config = dict(settings.values)
    if not args.live:
        config.update(provider='demo', model='scripted-demo', configured=True)
    elif args.model and config['provider'] == 'demo':
        config.update(provider='ollama', model=args.model, configured=True)
    elif not config['configured'] or config['provider'] == 'demo':
        parser.error('Connect a real model or choose a cached local model with --model.')
    if args.model:
        config.update(model=args.model, thinking=None)
    if args.protocol:
        config['protocol'] = args.protocol
    if args.max_steps is not None:
        if not 1 <= args.max_steps <= 200:
            parser.error('Use between 1 and 200 steps.')
        config['max_steps'] = args.max_steps
    if args.self_improve:
        config['terminal'] = True
    for name in ('context_tokens', 'response_tokens'):
        if getattr(args, name) is not None:
            config[name] = getattr(args, name)
    config = settings.preview(config)
    fixed = SimpleNamespace(values=config, key=lambda: settings.key())
    engine = LocalRuntime(root, fixed)
    report_id = uuid.uuid4().hex
    directory = root / '.data/evaluations/runs' / report_id
    store = Store(directory / 'sessions')
    agent = IsolatedAgent(root, store, fixed, execution=execution)
    results = []
    try:
        if config['provider'] == 'ollama':
            config['base_url'] = engine.ensure_service(allow_download=False)
        tasks = json.loads((root / 'evaluations/tasks.json').read_text(encoding='utf-8')) if args.live else [
            {'name':'scripted-demo', 'task':'Create a welcome note and verify it.', 'checks':[
                {'path':'welcome.md','contains':'Hello from AutoProteus'}, {'path':'todo.txt','not_contains':'[ ]','contains':'[x]'}]}]
        if args.self_improve:
            tasks = [json.loads((root / 'evaluations/harness-feature.json').read_text(encoding='utf-8'))]
        if args.task_file:
            tasks = [json.loads(Path(args.task_file).read_text(encoding='utf-8'))]
        if args.task:
            tasks = [task for task in tasks if task['name'] == args.task]
            if not tasks:
                parser.error('Unknown task name')
        sources = {'starter': seed_files(root)}
        if args.candidate:
            app_store = Store(root / '.data/sessions')
            sources['edited'] = candidate_source(app_store, app_store.get(args.candidate))
        frozen = {name: freeze_source(store, source, name) for name, source in sources.items()}
        report = {'id': report_id, 'model': config['model'], 'live': args.live,
                  'execution_mode': execution.mode, 'isolated': execution.mode == 'vm',
                  'checks_protected': execution.mode == 'vm', 'warning': execution.public()['warning'],
                  'configuration': {k:v for k,v in config.items() if k not in ('base_url','api_key')},
                  'source_sha256': {name:source_identity(source) for name,source in sources.items()},
                  'results': results, 'summary': {}, 'regressions': {}, 'self_improve': args.self_improve}
        if args.candidate:
            for version in sources:
                report['regressions'][version] = run_regressions(root, store, frozen[version], execution=execution)
            if not all(result['passed'] for result in report['regressions'].values()):
                report.update(status='rejected', message='Protected guest checks failed. Task comparison did not run.')
                atomic_json(directory / 'report.json', report)
                print('REJECTED: protected guest checks failed. Report:', directory / 'report.json')
                return 1
        for repeat in range(1, args.repeat + 1):
            for task in tasks:
                for version in (list(sources) if repeat % 2 else list(reversed(sources))):
                    result = run_task(agent, store, config, task, frozen[version], args.timeout)
                    if args.self_improve:
                        session = store.get(result['session'])
                        try:
                            edited = candidate_source(store, session)
                        except ValueError:
                            edited = []
                        changes = source_changes(sources['starter'], edited)
                        ready = bool(edited) and result['passed'] and any(c['path'].startswith('autoproteus/') for c in changes) and any(c['path'].startswith('tests/') for c in changes)
                        result.update(artifact_passed=ready, passed=None if ready else False,
                                      review_required=True, changed_files=[c['path'] for c in changes])
                        if ready:
                            candidate = freeze_source(store, edited, 'Self-improvement candidate')
                            report['regressions']['edited'] = run_regressions(root, store, candidate, execution=execution)
                        atomic_json(directory / 'candidate-source.json', edited)
                        atomic_json(directory / 'changes.json', changes)
                    results.append({**result, 'version': version, 'repeat': repeat})
                    report['summary'] = summarize([r for r in results if r['passed'] is not None])
                    atomic_json(directory / 'report.json', report)
                    print('REVIEW' if result['passed'] is None else 'PASS' if result['passed'] else 'FAIL',
                          version, task['name'], f"({result['seconds']}s, {result['steps']} steps)", flush=True)
        print('Report:', directory / 'report.json')
        return 1 if any(item['passed'] is False for item in results) else 2 if any(item['passed'] is None for item in results) else 0
    finally:
        agent.close()
        engine.close()


if __name__ == '__main__':
    raise SystemExit(main())
