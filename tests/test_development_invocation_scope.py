"""Coverage for the opt-in receipt experiment and frozen guest helper sources.

Only the opt-in VM case executes guest helper code. Host-only cases inspect
frozen source as bytes or existing trusted grading functions.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from model_plan import development_invoker
import model_plan
import activation_use
import development_receipts
from test_seed import temporary_directory


class DevelopmentInvokerSourceTests(unittest.TestCase):
    def test_cue_is_opt_in_and_default_sources_remain_unchanged(self):
        import ast
        import base64
        from controller.isolation import seed_files
        source = seed_files(ROOT)
        before = copy.deepcopy(source)
        candidate = development_receipts.variant(source)
        changed = [item['path'] for item, original in zip(candidate, source) if item != original]
        self.assertEqual(changed, ['seed.py'])
        self.assertEqual(source, before)
        seed = next(item for item in candidate if item['path'] == 'seed.py')
        self.assertIn("'scope': 'invocation_only'", base64.b64decode(seed['data']).decode())
        ast.parse(base64.b64decode(seed['data']).decode())
        helper = (ROOT / 'evaluations/invoke_tool.py').read_text(encoding='utf-8')
        self.assertNotIn('execution_route', helper)
        self.assertNotIn('execution_route', (ROOT / 'seed.py').read_text(encoding='utf-8'))
        scoped_helper = development_receipts.invoker(helper)
        self.assertIn("'execution_route': 'development_helper'", scoped_helper)
        ast.parse(scoped_helper)
        with self.assertRaises(ValueError):
            development_receipts.variant(candidate)

    def test_guest_source_is_frozen_verbatim_without_execution(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'guest.py'
            raw = '# café\r\nraise RuntimeError("must not execute on host")\r\n'.encode('utf-8')
            path.write_bytes(raw)
            frozen = development_invoker(path)
            self.assertEqual(frozen['source'].encode('utf-8'), raw)
            self.assertEqual(frozen['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(frozen['path'], str(path.resolve()))

    def test_empty_oversized_and_non_utf8_sources_are_rejected(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'guest.py'
            for raw in (b'', b'x' * 65537, b'\xff'):
                with self.subTest(size=len(raw)):
                    path.write_bytes(raw)
                    with self.assertRaises(ValueError):
                        development_invoker(path)

    def test_size_boundary_and_frozen_copy_survive_later_file_changes(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'guest.py'
            path.write_bytes(b'#' * 65536)
            frozen = development_invoker(path)
            path.write_text('changed', encoding='utf-8')
            self.assertEqual(frozen['source'], '#' * 65536)
            self.assertEqual(frozen['sha256'], hashlib.sha256(b'#' * 65536).hexdigest())

    def test_preparation_freezes_each_arm_helper_instead_of_shared_checkout_default(self):
        from controller.config import DEFAULTS
        with temporary_directory() as directory:
            root = Path(directory)
            (root / 'evaluations').mkdir()
            (root / 'evaluations/invoke_tool.py').write_text('shared checkout default', encoding='utf-8')
            (root / 'evaluations/tasks.json').write_text('[]', encoding='utf-8')
            profiles = root / 'profiles.json'
            config = {**DEFAULTS, 'configured': True, 'provider': 'ollama',
                      'base_url': 'http://127.0.0.1:47938', 'model': 'fixture',
                      'protocol': 'native', 'context_tokens': 4096, 'response_tokens': 512}
            profiles.write_text(json.dumps([{'id': 'fixture', 'config': config}]), encoding='utf-8')
            plans = []
            with patch.object(model_plan, 'ROOT', root), patch.object(model_plan, 'seed_files', return_value=[]), \
                    patch.object(model_plan, 'trusted_files', return_value={}), \
                    patch.object(model_plan, 'environment', return_value={'fixture': True}):
                for arm in ('baseline', 'candidate', 'default'):
                    helper = root / (arm + '.py')
                    text = '# ' + arm + '\nraise RuntimeError("guest source must not run on host")\n'
                    helper.write_bytes(text.encode('utf-8'))
                    output = root / '.data' / arm
                    args = SimpleNamespace(output=str(output), profiles=str(profiles), mode='basic',
                        repeats=1, timeout=600, output_token_budget=16384,
                        invoke_tool_file=str(helper) if arm != 'default' else None)
                    model_plan.prepare(args)
                    plan = json.loads((output / 'plan.json').read_text(encoding='utf-8'))
                    if arm == 'default':
                        self.assertEqual(plan['invoke_tool'], 'shared checkout default')
                        self.assertNotIn('development_invoker', plan)
                    else:
                        self.assertEqual(plan['invoke_tool'], text)
                        self.assertEqual(plan['development_invoker']['sha256'], hashlib.sha256(text.encode()).hexdigest())
                    plans.append(plan)
            self.assertNotEqual(plans[0]['invoke_tool'], plans[1]['invoke_tool'])


class DevelopmentReceiptAttributionTests(unittest.TestCase):
    def test_scope_metadata_neither_invents_native_use_nor_changes_functional_cli_credit(self):
        spec = activation_use.contract('sha256_file', 'receipt-scope')
        final, receipt = activation_use.expected(spec)

        class Files:
            def read(self, path):
                return {spec['input']: final, spec['output']: json.dumps(receipt).encode()}[path]

        arguments = json.dumps({'path': spec['input']})
        forms = (
            ('candidate tool invocation', "python3 harness/seed.py invoke --tool sha256_file --arguments '" + arguments + "'"),
            ('development tool invocation', "python3 experience/invoke_tool.py sha256_file '" + arguments + "'"),
        )
        for check, command in forms:
            output = {'check': check, 'passed': True, 'tool': 'sha256_file', 'result': receipt,
                      'scope': 'invocation_only', 'execution_route': 'development_helper'}
            event = {'type': 'action_result', 'data': {'ok': True,
                     'action': {'tool': 'run_command', 'arguments': {'command': command}},
                     'result': {'exit_code': 0, 'output': json.dumps(output)}}}
            grade = activation_use.grade(Files(), spec, [event], source_unchanged=True, completed=True)
            self.assertTrue(grade['passed'])  # Preserve existing functional-route acceptance.
            self.assertEqual(grade['usage']['direct'], [])
            self.assertIn('sha256_file', grade['usage']['development'])
            self.assertFalse(activation_use.grade(Files(), spec, [event],
                source_unchanged=True, completed=False)['passed'])
            spoof = copy.deepcopy(event)
            output['execution_route'] = 'native'
            spoof['data']['result']['output'] = json.dumps(output)
            self.assertEqual(activation_use.grade(Files(), spec, [spoof],
                source_unchanged=True, completed=True)['usage']['direct'], [])
        native = {'type': 'action_result', 'data': {'ok': True,
                  'action': {'tool': 'sha256_file', 'arguments': {'path': spec['input']}}, 'result': receipt}}
        self.assertIn('sha256_file', activation_use.grade(Files(), spec, [native],
            source_unchanged=True, completed=True)['usage']['direct'])


VM_SCOPE_SCRIPT = '''import json, subprocess
from pathlib import Path
def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=20)
arguments = json.dumps({'path':'input.txt'})
canonical = run(['python3','harness/seed.py','invoke','--tool','read_file','--arguments',arguments])
legacy = run(['python3','experience/invoke_tool.py','read_file',arguments])
receipts = []
for result in (canonical, legacy):
    assert result.returncode == 0, result.stderr + result.stdout
    value = json.loads(result.stdout.splitlines()[0])
    assert value['passed'] is True and value['result']['content'] == 'sample\\n'
    assert value['scope'] == 'invocation_only'
    assert value['execution_route'] == 'development_helper'
    assert 'does not establish' in value['notice']
    receipts.append(value)
failed = run(['python3','harness/seed.py','invoke','--tool','finish','--arguments','{}'])
assert failed.returncode != 0
failure = json.loads(failed.stdout)
assert failure['passed'] is False and failure['execution_route'] == 'development_helper'
assert failure['scope'] == 'invocation_only'
legacy_failure = run(['python3','experience/invoke_tool.py','finish','{}'])
assert legacy_failure.returncode != 0
Path('scope-check.json').write_text(json.dumps({'receipts':receipts,'failure':failure}))
'''


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Guest helper coverage requires explicit VM opt in')
class DevelopmentReceiptVMTests(unittest.TestCase):
    def test_both_real_guest_entrypoints_label_scope_without_changing_source_or_tool_results(self):
        from controller.config import DEFAULTS
        from controller.evaluation import run_task, freeze_source, candidate_source, source_identity
        from controller.isolation import Artifacts, IsolatedAgent, seed_files
        from controller.storage import Store
        config = {**DEFAULTS, 'configured': True, 'provider': 'demo', 'terminal': True,
                  'action_limit': True, 'max_steps': 2}
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            settings = SimpleNamespace(values=config, key=lambda: '')
            source = development_receipts.variant(seed_files(ROOT))
            client = Mock()
            client.complete.side_effect = [
                {'content': json.dumps({'action': {'tool': 'run_command', 'arguments': {
                    'command': 'python3 development/scope_check.py'}}})},
                {'content': json.dumps({'status': 'completed'})},
            ]
            agent = IsolatedAgent(ROOT, store, settings, lambda _: client)
            try:
                task = {'name': 'development-receipt-scope', 'task': 'Run the scoped helper fixture.',
                        'fixtures': {'input.txt': 'sample\n', 'development/scope_check.py': VM_SCOPE_SCRIPT,
                                     'experience/invoke_tool.py': development_receipts.invoker(
                                         (ROOT / 'evaluations/invoke_tool.py').read_text(encoding='utf-8'))},
                        'checks': [{'path': 'scope-check.json'}]}
                result = run_task(agent, store, config, task, freeze_source(store, source, 'Scope fixture'), timeout=60)
                self.assertTrue(result['passed'], result)
                session = store.get(result['session'])
                self.assertEqual(source_identity(candidate_source(store, session)), source_identity(source))
                evidence = json.loads(Artifacts(store, session).read('scope-check.json'))
                self.assertEqual(len(evidence['receipts']), 2)
                self.assertFalse(evidence['failure']['passed'])
            finally:
                agent.close()
