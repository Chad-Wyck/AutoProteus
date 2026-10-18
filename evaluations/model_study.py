"""Resumable local model screens and full first/second-pass qualification.

    python evaluations/model_study.py prepare --profiles profiles.json --output .data/study --mode full --repeats 1
    python evaluations/model_study.py run --input .data/study

Connect already prepared local inference services. This runner downloads nothing,
changes no app preferences and executes candidates only in disposable VMs.
"""
import argparse
import copy
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
from workflow_variants import TREATMENTS, variant, DEVELOPMENT_FOCUS, USE_FOCUS
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
        'evaluations/grader_faults.py', 'evaluations/workflow_variants.py', 'evaluations/workflow_support.py',
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
    experiment = getattr(args, 'experiment', None)
    if experiment:
        if args.mode != 'full':
            raise ValueError('Paired workflow experiments require full mode')
        plan['experiment'] = experiment
        plan['mask_settings'] = {'keep': getattr(args, 'mask_keep', 8), 'threshold': getattr(args, 'mask_threshold', 512)}
        plan['variants'] = {name: variant(source, name, **plan['mask_settings']) for name in ('baseline', experiment)}
        plan['scope'] += ' Paired opt-in treatment; original default seed remains unchanged. Success and matched-success costs are separate.'
        parent_path = getattr(args, 'parent_source', None)
        parent_tool = getattr(args, 'parent_tool', None)
        if bool(parent_path) != bool(parent_tool):
            raise ValueError('Provide both --parent-source and --parent-tool')
        if parent_path:
            if experiment != 'phases' or parent_tool not in study.CONTRACTS:
                raise ValueError('A supplied parent is supported only for the phase comparison')
            parent = json.loads(Path(parent_path).read_text(encoding='utf-8'))
            # Inert bytes only; actual regression/feature/public checks precede inference.
            source_identity(parent)
            plan['parent'] = {'source': parent, 'tool': parent_tool, 'sha256': source_identity(parent),
                              'provenance': str(Path(parent_path).resolve()), 'supplied_parent': True}
        elif experiment == 'phases':
            raise ValueError('Phase comparison requires one exact supplied parent and --parent-tool; it is independently checked before trials')
        reuse_path = getattr(args, 'reuse_task', None)
        if reuse_path:
            if not plan.get('parent'):
                raise ValueError('--reuse-task requires the phase comparison and a supplied parent')
            task = json.loads(Path(reuse_path).read_text(encoding='utf-8'))
            required = task.get('required_tools')
            if (not isinstance(required, list) or not required or any(name not in study.CONTRACTS for name in required)
                    or not isinstance(task.get('checks'), list) or not task['checks'] or not isinstance(task.get('task'), str)):
                raise ValueError('Reuse task needs a task, nonempty checks and required_tools from the known contracts')
            plan['reuse_task'] = task
    elif any(getattr(args, name, None) for name in ('parent_source', 'parent_tool', 'reuse_task')):
        raise ValueError('Parent/reuse options require --experiment phases')
    task_pack = getattr(args, 'task_pack', None)
    if task_pack:
        tasks = json.loads(Path(task_pack).read_text(encoding='utf-8'))
        if (not isinstance(tasks, list) or not tasks or any(not isinstance(task.get('name'), str) or
                not task.get('task') or not task.get('checks') for task in tasks) or
                len({task['name'] for task in tasks}) != len(tasks)):
            raise ValueError('Task pack needs uniquely named tasks with instructions and independent checks')
        plan['tasks'], plan['ordinary_tasks'] = tasks, [task['name'] for task in tasks]
        plan['task_pack'] = {'path': str(Path(task_pack).resolve()), 'sha256': file_identity(task_pack)}
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
    def __init__(self, folder, plan, deadline=None):
        # Candidate observations can be reused inside one attempt only. A fresh
        # inference repetition still gets fresh independent VM executions.
        self.cache = ResultCache(folder / 'scripted-check-cache')
        self.base = {'trusted': plan['trusted_sha256'], 'environment': plan['environment']}
        self.receipts = []
        self.deadline = deadline

    def run(self, store, frozen, kind, execute, feature=None):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.receipts.append({'kind': kind, 'feature': feature, 'skipped': 'shared_deadline'})
            return {'passed': False, 'timed_out': True, 'reason': 'Shared task deadline expired; check not launched.'}
        key = {**self.base, 'source': source_identity(candidate_source(store, frozen)),
               'kind': kind, 'feature': feature}
        def bounded():
            if self.deadline is not None and time.monotonic() >= self.deadline:
                return {'passed': False, 'timed_out': True, 'reason': 'Shared deadline expired; check not launched.'}
            return execute()
        value, receipt = self.cache.run(key, bounded, lambda row: row.get('passed') is True and
            (self.deadline is None or time.monotonic() < self.deadline))
        self.receipts.append({'kind': kind, 'feature': feature, **receipt})
        if self.deadline is not None and time.monotonic() >= self.deadline:
            value = {**value, 'passed': False, 'timed_out': True, 'reason': 'Check did not finish within the shared task deadline.'}
        return value

    def feature(self, store, frozen, name):
        return self.run(store, frozen, 'feature', lambda: study.verify_feature(store, frozen, name,
            **({'deadline': self.deadline} if self.deadline is not None else {})), name)

    def public(self, store, frozen, name):
        return self.run(store, frozen, 'fresh-worker-public', lambda: study.verify_public(store, frozen, name,
            **({'deadline': self.deadline} if self.deadline is not None else {})), name)

    def regressions(self, root, store, frozen):
        return self.run(store, frozen, 'regressions', lambda: run_regressions(root, store, frozen,
            **({'deadline': self.deadline} if self.deadline is not None else {})))

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
    task = copy.deepcopy(task)
    original_task = copy.deepcopy(task)
    reuse_only = not feature and bool(plan.get('reuse_task')) and task['name'] == plan['reuse_task']['name']
    focused = plan.get('treatment') == 'phases' and earlier is not None
    if focused:
        task['task'] += DEVELOPMENT_FOCUS
    elif plan.get('treatment') == 'phases' and reuse_only:
        task['task'] += USE_FOCUS
    store = Store(folder / 'sessions')
    recorder = CallRecorder(folder / 'provider-calls.jsonl')
    budget = GeneratedTokenBudget(plan['generated_tokens'] if feature or reuse_only else plan['ordinary_generated_tokens'])
    clients = []
    def factory(values):
        client = BudgetModelClient(values, token_budget=budget, observer=recorder)
        clients.append(client)
        return client
    settings = SimpleNamespace(values=config, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, factory)
    if agent.execution.mode != 'vm':
        raise ValueError('Disposable VMs are required')
    started = time.monotonic()
    deadline = started + (plan['deadline'] if feature or reuse_only else plan['ordinary_deadline'])
    checks = Checks(folder, plan, deadline=deadline)
    timings = Timings()
    row = {'task': task['name'], 'earlier': earlier, 'added': feature, 'operator_candidate_repairs': [],
           'treatment': plan.get('treatment', 'baseline'), 'stages': {'activated': False},
           'experimental_instructions': [DEVELOPMENT_FOCUS, USE_FOCUS] if focused else
                                       [USE_FOCUS] if reuse_only and plan.get('treatment') == 'phases' else []}
    atomic_json(folder / 'original-task.json', original_task)
    atomic_json(folder / 'task.json', task)
    try:
        with timings.measure('development_or_basic'):
            row['run'] = run_task(agent, store, config, task, freeze_source(store, source, 'Frozen input'),
                                  max(0, deadline - time.monotonic()), deadline=deadline)
        session = store.get(row['run']['session'])
        row['stages']['submitted'] = session['status'] in ('completed', 'waiting') and not row['run']['timed_out']
        row['stages']['activation_requested'] = session['status'] == 'waiting'
        row['navigation'] = navigation_metrics(study.journal(store, session))
        if reuse_only:
            usage = tool_use(study.journal(store, session))
            unchanged = source_identity(candidate_source(store, session)) == source_identity(source)
            row['reuse'] = {'source_unchanged': unchanged, 'usage': usage,
                'passed': bool(row['run']['passed'] and unchanged and set(plan['reuse_task']['required_tools']).issubset(
                    set(usage['direct']) | set(usage['development']))),
                'scope': 'Reuse of supplied verified capabilities; no new upgrade credit.'}
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
                row['stages']['independently_verified'] = row['verified_extension']
                row['stages']['submitted_source_sha256'] = source_identity(edited)
                artifact = 'sample.txt' if earlier == 'csv_preview' else 'inventory.json'
                try:
                    row['stage_order_preserved'] = Artifacts(store, session).read(artifact) == task['fixtures'][artifact].encode()
                except (OSError, ValueError):
                    row['stage_order_preserved'] = False
                retained = row['retained']['passed'] and row['retained_public']['passed']
                remaining = deadline - time.monotonic()
                remaining_actions = max(0, config['max_steps'] - session['steps'])
                if (row['verified_extension'] and retained and row['stage_order_preserved'] and remaining > 0 and
                        session['status'] in ('completed', 'waiting') and not row['run']['timed_out'] and not budget.summary()['exhausted'] and
                        (not plan.get('experiment') or remaining_actions > 0)):
                    with timings.measure('activation_and_final_use'):
                        if plan.get('experiment'):
                            # Both sides of the paired experiment share action,
                            # wall and generated-token allowances across stages.
                            settings.values = {**config, 'max_steps': remaining_actions}
                        if focused:
                            session['candidate_from'] = session['id']
                            agent.start(session, USE_FOCUS, candidate=session, handoff='concise', deadline=deadline)
                        else:
                            agent.restart_seed(session, handoff='concise', deadline=deadline)
                        row['stages']['activated'] = True
                        # Synchronous activation/setup consumes wall time too.
                        row['final'] = study.wait(agent, session, max(0, deadline - time.monotonic()))
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
                    row['stages'].update(correct_final_use=correct, explicit_finish=session['status'] == 'completed')
                    row['scores'] = growth_scores(row['final_source_unchanged'], retained,
                        session['status'] == 'completed' and not row['final']['timed_out'], correct,
                        row['final_usage'], [earlier, feature])
    finally:
        work_finished = time.monotonic()
        with timings.measure('cleanup'):
            agent.close()
        row['wall_budget'] = {'allowance_seconds': deadline - started,
            'work_seconds': round(work_finished - started, 6), 'deadline_reached': work_finished >= deadline,
            'deadline_overrun_seconds': round(max(0, work_finished - deadline), 6),
            'cleanup_seconds': timings.seconds['cleanup'],
            'scope': 'One deadline for development, grading, retention and final use. No new check starts after expiry. '
                     'Stopping workers and saving evidence can overrun; that delay and final cleanup are reported separately.'}
        if work_finished >= deadline and row.get('review', {}).get('accepted'):
            row['review'].update(accepted=False, autonomously_completed=False, deadline_exhausted=True)
            review_path = folder / 'review/review.json'
            if review_path.exists():
                atomic_json(review_path, row['review'])
        row.update(token_budget=budget.summary(), timings=timings.seconds, check_cache=checks.receipts,
                   total_seconds=round(time.monotonic() - started, 3), **metrics(folder, recorder, clients))
        # This residual includes VM startup, guest tools and orchestration. It is
        # not a separately measured VM boot time or a true time-to-first-token.
        measured = row['calls']['measurements']['call_seconds']
        row['timings']['vm_tools_and_orchestration_seconds'] = (round(max(0, row['total_seconds'] -
            sum(timings.seconds.get(key, 0) for key in ('independent_grading', 'retention_grading', 'cleanup')) - measured['known_sum']), 6)
            if measured['complete'] else None)
        atomic_json(folder / 'result.json', row)
    return row


def growth_feature(parent):
    return 'sha256_file' if parent in ('format_json', 'csv_preview') else 'format_json'


def growth_task(parent, plan):
    added = growth_feature(parent)
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
        reuse = [row['result'] for row in rows if row['cell'][len(prefix):].startswith('reuse_')]
        speed = [row['result'] for row in rows if row['cell'][len(prefix):].startswith('benchmark_')]
        profiles[profile['id']] = {'benchmarks': speed,
            'scheduled_first_tasks': 0 if plan.get('parent') else len(plan['upgrade_tasks']) * plan['repeats'] * len(plan.get('variants', {'baseline': []})),
            'first_attempts': sum(row['cell'][len(prefix):].startswith('first_') for row in all_rows), 'first_finished': len(first),
            'first_verified': sum(study.verified(row.get('review', {})) for row in first),
            'first_accepted': sum(bool(row.get('review', {}).get('accepted')) for row in first),
            'second_attempts': sum(row['cell'][len(prefix):].startswith('growth_') for row in all_rows), 'second_finished': len(growth),
            'second_verified': sum(bool(row.get('verified_extension')) for row in growth),
            'complete_growth': sum(bool(row.get('scores', {}).get('functional_growth')) for row in growth),
            'reuse_attempts': sum(row['cell'][len(prefix):].startswith('reuse_') for row in all_rows),
            'reuse_finished': len(reuse), 'reuse_passed': sum(bool(row.get('reuse', {}).get('passed')) for row in reuse)}
    report = {'mode': plan['mode'], 'scope': plan['scope'], 'queue': queue.summary(), 'profiles': profiles}
    if plan.get('experiment'):
        report['comparison'] = comparison(queue, plan)
    return report


def comparison(queue, plan):
    """Never rank a treatment using partial costs or excluding failed attempts."""
    groups, pairs = {}, {}
    for cell, attempts in queue.data['cells'].items():
        if not any(kind in cell for kind in ('_first_', '_growth_', '_reuse_')):
            continue
        for attempt in attempts:
            name = next((v for v in plan['variants'] if cell.endswith('_' + v)), None)
            if name is None or attempt['attempt'] == 0:
                continue
            group = groups.setdefault(name, {'launched': 0, 'finished': 0, 'successes': 0, 'attempt_costs': []})
            group['launched'] += 1
            row = attempt.get('result', {})
            if not row and attempt.get('folder'):
                try:
                    saved = json.loads((Path(attempt['folder']) / 'result.json').read_text(encoding='utf-8'))
                    if isinstance(saved, dict): row = saved
                except (OSError, ValueError):
                    pass
            # Record incomplete attempts as unknown costs; never zero.
            captured = row.get('capture', {}).get('complete') and not row.get('capture', {}).get('observer_failed')
            costs = {key: {**row.get('calls', {}).get('measurements', {}).get(key, {}),
                           'complete': bool(captured and row.get('calls', {}).get('measurements', {}).get(key, {}).get('complete'))}
                     for key in ('input_tokens', 'output_tokens', 'call_seconds')}
            for value in costs.values():
                value['status'] = 'complete' if value['complete'] else 'partial' if value.get('known_sum') is not None else 'unavailable'
            group['attempt_costs'].append(costs)
            if attempt['state'] != 'completed':
                continue
            success = bool(row.get('reuse', {}).get('passed') if '_reuse_' in cell else
                           row.get('scores', {}).get('functional_growth') if '_growth_' in cell else row.get('review', {}).get('accepted'))
            group['finished'] += 1
            group['successes'] += success
            # Explicit retries remain in totals but do not replace an original
            # attempt in a matched pair or select the best of several responses.
            if attempt['attempt'] == 1:
                pairs.setdefault(cell[:-len(name)-1], {})[name] = (success, row, costs)
    matched = []
    for cell, rows in pairs.items():
        if set(rows) != set(plan['variants']) or not all(value[0] for value in rows.values()):
            continue
        costs = {name: cost for name, (_, row, cost) in rows.items()}
        matched.append({'cell': cell, 'costs': costs, 'comparable': {
            key: all(value.get(key, {}).get('complete') is True for value in costs.values())
            for key in ('input_tokens', 'output_tokens', 'call_seconds')},
            'task_seconds': {name: row['total_seconds'] for name, (_, row, _) in rows.items()}})
    for group in groups.values():
        costs = group.pop('attempt_costs')
        group['measurements'] = {}
        for key in ('input_tokens', 'output_tokens', 'call_seconds'):
            values = [row[key]['known_sum'] for row in costs if row[key].get('known_sum') is not None]
            complete = bool(costs and all(row[key]['complete'] for row in costs))
            group['measurements'][key] = {'known_sum': sum(values) if values else None, 'complete': complete,
                'status': 'complete' if complete else 'partial' if values else 'unavailable',
                'expected_attempts': len(costs), 'complete_attempts': sum(row[key]['complete'] for row in costs)}
    return {'variants': groups, 'matched_original_successes': matched,
            'expense_scope': 'All attempts retained with full costs in queue/trials, including failed and interrupted work; matched pairs use original attempts only.',
            'supplied_parent': bool(plan.get('parent')),
            'kind': 'unchanged_capability_reuse' if plan.get('reuse_task') else 'supplied_parent_growth' if plan.get('parent') else 'first_and_second_upgrades'}


def workflow_requirements(plan):
    """One description drives both cache identity and the checks it represents."""
    parent = plan.get('parent', {}).get('tool')
    reuse = bool(plan.get('reuse_task'))
    required = set(plan.get('reuse_task', {}).get('required_tools', []))
    if parent:
        required.add(parent)
    return {'experiment': plan['experiment'], 'mode': 'reuse' if reuse else 'growth',
            'parent_tool': parent, 'required_existing_tools': sorted(required),
            'required_absent_tool': growth_feature(parent) if parent and not reuse else None}


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
    if plan.get('experiment'):
        # This calibration is tied to the exact copied input, never to a model's
        # claim of readiness. A supplied parent earns no first-upgrade credit.
        requirements = workflow_requirements(plan)
        inputs = {'source': plan.get('parent', {}).get('sha256', plan['source_sha256']),
                  'variants': {key: source_identity(value) for key, value in plan['variants'].items()},
                  'trusted': plan['trusted_sha256'], 'environment': plan['environment'], 'kind': 'workflow-inputs',
                  'requirements': requirements}
        def calibrate_inputs():
            store = Store(output / 'input-calibration/sessions')
            results = {}
            for name, source in plan['variants'].items():
                source = plan['parent']['source'] if plan.get('parent') else source
                frozen = freeze_source(store, source, 'Exact workflow input ' + name)
                results[name] = {'regressions': run_regressions(ROOT, store, frozen)}
                if plan.get('parent'):
                    for feature in requirements['required_existing_tools']:
                        results[name].update({feature: study.verify_feature(store, frozen, feature),
                                             feature + '_public': study.verify_public(store, frozen, feature)})
                    added = requirements['required_absent_tool']
                    if added:
                        absent = study.verify_feature(store, frozen, added)
                        cases = absent.get('probe', {}).get('checks', {})
                        results[name]['new_tool_absent'] = {'passed': not absent['passed'] and cases.get('registered') is False,
                                                           'evidence': absent}
                atomic_json(output / 'input-calibration.json', results)
                if not all(row['passed'] for row in results[name].values()):
                    raise ValueError('Workflow input failed independent checks: ' + name)
            return {'passed': True, 'requirements': requirements, 'results': results, 'evidence': str(output / 'input-calibration.json'),
                    'report_sha256': file_identity(output / 'input-calibration.json')}
        def valid_inputs(row):
            try:
                return (row.get('passed') is True and row.get('requirements') == requirements and
                        file_identity(row['evidence']) == row['report_sha256'])
            except (OSError, TypeError, KeyError):
                return False
        value, receipt = cache.run(inputs, calibrate_inputs, valid_inputs)
        atomic_json(output / 'input-calibration-receipt.json', {'result': value, 'cache': receipt})
    if getattr(args, 'check_only', False):
        check(plan)
        atomic_json(output / 'check-only.json', {'passed': True, 'plan_sha256': identity(plan), 'finished': now(),
            'scope': 'Frozen inputs and scripted calibration only; no model inference or capability result.'})
        print('Scripted calibration passed. No model inference started.', flush=True)
        return
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
                if plan.get('parent'):
                    parent = plan['parent']
                    added, task = growth_task(parent['tool'], plan)
                    if plan.get('reuse_task'):
                        task = plan['reuse_task']
                    order = list(plan['variants'])
                    if repeat % 2 == 0:
                        order.reverse()
                    for treatment in order:
                        suffix = ('reuse' if plan.get('reuse_task') else 'growth') + '_%02d_%s_%s' % (repeat, parent['tool'], treatment)
                        if gate:
                            cell(suffix, lambda folder, treatment=treatment: trial(folder, task, parent['source'], config,
                                {**plan, 'treatment': treatment}, None if plan.get('reuse_task') else added,
                                None if plan.get('reuse_task') else parent['tool']))
                        else:
                            queue.skip(profile['id'] + '_' + suffix, 'Basic gate did not qualify; supplied-parent growth untested')
                    continue
                features = plan['upgrade_tasks']
                features = features[(repeat - 1) % len(features):] + features[:(repeat - 1) % len(features)]
                for index, feature in enumerate(features):
                    order = list(plan.get('variants', {'baseline': plan['source']}))
                    if plan.get('experiment') and (repeat + index) % 2 == 0:
                        order.reverse()
                    for treatment in order:
                        suffix = '_' + treatment if plan.get('experiment') else ''
                        first_id = 'first_%02d_%s%s' % (repeat, feature, suffix)
                        growth_id = 'growth_%02d_%s%s' % (repeat, feature, suffix)
                        if not gate:
                            for name in (first_id, growth_id):
                                queue.skip(profile['id'] + '_' + name, 'Protocol/basic gate did not qualify; not an upgrade failure')
                            continue
                        input_source = plan.get('variants', {}).get(treatment, plan['source'])
                        inputs = {**plan, 'treatment': treatment}
                        task = {'name': feature, 'task': 'Add exactly one new public tool. ' + plan['contracts'][feature] + plan['recipe'], 'checks': []}
                        first = cell(first_id, lambda folder: trial(folder, task, input_source, config, inputs, feature))
                        if first.get('review', {}).get('accepted'):
                            saved = queue.latest(profile['id'] + '_' + first_id)
                            source = json.loads((Path(saved['folder']) / 'review/candidate-source.json').read_text())
                            added, task = growth_task(feature, plan)
                            cell(growth_id, lambda folder: trial(folder, task, source, config, inputs, added, feature))
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
    p.add_argument('--experiment', choices=TREATMENTS, help='Pair the frozen default with one opt-in treatment')
    p.add_argument('--mask-keep', type=int, default=8)
    p.add_argument('--mask-threshold', type=int, default=512)
    p.add_argument('--parent-source', help='Inert exported candidate-source.json for a controlled phase comparison')
    p.add_argument('--parent-tool', choices=tuple(study.CONTRACTS))
    p.add_argument('--reuse-task', help='JSON task with required_tools and exact artifact checks; reuse only, no upgrade credit')
    p.add_argument('--task-pack', help='Optional independently checked offline tasks replacing the basic-task pack')
    p = commands.add_parser('run')
    p.add_argument('--input', required=True)
    p.add_argument('--check-only', action='store_true', help='Verify frozen inputs and scripted graders without contacting inference')
    p.add_argument('--retry', action='append', default=[], metavar='CELL_ID', help='Explicit new attempt after interruption/error; preserves the original')
    args = parser.parse_args()
    {'prepare': prepare, 'run': run}[args.command](args)
