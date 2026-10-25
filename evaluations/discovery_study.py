"""Opt-in outcome-first capability discovery; names and tool interface are chosen by the model."""
import argparse
import base64
import copy
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluations')]
from controller.capabilities import declared_tools
from controller.compatibility import model_identity
from controller.config import DEFAULTS
from controller.evaluation import candidate_source, freeze_source, run_task, source_identity, tool_use
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store, atomic_json, now
from model_plan import trusted_files, environment
from observations import CallRecorder, call_metrics, read_events
from run_budget import BudgetModelClient, GeneratedTokenBudget
from study_support import file_identity, identity
import generalization as study


TASK = {
    'name': 'discover-stock-reconciliation', 'checks': [],
    'fixtures': {'shops/east.tsv': 'sku\tunits\napple\t2\npear\t4\napple\t1\n',
                 'shops/west.tsv': 'sku\tunits\npear\t3\nplum\t5\n'},
    'task': 'I regularly receive UTF-8 tab-separated stock files from two shops, with sku and units columns. '
            'Create a reusable seed capability of your choosing that combines both files, sums integer units '
            'for each sku, sorts sku using Python string order, and saves JSON with exactly '
            '{"items":[{"sku":NAME,"units":TOTAL}],"total_units":TOTAL_OF_ALL_UNITS}. '
            'Keep both inputs byte-for-byte unchanged. Choose the tool name and its argument interface yourself. '
            'The output path and both input paths must be caller-selectable. No new dependencies. '
            'Implement and register the capability in harness/autoproteus/tools.py and providers.py; preserve '
            'all existing files and tests and add a separate focused test file. Run the full seed check and '
            'try a small example. Save capability.json containing {"tool":YOUR_TOOL_NAME,"arguments":YOUR_ARGUMENT_OBJECT}. '
            'Within that argument object use the exact strings @INPUT_A, @INPUT_B and @OUTPUT in place of the '
            'two caller input paths and output path. These placeholders describe invocation only; choose all '
            'parameter names and structure yourself. Finish needs_input requesting independent checking and activation. '
            'After activation, use your new capability on shops/east.tsv and shops/west.tsv, save summary.json, '
            'inspect it and finish completed. Internet access is disabled for this offline task.'}


def declaration(value, source, starter):
    if (not isinstance(value, dict) or set(value) != {'tool', 'arguments'} or
            not isinstance(value['tool'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', value['tool']) or
            not isinstance(value['arguments'], dict) or len(json.dumps(value).encode()) > 12000):
        raise ValueError('Invalid capability declaration')
    if value['tool'] == 'finish' or value['tool'] in declared_tools(starter) or value['tool'] not in declared_tools(source):
        raise ValueError('Choose a newly registered capability')
    def leaves(item):
        if isinstance(item, str): return [item]
        if isinstance(item, list): return [leaf for entry in item for leaf in leaves(entry)]
        if isinstance(item, dict): return [leaf for entry in item.values() for leaf in leaves(entry)]
        return []
    if not {'@INPUT_A', '@INPUT_B', '@OUTPUT'} <= set(leaves(value['arguments'])):
        raise ValueError('All three caller-selectable paths must be represented')
    return value


def submitted_declaration(files, source, starter):
    """Invalid handoff data is an observed submission failure, not a crash."""
    try:
        raw = files.read('capability.json')
    except (ValueError, OSError):
        return None, {'valid': False, 'reason': 'missing_root_declaration', 'expected_path': 'capability.json'}
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        return None, {'valid': False, 'reason': 'invalid_json', 'expected_path': 'capability.json'}
    try:
        return declaration(value, source, starter), {'valid': True, 'path': 'capability.json'}
    except ValueError as error:
        return None, {'valid': False, 'reason': 'invalid_declaration', 'detail': str(error)}


def probe(store, source, selected, deadline):
    settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo', 'terminal': True, 'internet': False}, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, lambda _: study.benchmark.ScriptedClient([
        {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 harness/seed.py check && python3 protected-discovery.py'}}}, {'status': 'completed'}]))
    try:
        row = run_task(agent, store, settings.values, {'name': 'independent-discovery', 'task': 'Run held-out outcome checks.',
            'fixtures': {'protected-discovery.py': (ROOT / 'evaluations/discovery_probe.py').read_text(encoding='utf-8'),
                         'discovery-declaration.json': json.dumps(selected)}, 'checks': [{'path': 'discovery-result.json'}]},
            source, max(0, deadline - time.monotonic()), deadline=deadline)
        result = json.loads(Artifacts(store, store.get(row['session'])).read('discovery-result.json')) if row.get('passed') else {}
        return {'passed': bool(row.get('passed') and result.get('passed')), 'probe': result, 'run': row}
    finally: agent.close()


def calibration_source(source, faulty=False):
    result = copy.deepcopy(source)
    implementation = '''        if tool == "stock_reference":
            import csv, io, json
            counts = {}
            for name in args["sources"]:
                for row in csv.DictReader(io.StringIO(self.read_text(self.path(name))), delimiter="\\t"):
                    counts[row["sku"]] = counts.get(row["sku"], 0) + int(row["units"])
            value = {"items": [{"sku": key, "units": counts[key]} for key in sorted(counts)], "total_units": sum(counts.values())}
            return self.write_text(self.path(args["output"]), json.dumps(value, ensure_ascii=False))
'''
    if faulty:
        implementation = implementation.replace('counts.get(row["sku"], 0) + int(row["units"])', 'int(row["units"])')
    for item in result:
        if item['path'] == 'autoproteus/tools.py':
            text = base64.b64decode(item['data']).decode()
            text = text.replace('        if tool == "list_files":', implementation + '        if tool == "list_files":', 1)
            item['data'] = base64.b64encode(text.encode()).decode()
        elif item['path'] == 'autoproteus/providers.py':
            text = base64.b64decode(item['data']).decode().replace('TOOL_SPECS = {', 'TOOL_SPECS = {\n'
                '    "stock_reference": ("Calibration only", {"sources": {"type": "array", "items": STRING}, "output": STRING}, ["sources", "output"]),', 1)
            item['data'] = base64.b64encode(text.encode()).decode()
    return result


def prepare(args):
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / '.data'):
        raise ValueError('Keep evidence under .data')
    output.mkdir(parents=True, exist_ok=False)
    profile = json.loads(Path(args.profile).read_text())
    config = {**DEFAULTS, **profile['config'], 'internet': False}
    source = seed_files(ROOT)
    plan = {'created': now(), 'source': source, 'source_sha256': source_identity(source), 'config': config,
            'task': TASK, 'trusted': trusted_files(), 'environment': environment(),
            'probe_sha256': file_identity(ROOT / 'evaluations/discovery_probe.py'),
            'runner_sha256': file_identity(__file__), 'assets': profile.get('assets', {}),
            'deadline': 3600, 'generated_tokens': 65536,
            'scope': 'Model chooses capability/interface for a fixed business outcome. One directed discovery task, not broad discovery qualification.'}
    atomic_json(output / 'plan.json', plan); (output / 'plan.sha256').write_text(identity(plan))


def run(args):
    output = (ROOT / args.input).resolve()
    if not output.is_relative_to(ROOT / '.data'): raise ValueError('Keep evidence under .data')
    plan = json.loads((output / 'plan.json').read_text())
    if identity(plan) != (output / 'plan.sha256').read_text(): raise ValueError('Plan identity changed')
    def guard():
        if (trusted_files() != plan['trusted'] or environment() != plan['environment'] or
                source_identity(seed_files(ROOT)) != plan['source_sha256'] or
                file_identity(__file__) != plan['runner_sha256'] or
                file_identity(ROOT / 'evaluations/discovery_probe.py') != plan['probe_sha256']):
            raise ValueError('Frozen inputs changed; prepare a new study')
    guard()
    if args.check_only:
        calibration = output / 'calibration'; calibration.mkdir(exist_ok=False)
        store = Store(calibration / 'sessions')
        selected = {'tool': 'stock_reference', 'arguments': {'sources': ['@INPUT_A', '@INPUT_B'], 'output': '@OUTPUT'}}
        rows = {}
        for name, source, expected in [('absent', plan['source'], False),
                ('positive', calibration_source(plan['source']), True),
                ('overwrites_duplicates', calibration_source(plan['source'], True), False)]:
            rows[name] = probe(store, freeze_source(store, source, name), selected, time.monotonic() + 120)
            if not rows[name].get('probe', {}).get('checks') or rows[name]['passed'] != expected:
                atomic_json(calibration / 'results.json', rows)
                raise ValueError('Discovery grader calibration failed: ' + name)
        atomic_json(calibration / 'results.json', rows)
        atomic_json(output / 'calibration.json', {'passed': True, 'plan_sha256': identity(plan)})
        return
    if not (output / 'calibration.json').exists() or json.loads((output / 'calibration.json').read_text()) != {'passed': True, 'plan_sha256': identity(plan)}:
        raise ValueError('Run --check-only before live inference')
    for path, expected in plan.get('assets', {}).items():
        if file_identity(path) != expected: raise ValueError('Inference asset identity changed: ' + path)
    live = output / 'attempt'; live.mkdir(exist_ok=False)
    config = plan['config']; settings = SimpleNamespace(values=config, key=lambda: '')
    store = Store(live / 'sessions'); recorder = CallRecorder(live / 'provider-calls.jsonl')
    budget = GeneratedTokenBudget(plan['generated_tokens'])
    clients = []
    def factory(values):
        client = BudgetModelClient(values, token_budget=budget, observer=recorder)
        clients.append(client)
        return client
    agent = IsolatedAgent(ROOT, store, settings, factory)
    identity_before = model_identity(config)
    deadline = time.monotonic() + plan['deadline']; result = {'started': now(), 'activated': False, 'complete': False,
                                                            'inference_identity': identity_before}
    try:
        result['run'] = run_task(agent, store, config, plan['task'], freeze_source(store, plan['source'], 'Frozen discovery seed'),
                                 plan['deadline'], deadline=deadline)
        session = store.get(result['run']['session']); edited = candidate_source(store, session)
        guard()
        selected, result['submission'] = submitted_declaration(Artifacts(store, session), edited, plan['source'])
        if selected is None:
            result['verification'] = {'status': 'not_run', 'reason': 'invalid_submission',
                                      'scope': 'Unverified capability; submission failure is distinct from a behavior defect.'}
            return
        result['declaration'] = selected
        def feature(store, frozen, _name): return probe(store, frozen, selected, deadline)
        result['review'] = study.benchmark.assess(store, plan['source'], result['run'], selected['tool'], live / 'review', feature, feature,
            lambda root, store, frozen: study.run_regressions(root, store, frozen, deadline=deadline))
        result['verified_extension'] = study.verified(result['review'])
        remaining = config['max_steps'] - session['steps']
        development_preserved = all(Artifacts(store, session).read(path) == text.encode() for path, text in TASK['fixtures'].items())
        result['development_inputs_preserved'] = development_preserved
        if (result['verified_extension'] and development_preserved and session['status'] in ('waiting', 'completed') and
                not result['run']['timed_out'] and remaining > 0 and time.monotonic() < deadline and not budget.summary()['exhausted']):
            from discovery_probe import expected
            settings.values = {**config, 'max_steps': remaining}
            session['candidate_from'] = session['id']
            agent.start(session, 'Use your activated capability to complete the original stock task and inspect summary.json.',
                        candidate=session, handoff='concise', deadline=deadline)
            result['activated'] = True; result['final'] = study.wait(agent, session, max(0, deadline - time.monotonic()))
            result['source_unchanged'] = source_identity(candidate_source(store, session)) == source_identity(edited)
            files = Artifacts(store, session)
            result['artifacts_correct'] = json.loads(files.read('summary.json')) == expected(
                TASK['fixtures']['shops/east.tsv'], TASK['fixtures']['shops/west.tsv']) and all(
                files.read(path) == text.encode() for path, text in TASK['fixtures'].items())
            use = tool_use(study.latest_run(study.journal(store, session))); result['usage'] = use
            result['complete'] = bool(result['final']['status'] == 'completed' and not result['final']['timed_out'] and
                                      result['artifacts_correct'] and result['source_unchanged'] and
                                      selected['tool'] in set(use['direct']) | set(use['development']))
        guard()
        if model_identity(config) != identity_before:
            raise ValueError('Inference service identity changed during the attempt')
    except BaseException as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        agent.close(); result.update(finished=now(), token_budget=budget.summary(), calls=call_metrics(read_events(recorder.path)),
            capture={**recorder.summary(), 'observer_failed': any(client.observation_failed for client in clients)})
        atomic_json(live / 'results.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--profile', required=True); p.add_argument('--output', required=True)
    p = commands.add_parser('run'); p.add_argument('--input', required=True); p.add_argument('--check-only', action='store_true')
    args = parser.parse_args(); {'prepare': prepare, 'run': run}[args.command](args)
