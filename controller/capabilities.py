"""Source-bound capability observations, separate from independent checks."""
import ast
import base64
import re

from .submissions import source_hash


def declared_tools(source):
    """Only literal declarations count. Dynamic registries remain unmeasured."""
    item = next((item for item in source if item['path'] == 'autoproteus/providers.py'), None)
    if not item:
        return []
    try:
        tree = ast.parse(base64.b64decode(item['data']).decode('utf-8'))
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and
                          any(isinstance(target, ast.Name) and target.id == 'TOOL_SPECS' for target in node.targets))
        return sorted({key.value for key in assignment.value.keys if isinstance(key, ast.Constant) and
                       isinstance(key.value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key.value)})[:64]
    except (SyntaxError, ValueError, UnicodeError, RecursionError, StopIteration, AttributeError):
        return []


def capability_progress(source, active, verification):
    current = source_hash(source)
    same = active.get('source_sha256') == current
    return {'source_sha256': current, 'declared': declared_tools(source),
            'checked_source': verification['state'], 'checks_scope': verification['scope'],
            'activated': same, 'active_source_sha256': active.get('source_sha256'),
            'model_used': sorted(set(active.get('direct', []))) if same else [],
            'development_used': sorted(set(active.get('development', []))) if same else [],
            'scope': 'Up to 64 declared tools are static source observations. Use records are successful guest-reported calls in model runs, '
                     'not independent proof of correctness. Source comparisons cover only their listed tasks.'}
