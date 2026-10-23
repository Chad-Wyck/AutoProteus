"""Provider-envelope regression checks. No model or candidate code is run."""
import copy
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

from controller.config import DEFAULTS
from controller.providers import ModelClient, ProviderError, context_bytes, validate_context, wire_messages
from controller.action_protocol import with_response_instructions

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluations'))
from experience import UsageClient
from usage_budget import UsageBudget


def history(count=40):
    messages = [{'role': 'system', 'content': 'Keep the entire original contract.'},
                {'role': 'user', 'content': 'Original request: café 猫.'}]
    for index in range(count):
        messages.extend([
            {'role': 'assistant', 'content': json.dumps({'message': 'Inspect', 'action': {
                'tool': 'read_section', 'arguments': {'path': 'harness/tools.py', 'start': index, 'length': 100}}}, ensure_ascii=False)},
            {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({
                'tool': 'read_section', 'ok': True, 'result': {'content': 'é猫\\"\n' * 5}}, ensure_ascii=False)}])
        if index == count // 2:
            messages.append({'role': 'user', 'content': 'Human correction: keep CRLF and defaults.'})
    messages.append({'role': 'user', 'content': 'Runtime notice: finish only after checking.'})
    return messages


def tight_config(messages, provider='hosted', tools=None):
    wire = with_response_instructions(wire_messages(messages, provider == 'ollama'), 'native', tools)
    # The actual wire request is two or three bytes over the enforced bound.
    return {**DEFAULTS, 'provider': provider, 'response_tokens': 512,
            'context_tokens': 512 + 128 + (context_bytes(wire, tools) - 2) // 2}


FINISHED = {'choices': [{'message': {'tool_calls': [{'function': {'name': 'finish',
    'arguments': {'message': 'Verified', 'status': 'completed'}}}]}, 'finish_reason': 'tool_calls'}],
    'usage': {'prompt_tokens': 1000, 'completion_tokens': 10}}


class ContextBudgetTests(unittest.TestCase):
    def test_neutral_fits_but_native_overhead_is_trimmed_before_one_request(self):
        messages = history()
        original = copy.deepcopy(messages)
        tools = [{'type': 'function', 'function': {'name': 'finish', 'parameters': {}}}]
        config = tight_config(messages, tools=tools)
        validate_context(messages, tools, config)
        with self.assertRaises(ProviderError):
            validate_context(with_response_instructions(wire_messages(messages, False), 'native', tools), tools, config)
        events = []
        with patch('controller.providers.request_json', return_value=FINISHED) as transport:
            answer = ModelClient(config, observer=events.append).complete(messages, threading.Event(), tools=tools)
        transport.assert_called_once()
        wire = transport.call_args.args[1]['messages']
        validate_context(wire, tools, config)
        self.assertEqual(answer['context_adjustment']['removed_tool_exchanges'], 1)
        self.assertEqual([e['type'] for e in events].count('context_trimmed'), 1)
        self.assertEqual(messages, original)

    def test_both_native_formats_keep_humans_schemas_latest_pair_and_matching_ids(self):
        messages = history()
        original = copy.deepcopy(messages)
        tools = [{'type': 'function', 'function': {'name': 'read_section', 'parameters': {}}}]
        for provider in ('ollama', 'hosted'):
            with self.subTest(provider=provider):
                config = tight_config(messages, provider, tools)
                expected = with_response_instructions(wire_messages(messages, provider == 'ollama'), 'native', tools)
                actual, adjustment = ModelClient(config).prepare_messages(messages, tools)
                validate_context(actual, tools, config)
                self.assertGreater(adjustment['removed_tool_exchanges'], 0)
                self.assertEqual([m for m in actual if m['role'] in ('system', 'user')],
                                 [m for m in expected if m['role'] in ('system', 'user')])
                self.assertEqual(actual[-3:], expected[-3:])
                self.assertNotIn(expected[2], actual)
                for index, item in enumerate(actual):
                    if item['role'] == 'tool':
                        previous = actual[index - 1]['tool_calls'][0]
                        self.assertEqual(item.get('tool_call_id', item.get('tool_name')),
                                         previous['function']['name'] if provider == 'ollama' else previous['id'])
                self.assertEqual(messages, original)

    def test_admissible_history_keeps_exact_wire_ids_and_has_no_adjustment(self):
        messages = history()
        for provider in ('ollama', 'hosted'):
            actual, adjustment = ModelClient({**DEFAULTS, 'provider': provider}).prepare_messages(messages, [])
            self.assertEqual(actual, with_response_instructions(wire_messages(messages, provider == 'ollama'), 'native', []))
            self.assertIsNone(adjustment)

    def test_multiple_old_pairs_can_be_removed_across_a_human_correction(self):
        messages = history(8)
        expected = with_response_instructions(wire_messages(messages, False), 'native', [])
        # Leave room for precisely the instructions and most recent exchange.
        retained = [item for index, item in enumerate(expected)
                    if item['role'] in ('system', 'user') or index >= len(expected) - 3]
        allowance = context_bytes(retained, [])
        config = {**DEFAULTS, 'provider': 'hosted', 'response_tokens': 512,
                  'context_tokens': 512 + 128 + (allowance + 1) // 2}
        actual, adjustment = ModelClient(config).prepare_messages(messages, [])
        self.assertEqual(actual, retained)
        self.assertEqual(adjustment['removed_tool_exchanges'], 7)

    def test_irreducible_input_fails_before_transport(self):
        cases = [([{'role': 'user', 'content': '人' * 10000}], 'native', []),
                 (history(1), 'native', [{'schema': 'x' * 100000}])]
        for messages, protocol, tools in cases:
            with self.subTest(protocol=protocol, count=len(messages)):
                config = {**tight_config(messages), 'protocol': protocol, 'context_tokens': 1024}
                with patch('controller.providers.request_json') as transport, self.assertRaises(ProviderError) as caught:
                    ModelClient(config).complete(messages, threading.Event(), tools=tools)
                self.assertEqual(caught.exception.category, 'context')
                transport.assert_not_called()

    def test_non_context_error_is_not_repaired_or_retried(self):
        client = ModelClient(tight_config(history()))
        with patch.object(client, 'check_context', side_effect=ProviderError('Budget ended', category='budget')) as check:
            with self.assertRaises(ProviderError) as caught:
                client.prepare_messages(history(), [])
        self.assertEqual(caught.exception.category, 'budget')
        check.assert_called_once()

    def test_explicit_human_result_marker_and_interrupted_pairs_are_preserved(self):
        messages = history(2)[:-1]
        marker = {'role': 'user', 'origin': 'human', 'content': 'ACTION RESULT\n' + json.dumps({
            'tool': 'read_section', 'ok': True, 'result': 'Human instruction: retain this.'})}
        # Leave the previous action interrupted, then supply a human correction.
        messages[-1] = marker
        wire = wire_messages(messages, False)
        self.assertEqual(wire[-1], marker)
        # A later orphan result cannot pair across an intervening human message.
        messages += [{'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({
            'tool': 'read_section', 'ok': True, 'result': 'orphan'})}]
        self.assertEqual(wire_messages(messages, False)[-1]['role'], 'user')

    def test_usage_anchor_matches_the_actual_shortened_provider_input(self):
        messages = history()
        config = tight_config(messages)
        client = UsageClient(config)
        with patch('controller.providers.request_json', return_value=FINISHED) as transport:
            answer = client.complete(messages, threading.Event(), tools=[])
        self.assertIn('context_adjustment', answer)
        expected = UsageBudget()
        expected.observe(transport.call_args.args[1]['messages'], [], config, FINISHED['usage'])
        self.assertEqual(client.budget.anchor, expected.anchor)


if __name__ == '__main__':
    unittest.main()
