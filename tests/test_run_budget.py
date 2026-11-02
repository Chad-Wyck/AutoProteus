import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from controller.config import DEFAULTS
from controller.providers import ModelClient, ProviderError
from controller.errors import Cancelled

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
            'reported_output_tokens': 0, 'unmeasured_sent_calls': 1, 'usage_complete': False, 'exhausted': True,
            'reserved_output_tokens': 8, 'pending_dispatch_calls': 0})

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

    def test_cancel_before_late_request_reserves_unknown_usage_without_double_charging(self):
        budget = GeneratedTokenBudget(20)
        release, settled = threading.Event(), threading.Event()
        events = []
        def observer(event):
            events.append(event)
            if event['type'] == 'transport_end': settled.set()
        client = BudgetModelClient({**DEFAULTS, 'response_tokens': 8}, token_budget=budget, observer=observer)
        def delayed(client, messages, cancel, progress, tools=None, observe=None):
            cancel.set()
            if not release.wait(5): raise AssertionError('Test failed to release worker')
            observe('provider_request', {'payload': {}})
            return {'content': 'late action must never return', 'usage': {'completion_tokens': 3}}
        try:
            with patch.object(ModelClient, '_complete', delayed), self.assertRaises(Cancelled):
                client.complete([], threading.Event())
            before = budget.summary()
            self.assertFalse(before['usage_complete'])
            self.assertEqual(before['charged_output_tokens'], 8)
            self.assertEqual(before['reported_output_tokens'], 0)
            self.assertEqual(before['pending_dispatch_calls'], 1)
        finally:
            release.set()
            self.assertTrue(settled.wait(5))
        after = budget.summary()
        self.assertEqual(after['charged_output_tokens'], 8)
        self.assertEqual(after['reserved_output_tokens'], 8)
        self.assertEqual(after['reported_output_tokens'], 0)
        self.assertEqual(after['unmeasured_sent_calls'], 1)
        self.assertEqual(after['pending_dispatch_calls'], 0)
        self.assertFalse(after['usage_complete'])
        self.assertEqual([e['type'] for e in events].count('call_end'), 1)
        self.assertLess(next(i for i,e in enumerate(events) if e['type']=='call_end'),
                        next(i for i,e in enumerate(events) if e['type']=='provider_request'))

    def test_cancelled_pretransport_worker_can_settle_without_any_request(self):
        budget = GeneratedTokenBudget(20)
        release, settled = threading.Event(), threading.Event()
        client = BudgetModelClient({**DEFAULTS, 'response_tokens': 8}, token_budget=budget,
            observer=lambda event: settled.set() if event['type']=='transport_end' else None)
        def rejected(client, messages, cancel, progress, tools=None, observe=None):
            cancel.set()
            if not release.wait(5): raise AssertionError('Test failed to release worker')
            raise ProviderError('Local validation only', category='context')
        try:
            with patch.object(ModelClient, '_complete', rejected), self.assertRaises(Cancelled):
                client.complete([], threading.Event())
            self.assertFalse(budget.summary()['usage_complete'])
            self.assertEqual(budget.summary()['charged_output_tokens'], 8)
        finally:
            release.set()
            self.assertTrue(settled.wait(5))
        self.assertTrue(budget.summary()['usage_complete'])
        self.assertEqual(budget.summary()['charged_output_tokens'], 0)
        self.assertEqual(budget.summary()['reserved_output_tokens'], 0)

    def test_cancel_after_dispatch_keeps_unknown_reservation_after_late_response(self):
        budget = GeneratedTokenBudget(20)
        release, settled = threading.Event(), threading.Event()
        client = BudgetModelClient({**DEFAULTS, 'response_tokens': 8}, token_budget=budget,
            observer=lambda e: settled.set() if e['type']=='transport_end' else None)
        def delayed(client, messages, cancel, progress, tools=None, observe=None):
            observe('provider_request', {'payload': {}})
            cancel.set()
            if not release.wait(5): raise AssertionError('Test failed to release worker')
            observe('provider_response', {'payload': {'usage': {'completion_tokens': 3}}})
            return {'content': 'discarded', 'usage': {'completion_tokens': 3}}
        try:
            with patch.object(ModelClient, '_complete', delayed), self.assertRaises(Cancelled):
                client.complete([], threading.Event())
            before = budget.summary()
            self.assertFalse(before['usage_complete'])
            self.assertEqual(before['unmeasured_sent_calls'], 1)
            self.assertEqual(before['charged_output_tokens'], 8)
        finally:
            release.set()
            self.assertTrue(settled.wait(5))
        self.assertEqual(budget.summary()['charged_output_tokens'], 8)
        self.assertEqual(budget.summary()['reported_output_tokens'], 0)
        self.assertFalse(budget.summary()['usage_complete'])

    def test_stop_before_worker_start_has_no_inference_charge(self):
        budget = GeneratedTokenBudget(20)
        cancel = threading.Event(); cancel.set()
        with patch.object(ModelClient, '_complete') as work, self.assertRaises(Cancelled):
            self.client(budget).complete([], cancel)
        work.assert_not_called()
        self.assertTrue(budget.summary()['usage_complete'])
        self.assertEqual(budget.summary()['charged_output_tokens'], 0)

    def test_late_callbacks_keep_their_original_call_and_observer_after_client_reuse(self):
        budget = GeneratedTokenBudget(20)
        release, settled = threading.Event(), threading.Event()
        old_events, new_events = [], []
        def old_observer(event):
            old_events.append(event)
            if event['type']=='transport_end': settled.set()
        client = BudgetModelClient({**DEFAULTS, 'response_tokens': 8}, token_budget=budget, observer=old_observer)
        def delayed(client, messages, cancel, progress, tools=None, observe=None):
            cancel.set()
            if not release.wait(5): raise AssertionError('Test failed to release worker')
            observe('provider_request', {'payload': {}})
            return {'content': 'discarded', 'usage': {'completion_tokens': 3}}
        def returned(client, messages, cancel, progress, tools=None, observe=None):
            observe('provider_request', {'payload': {}})
            return {'content': '{}', 'usage': {'completion_tokens': 2}}
        try:
            with patch.object(ModelClient, '_complete', delayed), self.assertRaises(Cancelled):
                client.complete([], threading.Event())
            client._budget_observer = new_events.append
            with patch.object(ModelClient, '_complete', returned):
                client.complete([], threading.Event())
            self.assertEqual(budget.summary()['charged_output_tokens'], 10)
        finally:
            release.set()
            self.assertTrue(settled.wait(5))
        self.assertEqual(budget.summary()['charged_output_tokens'], 10)
        self.assertEqual(budget.summary()['reported_output_tokens'], 2)
        self.assertEqual(budget.summary()['unmeasured_sent_calls'], 1)
        old_id, new_id = old_events[0]['call_id'], new_events[0]['call_id']
        self.assertNotEqual(old_id, new_id)
        self.assertEqual({e['call_id'] for e in old_events}, {old_id})
        self.assertEqual({e['call_id'] for e in new_events}, {new_id})
        self.assertFalse(client._budget_calls)

    def test_timeout_before_dispatch_is_reserved_until_late_transport_settles(self):
        budget = GeneratedTokenBudget(20)
        release, settled = threading.Event(), threading.Event()
        client = BudgetModelClient({**DEFAULTS, 'response_tokens': 8, 'request_timeout': 0},
            token_budget=budget, observer=lambda e: settled.set() if e['type']=='transport_end' else None)
        def delayed(client, messages, cancel, progress, tools=None, observe=None):
            if not release.wait(5): raise AssertionError('Test failed to release worker')
            observe('provider_request', {'payload': {}})
            raise ProviderError('No usage available')
        try:
            with patch.object(ModelClient, '_complete', delayed), self.assertRaises(ProviderError) as error:
                client.complete([], threading.Event())
            self.assertEqual(error.exception.category, 'timeout')
            self.assertFalse(budget.summary()['usage_complete'])
            self.assertEqual(budget.summary()['pending_dispatch_calls'], 1)
        finally:
            release.set()
            self.assertTrue(settled.wait(5))
        self.assertEqual(budget.summary()['charged_output_tokens'], 8)
        self.assertEqual(budget.summary()['unmeasured_sent_calls'], 1)

    def test_paid_reservation_is_retained_for_cancelled_unsettled_dispatch(self):
        import hosted_study
        from test_seed import temporary_directory
        release, settled = threading.Event(), threading.Event()
        def delayed(client, messages, cancel, progress, tools=None, observe=None):
            cancel.set()
            if not release.wait(5): raise AssertionError('Test failed to release worker')
            observe('provider_request', {'payload': {}})
            raise ProviderError('No response')
        with temporary_directory() as directory:
            spend = hosted_study.Spend(Path(directory) / 'spend.json', 1)
            config = {**DEFAULTS, 'model': 'gpt-6.1-sol', 'context_tokens': 4096, 'response_tokens': 8}
            client = hosted_study.PaidClient(config,
                observer=lambda e: settled.set() if e['type']=='transport_end' else None)
            try:
                with patch.object(hosted_study, '_spend', spend), patch.object(ModelClient, '_complete', delayed), self.assertRaises(Cancelled):
                    client.complete([], threading.Event())
                self.assertGreater(spend.charged, 0)
                self.assertTrue(spend.calls[0]['dispatch_uncertain'])
                self.assertFalse(spend.calls[0]['usage_complete'])
                self.assertIsNone(spend.calls[0]['usage'])
            finally:
                release.set()
                self.assertTrue(settled.wait(5))
            self.assertEqual(len(spend.calls), 1)


if __name__ == '__main__':
    unittest.main()
