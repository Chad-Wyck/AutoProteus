"""Bounded retrieval of this guest task's journal and its inert resume archive."""
import json
import re

SCAN_BYTES = 4 * 1024 * 1024


def records(workspace):
    # No caller-supplied journal path or cross-session lookup. The live path is
    # attached by the copied Agent; the archive is a guest workspace snapshot.
    paths = [workspace.path('experience/history.jsonl')]
    if getattr(workspace, 'history_journal', None):
        paths.append(workspace.history_journal)
    values, seen, incomplete = [], set(), False
    remaining = SCAN_BYTES
    for index, path in enumerate(paths):
        try:
            with path.open('rb') as stream:
                raw = stream.read(remaining + 1)
        except FileNotFoundError:
            continue
        if workspace.cancel.is_set():
            raise ValueError('History retrieval cancelled')
        if len(raw) > remaining:
            raw, incomplete = raw[:remaining], True
        remaining -= len(raw)
        seed = getattr(workspace, 'history_seed_sha256', None)
        for line in raw.splitlines():
            try:
                event = json.loads(line)
                if event.get('type') == 'run_started':
                    seed = event.get('data', {}).get('seed_sha256', seed)
                entry = normalize(event, seed)
            except (ValueError, TypeError, AttributeError):
                incomplete = True
                continue
            if entry and entry['id'] not in seen:
                seen.add(entry['id'])
                values.append(entry)
            if len(values) >= 2000:
                return values, True
        if remaining <= 0:
            incomplete = incomplete or index < len(paths) - 1
            break
    return values, incomplete


def normalize(event, seed):
    identity = event.get('id', '')
    if not isinstance(identity, str) or not re.fullmatch('[0-9a-f]{32}', identity):
        return None
    kind, data = event.get('type'), event.get('data', {})
    if kind == 'display' and data.get('kind') == 'user':
        origin, text = 'human', data.get('text', '')
    elif kind == 'action_result':
        if data.get('action', {}).get('tool') in ('history_search', 'history_read'):
            return None  # Avoid recursively retrieving prior retrieval outputs.
        origin, text = 'guest_tool_result', json.dumps(data, ensure_ascii=False)
    elif kind == 'run_started':
        origin, text = 'runtime_record', json.dumps(data, ensure_ascii=False)
    else:
        return None
    return {'id': identity, 'time': event.get('time'), 'origin': origin,
            'seed_sha256': event.get('seed_sha256', seed), 'text': text,
            'authority': 'Historical guest record; a past pass does not verify current code.'}


def history_search(workspace, args):
    query, limit = args.get('query'), args.get('limit', 5)
    if not isinstance(query, str) or not 1 <= len(query) <= 200 or type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('Use a query of 1-200 characters and limit of 1-10')
    entries, incomplete = records(workspace)
    matches = [entry for entry in entries if query.casefold() in entry['text'].casefold()]
    result = []
    for entry in matches[:limit]:
        at = entry['text'].casefold().find(query.casefold())
        # Snippets are discovery hints; read exact original characters by ID.
        result.append({key: value for key, value in entry.items() if key != 'text'} | {
            'preview': entry['text'][max(0, at - 80):at + 300], 'characters': len(entry['text'])})
    return {'matches': result, 'truncated': incomplete or len(matches) > limit,
            'scope': 'current task only; archive copies are not protected verification evidence'}


def history_read(workspace, args):
    identity, start, length = args.get('id'), args.get('start', 0), args.get('length', 4000)
    if (not isinstance(identity, str) or not re.fullmatch('[0-9a-f]{32}', identity) or
            type(start) is not int or start < 0 or type(length) is not int or not 1 <= length <= 10000):
        raise ValueError('Use an event ID, nonnegative character start and length of 1-10000')
    entries, incomplete = records(workspace)
    entry = next((item for item in entries if item['id'] == identity), None)
    if entry is None:
        raise ValueError('Event not found in this task; the bounded scan may be incomplete' if incomplete else 'Event not found in this task')
    text = entry.pop('text')
    content = text[start:start + length]
    return entry | {'content': content, 'start': start, 'next_start': start + len(content),
                    'eof': start + len(content) >= len(text), 'scan_incomplete': incomplete}
