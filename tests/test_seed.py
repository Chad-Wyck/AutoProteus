import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from autoproteus.agent import Agent, parse_action
from types import SimpleNamespace
from autoproteus.providers import TOOL_SPECS, tool_definitions
from autoproteus.storage import Store
from autoproteus.tools import Cancelled, Workspace

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP = Path(os.environ.get('AUTOPROTEUS_TEST_ROOT', str(ROOT / '.data/test-tmp')))


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
    def test_edit_conflict_locations_count_overlaps_and_preserve_bytes(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            path = Path(directory) / 'source.txt'
            raw = '猫\r\naaa\r\naaa'.encode('utf-8')
            path.write_bytes(raw)
            with self.assertRaises(ValueError) as failure:
                workspace.execute('edit_file', {'path': 'source.txt', 'old_text': 'aa', 'new_text': 'x'})
            details = failure.exception.details
            self.assertEqual(details['matches'], 4)
            self.assertEqual([item['start'] for item in details['locations']], [3, 4, 8])
            self.assertEqual(details['locations'][0]['line'], 2)
            self.assertEqual(path.read_bytes(), raw)
            with self.assertRaises(ValueError) as failure:
                workspace.execute('edit_file', {'path': 'source.txt', 'old_text': '猫\naaa', 'new_text': 'x'})
            self.assertEqual(failure.exception.details['matches'], 0)
            self.assertIn('line endings', failure.exception.details['hint'])
            self.assertEqual(path.read_bytes(), raw)
            path.write_text('a' * 1000, encoding='utf-8')
            with self.assertRaises(ValueError) as failure:
                workspace.execute('edit_file', {'path': 'source.txt', 'old_text': 'aa', 'new_text': 'x'})
            self.assertEqual(failure.exception.details['matches'], 50)
            self.assertTrue(failure.exception.details['matches_truncated'])
            self.assertEqual(len(failure.exception.details['locations']), 3)
            self.assertEqual(path.read_text(encoding='utf-8'), 'a' * 1000)

    def test_delete_recreate_identical_file_and_reject_directories(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            for _ in range(2):
                workspace.execute('write_file', {'path': 'file.txt', 'content': 'same'})
                self.assertTrue(workspace.execute('delete_file', {'path': 'file.txt'})['deleted'])
                self.assertFalse((Path(directory) / 'file.txt').exists())
            for value in ('.', '../outside', 'missing.txt'):
                with self.assertRaises((ValueError, OSError)):
                    workspace.execute('delete_file', {'path': value})

    def test_literal_search_returns_unicode_line_numbers_without_running_regex(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            workspace.execute('write_file', {'path': 'source/code.py', 'content': 'first\r\nneedle.* café\nlast\n'})
            result = workspace.execute('search_files', {'query': 'needle.*', 'path': 'source'})
            self.assertEqual(result['matches'], [{'path': 'source/code.py', 'line': 2, 'start': 7, 'snippet': 'needle.* café'}])
            self.assertFalse(result['incomplete'])
            self.assertEqual(workspace.execute('search_files', {'query': 'needle.+'})['matches'], [])
            with self.assertRaises(ValueError): workspace.execute('search_files', {'query': 'x', 'path': '../outside'})

    def test_search_bounds_results_skips_binary_and_checks_cancellation(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            (Path(directory) / 'binary').write_bytes(b'\xff')
            workspace.execute('write_file', {'path': 'many.txt', 'content': 'find me\n' * 60})
            result = workspace.execute('search_files', {'query': 'find'})
            self.assertEqual(len(result['matches']), 30)
            self.assertTrue(result['incomplete'])
            for query in ('', 'x' * 201, 'a\nb'):
                with self.assertRaises(ValueError): workspace.execute('search_files', {'query': query})
            workspace.cancel.set()
            with self.assertRaises(Cancelled): workspace.execute('search_files', {'query': 'find'})
    def test_traversal_and_absolute_paths_are_rejected(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            for path in ('../outside.txt', str(Path(directory).parent / 'outside.txt')):
                for tool, arguments in [('write_file', {'content': 'bad'}), ('read_file', {}), ('read_section', {}),
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

    def test_whole_file_returns_complete_text_or_rejects_oversize(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            for content in ('', '\ufeffHello é🙂\r\n世界\n', '🙂' * 12000):
                workspace.execute('write_file', {'path': 'text.txt', 'content': content})
                result = workspace.execute('read_file', {'path': 'text.txt'})
                self.assertEqual(result['content'], content)
                self.assertTrue(result['eof'])
                self.assertEqual(result['next_start'], len(content))
            workspace.execute('write_file', {'path': 'text.txt', 'content': 'x' * 12001})
            with self.assertRaisesRegex(ValueError, 'read_section'):
                workspace.execute('read_file', {'path': 'text.txt'})
            for arguments in ({'offset': 1}, {'start': 1}, {'length': 2}):
                with self.subTest(arguments=arguments), self.assertRaisesRegex(ValueError, 'read_section'):
                    workspace.execute('read_file', {'path': 'text.txt', **arguments})

    def test_section_continuation_preserves_unicode_and_line_endings(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            content = '\ufeffHello é🙂\r\n世界\n'
            workspace.execute('write_file', {'path': 'text.txt', 'content': content})
            self.assertEqual((Path(directory) / 'text.txt').read_bytes(), content.encode('utf-8'))
            start, chunks = 0, []
            for _ in range(len(content)):
                result = workspace.execute('read_section', {'path': 'text.txt', 'start': start, 'length': 2})
                self.assertLessEqual(len(result['content']), 2)
                self.assertEqual(result['next_start'], start + len(result['content']))
                chunks.append(result['content'])
                start = result['next_start']
                if result['eof']:
                    break
            self.assertTrue(result['eof'])
            self.assertEqual(''.join(chunks), content)
            self.assertEqual(start, len(content))
            self.assertEqual(workspace.execute('read_section', {'path': 'text.txt', 'start': start})['content'], '')

    def test_section_uses_character_positions_and_rejects_invalid_ranges(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            (Path(directory) / 'text.txt').write_bytes('é'.encode('utf-8') + b'x' * 13000)
            self.assertEqual(len(workspace.execute('read_section', {'path': 'text.txt'})['content']), 1000)
            self.assertEqual(workspace.execute('read_section', {'path': 'text.txt', 'start': 1, 'length': 2})['content'], 'xx')
            for arguments in ({'start': -1}, {'start': True}, {'offset': 1}, {'start': 0.5},
                              {'length': 0}, {'length': True}, {'length': 12001}, {'length': '10'}):
                with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                    workspace.execute('read_section', {'path': 'text.txt', **arguments})

    def test_section_skips_large_unicode_prefix_and_handles_past_eof(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            content = 'é🙂\r\n' * 10000
            workspace.execute('write_file', {'path': 'large.txt', 'content': content})
            result = workspace.execute('read_section', {'path': 'large.txt', 'start': 12003, 'length': 17})
            self.assertEqual(result['content'], content[12003:12020])
            self.assertEqual(result['next_start'], 12020)
            self.assertFalse(result['eof'])
            result = workspace.execute('read_section', {'path': 'large.txt', 'start': 10**12})
            self.assertEqual(result['content'], '')
            self.assertTrue(result['eof'])

    def test_both_read_tools_reject_invalid_utf8(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            (Path(directory) / 'binary.txt').write_bytes(b'\xff\n')
            for tool in ('read_file', 'read_section'):
                with self.subTest(tool=tool), self.assertRaisesRegex(ValueError, 'UTF-8'):
                    workspace.execute(tool, {'path': 'binary.txt'})

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
            workspace = Workspace(Path(directory), terminal=True, timeout=15)
            command = "Write-Output 'terminal-ok'" if os.name == 'nt' else "printf terminal-ok"
            result = workspace.execute('run_command', {'command': command})
            self.assertEqual(result['exit_code'], 0)
            self.assertIn('terminal-ok', result['output'])
            workspace.timeout = 1
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


class Settings:
    def __init__(self, directory):
        self.values = {'configured':True, 'provider':'demo', 'model':'scripted-demo',
                       'context_tokens':8192, 'response_tokens':2048, 'max_steps':32,
                       'terminal':False, 'command_timeout':60, 'protocol':'native'}
    def update(self, values): self.values.update(values)
    def key(self): return ''


class DemoClient:
    def complete(self, messages, cancel):
        if cancel.wait(0.02): raise Cancelled()
        index = sum(m['role']=='user' and m['content'].startswith('ACTION RESULT') for m in messages)
        actions = [
            {'tool':'write_file','arguments':{'path':'todo.txt','content':'[ ] Create welcome.md\n[ ] Verify it\n'}},
            {'tool':'write_file','arguments':{'path':'welcome.md','content':'Hello from AutoProteus\n'}},
            {'tool':'read_file','arguments':{'path':'welcome.md'}},
            {'tool':'write_file','arguments':{'path':'todo.txt','content':'[x] Create welcome.md\n[x] Verify it\n'}}]
        return {'content':json.dumps({'message':'Fixture', 'action':actions[index]} if index<len(actions)
                                    else {'message':'Verified', 'status':'completed'})}


def normalize_tool_response(content, calls):
    decisions=[]
    for call in calls:
        fn=call['function']; args=fn['arguments']
        decisions.append({'message':args['message'], 'status':args['status']} if fn['name']=='finish'
                         else {'message':content, 'action':{'tool':fn['name'], 'arguments':args}})
    if len(decisions)==1: return json.dumps(decisions[0])
    return json.dumps({'message':content, 'actions':[d['action'] for d in decisions if 'action' in d],
                       'deferred_finish':any('status' in d for d in decisions)})


def model_response(content, calls, native):
    if not calls: return {'content':'', 'normalization_error':'Call finish with explicit completion'}
    return {'content':normalize_tool_response(content,calls)}


class AgentTests(unittest.TestCase):
    def test_activation_context_uses_runtime_budget_and_preserves_the_prompt_prefix_and_user(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: None)
        try:
            session = self.store.create('Keep this full original requirement.', 'ollama', 'fixture')
            config = {**self.settings.values, 'provider':'ollama'}
            initial = agent.messages(session, config)
            phase = 'CURRENT ACTIVATION STATE\nThe running version is active.'
            active = agent.messages(session, {**config,'activation_context':phase})
            self.assertEqual(active[0], initial[0])
            self.assertEqual(active[-1]['content'], phase)
            bounded = agent.messages(session, {**config,'activation_context':'x' * 1000000})
            self.assertIn(session['task'], [item['content'] for item in bounded])
            self.assertNotIn('x' * 1000000, [item['content'] for item in bounded])
        finally:
            agent.close()

    def test_cutoff_retries_a_smaller_action_without_executing_partial_content(self):
        for protocol in ('native', 'json'):
            with self.subTest(protocol=protocol):
                self.settings.values.update(provider='ollama', protocol=protocol)
                prompts = []
                class Client:
                    def complete(client, messages, cancel):
                        prompts.append(messages)
                        if len(prompts) == 1:
                            return {'provider_error': 'cutoff', 'content': json.dumps({'action': {
                                'tool': 'write_file', 'arguments': {'path': 'partial.txt', 'content': 'unsafe'}}})}
                        return {'content': json.dumps({'status': 'completed'})}
                agent = Agent(ROOT, self.store, self.settings, lambda _: Client())
                try:
                    session = self.store.create('Handle a cut-off response.', 'ollama', 'offline-test')
                    agent.start(session)
                    self.assertEqual(wait_session(agent, session), 'completed')
                    self.assertEqual(session['steps'], 0)
                    self.assertFalse((Path(session['workspace']) / 'partial.txt').exists())
                    self.assertEqual(prompts[0][0], prompts[1][0])
                    self.assertIn('smaller action or patch', prompts[1][-1]['content'])
                    self.assertEqual(session['messages'][-2]['origin'], 'internal')
                finally:
                    agent.close()

    def test_repeated_cutoffs_share_the_bounded_response_repair_allowance(self):
        class Client:
            calls = 0
            def complete(client, *args):
                client.calls += 1
                return {'provider_error': 'cutoff', 'content': ''}
        client = Client()
        agent = Agent(ROOT, self.store, self.settings, lambda _: client)
        try:
            session = self.store.create('Stop repeated incomplete output.', 'demo', 'offline-test')
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'error')
            self.assertEqual(client.calls, 3)
            self.assertEqual(session['steps'], 0)
        finally:
            agent.close()

    def test_human_correction_survives_internal_notices_and_legacy_journals(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        notices = ['Your response was not accepted: invalid format. No action was executed.',
                   'Resume this task. Inspect current files and todo.txt before continuing.',
                   'Your finish call was deferred until you inspect the tool results above.']
        try:
            for protocol in ('native', 'json'):
                for legacy in (False, True):
                    for notice in notices:
                        with self.subTest(protocol=protocol, legacy=legacy, notice=notice):
                            session = self.store.create('Add a capability without removing existing behavior.', 'ollama', 'offline-test')
                            correction = 'Your response was not accepted: preserve the original Unicode and CRLF behavior.'
                            self.store.feed(session, 'user', correction)
                            session['messages'] = [
                                {'role': 'user', 'content': session['task']},
                                {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'old.txt'}}})},
                                {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': {'content': 'x' * 30000}})},
                                {'role': 'user', 'content': correction, **({} if legacy else {'origin': 'human'})},
                                {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'current.txt'}}})},
                                {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': {'content': 'current source'}})},
                                {'role': 'user', 'content': notice, **({} if legacy else {'origin': 'internal'})}]
                            original_history = [dict(item) for item in session['messages']]
                            config = {**self.settings.values, 'provider': 'ollama', 'protocol': protocol,
                                      'context_tokens': 8192, 'response_tokens': 2048}
                            messages = agent.messages(session, config)
                            self.assertIn({'role': 'user', 'content': correction}, messages)
                            self.assertEqual(sum(item['content'] == session['task'] for item in messages), 1)
                            self.assertTrue(all(set(item) == {'role', 'content'} for item in messages))
                            self.assertEqual(session['messages'], original_history)
        finally:
            agent.close()

    def test_start_resume_and_format_repair_record_explicit_message_origins(self):
        class Client:
            calls = 0
            def complete(client, *args):
                client.calls += 1
                return {'content': 'invalid JSON' if client.calls == 1 else json.dumps({'status': 'needs_input'})}
        client = Client()
        agent = Agent(ROOT, self.store, self.settings, lambda _: client)
        try:
            session = self.store.create('Track human inputs.', 'demo', 'fixture')
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'waiting')
            self.assertEqual(session['messages'][0]['origin'], 'human')
            repair = next(item for item in session['messages'] if item['content'].startswith('Your response was not accepted:'))
            self.assertEqual(repair['origin'], 'internal')
            correction = 'Resume this task. Inspect current files, but preserve my constraint.'
            agent.start(session, correction)
            self.assertEqual(wait_session(agent, session), 'waiting')
            self.assertEqual(next(item for item in session['messages'] if item['content'] == correction)['origin'], 'human')
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'waiting')
            resume = next(item for item in reversed(session['messages']) if item.get('origin') == 'internal')
            self.assertTrue(resume['content'].startswith('Resume this task.'))
        finally:
            agent.close()

    def test_finish_after_last_action_is_free_with_stable_opening_in_both_protocols(self):
        for protocol in ('native', 'json'):
            with self.subTest(protocol=protocol):
                self.settings.update({'provider': 'ollama', 'protocol': protocol, 'max_steps': 1})
                prompts = []
                class Client:
                    def complete(client, messages, cancel):
                        prompts.append(messages)
                        decision = ({'action': {'tool': 'write_file', 'arguments': {'path': 'last.txt', 'content': 'saved'}}}
                                    if len(prompts) == 1 else {'status': 'completed'})
                        return {'content': json.dumps(decision)}
                agent = Agent(ROOT, self.store, self.settings, lambda _: Client())
                try:
                    session = self.store.create('Use the last action', 'ollama', 'offline-test')
                    agent.start(session)
                    self.assertEqual(wait_session(agent, session), 'completed')
                    self.assertEqual(session['steps'], 1)
                    self.assertEqual(prompts[0][0], prompts[1][0])
                    self.assertFalse(any('allowance is exhausted' in item['content'] for item in prompts[0]))
                    self.assertIn('allowance is exhausted', prompts[1][-1]['content'])
                    self.assertIn('Stop reading when you have enough context', prompts[0][0]['content'])
                finally:
                    agent.close()

    def test_exhausted_budget_blocks_tools_and_resume_resets_counter(self):
        self.settings.update({'max_steps': 1})
        prompts = []
        class Client:
            def complete(client, messages, cancel):
                prompts.append(messages[0]['content'])
                decision = ({'status': 'completed'} if len(prompts) == 4 else
                            {'action': {'tool': 'write_file', 'arguments': {'path': f'call-{len(prompts)}.txt', 'content': 'saved'}}})
                return {'content': json.dumps(decision)}
        agent = Agent(ROOT, self.store, self.settings, lambda _: Client())
        try:
            session = self.store.create('Save and resume', 'demo', 'offline-test')
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'paused')
            workspace = Path(session['workspace'])
            self.assertTrue((workspace / 'call-1.txt').exists())
            self.assertFalse((workspace / 'call-2.txt').exists())
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'completed')
            self.assertEqual(session['steps'], 2)
            self.assertEqual(prompts[0], prompts[2])
            self.assertNotIn('tool actions used', prompts[2])
            self.assertTrue((workspace / 'call-3.txt').exists())
        finally:
            agent.close()

    def test_native_batch_cannot_exceed_budget_and_can_finish_after_inspection(self):
        self.settings.update({'max_steps': 2})
        class Client:
            calls = 0
            def complete(client, messages, cancel):
                client.calls += 1
                if client.calls == 1:
                    return {'content': json.dumps({'actions': [
                        {'tool': 'write_file', 'arguments': {'path': f'batch-{i}.txt', 'content': 'saved'}} for i in range(3)]})}
                self.assertIn('allowance is exhausted', messages[-1]['content'])
                self.assertNotIn('allowance is exhausted', messages[0]['content'])
                return {'content': json.dumps({'status': 'completed'})}
        agent = Agent(ROOT, self.store, self.settings, lambda _: Client())
        try:
            session = self.store.create('Bound a native batch', 'demo', 'offline-test')
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'completed')
            self.assertEqual(session['steps'], 2)
            self.assertFalse((Path(session['workspace']) / 'batch-2.txt').exists())
        finally:
            agent.close()

    def test_edit_failure_details_reach_model_and_allow_a_corrected_edit(self):
        class Client:
            calls = 0
            def complete(client, messages, cancel):
                client.calls += 1
                if client.calls == 1:
                    decision = {'action': {'tool': 'edit_file', 'arguments': {'path': 'source.txt', 'old_text': 'x', 'new_text': 'y'}}}
                elif client.calls == 2:
                    result = json.loads(messages[-1]['content'].split('\n', 1)[1])
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['result']['matches'], 2)
                    self.assertEqual(result['result']['locations'][1]['start'], 4)
                    decision = {'action': {'tool': 'edit_file', 'arguments': {'path': 'source.txt', 'old_text': 'x = x', 'new_text': 'x = 1'}}}
                else:
                    decision = {'status': 'completed'}
                return {'content': json.dumps(decision)}
        agent = Agent(ROOT, self.store, self.settings, lambda _: Client())
        try:
            session = self.store.create('Repair the exact match', 'demo', 'offline-test')
            path = Path(session['workspace']) / 'source.txt'; path.write_bytes(b'x = x\r\n')
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'completed')
            self.assertEqual(path.read_bytes(), b'x = 1\r\n')
        finally:
            agent.close()

    def test_different_tiny_reads_receive_a_progress_hint_without_forcing_a_stop(self):
        class Client:
            calls = 0
            def complete(client, messages, cancel):
                client.calls += 1
                if client.calls <= 8:
                    decision = {'action': {'tool': 'read_section', 'arguments': {'path': 'source.txt', 'start': client.calls - 1, 'length': 1}}}
                else:
                    result = json.loads(messages[-1]['content'].split('\n', 1)[1])['result']
                    self.assertIn('8 consecutive source reads', result['progress_hint'])
                    decision = {'status': 'completed'}
                return {'content': json.dumps(decision)}
        agent = Agent(ROOT, self.store, self.settings, lambda _: Client())
        try:
            session = self.store.create('Navigate efficiently', 'demo', 'offline-test')
            (Path(session['workspace']) / 'source.txt').write_text('abcdefgh')
            agent.start(session)
            self.assertEqual(wait_session(agent, session), 'completed')
        finally:
            agent.close()

    def test_complete_input_budget_rejects_oversize_without_shortening_user_text(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        session = self.store.create('x' * 12000, 'ollama', 'offline-test')
        session['messages'] = [{'role': 'user', 'content': session['task']}]
        with self.assertRaisesRegex(ValueError, 'context'):
            agent.messages(session, {**self.settings.values, 'provider': 'ollama', 'context_tokens': 2048, 'response_tokens': 512})
        self.assertEqual(session['task'], 'x' * 12000)
        config = {**self.settings.values, 'provider': 'ollama', 'context_tokens': 16384}
        messages = agent.messages(session, config)
        self.assertEqual(sum(item['content'] == session['task'] for item in messages), 1)
        self.assertNotIn(session['task'], messages[0]['content'])
        agent.close()

    def test_todo_and_exhaustion_notice_follow_history_without_changing_opening(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        try:
            session = self.store.create('Keep my task intact.', 'ollama', 'offline-test')
            session['messages'] = [{'role': 'user', 'content': session['task'], 'origin': 'human'}]
            config = {**self.settings.values, 'provider': 'ollama', 'protocol': 'native',
                      'context_tokens': 8192, 'response_tokens': 2048, 'max_steps': 2}
            first = agent.messages(session, config, 0)
            todo = Path(session['workspace']) / 'todo.txt'
            todo.write_text('[ ] Verify the edit', encoding='utf-8')
            later = agent.messages(session, config, 1)
            todo.write_text('[x] Verify the edit', encoding='utf-8')
            final = agent.messages(session, config, 2)
            self.assertEqual(first, later[:len(first)])
            self.assertEqual(first, final[:len(first)])
            self.assertIn('[ ] Verify the edit', later[-1]['content'])
            self.assertIn('[x] Verify the edit', final[-2]['content'])
            self.assertIn('allowance is exhausted', final[-1]['content'])
            self.assertNotIn('Current todo.txt:', first[0]['content'])
            limit = (config['context_tokens'] - config['response_tokens'] - 128) * 2
            self.assertLessEqual(len(json.dumps({'messages': final, 'tools': tool_definitions(config['terminal'])}, ensure_ascii=False).encode('utf-8')), limit)
            self.assertEqual(len(session['messages']), 1)
        finally:
            agent.close()

    def test_exhaustion_notice_cannot_displace_a_full_user_request(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        try:
            for protocol in ('native', 'json'):
                with self.subTest(protocol=protocol):
                    session = self.store.create('Preserve the complete request.', 'ollama', 'offline-test')
                    config = {**self.settings.values, 'provider': 'ollama', 'protocol': protocol,
                              'context_tokens': 8192, 'response_tokens': 2048, 'max_steps': 1}
                    schemas = tool_definitions(config['terminal']) if protocol == 'native' else []
                    def size(messages):
                        return len(json.dumps({'messages': messages, 'tools': schemas}, ensure_ascii=False).encode('utf-8'))
                    allowance = (config['context_tokens'] - config['response_tokens'] - 128) * 2
                    session['task'] += 'x' * (allowance - size(agent.messages(session, config)))
                    before = agent.messages(session, config, 0)
                    exhausted = agent.messages(session, config, 1)
                    self.assertEqual(size(before), allowance)
                    self.assertEqual(before, exhausted)
                    self.assertEqual(exhausted[1]['content'], session['task'])
        finally:
            agent.close()

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
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
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
        self.assertEqual(session['steps'], 0)
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
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
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
        self.settings.update({'context_tokens': 4096, 'response_tokens': 512})
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        session = self.store.create('Preserve valid history', 'demo', 'scripted-demo')
        session['messages'] = [
            {'role':'assistant', 'content':json.dumps({'action':{'tool':'write_file','arguments':{'path':'large.txt','content':'a' * 20000}}})},
            {'role':'user', 'content':'ACTION RESULT\n' + json.dumps({'tool':'write_file','ok':True,'result':{'content':'a' * 20000}})}]
        config = {**self.settings.values, 'provider':'ollama'}
        messages = agent.messages(session, config)
        self.assertEqual(messages[-1]['role'], 'user')
        self.assertTrue(json.loads(messages[-1]['content'].split('\n', 1)[1])['result']['context_shortened'])
        agent.close()

    def test_trimming_retains_request_and_recent_tool_pair_without_changing_journal(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        session = self.store.create('Keep this original request.', 'ollama', 'offline-test')
        recent = {'action': {'tool': 'read_file', 'arguments': {'path': 'recent.txt'}}}
        result = 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': {'content': 'recent'}})
        session['messages'] = [
            {'role': 'user', 'content': session['task']},
            {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'old.txt'}}})},
            {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': {'content': 'x' * 20000}})},
            {'role': 'assistant', 'content': json.dumps(recent)},
            {'role': 'user', 'content': result}]
        journal = list(session['messages'])
        for protocol in ('native', 'json'):
            config = {**self.settings.values, 'provider': 'ollama', 'protocol': protocol,
                      'context_tokens': 4096, 'response_tokens': 512}
            messages = agent.messages(session, config)
            self.assertEqual(messages[1], {'role': 'user', 'content': session['task']})
            self.assertEqual(messages[-2:], journal[-2:])
            self.assertEqual(len(messages), 4)
            self.assertEqual(session['messages'], journal)
        agent.close()

    def test_original_request_is_not_duplicated_and_follow_up_remains(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        session = self.store.create('Original request', 'ollama', 'offline-test')
        session['messages'] = [{'role': 'user', 'content': session['task']},
                               {'role': 'user', 'content': 'Please use the newer filename.'}]
        config = {**self.settings.values, 'provider': 'ollama'}
        messages = agent.messages(session, config)
        self.assertEqual(sum(item == session['messages'][0] for item in messages), 1)
        self.assertEqual(messages[-1], session['messages'][-1])
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
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        session = self.store.create('Read a large file', 'demo', 'scripted-demo')
        workspace = Workspace(Path(session['workspace']))
        text = 'é🙂\r\n' * 3000
        workspace.execute('write_file', {'path': 'large.txt', 'content': text})
        result = workspace.execute('read_section', {'path': 'large.txt', 'length': 12000})
        session['messages'] = [
            {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_section', 'arguments': {'path': 'large.txt'}}})},
            {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_section', 'ok': True, 'result': result})}]
        config = {**self.settings.values, 'provider': 'ollama', 'context_tokens': 4096, 'response_tokens': 512}
        shortened = json.loads(agent.messages(session, config)[-1]['content'].split('\n', 1)[1])['result']
        self.assertTrue(shortened['context_shortened'])
        self.assertFalse(shortened['eof'])
        self.assertEqual(shortened['next_start'], len(shortened['content']))
        following = workspace.execute('read_section', {'path': 'large.txt', 'start': shortened['next_start'], 'length': 10})
        combined = shortened['content'] + following['content']
        self.assertEqual(combined, text[:len(combined)])
        self.assertEqual(json.loads(session['messages'][-1]['content'].split('\n', 1)[1])['result'], result)
        agent.close()

    def test_whole_file_context_omission_never_pretends_to_be_a_full_read(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        session = self.store.create('Inspect a complete file', 'demo', 'scripted-demo')
        workspace = Workspace(Path(session['workspace']))
        content = 'é🙂\r\n' * 1500
        workspace.execute('write_file', {'path': 'text.txt', 'content': content})
        result = workspace.execute('read_file', {'path': 'text.txt'})
        session['messages'] = [
            {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'text.txt'}}})},
            {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': result})}]
        config = {**self.settings.values, 'provider': 'ollama', 'context_tokens': 4096, 'response_tokens': 512}
        omitted = json.loads(agent.messages(session, config)[-1]['content'].split('\n', 1)[1])['result']
        self.assertTrue(omitted['content_omitted'])
        self.assertNotIn('content', omitted)
        self.assertNotIn('eof', omitted)
        self.assertIn('read_section', omitted['hint'])
        self.assertEqual(result['content'], content)
        agent.close()

    def test_one_tool_entry_reaches_native_schema_and_json_prompt(self):
        agent = Agent(ROOT, self.store, self.settings, lambda _: DemoClient())
        session = self.store.create('Use the added tool', 'demo', 'scripted-demo')
        spec = ('Count words in a workspace file.', {'path': {'type': 'string'}}, ['path'])
        with patch.dict(TOOL_SPECS, {'word_count': spec}):
            tools = {tool['function']['name']: tool['function'] for tool in tool_definitions()}
            self.assertEqual(tools['word_count']['description'], spec[0])
            self.assertEqual(tools['word_count']['parameters']['required'], ['path'])
            config = {**self.settings.values, 'provider': 'ollama', 'protocol': 'json'}
            prompt = agent.messages(session, config)[0]['content']
            self.assertIn('word_count: ' + spec[0], prompt)
            self.assertNotIn('finish:', prompt)
            self.assertNotIn('run_command:', prompt)
            self.assertIn('run_command:', agent.messages(session, {**config, 'terminal': True})[0]['content'])
        agent.close()



if __name__ == '__main__':
    unittest.main()
