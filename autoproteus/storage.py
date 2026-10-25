"""Atomic session snapshots and an append-only event journal."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


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
        temporary.unlink(missing_ok=True)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.sessions = {}
        for path in self.root.glob("*/session.json"):
            try:
                session = json.loads(path.read_text(encoding="utf-8"))
                if session.get("status") in ("running", "stopping"):
                    session["status"] = "interrupted"
                    session["activity"] = "Ready to resume"
                    atomic_json(path, session)
                self.sessions[session["id"]] = session
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
                raise ValueError("Session not found")
            return self.sessions[session_id]

    def save(self, session):
        with self.lock:
            session["updated"] = now()
            atomic_json(self.directory(session["id"]) / "session.json", session)

    def event(self, session, kind, data):
        with self.lock:
            event = {"id": uuid.uuid4().hex, "time": now(), "type": kind, "data": data}
            path = self.directory(session["id"]) / "events.jsonl"
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
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
            return [{key: session[key] for key in ("id", "title", "updated", "status", "provider", "model")}
                    for session in sorted(self.sessions.values(), key=lambda item: item["updated"], reverse=True)]


def snapshot_seed(root, session, version):
    """Copy the starter source once; subsequent edits stay in the workspace."""
    import hashlib
    import shutil
    target = Path(session["workspace"]) / "harness"
    if target.exists():
        return
    target.mkdir()
    digest = hashlib.sha256()
    for name in ("autoproteus", "tests", "examples", "seed.py", "README.md"):
        path = Path(root) / name
        if path.is_dir():
            shutil.copytree(path, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif path.exists():
            shutil.copy2(path, target / name)
    for path in sorted(target.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(target).as_posix().encode())
            digest.update(path.read_bytes())
    session["seed_version"] = version
    session["seed_sha256"] = digest.hexdigest()
