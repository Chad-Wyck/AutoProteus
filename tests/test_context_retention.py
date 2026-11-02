"""Offline context-retention controls. No model, tokenizer or VM is started."""
import ast
import base64
import copy
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

from autoproteus.context import build_messages
from autoproteus.providers import tool_definitions
from controller.config import DEFAULTS
from controller.errors import Cancelled
from controller.isolation import seed_files
from controller.providers import ModelClient, context_bytes, ProviderError
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from context_retention import RetentionBudget, neutral_identity
from retention_client import RetentionModelClient, variant
from run_budget import GeneratedTokenBudget
from types import SimpleNamespace
import model_plan
import model_study


def history(count=8):
    messages = [{'role': 'system', 'content': 'Keep the exact contract.'},
                {'role': 'user', 'content': 'Original human request.'}]
    for index in range(count):
        messages.extend([{'role': 'assistant', 'content': json.dumps({'action': {
            'tool': 'read_file', 'arguments': {'path': str(index) + '.txt'}}})},
            {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'read_file',
                'ok': True, 'result': {'content': 'context ' * 500}})}])
    return messages


def reply(prompt=4000):
    return {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': '', 'tool_calls': [{
        'function': {'name': 'finish', 'arguments': '{"status":"completed","message":"done"}'}}]}}],
        'usage': {'prompt_tokens': prompt, 'completion_tokens': 2}}


class RetentionTests(unittest.TestCase):
    config = {**DEFAULTS, 'provider': 'hosted', 'base_url': 'http://127.0.0.1:47958/v1',
              'context_tokens': 32768, 'response_tokens': 4096, 'protocol': 'native'}

    def test_first_call_fallback_and_exact_prefix_anchor_with_changing_metadata(self):
        messages = history()
        budget = RetentionBudget()
        fallback = budget.estimate(messages, [], self.config, 'seed-a')
        self.assertEqual(budget.last['mode'], 'conservative_fallback')
        old = messages + [{'role': 'user', 'content': 'Current task plan (model-written todo.txt; human first):\nold'}]
        budget.observe(old, [], self.config, {'prompt_tokens': 4000}, 'seed-a')
        new = messages + history(1)[2:] + [{'role': 'user', 'content': 'Current task plan (model-written todo.txt; human first):\nnew'}]
        estimate = budget.estimate(new, [], self.config, 'seed-a')
        self.assertEqual(budget.last['mode'], 'provider_anchor')
        self.assertGreater(estimate, 4000 + 256)
        self.assertLess(estimate, fallback)

    def test_scope_changes_and_rewritten_prefix_do_not_reuse_usage(self):
        messages = history()
        cases = [(messages, [{'new': 'tool'}], self.config, 'seed-a'),
                 (messages, [], {**self.config, 'model': 'other'}, 'seed-a'),
                 (messages, [], {**self.config, 'base_url': 'http://127.0.0.1:1'}, 'seed-a'),
                 (messages, [], self.config, 'seed-b'),
                 ([{**messages[0], 'content': 'Changed instructions'}, *messages[1:]], [], self.config, 'seed-a'),
                 ([*messages[:-1], {**messages[-1], 'content': 'Changed observation'}], [], self.config, 'seed-a')]
        for changed, tools, config, source in cases:
            with self.subTest(source=source, model=config['model'], tools=tools):
                budget = RetentionBudget()
                budget.observe(messages, [], self.config, {'prompt_tokens': 4000}, 'seed-a')
                budget.estimate(changed, tools, config, source)
                self.assertEqual(budget.last['mode'], 'conservative_fallback')
        budget.observe(messages, [], self.config, {}, 'seed-a')
        self.assertIsNone(budget.anchor)

    def test_seed_usage_requires_exact_host_receipt_without_wire_trimming(self):
        messages = history()
        good = {'usage': {'prompt_tokens': 4000}, 'context_retention': {
            'neutral_sha256': neutral_identity(messages), 'wire_trimmed': False}}
        budget = RetentionBudget()
        self.assertTrue(budget.observe_response(messages, [], self.config, good))
        for response in [{**good, 'context_retention': {**good['context_retention'], 'wire_trimmed': True}},
                         {**good, 'context_retention': {**good['context_retention'], 'neutral_sha256': 'handoff-changed'}},
                         {**good, 'normalization_error': 'invalid call'}, {**good, 'provider_error': 'cutoff'},
                         {**good, 'usage': {'prompt_tokens': True}}, {'usage': {'prompt_tokens': 4000}}]:
            self.assertFalse(budget.observe_response(messages, [], self.config, response))
            self.assertIsNone(budget.anchor)
        self.assertTrue(budget.observe_response([{**m, 'origin': 'human'} for m in messages], [], self.config, good))

    def test_guest_measurement_keeps_more_history_without_losing_human_or_activation_state(self):
        with temporary_directory() as directory:
            config = {**self.config, 'terminal': False, 'activation_context': 'Host-confirmed activation state'}
            session = {'id': 's', 'task': 'Original request: café 猫', 'workspace': directory,
                'messages': history(8)[2:], 'feed': []}
            initial = build_messages(session, config)
            budget = RetentionBudget()
            tools = tool_definitions(False)
            budget.observe(initial, tools, config, {'prompt_tokens': 4000})
            session['messages'] += history(7)[2:] + [{'role': 'user', 'origin': 'human',
                'content': 'Correction: preserve CRLF and use defaults.'}]
            original = copy.deepcopy(session['messages'])
            baseline = build_messages(session, config)
            retained = build_messages(session, config,
                measure=lambda messages, schemas: budget.estimate(messages, schemas, config) * 2)
            self.assertGreater(len(retained), len(baseline))
            self.assertIn({'role': 'user', 'content': session['task']}, retained)
            self.assertIn({'role': 'user', 'content': 'Correction: preserve CRLF and use defaults.'}, retained)
            self.assertIn({'role': 'user', 'content': config['activation_context']}, retained)
            self.assertEqual(session['messages'], original)
            for i, message in enumerate(retained):
                if message['content'].startswith('ACTION RESULT\n'):
                    self.assertEqual(retained[i - 1]['role'], 'assistant')

    def test_host_anchor_prices_actual_wire_and_retains_more_of_the_same_neutral_input(self):
        client = RetentionModelClient(self.config, token_budget=GeneratedTokenBudget(100000))
        client.observation_context = lambda messages: {'seed_sha256': 'source-a'}
        first, second = history(8), history(15)
        before = copy.deepcopy(second)
        with patch('controller.providers.request_json', return_value=reply()) as transport:
            a = client.complete(first, threading.Event(), tools=[])
            anchor = copy.deepcopy(client.retention.anchor)
            b = client.complete(second, threading.Event(), tools=[])
        self.assertEqual(anchor['input_tokens'], 4000)
        self.assertEqual(b['context_retention']['neutral_sha256'], neutral_identity(second))
        self.assertFalse(b['context_retention']['wire_trimmed'])
        wire = transport.call_args.args[1]['messages']
        baseline, adjustment = ModelClient(self.config).prepare_messages(second, [])
        self.assertIsNotNone(adjustment)
        self.assertGreater(len(wire), len(baseline))
        self.assertEqual(b['context_retention']['host_estimate']['mode'], 'provider_anchor')
        self.assertEqual(first, history(8))
        self.assertEqual(second, before)
        self.assertEqual(client.token_budget.summary()['reported_output_tokens'], 4)
        self.assertEqual(a['usage'], reply()['usage'])

    def test_first_request_is_identical_to_standard_production_transport(self):
        messages = history(2)
        with patch('controller.providers.request_json', return_value=reply()) as transport:
            ModelClient(self.config).complete(messages, threading.Event(), tools=[])
            RetentionModelClient(self.config).complete(messages, threading.Event(), tools=[])
        self.assertEqual(transport.call_args_list[0], transport.call_args_list[1])

    def test_missing_usage_source_changes_and_cancelled_late_workers_invalidate_cleanly(self):
        release, settled, cancel = threading.Event(), threading.Event(), threading.Event()
        client = RetentionModelClient(self.config, token_budget=GeneratedTokenBudget(20000),
            observer=lambda e: settled.set() if e['type'] == 'transport_end' else None)
        calls = []
        def transport(*args, **kwargs):
            calls.append(args)
            if len(calls) == 2:
                cancel.set()
                if not release.wait(5): raise AssertionError('Worker release timed out')
                return reply(999)
            return reply(4000 if len(calls) == 1 else 5000)
        try:
            with patch('controller.providers.request_json', side_effect=transport):
                client.complete(history(), threading.Event(), tools=[])
                settled.clear()
                with self.assertRaises(Cancelled): client.complete(history(), cancel, tools=[])
                self.assertIsNone(client.retention.anchor)
                client.complete(history(), threading.Event(), tools=[])
                saved = copy.deepcopy(client.retention.anchor)
                settled.clear()
                release.set()
                self.assertTrue(settled.wait(5))
                self.assertEqual(client.retention.anchor, saved)
        finally:
            release.set()

    def test_variant_is_inert_small_and_changes_only_estimation_wiring(self):
        source = seed_files(ROOT)
        original = copy.deepcopy(source)
        result = variant(source)
        old = {x['path']: x['data'] for x in source}
        changed = {x['path'] for x in result if x['data'] != old.get(x['path'])}
        self.assertEqual(changed, {'autoproteus/agent.py', 'autoproteus/context_retention.py'})
        for item in result:
            if item['path'] in changed: ast.parse(base64.b64decode(item['data']).decode('utf-8'))
        helper = next(x for x in result if x['path'] == 'autoproteus/context_retention.py')
        self.assertLess(len(base64.b64decode(helper['data'])), 5000)
        self.assertEqual(source, original)
        with self.assertRaises(ValueError): variant(result)

    def test_factory_requires_explicit_host_opt_in_and_preserves_default_client(self):
        self.assertNotIsInstance(model_study.budget_client(self.config), RetentionModelClient)
        self.assertIsInstance(model_study.budget_client(self.config, retention=True), RetentionModelClient)
        with self.assertRaises(ValueError):
            model_study.budget_client({**self.config, 'base_url': 'https://example.com'}, retention=True)
        with self.assertRaises(ValueError):
            model_study.budget_client({**self.config, 'protocol': 'json'}, retention=True)

    def test_prepared_comparison_is_inert_and_counterbalances_each_feature(self):
        with temporary_directory() as directory:
            root = Path(directory)
            profiles = root / 'profiles.json'
            profiles.write_text(json.dumps([{'id': 'qwen9b', 'config': self.config}]))
            args = SimpleNamespace(output=str(root / 'study'), profiles=str(profiles), mode='full',
                repeats=2, timeout=600, output_token_budget=16384, experiment='context-retention')
            with patch.object(model_study, 'model_identity', side_effect=AssertionError('No inference connection during prepare')):
                model_plan.prepare(args)
            plan = json.loads((root / 'study/plan.json').read_text())
            self.assertEqual(plan['variants']['baseline'], plan['source'])
            self.assertFalse((root / 'study/queue.json').exists())
            self.assertFalse(plan['context_retention']['defaults_changed'])
            self.assertTrue(plan['require_first_use'])
            for feature in plan['upgrade_tasks']:
                self.assertEqual(plan['variant_orders']['1-' + feature],
                                 list(reversed(plan['variant_orders']['2-' + feature])))
            self.assertEqual(plan['trusted_sha256'], model_plan.trusted_files())

    def test_retention_comparison_does_not_launch_second_extension_after_failed_first_use(self):
        with temporary_directory() as directory:
            root = Path(directory)
            profiles = root / 'profiles.json'
            profiles.write_text(json.dumps([{'id': 'fixture', 'config': self.config}]))
            args = SimpleNamespace(output=str(root / 'study'), profiles=str(profiles), mode='full',
                repeats=1, timeout=600, output_token_budget=16384, experiment='context-retention')
            model_plan.prepare(args)
            observed = []
            def trial(folder, task, source, config, plan, feature=None, earlier=None):
                observed.append((feature, earlier))
                self.assertIsNone(earlier)
                return {'first_package_accepted': True, 'review': {'accepted': True}, 'first_use': {'passed': False}} if feature else {'run': {'passed': True}}
            with patch.object(model_study, 'calibrate'), patch.object(model_study, 'Appliance'), \
                 patch.object(model_study, 'model_identity', return_value={'model': 'offline'}), \
                 patch.object(model_study, 'benchmark', return_value={'passed': True}), \
                 patch.object(model_study, 'trial', side_effect=trial), \
                 patch('controller.providers.request_json', side_effect=AssertionError('No provider calls')):
                model_study._run(SimpleNamespace(input=args.output, retry=[]))
            queue = json.loads((root / 'study/queue.json').read_text())
            second = [v[-1] for k,v in queue['cells'].items() if '_growth_' in k]
            self.assertEqual(len(second), 6)
            self.assertTrue(all(row['state'] == 'not_run' for row in second))
            self.assertEqual(sum(bool(feature) for feature, _ in observed), 6)


if __name__ == '__main__':
    unittest.main()
