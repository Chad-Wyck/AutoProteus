import copy
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from controller.config import DEFAULTS, Settings
from controller.providers import ModelClient, ProviderError
from controller.openai_responses import ResponsesHistory, payload, selected, unpack
from autoproteus.providers import tool_definitions

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluations'))
import hosted_study
from repeatability import repeat_config


def reply(name='read_file', arguments=None, status='completed'):
    return {'id': 'resp_saved', 'model': 'gpt-6.1-sol', 'status': status,
        'usage': {'input_tokens': 250, 'output_tokens': 30,
                  'output_tokens_details': {'reasoning_tokens': 20}},
        'output': [{'id': 'rs_private', 'type': 'reasoning', 'summary': [], 'encrypted_content': 'OPAQUE'},
                   {'id': 'fc_saved', 'type': 'function_call', 'status': 'completed', 'call_id': 'actual_saved_id',
                    'name': name, 'arguments': json.dumps(arguments or {'path': 'sample.txt'})}]}


class OpenAIResponsesTests(unittest.TestCase):
    def setUp(self):
        self.config = {**DEFAULTS, 'provider': 'hosted', 'base_url': 'https://api.openai.com/v1',
                       'model': 'gpt-6.1-sol', 'reasoning_effort': 'low'}

    def test_official_auto_routing_preserves_other_hosted_and_local_transports(self):
        self.assertTrue(selected(self.config))
        self.assertFalse(selected({**self.config, 'provider': 'ollama'}))
        self.assertFalse(selected({**self.config, 'base_url': 'https://other.example/v1'}))
        self.assertFalse(selected({**self.config, 'api_format': 'chat-completions'}))

    def test_real_client_keeps_optional_arguments_and_replays_provider_state_with_matching_ids(self):
        captured = []
        def request(url, data, headers, timeout):
            captured.append((url, copy.deepcopy(data), headers))
            return reply() if len(captured) == 1 else reply('finish', {'message': 'Done', 'status': 'completed'})
        client = ModelClient(self.config, 'KEY_NEVER_IN_PAYLOAD')
        messages = [{'role': 'system', 'content': 'Follow instructions.'}, {'role': 'user', 'content': 'Read sample.txt.'}]
        with patch('controller.providers.request_json', side_effect=request):
            answer = client.complete(messages, threading.Event(), tools=tool_definitions())
            self.assertEqual(json.loads(answer['content'])['action']['tool'], 'read_file')
            messages += [{'role': 'assistant', 'content': answer['content']},
                         {'role': 'user', 'origin': 'tool', 'content': 'ACTION RESULT\n' + json.dumps(
                             {'tool': 'read_file', 'ok': True, 'result': {'content': 'hello'}})}]
            answer = client.complete(messages, threading.Event(), tools=tool_definitions())
        self.assertEqual(json.loads(answer['content'])['status'], 'completed')
        first, second = captured[0][1], captured[1][1]
        self.assertEqual(captured[0][0], 'https://api.openai.com/v1/responses')
        self.assertEqual(first['reasoning'], {'effort': 'low'})
        self.assertFalse(first['store'])
        self.assertFalse(first['parallel_tool_calls'])
        for key in ('temperature', 'seed', 'max_tokens', 'previous_response_id'):
            self.assertNotIn(key, first)
        tools = tool_definitions()
        self.assertEqual([t['parameters'] for t in first['tools']], [t['function']['parameters'] for t in tools])
        self.assertTrue(all(t['strict'] is False for t in first['tools']))
        reasoning = next(item for item in second['input'] if item.get('type') == 'reasoning')
        self.assertEqual(reasoning['encrypted_content'], 'OPAQUE')
        output = next(item for item in second['input'] if item.get('type') == 'function_call_output')
        self.assertEqual(output['call_id'], 'actual_saved_id')
        self.assertNotIn('KEY_NEVER_IN_PAYLOAD', json.dumps(first))

    def test_incomplete_unknown_execution_and_malformed_outputs_never_release_actions(self):
        rows = [reply(status='incomplete'), {**reply(), 'output': [{'type': 'program', 'code': 'danger'}]},
                {**reply(), 'output': [{'type': 'function_call', 'name': 'read_file', 'arguments': '{}'}]}]
        for data in rows:
            with self.subTest(data=data), self.assertRaises(ProviderError) as raised:
                unpack(data)
            self.assertEqual(raised.exception.response['usage']['output_tokens'], 30)

    def test_human_result_prefix_remains_a_user_message_and_unknown_outcomes_are_explicit(self):
        captured = []
        def request(url, data, headers, timeout):
            captured.append(data)
            return reply('finish', {'status': 'completed', 'message': 'Done'})
        messages = [{'role': 'user', 'origin': 'human', 'content': 'ACTION RESULT\nnot JSON'},
                    {'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'x'}}})}]
        with patch('controller.providers.request_json', side_effect=request):
            ModelClient(self.config).complete(messages, threading.Event(), tools=tool_definitions())
        items = captured[0]['input']
        self.assertTrue(any(item.get('role') == 'user' and item['content'] == messages[0]['content'] for item in items))
        self.assertIn('outcome is unknown', next(item['output'] for item in items if item.get('type') == 'function_call_output'))

    def test_changed_history_does_not_reuse_opaque_state(self):
        history = ResponsesHistory()
        call = {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'call_1', 'function':
            {'name': 'read_file', 'arguments': '{"path": "sample.txt"}'}}]}
        prefix = [{'role': 'user', 'content': 'Original task'}]
        history.remember(prefix + [call, {'role': 'tool', 'content': '{}', 'tool_call_id': 'call_1'}], reply()['output'])
        changed = history.input([{'role': 'user', 'content': 'Different task'}, call])
        self.assertFalse(any(item.get('type') == 'reasoning' for item in changed))

    def test_provider_default_sampling_has_no_fictitious_seed(self):
        config = repeat_config({'sampling_seed_mode': 'provider-default', 'repeatability': {'sampling_seeds': [104729]}},
                               {**self.config, 'sampling_seed': 104729}, 1)
        self.assertNotIn('sampling_seed', config)
        self.assertEqual(config['case_schedule_seed'], 104729)

    def test_spend_cap_counts_reasoning_once_and_unknown_calls_conservatively(self):
        with tempfile.TemporaryDirectory() as folder:
            guard = hosted_study.Spend(Path(folder) / 'spend.json', .25)
            reservation = guard.reserve(self.config)
            guard.close(reservation, True, reply()['usage'])
            self.assertAlmostEqual(guard.charged, .000925)
            reservation = guard.reserve(self.config)
            guard.close(reservation, True, {})
            with self.assertRaises(ProviderError): guard.reserve(self.config)
            saved = json.loads(guard.path.read_text())
            self.assertFalse(saved['calls'][-1]['usage_complete'])

    def test_paid_study_rejects_missing_optin_before_unlocking_key(self):
        plan = {'allow_hosted': True, 'profiles': [{'config': {**self.config, 'api_format': 'responses'}}]}
        with patch('hosted_study.protect') as decrypt:
            with self.assertRaises(ValueError):
                with hosted_study.connection(plan, SimpleNamespace(allow_hosted=False), Path('.')): pass
            decrypt.assert_not_called()

    def test_full_host_history_path_records_responses_and_cannot_suppress_spend(self):
        from controller.storage import Store
        from controller.inference_history import attach_history
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / 'sessions')
            session = store.create('Check the provider', 'hosted', 'gpt-6.1-sol')
            guard = hosted_study.Spend(root / 'spend.json', 1)
            events = []
            with patch.object(hosted_study, '_spend', guard):
                client = hosted_study.PaidClient(self.config, key='PRIVATE', observer=events.append)
                history = attach_history(client, store, session, self.config)
                with patch('controller.providers.request_json', return_value=reply()):
                    client.complete([{'role': 'user', 'content': 'Read sample.txt.'}],
                                    threading.Event(), tools=tool_definitions())
            self.assertFalse(history.failed)
            self.assertFalse(client.observation_failed)
            self.assertEqual(sum(e['type'] == 'provider_request' for e in events), 1)
            self.assertTrue(guard.calls[-1]['sent'])
            self.assertAlmostEqual(guard.charged, .000925)
            saved = [json.loads(line) for line in (store.directory(session['id']) / 'events.jsonl').read_text().splitlines()]
            request = next(e['data'] for e in saved if e['type'] == 'host_inference_request')
            self.assertEqual(request['input_format'], 'responses')
            self.assertNotIn('input', request['options'])

    def test_reported_usage_is_charged_even_if_request_observation_was_lost(self):
        with tempfile.TemporaryDirectory() as folder:
            guard = hosted_study.Spend(Path(folder) / 'spend.json', 1)
            reservation = guard.reserve(self.config)
            guard.close(reservation, False, reply()['usage'])
            self.assertTrue(guard.calls[-1]['sent'])
            self.assertAlmostEqual(guard.charged, .000925)

    def test_new_configuration_invalidates_previous_qualification(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(Path(folder))
            settings.values['compatibility'] = {'passed': True}
            settings.update({'api_format': 'responses', 'reasoning_effort': 'low'})
            self.assertNotIn('compatibility', settings.values)
            with self.assertRaises(ValueError): settings.preview({'reasoning_effort': 'invented'})


if __name__ == '__main__':
    unittest.main()
