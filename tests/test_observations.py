import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

from controller.config import DEFAULTS
from controller.isolation import Broker
from controller.providers import ModelClient, ProviderError
from controller.storage import Store
from test_providers import FakeModelServer
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from observations import CallRecorder, call_metrics, navigation_metrics, read_events


class ObservationTests(unittest.TestCase):
    @staticmethod
    def trace(usages):
        events = []
        for index, usage in enumerate(usages):
            identity = 'call-' + str(index)
            for kind, data in [('call_start', {}), ('provider_request', {}), ('provider_response', {}),
                               ('transport_end', {}), ('call_end', {'status': 'returned', 'usage': usage})]:
                events.append({'type': kind, 'call_id': identity, 'elapsed_seconds': 1.25, 'data': data})
        return events

    def test_partial_usage_is_separate_from_complete_trace_and_timings(self):
        result = call_metrics(self.trace([{'prompt_tokens': 100, 'completion_tokens': 10}, {}]))
        self.assertTrue(result['trace_complete'])
        self.assertEqual(result['input_tokens'], 100)
        self.assertEqual(result['output_tokens'], 10)
        for name in ('input_tokens', 'output_tokens'):
            self.assertEqual(result['measurements'][name]['status'], 'partial')
            self.assertEqual(result['measurements'][name]['measured_calls'], 1)
            self.assertEqual(result['measurements'][name]['expected_calls'], 2)
            self.assertFalse(result['measurements'][name]['complete'])
        self.assertTrue(result['measurements']['call_seconds']['complete'])
        self.assertTrue(result['measurements']['transport_seconds']['complete'])
        split = call_metrics(self.trace([{'prompt_tokens': 0, 'completion_tokens': 0}, {'prompt_tokens': 30}]))
        self.assertTrue(split['measurements']['input_tokens']['complete'])
        self.assertFalse(split['measurements']['output_tokens']['complete'])
        misplaced = self.trace([{}, {'prompt_tokens': 30, 'completion_tokens': 5}])
        misplaced = [event for event in misplaced if not
                     (event['call_id'] == 'call-1' and event['type'] in ('provider_request', 'provider_response'))]
        result = call_metrics(misplaced)
        self.assertTrue(result['trace_complete'])
        self.assertFalse(result['measurements']['input_tokens']['complete'])

    def test_invalid_usage_and_missing_timing_are_not_complete_or_zero(self):
        events = self.trace([{'prompt_tokens': -1, 'completion_tokens': True}, {'prompt_tokens': '25', 'completion_tokens': 0}])
        for event in events:
            if event['type'] == 'call_end' and event['call_id'] == 'call-1':
                event['elapsed_seconds'] = float('nan')
        result = call_metrics(events)
        self.assertTrue(result['trace_complete'])
        self.assertIsNone(result['input_tokens'])
        self.assertEqual(result['measurements']['input_tokens']['status'], 'unavailable')
        self.assertEqual(result['output_tokens'], 0)
        self.assertFalse(result['measurements']['output_tokens']['complete'])
        self.assertEqual(result['call_seconds'], 1.25)
        self.assertFalse(result['measurements']['call_seconds']['complete'])
        self.assertTrue(result['measurements']['transport_seconds']['complete'])

    def test_duplicate_and_missing_terminal_records_invalidate_coverage(self):
        events = self.trace([{'prompt_tokens': 100, 'completion_tokens': 10}])
        duplicate = call_metrics(events + [events[-1]])
        self.assertFalse(duplicate['trace_complete'])
        self.assertEqual(duplicate['input_tokens'], 100)
        self.assertFalse(duplicate['measurements']['input_tokens']['complete'])
        missing = call_metrics([event for event in events if event['type'] != 'transport_end'])
        self.assertFalse(missing['trace_complete'])
        self.assertFalse(missing['measurements']['transport_seconds']['complete'])
    def test_host_recorder_sees_converted_request_and_raw_response_with_no_credentials(self):
        server = FakeModelServer(hosted=True, native=True)
        try:
            with temporary_directory() as directory:
                root = Path(directory)
                store = Store(root / 'sessions')
                session = store.create('Use the new tool.', 'hosted', 'fixture')
                session['messages'] = [{'role': 'assistant', 'content': 'omitted history'}]
                recorder = CallRecorder(root / 'calls.jsonl')
                config = {**DEFAULTS, 'provider': 'hosted', 'base_url': server.url}
                client = ModelClient(config, 'known-test-secret', recorder)
                broker = Broker(store, session, client, config, threading.Event())
                messages = [{'role': 'assistant', 'content': json.dumps({'action': {'tool': 'read_file', 'arguments': {'path': 'x'}}})},
                            {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file', 'ok': True, 'result': 'known-test-secret'})}]
                broker.handle({'op': 'infer', 'messages': messages, 'tools': [{'type': 'function', 'function': {'name': 'read_file', 'parameters': {}}}]})
                events = read_events(recorder.path)
                self.assertEqual([item['type'] for item in events[:3]], ['call_start', 'provider_request', 'provider_response'])
                self.assertEqual({item['type'] for item in events[3:]}, {'call_end', 'transport_end'})
                payload = events[1]['data']['payload']
                self.assertEqual(payload['messages'][-1]['role'], 'tool')
                self.assertIn('[REDACTED]', payload['messages'][-1]['content'])
                self.assertIn('known-test-secret', server.payloads[0]['messages'][-1]['content'])
                self.assertEqual(events[0]['data']['context']['host_history_messages_omitted'], 1)
                self.assertEqual(events[0]['data']['context']['request_index'], 1)
                self.assertIn('choices', events[2]['data']['payload'])
                text = recorder.path.read_text()
                for forbidden in ('known-test-secret', 'Authorization', server.url):
                    self.assertNotIn(forbidden, text)
                self.assertTrue(recorder.summary()['complete'])
        finally:
            server.close()

    def test_cutoff_is_recorded_without_becoming_an_action_and_collector_failure_does_not_change_inference(self):
        server = FakeModelServer(cut_short=True)
        try:
            events = []
            config = {**DEFAULTS, 'base_url': server.url, 'protocol': 'json'}
            client = ModelClient(config, observer=events.append)
            with self.assertRaises(ProviderError) as error:
                client.complete([{'role': 'user', 'content': 'test'}], threading.Event())
            self.assertEqual(error.exception.category, 'cutoff')
            self.assertFalse(next(item for item in events if item['type'] == 'provider_response')['data']['complete'])
            self.assertEqual(next(item for item in events if item['type'] == 'call_end')['data']['category'], 'cutoff')
        finally:
            server.close()
        server = FakeModelServer()
        try:
            def broken(_):
                raise OSError('fixture collector unavailable')
            client = ModelClient({**DEFAULTS, 'base_url': server.url, 'protocol': 'json'}, observer=broken)
            response = client.complete([{'role': 'user', 'content': 'test'}], threading.Event())
            self.assertIn('completed', response['content'])
            self.assertTrue(client.observation_failed)
        finally:
            server.close()

    def test_context_rejection_and_cancellation_are_terminal_without_a_wire_request(self):
        for cancel in (False, True):
            events = []
            config = {**DEFAULTS, 'protocol': 'json'}
            if not cancel:
                config.update(context_tokens=512, response_tokens=512)
            flag = threading.Event()
            if cancel:
                flag.set()
            client = ModelClient(config, observer=events.append)
            with patch('controller.providers.urllib.request.urlopen') as network, self.assertRaises(Exception):
                client.complete([{'role': 'user', 'content': 'test'}], flag)
            network.assert_not_called()
            self.assertTrue(any(item['type'] == 'call_end' for item in events))
            self.assertFalse(any(item['type'] == 'provider_request' for item in events))
            result = call_metrics(events)
            self.assertTrue(result['trace_complete'])
            self.assertEqual(result['input_tokens'], 0)
            self.assertEqual(result['output_tokens'], 0)
            self.assertTrue(result['measurements']['input_tokens']['complete'])

    def test_trace_storage_is_bounded_and_does_not_mix_trials(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'calls.jsonl'
            recorder = CallRecorder(path, limit=100)
            recorder({'type': 'small'})
            recorder({'type': 'large', 'text': 'x' * 200})
            self.assertEqual(len(read_events(path)), 1)
            self.assertFalse(recorder.summary()['complete'])
            self.assertLessEqual(path.stat().st_size, 100)
            with self.assertRaises(FileExistsError):
                CallRecorder(path)

    def test_late_transport_is_visible_after_timeout_without_releasing_a_late_action(self):
        events, release, ended = [], threading.Event(), threading.Event()
        def observe(item):
            events.append(item)
            if item['type'] == 'transport_end':
                ended.set()
        client = ModelClient({**DEFAULTS, 'request_timeout': 0.01}, observer=observe)
        def slow(*args, observe=None):
            observe('provider_request', {'payload': {}})
            release.wait(timeout=2)
            return {'content': 'late action'}
        try:
            with patch.object(client, '_complete', side_effect=slow), self.assertRaises(ProviderError) as error:
                client.complete([{'role': 'user', 'content': 'test'}], threading.Event())
            self.assertEqual(error.exception.category, 'timeout')
            self.assertEqual(call_metrics(events)['transport_finished_calls'], 0)
            self.assertFalse(call_metrics(events)['measurements']['call_seconds']['complete'])
        finally:
            release.set()
            self.assertTrue(ended.wait(timeout=2))
        self.assertEqual(call_metrics(events)['transport_finished_calls'], 1)
        self.assertEqual(call_metrics(events)['statuses'], {'error': 1})
        self.assertFalse(call_metrics(events)['measurements']['input_tokens']['complete'])

    def test_incomplete_trace_is_flagged_and_missing_token_counts_stay_unknown(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'calls.jsonl'
            path.write_bytes(b'{"type":"call_end","elapsed_seconds":1,"data":{"status":"returned"}}\n{"partial":')
            result = call_metrics(read_events(path))
            self.assertEqual(result['trace_read_errors'], 1)
            self.assertIsNone(result['input_tokens'])
        reported = call_metrics([{'type': 'call_end', 'elapsed_seconds': 1,
            'data': {'status': 'error', 'category': 'cutoff', 'usage': {'prompt_tokens': 50, 'completion_tokens': 12}}}])
        self.assertEqual((reported['input_tokens'], reported['output_tokens']), (50, 12))

    def test_overlapping_reads_and_green_check_tail_are_measured_without_stale_coverage(self):
        def action(tool, args, result, second):
            return {'type': 'action_result', 'time': f'2026-10-16T00:00:{second:02d}+00:00',
                    'data': {'ok': True, 'action': {'tool': tool, 'arguments': args}, 'result': result}}
        events = [{'type': 'run_started', 'time': '2026-10-16T00:00:00+00:00'},
                  action('read_section', {'path': 'harness/x.py'}, {'start': 0, 'content': 'abcdefghij'}, 1),
                  action('read_section', {'path': 'harness/x.py'}, {'start': 5, 'content': 'fghijklmno'}, 2),
                  action('edit_file', {'path': 'harness/x.py'}, {}, 3),
                  action('read_section', {'path': 'harness/x.py'}, {'start': 0, 'content': 'abcdefghij'}, 4),
                  action('run_command', {'command': 'python3 harness/seed.py check'}, {'exit_code': 0, 'output': json.dumps({'check': 'candidate tests', 'passed': True, 'tests': 49})}, 5),
                  action('read_section', {'path': 'harness/x.py'}, {'start': 0, 'content': 'abcdefghij'}, 6)]
        metrics = navigation_metrics(events)
        self.assertEqual(metrics['read_characters'], 40)
        self.assertEqual(metrics['overlapping_read_characters'], 5)
        self.assertEqual(metrics['first_runtime_source_edit_seconds'], 3)
        self.assertEqual(metrics['first_green_development_check_seconds'], 5)
        self.assertEqual(metrics['reads_after_last_green_check'], 1)
        self.assertEqual(metrics['actions_after_last_green_check'], 1)


if __name__ == '__main__':
    unittest.main()
