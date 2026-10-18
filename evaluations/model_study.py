"""Resumable local model screens and full first/second-pass qualification.

    python evaluations/model_study.py prepare --profiles profiles.json --output .data/study --mode full --repeats 1
    python evaluations/model_study.py run --input .data/study

Connect already prepared local inference services. This runner downloads nothing,
changes no app preferences and executes candidates only in disposable VMs.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluations')]
from autoproteus.providers import tool_definitions
from controller.appliance import Appliance
from controller.compatibility import model_identity
from controller.config import DEFAULTS
from controller.evaluation import candidate_source, freeze_source, growth_scores, run_regressions, run_task, source_identity, tool_use
from controller.isolation import Artifacts, IsolatedAgent, VMLease, seed_files
from controller.providers import ProviderError
from controller.storage import Store, atomic_json, now
from observations import CallRecorder, call_metrics, latency_metrics, navigation_metrics, read_events
from run_budget import BudgetModelClient, GeneratedTokenBudget, DEFAULT_OUTPUT_TOKENS, DEFAULT_TASK_SECONDS
from study_support import ResultCache, StudyQueue, Timings, file_identity, identity
import generalization as study


def private(path):
    path = (ROOT / path).resolve()
    if not path.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Study outputs must stay inside .data')
    return path


def trusted_files():
    paths = list((ROOT / 'controller').glob('*.py'))
    paths += [ROOT / name for name in ('guest/worker.py', 'controller/runtime-lock.json',
        'controller/managed-runtime-lock.json', 'tests/test_seed.py', 'tests/test_text_helpers.py',
        'evaluations/model_study.py', 'evaluations/study_support.py', 'evaluations/generalization.py',
        'evaluations/generalization-probe.py', 'evaluations/local-model-benchmark.py',
        'evaluations/local-feature-probe.py', 'evaluations/local-upgrade-tasks.json',
        'evaluations/observations.py', 'evaluations/run_budget.py', 'evaluations/invoke_tool.py', 'evaluations/tasks.json')]
    return {p.relative_to(ROOT).as_posix(): file_identity(p) for p in paths}


def environment():
    # Appliance.verify checks the installed bytes against this complete inventory
    # before any cached calibration can be reused.
    record = ROOT / '.runtime/isolation/installed.json'
    return {'platform': platform.platform(), 'machine': platform.machine(),
            'python': platform.python_version(), 'root': str(ROOT),
            'appliance_inventory_sha256': file_identity(record) if record.exists() else None}


def prepare(args):
    output = private(args.output)
    if output.exists():
        raise ValueError('Prepare into a new directory; existing evidence is preserved')
    profiles = json.loads(Path(args.profiles).read_text(encoding='utf-8'))
    if not isinstance(profiles, list) or not profiles:
        raise ValueError('Supply a nonempty list of profiles')
    seen = set()
    for profile in profiles:
        slug = profile['id']
        if not isinstance(slug, str) or not slug or len(slug) > 60 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in slug) or slug in seen:
            raise ValueError('Profiles need unique lowercase IDs')
        seen.add(slug)
        config = profile['config'] = {**DEFAULTS, 'configured': True, 'terminal': True, **profile['config']}
        if config['provider'] not in ('ollama', 'hosted') or urlparse(config['base_url']).hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('This runner accepts local inference endpoints only')
        if config['response_tokens'] >= config['context_tokens']:
            raise ValueError('Response allowance must be smaller than context')
        for path, digest in profile.get('assets', {}).items():
            if file_identity(path) != digest:
                raise ValueError('Profile asset failed verification: ' + path)
    source = seed_files(ROOT)
    plan = {'created': now(), 'mode': args.mode, 'repeats': args.repeats if args.repeats is not None else (3 if args.mode == 'full' else 1),
            'source': source, 'source_sha256': source_identity(source), 'profiles': profiles,
            'trusted_sha256': trusted_files(), 'environment': environment(),
            'contracts': study.CONTRACTS, 'recipe': study.RECIPE,
            'tasks': json.loads((ROOT / 'evaluations/tasks.json').read_text(encoding='utf-8')),
            'tools': tool_definitions(True),
            'invoke_tool': (ROOT / 'evaluations/invoke_tool.py').read_text(encoding='utf-8'),
            'deadline': args.timeout, 'generated_tokens': args.output_token_budget,
            'ordinary_deadline': 240, 'ordinary_generated_tokens': 8192,
            'ordinary_tasks': ['exact-file', 'precise-edit', 'recovery', 'unicode', 'bug-fix'],
            'upgrade_tasks': (list(study.CONTRACTS) if args.mode == 'full' else
                              ['sha256_file', 'format_json'] if args.mode == 'screen' else []),
            'scope': 'Screens select profiles for qualification; incomplete screens are not model rankings. '
                     'Each accepted first upgrade receives one fresh second-extension task. '
                     'Retries, untested cells, cached checks and infrastructure failures are recorded separately.'}
    if plan['repeats'] < 1 or args.timeout < 1 or args.output_token_budget < 1:
        raise ValueError('Repeat and budget values must be positive')
    output.mkdir(parents=True)
    atomic_json(output / 'plan.json', plan)
    (output / 'plan.sha256').write_text(identity(plan), encoding='ascii')
    for name in plan['trusted_sha256']:
        target = output / 'trusted-runner' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    print('Prepared', args.mode, 'with', len(profiles), 'profiles and', plan['repeats'], 'repeat(s). No inference started.', flush=True)


def check(plan):
    if source_identity(seed_files(ROOT)) != plan['source_sha256'] or trusted_files() != plan['trusted_sha256']:
        raise ValueError('Seed or trusted runner changed; prepare a new plan')
    if environment() != plan['environment']:
        raise ValueError('Execution environment changed; prepare a new plan')


class Checks:
    def __init__(self, folder, plan):
        # Candidate observations can be reused inside one attempt only. A fresh
        # inference repetition still gets fresh independent VM executions.
        self.cache = ResultCache(folder / 'scripted-check-cache')
        self.base = {'trusted': plan['trusted_sha256'], 'environment': plan['environment']}
        self.receipts = []

    def run(self, store, frozen, kind, execute, feature=None):
        key = {**self.base, 'source': source_identity(candidate_source(store, frozen)),
               'kind': kind, 'feature': feature}
        value, receipt = self.cache.run(key, execute, lambda row: row.get('passed') is True)
        self.receipts.append({'kind': kind, 'feature': feature, **receipt})
        return value

    def feature(self, store, frozen, name):
        return self.run(store, frozen, 'feature', lambda: study.verify_feature(store, frozen, name), name)

    def public(self, store, frozen, name):
        return self.run(store, frozen, 'fresh-worker-public', lambda: study.verify_public(store, frozen, name), name)

    def regressions(self, root, store, frozen):
        return self.run(store, frozen, 'regressions', lambda: run_regressions(root, store, frozen))

    def assess(self, store, source, result, name, output):
        output.mkdir(parents=True)
        return study.benchmark.assess(store, source, result, name, output, self.feature, self.public, self.regressions)


def metrics(folder, recorder, clients):
    events = read_events(recorder.path)
    capture = recorder.summary()
    capture['observer_failed'] = any(client.observation_failed for client in clients)
    return {'calls': call_metrics(events), 'latency': latency_metrics(events), 'capture': capture}


def benchmark(folder, config, plan):
    recorder = CallRecorder(folder / 'provider-calls.jsonl')
    response = min(config['response_tokens'], 256 if config.get('thinking') is False else 1024)
    client = BudgetModelClient({**config, 'response_tokens': response}, token_budget=GeneratedTokenBudget(response * 2), observer=recorder)
    results = []
    started = time.monotonic()
    for length in (0, min(24000, (config['context_tokens'] - 1024) // 2)):
        instruction = ('Call finish with status completed and message exactly BENCH_READY. Do not call any other tool.'
                       if config['protocol'] == 'native' else
                       'Return exactly {"status":"completed","message":"BENCH_READY"} with no other text.')
        reference = 'alpha beta gamma\n' * (length // 17)
        messages = [{'role': 'system', 'content': 'Follow the final instruction.'},
                    {'role': 'user', 'content': 'Reference material:\n' + reference + '\n' + instruction}]
        row = {'reference_characters': len(reference), 'started': now()}
        try:
            answer = client.complete(messages, threading.Event(), tools=plan['tools'])
            value = json.loads(answer['content'])
            row.update(passed=value.get('status') == 'completed' and value.get('message') == 'BENCH_READY' and 'action' not in value,
                       usage=answer.get('usage', {}), response=value)
        except (ProviderError, ValueError) as error:
            row.update(passed=False, error=str(error), category=getattr(error, 'category', 'protocol'))
        results.append(row)
    return {'passed': all(row['passed'] for row in results), 'requests': results,
            'seconds': round(time.monotonic() - started, 3), **metrics(folder, recorder, [client]),
            'scope': 'Inference-only speed/protocol screen. No model-chosen tool executes. '
                     'First measured call and longer-prompt call; cache warmth is not controlled.'}


def trial(folder, task, source, config, plan, feature=None, earlier=None):
    store = Store(folder / 'sessions')
    recorder = CallRecorder(folder / 'provider-calls.jsonl')
    budget = GeneratedTokenBudget(plan['generated_tokens'] if feature else plan['ordinary_generated_tokens'])
    clients = []
    def factory(values):
        client = BudgetModelClient(values, token_budget=budget, observer=recorder)
        clients.append(client)
        return client
    settings = SimpleNamespace(values=config, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, factory)
    if agent.execution.mode != 'vm':
        raise ValueError('Disposable VMs are required')
    checks = Checks(folder, plan)
    timings = Timings()
    row = {'task': task['name'], 'earlier': earlier, 'added': feature, 'operator_candidate_repairs': []}
    atomic_json(folder / 'task.json', task)
    started = time.monotonic()
    try:
        with timings.measure('development_or_basic'):
            row['run'] = run_task(agent, store, config, task, freeze_source(store, source, 'Frozen input'),
                                  plan['deadline'] if feature else plan['ordinary_deadline'])
        session = store.get(row['run']['session'])
        row['navigation'] = navigation_metrics(study.journal(store, session))
        if feature:
            with timings.measure('independent_grading'):
                row['review'] = checks.assess(store, source, row['run'], feature, folder / 'review')
            if earlier:
                edited = candidate_source(store, session)
                frozen = freeze_source(store, edited, 'Exact combined candidate')
                with timings.measure('retention_grading'):
                    row['retained'] = checks.feature(store, frozen, earlier)
                    row['retained_public'] = checks.public(store, frozen, earlier)
                row['verified_extension'] = study.verified(row['review'])
                artifact = 'sample.txt' if earlier == 'csv_preview' else 'inventory.json'
                try:
                    row['stage_order_preserved'] = Artifacts(store, session).read(artifact) == task['fixtures'][artifact].encode()
                except (OSError, ValueError):
                    row['stage_order_preserved'] = False
                retained = row['retained']['passed'] and row['retained_public']['passed']
                remaining = plan['deadline'] - (time.monotonic() - started)
                if (row['verified_extension'] and retained and row['stage_order_preserved'] and remaining > 0 and
                        session['status'] in ('completed', 'waiting') and not row['run']['timed_out'] and not budget.summary()['exhausted']):
                    with timings.measure('activation_and_final_use'):
                        agent.restart_seed(session, handoff='concise')
                        row['final'] = study.wait(agent, session, remaining)
                    row['final_source_unchanged'] = source_identity(candidate_source(store, session)) == source_identity(edited)
                    expected = task['fixtures'][artifact] if earlier == 'csv_preview' else json.dumps(
                        json.loads(task['fixtures'][artifact]), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
                    try:
                        raw = Artifacts(store, session).read(artifact)
                        receipt = json.loads(Artifacts(store, session).read('audit.json'))
                        correct = raw == expected.encode() and all(receipt.get(key) == value for key, value in
                            {'path': artifact, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}.items())
                        if earlier == 'csv_preview':
                            import csv, io
                            rows = list(csv.reader(io.StringIO(task['fixtures'][artifact], newline='')))
                            correct = correct and receipt.get('rows') == rows[:5] and receipt.get('truncated') == (len(rows) > 5)
                    except (OSError, ValueError, AttributeError):
                        correct = False
                    row['final_usage'] = tool_use(study.latest_run(study.journal(store, session)))
                    row['final_artifacts_correct'] = correct
                    row['scores'] = growth_scores(row['final_source_unchanged'], retained,
                        session['status'] == 'completed' and not row['final']['timed_out'], correct,
                        row['final_usage'], [earlier, feature])
    finally:
        agent.close()
        row.update(token_budget=budget.summary(), timings=timings.seconds, check_cache=checks.receipts,
                   total_seconds=round(time.monotonic() - started, 3), **metrics(folder, recorder, clients))
        # This residual includes VM startup, guest tools and orchestration. It is
        # not a separately measured VM boot time or a true time-to-first-token.
        measured = row['calls']['measurements']['call_seconds']
        row['timings']['vm_tools_and_orchestration_seconds'] = (round(max(0, row['total_seconds'] -
            sum(timings.seconds.get(key, 0) for key in ('independent_grading', 'retention_grading')) - measured['known_sum']), 6)
            if measured['complete'] else None)
        atomic_json(folder / 'result.json', row)
    return row


def growth_task(parent, plan):
    added = 'sha256_file' if parent == 'format_json' or parent == 'csv_preview' else 'format_json'
    sample, arguments, _, _ = study.sample_case(parent)
    fixtures = {'sample.txt': sample, 'inventory.json': '{"z":[2,false],"a":"café 猫"}',
                'experience/invoke_tool.py': plan['invoke_tool']}
    final = ('Use csv_preview and sha256_file on sample.txt. Write audit.json with path="sample.txt", bytes, sha256, '
             'rows (default preview) and truncated matching the actual results.' if parent == 'csv_preview' else
             'Use format_json to format inventory.json and sha256_file to hash its final bytes. '
             'Write audit.json with path="inventory.json", bytes and sha256 matching the formatted file.')
    return added, {'name': 'second-extension-audit', 'checks': [], 'fixtures': fixtures, 'task':
        'Your active seed already includes the independently verified ' + parent + ' tool. Use it on sample.txt with arguments ' +
        json.dumps(arguments) + '. Then add exactly one new tool: ' + plan['contracts'][added] +
        plan['recipe'].replace('Finish completed only after implementing and verifying the feature.', '') +
        '\nPreserve every existing capability and test. Keep inventory.json unchanged during development; '
        'use disposable examples. You can invoke an edited tool before its full suite passes with '
        'python3 experience/invoke_tool.py TOOL_NAME \'{"path":"sample.txt"}\'. '
        'Check actual file contents as well as return values. After development checks pass, finish needs_input requesting activation. '
        'After independent verification and activation, ' + final +
        ' Inspect the input and receipt, then finish completed. Do not edit the seed after activation.'}


def summarize(queue, plan):
    profiles = {}
    for profile in plan['profiles']:
        prefix = profile['id'] + '_'
        rows = [row for key, attempts in queue.data['cells'].items() if key.startswith(prefix)
                for row in attempts if row['state'] == 'completed']
        all_rows = [row for key, attempts in queue.data['cells'].items() if key.startswith(prefix)
                    for row in attempts if row['attempt'] > 0]
        first = [row['result'] for row in rows if row['cell'][len(prefix):].startswith('first_')]
        growth = [row['result'] for row in rows if row['cell'][len(prefix):].startswith('growth_')]
        speed = [row['result'] for row in rows if row['cell'][len(prefix):].startswith('benchmark_')]
        profiles[profile['id']] = {'benchmarks': speed,
            'scheduled_first_tasks': len(plan['upgrade_tasks']) * plan['repeats'],
            'first_attempts': sum(row['cell'][len(prefix):].startswith('first_') for row in all_rows), 'first_finished': len(first),
            'first_verified': sum(study.verified(row.get('review', {})) for row in first),
            'first_accepted': sum(bool(row.get('review', {}).get('accepted')) for row in first),
            'second_attempts': sum(row['cell'][len(prefix):].startswith('growth_') for row in all_rows), 'second_finished': len(growth),
            'second_verified': sum(bool(row.get('verified_extension')) for row in growth),
            'complete_growth': sum(bool(row.get('scores', {}).get('functional_growth')) for row in growth)}
    return {'mode': plan['mode'], 'scope': plan['scope'], 'queue': queue.summary(), 'profiles': profiles}


def run(args):
    # A second runner must not overwrite the ledger or duplicate inference.
    lease = VMLease(private(args.input))
    try:
        lease.acquire(threading.Event(), time.monotonic() + 1)
        return _run(args)
    finally:
        lease.close()


def _run(args):
    output = private(args.input)
    plan = json.loads((output / 'plan.json').read_text(encoding='utf-8'))
    if identity(plan) != (output / 'plan.sha256').read_text().strip():
        raise ValueError('Frozen plan changed')
    check(plan)
    if plan['mode'] != 'benchmark':
        Appliance(ROOT).verify()
    for profile in plan['profiles']:
        for path, digest in profile.get('assets', {}).items():
            if file_identity(path) != digest:
                raise ValueError('Profile asset changed: ' + path)
    queue = StudyQueue(output, identity(plan))
    for cell_id in args.retry:
        previous = queue.latest(cell_id)
        if not previous or previous['state'] not in ('interrupted', 'error'):
            raise ValueError('--retry requires an existing interrupted/error cell: ' + cell_id)
    cache = ResultCache(ROOT / '.data/study-cache/calibration')
    def calibration():
        folder = output / 'grader-calibration'
        suffix = 1
        while folder.exists():
            suffix += 1
            folder = output / ('grader-calibration-%03d' % suffix)
        study.self_check(folder, plan['source'])
        return {'passed': True, 'evidence': str(folder),
                'report_sha256': file_identity(folder / 'calibration.json'),
                'report': json.loads((folder / 'calibration.json').read_text(encoding='utf-8'))}
    def valid_calibration(row):
        try:
            return row.get('passed') is True and file_identity(Path(row['evidence']) / 'calibration.json') == row['report_sha256']
        except (OSError, KeyError, TypeError):
            return False
    if plan['mode'] != 'benchmark':
        value, receipt = cache.run({'source': plan['source_sha256'], 'trusted': plan['trusted_sha256'],
                                    'environment': plan['environment'], 'kind': 'generalization-calibration'},
                                   calibration, valid_calibration)
        atomic_json(output / 'calibration-receipt.json', {'cache': receipt, 'result': value})
    try:
        for profile in plan['profiles']:
            config = profile['config']
            public_identity = model_identity(config)
            marker = output / (profile['id'] + '-identity.json')
            if marker.exists() and json.loads(marker.read_text()) != public_identity:
                raise ValueError('Inference service identity changed; prepare a new plan')
            atomic_json(marker, public_identity)
            def cell(suffix, execute):
                check(plan)
                if model_identity(config) != public_identity:
                    raise ValueError('Inference service identity changed during study')
                name = profile['id'] + '_' + suffix
                previous = queue.latest(name)
                if not previous or (previous['state'] in ('interrupted', 'error') and name in args.retry):
                    print('START', name, flush=True)
                def checked_execute(folder):
                    result = execute(folder)
                    # Also check the final cell: a change during a long attempt
                    # must not become a completed frozen-study observation.
                    check(plan)
                    if model_identity(config) != public_identity:
                        raise ValueError('Inference service identity changed during the attempt')
                    return result
                row = queue.run(name, checked_execute, retry=name in args.retry)
                atomic_json(output / 'summary.json', summarize(queue, plan))
                print('CELL', name, row['state'], flush=True)
                return row.get('result', {})
            for repeat in range(1, (plan['repeats'] if plan['mode'] == 'benchmark' else 1) + 1):
                speed = cell('benchmark_%02d' % repeat, lambda folder: benchmark(folder, config, plan))
            if plan['mode'] == 'benchmark':
                continue
            names = plan['ordinary_tasks'] if plan['mode'] == 'full' else plan['ordinary_tasks'][:3]
            ordinary = []
            if speed.get('passed'):
                for name in names:
                    task = next(item for item in plan['tasks'] if item['name'] == name)
                    ordinary.append(cell('basic_' + name, lambda folder, task=task: trial(folder, task, plan['source'], config, plan)))
            else:
                for name in names:
                    queue.skip(profile['id'] + '_basic_' + name, 'Inference screen did not qualify; not run')
            gate = speed.get('passed') and sum(row.get('run', {}).get('passed', False) for row in ordinary) >= len(names) - 1
            for repeat in range(1, plan['repeats'] + 1):
                features = plan['upgrade_tasks']
                features = features[(repeat - 1) % len(features):] + features[:(repeat - 1) % len(features)]
                for feature in features:
                    first_id = 'first_%02d_%s' % (repeat, feature)
                    growth_id = 'growth_%02d_%s' % (repeat, feature)
                    if not gate:
                        for suffix in (first_id, growth_id):
                            queue.skip(profile['id'] + '_' + suffix, 'Protocol/basic gate did not qualify; not an upgrade failure')
                        continue
                    task = {'name': feature, 'task': 'Add exactly one new public tool. ' + plan['contracts'][feature] + plan['recipe'], 'checks': []}
                    first = cell(first_id, lambda folder: trial(folder, task, plan['source'], config, plan, feature))
                    if first.get('review', {}).get('accepted'):
                        saved = queue.latest(profile['id'] + '_' + first_id)
                        source = json.loads((Path(saved['folder']) / 'review/candidate-source.json').read_text())
                        added, task = growth_task(feature, plan)
                        cell(growth_id, lambda folder: trial(folder, task, source, config, plan, added, feature))
                    else:
                        queue.skip(profile['id'] + '_' + growth_id, 'First upgrade not fully accepted; no accepted parent exists')
        summary = summarize(queue, plan)
        summary['status'] = 'needs_attention' if summary['queue']['unresolved_cells'] else 'completed'
        atomic_json(output / 'summary.json', summary)
    finally:
        # Endpoint lifecycle belongs to its owner. No running app is shut down.
        atomic_json(output / 'queue-summary.json', queue.summary())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--profiles', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--mode', choices=('benchmark', 'screen', 'full'), default='screen')
    p.add_argument('--repeats', type=int)
    p.add_argument('--timeout', type=int, default=DEFAULT_TASK_SECONDS)
    p.add_argument('--output-token-budget', type=int, default=DEFAULT_OUTPUT_TOKENS)
    p = commands.add_parser('run')
    p.add_argument('--input', required=True)
    p.add_argument('--retry', action='append', default=[], metavar='CELL_ID', help='Explicit new attempt after interruption/error; preserves the original')
    args = parser.parse_args()
    {'prepare': prepare, 'run': run}[args.command](args)
