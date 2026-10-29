"""The editable guest entry point. The protected host never imports this file."""
def run(root, store, settings, client_factory, session, message=None):
    from autoproteus.agent import Agent
    agent = Agent(root, store, settings, client_factory)
    agent.start(session, message)
    return agent


def workspace_root():
    """Development paths use the running task root, independent of shell cwd."""
    import os
    from pathlib import Path
    return Path(os.environ.get('AUTOPROTEUS_WORKSPACE') or Path.cwd())


def invoke(tool, arguments):
    """Try an edited tool without requiring its development tests to pass."""
    import json
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from autoproteus.providers import tool_definitions
    from autoproteus.tools import Workspace
    try:
        definitions = {item['function']['name']: item['function'] for item in tool_definitions(False)}
        if tool == 'finish' or tool not in definitions:
            raise ValueError('The requested workspace tool must be registered in TOOL_SPECS')
        required = definitions[tool]['parameters']['required']
        if not isinstance(arguments, dict) or any(key not in arguments for key in required):
            raise ValueError('Supply a JSON argument object containing the required tool arguments')
        value = Workspace(workspace_root()).execute(tool, arguments)
        print(json.dumps({'check': 'candidate tool invocation', 'passed': True, 'tool': tool, 'result': value}, ensure_ascii=True))
        return 0
    except Exception as error:
        print(json.dumps({'check': 'candidate tool invocation', 'passed': False, 'tool': tool,
                          'error': type(error).__name__ + ': ' + str(error)}, ensure_ascii=True))
        return 1


def check(tool=None, arguments=None, test=None):
    """Development feedback from the editable copy, executed only where invoked."""
    import io
    import json
    from pathlib import Path
    import sys
    import unittest

    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    pattern = 'test_*.py'
    if test is not None:
        selected = Path(test)
        if (selected.parent != Path('tests') or not selected.stem.startswith('test_') or
                not selected.stem.isidentifier() or selected.suffix != '.py' or
                not (root / selected).resolve().is_relative_to((root / 'tests').resolve())):
            raise ValueError('Select one tests/test_NAME.py file inside this seed')
        if tool:
            raise ValueError('Focused checks cannot invoke tools. Use invoke separately, then run the full check.')
        pattern = selected.name
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=pattern)
    result = unittest.TextTestRunner(stream=log, verbosity=1, buffer=True).run(suite)
    passed = result.wasSuccessful() and result.testsRun > len(result.skipped)
    print(json.dumps({'check': 'candidate tests' if test is None else 'candidate focused tests',
                      'scope': 'full' if test is None else 'focused', 'selection': test,
                      'passed': passed, 'tests': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}))
    if not passed:
        # Put the summary first and bound traces so the model sees useful failures.
        for case, trace in (result.failures + result.errors)[:3]:
            print(str(case) + '\n' + trace[-2400:])
        if not result.testsRun:
            print('No tests were discovered. Add tests/test_*.py with unittest test methods.')
        elif result.testsRun == len(result.skipped):
            print('Every discovered test was skipped; no test executed.')
        return 1
    if tool:
        if invoke(tool, arguments):
            return 1
    if test is not None:
        print('Focused repair check only. Run python3 harness/seed.py check before requesting activation.')
    print('These are development checks, not independent upgrade approval. Inspect the result and test boundary cases.')
    return 0


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Test or invoke the edited seed in its current environment.')
    parser.add_argument('command', choices=['check', 'invoke'])
    parser.add_argument('--test', metavar='tests/test_NAME.py', help='Check only this file while repairing; the full check is still required')
    parser.add_argument('--tool', help='Registered file tool from this edited copy, in the current workspace')
    arguments = parser.add_mutually_exclusive_group()
    arguments.add_argument('--arguments', type=json.loads, help='JSON object for --tool; use a disposable test file')
    arguments.add_argument('--arguments-file', help='Workspace UTF-8 JSON argument object, at most 100000 characters')
    parser.add_argument('--text-file', nargs=2, action='append', default=[], metavar=('ARGUMENT', 'FILE'),
                        help='Load one text argument from an ordinary workspace UTF-8 file; repeat for other arguments')
    args = parser.parse_args()
    if args.test is not None and (args.command != 'check' or args.tool):
        parser.error('--test is for focused checks only; use invoke separately or run the full check with --tool')
    if args.arguments_file or args.text_file:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from autoproteus.tools import Workspace
        try:
            workspace = Workspace(workspace_root())
            if args.arguments_file:
                args.arguments = json.loads(workspace.read_text(args.arguments_file))
            if args.text_file:
                if args.arguments is None:
                    args.arguments = {}
                if not isinstance(args.arguments, dict):
                    raise ValueError('Tool arguments must be a JSON object')
                for name, path in args.text_file:
                    if name in args.arguments:
                        raise ValueError('Each text argument must have a unique name and must not replace a supplied argument')
                    args.arguments[name] = workspace.read_text(path)
        except (ValueError, OSError) as error:
            parser.error(str(error))
    if bool(args.tool) != (args.arguments is not None):
        parser.error('--tool and either --arguments or --arguments-file must be supplied together')
    if args.command == 'invoke' and not args.tool:
        parser.error('invoke requires --tool and arguments')
    if args.tool and not isinstance(args.arguments, dict):
        parser.error('Tool arguments must be a JSON object')
    try:
        code = invoke(args.tool, args.arguments) if args.command == 'invoke' else check(args.tool, args.arguments, args.test)
    except ValueError as error:
        parser.error(str(error))
    raise SystemExit(code)
