"""Controller input staging is opt in; these tests never contact inference."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from controller.config import DEFAULTS
from controller.evaluation import freeze_source
from controller.isolation import Artifacts, seed_files
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import model_study as runner


class StagedInputTests(unittest.TestCase):
    def test_final_bytes_arrive_only_after_checks_and_both_budgets_remain_shared(self):
        for verified, early_output in ((True, False), (False, False), (True, True)):
            with self.subTest(verified=verified, early_output=early_output), temporary_directory() as directory:
                folder = Path(directory)
                source = seed_files(ROOT)
                fixture = '{"z":3,"a":"猫"}'
                task = {'name': 'growth', 'task': 'Implement, activate, format inventory.json and audit it.',
                        'fixtures': {'sample.txt': 'parent example', 'inventory.json': fixture}, 'checks': []}
                plan = {'experiment': 'staged-inputs', 'treatment': 'staged-inputs', 'deadline': 30,
                        'generated_tokens': 17, 'ordinary_generated_tokens': 5,
                        'trusted_sha256': {}, 'environment': {}}
                agent = Mock(execution=SimpleNamespace(mode='vm'))
                state = {}
                def make_agent(root, store, settings, factory):
                    state.update(store=store, settings=settings)
                    return agent
                def develop(agent, store, config, actual, frozen, timeout, deadline):
                    self.assertNotIn('inventory.json', actual['fixtures'])
                    self.assertNotIn(fixture, json.dumps(actual, ensure_ascii=False))
                    self.assertIn('development/example.json', actual['fixtures'])
                    session = freeze_source(store, source, 'Submitted hand-written fixture')
                    session.update(status='waiting', steps=3)
                    state['session'] = session
                    if early_output:
                        files = Artifacts(store, session)
                        files.put('audit.json', base64.b64encode(b'{}').decode())
                        files.checkpoint([*session['artifacts'], 'audit.json'])
                    return {'session': session['id'], 'timed_out': False}
                def activate(session, message, **kwargs):
                    self.assertEqual(Artifacts(state['store'], session).read('inventory.json'), fixture.encode())
                    self.assertEqual(state['settings'].values['max_steps'], 1)
                    self.assertEqual(kwargs['handoff'], 'concise')
                    self.assertIn('now available', message)
                agent.start.side_effect = activate
                def final_use(agent, session, timeout):
                    raw = (json.dumps(json.loads(fixture), sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()
                    files = Artifacts(state['store'], session)
                    for name, data in [('inventory.json', raw), ('audit.json', json.dumps({
                        'path': 'inventory.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}).encode())]:
                        files.put(name, base64.b64encode(data).decode())
                    files.checkpoint([*session['artifacts'], 'audit.json'])
                    session['status'] = 'completed'
                    return {'timed_out': False}
                checks = Mock(receipts=[])
                checks.assess.return_value = {'runtime_changed': True, 'new_test_files': ['tests/test_new.py'],
                    'protected_unchanged': True, 'allowed_files_only': True,
                    **{key: {'passed': verified} for key in ('regressions', 'feature', 'public')}}
                checks.feature.return_value = checks.public.return_value = {'passed': True}
                with patch.object(runner, 'IsolatedAgent', side_effect=make_agent), patch.object(runner, 'run_task', side_effect=develop), \
                        patch.object(runner, 'Checks', return_value=checks), patch.object(runner.study, 'journal', return_value=[]), \
                        patch.object(runner.study, 'wait', side_effect=final_use):
                    result = runner.trial(folder, task, source, {**DEFAULTS, 'max_steps': 4}, plan, 'format_json', 'sha256_file')
                allowed = verified and not early_output
                self.assertEqual(result['stages']['activated'], allowed)
                self.assertEqual(result['withheld_input']['delivered'], allowed)
                self.assertEqual(result['input_protocol'], 'withheld_final_input')
                self.assertEqual(result['token_budget']['limit'], 17)
                agent.restart_seed.assert_not_called()
                if allowed:
                    agent.start.assert_called_once()
                    self.assertTrue(result['final_artifacts_correct'])
                else:
                    agent.start.assert_not_called()
                    self.assertNotIn('inventory.json', state['session']['artifacts'])
                self.assertEqual(task['fixtures']['inventory.json'], fixture)

    def test_preparation_rejects_unsupported_parents_and_reuse_and_labels_protocols(self):
        with temporary_directory() as directory:
            folder = Path(directory)
            profiles = folder / 'profiles.json'
            profiles.write_text(json.dumps([{'id': 'fixture', 'config': {**DEFAULTS, 'provider': 'ollama'}}]))
            parent = folder / 'parent.json'
            parent.write_text(json.dumps(seed_files(ROOT)))
            args = SimpleNamespace(output=str(folder / 'study'), profiles=str(profiles), mode='full', repeats=1,
                timeout=30, output_token_budget=100, experiment='staged-inputs', parent_source=str(parent), parent_tool='sha256_file')
            runner.prepare(args)
            plan = json.loads((folder / 'study/plan.json').read_text())
            self.assertEqual(set(plan['variants']), {'baseline', 'staged-inputs'})
            self.assertIn('evaluations/model_plan.py', plan['trusted_sha256'])
            comparison = runner.comparison(SimpleNamespace(data={'cells': {}}), plan)
            self.assertEqual(comparison['input_protocols']['staged-inputs'], 'withheld_final_input')
            for parent_tool, reuse in [('csv_preview', None), ('sha256_file', 'unused.json')]:
                args.output, args.parent_tool, args.reuse_task = str(folder / 'rejected'), parent_tool, reuse
                with self.assertRaises(ValueError):
                    runner.prepare(args)
                self.assertFalse((folder / 'rejected').exists())


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Enable real VM checks explicitly')
class StagedInputVMTests(unittest.TestCase):
    def test_scripted_extension_is_checked_then_receives_input_in_a_fresh_vm(self):
        import copy
        import generalization as study
        sha = study.REFERENCE[:study.REFERENCE.index('        if tool == "csv_preview":')]
        formatter = study.REFERENCE[study.REFERENCE.index('        if tool == "format_json":'):]
        source, combined = seed_files(ROOT), {}
        specs = {name: ('Scripted fixture tool.', {'path': {'type': 'string'}}, ['path']) for name in ('sha256_file', 'format_json')}
        for item in source:
            if item['path'] not in ('autoproteus/tools.py', 'autoproteus/providers.py'):
                continue
            text = base64.b64decode(item['data']).decode()
            if item['path'].endswith('tools.py'):
                parent = text.replace('        if tool == "list_files":', sha + '        if tool == "list_files":')
                full = text.replace('        if tool == "list_files":', sha + formatter + '        if tool == "list_files":')
            else:
                parent = text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr({'sha256_file': specs['sha256_file']}) + ' | {')
                full = text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr(specs) + ' | {')
            item['data'] = base64.b64encode(parent.encode()).decode()
            combined['harness/' + item['path']] = full
        combined['harness/tests/test_new_format.py'] = '''import unittest
from pathlib import Path
from autoproteus.tools import Workspace
from test_seed import temporary_directory
class FormatTests(unittest.TestCase):
 def test_writes_exact_contents(self):
  with temporary_directory() as folder:
   root = Path(folder)
   (root / 'example.json').write_bytes(b'null')
   result = Workspace(root).execute('format_json', {'path':'example.json'})
   self.assertEqual((root / 'example.json').read_bytes(), b'null\\n')
   self.assertEqual(result['bytes'], 5)
'''
        plan = {'experiment': 'staged-inputs', 'treatment': 'staged-inputs', 'deadline': 180,
            'generated_tokens': 1000, 'ordinary_generated_tokens': 100, 'trusted_sha256': {}, 'environment': {},
            'contracts': study.CONTRACTS, 'recipe': study.RECIPE, 'invoke_tool': ''}
        feature, task = runner.growth_task('sha256_file', plan)
        final_raw = (json.dumps(json.loads(task['fixtures']['inventory.json']), sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()
        receipt = json.dumps({'path': 'inventory.json', 'bytes': len(final_raw), 'sha256': hashlib.sha256(final_raw).hexdigest()})
        phases = [[{'action': {'tool': 'run_command', 'arguments': {'command': 'test ! -e inventory.json && test ! -e audit.json'}}},
                   {'action': {'tool': 'sha256_file', 'arguments': {'path': 'sample.txt'}}}] +
                  [{'action': {'tool': 'write_file', 'arguments': {'path': name, 'content': text}}} for name, text in combined.items()] +
                  [{'action': {'tool': 'write_file', 'arguments': {'path': 'development/args.json', 'content': '{"path":"development/example.json"}'}}},
                   {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 harness/seed.py invoke --tool format_json --arguments-file development/args.json'}}},
                   {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 harness/seed.py check'}}},
                   {'status': 'needs_input'}],
                  [{'action': {'tool': 'read_file', 'arguments': {'path': 'inventory.json'}}},
                   {'action': {'tool': 'format_json', 'arguments': {'path': 'inventory.json'}}},
                   {'action': {'tool': 'sha256_file', 'arguments': {'path': 'inventory.json'}}},
                   {'action': {'tool': 'write_file', 'arguments': {'path': 'audit.json', 'content': receipt}}},
                   {'status': 'completed'}]]
        made = []
        def client(config, **kwargs):
            result = study.benchmark.ScriptedClient(phases[len(made)])
            result.observation_failed = False
            made.append(result)
            return result
        with temporary_directory() as directory, patch.object(runner, 'BudgetModelClient', side_effect=client):
            result = runner.trial(Path(directory), task, copy.deepcopy(source),
                {**DEFAULTS, 'provider': 'demo', 'configured': True, 'terminal': True, 'max_steps': 16}, plan, feature, 'sha256_file')
        self.assertEqual(len(made), 2)
        self.assertTrue(result['verified_extension'], result)
        self.assertTrue(result['stages']['activated'], result)
        self.assertTrue(result['withheld_input']['delivered'])
        self.assertTrue(result['scores']['strict_route_success'], result)
