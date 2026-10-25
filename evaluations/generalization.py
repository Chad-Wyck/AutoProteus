"""Controlled frozen-seed study. Candidate execution is confined to disposable VMs."""
import argparse
import base64
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evaluations'))
from run_budget import TokenBudgetMixin, GeneratedTokenBudget, DEFAULT_OUTPUT_TOKENS, DEFAULT_TASK_SECONDS
from controller.config import DEFAULTS
from controller.evaluation import (candidate_source, freeze_source, growth_scores, run_task,
                                   source_identity, tool_use)
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.providers import request_json
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json, now
from controller.compatibility import model_identity

spec = importlib.util.spec_from_file_location('benchmark', ROOT / 'evaluations/local-model-benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
class BudgetDiagnosticClient(TokenBudgetMixin, benchmark.DiagnosticClient):
    pass
PROBE = (ROOT / 'evaluations/generalization-probe.py').read_text(encoding='utf-8')

CONTRACTS = {
    'sha256_file': ('sha256_file(path) reads ordinary binary files up to 1048576 bytes without changing them. '
                   'Return path relative to the workspace, bytes, and sha256 as lowercase hexadecimal. '
                   'Reject larger files, missing files, directories and escaping paths.'),
    'csv_preview': ('csv_preview(path, limit=5) reads UTF-8 CSV of at most 100000 Unicode characters using Python csv.reader. '
                    'Return path relative to the workspace, rows (a list of lists of strings, at most limit records), '
                    'and truncated (whether additional records exist). Do not treat the first row as a special header. '
                    'Preserve quoted commas, Unicode and CRLF inside quoted fields. Empty input has no rows. '
                    'limit must be an integer from 1 to 20, excluding bool. Reject invalid UTF-8, oversized input, '
                    'missing files, directories and escaping paths. Preserve every input byte.'),
    'format_json': ('format_json(path) reads UTF-8 JSON of at most 100000 Unicode characters using Python json.loads. '
                    'Replace it with json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) followed by one LF newline. '
                    'Return path relative to the workspace and bytes of the final UTF-8 file. '
                    'The formatted output must also fit 100000 Unicode characters. Reject invalid JSON, invalid UTF-8, '
                    'oversized input or output, missing files, directories and escaping paths before changing any bytes.')}
RECIPE = ('\nRead harness/README.md and relevant source. Implement and register exactly the requested capability. '
          'Change runtime code only in harness/autoproteus/tools.py and harness/autoproteus/providers.py. '
          'Preserve the loop and every existing test file exactly; add a separate focused tests/test_*.py file. '
          'Use the shared helpers where appropriate. Generate large test data with short expressions. '
          'Run python3 harness/seed.py check and exercise the edited tool on disposable inputs. '
          'Repair actual failures. Finish completed only after implementing and verifying the feature. '
          'There is no network or package installation. No separate report is required.')

REFERENCE = '''        if tool == "sha256_file":
            import hashlib
            path = self.path(args["path"])
            with path.open("rb") as stream: raw = stream.read(1048577)
            if len(raw) > 1048576: raise ValueError("Too large")
            return {"path": str(path.relative_to(self.root)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if tool == "csv_preview":
            import csv, io
            limit = args.get("limit", 5)
            if type(limit) is not int or not 1 <= limit <= 20: raise ValueError("Invalid limit")
            path = self.path(args["path"])
            rows = list(csv.reader(io.StringIO(self.read_text(path), newline="")))
            return {"path": str(path.relative_to(self.root)), "rows": rows[:limit], "truncated": len(rows) > limit}
        if tool == "format_json":
            import json
            path = self.path(args["path"])
            text = json.dumps(json.loads(self.read_text(path)), ensure_ascii=False, sort_keys=True, indent=2) + "\\n"
            return self.write_text(path, text)
'''


def profile_configs():
    # This compares inference profiles, with terminal explicitly enabled in both.
    common = {**DEFAULTS, 'configured': True, 'terminal': True, 'base_url': 'http://127.0.0.1:11435', 'action_limit':True}
    return {'default': dict(common), 'qwen9b': {**common,
            'model': 'hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M', 'context_tokens': 65536,
            'response_tokens': 4096, 'temperature': 0.6, 'thinking': False}}


def sample_case(name):
    if name == 'sha256_file':
        text = 'café\r\n猫\x00'; result = {'path': 'sample.txt', 'bytes': len(text.encode()),
                                            'sha256': hashlib.sha256(text.encode()).hexdigest()}
        return text, {'path': 'sample.txt'}, result, text
    if name == 'csv_preview':
        text = 'id,value\r\n1,"café, 猫"\r\n2,"two\r\nlines"\r\n'
        return text, {'path': 'sample.txt', 'limit': 2}, {
            'path': 'sample.txt', 'rows': list(csv.reader(io.StringIO(text, newline='')))[:2], 'truncated': True}, text
    text = '{"z":1,"é":[2,true]}'
    final = json.dumps(json.loads(text), sort_keys=True, indent=2, ensure_ascii=False) + '\n'
    return text, {'path': 'sample.txt'}, {'path': 'sample.txt', 'bytes': len(final.encode())}, final


def verify_feature(store, source, name, deadline=None):
    settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo', 'terminal': True}, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, lambda _: benchmark.ScriptedClient([
        {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 heldout_probe.py ' + name}}},
        {'status': 'completed'}]))
    try:
        result = run_task(agent, store, settings.values, {'name': 'independent-' + name, 'task': 'Run the independent checks.',
            'fixtures': {'heldout_probe.py': PROBE}, 'checks': [{'path': 'heldout-result.json'}]}, source, 120,
            **({'deadline': deadline} if deadline is not None else {}))
        probe = benchmark.read_artifact(store, store.get(result['session']), 'heldout-result.json')
        return {'passed': bool(result['passed'] and probe.get('passed')), 'probe': probe, 'run': result}
    finally:
        agent.close()


def verify_public(store, source, name, deadline=None):
    text, arguments, expected, final = sample_case(name)
    settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo'}, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, lambda _: benchmark.ScriptedClient([
        {'action': {'tool': name, 'arguments': arguments}}, {'status': 'completed'}]))
    try:
        result = run_task(agent, store, settings.values, {'name': 'public-' + name, 'task': 'Invoke the new tool.',
            'fixtures': {'sample.txt': text}, 'checks': [{'path': 'sample.txt', 'equals': final}]}, source, 90,
            **({'deadline': deadline} if deadline is not None else {}))
        events = journal(store, store.get(result['session']))
        value = next((e['data']['result'] for e in events if e['type'] == 'action_result' and
                      e['data']['action']['tool'] == name and e['data']['ok']), {})
        return {'passed': result['passed'] and all(value.get(key) == item for key, item in expected.items()), 'run': result}
    finally:
        agent.close()


def journal(store, session):
    return [json.loads(line) for line in (store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8').splitlines()]


def latest_run(events):
    boundary = max((index for index, event in enumerate(events) if event['type'] == 'run_started'), default=0)
    return events[boundary:]


def assess(store, source, result, name, output):
    output.mkdir(parents=True)
    return benchmark.assess(store, source, result, name, output, verify_feature, verify_public)


def verified(review):
    return bool(review.get('runtime_changed') and review.get('new_test_files') and
                review.get('protected_unchanged') and review.get('allowed_files_only') and
                all(review.get(key, {}).get('passed') for key in ('regressions', 'feature', 'public')))


def self_check(output, source):
    store = Store(output / 'calibration')
    baseline = freeze_source(store, source, 'Frozen negative control')
    positive = copy.deepcopy(source)
    specs = {name: ('Calibration file tool.', {'path': {'type': 'string'},
                  **({'limit': {'type': 'integer'}} if name == 'csv_preview' else {})}, ['path'])
             for name in CONTRACTS}
    for item in positive:
        text = base64.b64decode(item['data']).decode('utf-8')
        if item['path'] == 'autoproteus/tools.py':
            text = text.replace('        if tool == "list_files":', REFERENCE + '        if tool == "list_files":')
        if item['path'] == 'autoproteus/providers.py':
            text = text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr(specs) + ' | {')
        item['data'] = base64.b64encode(text.encode()).decode()
    reference = freeze_source(store, positive, 'Human-written reference, never offered to the model')
    report = {}
    for name in CONTRACTS:
        negative, control = verify_feature(store, baseline, name), verify_feature(store, reference, name)
        public = verify_public(store, reference, name)
        report[name] = {'negative': negative, 'positive': control, 'public': public}
        atomic_json(output / 'calibration.json', report)
        if negative['passed'] or not control['passed'] or not public['passed']:
            raise RuntimeError('Independent grader calibration failed: ' + name)
    off_by_one = copy.deepcopy(positive)
    for item in off_by_one:
        if item['path'] == 'autoproteus/tools.py':
            text = base64.b64decode(item['data']).decode()
            faulty = REFERENCE.replace('len(rows) > limit}', 'len(rows) > limit + 1}')
            if faulty == REFERENCE:
                raise RuntimeError('CSV negative control was not constructed')
            item['data'] = base64.b64encode(text.replace(REFERENCE, faulty).encode()).decode()
    rejected = verify_feature(store, freeze_source(store, off_by_one, 'Faulty CSV truncation control'), 'csv_preview')
    report['csv_one_extra_negative'] = rejected
    atomic_json(output / 'calibration.json', report)
    checks = rejected.get('probe', {}).get('checks', {})
    expected = {'one_extra_' + str(limit) for limit in (1, 5, 20)}
    if (rejected['passed'] or not rejected.get('probe', {}).get('suite', {}).get('exit_code') == 0 or
            {key for key, value in checks.items() if value is not True} != expected):
        raise RuntimeError('The CSV grader did not isolate the one-extra-row defect')
    escaping = json.loads(json.dumps(positive))
    for item in escaping:
        if item['path'] == 'autoproteus/tools.py':
            text = base64.b64decode(item['data']).decode()
            # Deliberately bypass only the reference feature's path helpers;
            # the original tools and protected regressions are untouched.
            faulty = REFERENCE.replace('path = self.path(args["path"])', 'path = self.root / args["path"]')
            faulty = faulty.replace('self.read_text(path)', 'path.read_bytes().decode("utf-8")')
            faulty = faulty.replace('return self.write_text(path, text)',
                'path.write_bytes(text.encode("utf-8"))\n'
                '            return {"path": str(path.relative_to(self.root)), "bytes": len(text.encode("utf-8"))}')
            text = text.replace(REFERENCE, faulty)
            item['data'] = base64.b64encode(text.encode()).decode()
    faulty_source = freeze_source(store, escaping, 'Faulty path-bypass control')
    rejected = verify_feature(store, faulty_source, 'format_json')
    report['format_json_path_bypass_negative'] = rejected
    atomic_json(output / 'calibration.json', report)
    checks = rejected.get('probe', {}).get('checks', {})
    if rejected['passed'] or any(checks.get(key) is not False for key in ('reject_path_../outside-heldout.txt', 'reject_path_escape')):
        raise RuntimeError('The formatting grader did not reject both path-bypass controls')
    from grader_faults import controls
    report['fault_matrix'] = {}
    for name, feature, expected_cases, mutated in controls(positive, REFERENCE):
        rejected = verify_feature(store, freeze_source(store, mutated, 'Fault control: ' + name), feature)
        cases = rejected.get('probe', {}).get('checks', {})
        # Rejecting a broken import or test suite is not evidence that a
        # specific contract case detected the intended semantic defect.
        detected = (not rejected['passed'] and rejected.get('probe', {}).get('suite', {}).get('exit_code') == 0
                    and all(cases.get(key) is False for key in expected_cases))
        report['fault_matrix'][name] = {'feature': feature, 'expected_rejections': list(expected_cases),
                                      'detected': detected, 'result': rejected}
        atomic_json(output / 'calibration.json', report)
        if not detected:
            raise RuntimeError('Grader did not detect the intended defect: ' + name)


def clone_checkpoint(store, original, label):
    session = store.create(original['task'], original['provider'], original['model'])
    for key in ('messages', 'feed', 'steps', 'runs', 'todo', 'seed_version', 'seed_sha256'):
        if key in original:
            session[key] = copy.deepcopy(original[key])
    artifacts = Artifacts(store, session)
    files = Artifacts(store, original).pack()
    for item in files:
        artifacts.put(item['path'], item['data'])
    artifacts.checkpoint([item['path'] for item in files])
    session['activation_parent'] = original['id']
    store.save(session)
    (store.directory(session['id']) / 'parent-events.jsonl').write_bytes(
        (store.directory(original['id']) / 'events.jsonl').read_bytes())
    return session


def wait(agent, session, seconds):
    worker = agent.workers[session['id']][1]
    worker.join(timeout=seconds)
    timed_out = worker.is_alive()
    if timed_out:
        agent.stop(session['id']); worker.join(timeout=10)
    return {'session': session['id'], 'status': session['status'], 'timed_out': timed_out,
            'steps': session['steps'], 'provider_error_category': session.get('error_category'),
            'last_notices': [item['text'] for item in session.get('feed', []) if item.get('kind') in ('notice', 'error')][-3:]}


def choice_growth(store, settings, agent, frozen, source, output, timeout):
    text = '{"z":[1,true],"é":"猫"}'
    canonical = json.dumps(json.loads(text), sort_keys=True, indent=2, ensure_ascii=False) + '\n'
    task = {'name': 'model-selected-growth', 'fixtures': {'inventory.json': text}, 'checks': [],
        'task': 'Complete an inventory audit. inventory.json must end in canonical JSON and audit.json must '
                'contain its path, final bytes and SHA-256. Two capabilities are missing. Choose which to build first '
                'and write choice.json with {"tool":"format_json"} or {"tool":"sha256_file"}.\n' +
                '\n'.join(CONTRACTS[name] for name in ('format_json', 'sha256_file')) + RECIPE.replace(
                    'Finish completed only after implementing and verifying the feature.', '') +
                '\nStage 1: implement only your chosen capability, test on disposable files, keep inventory.json unchanged, '
                'then finish needs_input requesting activation. Stage 2: after activation, use your first capability '
                'and implement the other missing capability with a separate new test file. Preserve the earlier capability '
                'and all its tests. Finish needs_input requesting activation again. Stage 3: after the second activation, '
                'use both capabilities to finish the audit. audit.json must have path="inventory.json", bytes and sha256 '
                'matching the canonical file. Inspect results and finish completed. Use the tools you built.'}
    atomic_json(output / 'task.json', task)
    first = benchmark.enrich(store, run_task(agent, store, settings.values, task, frozen, timeout))
    session = store.get(first['session'])
    try:
        selected = json.loads(Artifacts(store, session).read('choice.json'))['tool']
        if selected not in ('format_json', 'sha256_file'):
            raise ValueError('Unknown capability choice')
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'first': first, 'selection_error': str(error), 'branches': []}
    review = assess(store, source, first, selected, output / 'first')
    result = {'first': first, 'selected': selected, 'first_review': review, 'branches': []}
    if first['status'] not in ('waiting', 'completed') or first['timed_out'] or not verified(review):
        return result
    if Artifacts(store, session).read('inventory.json') != text.encode():
        result['stage_order_violation'] = True
        return result
    first_source = candidate_source(store, session)
    remaining = 'sha256_file' if selected == 'format_json' else 'format_json'
    missing = verify_feature(store, freeze_source(store, first_source, 'Before second extension'), remaining)
    result['remaining_negative_control'] = missing
    if missing.get('probe', {}).get('checks', {}).get('registered') is not False or missing['passed']:
        result['stage_order_violation'] = True
        return result
    for mode in ('full', 'concise'):
        branch = clone_checkpoint(store, session, mode)
        agent.restart_seed(branch, handoff=mode)
        second = wait(agent, branch, timeout)
        second_review = assess(store, first_source, second, remaining, output / mode / 'second')
        outcome = {'handoff': mode, 'session': branch['id'], 'second': second, 'second_review': second_review}
        outcome['first_activation_usage'] = tool_use(latest_run(journal(store, branch)))
        try:
            edited = candidate_source(store, branch)
        except ValueError as error:
            outcome['candidate_error'] = str(error)
            result['branches'].append(outcome)
            atomic_json(output / 'growth.json', result)
            continue
        combined = freeze_source(store, edited, 'Combined independently checked seed')
        retained = verify_feature(store, combined, selected)
        outcome['retained'] = retained
        if (verified(second_review) and retained['passed'] and not second['timed_out'] and
                second['status'] in ('waiting', 'completed')):
            agent.restart_seed(branch, handoff=mode)
            final = wait(agent, branch, timeout)
            files = Artifacts(store, branch)
            try:
                actual = json.loads(files.read('audit.json'))
                correct = files.read('inventory.json') == canonical.encode() and all(actual.get(k) == v for k, v in {
                    'path': 'inventory.json', 'bytes': len(canonical.encode()),
                    'sha256': hashlib.sha256(canonical.encode()).hexdigest()}.items())
            except (ValueError, OSError, TypeError):
                correct = False
            events = journal(store, branch)
            outcome['final'] = final
            outcome['usage'] = tool_use(latest_run(events))
            outcome['scores'] = growth_scores(True, True, final['status'] == 'completed' and not final['timed_out'],
                                              correct, outcome['usage'], [selected, remaining])
        result['branches'].append(outcome)
        atomic_json(output / 'growth.json', result)
    return result


def main(args):
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Study outputs must stay under .data')
    output.mkdir(parents=True, exist_ok=False)
    source = seed_files(ROOT)
    fingerprint = source_identity(source)
    profiles = profile_configs()
    plan = {'started': now(), 'source_sha256': fingerprint, 'repeats': args.repeats,
            'timeout': args.timeout, 'output_token_budget': args.output_token_budget,
            'budget_scope': 'Per fresh feature task; per VM stage in the legacy forked-growth experiment. All stage budgets are recorded.',
            'profiles': {name: profiles[name] for name in args.profiles}, 'contracts': CONTRACTS,
            'terminal_note': 'Terminal is explicitly enabled for all upgrade trials; saved app preferences are untouched.',
            'choice': 'Model selects the first of two independently specified capabilities needed for a concrete audit.',
            'handoff': 'Full and concise continuations fork the exact same accepted checkpoint; journals remain saved.',
            'qualification': 'At least three repeats, all nine feature upgrades accepted and both growth branches functional. '
                             'A one-repeat pilot cannot qualify a profile; routing scores are reported separately.'}
    atomic_json(output / 'plan.json', plan)
    atomic_json(output / 'starter-source.json', source)
    plan['trusted_sha256'] = {}
    for name in ('evaluations/generalization.py', 'evaluations/generalization-probe.py', 'evaluations/local-model-benchmark.py', 'evaluations/grader_faults.py',
                 'controller/evaluation.py', 'controller/isolation.py', 'controller/artifacts.py',
                 'controller/transport.py', 'controller/providers.py', 'guest/worker.py',
                 'controller/runtime-lock.json', 'controller/managed-runtime-lock.json', 'evaluations/run_budget.py', 'tests/test_seed.py', 'tests/test_text_helpers.py'):
        path = output / 'trusted-runner' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (ROOT / name).read_bytes()
        path.write_bytes(data)
        plan['trusted_sha256'][name] = hashlib.sha256(data).hexdigest()
    atomic_json(output / 'plan.json', plan)
    if args.prepare_only:
        return
    self_check(output, source)
    if args.self_check:
        return
    report = {'status': 'running', 'source_sha256': fingerprint, 'profiles': {}, 'operator_candidate_repairs': []}
    atomic_json(output / 'results.json', report)
    settings = SimpleNamespace(values={**DEFAULTS, 'base_url': 'http://127.0.0.1:11435'}, key=lambda: '')
    engine = LocalRuntime(ROOT, settings)
    try:
        base = engine.ensure_service(allow_download=False)
        for profile in args.profiles:
            config = {**profiles[profile], 'base_url': base}
            settings.values = config
            identity = model_identity(config)
            store = Store(output / profile / 'sessions')
            frozen = freeze_source(store, source, 'Frozen v0.0.11 starter')
            rows = []
            report['profiles'][profile] = {'identity': identity, 'config': config, 'trials': rows,
                                            'qualification': 'not_established'}
            budgets = []
            def factory(cfg):
                budget = GeneratedTokenBudget(args.output_token_budget)
                budgets.append(budget)
                return BudgetDiagnosticClient(cfg, output / profile / 'provider-errors', {'profile': profile}, token_budget=budget)
            agent = IsolatedAgent(ROOT, store, settings, factory)
            try:
                for repeat in range(1, args.repeats + 1):
                    for name, contract in CONTRACTS.items():
                        if source_identity(seed_files(ROOT)) != fingerprint:
                            raise RuntimeError('Frozen starter changed during the study')
                        print('HELDOUT', profile, repeat, name, flush=True)
                        trial = benchmark.enrich(store, run_task(agent, store, config, {
                            'name': name, 'task': 'Add exactly one new public tool. ' + contract + RECIPE, 'checks': []}, frozen, args.timeout))
                        review = assess(store, source, trial, name, output / profile / ('trial-' + str(repeat)) / name)
                        trial['token_budget'] = budgets[-1].summary()
                        rows.append({'name': name, 'repeat': repeat, 'run': trial, 'review': review})
                        atomic_json(output / 'results.json', report)
                        print('HELDOUT RESULT', profile, name, review['accepted'], flush=True)
                growth_dir = output / profile / 'choice'
                growth_dir.mkdir(parents=True)
                growth = choice_growth(store, settings, agent, frozen, source, growth_dir, args.timeout)
                growth['stage_token_budgets'] = [budget.summary() for budget in budgets[len(rows):]]
                report['profiles'][profile]['growth'] = growth
                if args.repeats >= 3 and all(row['review']['accepted'] for row in rows) and len(growth['branches']) == 2 and all(
                        branch.get('scores', {}).get('functional_growth') for branch in growth['branches']):
                    report['profiles'][profile]['qualification'] = 'met_predeclared_criteria'
            finally:
                agent.close()
                try:
                    request_json(base + '/api/generate', {'model': config['model'], 'keep_alive': 0}, timeout=30)
                except Exception:
                    pass
                atomic_json(output / 'results.json', report)
        report.update(status='completed', finished=now(), source_unchanged=source_identity(seed_files(ROOT)) == fingerprint)
    except BaseException as error:
        report.update(status='interrupted', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        engine.close()
        atomic_json(output / 'results.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--profiles', nargs='+', choices=['default', 'qwen9b'], default=['default', 'qwen9b'])
    parser.add_argument('--repeats', type=int, choices=range(1, 6), default=3)
    parser.add_argument('--timeout', type=int, default=DEFAULT_TASK_SECONDS)
    parser.add_argument('--output-token-budget', type=int, default=DEFAULT_OUTPUT_TOKENS)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--self-check', action='store_true')
    main(parser.parse_args())
