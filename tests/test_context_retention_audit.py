"""Offline evidence controls; no provider, model or candidate program runs."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluations'))
from context_retention_audit import audit_calls, size


class ContextRetentionAuditTests(unittest.TestCase):
    config = {'context_tokens': 32768, 'response_tokens': 4096}

    def test_separates_seed_selection_handoff_wire_trimming_and_reported_tokens(self):
        messages = [{'role': 'user', 'content': 'café 猫'}]
        records = [
            {'type': 'call_start', 'call_id': 'a', 'data': {'context': {
                'host_history_messages': 40, 'host_history_messages_omitted': 10, 'neutral_message_count': 8}}},
            {'type': 'context_trimmed', 'call_id': 'a', 'data': {'removed_tool_exchanges': 2}},
            {'type': 'provider_request', 'call_id': 'a', 'data': {'payload': {
                'messages': messages, 'tools': [], 'max_tokens': 2048}}},
            {'type': 'provider_response', 'call_id': 'a', 'data': {'payload': {'usage': {'prompt_tokens': 12}}}}]
        original = copy.deepcopy(records)
        result = audit_calls(records, self.config, {'a': {'messages': messages * 10,
            'handoff': {'messages_before': 10, 'messages_after': 8}}})
        row = result['calls'][0]
        self.assertEqual(row['seed_selected_messages'], 10)
        self.assertEqual(row['neutral_message_count'], 8)
        self.assertEqual(row['wire_messages'], 1)
        self.assertEqual(row['wire_bytes'], size(messages, []))
        self.assertEqual(row['input_allowance_tokens'], 32768 - 2048 - 128)
        self.assertEqual(row['reported_prompt_tokens'], 12)
        self.assertEqual(row['removed_wire_exchanges'], 2)
        self.assertEqual(result['summary']['signature_mismatch_calls'], 1)
        self.assertEqual(records, original)

    def test_missing_usage_and_unsupported_format_are_not_zero_cost_or_zero_prompt(self):
        records = [{'type': 'provider_request', 'call_id': 'a', 'data': {'payload': {'input': []}}}]
        result = audit_calls(records, self.config)
        self.assertTrue(result['calls'][0]['unsupported_wire_format'])
        self.assertNotIn('wire_bytes', result['calls'][0])
        self.assertIsNone(result['summary']['largest_reported_prompt_tokens'])
        self.assertEqual(result['summary']['prompt_usage_measured_calls'], 0)

    def test_zero_prompt_usage_and_final_stream_usage_are_observed_without_summing_frames(self):
        records = [{'type': 'provider_response', 'call_id': 'a', 'data': {'frames': [
            {'prompt_eval_count': 999}, {'done': True, 'prompt_eval_count': 0}]}}]
        result = audit_calls(records, self.config)
        self.assertEqual(result['calls'][0]['reported_prompt_tokens'], 0)
        self.assertEqual(result['summary']['prompt_usage_measured_calls'], 1)


if __name__ == '__main__':
    unittest.main()
