"""Protected, guest-only checks of a model-selected inventory capability.

The controller supplies this program and declaration to a fresh disposable VM.
Never import a candidate harness on the host.
"""
import copy
import json
from pathlib import Path
import sys


CASES = [
    ('sku\tunits\npear\t2\napple\t3\npear\t4\n', 'sku\tunits\napple\t1\nplum\t0\n'),
    ('sku\tunits\n猫\t7\n雪\t1\n', 'sku\tunits\n猫\t2\n'),
    ('sku\tunits\n', 'sku\tunits\nsolo\t11\n'),
]


def expected(a, b):
    import csv
    import io
    counts = {}
    for text in (a, b):
        for row in csv.DictReader(io.StringIO(text), delimiter='\t'):
            counts[row['sku']] = counts.get(row['sku'], 0) + int(row['units'])
    return {'items': [{'sku': sku, 'units': counts[sku]} for sku in sorted(counts)],
            'total_units': sum(counts.values())}


def arguments(value, paths):
    if isinstance(value, str):
        return paths.get(value, value)
    if isinstance(value, list):
        return [arguments(item, paths) for item in value]
    if isinstance(value, dict):
        return {key: arguments(item, paths) for key, item in value.items()}
    return value


def main():
    sys.path.insert(0, str(Path('harness').resolve()))
    from autoproteus.tools import Workspace
    from autoproteus.providers import tool_definitions
    declaration = json.loads(Path('discovery-declaration.json').read_text(encoding='utf-8'))
    definitions = {entry['function']['name']: entry['function'] for entry in tool_definitions(False)}
    checks = {'registered': declaration['tool'] in definitions}
    params = definitions.get(declaration['tool'], {}).get('parameters', {})
    supplied = declaration['arguments']
    checks['declared_arguments'] = (set(params.get('required', [])) <= set(supplied) <= set(params.get('properties', {})))
    root = Path.cwd(); workspace = Workspace(root)
    for i, (a, b) in enumerate(CASES):
        folder = root / ('heldout-' + str(i)); folder.mkdir()
        pa, pb, output = (folder / name for name in ('branch-a.tsv', 'branch-b.tsv', 'summary.json'))
        pa.write_bytes(a.encode()); pb.write_bytes(b.encode())
        paths = {'@INPUT_A': pa.relative_to(root).as_posix(), '@INPUT_B': pb.relative_to(root).as_posix(),
                 '@OUTPUT': output.relative_to(root).as_posix()}
        try:
            workspace.execute(declaration['tool'], arguments(copy.deepcopy(declaration['arguments']), paths))
            checks['case_' + str(i)] = json.loads(output.read_text(encoding='utf-8')) == expected(a, b)
        except Exception:
            checks['case_' + str(i)] = False
        checks['preserved_' + str(i)] = pa.read_bytes() == a.encode() and pb.read_bytes() == b.encode()
    Path('discovery-result.json').write_text(json.dumps({'passed': all(checks.values()), 'checks': checks}))


if __name__ == '__main__': main()
