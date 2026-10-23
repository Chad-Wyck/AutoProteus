"""One seed interface, host-rendered formats and lossless argument transport."""
import copy
import json
import threading
import unittest
from unittest.mock import patch

from autoproteus.protocol import parse_action
from autoproteus.providers import tool_definitions
from controller.config import DEFAULTS
from controller.providers import ModelClient, ProviderError, context_bytes, model_response


class ActionProtocolTests(unittest.TestCase):
    def test_one_catalog_is_rendered_without_editing_seed_instructions_or_human_text(self):
        tools = tool_definitions(False) + [{'type': 'function', 'function': {
            'name': 'new_capability', 'description': 'Model-written capability.',
            'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}}]
        messages = [{'role': 'system', 'content': 'Shared editable instructions.'},
                    {'role': 'user', 'origin': 'human', 'content': 'Keep "quotes", 猫 and CRLF\r\n'}]
        original = copy.deepcopy(messages)
        for protocol in ('native', 'json'):
            config = {**DEFAULTS, 'provider': 'hosted', 'protocol': protocol}
            wire, adjustment = ModelClient(config).prepare_messages(messages, tools)
            self.assertIsNone(adjustment)
            self.assertTrue(wire[0]['content'].startswith(messages[0]['content'] + '\n'))
            self.assertEqual(wire[1], {'role': 'user', 'content': messages[1]['content']})
            if protocol == 'json':
                rendered = json.loads(wire[0]['content'].split('Tools:\n', 1)[1])
                names = {item['function']['name'] for item in rendered}
                self.assertIn('new_capability', names)
                self.assertNotIn('run_command', names)
                self.assertNotIn('finish', names)  # JSON status, same seed decision.
            self.assertEqual(messages, original)

    def test_native_arguments_keep_arbitrary_source_text_without_guessing_or_rewriting(self):
        content = 'print("猫\\n")\r\n# </parameter> {"key": "value"}\r\n'
        arguments = {'path': 'example.py', 'content': content}
        for serialized in (arguments, json.dumps(arguments)):
            answer = model_response('', [{'function': {'name': 'write_file', 'arguments': serialized}}], True)
            self.assertEqual(parse_action(answer['content'])['action']['arguments'], arguments)
        malformed = model_response('', [{'function': {'name': 'write_file', 'arguments': '{broken'}}], True)
        self.assertIn('normalization_error', malformed)
        self.assertEqual(malformed['content'], '')

    def test_effective_prefix_is_stable_and_catalog_stays_out_of_json_api_tools(self):
        tools = tool_definitions()
        for protocol in ('native', 'json'):
            payloads = []
            def respond(url, payload, *args):
                payloads.append(payload)
                message = ({'tool_calls': [{'function': {'name': 'finish',
                    'arguments': {'message': 'Checked', 'status': 'completed'}}}]} if protocol == 'native'
                    else {'content': '{"message":"Checked","status":"completed"}'})
                return {'choices': [{'finish_reason': 'stop', 'message': message}]}
            config = {**DEFAULTS, 'provider': 'hosted', 'protocol': protocol, 'json_mode': True}
            client = ModelClient(config)
            first = [{'role': 'system', 'content': 'Shared seed prompt.'}, {'role': 'user', 'content': 'Original request.'}]
            with patch('controller.providers.request_json', side_effect=respond):
                client.complete(first, threading.Event(), tools=tools)
                client.complete(first + [{'role': 'user', 'content': 'Current todo: verify.'}], threading.Event(), tools=tools)
            self.assertEqual(payloads[0]['messages'][0], payloads[1]['messages'][0])
            if protocol == 'native':
                self.assertEqual(payloads[0]['tools'], tools)
                self.assertNotIn('response_format', payloads[0])
            else:
                self.assertNotIn('tools', payloads[0])
                self.assertEqual(payloads[0]['response_format'], {'type': 'json_object'})

    def test_json_budget_removes_only_old_matched_pairs_preserving_human_marker_and_latest_result(self):
        def pair(path, content):
            return [{'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': path}}})},
                    {'role': 'user', 'origin': 'tool', 'content': 'ACTION RESULT\n' + json.dumps({
                        'tool': 'read_file', 'ok': True, 'result': {'content': content}})}]
        human = 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'result': 'Keep this correction.'})
        messages = [{'role': 'system', 'content': 'Shared instructions.'}, {'role': 'user', 'content': 'Original task.'},
                    *pair('old.txt', 'old ' * 2500), {'role': 'user', 'origin': 'human', 'content': human},
                    *pair('latest.txt', 'Latest result must survive.')]
        config = {**DEFAULTS, 'provider': 'hosted', 'protocol': 'json'}
        tools = tool_definitions()
        full, _ = ModelClient(config).prepare_messages(messages, tools)
        kept = full[:2] + full[4:]
        allowance = context_bytes(kept, [])
        client = ModelClient({**config, 'response_tokens': 512, 'context_tokens': 640 + (allowance + 1) // 2})
        shortened, adjustment = client.prepare_messages(messages, tools)
        self.assertEqual(shortened, kept)
        self.assertEqual(adjustment['removed_tool_exchanges'], 1)
        self.assertIn({'role': 'user', 'content': human}, shortened)
        self.assertIn('Latest result must survive.', shortened[-1]['content'])

    def test_json_overhead_cannot_silently_displace_user_instructions(self):
        tools = tool_definitions()
        messages = [{'role': 'system', 'content': 'Shared instructions.'}, {'role': 'user', 'content': '人' * 500}]
        # Neutral messages fit; required fallback declarations do not.
        limit = context_bytes(messages, []) + 2
        client = ModelClient({**DEFAULTS, 'provider': 'hosted', 'protocol': 'json',
                              'response_tokens': 512, 'context_tokens': 640 + limit // 2})
        with patch('controller.providers.request_json') as network, self.assertRaises(ProviderError) as caught:
            client.complete(messages, threading.Event(), tools=tools)
        self.assertEqual(caught.exception.category, 'context')
        network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
