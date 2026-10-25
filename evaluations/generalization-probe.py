"""Independent guest-only held-out contracts; never import candidates on the host."""
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path('harness').resolve()))
from autoproteus.tools import Workspace
from autoproteus.providers import tool_definitions, tool_instructions

feature = sys.argv[1]
root = Path('heldout-probe').resolve()
root.mkdir(exist_ok=True)
workspace = Workspace(root)
checks, errors = {}, {}


def check(name, callback):
    try:
        checks[name] = bool(callback())
    except Exception as error:
        checks[name] = False
        errors[name] = type(error).__name__ + ': ' + str(error)[:400]


def rejects(callback):
    try:
        callback()
        return False
    except (ValueError, OSError, TypeError, KeyError):
        return True


def call(path, **kwargs):
    return workspace.execute(feature, {'path': path, **kwargs})


definitions = {item['function']['name']: item['function'] for item in tool_definitions(False)}
check('registered', lambda: feature in definitions and feature + ':' in tool_instructions(False))
check('schema', lambda: definitions[feature]['parameters']['properties']['path']['type'] == 'string' and
      set(definitions[feature]['parameters']['required']) == {'path'} and
      (feature != 'csv_preview' or definitions[feature]['parameters']['properties']['limit']['type'] == 'integer'))

if feature == 'sha256_file':
    for name, raw in [('empty', b''), ('binary', b'\xff\x00\r\n' * 1300), ('exact', b'x' * 1048576)]:
        (root / name).write_bytes(raw)
        def verify(name=name, raw=raw):
            value = call(name)
            return (all(value[key] == expected for key, expected in {
                'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}.items()) and
                    (root / name).read_bytes() == raw)
        check(name, verify)
    (root / 'large').write_bytes(b'x' * 1048577)
    check('oversized', lambda: rejects(lambda: call('large')))
elif feature == 'csv_preview':
    check('optional_limit_schema', lambda: definitions[feature]['parameters']['properties']['limit']['type'] == 'integer' and
          'limit' not in definitions[feature]['parameters']['required'])
    for name, text in [('empty', ''), ('quoted', 'id,value\r\n1,"café, 猫"\r\n2,"two\r\nlines"\r\n'),
                       ('exact', 'x' * 100000), ('unicode_exact', '猫' * 100000), ('many', 'x\n' * 25)]:
        raw = text.encode()
        (root / name).write_bytes(raw)
        rows = list(csv.reader(io.StringIO(text, newline='')))
        for limit in (1, 5, 20):
            def verify(name=name, raw=raw, rows=rows, limit=limit):
                value = call(name, limit=limit)
                return (value['path'] == name and value['rows'] == rows[:limit] and
                        value['truncated'] is (len(rows) > limit) and (root / name).read_bytes() == raw)
            check(name + '_' + str(limit), verify)
    check('default_limit', lambda: call('many')['rows'] == [['x']] * 5)
    for limit in (1, 5, 20):
        raw = b'x\n' * (limit + 1)
        (root / 'one-extra').write_bytes(raw)
        def verify_extra(limit=limit, raw=raw):
            value = call('one-extra', limit=limit)
            return (value['path'] == 'one-extra' and value['rows'] == [['x']] * limit and
                    value['truncated'] is True and (root / 'one-extra').read_bytes() == raw)
        check('one_extra_' + str(limit), verify_extra)
    for limit in (0, 21, True, '5', None):
        check('invalid_limit_' + repr(limit), lambda limit=limit: rejects(lambda: call('many', limit=limit)))
    (root / 'bad').write_bytes(b'\xff')
    (root / 'large').write_bytes(b'x' * 100001)
    (root / 'unicode_large').write_bytes(('猫' * 100001).encode())
    for name in ('bad', 'large', 'unicode_large'):
        check('reject_' + name, lambda name=name: rejects(lambda: call(name)))
elif feature == 'format_json':
    for name, text in [('object', '{"z":1,"é":[2,{"a":true}]}'), ('array', '[1, false, null]'),
                       ('scalar', '"猫"'), ('exact', '"' + 'x' * 99998 + '"'),
                       ('unicode_output_exact', '"' + '猫' * 99997 + '"')]:
        (root / name).write_bytes(text.encode())
        expected = (json.dumps(json.loads(text), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
        if len(expected.decode()) > 100000:
            check(name + '_output_limit', lambda name=name: rejects(lambda: call(name)) and
                  (root / name).read_bytes() == text.encode())
        else:
            def verify(name=name, expected=expected):
                value = call(name)
                return value['path'] == name and value['bytes'] == len(expected) and (root / name).read_bytes() == expected
            check(name, verify)
            check(name + '_idempotent', verify)
    for name, raw in [('invalid', b'{bad'), ('utf8', b'\xff'), ('large', b' ' * 100001),
                       ('expanded', ('[' + ','.join(['0'] * 30000) + ']').encode())]:
        (root / name).write_bytes(raw)
        check('preserve_' + name, lambda name=name, raw=raw: rejects(lambda: call(name)) and
              (root / name).read_bytes() == raw)
else:
    raise ValueError('Unknown held-out feature')

(root / 'directory').mkdir(exist_ok=True)
outside = root.parent / 'outside-heldout.txt'
outside_raw = b'{"outside":1}'
outside.write_bytes(outside_raw)
(root / 'escape').symlink_to(outside)
for name in ('directory', 'missing', '../outside-heldout.txt', 'escape'):
    check('reject_path_' + name, lambda name=name: rejects(lambda: call(name)))
check('outside_preserved', lambda: outside.read_bytes() == outside_raw)
suite = subprocess.run([sys.executable, 'harness/seed.py', 'check'], capture_output=True, text=True, timeout=60)
report = {'feature': feature, 'checks': checks, 'errors': errors,
          'suite': {'exit_code': suite.returncode, 'output': (suite.stdout + suite.stderr)[-6000:]}}
report['passed'] = bool(checks and all(checks.values()) and suite.returncode == 0)
Path('heldout-result.json').write_text(json.dumps(report, ensure_ascii=True))
