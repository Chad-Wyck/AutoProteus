"""Experimental guest helper: inspect Python structure without importing it."""
import ast
import json


def source_outline(workspace, args):
    path = workspace.path(args['path'])
    text = workspace.read_text(path)
    try:
        tree = ast.parse(text)
    except (SyntaxError, RecursionError) as error:
        raise ValueError('Cannot outline this Python source; use read_section to inspect it') from error
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    result = {'path': str(path.relative_to(workspace.root)), 'definitions': [], 'truncated': False}

    def definitions(body, prefix=''):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                line = min([node.lineno] + [item.lineno for item in node.decorator_list])
                start, end = offsets[line - 1], offsets[node.end_lineno]
                yield {'name': name, 'line': line, 'start': start,
                       'length': min(end - start, 12000), 'characters': end - start}
                if isinstance(node, ast.ClassDef):
                    yield from definitions(node.body, name + '.')
    for entry in definitions(tree.body):
        result['definitions'].append(entry)
        if len(result['definitions']) > 60 or len(json.dumps(result, ensure_ascii=False)) > 6000:
            result['definitions'].pop()
            result['truncated'] = True
            break
    return result
