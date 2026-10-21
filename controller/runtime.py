"""Optional, project-local Ollama bootstrap with visible download progress."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from .providers import request_json, ProviderError, ERROR_MESSAGES
from .compatibility import qualify_profile as check_protocol
from .integrity import record_runtime, verify_runtime


ENGINE_PORT = 11435


class LocalRuntime:
    def __init__(self, root, settings):
        self.root, self.settings = Path(root), settings
        self.lock = threading.Lock()
        self.lifecycle_lock = threading.Lock()
        self.state = {"busy": False, "phase": "idle", "message": "", "progress": None}
        self.process = None
        self.job = None
        self.closed = threading.Event()

    def pin(self):
        pins = json.loads((self.root / 'controller/managed-runtime-lock.json').read_text(encoding='utf-8'))
        return pins['ollama_linux' if sys.platform == 'linux' else 'ollama_windows']

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
            self.update(busy=False, phase='error', message=ERROR_MESSAGES[error.category] if isinstance(error, ProviderError) else str(error), progress=None)

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
        if self.closed.is_set():
            raise ValueError('The app is closing')
        base = self.settings.values["base_url"]
        try:
            self.models(base)
            return base
        except ProviderError:
            pass
        portable = (self.root / '.runtime/ollama-linux/bin/ollama' if sys.platform == 'linux' else
                    self.root / '.runtime/ollama/ollama.exe')
        installed = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Ollama' / 'ollama.exe'
        binary = str(portable) if portable.exists() else shutil.which('ollama') or (str(installed) if installed.exists() else str(portable))
        if binary == str(portable) and portable.exists():
            try:
                verify_runtime(portable.parents[1] if sys.platform == 'linux' else portable.parent, self.pin())
            except ValueError:
                if not allow_download:
                    raise
                self._download_runtime()
        if not Path(binary).exists():
            if not allow_download:
                raise ValueError('Your local engine is not available. Use model setup to prepare it or reconnect an existing service.')
            if os.name != 'nt' and sys.platform != 'linux':
                raise ValueError('Automatic engine setup supports Windows and Linux.')
            self._download_runtime()
        if binary == str(portable):
            verify_runtime(portable.parents[1] if sys.platform == 'linux' else portable.parent, self.pin())
        base = f"http://127.0.0.1:{ENGINE_PORT}"
        # Reuse a managed server from a previous app launch, if it is still alive.
        try:
            self.models(base)
            return base
        except ProviderError:
            pass
        self.update(phase="starting", message="Starting your local model service…", progress=None)
        environment = dict(os.environ, OLLAMA_HOST=f"127.0.0.1:{ENGINE_PORT}", OLLAMA_MODELS=str(self.root / ".data" / "models"),
                           OLLAMA_MAX_LOADED_MODELS='1', OLLAMA_NUM_PARALLEL='1')
        log_path = self.root / ".data" / "ollama.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lifecycle_lock, log_path.open("ab") as log:
            if self.closed.is_set():
                raise ValueError('The app is closing')
            if os.name == 'nt':
                from .windows_job import Job
                self.job = Job(vm_limits=False)
            else:
                from .linux_process import Job, command
                self.job = Job()
            try:
                arguments = [binary, 'serve'] if os.name == 'nt' else command(binary, ['serve'], 'engine')
                self.process = subprocess.Popen(arguments, env=environment, cwd=self.root,
                    stdout=log, stderr=log,
                    creationflags=(subprocess.CREATE_NO_WINDOW | 0x4) if os.name == "nt" else 0,
                    **({} if os.name == 'nt' else {'start_new_session': True}))
                if self.job:
                    self.job.attach_and_resume(self.process)
            except Exception:
                if self.job:
                    self.job.close(); self.job = None
                if self.process and self.process.poll() is None:
                    self.process.kill(); self.process.wait(timeout=5)
                raise
            process = self.process
        for _ in range(80):
            if self.closed.is_set():
                raise ValueError('The app is closing')
            try:
                self.models(base)
                return base
            except ProviderError:
                if process.poll() is not None:
                    raise ValueError("The local model service could not start. See .data/ollama.log for details.")
                time.sleep(0.5)
        raise ValueError("The local model service did not start in time. Try again or connect an existing service.")

    def _download_runtime(self):
        self.update(phase="download", message="Downloading the local model engine…", progress=None)
        pin = self.pin()
        linux = sys.platform == 'linux'
        if linux and platform.machine().lower() not in ('x86_64', 'amd64'):
            raise ValueError('Automatic Linux engine setup currently supports 64-bit Intel/AMD computers.')
        asset = {'size': pin['size'], 'browser_download_url': pin['url'], 'digest': 'sha256:' + pin['sha256']}
        if linux and (not shutil.which('zstd') or not hasattr(tarfile, 'data_filter')):
            raise ValueError('Reopen the Linux launcher to complete the bundled runtime setup.')
        if linux and not str(asset.get('digest', '')).startswith('sha256:'):
            raise ValueError('The official Linux runtime has no integrity checksum. Please retry later.')
        directory = self.root / ".runtime"
        directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(directory).free < asset["size"] * 3 + 4000000000:
            raise ValueError("There is not enough free disk space for the local engine and model. Free some space or use a hosted connection.")
        archive = directory / ('ollama-linux-download.tar.zst' if linux else 'ollama-download.zip')
        digest = hashlib.sha256()
        downloaded = 0
        request = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "AutoProteus-Seed"})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as destination:
            while chunk := response.read(1024 * 1024):
                destination.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if downloaded > asset['size']:
                    raise ValueError('The runtime download exceeded its declared size.')
                self.update(progress=min(99, round(downloaded / max(1, asset["size"]) * 100)),
                            message=f"Downloading local engine · {downloaded // 1048576:,} MB")
        expected = asset.get("digest", "") or ""
        if expected.startswith("sha256:") and digest.hexdigest() != expected.split(":", 1)[1]:
            archive.unlink(missing_ok=True)
            raise ValueError("The runtime download did not pass its checksum. Please retry.")
        self.update(phase="extract", message="Preparing the local engine…", progress=None)
        if downloaded != asset['size']:
            raise ValueError('The runtime download was interrupted. Please retry.')
        if linux:
            self._extract_linux(archive, directory / 'ollama-linux', asset['size'])
            record_runtime(directory / 'ollama-linux', pin)
            archive.unlink(missing_ok=True)
            return
        target = directory / 'ollama'
        with tempfile.TemporaryDirectory(prefix='ollama-win-stage-', dir=directory) as stage:
            with zipfile.ZipFile(archive) as bundle:
                if len(bundle.infolist()) > 50000 or sum(m.file_size for m in bundle.infolist()) > 16 * 1024**3:
                    raise ValueError('The runtime archive exceeded its extraction limits')
                for member in bundle.infolist():
                    path = (Path(stage) / member.filename).resolve()
                    if not path.is_relative_to(Path(stage).resolve()) or ':' in member.filename or '\\' in member.filename or (member.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError('The runtime archive contains an unexpected path')
                bundle.extractall(stage)
            if not (Path(stage) / 'ollama.exe').is_file():
                raise ValueError('The runtime archive is missing its executable')
            record_runtime(stage, pin)
            if target.exists():
                if target.is_symlink():
                    raise ValueError('The runtime cache contains an unexpected link')
                target.rename(target.with_name('ollama-incomplete-' + str(time.time_ns())))
            Path(stage).rename(target)
        archive.unlink(missing_ok=True)

    def _extract_linux(self, archive, target, compressed_size):
        """Verify tar paths and links in a fresh directory before publishing a runtime."""
        total, count = 0, 0

        def checked(member, destination):
            nonlocal total, count
            total += member.size
            count += 1
            if total > min(16 * 1024**3, compressed_size * 40) or count > 50000:
                raise ValueError('The runtime archive exceeded its extraction limits.')
            return tarfile.data_filter(member, destination)

        with tempfile.TemporaryDirectory(prefix='ollama-linux-stage-', dir=target.parent) as stage:
            process = subprocess.Popen([shutil.which('zstd'), '-d', '-c', str(archive)],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                with tarfile.open(fileobj=process.stdout, mode='r|') as bundle:
                    bundle.extractall(stage, filter=checked)
                if process.wait(timeout=10) != 0:
                    raise ValueError('The Linux engine archive could not be decompressed.')
                binary = Path(stage) / 'bin/ollama'
                if not binary.is_file() or not os.access(binary, os.X_OK):
                    raise ValueError('The Linux engine archive is missing its executable.')
                if target.exists():
                    if target.is_symlink() or not target.resolve().is_relative_to(self.root.resolve() / '.runtime'):
                        raise ValueError('The Linux runtime cache contains an unexpected link.')
                    target.rename(target.with_name('ollama-linux-incomplete-' + str(time.time_ns())))
                Path(stage).rename(target)
            finally:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=5)
                process.stdout.close()

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
            config = self.settings.preview({'provider': 'ollama', 'base_url': base, 'model': model, 'thinking': None})
            self.update(phase='check', message='Checking repeated tool replies and error recovery…', progress=None)
            compatibility = check_protocol(config, self.settings.key())
            self.settings.update({"provider": "ollama", "base_url": base, "model": model, "configured": True,
                                  "thinking": None})
            self.settings.record_compatibility(compatibility)
            self.update(busy=False, phase="ready", message=f"{model} is ready", progress=100)
        except Exception as error:
            self.update(busy=False, phase="error", message=ERROR_MESSAGES[error.category] if isinstance(error, ProviderError) else str(error), progress=None)

    def close(self):
        self.closed.set()
        with self.lifecycle_lock:
            if self.job:
                self.job.close(); self.job = None
            if self.process and self.process.poll() is None:
                if os.name == 'nt':
                    self.process.terminate()
                else:
                    import signal
                    os.killpg(self.process.pid, signal.SIGTERM)
            if self.process:
                self.process.wait(timeout=5)
