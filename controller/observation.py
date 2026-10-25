"""Read-only views through the owning controller; never open another Store."""
from copy import deepcopy
import json
import re

from .artifacts import safe_path
from .inference_history import digest


def preview(value, depth=0):
    if depth > 5:
        return '[More detail in saved trace]'
    if isinstance(value, str):
        return value if len(value) <= 1200 else value[:1200] + '\n[Preview shortened; original remains in trace]'
    if isinstance(value, list):
        return [preview(item, depth + 1) for item in value[:30]] + (['[More entries in trace]'] if len(value) > 30 else [])
    if isinstance(value, dict):
        return {key: preview(item, depth + 1) for key, item in list(value.items())[:40]}
    return value


class Observer:
    """Only the active owner supplies storage. This interface cannot schedule work.

    File reads hold the owner's lock, so Windows atomic replacement cannot race
    them. Independent tools should use the API or an exported, closed trace.
    """
    def __init__(self, store):
        self._store = store

    def session(self, identifier, after=0, revision=None):
        with self._store.lock:
            return deepcopy(self._store.view(identifier, after, revision))

    def timeline(self, identifier, offset=0, limit=40):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Invalid evidence page')
        with self._store.lock:
            self._store.get(identifier)
            path = safe_path(self._store.directory(identifier), 'events.jsonl')
            rows, scanned, returned, incomplete = [], 0, 0, False
            with path.open('rb') as stream:
                size = path.stat().st_size
                if offset > size:
                    raise ValueError('Evidence position is outside the journal')
                if offset:
                    stream.seek(offset - 1)
                    if stream.read(1) != b'\n':
                        raise ValueError('Evidence position must follow a complete record')
                stream.seek(offset)
                while len(rows) < limit and scanned < 4 * 1024 * 1024:
                    start = stream.tell()
                    line = stream.readline(1600001)
                    if not line:
                        break
                    scanned += len(line)
                    if not line.endswith(b'\n'):
                        incomplete = True
                        stream.seek(start)
                        break
                    try:
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError('Invalid record')
                        value = preview(event)
                        size_hint = len(json.dumps(value).encode())
                        if size_hint > 24000:
                            value['data'] = {'preview': json.dumps(value.get('data'), ensure_ascii=False)[:1200],
                                             'preview_shortened': True}
                            size_hint = len(json.dumps(value).encode())
                        if rows and returned + size_hint > 256000:
                            stream.seek(start)
                            break
                        rows.append(value); returned += size_hint
                    except (ValueError, UnicodeError):
                        rows.append({'type': 'unreadable_record', 'offset': start,
                                     'data': 'Original bytes remain in the saved trace.'})
                next_offset = stream.tell()
            return {'id': identifier, 'events': rows, 'offset': offset, 'next_offset': next_offset,
                    'has_more': next_offset < size and not incomplete, 'incomplete_tail': incomplete,
                    'read_only': True, 'storage_warning': deepcopy(self._store.failures.get(identifier))}

    def blob(self, identifier, key):
        if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{64}', key):
            raise ValueError('Invalid evidence identity')
        with self._store.lock:
            self._store.get(identifier)
            path = safe_path(self._store.directory(identifier), 'inference/' + key + '.json')
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Evidence is too large to preview; save the trace instead')
            value = json.loads(path.read_text(encoding='utf-8'))
            if digest(value) != key:
                raise ValueError('Evidence identity mismatch')
            return {'sha256': key, 'value': value, 'read_only': True}
