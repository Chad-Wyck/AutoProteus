"""Resumable local model screens and full first/second-pass qualification.

    python evaluations/model_study.py prepare --profiles profiles.json --output .data/study --mode full --repeats 1
    python evaluations/model_study.py run --input .data/study

Connect already prepared local inference services. This runner downloads nothing,
changes no app preferences and executes candidates only in disposable VMs.
"""
import argparse
import base64
import copy
from contextlib import nullcontext
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
from controller.submissions import repair_ticket, ticket_message
from observations import CallRecorder, call_metrics, latency_metrics, navigation_metrics, read_events
from run_budget import BudgetModelClient, GeneratedTokenBudget, DEFAULT_OUTPUT_TOKENS, DEFAULT_TASK_SECONDS
from study_support import ResultCache, StudyQueue, Timings, file_identity, identity, task_observations
from workflow_variants import TREATMENTS, variant, DEVELOPMENT_FOCUS, USE_FOCUS
import generalization as study
import activation_use
from repeatability import SEED_MODES, repeat_config, sampling_record
from owned_runtime import RuntimeOwner


from model_plan import private, trusted_files, environment, prepare, check, workflow_requirements, growth_feature, calibrate


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
    client = BudgetModelClient({**config, 'response_tokens': response}, token_budget=GeneratedTokenBudget(response * 2), observer=recorder,
                              native_instructions=plan.get('native_instructions'))
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
    return {'passed': all(row['passed'] for row in results), 'requests': results, 'sampling': sampling_record(config),
            'seconds': round(time.monotonic() - started, 3), **metrics(folder, recorder, [client]),
            'scope': 'Inference-only speed/protocol screen. No model-chosen tool executes. '
                     'First measured call and longer-prompt call; cache warmth is not controlled.'}


def trial(folder, task, source, config, plan, feature=None, earlier=None):
    task = copy.deepcopy(task)
    original_task = copy.deepcopy(task)
    staged = plan.get('treatment') == 'staged-inputs'
    final_input = 'inventory.json'
    if staged:
        if not feature or earlier not in ('sha256_file', 'format_json') or final_input not in task.get('fixtures', {}):
            raise ValueError('Staged inputs require a supplied JSON/hash parent and a final inventory fixture')
        del task['fixtures'][final_input]
        task['fixtures']['development/example.json'] = '{"example":1,"note":"é"}'
        task['task'] += ('\nThe controller is withholding inventory.json until independent verification and activation. '
            'It is not available during development; do not create it or audit.json yet. '
            'Use development/example.json and other disposable examples to try the edited tool, '
            'inspect exact file contents, repair tests, then request activation. Final use remains required.')
    reuse_only = not feature and bool(plan.get('reuse_task')) and task['name'] == plan['reuse_task']['name']
    focused = plan.get('treatment') == 'phases' and earlier is not None
    final_contract = plan.get('treatment') == 'final-contract'
    if final_contract and (not earlier or not feature or not task.get('final_task')):
        raise ValueError('Final-contract trials require a growth task with an explicit public final task')
    if focused:
        task['task'] += DEVELOPMENT_FOCUS
    elif plan.get('treatment') == 'phases' and reuse_only:
        task['task'] += USE_FOCUS
    support = None
    if feature and plan.get('treatment') in ('edit-context', 'verified-lesson'):
        from edit_context import task_support
        support = task_support(source, task['task'], plan['treatment'])
        task.setdefault('fixtures', {}).update(support.pop('fixtures'))
        task['task'] += '\nTASK SUPPORT (source observations, not additional requirements):\n' + support['text']
        atomic_json(folder / 'task-support.json', support)
    store = Store(folder / 'sessions')
    recorder = CallRecorder(folder / 'provider-calls.jsonl')
    budget = GeneratedTokenBudget(plan['generated_tokens'] if feature or reuse_only else plan['ordinary_generated_tokens'])
    clients = []
    def factory(values):
        client = BudgetModelClient(values, token_budget=budget, observer=recorder,
                                   native_instructions=plan.get('native_instructions'))
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
           'requested_sampling_seed':config.get('sampling_seed'),
           'sampling': sampling_record(config),
           'input_protocol': 'withheld_final_input' if staged else 'strict_preserve_visible_input',
           'treatment': plan.get('treatment', 'baseline'), 'stages': {'activated': False},
           'experimental_instructions': ['CURRENT FINAL TASK\n' + task['final_task']] if final_contract else
                                       [DEVELOPMENT_FOCUS, USE_FOCUS] if focused else
                                       [USE_FOCUS] if reuse_only and plan.get('treatment') == 'phases' else []}
    atomic_json(folder / 'original-task.json', original_task)
    atomic_json(folder / 'task.json', task)
    try:
        with timings.measure('development_or_basic'):
            row['run'] = run_task(agent, store, config, task, freeze_source(store, source, 'Frozen input'),
                                  max(0, deadline - time.monotonic()), deadline=deadline)
        session = store.get(row['run']['session'])
        if support:
            events = study.journal(store, session)
            lesson_read = any(event.get('type') == 'action_result' and event.get('data', {}).get('ok') and
                event['data'].get('action', {}).get('tool') in ('read_file', 'read_section') and
                event['data']['action'].get('arguments', {}).get('path') == 'experience/verified-submission.md' for event in events)
            row['task_support'] = {'kind': support['kind'], 'provided': True,
                'read_observed': bool(lesson_read) if support['kind'] == 'verified-lesson' else None,
                'exposure': 'file with read hint' if support['kind'] == 'verified-lesson' else 'direct task context',
                'followed': 'unmeasured', 'caused_success': 'unmeasured',
                'scope': 'Independent attempt outcomes are reported separately; exposure or a read is not evidence of benefit.'}
            if support['kind'] == 'edit-context':
                from edit_context import stale_paths
                row['task_support']['stale_after_development'] = stale_paths(support['packet'], candidate_source(store, session))
        if feature and plan.get('treatment') == 'submission-feedback':
            # Public feedback precedes every hidden check. No held-out failures
            # or answers are disclosed. Repairs use the original running seed.
            row['submission_feedback'] = []
            row['initial_submission'] = copy.deepcopy(row['run'])
            row['initial_submission_grading'] = 'Public policy only; no hidden grading before repair.'
            for attempt in range(2):
                ticket = repair_ticket(source, candidate_source(store, session), study.journal(store, session))
                entry = {'ticket': ticket, 'attempt': attempt + 1, 'continued': False}
                row['submission_feedback'].append(entry)
                remaining_actions = max(0, config['max_steps'] - session['steps'])
                if (ticket['ready_for_independent_checks'] or session['status'] not in ('completed', 'waiting') or
                        row['run']['timed_out'] or time.monotonic() >= deadline or
                        budget.summary()['exhausted'] or remaining_actions <= 0):
                    break
                settings.values = {**config, 'max_steps': remaining_actions}
                with timings.measure('public_submission_repair'):
                    agent.start(session, ticket_message(ticket), deadline=deadline)
                    row['run'] = study.wait(agent, session, max(0, deadline - time.monotonic()))
                entry['continued'] = True
                entry['run'] = copy.deepcopy(row['run'])
                entry['cumulative_actions'] = session['steps']
            row['final_submission_ticket'] = repair_ticket(source, candidate_source(store, session), study.journal(store, session))
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
            if task.get('first_use') and not earlier:
                row['first_package_accepted'] = bool(study.verified(row['review']) and row['stages']['submitted']
                    and time.monotonic()<deadline)
                if row['first_package_accepted']:
                    with timings.measure('first_activation_and_use'):
                        row['first_use'] = activation_use.activate(agent, store, session, settings, config,
                            task['first_use'], budget, deadline, study.wait)
                else:
                    row['first_use'] = {'attempted':False,'passed':False,'reason':'first_package_not_accepted'}
                row['stages'].update(activated=row['first_use'].get('activated',False),
                    independently_verified=study.verified(row['review']), first_use_passed=row['first_use']['passed'])
            if row.get('submission_feedback') is not None:
                repaired = sum(entry['continued'] for entry in row['submission_feedback'])
                row['public_submission_repairs'] = repaired
                row['accepted_without_public_repair'] = bool(row['review'].get('accepted') and not repaired)
                row['accepted_after_public_repair'] = bool(row['review'].get('accepted') and repaired)
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
                files = Artifacts(store, session)
                if staged:
                    row['stage_order_preserved'] = not any(name in session.get('artifacts', {}) for name in (artifact, 'audit.json'))
                    row['withheld_input'] = {'path': artifact, 'delivered': False,
                        'sha256': hashlib.sha256(original_task['fixtures'][artifact].encode()).hexdigest(),
                        'scope': 'Final bytes withheld; no credit for preserving a visible original input.'}
                else:
                    try:
                        row['stage_order_preserved'] = files.read(artifact) == task['fixtures'][artifact].encode()
                    except (OSError, ValueError):
                        row['stage_order_preserved'] = False
                retained = row['retained']['passed'] and row['retained_public']['passed']
                remaining = deadline - time.monotonic()
                remaining_actions = max(0, config['max_steps'] - session['steps'])
                if (row['verified_extension'] and retained and row['stage_order_preserved'] and remaining > 0 and
                        session['status'] in ('completed', 'waiting') and not row['run']['timed_out'] and not budget.summary()['exhausted'] and
                        remaining_actions > 0):
                    with timings.measure('activation_and_final_use'):
                        # Activation never grants a new task allowance. A later
                        # second-extension task receives its own fresh allowance.
                        settings.values = {**config, 'max_steps': remaining_actions}
                        if final_contract:
                            session['candidate_from'] = session['id']
                            agent.start(session, 'CURRENT FINAL TASK\n' + task['final_task'], candidate=session,
                                        handoff='concise', deadline=deadline)
                        elif focused:
                            session['candidate_from'] = session['id']
                            agent.start(session, USE_FOCUS, candidate=session, handoff='concise', deadline=deadline)
                        elif staged:
                            files.put(artifact, base64.b64encode(original_task['fixtures'][artifact].encode()).decode())
                            files.checkpoint([*session.get('artifacts', {}), artifact])
                            row['withheld_input']['delivered'] = True
                            session['candidate_from'] = session['id']
                            agent.start(session, 'The final inventory.json is now available. Use the activated tools to complete '
                                'the original task and verify inventory.json and audit.json before finishing.',
                                candidate=session, handoff='concise', deadline=deadline)
                        else:
                            agent.restart_seed(session, handoff='concise', deadline=deadline)
                        row['stages']['activated'] = True
                        # Synchronous activation/setup consumes wall time too.
                        row['final'] = study.wait(agent, session, max(0, deadline - time.monotonic()))
                    row['final_source_unchanged'] = source_identity(candidate_source(store, session)) == source_identity(edited)
                    expected = original_task['fixtures'][artifact] if earlier == 'csv_preview' else json.dumps(
                        json.loads(original_task['fixtures'][artifact]), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
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


def growth_task(parent, plan):
    added = growth_feature(parent)
    sample, arguments, _, _ = study.sample_case(parent)
    fixtures = {'sample.txt': sample, 'inventory.json': '{"z":[2,false],"a":"café 猫"}',
                'experience/invoke_tool.py': plan['invoke_tool']}
    final = ('Use csv_preview and sha256_file on sample.txt. Write audit.json with path="sample.txt", bytes, sha256, '
             'rows (default preview) and truncated matching the actual results.' if parent == 'csv_preview' else
             'Use format_json to format inventory.json and sha256_file to hash its final bytes. '
             'Write audit.json with path="inventory.json", bytes and sha256 matching the formatted file.')
    final += ' Inspect the input and receipt, then finish completed. Do not edit the seed after activation.'
    return added, {'name': 'second-extension-audit', 'checks': [], 'fixtures': fixtures, 'final_task': final, 'task':
        'Your active seed already includes the independently verified ' + parent + ' tool. Use it on sample.txt with arguments ' +
        json.dumps(arguments) + '. Then add exactly one new tool: ' + plan['contracts'][added] +
        plan['recipe'].replace('Finish completed only after implementing and verifying the feature.', '') +
        '\nPreserve every existing capability and test. Keep inventory.json unchanged during development; '
        'use disposable examples. You can invoke an edited tool before its full suite passes with '
        'python3 experience/invoke_tool.py TOOL_NAME \'{"path":"sample.txt"}\'. '
        'Check actual file contents as well as return values. After development checks pass, finish needs_input requesting activation. '
        'After independent verification and activation, ' + final}


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
        ordinary = [task_observations(row['result'].get('run', {})) for row in rows if row['cell'][len(prefix):].startswith('basic_')]
        profiles[profile['id']] = {'benchmarks': speed,
            'sampling': sampling_record(profile.get('config', {})),
            'ordinary': {'attempts': sum(row['cell'][len(prefix):].startswith('basic_') for row in all_rows),
                'artifact_checks': sum(type(row['artifacts_correct']) is bool for row in ordinary),
                'artifacts_correct': sum(row['artifacts_correct'] is True for row in ordinary),
                'completion_observations': sum(type(row['explicit_completion']) is bool for row in ordinary),
                'explicit_completion': sum(row['explicit_completion'] is True for row in ordinary),
                'passed': sum(row['task_passed'] is True for row in ordinary),
                'not_run': sum(key.startswith(prefix+'basic_') and attempts[-1]['state']=='not_run'
                               for key, attempts in queue.data['cells'].items())},
            'scheduled_first_tasks': 0 if plan.get('parent') else len(plan['upgrade_tasks']) * plan['repeats'] * len(plan.get('variants', {'baseline': []})),
            'first_attempts': sum(row['cell'][len(prefix):].startswith('first_') for row in all_rows), 'first_finished': len(first),
            'first_verified': sum(study.verified(row.get('review', {})) for row in first),
            'first_accepted': sum(bool(row.get('first_package_accepted')) if plan.get('protocol')==activation_use.PROTOCOL
                else bool(row.get('review',{}).get('accepted')) for row in first),
            'first_packages_ready': sum(bool(row.get('first_package_accepted')) for row in first),
            'first_use_attempts': sum(bool(row.get('first_use',{}).get('attempted')) for row in first),
            'first_use_passed': sum(bool(row.get('first_use',{}).get('passed')) for row in first),
            'second_attempts': sum(row['cell'][len(prefix):].startswith('growth_') for row in all_rows), 'second_finished': len(growth),
            'second_verified': sum(bool(row.get('verified_extension')) for row in growth),
            'second_use_passed': sum(bool(row.get('scores', {}).get('functional_growth')) for row in growth),
            'diagnostic_second_attempts': sum(bool(row.get('chain',{}).get('diagnostic_only')) for row in growth),
            'complete_growth': (None if plan.get('protocol')==activation_use.PROTOCOL and (plan.get('parent') or not plan.get('growth_enabled',True)) else
                sum(bool(row.get('chain',{}).get('complete_chain_passed')) if plan.get('protocol')==activation_use.PROTOCOL
                    else bool(row.get('scores',{}).get('functional_growth')) for row in growth)),
            'reuse_attempts': sum(row['cell'][len(prefix):].startswith('reuse_') for row in all_rows),
            'reuse_finished': len(reuse), 'reuse_passed': sum(bool(row.get('reuse', {}).get('passed')) for row in reuse)}
    report = {'mode': plan['mode'], 'protocol':plan.get('protocol','legacy'), 'scope': plan['scope'], 'queue': queue.summary(), 'profiles': profiles}
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
            if plan.get('protocol')==activation_use.PROTOCOL:
                success = bool(row.get('reuse',{}).get('passed') if '_reuse_' in cell else
                    row.get('chain',{}).get('complete_chain_passed') if '_growth_' in cell and not plan.get('parent') else
                    row.get('scores',{}).get('functional_growth') if '_growth_' in cell else row.get('first_use',{}).get('passed'))
            else:
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
            'input_protocols': ({'baseline': 'strict_preserve_visible_input', 'staged-inputs': 'withheld_final_input'}
                if plan.get('experiment') == 'staged-inputs' else {'all': 'strict_preserve_visible_input'}),
            'interpretation': ('Withheld-input success does not establish compliance with preserving visible final inputs. '
                'Report each protocol separately; this comparison includes input delivery instructions.'
                if plan.get('experiment') == 'staged-inputs' else 'Shared input protocol; report independent successes before costs.'),
            'expense_scope': 'All attempts retained with full costs in queue/trials, including failed and interrupted work; matched pairs use original attempts only.',
            'supplied_parent': bool(plan.get('parent')),
            'kind': 'unchanged_capability_reuse' if plan.get('reuse_task') else 'supplied_parent_growth' if plan.get('parent') else 'first_and_second_upgrades'}



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
    owners = {}
    for profile in plan['profiles']:
        if profile.get('runtime') is not None:
            owners[profile['id']] = RuntimeOwner(profile)
            continue
        for path, digest in profile.get('assets', {}).items():
            if file_identity(path) != digest:
                raise ValueError('Profile asset changed: ' + path)
    queue = StudyQueue(output, identity(plan))
    for cell_id in args.retry:
        previous = queue.latest(cell_id)
        if not previous or previous['state'] not in ('interrupted', 'error'):
            raise ValueError('--retry requires an existing interrupted/error cell: ' + cell_id)
    cache = ResultCache(ROOT / '.data/study-cache/calibration')
    calibrate(plan, output, cache, study, run_regressions)
    if getattr(args, 'check_only', False):
        check(plan)
        atomic_json(output / 'check-only.json', {'passed': True, 'plan_sha256': identity(plan), 'finished': now(),
            'scope': 'Frozen inputs and scripted calibration only; no model inference or capability result.'})
        print('Scripted calibration passed. No model inference started.', flush=True)
        return
    if plan['mode']=='outcomes':
        from outcome_study import run_plan
        return run_plan(plan,output,queue,args,owners=owners)
    try:
        for profile in plan['profiles']:
            config = profile['config']
            owner = owners.get(profile['id'])
            public_identity = None if owner else model_identity(config)
            marker = output / (profile['id'] + '-identity.json')
            if not owner and marker.exists() and json.loads(marker.read_text()) != public_identity:
                raise ValueError('Inference service identity changed; prepare a new plan')
            if not owner: atomic_json(marker, public_identity)
            def cell(suffix, execute, runtime_config=None):
                check(plan)
                if not owner and model_identity(config) != public_identity:
                    raise ValueError('Inference service identity changed during study')
                name = profile['id'] + '_' + suffix
                previous = queue.latest(name)
                if not previous or (previous['state'] in ('interrupted', 'error') and name in args.retry):
                    print('START', name, flush=True)
                def checked_execute(folder):
                    context = owner.attempt(folder, runtime_config or config,
                        plan.get('ordinary_deadline', 240) if suffix.startswith('basic_') else
                        plan.get('deadline', 1800)) if owner else nullcontext(None)
                    with context as runtime:
                        expected = model_identity(config) if owner else public_identity
                        if owner:
                            if marker.exists() and json.loads(marker.read_text()) != expected:
                                raise ValueError('Owned inference service identity changed; prepare a new plan')
                            atomic_json(marker, expected)
                        result = execute(folder)
                        # Also check the final cell: partial mixed-source results
                        # cannot earn credit even after the trial wrote a result.
                        check(plan)
                        if model_identity(config) != expected:
                            raise ValueError('Inference service identity changed during the attempt')
                    if runtime:
                        result['runtime_observation'] = runtime.record
                        atomic_json(folder/'result.json', result)
                    return result
                row = queue.run(name, checked_execute, retry=name in args.retry)
                atomic_json(output / 'summary.json', summarize(queue, plan))
                print('CELL', name, row['state'], flush=True)
                return row.get('result', {})
            for repeat in range(1, (plan['repeats'] if plan['mode'] == 'benchmark' else 1) + 1):
                selected = repeat_config(plan, config, repeat)
                speed = cell('benchmark_%02d' % repeat, lambda folder: benchmark(folder, selected, plan), selected)
            if plan['mode'] == 'benchmark':
                continue
            if plan['mode'] == 'basic':
                for repeat in range(1, plan['repeats'] + 1):
                    selected = repeat_config(plan, config, repeat)
                    for name in plan['ordinary_tasks']:
                        suffix = 'basic_%02d_%s' % (repeat, name)
                        task = next(item for item in plan['tasks'] if item['name'] == name)
                        if speed.get('passed'):
                            cell(suffix, lambda folder, task=task: trial(folder, task, plan['source'], selected, plan), selected)
                        else:
                            queue.skip(profile['id']+'_'+suffix, 'Inference screen did not qualify; basic task untested')
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
                seeded_config=repeat_config(plan,config,repeat)
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
                            cell(suffix, lambda folder, treatment=treatment: trial(folder, task, parent['source'], seeded_config,
                                {**plan, 'treatment': treatment}, None if plan.get('reuse_task') else added,
                                None if plan.get('reuse_task') else parent['tool']), seeded_config)
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
                        if plan.get('protocol') == activation_use.PROTOCOL:
                            spec = plan['first_use_contracts'][f'{repeat}-{feature}']
                            task['first_use'] = spec
                            task['task'] = task['task'].replace('Finish completed only after implementing and verifying the feature.',
                                'After implementing and verifying the feature, finish needs_input requesting independent activation.')
                            task['task'] += ('\nAfter independent checking and activation the controller will supply fresh task inputs. '
                                'Do not create those input or receipt paths during development. Complete this first-use task: '+spec['instruction'])
                        first = cell(first_id, lambda folder: trial(folder, task, input_source, seeded_config, inputs, feature), seeded_config)
                        if not plan.get('growth_enabled',True):
                            queue.skip(profile['id']+'_'+growth_id, 'Second extension not requested in this first-only comparison')
                        elif activation_use.eligible_parent(first, plan.get('protocol')):
                            saved = queue.latest(profile['id'] + '_' + first_id)
                            source = json.loads((Path(saved['folder']) / 'review/candidate-source.json').read_text())
                            added, task = growth_task(feature, plan)
                            def second_trial(folder):
                                row = trial(folder, task, source, seeded_config, inputs, added, feature)
                                row['chain'] = activation_use.chain_result(first, row, plan.get('protocol'))
                                atomic_json(folder/'result.json', row)
                                return row
                            cell(growth_id, second_trial, seeded_config)
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
    p.add_argument('--mode', choices=('benchmark', 'basic', 'screen', 'full', 'outcomes'), default='screen')
    p.add_argument('--repeats', type=int)
    p.add_argument('--first-only', action='store_true', help='Measure first extension and activation/use without requesting a second extension')
    p.add_argument('--timeout', type=int, default=DEFAULT_TASK_SECONDS)
    p.add_argument('--output-token-budget', type=int, default=DEFAULT_OUTPUT_TOKENS)
    p.add_argument('--experiment', choices=TREATMENTS, help='Pair the frozen default with one opt-in treatment')
    p.add_argument('--mask-keep', type=int, default=8)
    p.add_argument('--mask-threshold', type=int, default=512)
    p.add_argument('--parent-source', help='Inert exported candidate-source.json for a controlled phase comparison')
    p.add_argument('--parent-tool', choices=tuple(study.CONTRACTS))
    p.add_argument('--reuse-task', help='JSON task with required_tools and exact artifact checks; reuse only, no upgrade credit')
    p.add_argument('--task-pack', help='Optional independently checked offline tasks replacing the basic-task pack')
    p.add_argument('--source-pack', help='Inert comparison source JSON; must preserve the common starter tests')
    p.add_argument('--native-instructions-file', help='Host-owned frozen native-format text for controlled comparisons')
    p.add_argument('--case-pack', help='Portable fixed upgrade cases and predeclared seed schedule')
    p.add_argument('--sampling-seed-mode', choices=SEED_MODES, default='per-request',
                   help='Per-call seed, or omit request seeds and declare externally managed server initialization (not verified by runner)')
    p = commands.add_parser('run')
    p.add_argument('--input', required=True)
    p.add_argument('--check-only', action='store_true', help='Verify frozen inputs and scripted graders without contacting inference')
    p.add_argument('--retry', action='append', default=[], metavar='CELL_ID', help='Explicit new attempt after interruption/error; preserves the original')
    args = parser.parse_args()
    {'prepare': prepare, 'run': run}[args.command](args)
