"""Public handoff checks. Safe to copy into a guest; imports no candidate code."""
import ast
import json
from pathlib import Path

ROLES = {'@INPUT_A', '@INPUT_B', '@OUTPUT'}
EXAMPLE = {'tool':'your_chosen_name', 'arguments':{
    'your_first_input':'@INPUT_A', 'your_second_input':'@INPUT_B', 'your_destination':'@OUTPUT'}}


def structural_issues(value, providers=None):
    issues = []
    if not isinstance(value, dict) or set(value) != {'tool', 'arguments'}:
        return ['Use exactly the keys tool and arguments.']
    tool, args = value['tool'], value['arguments']
    if not isinstance(tool, str) or not tool or len(tool) > 64 or not all(c.isascii() and (c.isalnum() or c in '_-') for c in tool) or tool == 'finish':
        issues.append('tool must name your newly registered tool.')
    if not isinstance(args, dict):
        return issues + ['arguments must be a JSON object.']
    leaves, keys = [], []
    def visit(item):
        if isinstance(item, str): leaves.append(item)
        elif isinstance(item, list):
            for entry in item: visit(entry)
        elif isinstance(item, dict):
            keys.extend(item)
            for entry in item.values(): visit(entry)
    visit(args)
    if ROLES & set(keys):
        issues.append('Placeholders are argument VALUES, not keys. Keep your own parameter names as keys.')
    if not ROLES <= set(leaves):
        issues.append('Argument values must include @INPUT_A, @INPUT_B and @OUTPUT; do not substitute actual task paths.')
    if providers is not None:
        try:
            tree = ast.parse(providers)
            matches = [entry for node in ast.walk(tree) if isinstance(node, ast.Dict)
                       for key, entry in zip(node.keys, node.values) if isinstance(key, ast.Constant) and key.value == tool]
            if not matches:
                issues.append('The chosen name was not found in the edited tool declarations.')
            elif isinstance(matches[0], (ast.Tuple, ast.List)) and len(matches[0].elts) == 3:
                properties, required = matches[0].elts[1:]
                if isinstance(properties, ast.Dict) and all(isinstance(key, ast.Constant) and isinstance(key.value, str) for key in properties.keys):
                    allowed = {key.value for key in properties.keys}
                    if set(args)-allowed: issues.append('Undeclared top-level argument names: ' + ', '.join(sorted(set(args)-allowed)))
                if isinstance(required, ast.List) and all(isinstance(entry, ast.Constant) and isinstance(entry.value, str) for entry in required.elts):
                    missing = {entry.value for entry in required.elts}-set(args)
                    if missing: issues.append('Missing required arguments: ' + ', '.join(sorted(missing)))
        except (SyntaxError, ValueError, RecursionError):
            issues.append('The edited providers.py must parse before submission.')
    return issues


def check(workspace):
    workspace = Path(workspace).resolve()
    try:
        path = workspace/'capability.json'
        if not path.resolve().is_relative_to(workspace): raise ValueError('Declaration must stay in the workspace')
        with path.open('rb') as stream: raw = stream.read(12001)
        if len(raw) > 12000: raise ValueError('Declaration exceeds 12000 UTF-8 bytes')
        value = json.loads(raw)
        providers = workspace/'harness/autoproteus/providers.py'
        if not providers.resolve().is_relative_to(workspace): raise ValueError('Source must stay in the workspace')
        with providers.open('rb') as stream: source = stream.read(2 * 1024 * 1024 + 1)
        if len(source) > 2 * 1024 * 1024: raise ValueError('Source exceeds the workspace file limit')
        issues = structural_issues(value, source.decode('utf-8'))
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        issues = ['Read capability.json from the workspace root (alongside harness/): ' + str(error)[:300]]
    return {'valid':not issues, 'issues':issues, 'example':EXAMPLE,
            'scope':'Public structural preflight only; it neither executes candidate code nor approves behavior or activation.'}


if __name__ == '__main__':
    result = check(Path.cwd())
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result['valid'] else 1)
