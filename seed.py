"""The editable guest entry point. The protected host never imports this file."""
def run(root, store, settings, client_factory, session, message=None):
    from autoproteus.agent import Agent
    agent = Agent(root, store, settings, client_factory)
    agent.start(session, message)
    return agent


def check(tool=None, arguments=None):
    """Development feedback from the editable copy, executed only where invoked."""
    import io
    import json
    from pathlib import Path
    import sys
    import unittest

    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    from autoproteus.providers import tool_definitions, tool_instructions
    from autoproteus.tools import Workspace
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(stream=log, verbosity=1, buffer=True).run(suite)
    passed = result.wasSuccessful() and result.testsRun > 0
    print(json.dumps({'check': 'candidate tests', 'passed': passed, 'tests': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}))
    if not passed:
        # Put the summary first and bound traces so the model sees useful failures.
        for test, trace in (result.failures + result.errors)[:3]:
            print(str(test) + '\n' + trace[-2400:])
        if not result.testsRun:
            print('No tests were discovered. Add tests/test_*.py with unittest test methods.')
        return 1
    if tool:
        try:
            definitions = {item['function']['name']: item['function'] for item in tool_definitions(False)}
            if tool == 'finish' or tool not in definitions or tool + ':' not in tool_instructions(False):
                raise ValueError('The requested workspace tool must be registered in TOOL_SPECS for both protocols')
            required = definitions[tool]['parameters']['required']
            if not isinstance(arguments, dict) or any(key not in arguments for key in required):
                raise ValueError('Supply a JSON argument object containing the required tool arguments')
            value = Workspace(Path.cwd()).execute(tool, arguments)
            print(json.dumps({'check': 'candidate tool invocation', 'passed': True, 'tool': tool, 'result': value}, ensure_ascii=True))
        except Exception as error:
            print(json.dumps({'check': 'candidate tool invocation', 'passed': False, 'tool': tool,
                              'error': type(error).__name__ + ': ' + str(error)}, ensure_ascii=True))
            return 1
    print('These are development checks, not independent upgrade approval. Inspect the result and test boundary cases.')
    return 0


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Check the edited seed in its current environment.')
    parser.add_argument('command', choices=['check'])
    parser.add_argument('--tool', help='Also invoke one registered file tool from this edited copy, in the current workspace')
    parser.add_argument('--arguments', type=json.loads, help='JSON object for --tool; use a disposable test file')
    args = parser.parse_args()
    if bool(args.tool) != (args.arguments is not None):
        parser.error('--tool and --arguments must be supplied together')
    raise SystemExit(check(args.tool, args.arguments))
