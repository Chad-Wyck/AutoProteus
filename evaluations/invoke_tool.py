"""Opt-in development invocation. Run only inside the guest, never on the host."""
import json
from pathlib import Path
import sys


def main():
    sys.path.insert(0, str(Path('harness').resolve()))
    from autoproteus.providers import tool_definitions
    from autoproteus.tools import Workspace
    tool, arguments = sys.argv[1], json.loads(sys.argv[2])
    definitions = {entry['function']['name']: entry['function'] for entry in tool_definitions(False)}
    if tool == 'finish' or tool not in definitions or not isinstance(arguments, dict):
        raise ValueError('Use a registered workspace tool and a JSON argument object')
    if any(key not in arguments for key in definitions[tool]['parameters']['required']):
        raise ValueError('Missing required tool arguments')
    result = Workspace(Path.cwd()).execute(tool, arguments)
    print(json.dumps({'check': 'development tool invocation', 'passed': True, 'tool': tool, 'result': result}, ensure_ascii=True))
    print('Invocation only. Read the resulting file and compare exact expected contents; run the full suite separately.')


if __name__ == '__main__':
    main()
