"""Atomic session snapshots and an append-only event journal."""
from __future__ import annotations

import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class PersistenceError(OSError):
    """A save failure with an explicit durable outcome, never a replay request."""
    def __init__(self, stage, committed):
        self.stage, self.committed = stage, committed
        outcome = ('The session snapshot was saved.' if committed is True else
                   'The session snapshot was not saved.' if committed is False else
                   'The save outcome is uncertain.')
        super().__init__(outcome + ' Storage failed during ' + stage +
                         '; inspect saved work before retrying. No operation was replayed.')


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        # Cleanup cannot turn a successful replacement into an apparent failed
        # commit, or hide the original write error.
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.sessions = {}
        self.summaries = {}
        self.revision = 0
        self.failures = {}
        for path in self.root.glob("*/session.json"):
            try:
                summary_path = path.with_name('summary.json')
                fresh_summary = summary_path.exists() and summary_path.stat().st_mtime_ns > path.stat().st_mtime_ns
                session = json.loads((summary_path if fresh_summary else path).read_text(encoding="utf-8"))
                if session['id'] != path.parent.name or path.parent.is_symlink() or getattr(path.parent.lstat(), 'st_file_attributes', 0) & 0x400:
                    continue
                directory = self.directory(session['id'])
                # Saved guest/legacy metadata cannot select arbitrary host folders.
                self.summaries[session['id']] = self.summary(session)
                self.revision = max(self.revision, session.get('_revision', 0))
                if session.get("status") in ("running", "stopping"):
                    session = self.get(session['id'])
                    session["status"] = "interrupted"
                    session["activity"] = "Ready to resume"
                    self.save(session)
                elif not fresh_summary:
                    atomic_json(summary_path, self.summary(session))
            except (OSError, ValueError, KeyError):
                continue

    def directory(self, session_id):
        if not isinstance(session_id, str) or len(session_id) != 32:
            raise ValueError("Unknown session")
        try:
            int(session_id, 16)
        except ValueError:
            raise ValueError("Unknown session") from None
        return self.root / session_id

    def create(self, task, provider, model):
        session_id = uuid.uuid4().hex
        directory = self.directory(session_id)
        (directory / "workspace").mkdir(parents=True)
        session = {
            "id": session_id, "title": task.splitlines()[0][:70], "task": task,
            "created": now(), "updated": now(), "status": "ready",
            "activity": "Ready", "provider": provider, "model": model,
            "messages": [], "feed": [], "steps": 0, "runs": 0,
            "todo": "", "workspace": str(directory / "workspace"),
        }
        with self.lock:
            self.sessions[session_id] = session
            self.save(session)
            self.event(session, "session_created", {"task": task, "model": model, "provider": provider})
        return session

    def get(self, session_id):
        with self.lock:
            if session_id not in self.sessions:
                if session_id not in self.summaries:
                    raise ValueError("Session not found")
                directory = self.directory(session_id)
                if directory.is_symlink() or getattr(directory.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise ValueError('Session storage cannot be a link')
                session = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
                if session['id'] != session_id:
                    raise ValueError('Invalid session identity')
                session['workspace'] = str(directory / 'workspace')
                self.sessions[session_id] = session
            return self.sessions[session_id]

    def save(self, session):
        with self.lock:
            identifier = session['id']
            path = self.directory(identifier) / 'session.json'
            candidate = deepcopy(session)
            candidate.update(updated=now(), _revision=self.revision + 1)
            try:
                atomic_json(path, candidate)
            except OSError as error:
                # Faults may be reported after replace succeeded. Inspect the
                # authoritative snapshot; do not infer rollback from an error.
                try:
                    saved = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
                    committed = saved == candidate
                    if saved is not None:
                        session.clear(); session.update(saved)
                        self.sessions[identifier] = session
                        self.summaries[identifier] = self.summary(saved)
                        self.revision = max(self.revision, saved.get('_revision', 0))
                    else:
                        self.sessions.pop(identifier, None)
                        self.summaries.pop(identifier, None)
                except (OSError, ValueError):
                    committed = None
                self._failed(identifier, 'snapshot', committed)
                raise PersistenceError('snapshot', committed) from error
            # Keep references held by queue/receipt handlers valid on success.
            session.update(updated=candidate['updated'], _revision=candidate['_revision'])
            self.sessions[identifier] = session
            self.revision = candidate['_revision']
            self.summaries[identifier] = self.summary(candidate)
            try:
                atomic_json(path.with_name('summary.json'), self.summaries[identifier])
            except OSError as error:
                # This file is a disposable index. The session is already
                # committed; remove a stale index when possible for recovery.
                try:
                    path.with_name('summary.json').unlink(missing_ok=True)
                except OSError:
                    pass
                self._failed(identifier, 'summary', True)
                raise PersistenceError('summary', True) from error
            if self.failures.get(identifier, {}).get('stage') != 'journal':
                self.failures.pop(identifier, None)

    def _failed(self, identifier, stage, committed):
        self.failures[identifier] = {'stage': stage, 'snapshot_committed': committed,
                                    'message': str(PersistenceError(stage, committed))}

    def event(self, session, kind, data):
        with self.lock:
            event = {"id": uuid.uuid4().hex, "time": now(), "type": kind, "data": data}
            path = self.directory(session["id"]) / "events.jsonl"
            try:
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as error:
                # Append/fsync errors can leave a whole, partial, or absent
                # record. A saved snapshot is not proof of a durable journal.
                self._failed(session['id'], 'journal', None)
                raise PersistenceError('journal', None) from error
            return event

    def feed(self, session, kind, text, **details):
        with self.lock:
            item = {"id": uuid.uuid4().hex, "time": now(), "kind": kind, "text": text, **details}
            session["feed"].append(item)
            self.event(session, "display", item)
            self.save(session)

    def public(self, session_id=None):
        with self.lock:
            if session_id:
                return json.loads(json.dumps(self.get(session_id)))
            return [dict(s) for s in sorted(self.summaries.values(), key=lambda item: item['updated'], reverse=True)]

    @staticmethod
    def summary(session):
        return {**{key: session[key] for key in ('id', 'title', 'updated', 'status', 'provider', 'model')},
                'execution_mode': session.get('execution_mode', 'unknown'), 'isolation': session.get('isolation', False),
                'archived': session.get('archived', False), '_revision': session.get('_revision', 0)}

    def page(self, query='', offset=0, limit=30, archived=False):
        if not isinstance(query, str) or len(query) > 200 or type(offset) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('Invalid session page')
        values = [s for s in self.public() if bool(s['archived']) == archived and query.casefold() in s['title'].casefold()]
        return {'items': values[offset:offset+limit], 'total': len(values), 'offset': offset, 'limit': limit}

    def view(self, session_id, after=0, revision=None):
        with self.lock:
            session = self.get(session_id)
            warning = deepcopy(self.failures.get(session_id))
            if revision == session.get('_revision') and warning is None:
                return {'id': session_id, 'unchanged': True, 'revision': revision}
            if type(after) is not int or after < 0:
                raise ValueError('Invalid feed position')
            feed = session['feed']
            reset = after > len(feed)
            start = 0 if reset else after
            omitted = {'messages', 'artifacts', 'workspace', 'feed', '_revision'}
            return {**{k: v for k, v in session.items() if k not in omitted}, 'feed': feed[start:],
                    'feed_start': start, 'feed_count': len(feed), 'reset': reset, 'revision': session.get('_revision', 0),
                    'storage_warning': warning}

    def rename(self, session_id, title):
        if not isinstance(title, str) or not title.strip() or len(title) > 120 or any(ord(c) < 32 for c in title):
            raise ValueError('Use a title of 1–120 characters')
        session = self.get(session_id); session['title'] = title.strip(); self.save(session)

    def archive(self, session_id, archived=True):
        if type(archived) is not bool:
            raise ValueError('Invalid archive preference')
        session = self.get(session_id); session['archived'] = archived; self.save(session)

    def delete(self, session_id):
        with self.lock:
            self.get(session_id)
            source, destination = self.directory(session_id), self.root / '.trash' / session_id
            self._move(source, destination)
            self.sessions.pop(session_id, None); self.summaries.pop(session_id, None); self.revision += 1

    def restore(self, session_id):
        with self.lock:
            target = self.directory(session_id)
            source = self.root / '.trash' / session_id
            session = json.loads((source / 'session.json').read_text(encoding='utf-8'))
            if session['id'] != session_id:
                raise ValueError('Invalid trashed session')
            self._move(source, target)
            session['workspace'] = str(target / 'workspace')
            self.sessions[session_id] = session; self.save(session)

    def _move(self, source, destination):
        # Fixed storage locations, checked before moving a directory on Windows.
        for path in (source, destination, destination.parent):
            if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400) or not path.resolve().is_relative_to(self.root):
                raise ValueError('Invalid session move location')
        if destination.exists():
            raise ValueError('The destination session already exists')
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)

    def trash(self):
        result = []
        for path in (self.root / '.trash').glob('*/summary.json'):
            if path.parent.is_symlink() or getattr(path.parent.lstat(), 'st_file_attributes', 0) & 0x400:
                continue
            try:
                item = json.loads(path.read_text(encoding='utf-8'))
                if self.directory(item['id']).name == path.parent.name:
                    result.append(item)
            except (ValueError, KeyError, OSError):
                continue
        return sorted(result, key=lambda s: s['updated'], reverse=True)
