"""Optional guest-side batch inspection; JSON data only, no imports of inspected code."""
import ast
import json
from pathlib import Path
import sys


def inspect(root, names):
    root = root.resolve()
    if not 1 <= len(names) <= 12:
        raise ValueError('Inspect 1-12 workspace files')
    rows = []
    for name in names:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Inspect ordinary files inside the workspace')
        with path.open('r', encoding='utf-8', newline='') as stream:
            text = stream.read(100001)
        if len(text) > 100000:
            raise ValueError('Inspect files of at most 100000 characters')
        row = {'path': path.relative_to(root).as_posix(), 'characters': len(text),
               'lines': len(text.splitlines()), 'definitions': []}
        if path.suffix == '.py':
            try:
                tree = ast.parse(text)
                row['definitions'] = [{'name': node.name, 'line': node.lineno} for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))][:20]
            except (SyntaxError, RecursionError):
                row['parse_error'] = True
        rows.append(row)
    return rows


if __name__ == '__main__':
    print(json.dumps(inspect(Path.cwd(), sys.argv[1:]), ensure_ascii=False))
