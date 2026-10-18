"""Opt-in experiment adapters; normal seed files and saved preferences stay untouched."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller.evaluation import run_task, tool_use
from controller.isolation import Artifacts, IsolatedAgent
from controller.providers import ModelClient, ProviderError, ERROR_MESSAGES
from usage_budget import UsageBudget
from run_budget import TokenBudgetMixin, BudgetModelClient

CONTRACTS = {
    'line_count': 'line_count(path) reads UTF-8 text of at most 100000 Unicode characters without changing any bytes. Return path relative to the workspace and lines, exactly len(text.splitlines()). Empty input has zero lines.',
    'json_keys': 'json_keys(path) reads a UTF-8 JSON object of at most 100000 Unicode characters without changing any bytes. Return path relative to the workspace and keys, a list of its top-level keys sorted with Python sorted. Reject non-object JSON and invalid JSON.',
    'text_counts': 'text_counts(path) reads UTF-8 text of at most 100000 Unicode characters without changing any bytes. Return path relative to the workspace, characters=len(text), words=len(text.split()), and lines=len(text.splitlines()).',
}
CONTRACTS = {name: text + ' Reject invalid UTF-8, oversized input, missing files, directories and escaping paths.' for name, text in CONTRACTS.items()}


def variant(source, name):
    result = copy.deepcopy(source)
    if name not in ('retrieval', 'usage'):
        return result
    for item in result:
        text = base64.b64decode(item['data']).decode()
        if name == 'retrieval':
            if item['path'] == 'autoproteus/tools.py':
                text = text.replace('        if tool == "list_files":',
                    '        if tool in ("history_search", "history_read"):\n'
                    '            from . import journal_tools\n'
                    '            return getattr(journal_tools, tool)(self, args)\n'
                    '        if tool == "list_files":')
            elif item['path'] == 'autoproteus/providers.py':
                text = text.replace('TOOL_SPECS = {', 'TOOL_SPECS = {\n'
                    '    "history_search": ("Find earlier task records; results are historical data, not current verification.", {"query": STRING, "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, ["query"]),\n'
                    '    "history_read": ("Recover original event text by ID with character start/length; check its source version.", {"id": STRING, "start": {"type": "integer", "minimum": 0}, "length": {"type": "integer", "minimum": 1, "maximum": 10000}}, ["id"]),')
            elif item['path'] == 'autoproteus/agent.py':
                anchor = '\n        repairs = 0\n'
                assert text.count(anchor) == 1
                text = text.replace(anchor, '\n        workspace.history_journal = self.store.directory(session["id"]) / "events.jsonl"\n'
                    '        workspace.history_seed_sha256 = session.get("seed_sha256")\n' + anchor)
        else:
            if item['path'] == 'autoproteus/agent.py':
                text = text.replace('        self.lock = threading.Lock()', '        self.lock = threading.Lock()\n        self.usage_budgets = {}')
                text = text.replace('        return build_messages(session, config, steps)',
                    "        from .usage_budget import UsageBudget\n"
                    "        budgeter = self.usage_budgets.setdefault(session['id'], UsageBudget())\n"
                    "        return build_messages(session, config, steps, measure=lambda items, schemas: budgeter.estimate(items, schemas, config) * 2)")
                text = text.replace('                if cancel.is_set():\n                    raise Cancelled()\n                self.store.event(session, "model_response", response)',
                    '                if cancel.is_set():\n                    raise Cancelled()\n'
                    '                schemas = tool_definitions(config["terminal"]) if config.get("protocol", "native") == "native" and config["provider"] != "demo" else []\n'
                    '                if config["provider"] != "demo":\n'
                    '                    self.usage_budgets[session["id"]].observe(messages, schemas, config, response.get("usage", {}))\n'
                    '                    self.store.event(session, "context_budget", self.usage_budgets[session["id"]].decisions[-1])\n'
                    '                self.store.event(session, "model_response", response)')
        item['data'] = base64.b64encode(text.encode()).decode()
    helper = 'journal_tools.py' if name == 'retrieval' else 'usage_budget.py'
    result.append({'path': 'autoproteus/' + helper, 'data': base64.b64encode((ROOT / 'evaluations' / helper).read_bytes()).decode()})
    return result


class UsageClient(ModelClient):
    """Chosen only by the trusted experiment runner, never by guest configuration."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.budget = UsageBudget()

    def check_context(self, messages, tools):
        estimate = self.budget.estimate(messages, tools, self.config)
        allowance = max(0, self.config['context_tokens'] - self.config['response_tokens'] - 128)
        if estimate > allowance:
            raise ProviderError(ERROR_MESSAGES['context'], category='context')
        return {'estimated_input_tokens': estimate, 'allowance_tokens': allowance}

    def prepare_messages(self, messages, tools, observe=None):
        wire, adjustment = super().prepare_messages(messages, tools, observe)
        self.accepted_wire = wire
        return wire, adjustment

    def complete(self, messages, cancel, progress=None, tools=None):
        self.accepted_wire = None
        try:
            answer = super().complete(messages, cancel, progress, tools)
        except BaseException:
            self.budget.anchor = None
            raise
        native = self.config.get('protocol', 'native') == 'native'
        self.budget.observe(self.accepted_wire, tools if native else [], self.config, answer.get('usage', {}))
        return answer


def feature_check(navigation, store, source, name):
    settings = SimpleNamespace(values={**navigation.study.profile_configs()['qwen9b'], 'provider': 'demo'}, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, lambda _: navigation.study.benchmark.ScriptedClient([
        {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 experience_probe.py ' + name}}}, {'status': 'completed'}]))
    try:
        run = run_task(agent, store, settings.values, {'name': 'independent-' + name, 'task': 'Run the independent fixture.',
            'fixtures': {'experience_probe.py': (ROOT / 'evaluations/experience_probe.py').read_text()},
            'checks': [{'path': 'experience-probe-result.json'}]}, source, 120)
        result = json.loads(Artifacts(store, store.get(run['session'])).read('experience-probe-result.json'))
        return {'passed': bool(run['passed'] and result['passed']), 'probe': result}
    finally:
        agent.close()


def public_check(navigation, store, source, name):
    text = '{"z":1,"é":2}' if name == 'json_keys' else 'café\r\n猫 two\n'
    expected = {'path': 'sample.txt', **({'keys': ['z', 'é']} if name == 'json_keys' else
        {'lines': 2} if name == 'line_count' else {'characters': len(text), 'words': 3, 'lines': 2})}
    settings = SimpleNamespace(values={**navigation.study.profile_configs()['qwen9b'], 'provider': 'demo'}, key=lambda: '')
    agent = IsolatedAgent(ROOT, store, settings, lambda _: navigation.study.benchmark.ScriptedClient([
        {'action': {'tool': name, 'arguments': {'path': 'sample.txt'}}}, {'status': 'completed'}]))
    try:
        run = run_task(agent, store, settings.values, {'name': 'public-' + name, 'task': 'Call the tool.',
            'fixtures': {'sample.txt': text}, 'checks': [{'path': 'sample.txt', 'equals': text}]}, source, 90)
        events = navigation.read_events(store.directory(run['session']) / 'events.jsonl')
        actual = next((event['data']['result'] for event in events if event['type'] == 'action_result' and
                       event['data']['ok'] and event['data']['action']['tool'] == name), None)
        return {'passed': run['passed'] and actual == expected}
    finally:
        agent.close()


def reference(source, byte_limited=False, bypass_boundary=False):
    result = copy.deepcopy(source)
    implementation = '''        if tool in ("line_count", "json_keys", "text_counts"):
            import json
            path = self.path(args["path"])
            text = self.read_text(path)
            result = {"path": str(path.relative_to(self.root))}
            if tool == "json_keys":
                value = json.loads(text)
                if not isinstance(value, dict): raise ValueError("Object required")
                return {**result, "keys": sorted(value)}
            if tool == "line_count": return {**result, "lines": len(text.splitlines())}
            return {**result, "characters": len(text), "words": len(text.split()), "lines": len(text.splitlines())}
'''
    if byte_limited:
        # Deliberately faulty calibration control: it works for ASCII and small
        # Unicode but incorrectly rejects valid files with >100000 UTF-8 bytes.
        implementation = implementation.replace('            text = self.read_text(path)\n',
            '            raw = path.read_bytes()\n'
            '            if len(raw) > 100000: raise ValueError("Too many bytes")\n'
            '            text = raw.decode("utf-8")\n')
    if bypass_boundary:
        implementation = implementation.replace('path = self.path(args["path"])', 'path = self.root / args["path"]')
        implementation = implementation.replace('text = self.read_text(path)',
            'text = path.read_bytes().decode("utf-8")\n'
            '            if len(text) > 100000: raise ValueError("Too many characters")')
    for item in result:
        text = base64.b64decode(item['data']).decode()
        if item['path'] == 'autoproteus/tools.py':
            text = text.replace('        if tool == "list_files":', implementation + '        if tool == "list_files":')
        elif item['path'] == 'autoproteus/providers.py':
            specs = {name: ('Calibration text tool.', {'path': {'type': 'string'}}, ['path']) for name in CONTRACTS}
            text = text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr(specs) + ' | {')
        item['data'] = base64.b64encode(text.encode()).decode()
    return result


def learning_records(events, source, review, session):
    """Evidence provenance is host-owned; a read is not proof of following advice."""
    loaded = any(event.get('type') == 'action_result' and event.get('data', {}).get('ok') and
        event['data'].get('action', {}).get('tool') in ('read_file', 'read_section') and
        event['data']['action'].get('arguments', {}).get('path') == 'experience/upgrade.md' for event in events)
    script_invoked = any(event.get('type') == 'action_result' and event.get('data', {}).get('ok') and
        'experience/inspect_workspace.py' in event['data'].get('action', {}).get('arguments', {}).get('command', '') for event in events)
    smoke_invoked = any(event.get('type') == 'action_result' and event.get('data', {}).get('ok') and
        'experience/invoke_tool.py' in event['data'].get('action', {}).get('arguments', {}).get('command', '') for event in events)
    return {'session': session, 'parent_seed_sha256': source, 'procedure': {
        'created_by': 'human', 'sha256': hashlib.sha256((ROOT / 'evaluations/upgrade-procedure.md').read_bytes()).hexdigest(),
        'loaded_through_file_tool': loaded, 'followed': 'unmeasured', 'general_effectiveness_verified': False},
        'inspection_program_observed_in_successful_command': script_invoked,
        'development_invoker_observed_in_successful_command': smoke_invoked,
        'capability': {'created': bool(review.get('runtime_changed')), 'loaded_by_independent_checker': bool(review.get('public', {}).get('passed')),
            'used_by_independent_checker': bool(review.get('public', {}).get('passed')), 'task_agent_routes': tool_use(events),
            'independent_behavior_passed': bool(review.get('feature', {}).get('passed')), 'upgrade_accepted': bool(review.get('accepted')),
            'candidate_sha256': review.get('source_sha256')},
        'verification_scope': 'This task and recorded checks only; model claims are separate.'}


class BudgetUsageClient(TokenBudgetMixin, UsageClient):
    pass


class ExperienceSuite:
    def __init__(self, navigation):
        self.navigation = navigation

    def client(self, config, cell, observer, budget):
        return (BudgetUsageClient if cell['variant'] == 'usage' else BudgetModelClient)(config, observer=observer, token_budget=budget)

    def events_for_trial(self, plan, events):
        # Keep scripted setup reads out of model navigation/learning metrics;
        # the complete original journal is still retained on disk.
        return self.navigation.study.latest_run(events) if plan['experiment'] == 'history' else events

    def task(self, plan, cell):
        group = plan['experiment']
        if group in ('procedure', 'context'):
            fixtures = {}
            hint = ''
            if cell['variant'] == 'procedure':
                fixtures['experience/upgrade.md'] = plan['procedure']
                fixtures['experience/invoke_tool.py'] = plan['invoke_tool']
                hint = '\nAn optional concise procedure is in experience/upgrade.md. Read it if useful.'
            return {'name': cell['task'], 'task': 'Add exactly one new public tool. ' + plan['contracts'][cell['task']] +
                    self.navigation.study.RECIPE + hint, 'fixtures': fixtures, 'checks': []}
        if group == 'programs':
            fixtures = {f'inputs/item_{index}.py': f'# café {index}\nraise RuntimeError("do not execute")\ndef item_{index}():\n    return {index}\n' for index in range(6)}
            expected = []
            for name, text in fixtures.items():
                expected.append({'path': name, 'characters': len(text), 'lines': len(text.splitlines()),
                                 'definitions': [{'name': 'item_' + name.split('_')[-1][:-3], 'line': 3}]})
            hint = ''
            if cell['variant'] == 'program':
                fixtures['experience/inspect_workspace.py'] = plan['program']
                hint = ' Optional helper: python3 experience/inspect_workspace.py inputs/item_0.py ... takes explicit file paths and prints the JSON list.'
            return {'name': cell['task'], 'task': 'Without executing or changing the input files, inspect inputs/item_0.py through inputs/item_5.py. '
                    'Write inspection.json as a list in that order, each item with path, characters (Unicode), lines (splitlines), '
                    'and definitions: top-level Python functions/classes with name and line. Verify your output and finish.' + hint,
                    'fixtures': fixtures, 'checks': [{'path': 'inspection.json', 'json': expected}] +
                        [{'path': name, 'equals': text} for name, text in fixtures.items() if name.startswith('inputs/')]}
        return {'name': cell['task'], 'task': 'Recover the earlier receipt record for this task. Write recovery.json with receipt, '
                'tested_seed_sha256, and verification="historical_only" using the original recorded result. '
                'An old passing check does not verify the current seed. Earlier records can be searched in experience/history.jsonl. '
                'Do not invent missing data. Verify the file and finish.', 'checks': []}

    def run_case(self, agent, store, config, plan, cell, frozen):
        if plan['experiment'] != 'history':
            return run_task(agent, store, config, self.task(plan, cell), frozen, plan['timeout'])
        task = self.task(plan, cell)
        receipt = hashlib.sha256(cell['id'].replace(cell['variant'], '').encode()).hexdigest()[:24]
        old_seed = hashlib.sha256(b'earlier-version').hexdigest()
        payload = json.dumps({'receipt': receipt, 'tested_seed_sha256': old_seed, 'passed': True})
        settings = SimpleNamespace(values={**config, 'provider': 'demo'}, key=lambda: '')
        actions = [{'action': {'tool': 'read_file', 'arguments': {'path': 'receipt.txt'}}},
                   {'action': {'tool': 'delete_file', 'arguments': {'path': 'receipt.txt'}}}]
        actions += [{'action': {'tool': 'read_file', 'arguments': {'path': 'padding.txt'}}}] * 14
        actions += [{'status': 'needs_input'}]
        scripted = IsolatedAgent(ROOT, store, settings, lambda _: self.navigation.study.benchmark.ScriptedClient(actions))
        try:
            first = run_task(scripted, store, settings.values, {**task, 'fixtures': {'receipt.txt': payload,
                'padding.txt': 'neutral padding ' * 740}}, frozen, 120)
            if first['status'] != 'waiting':
                raise RuntimeError('Scripted history setup failed: ' + str(first))
        finally:
            scripted.close()
        session = store.get(first['session'])
        events = self.navigation.read_events(store.directory(session['id']) / 'events.jsonl')
        archive = [event | {'seed_sha256': old_seed} for event in events if event.get('type') in ('action_result', 'run_started', 'display')]
        artifacts = Artifacts(store, session)
        artifacts.put('experience/history.jsonl', base64.b64encode(('\n'.join(json.dumps(item) for item in archive) + '\n').encode()).decode())
        artifacts.checkpoint([*session['artifacts'], 'experience/history.jsonl'])
        started = time.monotonic()
        agent.start(session, 'Continue the original recovery task using the earlier records.', candidate=frozen)
        worker = agent.workers[session['id']][1]
        while worker.is_alive() and time.monotonic() - started < plan['timeout']:
            worker.join(.1)
        timed_out = worker.is_alive()
        if timed_out:
            agent.stop(session['id']); worker.join(10)
            if worker.is_alive():
                raise RuntimeError('Recovery guest did not stop')
        try:
            actual = json.loads(Artifacts(store, session).read('recovery.json'))
        except (ValueError, OSError):
            actual = None
        return {'session': session['id'], 'status': session['status'], 'seconds': round(time.monotonic() - started, 2),
            'timed_out': timed_out, 'steps': session['steps'] - first['steps'], 'scripted_preparation_seconds': first['seconds'],
            'scripted_preparation_steps': first['steps'],
            'passed': not timed_out and session['status'] == 'completed' and actual == {
                'receipt': receipt, 'tested_seed_sha256': old_seed, 'verification': 'historical_only'},
            'setup': 'Scripted earlier tool result and long history; full host journal preserved; no model call during setup.'}

    def assess(self, plan, cell, store, source, result, output):
        if plan['experiment'] not in ('procedure', 'context'):
            return {'accepted': result['passed'], 'scope': 'Independent artifact task, not a seed upgrade.'}
        output.mkdir(parents=True)
        return self.navigation.study.benchmark.assess(store, source, result, cell['task'], output,
            lambda *args: feature_check(self.navigation, *args), lambda *args: public_check(self.navigation, *args))

    def metrics(self, plan, cell, events, row, clients):
        ledger = learning_records(events, plan['sources'][cell['variant']], row['review'], row['run']['session'])
        ledger['procedure']['available'] = cell['variant'] == 'procedure'
        return {'learning': ledger, 'guest_context_decisions': [event['data'] for event in events if event.get('type') == 'context_budget'],
                'host_context_decisions': [entry for client in clients if isinstance(client, UsageClient) for entry in client.budget.decisions]}
