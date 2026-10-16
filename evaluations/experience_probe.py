"""Independent feature checks. Execute only inside the disposable verifier VM."""
import json
from pathlib import Path
import sys
sys.path.insert(0, 'harness')
from autoproteus.tools import Workspace

name = sys.argv[1]
root = Path.cwd()
workspace = Workspace(root)
checks = []


def case(text, expected, label):
    path = root / 'probe.txt'
    path.write_bytes(text.encode())
    before = path.read_bytes()
    try:
        result = workspace.execute(name, {'path': 'probe.txt'})
        checks.append({'name': label, 'passed': result == {'path': 'probe.txt', **expected} and path.read_bytes() == before})
    except Exception as error:
        checks.append({'name': label, 'passed': False, 'error': type(error).__name__})


def reject(path, label):
    original = (root / 'probe.txt').read_bytes()
    try:
        workspace.execute(name, {'path': path})
        passed = False
    except (ValueError, OSError, UnicodeError):
        passed = True
    checks.append({'name': label, 'passed': passed and (root / 'probe.txt').read_bytes() == original})


if name == 'line_count':
    for text in ('', 'cat', 'cat\n', '猫\r\ncafé\rnext\u2028last', '\n\n'):
        case(text, {'lines': len(text.splitlines())}, 'lines-' + repr(text))
elif name == 'json_keys':
    for text in ('{}', '{"z":1,"a":[2],"é":"猫"}', '{"b":0,"a":1,"b":2}'):
        case(text, {'keys': sorted(json.loads(text))}, 'keys-' + text)
    for text in ('[]', 'null', 'true', '1', '"text"', '{bad'):
        (root / 'probe.txt').write_text(text)
        reject('probe.txt', 'not-object-' + text)
elif name == 'text_counts':
    for text in ('', ' a  b\n猫 ', 'café\r\n猫\tend', '\n\n', 'é\u0301'):
        case(text, {'characters': len(text), 'words': len(text.split()), 'lines': len(text.splitlines())}, 'counts-' + repr(text))
else:
    raise ValueError('Unknown protected contract')
(root / 'probe.txt').write_bytes(b'\xff')
reject('probe.txt', 'invalid-utf8')
(root / 'probe.txt').write_text('x' * 100001)
reject('probe.txt', 'oversized')
(root / 'probe.txt').write_text('preserved')
outside = root.parent / 'outside.txt'
# The escaped target must be valid input, so parsing cannot impersonate a
# workspace-boundary rejection. Create it before traversal AND symlink checks.
outside_raw = b'{"outside":1}'
outside.write_bytes(outside_raw)
for path in ('missing.txt', '.', '../outside.txt', '/etc/passwd'):
    reject(path, path)
(root / 'escape.txt').symlink_to(outside)
reject('escape.txt', 'escaping-link')
checks.append({'name': 'outside-preserved', 'passed': outside.read_bytes() == outside_raw})
if name == 'json_keys':
    # Both cases are valid JSON. Invalid JSON above the limit could be rejected
    # by parsing alone and would not exercise the character bound.
    for size in (100000, 100001):
        text = '{"key":"' + '猫' * (size - len('{"key":""}')) + '"}'
        assert len(text) == size and len(text.encode('utf-8')) > 100000
        if size == 100000:
            case(text, {'keys': ['key']}, 'unicode-character-bound')
        else:
            (root / 'probe.txt').write_bytes(text.encode('utf-8'))
            reject('probe.txt', 'unicode-character-over-bound')
else:
    expected = {'lines': 1} if name == 'line_count' else {'characters': 100000, 'words': 1, 'lines': 1}
    case('猫' * 100000, expected, 'unicode-character-bound')
Path('experience-probe-result.json').write_text(json.dumps({'passed': all(item['passed'] for item in checks), 'checks': checks}))
