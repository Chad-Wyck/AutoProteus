"""Real guest checks; reference/candidate code is never imported on the host."""
import base64
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from controller.config import DEFAULTS
from controller.evaluation import freeze_source, run_task
from controller.isolation import IsolatedAgent, seed_files
from controller.storage import Store
from controller.providers import ModelClient
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import generalization as study
from run_budget import TokenBudgetMixin, GeneratedTokenBudget
from experience import reference, feature_check
spec = importlib.util.spec_from_file_location('grader_navigation', ROOT / 'evaluations/navigation-study.py')
navigation = importlib.util.module_from_spec(spec); spec.loader.exec_module(navigation)


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Enable real VM checks explicitly')
class GraderVMTests(unittest.TestCase):
    def test_host_token_exhaustion_preserves_checkpoint_and_blocks_another_action(self):
        import json
        class FixedClient(TokenBudgetMixin, ModelClient):
            def _complete(self, messages, cancel, progress, tools=None, observe=None):
                observe('provider_request', {'payload': {}})
                return {'content': json.dumps({'action': {'tool': 'write_file', 'arguments': {
                    'path': 'saved.txt', 'content': 'checkpoint survived'}}}), 'usage': {'completion_tokens': 8}}
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'hosted', 'protocol': 'json'}, key=lambda: '')
            budget = GeneratedTokenBudget(8)
            agent = IsolatedAgent(ROOT, store, settings, lambda config: FixedClient(config, token_budget=budget))
            try:
                result = run_task(agent, store, settings.values, {'name': 'bounded', 'task': 'Write a file and finish.',
                    'checks': [{'path': 'saved.txt', 'equals': 'checkpoint survived'}]},
                    freeze_source(store, seed_files(ROOT), 'starter'), 120)
                self.assertEqual(result['failure_kind'], 'budget')
                self.assertEqual(result['steps'], 1)
                self.assertTrue(result['checks'][0]['passed'])
                self.assertEqual(budget.summary()['reported_output_tokens'], 8)
            finally:
                agent.close()

    def test_experience_rejects_boundary_bypass_and_byte_limit_but_accepts_reference(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            source = seed_files(ROOT)
            positive = feature_check(navigation, store, freeze_source(store, reference(source), 'positive'), 'json_keys')
            self.assertTrue(positive['passed'], positive)
            for kwargs, failed in [({'bypass_boundary': True}, ('../outside.txt', 'escaping-link')),
                                   ({'byte_limited': True}, ('unicode-character-bound',))]:
                bad = feature_check(navigation, store, freeze_source(store, reference(source, **kwargs), 'negative'), 'json_keys')
                checks = {item['name']: item['passed'] for item in bad['probe']['checks']}
                self.assertFalse(bad['passed'])
                self.assertTrue(all(checks[key] is False for key in failed), bad)

    def test_generalization_positive_absent_and_boundary_controls(self):
        with temporary_directory() as directory:
            study.self_check(Path(directory), seed_files(ROOT))

    def test_development_invoker_works_with_a_failing_suite_without_implying_approval(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            source = seed_files(ROOT)
            source.append({'path': 'tests/test_deliberate_failure.py', 'data': base64.b64encode(
                b'import unittest\nclass Example(unittest.TestCase):\n def test_failure(self): self.fail("intentional")\n').decode()})
            settings = SimpleNamespace(values={**DEFAULTS, 'provider': 'demo', 'configured': True, 'terminal': True}, key=lambda: '')
            client = lambda _: study.benchmark.ScriptedClient([
                {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 experience/invoke_tool.py write_file \'{"path":"sample.txt","content":"written"}\''}}},
                {'status': 'completed'}])
            agent = IsolatedAgent(ROOT, store, settings, client)
            try:
                result = run_task(agent, store, settings.values, {'name': 'invoke-with-failed-tests', 'task': 'Exercise the edited tool.',
                    'fixtures': {'experience/invoke_tool.py': (ROOT / 'evaluations/invoke_tool.py').read_text()},
                    'checks': [{'path': 'sample.txt', 'equals': 'written'}]}, freeze_source(store, source, 'failing suite'), 120)
                self.assertTrue(result['passed'], result)
            finally:
                agent.close()


if __name__ == '__main__':
    unittest.main()
