"""Loopback-only UI server. No third-party web framework is required."""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import secrets
import threading
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .isolation import IsolatedAgent, Artifacts, safe_path
from .config import Settings
from .providers import ModelClient
from .runtime import LocalRuntime
from .storage import Store


class Application:
    def __init__(self, root, data=None, client_factory=None):
        self.root = Path(root).resolve()
        self.data = Path(data or self.root / ".data")
        self.settings = Settings(self.data)
        self.store = Store(self.data / "sessions")
        self.agent = IsolatedAgent(self.root, self.store, self.settings, client_factory)
        self.local = LocalRuntime(self.root, self.settings)
        self.token = secrets.token_urlsafe(32)
        self.identity = hashlib.sha256(str(self.root).encode()).hexdigest()[:20]
        self.server = None
        self.local.restore()

    def state(self):
        return {"version": __version__, "settings": self.settings.public(), "sessions": self.store.public(),
                "setup": self.local.public(), "isolation": self.agent.appliance.public(), "root": str(self.root)}

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
                    return self.send({"app": "AutoProteus", "identity": app.identity, "version": __version__, "isolation_required": True})
                if path == "/api/state":
                    return self.send(app.state())
                if path == "/api/local":
                    try:
                        models = app.local.models()
                        return self.send({"available": True, "models": models})
                    except Exception as error:
                        return self.send({"available": False, "models": [], "message": str(error)})
                if path in ("/api/session", "/api/files", "/api/file", "/api/export", "/api/download"):
                    session = app.store.get(query.get("id", [""])[0])
                    if path == "/api/session":
                        return self.send(app.store.public(session["id"]))
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
                    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                        for name in ("session.json", "events.jsonl"):
                            archive.write(app.store.directory(session["id"]) / name, name)
                    return self.send(buffer.getvalue(), mime="application/zip", filename="autoproteus-session-" + session["id"][:8] + ".zip")
                if path == "/":
                    page = (app.root / "web" / "index.html").read_text(encoding="utf-8").replace("__APP_TOKEN__", app.token)
                    return self.send(page.encode(), mime="text/html")
                if path in ("/app.js", "/style.css", "/favicon.svg"):
                    target = app.root / "web" / path.lstrip("/")
                    return self.send(target.read_bytes(), mime=mimetypes.guess_type(str(target))[0] or "application/octet-stream")
                self.send({"error": "Page not found"}, 404)
            except (ValueError, KeyError, OSError) as error:
                self.send({"error": str(error)}, 400)

        def do_POST(self):
            if not self.allowed(api=True):
                return
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 250000:
                    raise ValueError("The request is empty or too large")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Provide a JSON object")
                if self.path == "/api/settings":
                    return self.send(app.settings.update(data))
                if self.path == "/api/connect":
                    config = app.settings.preview({**data, "configured": False})
                    if config["provider"] == "ollama":
                        names = [item["name"] for item in app.local.models(config["base_url"])]
                        if config["model"] not in names and config["model"] + ":latest" not in names:
                            raise ValueError("This model is not installed yet. Use Prepare local model to download it.")
                    elif config["provider"] == "hosted":
                        test_config = {**config, "protocol": "json", "json_mode": False, "response_tokens": 256, "request_timeout": 30}
                        answer = ModelClient(test_config, data.get('api_key') or app.settings.key()).complete([
                            {"role": "system", "content": 'Return exactly {"message":"Ready","status":"completed"} as JSON.'},
                            {"role": "user", "content": "Test the connection."}], threading.Event())
                        result = json.loads(answer['content'])
                        if result.get('status') != 'completed':
                            raise ValueError('The connection test did not complete')
                    return self.send(app.settings.update({**data, "configured": True}))
                if self.path == "/api/setup":
                    app.local.prepare(data.get("model", "qwen3:4b-instruct"))
                    return self.send(app.local.public())
                if self.path == '/api/isolation/setup':
                    app.agent.appliance.prepare()
                    return self.send(app.agent.appliance.public())
                if self.path == "/api/start":
                    task = data.get("task", "").strip()
                    if not task or len(task) > 12000:
                        raise ValueError("Describe your task in 12,000 characters or fewer")
                    if not app.settings.values["configured"]:
                        raise ValueError("Connect a model first, or try the interactive demo")
                    app.agent.appliance.verify()
                    if app.settings.values['provider'] == 'ollama' and app.local.public()['busy']:
                        raise ValueError('Your local model engine is starting. Give it a moment, then start the task.')
                    session = app.store.create(task, app.settings.values["provider"], app.settings.values["model"])
                    app.agent.start(session)
                    return self.send({"id": session["id"]})
                if self.path == '/api/try-seed':
                    candidate = app.store.get(data.get('id'))
                    task = data.get('task', candidate['task'])
                    if not isinstance(task, str) or not task.strip() or len(task) > 12000:
                        raise ValueError('Describe the test task in 12,000 characters or fewer')
                    session = app.store.create(task, app.settings.values['provider'], app.settings.values['model'])
                    session['candidate_from'] = candidate['id']
                    app.agent.start(session, candidate=candidate)
                    return self.send({'id': session['id']})
                if self.path in ("/api/resume", "/api/stop", "/api/reset", "/api/open-workspace"):
                    session = app.store.get(data.get("id"))
                    if self.path == "/api/resume":
                        message = data.get("message", "")
                        if not isinstance(message, str) or len(message) > 12000:
                            raise ValueError("Keep your reply under 12,000 characters")
                        app.agent.start(session, message)
                    elif self.path == "/api/stop":
                        app.agent.stop(session["id"])
                    elif self.path == '/api/reset':
                        app.agent.stop(session['id'])
                        worker = app.agent.workers.get(session['id'])
                        if worker:
                            worker[1].join(timeout=5)
                        session.pop('candidate_from', None)
                        app.agent.start(session)
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
            except Exception as error:
                self.send({"error": str(error)}, 400)
    return Handler


def make_server(app, port=47831):
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(app))
    server.daemon_threads = True
    app.server = server
    return server
