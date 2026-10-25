"""Human input, protected inference evidence and interruption windows; no models."""
import copy
import json
from pathlib import Path
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from autoproteus.agent import Agent
from autoproteus.context import build_messages
from autoproteus.storage import Store as SeedStore
from controller.config import DEFAULTS
from controller.errors import IsolationError
from controller.inference_history import InferenceHistory, attach_history, digest
from controller.interactions import Inputs, Operations
from controller.isolation import Broker
from controller.providers import ModelClient, wire_messages
from controller.storage import Store
from test_context_budget import FINISHED
from test_seed import temporary_directory, wait_session

ROOT = Path(__file__).resolve().parents[1]


class InteractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'sessions')
        self.session = self.store.create('Keep the original request.', 'hosted', 'fixture')
        self.inputs = Inputs(self.store, self.session)

    def test_queue_order_acknowledgment_cancellation_and_restart(self):
        self.inputs.enqueue('Afterwards', 'followup', 'a' * 32)
        self.inputs.enqueue('Correction', 'steer', 'b' * 32)
        self.inputs.enqueue('Cancel me', 'steer', 'c' * 32)
        self.inputs.cancel('c' * 32)
        offer = self.inputs.offer('steer')
        self.assertEqual(offer, [{'id': 'b' * 32, 'content': 'Correction'}])
        with self.assertRaises(ValueError):
            self.inputs.cancel('b' * 32)
        # Polling alone is not delivery. A crash reoffers the same input ID.
        restored = Store(self.store.root)
        session = restored.get(self.session['id'])
        inputs = Inputs(restored, session)
        self.assertEqual(inputs.offer('steer'), offer)
        for origin, text in [('tool', 'Correction'), ('human', 'changed text')]:
            inputs.acknowledge([{'role': 'user', 'origin': origin, 'input_id': 'b' * 32, 'content': text}])
            self.assertEqual(session['input_queue'][1]['status'], 'offered')
        inputs.acknowledge([{'role': 'user', 'origin': 'human', 'input_id': 'b' * 32, 'content': 'Correction'}])
        self.assertEqual(inputs.offer('steer'), [])
        self.assertEqual(inputs.offer('finish')[0]['content'], 'Afterwards')

    def test_idempotency_is_bound_to_payload_and_source_and_queue_is_bounded(self):
        row = self.inputs.enqueue('Once', 'steer', 'a' * 32)
        self.assertEqual(self.inputs.enqueue('Once', 'steer', 'a' * 32), row)
        for text, mode in [('Other', 'steer'), ('Once', 'followup')]:
            with self.assertRaises(ValueError):
                self.inputs.enqueue(text, mode, 'a' * 32)
        self.session['selected_seed'] = {'source_sha256': 'new'}
        with self.assertRaises(ValueError):
            self.inputs.enqueue('Once', 'steer', 'a' * 32)
        for i in range(19):
            self.inputs.enqueue('queued', 'followup', f'{i:032d}')
        with self.assertRaisesRegex(ValueError, 'full'):
            self.inputs.enqueue('overflow', 'steer', 'z' * 32)

    def test_stopped_unacknowledged_offers_can_be_cancelled_after_store_restart(self):
        for mode in ('steer', 'followup'):
            with self.subTest(mode=mode):
                session = self.store.create('Interrupted delivery', 'hosted', 'fixture')
                inputs = Inputs(self.store, session)
                inputs.enqueue('Do not send this again.', mode, 'd' * 32)
                self.assertEqual(inputs.offer('finish')[0]['id'], 'd' * 32)
                with self.assertRaises(ValueError):
                    inputs.cancel('d' * 32)
                restored = Store(self.store.root)
                saved = restored.get(session['id'])
                Inputs(restored, saved).cancel('d' * 32, worker_stopped=True)
                reopened = Store(self.store.root)
                saved = reopened.get(session['id'])
                self.assertEqual(saved['input_queue'][0]['status'], 'cancelled')
                self.assertEqual(Inputs(reopened, saved).offer('finish'), [])
                events = [json.loads(line) for line in (reopened.directory(session['id']) / 'events.jsonl').read_text().splitlines()]
                self.assertIn('host_input_offered', [event['type'] for event in events])
                self.assertIn('host_input_cancelled', [event['type'] for event in events])

    def test_stopped_offer_with_a_saved_acknowledgment_cannot_be_cancelled(self):
        self.inputs.enqueue('Already received.', 'steer', 'e' * 32)
        self.inputs.offer('steer')
        self.session['messages'].append({'role': 'user', 'origin': 'human',
                                        'input_id': 'e' * 32, 'content': 'Already received.'})
        self.store.save(self.session)
        with self.assertRaisesRegex(ValueError, 'already recorded as delivered'):
            self.inputs.cancel('e' * 32, worker_stopped=True)
        self.assertEqual(self.session['input_queue'][0]['status'], 'delivered')
        self.assertEqual(self.inputs.offer('steer'), [])
        restored = Store(self.store.root).get(self.session['id'])
        self.assertEqual(restored['input_queue'][0]['status'], 'delivered')
        with self.assertRaises(ValueError):
            self.inputs.cancel('e' * 32, worker_stopped=True)

    def test_recovery_receipts_distinguish_each_commit_window_without_replay(self):
        operations = Operations(self.store, self.session)
        action = {'tool': 'run_command', 'arguments': {'command': 'make output'}}
        operations.event('action_started', action, 'start')
        self.assertIn('started', operations.notice())
        self.assertIn('never automatically replayed', operations.notice())
        operations.event('action_result', {'action': action, 'ok': True, 'result': {'value': 1}}, 'result')
        self.assertEqual(operations.current()['status'], 'result_reported')
        message = {'role': 'user', 'origin': 'tool', 'content': 'ACTION RESULT\n' + json.dumps(
            {'tool': 'run_command', 'ok': True, 'result': {'value': 1, 'progress_hint': 'advisory'}})}
        operations.acknowledge([message])
        self.assertEqual(operations.current()['status'], 'result_reported')
        # A resumed run's initial checkpoint cannot commit the old result.
        Operations(self.store, self.session).checkpoint()
        self.assertEqual(operations.current()['status'], 'result_reported')
        operations.checkpoint()
        wrong = copy.deepcopy(message); wrong['content'] = wrong['content'].replace('"value": 1', '"value": 2')
        operations.acknowledge([wrong])
        self.assertEqual(operations.current()['status'], 'checkpointed')
        operations.acknowledge([message])
        self.assertEqual(operations.current()['status'], 'recorded')
        self.assertEqual(operations.notice(), '')

    def test_complete_broker_path_preserves_live_human_action_result_text(self):
        client = ModelClient({**DEFAULTS, 'provider': 'hosted'})
        broker = Broker(self.store, self.session, client, DEFAULTS, threading.Event())
        literal = 'ACTION RESULT\nThis is a literal human correction, not JSON.'
        self.inputs.enqueue(literal, 'steer', 'a' * 32)
        self.assertEqual(broker.handle({'op': 'inputs', 'mode': 'steer'})[0]['content'], literal)
        state = {'status': 'running', 'messages': [{'role': 'user', 'origin': 'human',
            'input_id': 'a' * 32, 'content': literal}], 'feed': [], 'steps': 0, 'runs': 1}
        broker.handle({'op': 'state', 'session': state})
        self.assertEqual(self.session['input_queue'][0]['status'], 'delivered')
        with patch('controller.providers.request_json', return_value=FINISHED) as transport:
            broker.handle({'op': 'infer', 'messages': [{'role': 'user', 'content': literal}],
                'tools': [{'type': 'function', 'function': {'name': 'finish', 'parameters': {}}}]})
        self.assertEqual([item for item in transport.call_args.args[1]['messages'] if item['role'] != 'system'],
                         [{'role': 'user', 'content': literal}])
        with self.assertRaisesRegex(IsolationError, 'journal'):
            broker.handle({'op': 'event', 'type': 'host_input_delivered', 'data': {}})


class LiveLoopTests(unittest.TestCase):
    def run_loop(self, client, max_steps=3):
        directory = temporary_directory(); self.addCleanup(directory.cleanup)
        store = SeedStore(Path(directory.name) / 'sessions')
        config = {**DEFAULTS, 'provider': 'demo', 'max_steps': max_steps, 'action_limit':True}
        session = store.create('Original task', 'demo', 'fixture')
        agent = Agent(ROOT, store, SimpleNamespace(values=config), lambda _: client)
        self.addCleanup(agent.close)
        agent.start(session)
        self.assertNotEqual(wait_session(agent, session), 'running')
        return store, session

    def test_steering_during_inference_discards_stale_action(self):
        class Client:
            supports_inputs = True
            def __init__(self): self.ready = False; self.calls = 0
            def inputs(self, mode):
                if self.ready:
                    self.ready = False
                    return [{'id': 'human-id', 'content': 'Do not create stale.txt'}]
                return []
            def complete(self, messages, cancel):
                self.calls += 1
                if self.calls == 1:
                    self.ready = True
                    return {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {'path': 'stale.txt', 'content': 'wrong'}}})}
                assert any(m['content'] == 'Do not create stale.txt' for m in messages)
                return {'content': '{"status":"completed","message":"Changed direction"}'}
        _, session = self.run_loop(Client())
        self.assertEqual(session['status'], 'completed')
        self.assertEqual(session['steps'], 0)
        self.assertFalse((Path(session['workspace']) / 'stale.txt').exists())

    def test_followup_runs_after_finish_and_uses_remaining_action_allowance(self):
        class Client:
            supports_inputs = True
            def __init__(self): self.delivered = False; self.calls = 0
            def inputs(self, mode):
                if mode == 'finish' and not self.delivered:
                    self.delivered = True
                    return [{'id': 'later', 'content': 'Write followup.txt next'}]
                return []
            def complete(self, messages, cancel):
                self.calls += 1
                if self.calls == 2:
                    return {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {'path': 'followup.txt', 'content': 'done'}}})}
                return {'content': '{"status":"completed","message":"Done"}'}
        client = Client()
        _, session = self.run_loop(client, max_steps=1)
        self.assertEqual(session['steps'], 1)
        self.assertEqual(session['status'], 'completed')
        self.assertEqual((Path(session['workspace']) / 'followup.txt').read_text(), 'done')

    def test_steering_between_batched_actions_prevents_the_remaining_action(self):
        class Client:
            supports_inputs = True
            def __init__(self): self.polls = 0; self.calls = 0
            def inputs(self, mode):
                self.polls += 1
                return [{'id': 'correction', 'content': 'Stop creating more files'}] if self.polls == 3 else []
            def complete(self, messages, cancel):
                self.calls += 1
                if self.calls == 1:
                    return {'content': json.dumps({'actions': [{'tool': 'write_file', 'arguments': {
                        'path': path, 'content': 'example'}} for path in ('first.txt', 'second.txt')]})}
                return {'content': '{"status":"completed","message":"Stopped after the first file"}'}
        _, session = self.run_loop(Client())
        self.assertEqual(session['steps'], 1)
        self.assertTrue((Path(session['workspace']) / 'first.txt').exists())
        self.assertFalse((Path(session['workspace']) / 'second.txt').exists())

    def test_exhausted_allowance_does_not_admit_a_followup_as_fresh_work(self):
        class Client:
            supports_inputs = True
            def __init__(self): self.calls = 0
            def inputs(self, mode):
                assert mode == 'steer', 'A follow-up must remain pending after the action cap'
                return []
            def complete(self, messages, cancel):
                self.calls += 1
                if self.calls == 1:
                    return {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {'path': 'one.txt', 'content': 'done'}}})}
                return {'content': '{"status":"completed","message":"Done"}'}
        _, session = self.run_loop(Client(), max_steps=1)
        self.assertEqual(session['steps'], 1)
        self.assertEqual(session['status'], 'completed')

    def test_all_human_corrections_survive_context_pressure(self):
        with temporary_directory() as directory:
            session = {'task': 'Original', 'workspace': directory, 'messages': [], 'feed': []}
            for index in range(20):
                session['messages'].extend([
                    {'role': 'assistant', 'content': 'old observation ' * 300},
                    {'role': 'user', 'origin': 'human', 'content': f'Human correction {index}'}])
            config = {**DEFAULTS, 'context_tokens': 17000, 'response_tokens': 4096}
            contents = [m['content'] for m in build_messages(session, config)]
            self.assertTrue(all(f'Human correction {i}' in contents for i in range(20)))


class InferenceEvidenceTests(unittest.TestCase):
    def test_json_history_preserves_absence_of_tools_and_drops_foreign_reasoning(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('test', 'hosted', 'fixture')
            client = ModelClient({**DEFAULTS, 'provider': 'hosted', 'protocol': 'json'})
            attach_history(client, store, session, client.config)
            response = {'choices': [{'message': {'content': '{"status":"completed"}'}, 'finish_reason': 'stop'}]}
            with patch('controller.providers.request_json', return_value=response) as transport:
                client.complete([{'role': 'user', 'content': 'Task', 'reasoning_content': 'foreign'}], threading.Event())
            payload = transport.call_args.args[1]
            self.assertNotIn('tools', payload)
            self.assertNotIn('foreign', json.dumps(payload))
            events = [json.loads(line) for line in (store.directory(session['id']) / 'events.jsonl').read_text().splitlines()]
            request = next(e['data'] for e in events if e['type'] == 'host_inference_request')
            state = json.loads((store.directory(session['id']) / 'inference' / (request['state'] + '.json')).read_text())
            self.assertFalse(state['tools_present'])

    def test_actual_wire_payload_and_changed_catalog_reconstruct_from_exportable_blobs(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('test', 'hosted', 'fixture')
            session['selected_seed'] = {'source_sha256': 'original'}
            observed = []
            client = ModelClient({**DEFAULTS, 'provider': 'hosted'}, key='secret-fixture', observer=observed.append)
            recorder = attach_history(client, store, session, client.config)
            tools = [{'type': 'function', 'function': {'name': 'tool', 'parameters': {}}}]
            messages = [{'role': 'system', 'content': 'You are AutoProteus'}, {'role': 'user', 'content': 'secret-fixture'}]
            with patch('controller.providers.request_json', return_value=FINISHED):
                client.complete(messages, threading.Event(), tools=tools)
                session['selected_seed']['source_sha256'] = 'later'
                tools[0]['function']['description'] = 'Changed instructions'
                client.complete(messages, threading.Event(), tools=tools)
            events = [json.loads(line) for line in (store.directory(session['id']) / 'events.jsonl').read_text().splitlines()]
            requests = [e['data'] for e in events if e['type'] == 'host_inference_request']
            self.assertEqual(len(requests), 2)
            self.assertNotEqual(requests[0]['state'], requests[1]['state'])
            self.assertEqual(requests[1]['seed']['source_sha256'], 'original')
            root = store.directory(session['id']) / 'inference'
            blob = lambda key: json.loads((root / (key + '.json')).read_text(encoding='utf-8'))
            payload = {**requests[0]['options'], 'tools': blob(requests[0]['state'])['tools'],
                       'messages': [blob(key) for key in requests[0]['messages']]}
            exact = next(e['data']['payload'] for e in observed if e['type'] == 'provider_request')
            self.assertEqual(payload, exact)
            self.assertIn('[REDACTED]', json.dumps(payload))
            self.assertTrue(all(digest(json.loads(p.read_text(encoding='utf-8'))) == p.stem for p in root.glob('*.json')))
            self.assertNotIn('secret-fixture', ''.join(p.read_text(encoding='utf-8') for p in root.glob('*.json')))
            with patch('controller.inference_history.LIMIT', 1):
                event = {'type': 'provider_response', 'call_id': 'extra', 'elapsed_seconds': 0, 'data': {'new': 'data'}}
                recorder(event); recorder(event)
            journal = (store.directory(session['id']) / 'events.jsonl').read_text()
            self.assertEqual(journal.count('host_inference_history_incomplete'), 1)

    def test_translation_marks_missing_outcomes_and_removes_foreign_metadata(self):
        action = {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'x'}}}),
                  'reasoning_content': 'foreign signature', 'tool_calls': [{'id': 'old-incompatible-id'}]}
        human = {'role': 'user', 'origin': 'human', 'content': 'ACTION RESULT\nnot JSON'}
        for ollama in (False, True):
            result = wire_messages([action, human, {'role': 'assistant', 'content': '42', 'signature': 'foreign'}], ollama)
            self.assertEqual(result[1]['role'], 'tool')
            self.assertFalse(json.loads(result[1]['content'])['ok'])
            self.assertIn('unknown', result[1]['content'])
            self.assertEqual(result[2], human)
            self.assertNotIn('foreign', json.dumps(result))
            self.assertEqual(result[-1], {'role': 'assistant', 'content': '42'})


class FinalContractTests(unittest.TestCase):
    def test_final_handoff_repeats_public_requirements_and_does_not_change_source(self):
        sys.path.insert(0, str(ROOT / 'evaluations'))
        import model_study
        import generalization
        from workflow_variants import variant
        for parent in ('csv_preview', 'sha256_file', 'format_json'):
            _, task = model_study.growth_task(parent, {'invoke_tool': '', 'contracts': generalization.CONTRACTS, 'recipe': generalization.RECIPE})
            self.assertIn(task['final_task'], task['task'])
            if parent == 'csv_preview':
                self.assertIn('default preview', task['final_task'])
            source = [{'path': 'unchanged', 'data': 'AA=='}]
            self.assertEqual(variant(source, 'final-contract'), source)


if __name__ == '__main__':
    unittest.main()
