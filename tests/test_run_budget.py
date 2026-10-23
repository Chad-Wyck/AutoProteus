import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from controller.config import DEFAULTS
from controller.providers import ModelClient, ProviderError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluations'))
from run_budget import BudgetModelClient, GeneratedTokenBudget


class RunBudgetTests(unittest.TestCase):
    def test_budget_preserves_standard_wire_messages_and_tool_call_ids(self):
        import json
        config = {**DEFAULTS, 'provider': 'hosted', 'protocol': 'native', 'response_tokens': 8}
        messages = [{'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'sample.txt'}}})},
                    {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'result': {'content': 'sample'}})}]
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '', 'tool_calls': [{
            'function': {'name': 'finish', 'arguments': '{"message":"done","status":"completed"}'}}]}}], 'usage': {'completion_tokens': 2}}
        with patch('controller.providers.request_json', return_value=response) as request:
            ModelClient(config).complete(messages, threading.Event(), tools=[])
            BudgetModelClient(config, token_budget=GeneratedTokenBudget(20)).complete(messages, threading.Event(), tools=[])
        payloads = [item.args[1] for item in request.call_args_list]
        self.assertEqual(payloads[0], payloads[1])
        call = next(item for item in payloads[1]['messages'] if item.get('tool_calls'))
        self.assertEqual(call['tool_calls'][0]['id'], 'call_0')

    def client(self, budget):
        return BudgetModelClient({**DEFAULTS, 'response_tokens': 8}, token_budget=budget)

    def test_cumulative_budget_caps_requests_counts_reasoning_once_and_survives_new_clients(self):
        budget = GeneratedTokenBudget(10)
        limits = []
        def response(client, messages, cancel, progress, tools=None, observe=None):
            limits.append(client.config['response_tokens'])
            observe('provider_request', {'payload': {}})
            return {'content': '{}', 'usage': {'completion_tokens': min(7, client.config['response_tokens']),
                'completion_tokens_details': {'reasoning_tokens': 3}}}
        with patch.object(ModelClient, '_complete', response):
            self.client(budget).complete([], threading.Event())
            self.client(budget).complete([], threading.Event())
            with self.assertRaises(ProviderError) as error:
                self.client(budget).complete([], threading.Event())
        self.assertEqual(error.exception.category, 'budget')
        self.assertEqual(limits, [8, 3])
        self.assertEqual(budget.summary()['reported_output_tokens'], 10)

    def test_cutoff_usage_is_charged_and_original_response_limit_restored(self):
        budget = GeneratedTokenBudget(10)
        client = self.client(budget)
        def cutoff(client, messages, cancel, progress, tools=None, observe=None):
            observe('provider_request', {'payload': {}})
            raise ProviderError('cutoff', {'usage': {'eval_count': 7}}, category='cutoff')
        with patch.object(ModelClient, '_complete', cutoff), self.assertRaises(ProviderError):
            client.complete([], threading.Event())
        self.assertEqual(budget.summary()['charged_output_tokens'], 7)
        self.assertEqual(client.config['response_tokens'], 8)

    def test_sent_request_without_usage_is_conservatively_charged_not_reported_as_measured(self):
        budget = GeneratedTokenBudget(8)
        def failed(client, messages, cancel, progress, tools=None, observe=None):
            observe('provider_request', {'payload': {}})
            raise ProviderError('unresponsive')
        with patch.object(ModelClient, '_complete', failed), self.assertRaises(ProviderError):
            self.client(budget).complete([], threading.Event())
        self.assertEqual(budget.summary(), {'limit': 8, 'charged_output_tokens': 8,
            'reported_output_tokens': 0, 'unmeasured_sent_calls': 1, 'usage_complete': False, 'exhausted': True})

    def test_local_rejection_costs_no_generation_and_provider_overrun_cannot_release_action(self):
        budget = GeneratedTokenBudget(5)
        with patch.object(ModelClient, '_complete', side_effect=ProviderError('too large', category='context')):
            with self.assertRaises(ProviderError): self.client(budget).complete([], threading.Event())
        self.assertEqual(budget.summary()['charged_output_tokens'], 0)
        def overrun(client, messages, cancel, progress, tools=None, observe=None):
            observe('provider_request', {'payload': {}})
            return {'content': 'must not execute', 'usage': {'completion_tokens': 6}}
        with patch.object(ModelClient, '_complete', overrun), self.assertRaises(ProviderError) as error:
            self.client(budget).complete([], threading.Event())
        self.assertEqual(error.exception.category, 'budget')


if __name__ == '__main__':
    unittest.main()
