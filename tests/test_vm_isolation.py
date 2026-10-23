"""Real hostile-guest tests. Opt in on a prepared Windows/WHPX or Linux/KVM host."""
import base64
import json
import os
from pathlib import Path
import tempfile
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

from controller.config import Settings
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store

ROOT = Path(__file__).resolve().parents[1]


class ScriptedClient:
    def __init__(self, actions):
        self.actions, self.index = actions, 0

    def complete(self, messages, cancel):
        result = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return {'content': json.dumps(result), 'usage': {}}


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Real VM checks require explicit opt in')
class RealVMTests(unittest.TestCase):
    def test_static_context_refresh_and_capability_observations_are_source_bound(self):
        from controller.evaluation import run_task, freeze_source, source_identity, candidate_source
        from controller.capabilities import capability_progress
        import sys
        sys.path.insert(0, str(ROOT / 'evaluations'))
        from edit_context import task_support
        source = seed_files(ROOT)
        support = task_support(source, 'Inspect source without importing it.', 'edit-context')
        probe = '''import json, subprocess
from pathlib import Path
def call(*args):
    return json.loads(subprocess.check_output(['python3', 'experience/context_packet.py', *args]))
before = call('--check', 'experience/context.json')
assert before['fresh'] is True
path = Path('harness/autoproteus/tools.py')
path.write_bytes(path.read_bytes() + b'\\n# Draft edit for freshness check\\n')
after = call('--check', 'experience/context.json')
assert after == {'fresh': False, 'stale_paths': ['autoproteus/tools.py'], 'use_old_excerpts': False}
packet = call()
assert len(json.dumps(packet, ensure_ascii=False).encode()) <= 12000
Path('packet-result.json').write_text(json.dumps({'passed': True, 'stale': after['stale_paths']}))
'''
        agent = self.agent([{'action': {'tool': 'run_command', 'arguments': {'command': 'python3 probe_context.py'}}},
                            {'action': {'tool': 'read_file', 'arguments': {'path': 'packet-result.json'}}},
                            {'status': 'completed', 'message': 'Checked actual packet output.'}])
        result = run_task(agent, self.store, self.settings.values,
            {'name': 'context-refresh', 'task': 'Run the static context freshness checks.',
             'fixtures': {**support['fixtures'], 'probe_context.py': probe},
             'checks': [{'path': 'packet-result.json', 'json': {'passed': True, 'stale': ['autoproteus/tools.py']}}]},
            freeze_source(self.store, source, 'Frozen source'), 90)
        self.assertTrue(result['passed'], result)
        session = self.store.get(result['session'])
        self.assertEqual(session['active_seed']['source_sha256'], source_identity(source))
        self.assertIn('read_file', session['active_seed']['direct'])
        progress = capability_progress(candidate_source(self.store, session), session['active_seed'],
                                       {'state': 'unchecked', 'scope': 'No independent feature checks'})
        self.assertFalse(progress['activated'])  # A draft edit is not activation.
        self.assertEqual(progress['model_used'], [])

    def test_concise_activation_preserves_humans_files_journal_and_new_results(self):
        prompts = [[], [], []]
        phases = [
            [{'message': 'OLD DEVELOPMENT EXPLANATION', 'action': {'tool': 'write_file', 'arguments': {'path': 'old.txt', 'content': 'keep'}}},
             {'status': 'needs_input'}],
            [{'action': {'tool': 'write_file', 'arguments': {'path': 'new.txt', 'content': 'new result'}}}, {'status': 'completed'}],
            [{'status': 'completed'}]]
        made = []
        def factory(config):
            index = len(made)
            client = ScriptedClient(phases[index])
            class Capture:
                def complete(self, messages, cancel):
                    prompts[index].append(messages)
                    return client.complete(messages, cancel)
            made.append(client)
            return Capture()
        agent = IsolatedAgent(ROOT, self.store, self.settings, factory)
        self.agents.append(agent)
        task = 'Original user requirements must survive.'
        session = self.store.create(task, 'hosted', 'handoff fixture')
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'waiting')
        for text, origin in [('Keep this human correction.', 'human'), ('Preserve this legacy user constraint.', None)]:
            item = {'role': 'user', 'content': text}
            if origin:
                item['origin'] = origin
            session['messages'].append(item)
            self.store.feed(session, 'user', text)
        agent.restart_seed(session, handoff='concise')
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'][-3:])
        for prompt in prompts[1]:
            content = '\n'.join(item['content'] for item in prompt)
            for expected in (task, 'Keep this human correction.', 'Preserve this legacy user constraint.'):
                self.assertIn(expected, content)
            self.assertNotIn('OLD DEVELOPMENT EXPLANATION', content)
            self.assertTrue(prompt[-1]['content'].startswith('CURRENT ACTIVATION STATE\nRunning seed bundle SHA-256:'))
            self.assertIn('earlier activation request is fulfilled', prompt[-1]['content'])
        phase = prompts[1][0][-1]
        self.assertEqual(phase, prompts[1][-1][-1])
        self.assertFalse(any(item['content'].startswith('CURRENT ACTIVATION STATE') for item in prompts[0][0]))
        self.assertIn('new result', '\n'.join(item['content'] for item in prompts[1][-1]))
        self.assertEqual(Artifacts(self.store, session).read('old.txt'), b'keep')
        self.assertTrue(any('OLD DEVELOPMENT EXPLANATION' in item['content'] for item in session['messages']))
        events = (self.store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8')
        self.assertIn('OLD DEVELOPMENT EXPLANATION', events)
        self.assertIn('context_handoff', events)
        # Ordinary Resume keeps its original full-history behavior.
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed')
        self.assertIn('OLD DEVELOPMENT EXPLANATION', '\n'.join(item['content'] for item in prompts[2][0]))
        self.assertEqual(prompts[2][0][-1], phase)

    def test_protocol_repairs_are_bounded_and_rejected_calls_never_execute(self):
        from controller.providers import ProviderError
        for recover in (False, True):
            class Client:
                calls = 0
                def complete(client, messages, cancel):
                    client.calls += 1
                    if client.calls == 1 or not recover:
                        raise ProviderError('private-provider-detail', {'protocol_reason':'tool_batch', 'tool_calls':[
                            {'function':{'name':'write_file','arguments':{'path':'partial.txt','content':'unsafe'}}}]}, category='protocol')
                    if client.calls == 2:
                        return {'content':json.dumps({'action':{'tool':'write_file','arguments':{'path':'safe.txt','content':'recovered'}}})}
                    return {'content':json.dumps({'status':'completed'})}
            client = Client()
            agent = IsolatedAgent(ROOT, self.store, self.settings, lambda _: client)
            self.agents.append(agent)
            session = self.store.create('Recover only through a valid new response.', 'hosted', 'protocol fixture')
            agent.start(session)
            self.assertEqual(self.wait(agent, session), 'completed' if recover else 'error')
            self.assertEqual(client.calls, 3)
            self.assertEqual(session['steps'], 1 if recover else 0)
            self.assertNotIn('partial.txt', session.get('artifacts', {}))
            self.assertNotIn('private-provider-detail', json.dumps(session))
            if recover:
                self.assertEqual(Artifacts(self.store, session).read('safe.txt'), b'recovered')

    def test_interleaved_cutoffs_preserve_actions_and_the_free_final_response(self):
        from controller.providers import ProviderError
        for retries in (1, 2):
            with self.subTest(retries=retries):
                self.settings.values['max_steps'] = 3
                replies = []
                for index in range(4):
                    replies += [None] * retries
                    replies.append({'action': {'tool': 'write_file', 'arguments': {
                        'path': str(index) + '.txt', 'content': 'saved'}}} if index < 3 else {'status': 'completed'})
                class Client:
                    calls = 0
                    def complete(client, *args):
                        value = replies[client.calls]
                        client.calls += 1
                        if value is None:
                            raise ProviderError('incomplete', category='cutoff')
                        return {'content': json.dumps(value)}
                client = Client()
                agent = IsolatedAgent(ROOT, self.store, self.settings, lambda _: client)
                self.agents.append(agent)
                session = self.store.create('Save all three files and finish after repaired responses.', 'hosted', 'fixture')
                agent.start(session)
                self.assertEqual(self.wait(agent, session, 120), 'completed', session['feed'][-2:])
                self.assertEqual(client.calls, 4 * (retries + 1))
                self.assertEqual(session['steps'], 3)
                for index in range(3):
                    self.assertEqual(Artifacts(self.store, session).read(str(index) + '.txt'), b'saved')

    def test_long_history_uses_bounded_deltas_and_keeps_every_result(self):
        self.settings.values['max_steps'] = 105
        text = 'x' * 6000
        actions = [{'action': {'tool': 'write_file', 'arguments': {'path': 'source.txt', 'content': text}}}]
        actions += [{'action': {'tool': 'read_file', 'arguments': {'path': 'source.txt'}}}] * 100
        actions += [{'status': 'completed'}]
        agent = self.agent(actions)
        session = self.store.create('Keep a long journal without repeated full-state transfer.', 'hosted', 'offline-history-fixture')
        agent.start(session)
        self.assertEqual(self.wait(agent, session, 180), 'completed', session['feed'][-3:])
        self.assertEqual(session['steps'], 101)
        results = [item for item in session['messages'] if item['content'].startswith('ACTION RESULT\n')]
        self.assertEqual(len(results), 101)
        reads = [json.loads(item['content'].split('\n', 1)[1]) for item in results]
        self.assertEqual(sum(item['tool'] == 'read_file' and item['result']['content'] == text for item in reads), 100)
        self.assertEqual(Artifacts(self.store, session).read('source.txt'), text.encode())

    def test_checkpoint_ignores_transient_hidden_paths_and_handles_a_disappearing_file(self):
        candidate = self.candidate('''from pathlib import Path
from autoproteus.agent import Agent

def run(root, store, settings, client_factory, session, message=None):
    workspace = Path(session['workspace'])
    (workspace / '.ignored-export').write_text('ignored')
    (workspace / 'vanished.txt').write_text('transient')
    (workspace / 'keep.txt').write_text('preserved')
    original_stat, original_read = Path.lstat, Path.read_bytes
    def transient_stat(path, *args, **kwargs):
        if path.name == '.ignored-export':
            raise FileNotFoundError(str(path))
        return original_stat(path, *args, **kwargs)
    def transient_read(path, *args, **kwargs):
        if path.name == 'vanished.txt':
            path.unlink(missing_ok=True)
            raise FileNotFoundError(str(path))
        return original_read(path, *args, **kwargs)
    Path.lstat, Path.read_bytes = transient_stat, transient_read
    agent = Agent(root, store, settings, client_factory)
    agent.start(session, message)
    return agent
''')
        agent = self.agent([{'status': 'completed'}])
        session = self.store.create('Ignore paths that vanish during a checkpoint.', 'hosted', 'offline-export-fixture')
        agent.start(session, candidate=candidate)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        self.assertEqual(Artifacts(self.store, session).read('keep.txt'), b'preserved')
        self.assertNotIn('vanished.txt', session['artifacts'])
        self.assertFalse(any('.ignored-export' in name for name in session['artifacts']))

    def test_cutoff_marker_reaches_the_seed_and_partial_calls_never_execute(self):
        from controller.providers import ProviderError
        class Client:
            calls = 0
            def complete(client, messages, cancel):
                client.calls += 1
                if client.calls == 1:
                    raise ProviderError('Bearer private-host-key', response={'tool_calls': [{'unsafe': True}]}, category='cutoff')
                if client.calls == 2:
                    return {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {'path': 'safe.txt', 'content': 'recovered'}}})}
                return {'content': json.dumps({'status': 'completed'})}
        client = Client()
        agent = IsolatedAgent(ROOT, self.store, self.settings, lambda _: client)
        self.agents.append(agent)
        session = self.store.create('Recover without executing partial calls.', 'hosted', 'offline-cutoff-fixture')
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        self.assertEqual(Artifacts(self.store, session).read('safe.txt'), b'recovered')
        self.assertEqual(session['steps'], 1)
        self.assertEqual(client.calls, 3)
        self.assertNotIn('private-host-key', json.dumps(session))

    def test_two_extensions_are_used_and_retained_across_restarts_and_resume(self):
        from controller.evaluation import source_identity
        starter_hash = source_identity(seed_files(ROOT))
        self.settings.values['max_steps'] = 16
        dispatch = '        if tool == "list_files":'
        table = 'TOOL_SPECS = {'
        upper = '''        if tool == "uppercase_file":
            text = self.execute("read_file", {"path": args["path"]})["content"]
            return self.execute("write_file", {"path": args["path"], "content": text.upper()})
'''
        append = '''        if tool == "append_note":
            text = self.execute("read_file", {"path": args["path"]})["content"]
            return self.execute("write_file", {"path": args["path"], "content": text + args["content"]})
'''
        upper_spec = '\n    "uppercase_file": ("Uppercase a file.", {"path": STRING}, ["path"]),'
        append_spec = '\n    "append_note": ("Append a note.", {"path": STRING, "content": STRING}, ["path", "content"]),'
        tests_a = '''import unittest
from pathlib import Path
from autoproteus.tools import Workspace
from test_seed import temporary_directory

class ExtensionTests(unittest.TestCase):
    def test_uppercase(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            workspace.execute("write_file", {"path": "note.txt", "content": "seed"})
            workspace.execute("uppercase_file", {"path": "note.txt"})
            self.assertEqual(workspace.execute("read_file", {"path": "note.txt"})["content"], "SEED")
'''
        tests_ab = tests_a + '''
    def test_append_preserves_first_tool(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            workspace.execute("write_file", {"path": "note.txt", "content": "seed"})
            workspace.execute("append_note", {"path": "note.txt", "content": "!"})
            workspace.execute("uppercase_file", {"path": "note.txt"})
            self.assertEqual(workspace.execute("read_file", {"path": "note.txt"})["content"], "SEED!")
'''
        def action(tool, **arguments):
            return {'action': {'tool': tool, 'arguments': arguments}}
        def install(code, spec, tests):
            return [action('edit_file', path='harness/autoproteus/tools.py', old_text=dispatch, new_text=code + dispatch),
                    action('edit_file', path='harness/autoproteus/providers.py', old_text=table, new_text=table + spec),
                    action('write_file', path='harness/tests/test_extensions.py', content=tests)]
        phases = [
            [action('uppercase_file', path='note.txt'),  # encounter a missing capability
             action('write_file', path='note.txt', content='seed\n'),
             action('write_file', path='probe.txt', content='probe\n'),
             *install(upper, upper_spec, tests_a),
             action('run_command', command="python3 harness/seed.py check --tool uppercase_file --arguments '{\"path\":\"probe.txt\"}'"),
             {'message': 'Verified A. Restart this checkpoint to use it.', 'status': 'needs_input'}],
            [action('uppercase_file', path='note.txt'),
             *install(append, append_spec, tests_ab),
             action('run_command', command="python3 harness/seed.py check --tool append_note --arguments '{\"path\":\"probe.txt\",\"content\":\"!\"}'"),
             {'message': 'Verified A and B. Restart this checkpoint.', 'status': 'needs_input'}],
            [action('uppercase_file', path='note.txt'), action('append_note', path='note.txt', content='|B'),
             {'message': 'Both tools used. Ready for Resume.', 'status': 'needs_input'}],
            [action('append_note', path='note.txt', content='|resume'), action('uppercase_file', path='note.txt'),
             {'message': 'Used both tools after Resume.', 'status': 'completed'}],
        ]
        agent = IsolatedAgent(ROOT, self.store, self.settings, lambda _: ScriptedClient(phases.pop(0)))
        self.agents.append(agent)
        task = 'Grow two file capabilities, keep both, and finish the same saved note after Resume.'
        session = self.store.create(task, 'hosted', 'scripted growth fixture')
        identifier = session['id']
        agent.start(session)
        self.assertEqual(self.wait(agent, session, 120), 'waiting', session['feed'])
        agent.restart_seed(session)
        self.assertEqual(self.wait(agent, session, 120), 'waiting', session['feed'])
        self.assertEqual(Artifacts(self.store, session).read('note.txt'), b'SEED\n')
        agent.restart_seed(session)
        self.assertEqual(self.wait(agent, session, 120), 'waiting', session['feed'])
        agent.start(session)
        self.assertEqual(self.wait(agent, session, 120), 'completed', session['feed'])
        self.assertEqual((session['id'], session['task'], session['runs']), (identifier, task, 4))
        activations = [message for message in session['messages']
                       if message['content'].startswith('Your edited seed is now active.')]
        self.assertEqual(len(activations), 2)  # Ordinary Resume must not claim another activation.
        self.assertTrue(all(message.get('origin') == 'internal' for message in activations))
        self.assertEqual(session['candidate_from'], identifier)
        self.assertEqual(Artifacts(self.store, session).read('note.txt'), b'SEED\n|B|RESUME')
        events = [json.loads(line) for line in (self.store.directory(identifier) / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        commands = [event['data'] for event in events if event['type'] == 'action_result' and event['data']['action']['tool'] == 'run_command']
        self.assertEqual(len(commands), 2)
        self.assertTrue(all(item['ok'] and item['result']['exit_code'] == 0 for item in commands), commands)
        self.assertEqual(source_identity(seed_files(ROOT)), starter_hash)

    def test_development_check_invokes_an_edited_tool_inside_the_vm(self):
        from controller.evaluation import freeze_source
        source = seed_files(ROOT)
        for item in source:
            if item['path'] not in ('autoproteus/tools.py', 'autoproteus/providers.py'):
                continue
            text = base64.b64decode(item['data']).decode('utf-8')
            if item['path'].endswith('tools.py'):
                text = text.replace('        if tool == "list_files":',
                    '        if tool == "fixture_echo":\n            return {"edited_copy": True, "text": args["text"]}\n        if tool == "list_files":')
            else:
                text = text.replace('TOOL_SPECS = {',
                    'TOOL_SPECS = {\n    "fixture_echo": ("Echo a fixture.", {"text": STRING}, ["text"]),')
            item['data'] = base64.b64encode(text.encode('utf-8')).decode()
        candidate = freeze_source(self.store, source, 'Known development-check fixture')
        self.settings.values['max_steps'] = 1  # Finish must still work after the final tool result.
        command = "python3 harness/seed.py check --tool fixture_echo --arguments '{\"text\":\"edited copy\"}' > development-check.txt"
        agent = self.agent([
            {'action': {'tool': 'run_command', 'arguments': {'command': command}}},
            {'status': 'completed'},
        ])
        session = self.store.create('Check edited tools in the guest', 'hosted', 'offline-test')
        agent.start(session, candidate=candidate)
        self.assertEqual(self.wait(agent, session, seconds=90), 'completed', session['feed'])
        output = Artifacts(self.store, session).read('development-check.txt').decode('utf-8')
        records = [json.loads(line) for line in output.splitlines() if line.startswith('{')]
        self.assertTrue(records[0]['passed'], output)
        self.assertGreater(records[0]['tests'], 30)
        self.assertEqual(records[1]['result'], {'edited_copy': True, 'text': 'edited copy'})

    def test_invocation_with_arguments_file_runs_despite_broken_candidate_tests(self):
        from controller.evaluation import freeze_source, run_task
        source = seed_files(ROOT)
        source.append({'path': 'tests/test_deliberately_broken.py', 'data': base64.b64encode(
            b'raise RuntimeError("Deliberately failing development suite")\n').decode()})
        probe = '''import json, subprocess
from pathlib import Path
Path('arguments.json').write_text(json.dumps({'path':'result.txt','content':'猫\\r\\né'}))
invoked = subprocess.run(['python3','harness/seed.py','invoke','--tool','write_file','--arguments-file','arguments.json'], capture_output=True, text=True)
assert invoked.returncode == 0, invoked.stdout + invoked.stderr
assert json.loads(invoked.stdout)['result']['written'] is True
assert Path('result.txt').read_bytes() == '猫\\r\\né'.encode()
Path('arguments.json').write_text(json.dumps({'path':'raw.txt'}))
Path('fragment.txt').write_bytes('print("猫\\\\n")\\r\\n'.encode())
invoked = subprocess.run(['python3','harness/seed.py','invoke','--tool','write_file','--arguments-file','arguments.json',
                          '--text-file','content','fragment.txt'], capture_output=True, text=True)
assert invoked.returncode == 0, invoked.stdout + invoked.stderr
assert Path('raw.txt').read_bytes() == Path('fragment.txt').read_bytes()
outside = Path('/tmp/external-fragment.txt'); outside.write_text('valid external text')
Path('escape.txt').symlink_to(outside)
for name in (str(outside), 'escape.txt'):
    denied = subprocess.run(['python3','harness/seed.py','invoke','--tool','write_file','--arguments-file','arguments.json',
                             '--text-file','content',name], capture_output=True, text=True)
    assert denied.returncode != 0
    assert Path('raw.txt').read_bytes() == Path('fragment.txt').read_bytes()
assert outside.read_text() == 'valid external text'
checked = subprocess.run(['python3','harness/seed.py','check'], capture_output=True, text=True)
assert checked.returncode == 1, checked.stdout + checked.stderr
assert 'Deliberately failing development suite' in checked.stdout
Path('proof.json').write_text(json.dumps({'invoked':True,'tests_passed':False}))
'''
        agent = self.agent([{'action': {'tool': 'run_command', 'arguments': {'command': 'python3 probe.py'}}},
                            {'status': 'completed'}])
        result = run_task(agent, self.store, self.settings.values, {'name': 'invoke-broken-suite', 'task': 'Run the scripted guest probe.',
            'fixtures': {'probe.py': probe}, 'checks': [{'path': 'proof.json', 'json': {'invoked': True, 'tests_passed': False}},
                                                     {'path': 'result.txt', 'equals': '猫\r\né'}]},
            freeze_source(self.store, source, 'Hand-written broken-suite fixture'), 90)
        self.assertTrue(result['passed'], result)

    def test_deleted_file_recreated_with_identical_bytes_survives_checkpoint_and_resume(self):
        agent = self.agent([
            {'action': {'tool': 'write_file', 'arguments': {'path': 'lifecycle.txt', 'content': 'same\n'}}},
            {'action': {'tool': 'delete_file', 'arguments': {'path': 'lifecycle.txt'}}},
            {'action': {'tool': 'write_file', 'arguments': {'path': 'lifecycle.txt', 'content': 'same\n'}}},
            {'action': {'tool': 'read_file', 'arguments': {'path': 'lifecycle.txt'}}},
            {'status': 'completed'},
        ])
        session = self.store.create('Checkpoint deletion lifecycle', 'hosted', 'offline-test')
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        self.assertEqual(Artifacts(self.store, session).read('lifecycle.txt'), b'same\n')
        agent.start(session, 'Verify the restored file')
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        self.assertEqual(Artifacts(self.store, session).read('lifecycle.txt'), b'same\n')

    def test_behavior_check_executes_actual_function_and_rejects_comments_and_early_exit(self):
        from controller.evaluation import verify_behavior
        agent = self.agent([])
        rules = [{'path': 'add.py', 'python_function': 'add', 'cases': [
            {'args': [1, 2], 'equals': 3}, {'args': [-8, 3], 'equals': -5}]}]
        for code, expected in [('def add(a,b):\n # return a + b\n return 0\n', False),
                               ('import os\nos._exit(0)\n', False),
                               ('def add(a,b):\n return a+b\n', True)]:
            session = self.store.create('Behavior verifier', 'hosted', 'offline-test')
            files = Artifacts(self.store, session)
            files.put('add.py', base64.b64encode(code.encode()).decode()); files.checkpoint(['add.py'])
            result = verify_behavior(agent, self.store, session, rules)
            self.assertEqual(result['passed'], expected, result)

    def setUp(self):
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(exist_ok=True, parents=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.data = Path(self.temp.name)
        self.store = Store(self.data / 'sessions')
        self.settings = Settings(self.data)
        self.settings.values.update(configured=True, provider='hosted', model='offline-boundary-test',
                                    protocol='json', terminal=True, max_steps=8)
        self.agents = []

    def tearDown(self):
        for agent in self.agents:
            agent.close()
        self.temp.cleanup()

    def agent(self, actions):
        client = ScriptedClient(actions)
        agent = IsolatedAgent(ROOT, self.store, self.settings, lambda _: client)
        self.agents.append(agent)
        return agent

    def wait(self, agent, session, seconds=45):
        agent.workers[session['id']][1].join(timeout=seconds)
        if agent.workers[session['id']][1].is_alive():
            agent.stop(session['id'])
            self.fail('VM test did not finish within its deadline')
        return session['status']

    def candidate(self, text):
        session = self.store.create('candidate', 'hosted', 'offline-boundary-test')
        artifacts = Artifacts(self.store, session)
        files = {item['path']: item['data'] for item in seed_files(ROOT)}
        files['seed.py'] = base64.b64encode(text.encode()).decode()
        for name, encoded in files.items():
            artifacts.put('harness/' + name, encoded)
        artifacts.checkpoint(['harness/' + name for name in files])
        return session

    def test_commands_cannot_read_host_files_or_change_host_policy_and_have_no_network(self):
        sentinel = self.data / 'host-sentinel.txt'
        sentinel.write_text('HOST SENTINEL MUST SURVIVE')
        policy = (ROOT / 'controller/isolation.py').read_bytes()
        probe = '''import json,os,pathlib,socket,subprocess
report={"uid":os.getuid(),"interfaces":os.listdir('/sys/class/net'),"host_visible":pathlib.Path(HOST).exists(),"controller_visible":pathlib.Path('/controller/isolation.py').exists()}
try:
 os.setuid(0); report['became_root']=True
except PermissionError:
 report['became_root']=False
try:
 socket.create_connection(('10.0.2.2',47831),timeout=1).close(); report['host_network']=True
except OSError:
 report['host_network']=False
try:
 pathlib.Path('/seed/seed.py').write_text('damaged'); report['changed_starter']=True
except PermissionError:
 report['changed_starter']=False
report['remount_exit']=subprocess.run(['mount','-o','remount,size=1g','/work'],capture_output=True).returncode
pathlib.Path('boundary.json').write_text(json.dumps(report))
'''.replace('HOST', repr(str(sentinel)))
        encoded = base64.b64encode(probe.encode()).decode()
        command = "python3 -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""
        agent = self.agent([
            {'message': 'Probe the guest boundary', 'action': {'tool': 'run_command', 'arguments': {'command': command}}},
            {'message': 'Verified', 'status': 'completed'},
        ])
        session = self.store.create('Test boundary', 'hosted', 'offline-boundary-test')
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        report = json.loads(Artifacts(self.store, session).read('boundary.json'))
        self.assertEqual(report['uid'], 1000)
        self.assertEqual(report['interfaces'], ['lo'])
        for key in ('host_visible', 'controller_visible', 'became_root', 'host_network', 'changed_starter'):
            self.assertFalse(report[key], report)
        self.assertNotEqual(report['remount_exit'], 0)
        self.assertEqual(sentinel.read_text(), 'HOST SENTINEL MUST SURVIVE')
        self.assertEqual((ROOT / 'controller/isolation.py').read_bytes(), policy)
        # Restore the checkpoint into another fresh VM using the same policy.
        agent.start(session, 'Verify the saved boundary report')
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        self.assertEqual(json.loads(Artifacts(self.store, session).read('boundary.json')), report)

    def test_both_provider_formats_keep_credentials_outside_guest_and_save_verified_output(self):
        for protocol in ('native', 'json'):
            with self.subTest(protocol=protocol):
                self.provider_gateway(protocol)

    def provider_gateway(self, protocol):
        from controller.evaluation import freeze_source
        requests = []
        secret = 'boundary-test-key-never-send-to-guest'
        content = 'Protected gateway café 🙂\r\n世界 "quotes" \\n\n'
        section_start = content.index('café')
        actions = [
            ('fixture_write', {'path': 'gateway.txt', 'content': content}),
            ('read_file', {'path': 'gateway.txt'}),
            ('read_section', {'path': 'gateway.txt', 'start': section_start, 'length': 4}),
            ('finish', {'message': 'Verified', 'status': 'completed'}),
        ]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((payload, self.headers.get('Authorization')))
                name, args = actions[min(len(requests) - 1, len(actions) - 1)]
                message = ({'content': '', 'tool_calls': [
                    {'id': 'native-test', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}
                    if protocol == 'native' else {'content': json.dumps(args if name == 'finish' else {'action': {'tool': name, 'arguments': args}})})
                body = json.dumps({'choices': [{'finish_reason': 'tool_calls' if protocol == 'native' else 'stop', 'message': message}]}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.settings.update({'base_url': f'http://127.0.0.1:{server.server_port}/v1', 'api_key': secret, 'protocol': protocol})
            agent = IsolatedAgent(ROOT, self.store, self.settings)
            self.agents.append(agent)
            session = self.store.create('Verify the ' + protocol + ' provider gateway', 'hosted', 'offline-boundary-test')
            # A hand-written edited seed proves the active catalog crosses the
            # guest boundary in both formats, without importing it on the host.
            source = seed_files(ROOT)
            for item in source:
                if item['path'] not in ('autoproteus/tools.py', 'autoproteus/providers.py'):
                    continue
                text = base64.b64decode(item['data']).decode()
                if item['path'] == 'autoproteus/tools.py':
                    text = text.replace('        if tool == "list_files":',
                        '        if tool == "fixture_write":\n            return self.execute("write_file", args)\n        if tool == "list_files":')
                else:
                    text = text.replace('TOOL_SPECS = {',
                        'TOOL_SPECS = {\n    "fixture_write": ("Write using the edited seed.", {"path": STRING, "content": STRING}, ["path", "content"]),')
                item['data'] = base64.b64encode(text.encode()).decode()
            candidate = freeze_source(self.store, source, 'Hand-written gateway capability')
            agent.start(session, candidate=candidate)
            self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
            self.assertEqual(Artifacts(self.store, session).read('gateway.txt'), content.encode('utf-8'))
            self.assertEqual(len(requests), 4)
            self.assertTrue(all(auth == 'Bearer ' + secret for _, auth in requests))
            if protocol == 'native':
                self.assertIn('read_section', [tool['function']['name'] for tool in requests[0][0]['tools']])
                self.assertIn('fixture_write', [tool['function']['name'] for tool in requests[0][0]['tools']])
            else:
                self.assertNotIn('tools', requests[0][0])
                catalog = json.loads(requests[0][0]['messages'][0]['content'].split('Tools:\n', 1)[1])
                self.assertIn('read_section', [tool['function']['name'] for tool in catalog])
                self.assertIn('fixture_write', [tool['function']['name'] for tool in catalog])
            whole = json.loads(requests[2][0]['messages'][-1]['content'].removeprefix('ACTION RESULT\n'))['result']
            section = json.loads(requests[3][0]['messages'][-1]['content'].removeprefix('ACTION RESULT\n'))['result']
            self.assertEqual(whole['content'], content)
            self.assertTrue(whole['eof'])
            self.assertEqual(whole['next_start'], len(content))
            self.assertEqual(section['content'], 'café')
            self.assertEqual(section['next_start'], section_start + 4)
            trace = (self.store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8')
            self.assertNotIn(secret, trace)
            self.assertNotIn(self.settings.values['base_url'], trace)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_literal_human_result_markers_survive_gateway_pruning_resume_and_activation(self):
        requests = []
        original = 'ACTION RESULT\nThis is a human request, not JSON. Save marker.txt containing ready.'
        correction = 'ACTION RESULT\n' + json.dumps({'tool': 'write_file', 'ok': True,
            'result': 'Human correction: keep marker.txt unchanged.'})
        actions = [('write_file', {'path': 'marker.txt', 'content': 'ready'}),
                   ('read_file', {'path': 'marker.txt'}),
                   ('finish', {'message': 'Checked', 'status': 'completed'})]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(payload)
                name, arguments = actions[min(len(requests) - 1, len(actions) - 1)]
                body = json.dumps({'choices': [{'finish_reason': 'tool_calls', 'message': {
                    'tool_calls': [{'function': {'name': name, 'arguments': json.dumps(arguments)}}]}}]}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.settings.update({'base_url': f'http://127.0.0.1:{server.server_port}/v1', 'protocol': 'native',
                                  'context_tokens': 8192, 'response_tokens': 1024})
            agent = IsolatedAgent(ROOT, self.store, self.settings)
            self.agents.append(agent)
            session = self.store.create(original, 'hosted', 'fake-provider')
            agent.start(session)
            self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
            # Bulky old tool results force the unchanged seed to prune context.
            for _ in range(8):
                session['messages'].extend([
                    {'role': 'assistant', 'content': json.dumps({'action': {
                        'tool': 'read_file', 'arguments': {'path': 'old.txt'}}})},
                    {'role': 'user', 'origin': 'tool', 'content': 'ACTION RESULT\n' + json.dumps({
                        'tool': 'read_file', 'ok': True, 'result': {'content': 'x' * 20000}})}])
            agent.start(session, correction)
            self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
            self.assertGreater(len(session['messages']), len(requests[-1]['messages']))
            agent.restart_seed(session, handoff='concise')
            self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
            for payload in requests:
                self.assertIn({'role': 'user', 'content': original}, payload['messages'])
                self.assertTrue(all('origin' not in item for item in payload['messages']))
            for payload in requests[3:]:
                self.assertIn({'role': 'user', 'content': correction}, payload['messages'])
            self.assertEqual(Artifacts(self.store, session).read('marker.txt'), b'ready')
            self.assertEqual(len(requests), 5)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_shared_deadline_stops_a_busy_guest_and_skips_late_grading(self):
        from controller.evaluation import freeze_source, run_task, run_regressions
        agent = self.agent([{'action': {'tool': 'run_command', 'arguments': {
            'command': 'python3 -c "import time; time.sleep(120)"'}}}])
        started = time.monotonic()
        result = run_task(agent, self.store, self.settings.values,
            {'name': 'bounded-guest', 'task': 'Run the scripted command.', 'checks': []},
            freeze_source(self.store, seed_files(ROOT), 'Deadline input'), timeout=120, deadline=started + 4)
        self.assertFalse(result['passed'])
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(agent.vms, {})
        with patch('controller.isolation.VM', side_effect=AssertionError('An expired check must not launch a VM')) as vm:
            checked = run_regressions(ROOT, self.store,
                freeze_source(self.store, seed_files(ROOT), 'Late check input'), deadline=started + 4)
        self.assertFalse(checked['passed'])
        vm.assert_not_called()

    def test_editable_seed_regressions_run_inside_the_guest(self):
        agent = self.agent([
            {'message': 'Check the seed', 'action': {'tool': 'run_command', 'arguments': {
                'command': 'cd harness && python3 -m unittest discover -s tests -v'}}},
            {'message': 'Checked', 'status': 'completed'},
        ])
        session = self.store.create('Run the editable seed tests', 'hosted', 'offline-boundary-test')
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        events = [json.loads(line) for line in (self.store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        result = next(event['data']['result'] for event in events if event['type'] == 'action_result')
        self.assertEqual(result['exit_code'], 0, result['output'])
        self.assertIn('OK', result['output'])

    def test_host_rejects_a_forged_export_from_arbitrary_candidate_code(self):
        candidate = self.candidate('''def run(*args):
 import __main__,base64
 __main__.call({'op':'file','path':'../../controller/isolation.py','data':base64.b64encode(b'damaged').decode()})
''')
        policy = (ROOT / 'controller/isolation.py').read_bytes()
        agent = self.agent([])
        session = self.store.create('Try hostile candidate', 'hosted', 'offline-boundary-test')
        agent.start(session, candidate=candidate)
        self.assertEqual(self.wait(agent, session), 'error')
        self.assertIn('Invalid export path', session['feed'][-1]['text'])
        self.assertEqual((ROOT / 'controller/isolation.py').read_bytes(), policy)
        self.assertEqual(session.get('artifacts', {}), {})

    def test_stop_terminates_a_noncooperating_candidate_then_starter_recovers(self):
        candidate = self.candidate('''def run(*args):
 import time
 while True: time.sleep(0.1)
''')
        agent = self.agent([{'message': 'Recovered', 'status': 'completed'}])
        session = self.store.create('Try stuck candidate', 'hosted', 'offline-boundary-test')
        agent.start(session, candidate=candidate)
        limit = time.monotonic() + 15
        while session['id'] not in agent.vms and time.monotonic() < limit:
            time.sleep(.05)
        time.sleep(2)
        process = agent.vms[session['id']].process
        started = time.monotonic()
        agent.stop(session['id'])
        self.assertEqual(self.wait(agent, session, seconds=5), 'paused')
        self.assertLess(time.monotonic() - started, 5)
        self.assertIsNotNone(process.poll())
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])

    def test_comparison_checks_actual_files_from_a_frozen_candidate(self):
        from controller.evaluation import EvaluationService, source_identity, candidate_source
        candidate = self.candidate('''from autoproteus.agent import Agent
def run(root, store, settings, client_factory, session, message=None):
 import json
 class Client:
  calls=0
  def complete(self, messages, cancel):
   self.calls+=1
   return {'content':json.dumps({'action':{'tool':'write_file','arguments':{'path':'greeting.txt','content':'Wrong\\n'}}} if self.calls==1 else {'message':'All tests passed','status':'completed'})}
 agent=Agent(root,store,settings,lambda _:Client())
 agent.start(session,message)
 return agent
''')
        task_agent = self.agent([])
        service = EvaluationService(ROOT, self.data / 'evaluations', self.settings, task_agent)
        task = {'name':'exact-file', 'task':'Create greeting.txt', 'checks':[{'path':'greeting.txt','equals':'Hello, AutoProteus!\n'}]}
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            return json.dumps([task]) if path == ROOT / 'evaluations/tasks.json' else original(path, *args, **kwargs)
        def make_agent(root, store, settings, execution=None):
            return IsolatedAgent(root, store, settings, lambda _: ScriptedClient([
                {'action':{'tool':'write_file','arguments':{'path':'greeting.txt','content':'Hello, AutoProteus!\n'}}},
                {'status':'completed'}]), execution=execution)
        try:
            with patch.object(Path, 'read_text', read_text), patch('controller.evaluation.IsolatedAgent', side_effect=make_agent):
                initial = service.start(candidate, repeats=1)
            expected = initial['edited_sha256']
            # Later workspace edits must not change the frozen version under test.
            a = Artifacts(self.store, candidate)
            a.put('harness/seed.py', base64.b64encode(b'raise RuntimeError("later edit")').decode())
            a.checkpoint(list(candidate['artifacts']))
            service.thread.join(timeout=80)
            self.assertFalse(service.busy)
            report = service.public()
            self.assertEqual(report['status'], 'completed', report)
            self.assertEqual(report['edited_sha256'], expected)
            self.assertNotEqual(source_identity(candidate_source(self.store, candidate)), expected)
            self.assertEqual(report['summary']['starter']['passed'], 1)
            self.assertEqual(report['summary']['edited']['passed'], 0)
            self.assertEqual(report['results'][1]['status'], 'completed')
            self.assertTrue(report['regressions']['starter']['passed'], report['regressions']['starter'])
        finally:
            service.close()

    def test_damaged_input_is_rejected_before_seed_execution(self):
        from controller.isolation import VM
        agent = self.agent([{'status':'completed'}])
        session = self.store.create('damaged input', 'hosted', 'offline-test')
        send = VM.send
        def tamper(vm, value):
            if value.get('op') == 'input' and value.get('area') == 'seed' and value.get('path') == 'seed.py':
                value = {**value, 'data':base64.b64encode(b'raise RuntimeError("must not execute")').decode()}
            return send(vm, value)
        with patch.object(VM, 'send', tamper):
            agent.start(session)
            self.assertEqual(self.wait(agent, session), 'error')
        self.assertIn('Input integrity check failed', session['feed'][-1]['text'])
        self.assertEqual(session['model_requests'], 0)
        self.assertEqual(session.get('artifacts', {}), {})

    def test_navigation_runner_collects_a_scripted_provider_call_without_loading_a_model(self):
        import importlib.util
        from types import SimpleNamespace
        from unittest.mock import Mock
        from test_providers import FakeModelServer
        spec = importlib.util.spec_from_file_location('navigation_smoke', ROOT / 'evaluations/navigation-study.py')
        navigation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(navigation)
        directory = self.data / 'navigation-runner-smoke'
        directory.mkdir()
        server = FakeModelServer(hosted=True)
        try:
            source = seed_files(ROOT)
            config = {**self.settings.values, 'configured': True, 'provider': 'hosted', 'protocol': 'json'}
            cell = {'id': 'fixture-baseline', 'task': 'sha256_file', 'repeat': 1, 'variant': 'baseline'}
            plan = {'config': config, 'output_token_budget': 65536, 'sources': {'baseline': navigation.source_identity(source)},
                    'trusted_sha256': {}, 'schedule': [cell], 'contracts': navigation.study.CONTRACTS, 'timeout': 90}
            engine = Mock()
            engine.ensure_service.return_value = server.url
            with patch.object(navigation, 'private_path', return_value=directory), \
                    patch.object(navigation, 'load_plan', return_value=(plan, {'baseline': source})), \
                    patch.object(navigation, 'calibrate'), patch.object(navigation, 'LocalRuntime', return_value=engine), \
                    patch.object(navigation, 'model_identity', return_value={'digest': 'scripted-fixture', 'engine_version': 'fixture'}), \
                    patch.object(navigation, 'request_json'):
                navigation.run(SimpleNamespace(input='fixture', check_only=False))
            result = json.loads((directory / 'results.json').read_text())
            self.assertEqual(result['status'], 'completed')
            trial = result['trials'][0]
            self.assertEqual(trial['run']['status'], 'completed')
            self.assertFalse(trial['review']['accepted'])  # The fixture intentionally edits no source.
            self.assertTrue(trial['capture']['complete'])
            self.assertEqual(trial['calls']['wire_requests'], 1)
            engine.close.assert_called_once()
        finally:
            server.close()

    def test_usage_variant_anchors_guest_and_host_to_scripted_provider_usage(self):
        import sys
        sys.path.insert(0, str(ROOT / 'evaluations'))
        from experience import UsageClient, variant
        from controller.evaluation import freeze_source
        payloads = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                payloads.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                function = ({'name': 'read_file', 'arguments': {'path': 'sample.txt'}} if len(payloads) == 1 else
                            {'name': 'finish', 'arguments': {'message': 'Verified', 'status': 'completed'}})
                body = {'choices': [{'message': {'content': '', 'tool_calls': [{'function': function}]},
                                    'finish_reason': 'tool_calls'}],
                        'usage': {'prompt_tokens': 500, 'completion_tokens': 20}}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        clients = []
        def factory(config):
            client = UsageClient(config)
            clients.append(client)
            return client
        try:
            self.settings.values.update(base_url=f'http://127.0.0.1:{server.server_port}', protocol='native',
                                        context_tokens=65536, response_tokens=4096)
            agent = IsolatedAgent(ROOT, self.store, self.settings, factory)
            self.agents.append(agent)
            session = self.store.create('Read sample.txt, verify its content and finish.', 'hosted', 'usage fixture')
            Path(session['workspace'], 'sample.txt').write_text('safe text ' * 400)
            source = freeze_source(self.store, variant(seed_files(ROOT), 'usage'), 'Usage test source')
            agent.start(session, candidate=source)
            self.assertEqual(self.wait(agent, session), 'completed', session['feed'][-2:])
            self.assertEqual(len(payloads), 2)
            self.assertEqual(payloads[-1]['max_tokens'], 4096)
            self.assertEqual(clients[0].budget.decisions[-1]['mode'], 'provider_anchor')
            events = [json.loads(line) for line in (self.store.directory(session['id']) / 'events.jsonl').read_text().splitlines()]
            decisions = [event['data'] for event in events if event['type'] == 'context_budget']
            self.assertEqual([item['mode'] for item in decisions], ['conservative_fallback', 'provider_anchor'])
            self.assertEqual(Artifacts(self.store, session).read('sample.txt'), b'safe text ' * 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
