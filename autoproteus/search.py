"""Bounded literal search; all paths use the workspace validator."""


def search_files(workspace, args):
    from .tools import Cancelled, LIMIT
    query = args['query']
    if not isinstance(query, str) or not query or len(query) > 200 or '\n' in query or '\r' in query:
        raise ValueError('Search for one nonempty literal of at most 200 characters')
    root = workspace.path(args.get('path', '.'))
    if not root.exists():
        raise ValueError('The search path does not exist')
    matches, scanned, total, visited, output, incomplete = [], 0, 0, 0, 0, False
    paths = [root] if root.is_file() else root.rglob('*')
    for path in paths:
        if workspace.cancel.is_set():
            raise Cancelled()
        visited += 1
        if visited > 2000:
            incomplete = True; break
        if path.is_symlink() or not path.is_file() or any(p.startswith('.') or p == '__pycache__' for p in path.relative_to(workspace.root).parts):
            continue
        path = workspace.path(str(path.relative_to(workspace.root)))
        size = path.stat().st_size
        if size > 400000:
            incomplete = True; continue
        scanned += 1; total += size
        if scanned > 200 or total > 2 * 1024 * 1024:
            incomplete = True; break
        try:
            with path.open('rb') as stream:
                raw = stream.read(400001)
            if len(raw) > 400000:
                incomplete = True; continue
            content = raw.decode('utf-8')
        except UnicodeError:
            continue
        offset = 0
        for number, raw_line in enumerate(content.splitlines(keepends=True), 1):
            line = raw_line.rstrip('\r\n')
            position = line.find(query)
            if position >= 0:
                match = {'path': path.relative_to(workspace.root).as_posix(), 'line': number,
                         'start': offset + max(0, position - 60),
                         'snippet': line[max(0, position - 60):position + len(query) + 100]}
                output += len(str(match).encode('utf-8'))
                if output > LIMIT:
                    incomplete = True; break
                matches.append(match)
                if len(matches) == 30:
                    incomplete = True; break
            offset += len(raw_line)
        if len(matches) == 30 or output > LIMIT:
            break
    return {'matches': matches, 'files_scanned': min(scanned, 200), 'incomplete': incomplete}
