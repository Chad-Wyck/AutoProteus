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
        for name in ('__init__.py', 'providers.py', 'tools.py', 'search.py', 'terminal.py', 'file_ops.py'):
            shutil.copyfile(ROOT / 'autoproteus' / name, self.seed / 'autoproteus' / name)
        self.test_file = self.seed / 'tests/test_example.py'
        self.test_file.write_text('import unittest\nclass Example(unittest.TestCase):\n def test_example(self): self.assertTrue(True)\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def command(self, command, *arguments):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(self.seed / 'seed.py'), command, *arguments],
                              cwd=self.workspace, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding='utf-8', timeout=20,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def check(self, *arguments):
        return self.command('check', *arguments)

    def test_invoke_accepts_a_workspace_arguments_file_despite_failing_tests(self):
        self.test_file.write_text('raise RuntimeError("deliberately broken tests")\n', encoding='utf-8')
        (self.workspace / 'arguments.json').write_text(json.dumps({'path': 'result.txt', 'content': '猫\r\né'}), encoding='utf-8')
        result = self.command('invoke', '--tool', 'write_file', '--arguments-file', 'arguments.json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.workspace / 'result.txt').read_bytes(), '猫\r\né'.encode())
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertEqual(self.check().returncode, 1)

    def test_invocation_rejects_escaping_files_invalid_objects_and_terminal_access(self):
        (self.workspace / 'invalid.json').write_text('[]', encoding='utf-8')
        (self.workspace / 'large.json').write_text(' ' * 100001, encoding='utf-8')
        for arguments in [('--arguments-file', '../outside.json'), ('--arguments-file', 'invalid.json'),
                          ('--arguments-file', 'large.json'), ('--arguments', 'null'),
                          ('--arguments', '{}', '--arguments-file', 'invalid.json')]:
            with self.subTest(arguments=arguments):
                result = self.command('invoke', '--tool', 'write_file', *arguments)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.command('invoke', '--tool', 'run_command', '--arguments', '{"command":"echo forbidden"}')
        self.assertEqual(result.returncode, 1)
        self.assertIn('TOOL_SPECS', result.stdout)

    def test_text_file_arguments_preserve_code_quotes_unicode_and_line_endings(self):
        code = 'print("猫\\n")\r\n# literal </parameter> and "quotes"\r\n'
        (self.workspace / 'body.txt').write_bytes(code.encode())
        (self.workspace / 'args.json').write_text('{"path":"code.py"}', encoding='utf-8')
        result = self.command('invoke', '--tool', 'write_file', '--arguments-file', 'args.json',
                              '--text-file', 'content', 'body.txt')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.workspace / 'code.py').read_bytes(), code.encode())
        self.assertEqual(json.loads(result.stdout)['result']['bytes'], len(code.encode()))

    def test_two_raw_fragments_edit_one_exact_section_without_inline_json(self):
        original = 'before\r\nprint("old")\r\nafter\r\n'
        (self.workspace / 'code.py').write_bytes(original.encode())
        for path, content in [('path.txt', 'code.py'), ('old.txt', 'print("old")\r\n'),
                              ('new.txt', 'print("猫\\n")\r\n')]:
            (self.workspace / path).write_bytes(content.encode())
        result = self.command('invoke', '--tool', 'edit_file', '--text-file', 'path', 'path.txt',
                              '--text-file', 'old_text', 'old.txt', '--text-file', 'new_text', 'new.txt')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.workspace / 'code.py').read_bytes(), original.replace('print("old")', 'print("猫\\n")').encode())

    def test_text_argument_names_follow_the_registered_schema_not_python_identifier_rules(self):
        providers = self.seed / 'autoproteus/providers.py'
        providers.write_text(providers.read_text(encoding='utf-8').replace('TOOL_SPECS = {',
            'TOOL_SPECS = {\n    "fixture_echo": ("Echo text.", {"new-value": STRING}, ["new-value"]),'), encoding='utf-8')
        tools = self.seed / 'autoproteus/tools.py'
        tools.write_text(tools.read_text(encoding='utf-8').replace('        if tool == "list_files":',
            '        if tool == "fixture_echo":\n            return {"text": args["new-value"]}\n        if tool == "list_files":'), encoding='utf-8')
        (self.workspace / 'fragment.txt').write_text('猫 "quotes"', encoding='utf-8')
        result = self.command('invoke', '--tool', 'fixture_echo', '--text-file', 'new-value', 'fragment.txt')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['result']['text'], '猫 "quotes"')

    def test_text_files_reject_conflicts_oversize_invalid_text_and_existing_external_files_before_writing(self):
        (self.workspace / 'good.txt').write_text('content', encoding='utf-8')
        (self.workspace / 'large.txt').write_text('猫' * 100001, encoding='utf-8')
        (self.workspace / 'invalid.txt').write_bytes(b'\xff')
        (self.workspace / 'output.txt').write_bytes(b'preserve')
        with temporary_directory() as directory:
            outside = Path(directory) / 'outside.txt'
            outside.write_text('valid external content', encoding='utf-8')
            fixtures = [('--text-file', 'content', path) for path in
                        ('large.txt', 'invalid.txt', 'missing.txt', '.', str(outside))]
            fixtures += [('--text-file', 'content', 'good.txt', '--text-file', 'content', 'good.txt'),
                         ('--text-file', 'path', 'good.txt'), ('--text-file', 'bad-name', 'good.txt')]
            for extra in fixtures:
                with self.subTest(extra=extra):
                    result = self.command('invoke', '--tool', 'write_file', '--arguments', '{"path":"output.txt"}', *extra)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual((self.workspace / 'output.txt').read_bytes(), b'preserve')
            self.assertEqual(outside.read_text(), 'valid external content')

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

    def test_focused_check_isolates_one_file_without_approving_the_full_suite(self):
        (self.seed / 'tests/test_unrelated.py').write_text('raise RuntimeError("unrelated import failure")\n', encoding='utf-8')
        focused = self.check('--test', 'tests/test_example.py')
        self.assertEqual(focused.returncode, 0, focused.stdout + focused.stderr)
        record = json.loads(focused.stdout.splitlines()[0])
        self.assertEqual(record['check'], 'candidate focused tests')
        self.assertEqual(record['scope'], 'focused')
        self.assertEqual(record['selection'], 'tests/test_example.py')
        self.assertEqual(record['tests'], 1)
        self.assertIn('before requesting activation', focused.stdout)
        full = self.check()
        self.assertNotEqual(full.returncode, 0)
        self.assertEqual(json.loads(full.stdout.splitlines()[0])['scope'], 'full')
        self.assertIn('unrelated import failure', full.stdout)

    def test_focused_check_preserves_the_actual_failure_and_rejects_empty_or_skipped_selections(self):
        self.test_file.write_text('import unittest\nclass Example(unittest.TestCase):\n def test_example(self): self.assertEqual(1, 2, "contract mismatch")\n', encoding='utf-8')
        failed = self.check('--test', 'tests/test_example.py')
        self.assertEqual(failed.returncode, 1)
        self.assertIn('contract mismatch', failed.stdout)
        missing = self.check('--test', 'tests/test_missing.py')
        self.assertEqual(missing.returncode, 1)
        self.assertIn('No tests were discovered', missing.stdout)
        self.test_file.write_text('import unittest\n@unittest.skip("fixture")\nclass Example(unittest.TestCase):\n def test_example(self): pass\n', encoding='utf-8')
        for arguments in ((), ('--test', 'tests/test_example.py')):
            with self.subTest(arguments=arguments):
                skipped = self.check(*arguments)
                self.assertEqual(skipped.returncode, 1)
                self.assertFalse(json.loads(skipped.stdout.splitlines()[0])['passed'])
                self.assertIn('no test executed', skipped.stdout)

    def test_focused_check_rejects_traversal_patterns_and_tool_invocation(self):
        outside = self.workspace / 'test_outside.py'
        outside.write_text('raise RuntimeError("outside selection executed")\n', encoding='utf-8')
        for selection in ('../test_outside.py', str(outside), 'tests/../test_outside.py',
                          'tests/test_*.py', 'tests/test_example.py/extra', 'tests/example.py'):
            with self.subTest(selection=selection):
                result = self.check('--test', selection)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('outside selection executed', result.stderr)
        for command in ('check', 'invoke'):
            result = self.command(command, '--test', 'tests/test_example.py', '--tool', 'write_file',
                                  '--arguments', '{"path":"never.txt","content":"bad"}')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse((self.workspace / 'never.txt').exists())

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
