"""Trusted calibration fixture, run only inside a disposable VM."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path('harness').resolve()))
from autoproteus.tools import Workspace
from autoproteus.providers import tool_definitions, tool_instructions

root = Path('navigation-fixtures').resolve()
root.mkdir()
workspace = Workspace(root)
text = '# café 猫\r\nraise RuntimeError("never execute source")\r\n@decorator\r\nclass Example:\r\n    def method(self):\r\n        return "猫"\r\n'
(root / 'sample.py').write_bytes(text.encode())
value = workspace.execute('source_outline', {'path': 'sample.py'})
checks = {'registered_native': any(tool['function']['name'] == 'source_outline' for tool in tool_definitions()),
          'registered_json': 'source_outline:' in tool_instructions(),
          'names': [item['name'] for item in value['definitions']] == ['Example', 'Example.method'],
          'preserved_bytes': (root / 'sample.py').read_bytes() == text.encode()}
for entry in value['definitions']:
    section = workspace.execute('read_section', {'path': 'sample.py', 'start': entry['start'], 'length': entry['length']})
    expected = text[text.index('@decorator'):] if entry['name'] == 'Example' else text[text.index('    def method'):]
    checks[entry['name'] + '_section'] = section['content'] == expected
outside = root.parent / 'outside.py'
outside.write_text('def hidden(): pass')
(root / 'escape.py').symlink_to(outside)
for path in ('../outside.py', 'escape.py'):
    try:
        workspace.execute('source_outline', {'path': path})
        checks['reject_' + path] = False
    except ValueError:
        checks['reject_' + path] = True
Path('navigation-result.json').write_text(json.dumps({'passed': all(checks.values()), 'checks': checks}))
