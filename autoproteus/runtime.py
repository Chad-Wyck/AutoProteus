"""Optional, project-local Ollama bootstrap with visible download progress."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from .providers import request_json, ProviderError


class LocalRuntime:
    def __init__(self, root, settings):
        self.root, self.settings = Path(root), settings
        self.lock = threading.Lock()
        self.state = {"busy": False, "phase": "idle", "message": "", "progress": None}
        self.process = None
        self.closed = threading.Event()

    def restore(self):
        if self.settings.values['configured'] and self.settings.values['provider'] == 'ollama':
            self.update(busy=True, phase='starting', message='Starting your local model service…', progress=None)
            threading.Thread(target=self._restore, daemon=True).start()

    def _restore(self):
        try:
            base = self.ensure_service(allow_download=False)
            self.settings.update({'base_url': base})
            self.update(busy=False, phase='ready', message='Your local model is ready', progress=100)
        except Exception as error:
            self.settings.update({'configured': False})
            self.update(busy=False, phase='error', message=str(error), progress=None)

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def public(self):
        with self.lock:
            return dict(self.state)

    def models(self, base=None):
        base = base or self.settings.values["base_url"]
        result = request_json(base.rstrip("/") + "/api/tags", timeout=3)
        return [{"name": item["name"], "bytes": item.get("size", 0)} for item in result.get("models", [])]

    def prepare(self, model):
        if not isinstance(model, str) or not model.strip() or len(model) > 160 or any(c.isspace() for c in model):
            raise ValueError("Enter a model name from the Ollama library")
        with self.lock:
            if self.state["busy"]:
                raise ValueError("A model is already being prepared")
            self.state = {"busy": True, "phase": "starting", "message": "Checking your local model service…", "progress": None}
        threading.Thread(target=self._prepare, args=(model,), daemon=True).start()

    def ensure_service(self, allow_download=True):
        base = self.settings.values["base_url"]
        try:
            self.models(base)
            return base
        except ProviderError:
            pass
        portable = self.root / '.runtime' / 'ollama' / 'ollama.exe'
        installed = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Ollama' / 'ollama.exe'
        binary = str(portable) if portable.exists() else shutil.which('ollama') or (str(installed) if installed.exists() else str(portable))
        if not Path(binary).exists():
            if not allow_download:
                raise ValueError('Your local engine is not available. Use model setup to prepare it or reconnect an existing service.')
            if os.name != "nt":
                raise ValueError("Install Ollama on this computer, then connect it in Settings. Automatic runtime setup currently supports Windows.")
            self._download_runtime()
        base = "http://127.0.0.1:11435"
        # Reuse a managed server from a previous app launch, if it is still alive.
        try:
            self.models(base)
            return base
        except ProviderError:
            pass
        self.update(phase="starting", message="Starting your local model service…", progress=None)
        environment = dict(os.environ, OLLAMA_HOST="127.0.0.1:11435", OLLAMA_MODELS=str(self.root / ".data" / "models"))
        log_path = self.root / ".data" / "ollama.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log:
            if self.closed.is_set():
                raise ValueError('The app is closing')
            self.process = subprocess.Popen([binary, "serve"], env=environment, cwd=self.root,
                                            stdout=log, stderr=log,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(80):
            try:
                self.models(base)
                return base
            except ProviderError:
                if self.process.poll() is not None:
                    raise ValueError("The local model service could not start. See .data/ollama.log for details.")
                time.sleep(0.5)
        raise ValueError("The local model service did not start in time. Try again or connect an existing service.")

    def _download_runtime(self):
        self.update(phase="download", message="Downloading the local model engine…", progress=None)
        release = request_json("https://api.github.com/repos/ollama/ollama/releases/latest", headers={"User-Agent": "AutoProteus-Seed"}, timeout=30)
        asset = next((a for a in release["assets"] if a["name"] == "ollama-windows-amd64.zip"), None)
        if not asset:
            raise ValueError("The official Windows runtime download is unavailable. Connect an installed Ollama service instead.")
        directory = self.root / ".runtime"
        directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(directory).free < asset["size"] * 3 + 4000000000:
            raise ValueError("There is not enough free disk space for the local engine and model. Free some space or use a hosted connection.")
        archive = directory / "ollama-download.zip"
        digest = hashlib.sha256()
        downloaded = 0
        request = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "AutoProteus-Seed"})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as destination:
            while chunk := response.read(1024 * 1024):
                destination.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                self.update(progress=min(99, round(downloaded / max(1, asset["size"]) * 100)),
                            message=f"Downloading local engine · {downloaded // 1048576:,} MB")
        expected = asset.get("digest", "") or ""
        if expected.startswith("sha256:") and digest.hexdigest() != expected.split(":", 1)[1]:
            archive.unlink(missing_ok=True)
            raise ValueError("The runtime download did not pass its checksum. Please retry.")
        self.update(phase="extract", message="Preparing the local engine…", progress=None)
        target = directory / "ollama"
        target.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                path = (target / member.filename).resolve()
                if not path.is_relative_to(target.resolve()) or ":" in member.filename:
                    raise ValueError("The runtime archive contains an unexpected path")
            bundle.extractall(target)
        archive.unlink(missing_ok=True)

    def _prepare(self, model):
        try:
            base = self.ensure_service()
            self.update(phase="model", message=f"Downloading {model}…", progress=None)
            request = urllib.request.Request(base + "/api/pull", data=json.dumps({"model": model, "stream": True}).encode(),
                                             headers={"Content-Type": "application/json"})
            completed = False
            with urllib.request.urlopen(request, timeout=600) as response:
                for line in response:
                    item = json.loads(line)
                    if item.get("error"):
                        raise ValueError(item["error"])
                    progress = round(item.get("completed", 0) / item["total"] * 100) if item.get("total") else None
                    self.update(message=str(item.get("status", "Preparing model…")), progress=progress)
                    if item.get("status") == "success":
                        completed = True
            if not completed:
                raise ValueError("The model download was interrupted. Try again; Ollama can reuse downloaded layers.")
            self.settings.update({"provider": "ollama", "base_url": base, "model": model, "configured": True,
                                  "thinking": None})
            self.update(busy=False, phase="ready", message=f"{model} is ready", progress=100)
        except Exception as error:
            self.update(busy=False, phase="error", message=str(error), progress=None)

    def close(self):
        self.closed.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
