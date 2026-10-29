import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_seed import temporary_directory

SEED = ROOT / 'seed.py'


class WorkspaceInvocationTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Scripted VM check requires opt in')
    def test_real_vm_changed_directory_keeps_fixtures_outside_the_seed(self):
        from controller.config import DEFAULTS
        from controller.evaluation import run_task, freeze_source, candidate_source, source_identity
        from controller.isolation import Artifacts, IsolatedAgent, seed_files
        from controller.storage import Store
        config = {**DEFAULTS, 'configured': True, 'provider': 'demo', 'terminal': True,
                  'action_limit': True, 'max_steps': 4}
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            settings = SimpleNamespace(values=config, key=lambda: '')
            source = seed_files(ROOT)
            client = Mock(); client.complete.side_effect = [
                {'content': json.dumps({'action': {'tool': 'run_command', 'arguments': {
                    'command': 'cd harness && python3 seed.py invoke --tool write_file --arguments-file development/args.json --text-file content development/body.txt'}}})},
                {'content': json.dumps({'status': 'completed'})}]
            agent = IsolatedAgent(ROOT, store, settings, lambda _: client)
            try:
                result = run_task(agent, store, config, {'name': 'workspace-cli', 'task': 'Try the edited tool from harness/.',
                    'fixtures': {'development/args.json': json.dumps({'path': 'result.txt'}),
                                 'development/body.txt': 'café 猫\r\n'}, 'checks': [{'path': 'result.txt'}]},
                    freeze_source(store, source, 'Current starter'), timeout=60)
                session = store.get(result['session'])
                self.assertTrue(result['passed'], result)
                self.assertEqual(Artifacts(store, session).read('result.txt'), 'café 猫\r\n'.encode())
                self.assertEqual(source_identity(candidate_source(store, session)), source_identity(source))
            finally:
                agent.close()

    def cli(self, workspace, cwd, *arguments, anchored=True):
        environment = dict(os.environ)
        environment['PYTHONPATH'] = str(ROOT)
        environment.pop('AUTOPROTEUS_WORKSPACE', None)
        if anchored:
            environment['AUTOPROTEUS_WORKSPACE'] = str(workspace)
        return subprocess.run([sys.executable, '-X', 'utf8', str(SEED), 'invoke', *arguments],
            cwd=cwd, env=environment, capture_output=True, text=True, timeout=20)

    def test_arguments_and_tool_paths_are_task_relative_from_either_directory(self):
        with temporary_directory() as directory:
            workspace = Path(directory) / 'task'; harness = workspace / 'harness'
            harness.mkdir(parents=True); (workspace / 'development').mkdir()
            (workspace / 'input.txt').write_bytes('café 猫\r\n'.encode())
            (harness / 'input.txt').write_text('Wrong directory')
            (workspace / 'development/args.json').write_text(json.dumps({'path': 'input.txt'}))
            for cwd in (workspace, harness):
                result = self.cli(workspace, cwd, '--tool', 'read_file', '--arguments-file', 'development/args.json')
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                value = json.loads(result.stdout)
                self.assertEqual(value['result']['content'], 'café 猫\r\n')
                self.assertEqual(value['result']['path'], 'input.txt')
            (workspace / 'development/write.json').write_text(json.dumps({'path': 'output.txt'}))
            (workspace / 'development/body.txt').write_bytes('saved\r\n猫'.encode())
            result = self.cli(workspace, harness, '--tool', 'write_file', '--arguments-file', 'development/write.json',
                              '--text-file', 'content', 'development/body.txt')
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((workspace / 'output.txt').read_bytes(), 'saved\r\n猫'.encode())
            self.assertFalse((harness / 'output.txt').exists())

    def test_task_boundary_still_applies_to_files_and_argument_loading(self):
        with temporary_directory() as directory:
            outside = Path(directory) / 'outside.txt'; outside.write_text('Unchanged')
            workspace = Path(directory) / 'task'; harness = workspace / 'harness'; harness.mkdir(parents=True)
            result = self.cli(workspace, harness, '--tool', 'read_file', '--arguments', json.dumps({'path': '../outside.txt'}))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('outside the session workspace', result.stdout)
            args = Path(directory) / 'outside.json'; args.write_text(json.dumps({'path': 'input.txt'}))
            result = self.cli(workspace, harness, '--tool', 'read_file', '--arguments-file', '../outside.json')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('outside the session workspace', result.stderr)
            self.assertEqual(outside.read_text(), 'Unchanged')

    def test_standalone_use_without_task_environment_keeps_current_directory(self):
        with temporary_directory() as directory:
            cwd = Path(directory); (cwd / 'input.txt').write_text('Standalone')
            result = self.cli(cwd.parent, cwd, '--tool', 'read_file', '--arguments', json.dumps({'path': 'input.txt'}), anchored=False)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(result.stdout)['result']['content'], 'Standalone')
