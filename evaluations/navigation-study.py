"""Prepare, validate and run a paired Qwen 9B navigation study; no model downloads."""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evaluations'))
from observations import CallRecorder, call_metrics, navigation_metrics, read_events
from run_budget import BudgetModelClient, GeneratedTokenBudget, DEFAULT_OUTPUT_TOKENS, DEFAULT_TASK_SECONDS
from controller.evaluation import freeze_source, run_regressions, run_task, source_identity
from controller.isolation import IsolatedAgent, seed_files
from controller.providers import ModelClient, request_json
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json, now
from controller.compatibility import model_identity

spec = importlib.util.spec_from_file_location('study', ROOT / 'evaluations/generalization.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def private_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Study files must stay inside project .data')
    return path


def save_plan(directory, plan):
    atomic_json(directory / 'plan.json', plan)
    (directory / 'plan.sha256').write_text(hashlib.sha256((directory / 'plan.json').read_bytes()).hexdigest(), encoding='ascii')


def navigation_variant(source):
    result = copy.deepcopy(source)
    for item in result:
        text = base64.b64decode(item['data']).decode('utf-8')
        if item['path'] == 'autoproteus/tools.py':
            anchor = '        if tool == "list_files":'
            assert text.count(anchor) == 1
            text = text.replace(anchor, '        if tool == "source_outline":\n'
                '            from .source_navigation import source_outline\n'
                '            return source_outline(self, args)\n' + anchor)
        elif item['path'] == 'autoproteus/providers.py':
            anchor = 'TOOL_SPECS = {'
            assert text.count(anchor) == 1
            text = text.replace(anchor, anchor + '\n    "source_outline": ("Locate Python functions/classes and methods; use their character start and length with read_section.", {"path": STRING}, ["path"]),')
        elif item['path'] == 'README.md':
            text += '\nExperimental navigation: source_outline(path) lists Python functions, classes and methods with character start and bounded length for read_section. Inspect the relevant definition rather than paging through unrelated source.\n'
        item['data'] = base64.b64encode(text.encode()).decode()
    result.append({'path': 'autoproteus/source_navigation.py', 'data':
                   base64.b64encode((ROOT / 'evaluations/source_navigation.py').read_bytes()).decode()})
    return result


def prepare(args):
    GeneratedTokenBudget(getattr(args, 'output_token_budget', DEFAULT_OUTPUT_TOKENS))
    if args.timeout < 1:
        raise ValueError('Task deadline must be positive')
    output = private_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    baseline = seed_files(ROOT)
    sources = {'baseline': baseline, 'outline': navigation_variant(baseline)}
    plan = {'status': 'prepared', 'created': now(), 'config': study.profile_configs()['qwen9b'],
            'repeats': args.repeats, 'timeout': args.timeout,
            'output_token_budget': getattr(args, 'output_token_budget', DEFAULT_OUTPUT_TOKENS), 'contracts': study.CONTRACTS,
            'primary': 'Full accepted upgrades; independent behavior and candidate tests reported separately.',
            'efficiency': 'Costs on matched accepted task/repeat pairs, plus costs for all launched attempts.',
            'scope': 'Development comparison on previously tested contracts; any winner needs fresh validation tasks.',
            'observations': 'Opt-in, host-only, 32 MiB per trial. No headers, endpoint URLs or training token IDs. Known provider key is redacted.',
            'sources': {name: source_identity(source) for name, source in sources.items()}, 'schedule': [], 'trusted_sha256': {}}
    for name, source in sources.items():
        atomic_json(output / (name + '-source.json'), source)
    for repeat in range(1, args.repeats + 1):
        for index, task in enumerate(study.CONTRACTS):
            order = ('baseline', 'outline') if (repeat + index) % 2 else ('outline', 'baseline')
            for variant in order:
                plan['schedule'].append({'id': f'{repeat}-{task}-{variant}', 'repeat': repeat, 'task': task, 'variant': variant})
    trusted = ('controller/providers.py', 'controller/isolation.py', 'controller/evaluation.py',
        'controller/appliance.py', 'controller/config.py', 'controller/runtime.py', 'controller/storage.py',
        'controller/compatibility.py', 'controller/execution.py', 'controller/runtime-lock.json',
        'controller/managed-runtime-lock.json', 'guest/worker.py', 'tests/test_seed.py', 'tests/test_text_helpers.py',
        'evaluations/navigation-study.py', 'evaluations/navigation_probe.py', 'evaluations/source_navigation.py',
        'evaluations/observations.py', 'evaluations/run_budget.py', 'evaluations/generalization.py', 'evaluations/generalization-probe.py',
        'evaluations/local-model-benchmark.py')
    for name in trusted:
        raw = (ROOT / name).read_bytes()
        destination = output / 'trusted-runner' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        plan['trusted_sha256'][name] = hashlib.sha256(raw).hexdigest()
    save_plan(output, plan)
    command = (f'@echo off\nsetlocal\ncd /d "{ROOT}"\n"{ROOT / ".runtime/python/python.exe"}" -X utf8 '
               f'"{ROOT / "evaluations/navigation-study.py"}" run --input "{output}"\npause\n')
    (output / 'Start tests.cmd').write_text(command, encoding='utf-8')
    print('Prepared', len(plan['schedule']), 'trials; no inference started. Output:', output)


def load_plan(directory):
    expected = (directory / 'plan.sha256').read_text(encoding='ascii').strip()
    if hashlib.sha256((directory / 'plan.json').read_bytes()).hexdigest() != expected:
        raise RuntimeError('The prepared plan/settings changed. Prepare a fresh study directory.')
    plan = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected for name, expected in plan['trusted_sha256'].items()):
        raise RuntimeError('Prepared runner changed. Prepare a fresh study directory.')
    sources = {name: json.loads((directory / (name + '-source.json')).read_text(encoding='utf-8')) for name in plan['sources']}
    if any(source_identity(source) != plan['sources'][name] for name, source in sources.items()):
        raise RuntimeError('A frozen source snapshot changed')
    if source_identity(seed_files(ROOT)) != plan['sources']['baseline']:
        raise RuntimeError('The normal starter changed. Prepare a fresh study directory.')
    return plan, sources


def calibrate(directory, plan, sources):
    record = {'started': now(), 'sources': plan['sources'], 'trusted_sha256': plan['trusted_sha256'], 'variants': {}}
    store = Store(directory / 'calibration/sessions')
    for name, source in sources.items():
        frozen = freeze_source(store, source, name)
        result = run_regressions(ROOT, store, frozen)
        record['variants'][name] = result
        atomic_json(directory / 'calibration.json', record)
        if not result['passed']:
            raise RuntimeError('Protected regressions failed for ' + name)
    settings = SimpleNamespace(values={**plan['config'], 'provider': 'demo'}, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, lambda _: study.benchmark.ScriptedClient([
        {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 navigation_probe.py'}}}, {'status': 'completed'}]))
    try:
        frozen = freeze_source(store, sources['outline'], 'Outline calibration')
        result = run_task(agent, store, settings.values, {'name': 'outline-calibration', 'task': 'Run the fixture.',
            'fixtures': {'navigation_probe.py': (ROOT / 'evaluations/navigation_probe.py').read_text(encoding='utf-8')},
            'checks': [{'path': 'navigation-result.json', 'json': {'passed': True, 'checks': {
                'registered_native': True, 'registered_json': True, 'names': True, 'preserved_bytes': True,
                'Example_section': True, 'Example.method_section': True, 'reject_../outside.py': True, 'reject_escape.py': True}}}]}, frozen, 90)
        record['outline_probe'] = result
        record['passed'] = result['passed']
        atomic_json(directory / 'calibration.json', record)
        if not record['passed']:
            raise RuntimeError('Outline calibration failed')
    finally:
        agent.close()
    return record


def trial_costs(row):
    captured = bool(row.get('capture', {}).get('complete') and not row.get('capture', {}).get('observer_failed'))
    metrics = {}
    for name in ('input_tokens', 'output_tokens', 'call_seconds', 'transport_seconds'):
        value = row.get('calls', {}).get('measurements', {}).get(name, {})
        metrics[name] = {**value, 'known_sum': value.get('known_sum'),
                         'complete': bool(captured and value.get('complete'))}
    for name in ('model_task_seconds', 'total_trial_seconds'):
        value = row.get(name, row.get('run', {}).get('seconds') if name == 'model_task_seconds' else None)
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        # Host wall time can be known even when the provider trace is incomplete.
        metrics[name] = {'known_sum': value if valid else None, 'complete': valid}
    return metrics


def comparison_summary(rows):
    summary = {'variants': {}, 'matched_success_pairs': []}
    for name in sorted({row['variant'] for row in rows} or {'baseline', 'outline'}):
        launched = [row for row in rows if row['variant'] == name]
        graded = [row for row in launched if 'review' in row]
        summary['variants'][name] = {'launched': len(launched), 'graded': len(graded),
            'accepted': sum(row['review']['accepted'] for row in graded),
            'verified_upgrades': sum(row['review'].get('verified_upgrade', row['review']['accepted']) for row in graded),
            'budget_stops': sum(row.get('run', {}).get('failure_kind') == 'budget' or row.get('run', {}).get('timed_out', False) for row in launched),
            'all_launched_wire_requests': sum(row.get('calls', {}).get('wire_requests', 0) for row in launched),
            'all_model_task_seconds': round(sum(row.get('model_task_seconds', row.get('run', {}).get('seconds', 0)) for row in launched), 2),
            'capture_complete_trials': sum(bool(row.get('capture', {}).get('complete')) for row in launched),
            'operator_stops': sum(row.get('operator_stop', False) for row in launched)}
        costs = [trial_costs(row) for row in launched]
        measurements = {}
        for metric in ('input_tokens', 'output_tokens', 'call_seconds', 'transport_seconds', 'model_task_seconds', 'total_trial_seconds'):
            values = [cost[metric]['known_sum'] for cost in costs if cost[metric]['known_sum'] is not None]
            complete = bool(launched and all(cost[metric]['complete'] for cost in costs))
            measurements[metric] = {'known_sum': sum(values) if values else None,
                'complete': complete, 'status': 'complete' if complete else 'partial' if values else 'unavailable',
                'trials_with_measurements': len(values), 'complete_trials': sum(cost[metric]['complete'] for cost in costs),
                'expected_trials': len(launched)}
            summary['variants'][name]['all_launched_' + metric] = measurements[metric]['known_sum']
        summary['variants'][name]['measurements'] = measurements
        summary['variants'][name]['cost_totals_complete'] = all(value['complete'] for value in measurements.values())
        summary['variants'][name]['runtime_errors'] = [row['run'].get('failure_kind') or row['run'].get('detail')
            for row in launched if row.get('run', {}).get('status') == 'error']
    for task, repeat in sorted({(row['task'], row['repeat']) for row in rows}):
        pair = {row['variant']: row for row in rows if row['task'] == task and row['repeat'] == repeat}
        if len(pair) == 2 and all(row.get('review', {}).get('accepted') for row in pair.values()):
            costs = {name: trial_costs(row) for name, row in pair.items()}
            comparable = {metric: all(cost[metric]['complete'] for cost in costs.values())
                          for metric in next(iter(costs.values()))}
            summary['matched_success_pairs'].append({'task': task, 'repeat': repeat,
                'comparable_cost_metrics': comparable, 'cost_totals_complete': all(comparable.values()),
                'complete_observations': all(row.get('capture', {}).get('complete') and
                    not row.get('capture', {}).get('observer_failed') for row in pair.values()),
                **{name: {'calls': row.get('calls'), 'seconds': row['run']['seconds'], 'navigation': row.get('navigation'),
                          'measurements': costs[name]}
                   for name, row in pair.items()}})
    return summary


def run(args, suite=None):
    directory = private_path(args.input)
    plan, sources = load_plan(directory)
    if args.check_only:
        (suite.calibrate if suite else calibrate)(directory, plan, sources)
        print('Calibration passed; no model inference started.')
        return
    path = directory / 'results.json'
    report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'created': now(), 'trials': [], 'operator_candidate_repairs': [], 'candidate_promotions': 0}
    # Every launched schedule cell remains visible, including operator stops.
    for row in report['trials']:
        if 'review' not in row and 'run' not in row and not row.get('operator_stop'):
            row['infrastructure_failure'] = 'Previous runner ended before saving a result; no automatic retry.'
    report['status'] = 'running'
    atomic_json(path, report)
    settings = SimpleNamespace(values=dict(plan['config']), key=lambda: '')
    engine = LocalRuntime(ROOT, settings)
    active_agent = None
    used_model = False
    try:
        previous = directory / 'calibration.json'
        calibration = json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else {}
        if not (calibration.get('passed') and calibration.get('sources') == plan['sources'] and
                calibration.get('trusted_sha256') == plan['trusted_sha256']):
            (suite.calibrate if suite else calibrate)(directory, plan, sources)
        settings.values['base_url'] = engine.ensure_service(allow_download=False)
        identity = model_identity(settings.values)
        if report.get('model_identity') and report['model_identity'] != identity:
            raise RuntimeError('The model/runtime identity changed. Prepare a fresh study; existing results were preserved.')
        report['model_identity'] = identity
        if not identity.get('digest'):
            raise RuntimeError('Prepare the cached Qwen3.5 9B model before running this study.')
        for cell in plan['schedule']:
            if any(row['id'] == cell['id'] for row in report['trials']):
                continue
            load_plan(directory)
            if model_identity(settings.values) != identity:
                raise RuntimeError('The model/runtime identity changed during this study.')
            row = {**cell, 'started': now()}
            report['trials'].append(row)
            atomic_json(path, report)
            trial = directory / 'trials' / cell['id']
            store = Store(trial / 'sessions')
            recorder = CallRecorder(trial / 'provider-calls.jsonl', labels={**cell, 'source_sha256': plan['sources'][cell['variant']]})
            clients = []
            budget = GeneratedTokenBudget(plan['output_token_budget'])
            def factory(config):
                client = suite.client(config, cell, recorder, budget) if suite else BudgetModelClient(config, observer=recorder, token_budget=budget)
                clients.append(client)
                return client
            active_agent = IsolatedAgent(ROOT, store, settings, factory)
            trial_started = time.monotonic()
            try:
                print('TRIAL', cell['id'], flush=True)
                source = sources[cell['variant']]
                frozen = freeze_source(store, source, 'Frozen ' + cell['variant'])
                used_model = True
                row['run'] = study.benchmark.enrich(store, suite.run_case(active_agent, store, settings.values, plan, cell, frozen) if suite else run_task(active_agent, store, settings.values, {
                    'name': cell['task'], 'task': 'Add exactly one new public tool. ' + plan['contracts'][cell['task']] + study.RECIPE,
                    'checks': []}, frozen, plan['timeout']))
                row['model_task_seconds'] = row['run']['seconds']
                row['review'] = (suite.assess(plan, cell, store, source, row['run'], trial / 'review') if suite else
                                 study.assess(store, source, row['run'], cell['task'], trial / 'review'))
                events = read_events(store.directory(row['run']['session']) / 'events.jsonl')
                if suite:
                    events = suite.events_for_trial(plan, events)
                row['navigation'] = navigation_metrics(events)
                row['journal_outcomes'] = {name: sum(event['type'] == name for event in events)
                                            for name in ('provider_cutoff', 'invalid_response', 'context_handoff')}
                if suite:
                    row.update(suite.metrics(plan, cell, events, row, clients))
            except KeyboardInterrupt:
                row['operator_stop'] = True
                raise
            except Exception as error:
                row['infrastructure_failure'] = type(error).__name__ + ': ' + str(error)
                raise
            finally:
                active_agent.close()
                active_agent = None
                row.setdefault('model_task_seconds', round(time.monotonic() - trial_started, 3))
                row['total_trial_seconds'] = round(time.monotonic() - trial_started, 3)
                row['calls'] = call_metrics(read_events(recorder.path))
                row['token_budget'] = budget.summary()
                row['capture'] = recorder.summary()
                row['capture']['observer_failed'] = any(client.observation_failed for client in clients)
                row['capture']['complete'] = bool(row['capture']['complete'] and not row['capture']['observer_failed'] and
                    row['calls']['trace_complete'])
                row['finished'] = now()
                report['summary'] = comparison_summary(report['trials'])
                atomic_json(path, report)
            print('RESULT', cell['id'], row['review']['accepted'], flush=True)
        report.update(status='completed', finished=now())
    except KeyboardInterrupt:
        report['status'] = 'operator_stopped'
    except BaseException as error:
        report.update(status='infrastructure_error', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        if active_agent:
            active_agent.close()
        if used_model:
            try:
                request_json(settings.values['base_url'] + '/api/generate', {'model': settings.values['model'], 'keep_alive': 0}, timeout=30)
            except Exception:
                pass
        engine.close()
        report['summary'] = comparison_summary(report['trials'])
        atomic_json(path, report)


def replay(args):
    directory, output = private_path(args.input), private_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    report = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
    rows = []
    for profile, value in report['profiles'].items():
        runs = [(row['name'], row['run']) for row in value['trials']]
        if 'growth' in value:
            runs.append(('staged-audit', value['growth']['first']))
        for task, result in runs:
            events = read_events(directory / profile / 'sessions' / result['session'] / 'events.jsonl')
            rows.append({'profile': profile, 'task': task, 'status': result['status'],
                         'navigation': navigation_metrics(events)})
    atomic_json(output / 'replay.json', {'source_sha256': report['source_sha256'], 'trials': rows,
        'analysis_sha256': hashlib.sha256((ROOT / 'evaluations/observations.py').read_bytes()).hexdigest(),
        'scope': 'Offline replay only. Historical traces lack the new provider recorder; no model inference ran.'})
    print('Analysed', len(rows), 'saved trials; no inference started.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--output', required=True)
    p.add_argument('--repeats', type=int, choices=range(1, 6), default=3)
    p.add_argument('--timeout', type=int, default=DEFAULT_TASK_SECONDS)
    p.add_argument('--output-token-budget', type=int, default=DEFAULT_OUTPUT_TOKENS)
    p = commands.add_parser('run')
    p.add_argument('--input', required=True)
    p.add_argument('--check-only', action='store_true')
    p = commands.add_parser('replay')
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'replay': replay}[args.command](args)
