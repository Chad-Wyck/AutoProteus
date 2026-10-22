"""Loopback-only UI server. No third-party web framework is required."""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import base64
import os
import secrets
import threading
import time
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .artifacts import (Artifacts, MAX_FILE, MAX_FILES, MAX_EXPORT,
                        packed_files, relative_name, safe_path, seed_files)
from .isolation import IsolatedAgent
from .config import Settings
from .providers import ModelClient, ProviderError, ERROR_MESSAGES
from .compatibility import qualify_profile as check_protocol, PROFILE_FIELDS
from .runtime import LocalRuntime
from .storage import Store
from .evaluation import EvaluationService
from .evaluation import candidate_source
from .submissions import repair_ticket, ticket_message
from .execution import ExecutionPolicy
from .interactions import Inputs


class Application:
    def __init__(self, root, data=None, client_factory=None, execution=None):
        self.root = Path(root).resolve()
        self.data = Path(data or self.root / ".data")
        self.settings = Settings(self.data)
        self.store = Store(self.data / "sessions")
        self.execution = execution or ExecutionPolicy()
        self.agent = IsolatedAgent(self.root, self.store, self.settings, client_factory, self.execution)
        self.local = LocalRuntime(self.root, self.settings)
        self.evaluations = EvaluationService(self.root, self.data / 'evaluations', self.settings, self.agent)
        self.token = secrets.token_urlsafe(32)
        self.identity = hashlib.sha256(str(self.root).encode()).hexdigest()[:20]
        self.server = None
        self.usage_cache = None
        self.usage_time = 0
        self.local.restore()

    def active(self):
        with self.agent.lock:
            for identifier, (_, thread) in self.agent.workers.items():
                if thread.is_alive():
                    session = self.store.get(identifier)
                    return {k: session[k] for k in ('id', 'title', 'status', 'activity', 'provider', 'model')}
        return None

    def state(self, query='', offset=0, archived=False):
        page = self.store.page(query, offset, archived=archived)
        return {"version": __version__, "settings": self.settings.public(), "sessions": page['items'],
                'session_page': {k: v for k, v in page.items() if k != 'items'}, 'active': self.active(),
                'tasks_count': len(json.loads((self.root / 'evaluations/tasks.json').read_text(encoding='utf-8'))),
                "setup": self.local.public(), "isolation": self.agent.appliance.public(),
                "evaluation": self.evaluations.public(), "execution": self.execution.public(),
                "platform": 'windows' if os.name == 'nt' else 'linux', "root": str(self.root)}

    def ensure_idle(self, session_id=None):
        if self.evaluations.busy:
            raise ValueError('Stop the seed checks before changing this task')
        active = self.active()
        if active and (session_id is None or active['id'] == session_id):
            raise ValueError('Stop the active task before changing or starting work')

    def import_files(self, session, files):
        seed = seed_files(self.root)
        if not isinstance(files, list) or len(files) > MAX_FILES - len(seed):
            raise ValueError('Too many imported files')
        previous = session.get('artifacts', {}) if session else {}
        legacy = packed_files(session['workspace']) if session and 'artifacts' not in session else []
        existing = set(previous) | {item['path'] for item in legacy}
        seen, decoded, total = {name.casefold() for name in existing}, [], 0
        for item in files:
            if not isinstance(item, dict) or set(item) != {'path', 'data'}:
                raise ValueError('Import file names and encoded bytes')
            name = relative_name(item['path'])
            if name.startswith('harness/') or any(part.startswith('.') for part in name.split('/')) or name.casefold() in seen:
                raise ValueError('Choose distinct ordinary task file names; harness/ is reserved')
            data = item['data']
            if not isinstance(data, str) or len(data) > MAX_FILE * 4 // 3 + 8:
                raise ValueError('Each imported file must be at most 2 MiB')
            try:
                raw = base64.b64decode(data, validate=True)
            except ValueError:
                raise ValueError('Invalid imported file encoding') from None
            if len(raw) > MAX_FILE:
                raise ValueError('Each imported file must be at most 2 MiB')
            seen.add(name.casefold()); total += len(raw); decoded.append((name, data))
        needs_seed = not any(name.startswith('harness/') for name in existing)
        seed_count = len(seed) if needs_seed else 0
        seed_bytes = sum(len(base64.b64decode(item['data'])) for item in seed) if needs_seed else 0
        existing_bytes = sum(item['bytes'] for item in previous.values())
        existing_bytes += sum(len(base64.b64decode(item['data'])) for item in legacy)
        if len(existing) + len(decoded) + seed_count > MAX_FILES:
            raise ValueError('Too many files for one checkpoint')
        if total + existing_bytes + seed_bytes > MAX_EXPORT:
            raise ValueError('Imported files and the editable seed must fit the 32 MiB checkpoint limit')
        if session is None:
            return
        artifacts = Artifacts(self.store, session)
        for item in legacy:
            artifacts.put(item['path'], item['data'])
        for name, data in decoded:
            artifacts.put(name, data)
        artifacts.checkpoint([*existing, *(name for name, _ in decoded)])
        self.store.event(session, 'files_imported', {'paths': [name for name, _ in decoded], 'bytes': total})

    def storage_usage(self):
        if self.usage_cache is not None and time.monotonic() - self.usage_time < 30:
            return self.usage_cache
        def size(root):
            total = 0
            def ordinary(path):
                try:
                    return not path.is_symlink() and not getattr(path.lstat(), 'st_file_attributes', 0) & 0x400
                except OSError:
                    return False
            for directory, names, files in os.walk(root, followlinks=False):
                names[:] = [n for n in names if ordinary(Path(directory) / n)]
                for name in files:
                    path = Path(directory) / name
                    if ordinary(path):
                        try:
                            total += path.stat().st_size
                        except OSError:
                            pass
            return total
        self.usage_cache = {name: size(path) for name, path in {'sessions': self.store.root, 'models': self.root / '.data/models',
            'evaluations': self.data / 'evaluations', 'runtime': self.root / '.runtime', 'trash': self.store.root / '.trash'}.items()}
        self.usage_cache['sessions'] -= self.usage_cache['trash']
        self.usage_time = time.monotonic()
        return self.usage_cache

    def start_run(self, session, message=None, candidate=None):
        with self.evaluations.gate:
            if self.evaluations.busy:
                raise ValueError('Stop the seed checks before starting another task')
            self.agent.start(session, message, candidate=candidate)

    def files(self, session):
        if 'artifacts' in session:
            return [{'path': name, 'bytes': item['bytes']} for name, item in sorted(session['artifacts'].items())]
        root = Path(session["workspace"])
        files = []
        for directory, names, filenames in os.walk(root, followlinks=False):
            names[:] = [name for name in names if not name.startswith(".") and name != "__pycache__" and not (Path(directory) / name).is_symlink()]
            for name in sorted(filenames):
                path = Path(directory) / name
                if name.startswith(".") or path.is_symlink():
                    continue
                files.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size})
                if len(files) >= 300:
                    return files
        return sorted(files, key=lambda item: (item["path"].startswith("harness/"), item["path"]))

    def close(self):
        self.evaluations.close()
        self.agent.close()
        self.local.close()


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AutoProteus"

        def log_message(self, *_):
            pass

        def send(self, data, status=200, mime="application/json", filename=None):
            body = json.dumps(data, ensure_ascii=False).encode() if mime == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime == "application/json" else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; frame-ancestors 'none'; base-uri 'none'")
            if filename:
                safe = filename.replace('"', "").replace("\r", "").replace("\n", "")
                self.send_header("Content-Disposition", 'attachment; filename="' + safe + '"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def allowed(self, api=False):
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") not in (expected, f"localhost:{self.server.server_port}"):
                self.send({"error": "This app only accepts requests addressed to its local server"}, 403)
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in ("http://" + expected, f"http://localhost:{self.server.server_port}"):
                self.send({"error": "This request came from another website"}, 403)
                return False
            if api and not secrets.compare_digest(self.headers.get("X-AutoProteus-Token", ""), app.token):
                self.send({"error": "Reload AutoProteus to reconnect"}, 403)
                return False
            return True

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path, query = parsed.path, urllib.parse.parse_qs(parsed.query)
            if not self.allowed(path.startswith("/api/")):
                return
            try:
                if path == "/health":
                    return self.send({"app": "AutoProteus", "identity": app.identity, "version": __version__,
                                      "isolation_required": app.execution.mode == 'vm',
                                      "execution_mode": app.execution.mode})
                if path == "/api/state":
                    return self.send(app.state(query.get('query', [''])[0], int(query.get('offset', ['0'])[0]), query.get('archived', ['false'])[0] == 'true'))
                if path == '/api/storage':
                    return self.send(app.storage_usage())
                if path == '/api/trash':
                    return self.send(app.store.trash())
                if path == '/api/seed-check':
                    return self.send(app.evaluations.load(query.get('id', [''])[0]))
                if path == "/api/local":
                    try:
                        models = app.local.models()
                        return self.send({"available": True, "models": models})
                    except Exception as error:
                        return self.send({"available": False, "models": [], "message": str(error)})
                if path in ("/api/session", "/api/files", "/api/file", "/api/export", "/api/download"):
                    session = app.store.get(query.get("id", [""])[0])
                    if path == "/api/session":
                        view = app.store.view(session['id'], int(query.get('after', ['0'])[0]),
                            int(query['revision'][0]) if 'revision' in query else None)
                        return self.send({**view, 'verification': app.evaluations.status_for(session)})
                    if path == "/api/files":
                        return self.send(app.files(session))
                    if path in ("/api/file", "/api/download"):
                        name = query.get("path", [""])[0]
                        if 'artifacts' in session:
                            content = Artifacts(app.store, session).read(name)
                        else:
                            target = safe_path(session['workspace'], name)
                            if target.stat().st_size > 2000000:
                                raise ValueError('This legacy file is too large to preview')
                            content = target.read_bytes()
                        if path == "/api/download":
                            return self.send(content, mime="application/octet-stream", filename=Path(name).name)
                        return self.send({"path": query["path"][0], "content": content[:100000].decode("utf-8", errors="replace"), "truncated": len(content) > 100000})
                    buffer = io.BytesIO()
                    with app.store.lock, zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                        directory = app.store.directory(session['id'])
                        for name in ("session.json", "events.jsonl"):
                            archive.write(safe_path(directory, name), name)
                        history = safe_path(directory, 'inference')
                        if history.exists():
                            for blob in sorted(history.glob('*.json')):
                                archive.write(safe_path(directory, 'inference/' + blob.name), 'inference/' + blob.name)
                    return self.send(buffer.getvalue(), mime="application/zip", filename="autoproteus-session-" + session["id"][:8] + ".zip")
                if path == "/":
                    page = (app.root / "web" / "index.html").read_text(encoding="utf-8").replace("__APP_TOKEN__", app.token)
                    return self.send(page.encode(), mime="text/html")
                if path in ("/app.js", "/theme.js", "/style.css", "/favicon.svg"):
                    target = app.root / "web" / path.lstrip("/")
                    return self.send(target.read_bytes(), mime=mimetypes.guess_type(str(target))[0] or "application/octet-stream")
                self.send({"error": "Page not found"}, 404)
            except (ValueError, KeyError, OSError) as error:
                self.send({"error": str(error)}, 400)

        def do_POST(self):
            if self.path in ('/api/start', '/api/resume', '/api/reset', '/api/try-seed', '/api/restart-seed', '/api/import', '/api/session/manage'):
                with app.evaluations.gate:
                    if app.evaluations.busy:
                        if self.allowed(api=True):
                            self.send({'error': 'Stop the seed checks before starting another task'}, 400)
                        return
                    return self.handle_post()
            return self.handle_post()

        def handle_post(self):
            if not self.allowed(api=True):
                return
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= (MAX_EXPORT * 4 // 3 + 100000 if self.path in ('/api/start', '/api/import') else 250000):
                    raise ValueError("The request is empty or too large")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Provide a JSON object")
                if self.path == '/api/input':
                    with app.evaluations.gate, app.agent.lock:
                        active = app.active()
                        session = app.store.get(data.get('id'))
                        if (app.evaluations.busy or not active or active['id'] != session['id']
                                or session['status'] == 'stopping'):
                            raise ValueError('This task is no longer running. Send your message with Resume.')
                        return self.send(Inputs(app.store, session).enqueue(
                            data.get('message'), data.get('mode'), data.get('request_id')))
                if self.path == '/api/input/cancel':
                    Inputs(app.store, app.store.get(data.get('id'))).cancel(data.get('request_id'))
                    return self.send({'cancelled': True})
                if self.path == "/api/settings":
                    if any(key in data for key in ('execution', 'execution_mode', 'acknowledge_host_access')):
                        raise ValueError('Execution mode can only be selected at launch')
                    candidate = app.settings.preview(data)
                    changed = any(candidate[k] != app.settings.values[k] for k in (*PROFILE_FIELDS, 'base_url')) or bool(data.get('api_key') or data.get('clear_key'))
                    if data.get('api_key') or data.get('clear_key'):
                        candidate.pop('compatibility', None)
                    connection_key = data.get('api_key') or (os.environ.get('AUTOPROTEUS_API_KEY', '') if data.get('clear_key') else app.settings.key())
                    compatibility = check_protocol(candidate, connection_key) if candidate['configured'] and changed else None
                    result = app.settings.update(data)
                    if compatibility:
                        result = app.settings.record_compatibility(compatibility)
                    return self.send(result)
                if self.path == "/api/connect":
                    config = app.settings.preview({**data, "configured": False})
                    if data.get('api_key'):
                        config.pop('compatibility', None)
                    if config["provider"] == "ollama":
                        names = [item["name"] for item in app.local.models(config["base_url"])]
                        if config["model"] not in names and config["model"] + ":latest" not in names:
                            raise ValueError("This model is not installed yet. Use Prepare local model to download it.")
                    compatibility = check_protocol(config, data.get('api_key') or app.settings.key())
                    app.settings.update({**data, "configured": True})
                    return self.send(app.settings.record_compatibility(compatibility))
                if self.path == "/api/setup":
                    app.local.prepare(data.get("model", "qwen3:4b-instruct"))
                    return self.send(app.local.public())
                if self.path == '/api/isolation/setup':
                    app.agent.appliance.prepare()
                    return self.send(app.agent.appliance.public())
                if self.path == '/api/seed-check':
                    session = app.store.get(data.get('id'))
                    return self.send(app.evaluations.start(session, data.get('repeats', 2)))
                if self.path == '/api/seed-check/stop':
                    app.evaluations.stop()
                    return self.send({'ok': True})
                if self.path == '/api/submission-review':
                    app.ensure_idle()
                    session = app.store.get(data.get('id'))
                    source = candidate_source(app.store, session)
                    path = app.store.directory(session['id']) / 'candidate.json'
                    starter = json.loads(path.read_text(encoding='utf-8')) if path.exists() else seed_files(app.root)
                    journal = app.store.directory(session['id']) / 'events.jsonl'
                    events = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()] if journal.exists() else []
                    ticket = repair_ticket(starter, source, events)
                    return self.send({'ticket': ticket, 'message': ticket_message(ticket)})
                if self.path == "/api/start":
                    app.ensure_idle()
                    task = data.get("task", "").strip()
                    if not task or len(task) > 12000:
                        raise ValueError("Describe your task in 12,000 characters or fewer")
                    if not app.settings.values["configured"]:
                        raise ValueError("Connect a model first, or try the interactive demo")
                    app.agent.appliance.verify()
                    if app.settings.values['provider'] == 'ollama' and app.local.public()['busy']:
                        raise ValueError('Your local model engine is starting. Give it a moment, then start the task.')
                    if data.get('files'):
                        app.import_files(None, data['files'])
                    session = app.store.create(task, app.settings.values["provider"], app.settings.values["model"])
                    if data.get('files'):
                        try:
                            app.import_files(session, data['files'])
                        except Exception:
                            app.store.delete(session['id'])
                            raise
                    app.start_run(session)
                    return self.send({"id": session["id"]})
                if self.path == '/api/restart-seed':
                    app.ensure_idle()
                    session = app.store.get(data.get('id'))
                    app.agent.restart_seed(session)
                    return self.send({'id': session['id']})
                if self.path == '/api/try-seed':
                    app.ensure_idle()
                    candidate = app.store.get(data.get('id'))
                    task = data.get('task', candidate['task'])
                    if not isinstance(task, str) or not task.strip() or len(task) > 12000:
                        raise ValueError('Describe the test task in 12,000 characters or fewer')
                    session = app.store.create(task, app.settings.values['provider'], app.settings.values['model'])
                    session['candidate_from'] = candidate['id']
                    app.start_run(session, candidate=candidate)
                    return self.send({'id': session['id']})
                if self.path == '/api/import':
                    session = app.store.get(data.get('id'))
                    app.ensure_idle(session['id'])
                    app.import_files(session, data.get('files'))
                    return self.send({'ok': True})
                if self.path == '/api/session/manage':
                    identifier, action = data.get('id'), data.get('action')
                    app.ensure_idle(identifier)
                    if action == 'rename': app.store.rename(identifier, data.get('title'))
                    elif action == 'archive': app.store.archive(identifier, data.get('archived', True))
                    elif action == 'delete': app.store.delete(identifier)
                    elif action == 'restore': app.store.restore(identifier)
                    else: raise ValueError('Unknown session action')
                    app.usage_cache = None
                    return self.send({'ok': True})
                if self.path in ("/api/resume", "/api/stop", "/api/reset", "/api/open-workspace"):
                    session = app.store.get(data.get("id"))
                    if self.path == "/api/resume":
                        app.ensure_idle()
                        message = data.get("message", "")
                        if not isinstance(message, str) or len(message) > 12000:
                            raise ValueError("Keep your reply under 12,000 characters")
                        app.start_run(session, message)
                    elif self.path == "/api/stop":
                        app.agent.stop(session["id"])
                    elif self.path == '/api/reset':
                        active = app.active()
                        if active and active['id'] != session['id']:
                            raise ValueError('Stop the active task before resetting another session')
                        app.agent.stop(session['id'])
                        worker = app.agent.workers.get(session['id'])
                        if worker:
                            worker[1].join(timeout=5)
                        session.pop('candidate_from', None)
                        app.start_run(session)
                    else:
                        # Downloads are data only. Do not open generated programs on the host.
                        buffer = io.BytesIO()
                        artifacts = Artifacts(app.store, session)
                        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                            for name in session.get('artifacts', {}):
                                archive.writestr(name, artifacts.read(name))
                        return self.send(buffer.getvalue(), mime='application/zip', filename='autoproteus-files-' + session['id'][:8] + '.zip')
                    return self.send({"ok": True})
                if self.path == "/api/shutdown":
                    self.send({"ok": True})
                    threading.Thread(target=app.server.shutdown, daemon=True).start()
                    return
                self.send({"error": "Unknown action"}, 404)
            except ProviderError as error:
                self.send({'error': ERROR_MESSAGES[error.category], 'category': error.category}, 400)
            except Exception as error:
                self.send({"error": str(error)}, 400)
    return Handler


def make_server(app, port=47831):
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(app))
    server.daemon_threads = True
    app.server = server
    return server
