"""Opt-in static task context. Safe as a guest script; never imports candidate code."""
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import tokenize

LIMIT = 12000


def definitions(tree, prefix=''):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield prefix + node.name, node
            if isinstance(node, ast.ClassDef):
                yield from definitions(node, prefix + node.name + '.')


def header(text, node):
    """Keep the real header, including defaults; token columns count characters."""
    segment = ast.get_source_segment(text, node)
    lines = segment.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    depth = 0
    for token in tokenize.generate_tokens(io.StringIO(segment).readline):
        if token.string == ':' and depth == 0:
            return segment[:offsets[token.end[0] - 1] + token.end[1]]
        if token.type == tokenize.OP:
            depth += (token.string in '([{') - (token.string in ')]}')
    raise ValueError('No complete Python definition header')


def build_packet(source, limit=LIMIT):
    if not 3000 <= limit <= LIMIT:
        raise ValueError('Packet limit must be between 3000 and 12000 UTF-8 bytes')
    files = {item['path']: base64.b64decode(item['data'], validate=True) for item in source}
    packet = {'schema': 1, 'scope': 'Static source observations only; original user requirements remain authoritative.',
              'freshness': 'Bound to the hashes below. After editing these files, regenerate this packet before relying on it.',
              'requirements': 'Use the complete original user instructions above; this packet adds no feature requirements.',
              'sources': [], 'omissions': ['Unrelated modules, full existing tests, and hidden grading details are omitted.']}
    targets = {'autoproteus/tools.py': ['Workspace.execute', 'Workspace.read_text', 'Workspace.write_text',
                                       'Workspace.__init__', 'Workspace.path'],
               'autoproteus/providers.py': ['TOOL_SPECS', 'tool_definitions'], 'tests/test_seed.py': []}
    for path, wanted in targets.items():
        if path not in files:
            packet['omissions'].append(path + ' is absent.')
            continue
        raw = files[path]
        record = {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'observations': []}
        packet['sources'].append(record)
        try:
            text = raw.decode('utf-8')
            tree = ast.parse(text)
            imports = [ast.get_source_segment(text, node) for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
            record['imports'] = [item[:240] for item in imports[:8]]
            record['imports_omitted_or_shortened'] = len(imports) > 8 or any(len(item) > 240 for item in imports)
            if path == 'autoproteus/tools.py':
                record['shared_constants'] = [ast.get_source_segment(text, node) for node in tree.body if
                    isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in
                    ('LIMIT', 'READ_DEFAULT', 'TEXT_CHARACTER_LIMIT', 'WRITE_LIMIT') for target in node.targets)][:4]
            offsets = [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            nodes = dict(definitions(tree))
            if path == 'tests/test_seed.py':
                wanted = [name for name, node in nodes.items() if isinstance(node, ast.FunctionDef) and
                          any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and
                              call.func.attr == 'execute' for call in ast.walk(node))][:1]
            for name in wanted:
                node = nodes.get(name)
                if name == 'TOOL_SPECS':
                    node = next((node for node in tree.body if isinstance(node, ast.Assign) and
                                 any(isinstance(target, ast.Name) and target.id == name for target in node.targets)), None)
                if node is None:
                    packet['omissions'].append(path + ':' + name + ' was not found; do not invent its API.')
                    continue
                entry = {'symbol': name}
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    entry['header'] = header(text, node)
                if name in ('Workspace.execute', 'TOOL_SPECS') or path == 'tests/test_seed.py':
                    start = offsets[node.lineno - 1]
                    end = offsets[node.end_lineno]
                    length = min(end - start, 2200 if name == 'Workspace.execute' else 1600)
                    entry.update(start_character=start, characters=length, excerpt=text[start:start + length],
                                 omitted_characters=end - start - length)
                record['observations'].append(entry)
        except (SyntaxError, UnicodeError, ValueError, RecursionError, tokenize.TokenError) as error:
            record['parse_error'] = str(error)[:240]
    # Trim whole observations, never slice serialized JSON or original human text.
    while len(json.dumps(packet, ensure_ascii=False).encode()) > limit:
        entries = [entry for record in packet['sources'] for entry in record['observations'] if 'excerpt' in entry]
        if not entries:
            raise ValueError('Cannot fit source identities within the packet budget')
        largest = max(entries, key=lambda entry: len(entry['excerpt'].encode()))
        removed = len(largest.pop('excerpt'))
        largest['omitted_characters'] = largest.get('omitted_characters', 0) + removed
        largest['characters'] = 0
    return packet


def stale_paths(packet, source):
    current = {item['path']: hashlib.sha256(base64.b64decode(item['data'], validate=True)).hexdigest() for item in source}
    return [item['path'] for item in packet['sources'] if current.get(item['path']) != item['sha256']]


def task_support(source, instructions, treatment):
    if treatment == 'edit-context':
        packet = build_packet(source)
        script = Path(__file__).read_text(encoding='utf-8')
        return {'kind': treatment, 'packet': packet, 'text': json.dumps(packet, ensure_ascii=False) +
                '\nDiscard these excerpts after changing a listed file. To refresh: python3 experience/context_packet.py. '
                'To check the original packet: python3 experience/context_packet.py --check experience/context.json',
                'fixtures': {'experience/context_packet.py': script, 'experience/context.json': json.dumps(packet, ensure_ascii=False)},
                'provided': True, 'followed': 'unmeasured'}
    if treatment != 'verified-lesson':
        raise ValueError('Unknown support treatment')
    path = Path(__file__).with_name('lessons') / 'verified-submission.md'
    text = path.read_text(encoding='utf-8')
    return {'kind': treatment, 'text': 'Optional prior-work lesson: read experience/verified-submission.md if relevant.',
            'fixtures': {'experience/verified-submission.md': text}, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
            'provided': True, 'read': False, 'followed': 'unmeasured', 'independently_useful': 'unmeasured'}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check')
    args = parser.parse_args()
    root = Path('harness').resolve()
    if not root.is_relative_to(Path.cwd().resolve()):
        raise ValueError('Source must stay in this task workspace')
    source = []
    for name in ('autoproteus/tools.py', 'autoproteus/providers.py', 'tests/test_seed.py'):
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Source path escapes harness/')
        if path.exists():
            with path.open('rb') as stream:
                raw = stream.read(400001)
            if len(raw) > 400000:
                raise ValueError('Source file exceeds static inspection limit')
            source.append({'path': name, 'data': base64.b64encode(raw).decode()})
    if args.check:
        path = Path(args.check).resolve()
        if not path.is_relative_to(Path.cwd().resolve()):
            raise ValueError('Packet path must stay in this task workspace')
        with path.open('rb') as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('Packet exceeds its UTF-8 byte limit')
        stale = stale_paths(json.loads(raw), source)
        print(json.dumps({'fresh': not stale, 'stale_paths': stale, 'use_old_excerpts': not stale}))
    else:
        print(json.dumps(build_packet(source), ensure_ascii=False))


if __name__ == '__main__':
    main()
