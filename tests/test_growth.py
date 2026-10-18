import json
import shlex
import unittest

from controller.evaluation import growth_scores, tool_use


class GrowthScoringTests(unittest.TestCase):
    def test_functional_growth_and_direct_routing_are_independent(self):
        usage = {'direct': [], 'development': ['first', 'second']}
        result = growth_scores(True, True, True, True, usage, ['first', 'second'])
        self.assertTrue(result['functional_growth'])
        self.assertFalse(result['direct_tool_use'])
        self.assertFalse(result['strict_route_success'])
        result = growth_scores(True, True, True, True, {'direct': ['first', 'second'], 'development': []}, ['first', 'second'])
        self.assertTrue(result['strict_route_success'])

    def test_correct_artifacts_do_not_prove_growth_without_verified_extension_and_use(self):
        for verified, preserved, used in ((False, True, ['new']), (True, False, ['new']), (True, True, [])):
            result = growth_scores(verified, preserved, True, True, {'direct': used, 'development': []}, ['new'])
            self.assertFalse(result['functional_growth'])
            self.assertTrue(result['task_completed_correctly'])

    def test_development_evidence_requires_successful_checker_invocation(self):
        output = json.dumps({'check': 'candidate tool invocation', 'passed': True, 'tool': 'new'})
        def event(command, ok=True):
            return {'type': 'action_result', 'data': {'ok': ok, 'action': {'tool': 'run_command',
                'arguments': {'command': command}}, 'result': {'exit_code': 0, 'output': output}}}
        command = "python3 harness/seed.py check --tool new --arguments '{}'"
        self.assertEqual(tool_use([event(command)])['development'], ['new'])
        for operation in ('check', 'invoke'):
            for arguments in ("--arguments '{}'", '--arguments-file arguments.json'):
                self.assertEqual(tool_use([event('python3 harness/seed.py ' + operation + ' --tool new ' + arguments)])['development'], ['new'])
        self.assertEqual(tool_use([event('echo fabricated'), event(command, False)])['development'], [])

    def test_python_development_route_is_parsed_as_data_and_requires_a_successful_top_level_call(self):
        def event(script, ok=True):
            return {'type': 'action_result', 'data': {'ok': ok, 'action': {'tool': 'run_command',
                'arguments': {'command': 'python3 -c ' + shlex.quote(script)}}, 'result': {'exit_code': 0}}}
        script = "from autoproteus.tools import Workspace\nresult = Workspace(Path.cwd()).execute('new', {})"
        self.assertEqual(tool_use([event(script)])['development'], ['new'])
        self.assertEqual(tool_use([event(script, False), event('if False:\n    ' + script.replace('\n', '\n    ')),
                                   event("print(\"Workspace(Path.cwd()).execute('fake', {})\")")])['development'], [])


if __name__ == '__main__':
    unittest.main()
