import ast
import base64
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest

from autoproteus.tools import Workspace
from controller.config import DEFAULTS
from controller.isolation import Broker, seed_files
from controller.providers import ModelClient, ProviderError, validate_context
from controller.storage import Store
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from experience import variant, UsageClient, learning_records
from journal_tools import history_search, history_read
from usage_budget import UsageBudget
from inspect_workspace import inspect


class ExperienceTests(unittest.TestCase):
    def test_usage_anchor_matches_full_prefix_and_invalidates_changed_scope(self):
        config = {**DEFAULTS, 'context_tokens': 8192, 'response_tokens': 1024}
        original = [{'role': 'system', 'content': 'stable'}, {'role': 'user', 'content': '猫' * 4000}]
        budget = UsageBudget()
        fallback = budget.estimate(original, [], config)
        self.assertEqual(fallback, validate_context(original, [], config)['estimated_input_tokens'])
        self.assertTrue(budget.observe(original, [], config, {'prompt_eval_count': 1200}))
        self.assertLess(budget.estimate(original + [{'role': 'assistant', 'content': 'saved'}], [], config), fallback)
        edits = [original[:1], [original[0], {'role': 'user', 'content': 'different' * 1000}]]
        for messages in edits:
            self.assertEqual(budget.estimate(messages, [], config), UsageBudget().estimate(messages, [], config))
        for key in ('model', 'base_url', 'temperature', 'thinking', 'context_tokens'):
            changed = {**config, key: 'changed'}
            self.assertEqual(budget.estimate(original, [], changed), UsageBudget().estimate(original, [], changed))
        tools = [{'name': 'new'}]
        self.assertEqual(budget.estimate(original, tools, config), UsageBudget().estimate(original, tools, config))
        for value in (None, True, -1, float('nan'), float('inf'), '1200'):
            self.assertFalse(budget.observe(original, [], config, {'prompt_tokens': value}))
            self.assertIsNone(budget.anchor)

    def test_host_usage_client_is_opt_in_and_still_enforces_estimate(self):
        config = {**DEFAULTS, 'protocol': 'json', 'context_tokens': 4096, 'response_tokens': 1024}
        messages = [{'role': 'user', 'content': 'x' * 7000}]
        with self.assertRaises(ProviderError):
            ModelClient(config).check_context(messages, [])
        client = UsageClient(config)
        with self.assertRaises(ProviderError):
            client.check_context(messages, [])
        client.budget.observe(messages, [], config, {'prompt_tokens': 600})
        self.assertLess(client.check_context(messages, [])['estimated_input_tokens'], 1000)
        with self.assertRaises(ProviderError):
            client.check_context([{'role': 'user', 'content': 'changed' * 2000}], [])
        # Selecting an alternate estimator grants no extra broker operations.
        with temporary_directory() as directory:
            store = Store(Path(directory))
            session = store.create('boundary', 'demo', 'fixture')
            broker = Broker(store, session, client, config, threading.Event())
            with self.assertRaisesRegex(Exception, 'Invalid model request'):
                broker.handle({'op': 'infer', 'messages': [{'role': 'user', 'content': 'x' * 1500001}]})

    def test_history_retains_ids_versions_provenance_and_exact_character_windows(self):
        with temporary_directory() as directory:
            root = Path(directory)
            (root / 'experience').mkdir()
            events = [{'id': 'a' * 32, 'type': 'display', 'data': {'kind': 'user', 'text': 'keep this instruction'}},
                {'id': 'b' * 32, 'type': 'action_result', 'seed_sha256': 'c' * 64,
                 'data': {'action': {'tool': 'read_file'}, 'ok': True, 'result': {'value': 'café 猫' * 1000}}},
                {'id': 'd' * 32, 'type': 'action_result', 'data': {'action': {'tool': 'history_read'}, 'result': {'value': 'recursive'}}}]
            archive = root / 'experience/history.jsonl'
            archive.write_text('\n'.join(json.dumps(item) for item in events) + '\n{bad')
            workspace = Workspace(root)
            result = history_search(workspace, {'query': 'café'})
            self.assertTrue(result['truncated'])
            self.assertEqual(result['matches'][0]['seed_sha256'], 'c' * 64)
            recovered = history_read(workspace, {'id': 'b' * 32, 'start': 17, 'length': 31})
            self.assertEqual(recovered['content'], json.dumps(events[1]['data'], ensure_ascii=False)[17:48])
            self.assertEqual(recovered['origin'], 'guest_tool_result')
            self.assertFalse(recovered['eof'])
            self.assertIn('does not verify', recovered['authority'])
            self.assertEqual(history_search(workspace, {'query': 'instruction'})['matches'][0]['origin'], 'human')
            self.assertEqual(history_search(workspace, {'query': 'recursive'})['matches'], [])
            with self.assertRaises(ValueError):
                history_read(workspace, {'id': '../other-task'})
            with self.assertRaises(ValueError):
                history_read(workspace, {'id': 'b' * 32, 'length': True})

    def test_history_archive_cannot_escape_workspace_and_results_are_bounded(self):
        with temporary_directory() as directory:
            root = Path(directory)
            (root / 'experience').mkdir()
            event = {'id': 'a' * 32, 'type': 'action_result', 'data': {'result': 'needle' * 10000}}
            (root / 'experience/history.jsonl').write_text(json.dumps(event))
            result = history_search(Workspace(root), {'query': 'needle'})
            self.assertLess(len(json.dumps(result)), 1200)
            with self.assertRaises(ValueError):
                history_search(Workspace(root), {'query': 'x' * 201})
            with self.assertRaises(ValueError):
                history_read(Workspace(root), {'id': 'a' * 32, 'length': 10001})

    def test_variants_leave_seed_and_protected_tests_unchanged(self):
        baseline = seed_files(ROOT)
        before = {item['path']: item['data'] for item in baseline}
        for name in ('retrieval', 'usage', 'procedure', 'program'):
            changed = variant(baseline, name)
            after = {item['path']: item['data'] for item in changed}
            self.assertEqual({item['path']: item['data'] for item in baseline}, before)
            for path in before:
                if path.startswith('tests/') or path == 'seed.py':
                    self.assertEqual(after[path], before[path])
            for item in changed:
                if item['path'].endswith('.py'):
                    ast.parse(base64.b64decode(item['data']))  # Parse only; never import a candidate.
        usage = {item['path']: base64.b64decode(item['data']).decode() for item in variant(baseline, 'usage')}
        self.assertIn('budgeter.estimate(items, schemas, config)', usage['autoproteus/agent.py'])
        self.assertIn('.observe(messages, schemas, config', usage['autoproteus/agent.py'])

    def test_inspection_program_parses_without_executing_and_rejects_escape(self):
        with temporary_directory() as directory:
            root = Path(directory)
            text = '# café 猫\r\nraise RuntimeError("never execute")\r\ndef feature():\r\n    pass\r\n'
            (root / 'sample.py').write_bytes(text.encode())
            row = inspect(root, ['sample.py'])[0]
            self.assertEqual(row['characters'], len(text))
            self.assertEqual(row['definitions'], [{'name': 'feature', 'line': 3}])
            self.assertEqual((root / 'sample.py').read_bytes(), text.encode())
            for names in ([], ['sample.py'] * 13, ['../outside.py']):
                with self.assertRaises(ValueError):
                    inspect(root, names)

    def test_learning_ledger_does_not_infer_following_or_task_use_from_loading(self):
        event = {'type': 'action_result', 'data': {'ok': True, 'action': {'tool': 'read_file',
                 'arguments': {'path': 'experience/upgrade.md'}}, 'result': {'content': 'read'}}}
        record = learning_records([event], 'parent', {'runtime_changed': True, 'public': {'passed': True}}, 'session')
        self.assertTrue(record['procedure']['loaded_through_file_tool'])
        self.assertEqual(record['procedure']['followed'], 'unmeasured')
        self.assertFalse(record['procedure']['general_effectiveness_verified'])
        self.assertFalse(record['capability']['upgrade_accepted'])
        self.assertEqual(record['capability']['task_agent_routes']['direct'], ['read_file'])

    def test_prepared_settings_cannot_change_without_invalidating_the_plan(self):
        spec = importlib.util.spec_from_file_location('navigation_integrity', ROOT / 'evaluations/navigation-study.py')
        navigation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(navigation)
        with temporary_directory() as directory:
            root = Path(directory)
            source = seed_files(ROOT)
            (root / 'baseline-source.json').write_text(json.dumps(source))
            plan = {'config': {'model': 'frozen'}, 'trusted_sha256': {},
                    'sources': {'baseline': navigation.source_identity(source)}}
            navigation.save_plan(root, plan)
            self.assertEqual(navigation.load_plan(root)[0]['config']['model'], 'frozen')
            plan['config']['model'] = 'changed'
            (root / 'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(RuntimeError, 'plan/settings changed'):
                navigation.load_plan(root)


if __name__ == '__main__':
    unittest.main()
