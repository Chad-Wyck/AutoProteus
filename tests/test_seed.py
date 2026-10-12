import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from autoproteus.agent import Agent, parse_action
from autoproteus.config import Settings, protect
from autoproteus.providers import DemoClient, ModelClient, ProviderError, model_response, normalize_tool_response, tool_definitions, wire_messages
from autoproteus.server import Application, make_server
from autoproteus.storage import Store
from autoproteus.tools import Cancelled, Workspace

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP = ROOT / '.data' / 'test-tmp'


def temporary_directory():
    TEST_TEMP.mkdir(parents=True, exist_ok=True)
    directory = tempfile.TemporaryDirectory(dir=TEST_TEMP)
    # Verify every test cleanup target remains inside this workspace.
    if not Path(directory.name).resolve().is_relative_to(TEST_TEMP.resolve()):
        raise RuntimeError('Unexpected temporary directory')
    return directory


def wait_session(agent, session, seconds=8):
    # A final status is visible before the worker finishes its last save.
    worker = agent.workers[session['id']][1]
    worker.join(timeout=seconds)
    return 'running' if worker.is_alive() else session['status']


class WorkspaceTests(unittest.TestCase):
    def test_traversal_and_absolute_paths_are_rejected(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            for path in ('../outside.txt', str(Path(directory).parent / 'outside.txt')):
                for tool, arguments in [('write_file', {'content': 'bad'}), ('read_file', {}),
                                        ('edit_file', {'old_text': 'old', 'new_text': 'new'})]:
                    with self.subTest(tool=tool, path=path), self.assertRaises(ValueError):
                        workspace.execute(tool, {'path': path, **arguments})

    def test_terminal_requires_explicit_enablement(self):
        with temporary_directory() as directory:
            with self.assertRaises(ValueError):
                Workspace(Path(directory)).execute('run_command', {'command': 'echo test'})

    def test_checklist_uses_ordinary_file_tools(self):
        self.assertNotIn('update_todo', [tool['function']['name'] for tool in tool_definitions()])
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            workspace.execute('write_file', {'path': 'todo.txt', 'content': '[x] Verified\n'})
            self.assertEqual(workspace.execute('read_file', {'path': 'todo.txt'})['content'], '[x] Verified\n')

    def test_read_continuation_preserves_unicode_and_line_endings(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            content = '\ufeffHello é🙂\r\n世界\n'
            workspace.execute('write_file', {'path': 'text.txt', 'content': content})
            self.assertEqual((Path(directory) / 'text.txt').read_bytes(), content.encode('utf-8'))
            offset, chunks = 0, []
            for _ in range(len(content)):
                result = workspace.execute('read_file', {'path': 'text.txt', 'offset': offset, 'length': 2})
                self.assertLessEqual(len(result['content']), 2)
                self.assertEqual(result['next_offset'], offset + len(result['content'].encode('utf-8')))
                chunks.append(result['content'])
                offset = result['next_offset']
                if result['eof']:
                    break
            self.assertTrue(result['eof'])
            self.assertEqual(''.join(chunks), content)
            self.assertEqual(offset, len(content.encode('utf-8')))
            self.assertEqual(workspace.execute('read_file', {'path': 'text.txt', 'offset': offset})['content'], '')

    def test_read_rejects_invalid_ranges_and_split_utf8_characters(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            (Path(directory) / 'text.txt').write_bytes('é'.encode('utf-8') + b'x' * 13000)
            self.assertEqual(len(workspace.execute('read_file', {'path': 'text.txt'})['content']), 1000)
            for arguments in ({'offset': -1}, {'offset': True}, {'offset': 1}, {'offset': 0.5},
                              {'length': 0}, {'length': 12001}, {'length': '10'}):
                with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                    workspace.execute('read_file', {'path': 'text.txt', **arguments})

    def test_precise_edit_preserves_surrounding_bytes(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            path = Path(directory) / 'source.py'
            before = '\ufeff# café 🙂\r\nvalue = 1\r\n# end\n'.encode('utf-8')
            path.write_bytes(before)
            result = workspace.execute('edit_file', {'path': 'source.py', 'old_text': 'value = 1', 'new_text': 'value = 2'})
            self.assertEqual(path.read_bytes(), before.replace(b'value = 1', b'value = 2'))
            self.assertEqual(result['replacements'], 1)
            self.assertEqual(result['bytes'], len(path.read_bytes()))

    def test_precise_edit_rejects_missing_ambiguous_and_oversized_changes(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            path = Path(directory) / 'text.txt'
            for content, old, new in [('hello hello', 'hello', 'new'), ('aaa', 'aa', 'new'),
                                      ('unchanged', 'missing', 'new'), ('unchanged', '', 'new'),
                                      ('x', 'x', 'y' * 100001), ('target' + 'x' * 99994, 'target', 'longer target')]:
                before = content.encode('utf-8'); path.write_bytes(before)
                with self.subTest(old=old[:20]), self.assertRaises(ValueError):
                    workspace.execute('edit_file', {'path': 'text.txt', 'old_text': old, 'new_text': new})
                self.assertEqual(path.read_bytes(), before)

    def test_stop_before_edit_write_preserves_original_file(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            path = Path(directory) / 'text.txt'; path.write_bytes(b'original')
            with patch.object(workspace.cancel, 'is_set', side_effect=[False, True]), self.assertRaises(Cancelled):
                workspace.execute('edit_file', {'path': 'text.txt', 'old_text': 'original', 'new_text': 'changed'})
            self.assertEqual(path.read_bytes(), b'original')

    def test_cancellation_prevents_file_write(self):
        with temporary_directory() as directory:
            cancel = threading.Event(); cancel.set()
            with self.assertRaises(Cancelled):
                Workspace(Path(directory), cancel=cancel).execute('write_file', {'path': 'late.txt', 'content': 'bad'})
            self.assertFalse((Path(directory) / 'late.txt').exists())

    def test_enabled_terminal_returns_exit_code_and_times_out(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory), terminal=True, timeout=1)
            command = "Write-Output 'terminal-ok'" if os.name == 'nt' else "printf terminal-ok"
            result = workspace.execute('run_command', {'command': command})
            self.assertEqual(result['exit_code'], 0)
            self.assertIn('terminal-ok', result['output'])
            command = 'Start-Sleep -Seconds 10' if os.name == 'nt' else 'sleep 10'
            result = workspace.execute('run_command', {'command': command})
            self.assertTrue(result['timed_out'])


class ProtocolTests(unittest.TestCase):
    def test_prose_fences_multiple_objects_and_ambiguous_actions_fail(self):
        for text in ('```bash\necho bad\n```', '{}{}', '{}', '[]',
                     '{"message":"x","action":{"tool":"write_file","arguments":{}},"status":"completed"}',
                     '{"status":"anything"}', '{"action":{"tool":"write_file","arguments":"wrong"}}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_action(text)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.guest_marker = patch.dict(os.environ, {'AUTOPROTEUS_GUEST': '1'})
        self.guest_marker.start()
        self.temporary = temporary_directory()
        self.directory = Path(self.temporary.name)
        self.settings = Settings(self.directory)
        self.settings.update({'provider': 'demo', 'model': 'scripted-demo', 'configured': True})
        self.store = Store(self.directory / 'sessions')

    def tearDown(self):
        self.temporary.cleanup()
        self.guest_marker.stop()

    def test_complete_run_refreshes_todo_and_records_all_events(self):
        agent = Agent(ROOT, self.store, self.settings)
        session = self.store.create('Create a sample welcome file.', 'demo', 'scripted-demo')
        agent.start(session)
        self.assertEqual(wait_session(agent, session), 'completed')
        workspace = Path(session['workspace'])
        self.assertIn('Hello from AutoProteus', (workspace / 'welcome.md').read_text())
        self.assertIn('[x]', session['todo'])
        self.assertTrue((workspace / 'harness' / 'autoproteus' / 'agent.py').exists())
        journal = [json.loads(line) for line in (self.store.directory(session['id']) / 'events.jsonl').read_text().splitlines()]
        types = [event['type'] for event in journal]
        self.assertEqual(types.count('model_request'), 5)
        self.assertEqual(types.count('model_response'), 5)
        self.assertEqual(types.count('action_started'), 4)
        self.assertEqual(types.count('action_result'), 4)
        self.assertNotIn('api_key', json.dumps(journal))
        agent.close()

    def test_late_response_after_stop_cannot_execute(self):
        started = threading.Event()
        class LateClient:
            def complete(self, messages, cancel):
                started.set(); cancel.wait(2)
                return {'content': json.dumps({'message': 'late', 'action': {'tool': 'write_file', 'arguments': {'path': 'late.txt', 'content': 'bad'}}})}
        agent = Agent(ROOT, self.store, self.settings, lambda _: LateClient())
        session = self.store.create('Test cancellation', 'demo', 'scripted-demo')
        agent.start(session); self.assertTrue(started.wait(2)); agent.stop(session['id'])
        self.assertEqual(wait_session(agent, session), 'paused')
        self.assertFalse((Path(session['workspace']) / 'late.txt').exists())
        agent.close()

    def test_invalid_model_output_has_bounded_retries_and_no_action(self):
        class BadClient:
            def complete(self, *args):
                return {'content': '```bash\necho never execute\n```'}
        agent = Agent(ROOT, self.store, self.settings, lambda _: BadClient())
        session = self.store.create('Test formatting', 'demo', 'scripted-demo')
        agent.start(session)
        self.assertEqual(wait_session(agent, session), 'error')
        self.assertEqual(session['steps'], 0)
        self.assertEqual(len([item for item in session['feed'] if item['kind'] == 'notice']), 2)
        agent.close()

    def test_native_prose_is_repaired_before_explicit_finish(self):
        class RepairClient:
            calls = 0
            def complete(client, messages, cancel):
                client.calls += 1
                if client.calls == 1:
                    return model_response('All done.', [], True)
                self.assertIn('Call finish', messages[-1]['content'])
                return model_response('', [{'function': {'name': 'finish', 'arguments':
                    {'message': 'Verified.', 'status': 'completed'}}}], True)
        client = RepairClient()
        agent = Agent(ROOT, self.store, self.settings, lambda _: client)
        session = self.store.create('Test explicit completion', 'demo', 'scripted-demo')
        agent.start(session)
        self.assertEqual(wait_session(agent, session), 'completed')
        self.assertEqual(client.calls, 2)
        self.assertEqual(session['steps'], 1)
        self.assertEqual(len([item for item in session['feed'] if item['kind'] == 'notice']), 1)
        agent.close()

    def test_native_prose_does_not_infer_waiting_and_retries_are_bounded(self):
        class ProseClient:
            calls = 0
            def complete(client, *args):
                client.calls += 1
                return model_response('Which filename should I use?', [], True)
        client = ProseClient()
        agent = Agent(ROOT, self.store, self.settings, lambda _: client)
        session = self.store.create('Test explicit input request', 'demo', 'scripted-demo')
        agent.start(session)
        self.assertEqual(wait_session(agent, session), 'error')
        self.assertEqual(client.calls, 3)
        self.assertEqual(session['steps'], 0)
        agent.close()

    def test_restart_marks_active_run_interrupted_and_keeps_pending_action(self):
        session = self.store.create('Recover me', 'demo', 'scripted-demo')
        session.update(status='running', pending_action={'tool': 'write_file', 'arguments': {}})
        self.store.save(session)
        recovered = Store(self.directory / 'sessions').get(session['id'])
        self.assertEqual(recovered['status'], 'interrupted')
        self.assertEqual(recovered['pending_action']['tool'], 'write_file')

    def test_step_limit_pauses_and_resume_keeps_same_workspace(self):
        self.settings.update({'max_steps': 2})
        agent = Agent(ROOT, self.store, self.settings)
        session = self.store.create('Small run', 'demo', 'scripted-demo')
        agent.start(session); self.assertEqual(wait_session(agent, session), 'paused')
        workspace = session['workspace']
        self.settings.update({'max_steps': 10})
        agent.start(session); self.assertEqual(wait_session(agent, session), 'completed')
        self.assertEqual(session['workspace'], workspace)
        self.assertEqual(session['runs'], 2)
        agent.close()

    def test_native_batch_executes_in_order_then_verifies_before_finish(self):
        class BatchClient:
            calls = 0
            def complete(client, messages, cancel):
                client.calls += 1
                if client.calls == 1:
                    return {'content': normalize_tool_response('', [
                        {'function': {'name': 'write_file', 'arguments': {'path':'batch.txt','content':'verified'}}},
                        {'function': {'name': 'read_file', 'arguments': {'path':'batch.txt'}}},
                        {'function': {'name': 'finish', 'arguments': {'message':'Too early','status':'completed'}}}])}
                self.assertIn('verified', json.dumps(messages))
                self.assertIn('deferred', messages[-1]['content'])
                return {'content': json.dumps({'message':'Verified','status':'completed'})}
        client = BatchClient()
        agent = Agent(ROOT, self.store, self.settings, lambda _: client)
        session = self.store.create('Batch test', 'demo', 'scripted-demo')
        agent.start(session)
        self.assertEqual(wait_session(agent, session), 'completed')
        self.assertEqual(client.calls, 2)
        self.assertEqual((Path(session['workspace']) / 'batch.txt').read_text(), 'verified')
        agent.close()

    def test_batch_failure_skips_dependent_calls_and_obeys_step_limit(self):
        class BatchClient:
            def complete(client, *args):
                return {'content': json.dumps({'actions': [
                    {'tool':'read_file', 'arguments':{'path':'missing.txt'}},
                    {'tool':'write_file', 'arguments':{'path':'should-not-exist.txt', 'content':'bad'}}]})}
        self.settings.update({'max_steps': 2})
        agent = Agent(ROOT, self.store, self.settings, lambda _: BatchClient())
        session = self.store.create('Failure test', 'demo', 'scripted-demo')
        agent.start(session)
        self.assertEqual(wait_session(agent, session), 'paused')
        self.assertEqual(session['steps'], 2)
        self.assertFalse((Path(session['workspace']) / 'should-not-exist.txt').exists())
        agent.close()

    def test_large_history_keeps_tool_messages_valid(self):
        self.settings.update({'context_tokens': 2048, 'response_tokens': 512})
        agent = Agent(ROOT, self.store, self.settings)
        session = self.store.create('Preserve valid history', 'demo', 'scripted-demo')
        session['messages'] = [
            {'role':'assistant', 'content':json.dumps({'action':{'tool':'write_file','arguments':{'path':'large.txt','content':'a' * 20000}}})},
            {'role':'user', 'content':'ACTION RESULT\n' + json.dumps({'tool':'write_file','ok':True,'result':{'content':'a' * 20000}})}]
        config = {**self.settings.values, 'provider':'ollama'}
        messages = agent.messages(session, config)
        self.assertEqual(wire_messages(messages, False)[-1]['role'], 'user')
        self.assertTrue(json.loads(messages[-1]['content'].split('\n', 1)[1])['result']['context_shortened'])
        agent.close()

    def test_native_edit_is_verified_and_journaled(self):
        class EditClient:
            calls = 0
            def complete(client, messages, cancel):
                client.calls += 1
                if client.calls == 1:
                    name, arguments = 'edit_file', {'path': 'sample.py', 'old_text': 'value = 1', 'new_text': 'value = 2'}
                elif client.calls == 2:
                    name, arguments = 'read_file', {'path': 'sample.py'}
                else:
                    result = json.loads(messages[-1]['content'].split('\n', 1)[1])['result']
                    self.assertEqual(result['content'], 'value = 2\r\n')
                    self.assertTrue(result['eof'])
                    name, arguments = 'finish', {'message': 'Verified the edit.', 'status': 'completed'}
                return model_response('', [{'function': {'name': name, 'arguments': arguments}}], True)
        client = EditClient()
        self.settings.update({'provider': 'ollama', 'model': 'offline-test'})
        agent = Agent(ROOT, self.store, self.settings, lambda _: client)
        session = self.store.create('Change value to 2 and verify it.', 'ollama', 'offline-test')
        path = Path(session['workspace']) / 'sample.py'; path.write_bytes(b'value = 1\r\n')
        agent.start(session)
        self.assertEqual(wait_session(agent, session), 'completed')
        self.assertEqual(path.read_bytes(), b'value = 2\r\n')
        journal = [json.loads(line) for line in (self.store.directory(session['id']) / 'events.jsonl').read_text().splitlines()]
        actions = [event['data']['action']['tool'] for event in journal if event['type'] == 'action_result']
        self.assertEqual(actions, ['edit_file', 'read_file'])
        agent.close()

    def test_shortened_read_context_preserves_usable_continuation(self):
        agent = Agent(ROOT, self.store, self.settings)
        session = self.store.create('Read a large file', 'demo', 'scripted-demo')
        workspace = Workspace(Path(session['workspace']))
        text = 'é🙂\r\n' * 3000
        workspace.execute('write_file', {'path': 'large.txt', 'content': text})
        result = workspace.execute('read_file', {'path': 'large.txt', 'length': 12000})
        session['messages'] = [
            {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'large.txt'}}})},
            {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': result})}]
        config = {**self.settings.values, 'provider': 'ollama', 'context_tokens': 2048, 'response_tokens': 512}
        shortened = json.loads(agent.messages(session, config)[-1]['content'].split('\n', 1)[1])['result']
        self.assertTrue(shortened['context_shortened'])
        self.assertFalse(shortened['eof'])
        self.assertEqual(shortened['next_offset'], len(shortened['content'].encode('utf-8')))
        following = workspace.execute('read_file', {'path': 'large.txt', 'offset': shortened['next_offset'], 'length': 10})
        combined = shortened['content'] + following['content']
        self.assertEqual(combined, text[:len(combined)])
        self.assertEqual(json.loads(session['messages'][-1]['content'].split('\n', 1)[1])['result'], result)
        agent.close()


class FakeModelServer:
    def __init__(self, cut_short=False, hosted=False, native=False):
        self.payloads = []; parent = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                parent.payloads.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
                content = json.dumps({'message': 'Ready', 'status': 'completed'})
                calls = [{'function': {'name': 'write_file', 'arguments': {'path': 'sample.txt', 'content': 'sample'}}}]
                if hosted:
                    message = {'content': '' if native else content}
                    if native:
                        message['tool_calls'] = calls
                    self.wfile.write(json.dumps({'choices': [{'message': message, 'finish_reason': 'length' if cut_short else 'tool_calls' if native else 'stop'}]}).encode())
                else:
                    message = {'content': '' if native else content}
                    if native:
                        message['tool_calls'] = calls
                    self.wfile.write((json.dumps({'message': message, 'done': False}) + '\n').encode())
                    if not cut_short:
                        self.wfile.write((json.dumps({'message': {'content': ''}, 'done': True, 'done_reason': 'stop'}) + '\n').encode())
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.url = 'http://127.0.0.1:' + str(self.server.server_port)
    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()


class ProviderTests(unittest.TestCase):
    def run_client(self, server, hosted=False):
        config = dict(__import__('autoproteus.config', fromlist=['DEFAULTS']).DEFAULTS)
        config.update(provider='hosted' if hosted else 'ollama', base_url=server.url, protocol='json')
        return ModelClient(config).complete([{'role': 'user', 'content': 'test'}], threading.Event())

    def test_complete_ollama_stream_and_generation_budget(self):
        server = FakeModelServer()
        try:
            answer = self.run_client(server)
            self.assertEqual(parse_action(answer['content'])['status'], 'completed')
            self.assertEqual(server.payloads[0]['options']['num_predict'], 2048)
        finally: server.close()

    def test_incomplete_ollama_stream_is_discarded(self):
        server = FakeModelServer(cut_short=True)
        try:
            with self.assertRaises(ProviderError) as result: self.run_client(server)
            self.assertTrue(result.exception.response['incomplete'])
            self.assertIn('Ready', result.exception.response['raw_content'])
        finally: server.close()

    def test_hosted_response_and_cutoff_are_distinguished(self):
        for cut_short in (False, True):
            server = FakeModelServer(cut_short=cut_short, hosted=True)
            try:
                if cut_short:
                    with self.assertRaises(ProviderError): self.run_client(server, hosted=True)
                else:
                    self.assertEqual(parse_action(self.run_client(server, hosted=True)['content'])['status'], 'completed')
                self.assertEqual(server.payloads[0]['max_tokens'], 2048)
            finally: server.close()

    def test_native_calls_are_normalized_for_both_adapters(self):
        for hosted in (False, True):
            server = FakeModelServer(hosted=hosted, native=True)
            try:
                config = dict(__import__('autoproteus.config', fromlist=['DEFAULTS']).DEFAULTS)
                config.update(provider='hosted' if hosted else 'ollama', base_url=server.url)
                response = ModelClient(config).complete([{'role':'user','content':'Create sample.txt'}], threading.Event())
                decision = parse_action(response['content'])
                self.assertEqual(decision['action']['arguments']['path'], 'sample.txt')
                self.assertTrue(server.payloads[0]['tools'])
                self.assertNotIn('format', server.payloads[0])
            finally: server.close()

    def test_tool_history_has_matching_ids_and_orphans_remain_context(self):
        messages = [{'role':'assistant','content':json.dumps({'message':'Writing','action':{'tool':'write_file','arguments':{'path':'x','content':'hi'}}})},
                    {'role':'user','content':'ACTION RESULT\n' + json.dumps({'tool':'write_file','ok':True,'result':{'written':True}})}]
        wire = wire_messages(messages, False)
        self.assertEqual(wire[0]['tool_calls'][0]['id'], wire[1]['tool_call_id'])
        self.assertEqual(wire[1]['role'], 'tool')
        self.assertEqual(wire_messages(messages[1:], False)[0]['role'], 'user')

    def test_multiple_calls_are_ordered_and_plain_text_is_not_completion(self):
        call = {'function':{'name':'write_file','arguments':{'path':'x','content':'hi'}}}
        normalized = json.loads(normalize_tool_response('', [call, call]))
        self.assertEqual(len(normalized['actions']), 2)
        finish = {'function':{'name':'finish','arguments':{'message':'Done','status':'completed'}}}
        normalized = json.loads(normalize_tool_response('', [call, finish]))
        self.assertEqual(len(normalized['actions']), 1)
        self.assertTrue(normalized['deferred_finish'])
        for prose in ('All done.', 'Which filename?', ''):
            with self.subTest(prose=prose), self.assertRaisesRegex(ValueError, 'Call finish'):
                normalize_tool_response(prose, [])
            response = model_response(prose, [], True)
            self.assertEqual(response['raw_content'], prose)
            self.assertIn('Call finish', response['normalization_error'])
        decision = parse_action(normalize_tool_response('', [{'function': {'name': 'finish',
            'arguments': {'message': 'Which filename?', 'status': 'needs_input'}}}]))
        self.assertEqual(decision, {'message': 'Which filename?', 'status': 'needs_input'})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.guest_marker = patch.dict(os.environ, {'AUTOPROTEUS_GUEST': '1'})
        self.guest_marker.start()
        self.temporary = temporary_directory()
        self.app = Application(ROOT, data=Path(self.temporary.name))
        self.server = make_server(self.app, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
    def tearDown(self):
        self.app.close(); self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temporary.cleanup()
        self.guest_marker.stop()
    def request(self, path, data=None, token=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if token: headers['X-AutoProteus-Token'] = self.app.token
        if origin: headers['Origin'] = origin
        return urllib.request.urlopen(urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=5)
    def test_token_and_origin_checks(self):
        for kwargs in ({'token': False}, {'origin': 'https://another-site.example'}):
            with self.assertRaises(urllib.error.HTTPError) as result:
                self.request('/api/state', **kwargs)
            self.assertEqual(result.exception.code, 403)
    def test_failed_connection_keeps_working_settings_and_key(self):
        self.app.settings.update({'provider':'demo', 'model':'scripted-demo', 'configured':True})
        previous = self.app.settings.public()
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/connect', {'provider':'hosted', 'base_url':'https://bad.example', 'model':'', 'api_key':'do-not-save'})
        self.assertEqual(self.app.settings.public(), previous)
        self.assertFalse((self.app.data / 'credential.bin').exists())
    def test_hosted_connection_probes_json_and_keeps_native_preference(self):
        provider = FakeModelServer(hosted=True)
        try:
            with self.request('/api/connect', {'provider': 'hosted', 'base_url': provider.url,
                                               'model': 'fake-model', 'protocol': 'native', 'json_mode': True}) as response:
                self.assertTrue(json.load(response)['configured'])
            self.assertEqual(self.app.settings.values['protocol'], 'native')
            self.assertNotIn('tools', provider.payloads[0])
            self.assertNotIn('response_format', provider.payloads[0])
        finally:
            provider.close()
    def test_demo_session_api_file_and_export(self):
        with self.request('/api/connect', {'provider': 'demo', 'model': 'scripted-demo'}) as response:
            self.assertTrue(json.load(response)['configured'])
        with self.request('/api/start', {'task': 'Show the demo'}) as response:
            session_id = json.load(response)['id']
        session = self.app.store.get(session_id)
        self.assertEqual(wait_session(self.app.agent, session), 'completed')
        with self.request('/api/file?id=' + session_id + '&path=welcome.md') as response:
            self.assertIn('Hello from AutoProteus', json.load(response)['content'])
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/file?id=' + session_id + '&path=../session.json')
        with self.request('/api/export?id=' + session_id) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
            self.assertEqual(set(archive.namelist()), {'session.json', 'events.jsonl'})


if __name__ == '__main__':
    unittest.main()
