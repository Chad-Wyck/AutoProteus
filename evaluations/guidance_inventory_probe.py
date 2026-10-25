"""Held-out inventory contract checks. Candidate imports occur only in the guest."""
import json
import os
from pathlib import Path
import sys
import tempfile


def probe(workspace):
    from autoproteus.providers import tool_definitions
    root = workspace.root
    (root / 'records/archive').mkdir(parents=True)
    (root / 'records/a.txt').write_bytes('café\r\n'.encode())
    (root / 'records/z.bin').write_bytes(b'\x00\xff')
    (root / 'records/archive/old.txt').write_bytes(b'old')
    (root / 'records/.hidden').write_bytes(b'hidden')
    (root / 'empty').mkdir()
    outside = root.parent / 'outside'
    outside.mkdir()
    (outside / 'valid.txt').write_bytes(b'valid external file')
    (root / 'records/external.txt').symlink_to(outside / 'valid.txt')
    (root / 'records/external-dir').symlink_to(outside, target_is_directory=True)
    expected = [{'path': 'records/a.txt', 'bytes': len('café\r\n'.encode())},
                {'path': 'records/z.bin', 'bytes': 2}]
    snapshots = {path: path.read_bytes() for path in root.rglob('*') if path.is_file() and not path.is_symlink()}
    checks, errors = {}, {}

    def check(name, callback):
        try:
            checks[name] = bool(callback())
        except Exception as error:
            checks[name] = False
            errors[name] = type(error).__name__ + ': ' + str(error)[:300]

    def call(**arguments):
        return workspace.execute('inventory_files', arguments)

    def rejects(**arguments):
        try:
            call(**arguments)
        except (ValueError, OSError):
            return True
        return False

    def schema():
        definitions = [item['function'] for item in tool_definitions(False) if item['function']['name'] == 'inventory_files']
        if len(definitions) != 1:
            return False
        params = definitions[0]['parameters']
        return (params.get('type') == 'object' and params['properties']['path'].get('type') == 'string' and
                params['properties']['recursive'].get('type') == 'boolean' and not params.get('required', []))

    check('optional_argument_schema', schema)
    check('default_nonrecursive_bytes_sort_and_symlinks', lambda: call(path='records') == {'path': 'records', 'files': expected})
    check('explicit_false', lambda: call(path='records', recursive=False) == {'path': 'records', 'files': expected})
    recursive = sorted([*expected, {'path': 'records/archive/old.txt', 'bytes': 3}], key=lambda item: item['path'])
    check('recursive_true', lambda: call(path='records', recursive=True) == {'path': 'records', 'files': recursive})
    check('default_path', lambda: call() == {'path': '.', 'files': []})
    check('empty', lambda: call(path='empty') == {'path': 'empty', 'files': []})
    for value in (0, 1, None, 'false'):
        check('invalid_recursion_' + repr(value), lambda value=value: rejects(path='records', recursive=value))
    for path in ('missing', 'records/a.txt', '../outside', str(outside), 'records/external-dir'):
        check('invalid_path_' + path, lambda path=path: rejects(path=path))
    (root / 'many').mkdir()
    for index in range(200):
        (root / 'many' / str(index).zfill(3)).write_bytes(b'')
    many = {'path': 'many', 'files': [{'path': 'many/' + str(index).zfill(3), 'bytes': 0} for index in range(200)]}
    check('exact_200_default', lambda: call(path='many') == many)
    check('exact_200_recursive', lambda: call(path='many', recursive=True) == many)
    (root / 'many/200').write_bytes(b'')
    check('over_200', lambda: rejects(path='many'))
    check('over_200_recursive', lambda: rejects(path='many', recursive=True))
    check('inputs_unchanged', lambda: all(path.read_bytes() == raw for path, raw in snapshots.items()))
    return {'passed': all(checks.values()), 'checks': checks, 'errors': errors}


def main():
    if os.environ.get('AUTOPROTEUS_GUEST') != '1':
        raise RuntimeError('Run candidate checks only through a disposable AutoProteus VM')
    sys.path.insert(0, str(Path('harness').resolve()))
    from autoproteus.tools import Workspace
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        root = Path(directory) / 'task'
        root.mkdir()
        result = probe(Workspace(root))
    Path('guidance-probe-result.json').write_text(json.dumps(result), encoding='utf-8')


if __name__ == '__main__':
    main()
