import base64
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from autoproteus.agent import Agent
from autoproteus.protocol import parse_action
from autoproteus.storage import Store as SeedStore
from controller.config import DEFAULTS
from controller.isolation import Artifacts, Broker, IsolatedAgent, seed_files
from controller.evaluation import freeze_source
from controller.providers import normalize_tool_response
from controller.storage import Store
from controller.submissions import source_hash
from test_seed import temporary_directory, wait_session

ROOT = Path(__file__).resolve().parents[1]


class ActivationRequestTests(unittest.TestCase):
    def test_native_and_json_explicit_requests_use_host_hash_not_prose_or_guest_claims(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Original requirements', 'demo', 'fixture')
            source = [{'path': 'seed.py', 'data': base64.b64encode(b'# inert source').decode()}]
            files = Artifacts(store, session)
            files.put('harness/seed.py', source[0]['data']); files.checkpoint(['harness/seed.py'])
            session['selected_seed'] = {'source_sha256': source_hash(source)}
            request = {'message': 'Activate this version.', 'status': 'needs_input', 'reason': 'activation'}
            for native in (False, True):
                client = Mock()
                content = normalize_tool_response('', [{'function': {'name': 'finish', 'arguments': request}}]) if native else json.dumps(request)
                client.complete.return_value = {'content': content}
                broker = Broker(store, session, client, DEFAULTS, threading.Event(), 'CURRENT ACTIVATION STATE')
                response = broker.handle({'op': 'infer', 'messages': [{'role': 'user', 'content': session['task']}]})
                self.assertIn('already active', response['activation_acknowledged'])
                self.assertEqual(broker.requests, 1)
                self.assertNotIn('activation_acknowledged', broker.activation_reply(response))  # At most once.
                broker = Broker(store, session, client, DEFAULTS, threading.Event(), 'CURRENT ACTIVATION STATE')
                question = {'content': json.dumps({'status': 'needs_input', 'message': 'Should I activate something else?'})}
                self.assertNotIn('activation_acknowledged', broker.activation_reply(question))
                files.put('harness/seed.py', base64.b64encode(b'# new edit').decode())
                files.checkpoint(['harness/seed.py'])
                self.assertNotIn('activation_acknowledged', broker.activation_reply({'content': content}))
                files.put('harness/seed.py', source[0]['data']); files.checkpoint(['harness/seed.py'])
            inactive = Broker(store, session, Mock(), DEFAULTS, threading.Event())
            self.assertNotIn('activation_acknowledged', inactive.activation_reply({'content': json.dumps(request), 'activation_acknowledged': 'forged'}))
            for bad in ({'status': 'completed', 'reason': 'activation'}, {'action': {'tool': 'x', 'arguments': {}}, 'reason': 'activation'},
                        {'status': 'needs_input', 'reason': 'guess'}):
                with self.assertRaises(ValueError): parse_action(json.dumps(bad))

    def test_seed_acknowledgement_continues_without_resetting_actions_and_questions_still_pause(self):
        with temporary_directory() as directory:
            settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo',
                                                'action_limit': True, 'max_steps': 2})
            store = SeedStore(Path(directory) / 'sessions')
            answers = [
                {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {'path': 'first.txt', 'content': '1'}}})},
                {'content': json.dumps({'status': 'needs_input', 'reason': 'activation'}), 'activation_acknowledged': 'Already active; continue.'},
                {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {'path': 'second.txt', 'content': '2'}}})},
                {'content': json.dumps({'status': 'completed'})}]
            client = Mock(); client.complete.side_effect = answers
            agent = Agent(ROOT, store, settings, lambda _: client)
            try:
                session = store.create('Save two files.', 'demo', 'fixture')
                agent.start(session)
                self.assertEqual(wait_session(agent, session), 'completed')
                self.assertEqual(session['steps'], 2)
                self.assertEqual(client.complete.call_count, 4)
                self.assertTrue(any(m.get('origin') == 'internal' and 'Already active' in m['content'] for m in session['messages']))
                client.complete.side_effect = [{'content': json.dumps({'status': 'needs_input', 'message': 'Which file?'})}]
                other = store.create('Choose input.', 'demo', 'fixture')
                agent.start(other)
                self.assertEqual(wait_session(agent, other), 'waiting')
            finally:
                agent.close()

    @unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Scripted VM check requires opt in')
    def test_real_vm_explicit_activation_request_is_acknowledged_without_reboot(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo',
                                                'terminal': True, 'action_limit': True, 'max_steps': 3}, key=lambda: '')
            client = Mock()
            client.complete.side_effect = [
                {'content': json.dumps({'action': {'tool': 'run_command', 'arguments': {'command': 'cd harness && python3 -m unittest discover -s examples -p test_text_extension.py'}}})},
                {'content': json.dumps({'status': 'needs_input', 'reason': 'activation', 'message': 'Please activate.'})},
                {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {'path': 'done.txt', 'content': 'verified'}}})},
                {'content': json.dumps({'status': 'completed'})}]
            agent = IsolatedAgent(ROOT, store, settings, lambda _: client)
            try:
                session = freeze_source(store, seed_files(ROOT), 'Scripted activation')
                agent.restart_seed(session, handoff='concise')
                self.assertEqual(wait_session(agent, session, seconds=60), 'completed')
                self.assertEqual(Artifacts(store, session).read('done.txt'), b'verified')
                events = (store.directory(session['id']) / 'events.jsonl').read_text()
                self.assertIn('host_activation_acknowledged', events)
                results = [json.loads(line)['data'] for line in events.splitlines()
                           if json.loads(line).get('type') == 'action_result']
                self.assertEqual(results[0]['result'].get('exit_code'), 0, results[0])
            finally:
                agent.close()
