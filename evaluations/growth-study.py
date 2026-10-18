"""Paired cumulative-growth study using a frozen accepted seed and normal app client."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluations')]
import generalization as study
from controller.evaluation import candidate_source, freeze_source, growth_scores, run_task, source_identity, tool_use
from controller.isolation import Artifacts, IsolatedAgent
from controller.providers import request_json
from controller.compatibility import model_identity
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json, now
from observations import CallRecorder, call_metrics, navigation_metrics, read_events
from run_budget import BudgetModelClient, GeneratedTokenBudget, DEFAULT_OUTPUT_TOKENS, DEFAULT_TASK_SECONDS


def private(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to((ROOT / '.data').resolve()): raise ValueError('Use a project .data path')
    return path


def prepare(args):
    profile = json.loads(private(args.profile).read_text())
    if not profile.get('finished') or not any(r['review']['accepted'] for r in profile.get('trials', [])):
        raise ValueError('First complete an accepted upgrade through the normal app connection')
    source = json.loads(private(args.source).read_text())
    output = private(args.output); output.mkdir(parents=True, exist_ok=False)
    plan = {'created': now(), 'config': profile['config'], 'model_identity': profile['model_identity'],
        'source': source, 'source_sha256': source_identity(source), 'timeout': args.timeout,
        'output_token_budget': args.output_token_budget, 'procedure': (ROOT / 'evaluations/upgrade-procedure.md').read_text(),
        'invoke_tool': (ROOT / 'evaluations/invoke_tool.py').read_text(), 'schedule': [],
        'scope': 'Same frozen SHA seed, normal ModelClient, same helper in both arms; only optional procedure differs. No candidate repairs/promotions.',
        'trusted_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'evaluations/growth-study.py', 'evaluations/generalization.py', 'evaluations/generalization-probe.py', 'evaluations/grader_faults.py',
            'evaluations/local-model-benchmark.py', 'evaluations/run_budget.py', 'evaluations/upgrade-procedure.md',
            'evaluations/invoke_tool.py', 'controller/providers.py', 'controller/evaluation.py', 'controller/isolation.py',
            'controller/config.py', 'controller/runtime.py', 'guest/worker.py', 'tests/test_seed.py', 'tests/test_text_helpers.py')}}
    GeneratedTokenBudget(plan['output_token_budget'])
    if plan['timeout'] < 1: raise ValueError('Positive deadline required')
    for repeat in range(1, args.repeats + 1):
        for arm in (('baseline', 'procedure') if repeat % 2 else ('procedure', 'baseline')):
            plan['schedule'].append({'id': f'{repeat}-{arm}', 'repeat': repeat, 'arm': arm})
    atomic_json(output / 'plan.json', plan)
    (output / 'plan.sha256').write_text(hashlib.sha256((output / 'plan.json').read_bytes()).hexdigest())
    (output / 'Start tests.cmd').write_text(f'@echo off\ncd /d "{ROOT}"\n"{ROOT / ".runtime/python/python.exe"}" -X utf8 "{Path(__file__).resolve()}" run --input "{output}"\npause\n')
    print('Prepared', len(plan['schedule']), 'growth attempts; no inference started.', flush=True)


def task(plan, cell):
    fixtures = {'inventory.json': '{"z":[1,true],"é":"猫"}', 'sample.txt': '{"z":1,"a":2}',
                'experience/invoke_tool.py': plan['invoke_tool']}
    hint = ''
    if cell['arm'] == 'procedure':
        fixtures['experience/upgrade.md'] = plan['procedure']
        hint = '\nAn optional concise procedure is in experience/upgrade.md. Read it if useful.'
    return {'name': 'cumulative-audit', 'fixtures': fixtures, 'checks': [], 'task':
        'Your running seed already contains an independently verified sha256_file tool. '
        'Use it on sample.txt, then add exactly one new public tool: ' + study.CONTRACTS['format_json'] +
        study.RECIPE.replace('Finish completed only after implementing and verifying the feature.', '') +
        '\nPreserve sha256_file and every existing test file. Keep inventory.json unchanged during development; '
        'use disposable samples. You may invoke edited tools independently of failing tests using '
        'python3 experience/invoke_tool.py TOOL_NAME \'{"path":"sample.txt"}\'. '
        'After verification, finish needs_input requesting activation. The controller will independently check '
        'and activate the candidate. After activation, use format_json to canonicalize inventory.json and '
        'sha256_file to hash its final bytes. Write audit.json containing path="inventory.json", bytes and sha256 '
        'matching that final file. Inspect results and finish completed. Do not edit the seed after activation.' + hint}


def attempt(output, plan, cell, settings):
    folder = output / cell['id']; folder.mkdir()
    store = Store(folder / 'sessions')
    frozen = freeze_source(store, plan['source'], 'Exact accepted first extension')
    recorder = CallRecorder(folder / 'provider-calls.jsonl', labels=cell)
    budget = GeneratedTokenBudget(plan['output_token_budget'])
    clients = []
    def factory(config):
        client = BudgetModelClient(config, token_budget=budget, observer=recorder)
        clients.append(client); return client
    agent = IsolatedAgent(ROOT, store, settings, factory)
    row = {**cell, 'started': now(), 'operator_candidate_repairs': []}
    started = time.monotonic()
    try:
        if agent.execution.mode != 'vm': raise ValueError('VM isolation required')
        spec = task(plan, cell)
        row['development'] = run_task(agent, store, settings.values, spec, frozen, plan['timeout'])
        session = store.get(row['development']['session'])
        row['second_review'] = study.assess(store, plan['source'], row['development'], 'format_json', folder / 'review')
        edited = candidate_source(store, session)
        combined = freeze_source(store, edited, 'Second candidate')
        row['retained'] = study.verify_feature(store, combined, 'sha256_file')
        row['retained_public'] = study.verify_public(store, combined, 'sha256_file')
        row['verified_extension'] = study.verified(row['second_review'])
        row['stage_order_preserved'] = Artifacts(store, session).read('inventory.json') == spec['fixtures']['inventory.json'].encode()
        row['development_usage'] = tool_use(study.latest_run(study.journal(store, session)))
        retained = row['retained']['passed'] and row['retained_public']['passed']
        remaining = plan['timeout'] - (time.monotonic() - started)
        row['time_budget_exhausted'] = remaining <= 0
        if (row['verified_extension'] and retained and row['stage_order_preserved'] and remaining > 0 and
                not row['development']['timed_out'] and session['status'] in ('completed', 'waiting') and not budget.summary()['exhausted']):
            agent.restart_seed(session, handoff='concise')
            row['final'] = study.wait(agent, session, remaining)
            raw = (json.dumps(json.loads(spec['fixtures']['inventory.json']), sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()
            expected = {'path': 'inventory.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            try:
                receipt = json.loads(Artifacts(store, session).read('audit.json'))
                correct = Artifacts(store, session).read('inventory.json') == raw and all(receipt.get(k) == v for k, v in expected.items())
            except (ValueError, OSError, AttributeError): correct = False
            unchanged = source_identity(candidate_source(store, session)) == source_identity(edited)
            row['final_seed_matches_verified'] = unchanged
            row['final_usage'] = tool_use(study.latest_run(study.journal(store, session)))
            row['scores'] = growth_scores(unchanged, retained, session['status'] == 'completed' and not row['final']['timed_out'],
                correct, row['final_usage'], ['sha256_file', 'format_json'])
    except BaseException as error:
        row['infrastructure_failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        agent.close()
        row['token_budget'] = budget.summary()
        row['calls'] = call_metrics(read_events(recorder.path)); row['capture'] = recorder.summary()
        row['capture']['observer_failed'] = any(client.observation_failed for client in clients)
        if 'development' in row:
            row['navigation'] = navigation_metrics(study.journal(store, store.get(row['development']['session'])))
        row['seconds'] = round(time.monotonic() - started, 3)
        row['finished'] = now(); atomic_json(folder / 'result.json', row)
    return row


def summarize(rows):
    result = {'arms': {}, 'matched_functional_successes': []}
    for arm in ('baseline', 'procedure'):
        selected = [row for row in rows if row['arm'] == arm]
        result['arms'][arm] = {'launched': len(selected), 'finished': sum('finished' in r for r in selected),
            'verified_extensions': sum(bool(r.get('verified_extension')) for r in selected),
            'functional_growth': sum(bool(r.get('scores', {}).get('functional_growth')) for r in selected),
            'direct_route_success': sum(bool(r.get('scores', {}).get('strict_route_success')) for r in selected),
            'budget_stops': sum(bool(r.get('development', {}).get('failure_kind') == 'budget' or
                r.get('development', {}).get('timed_out') or r.get('final', {}).get('timed_out') or
                r.get('final', {}).get('provider_error_category') == 'budget' or
                (r.get('verified_extension') and not r.get('final') and r.get('token_budget', {}).get('exhausted')))
                for r in selected)}
    for repeat in sorted({row['repeat'] for row in rows}):
        pair = [row for row in rows if row['repeat'] == repeat]
        if len(pair) == 2 and all(r.get('scores', {}).get('functional_growth') for r in pair):
            result['matched_functional_successes'].append({'repeat': repeat, 'arms': {r['arm']: {
                'calls': r['calls'], 'seconds': r['seconds'], 'capture': r['capture']} for r in pair}})
    return result


def run(args):
    output = private(args.input)
    if hashlib.sha256((output / 'plan.json').read_bytes()).hexdigest() != (output / 'plan.sha256').read_text().strip():
        raise ValueError('Prepared plan changed')
    plan = json.loads((output / 'plan.json').read_text())
    for name, digest in plan['trusted_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest: raise ValueError('Runner changed; prepare afresh')
    if source_identity(plan['source']) != plan['source_sha256']: raise ValueError('Source changed')
    settings = SimpleNamespace(values=dict(plan['config']), key=lambda: '')
    calibration = Store(output / 'calibration/sessions')
    frozen = freeze_source(calibration, plan['source'], 'First extension calibration')
    if not study.verify_feature(calibration, frozen, 'sha256_file')['passed']:
        raise ValueError('Earlier capability failed calibration')
    engine = LocalRuntime(ROOT, settings)
    path = output / 'results.json'
    report = json.loads(path.read_text()) if path.exists() else {'trials': [], 'status': 'running'}
    try:
        settings.values['base_url'] = engine.ensure_service(allow_download=False)
        if model_identity(settings.values) != plan['model_identity']: raise ValueError('Model/runtime changed')
        for cell in plan['schedule']:
            if any(r['id'] == cell['id'] for r in report['trials']): continue
            if model_identity(settings.values) != plan['model_identity']:
                raise ValueError('Model/runtime changed during comparison')
            for name, digest in plan['trusted_sha256'].items():
                if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                    raise ValueError('Trusted runner changed during comparison')
            # Save launch before execution: interrupted attempts are not silently retried.
            marker = {**cell, 'launched': now()}; report['trials'].append(marker); atomic_json(path, report)
            print('GROWTH TRIAL', cell['id'], flush=True)
            marker.update(attempt(output, plan, cell, settings))
            report['summary'] = summarize(report['trials']); atomic_json(path, report)
            print('GROWTH RESULT', cell['id'], marker.get('verified_extension'), marker.get('scores', {}), flush=True)
        report.update(status='completed', finished=now())
    except BaseException as error:
        report.update(status='interrupted', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        try: request_json(settings.values['base_url'] + '/api/generate', {'model': settings.values['model'], 'keep_alive': 0}, timeout=30)
        except Exception: pass
        engine.close(); atomic_json(path, report)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); commands = p.add_subparsers(dest='command', required=True)
    a = commands.add_parser('prepare')
    a.add_argument('--profile', required=True); a.add_argument('--source', required=True); a.add_argument('--output', required=True)
    a.add_argument('--repeats', type=int, choices=range(1, 6), default=3)
    a.add_argument('--timeout', type=int, default=DEFAULT_TASK_SECONDS)
    a.add_argument('--output-token-budget', type=int, default=DEFAULT_OUTPUT_TOKENS)
    a = commands.add_parser('run'); a.add_argument('--input', required=True)
    args = p.parse_args(); {'prepare': prepare, 'run': run}[args.command](args)
