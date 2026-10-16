"""Development-check CLI tests use only hand-written fixtures, never submitted candidates."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from controller.config import Settings
from controller.isolation import Broker
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]


class SeedRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.workspace = Path(self.temp.name)
        self.seed = self.workspace / 'harness'
        (self.seed / 'autoproteus').mkdir(parents=True)
        (self.seed / 'tests').mkdir()
        shutil.copyfile(ROOT / 'seed.py', self.seed / 'seed.py')
        for name in ('__init__.py', 'providers.py', 'tools.py', 'search.py', 'terminal.py'):
            shutil.copyfile(ROOT / 'autoproteus' / name, self.seed / 'autoproteus' / name)
        self.test_file = self.seed / 'tests/test_example.py'
        self.test_file.write_text('import unittest\nclass Example(unittest.TestCase):\n def test_example(self): self.assertTrue(True)\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def check(self, *arguments):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(self.seed / 'seed.py'), 'check', *arguments],
                              cwd=self.workspace, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding='utf-8', timeout=20,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def test_check_reports_tests_and_invokes_the_edited_registered_tool(self):
        # Deliberately add a tool to the fixture copy, not to the starter modules.
        tools = self.seed / 'autoproteus/tools.py'
        tools.write_text(tools.read_text(encoding='utf-8').replace('        if tool == "list_files":',
            '        if tool == "fixture_echo":\n            return {"edited_copy": True, "text": args["text"]}\n        if tool == "list_files":'), encoding='utf-8')
        arguments = json.dumps({'text': '猫\r\né'})
        failed = self.check('--tool', 'fixture_echo', '--arguments', arguments)
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn('TOOL_SPECS', failed.stdout)
        providers = self.seed / 'autoproteus/providers.py'
        providers.write_text(providers.read_text(encoding='utf-8').replace('TOOL_SPECS = {',
            'TOOL_SPECS = {\n    "fixture_echo": ("Echo a fixture.", {"text": STRING}, ["text"]),'), encoding='utf-8')
        passed = self.check('--tool', 'fixture_echo', '--arguments', arguments)
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        records = [json.loads(line) for line in passed.stdout.splitlines() if line.startswith('{')]
        self.assertEqual(records[0]['tests'], 1)
        self.assertTrue(records[1]['result']['edited_copy'])
        self.assertEqual(records[1]['result']['text'], '猫\r\né')

    def test_failed_or_empty_suite_cannot_pass_or_execute_a_tool(self):
        self.test_file.write_text('import unittest\nclass Example(unittest.TestCase):\n def test_example(self): self.assertEqual(1, 2, "boundary failure")\n', encoding='utf-8')
        result = self.check('--tool', 'write_file', '--arguments', '{"path":"never.txt","content":"bad"}')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('boundary failure', result.stdout)
        self.assertFalse((self.workspace / 'never.txt').exists())
        self.test_file.unlink()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('No tests were discovered', result.stdout)

    def test_invalid_arguments_fail_without_writing_and_valid_call_preserves_unicode(self):
        result = self.check('--tool', 'write_file', '--arguments', '{}')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('required tool arguments', result.stdout)
        result = self.check('--tool', 'write_file', '--arguments', json.dumps({'path': 'sample.txt', 'content': '猫\r\né'}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.workspace / 'sample.txt').read_bytes(), '猫\r\né'.encode('utf-8'))

    def test_new_limits_preserve_saved_preferences_and_broker_has_final_status_room(self):
        settings = Settings(self.workspace / 'settings')
        self.assertEqual(settings.values['max_steps'], 128)
        self.assertEqual(settings.values['context_tokens'], 32768)
        self.assertEqual(settings.values['response_tokens'], 8192)
        settings.update({'max_steps': 32, 'context_tokens': 8192, 'response_tokens': 2048})
        restored = Settings(settings.directory)
        self.assertEqual(restored.values['max_steps'], 32)
        self.assertEqual(restored.values['response_tokens'], 2048)
        import threading
        from controller.storage import Store
        store = Store(self.workspace / 'sessions')
        session = store.create('Quota check', 'demo', 'fixture')
        broker = Broker(store, session, None, {**restored.values, 'max_steps': 1}, threading.Event())
        self.assertEqual(broker.request_limit, 6)  # one tool and finish, each with two repairs


if __name__ == '__main__':
    unittest.main()
