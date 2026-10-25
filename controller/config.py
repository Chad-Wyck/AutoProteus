"""User configuration; credentials are kept out of session journals."""
import base64
import ctypes
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse

from .storage import atomic_json

DEFAULTS = {
    "configured": False, "provider": "ollama", "base_url": "http://127.0.0.1:11434",
    "model": "qwen3:4b-instruct", "context_tokens": 32768, "response_tokens": 8192,
    "temperature": 0.2, "max_steps": 128, "request_timeout": 300,
    "command_timeout": 60, "terminal": False, "json_mode": False, "thinking": None,
    "protocol": "native", "internet": True,
}


def protect(value, decrypt=False):
    if os.name != "nt":
        raise ValueError("Saved credentials require Windows. Set AUTOPROTEUS_API_KEY instead.")
    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    # CRYPTPROTECT_UI_FORBIDDEN; DPAPI binds the saved key to this Windows account.
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError("Windows could not unlock the saved credential. Enter the key again.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


class Settings:
    def __init__(self, directory: Path):
        self.lock = threading.RLock()
        self.directory = directory
        self.path = directory / "settings.json"
        self.values = dict(DEFAULTS)
        if self.path.exists():
            try:
                self.values.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        # Missing preferences inherit the default. Saved False stays off;
        # invalid non-boolean values fail closed instead of becoming truthy.
        self.values['internet'] = self.values.get('internet') is True
        self.memory_key = ""

    def key(self):
        if self.memory_key:
            return self.memory_key
        if os.environ.get("AUTOPROTEUS_API_KEY"):
            return os.environ["AUTOPROTEUS_API_KEY"]
        path = self.directory / "credential.bin"
        if os.name == 'nt' and path.exists():
            return protect(base64.b64decode(path.read_bytes()), decrypt=True).decode()
        return ""

    def public(self):
        value = dict(self.values)
        value['has_key'] = bool(self.memory_key or os.environ.get('AUTOPROTEUS_API_KEY') or
                                (os.name == 'nt' and (self.directory / 'credential.bin').exists()))
        return value

    def update(self, data):
        with self.lock:
            return self._update(data)

    def preview(self, data):
        with self.lock:
            return self._update(data, save=False)

    def record_compatibility(self, result):
        with self.lock:
            self.values['compatibility'] = dict(result)
            atomic_json(self.path, self.values)
            return self.public()

    def _update(self, data, save=True):
        candidate = dict(self.values)
        for key in DEFAULTS:
            if key in data:
                candidate[key] = data[key]
        if candidate["provider"] not in ("ollama", "hosted", "demo"):
            raise ValueError("Choose a local model, hosted connection, or demo")
        if candidate["protocol"] not in ("native", "json"):
            raise ValueError("Action format must be native or json")
        parsed = urlparse(candidate["base_url"])
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Enter a valid service URL without credentials or query parameters")
        if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Remote model services must use HTTPS")
        if not isinstance(candidate["model"], str) or not candidate["model"].strip() or len(candidate["model"]) > 160:
            raise ValueError("Enter a model name")
        for key, low, high in (("context_tokens", 2048, 131072), ("response_tokens", 256, 16384),
                              ("max_steps", 1, 200), ("request_timeout", 10, 600), ("command_timeout", 1, 300)):
            candidate[key] = int(candidate[key])
            if not low <= candidate[key] <= high:
                raise ValueError(f"{key.replace('_', ' ')} must be between {low} and {high}")
        if candidate["response_tokens"] >= candidate["context_tokens"]:
            raise ValueError("The response budget must be smaller than the context window")
        candidate["temperature"] = float(candidate["temperature"])
        if not 0 <= candidate["temperature"] <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        for key in ("configured", "terminal", "json_mode", "internet"):
            if not isinstance(candidate[key], bool):
                raise ValueError(f"{key} must be true or false")
        if candidate["thinking"] not in (None, True, False):
            raise ValueError("Thinking must be automatic, enabled, or disabled")
        key = data.get("api_key", "")
        if key:
            if not isinstance(key, str) or len(key) > 4096:
                raise ValueError("Invalid API key")
        if not save:
            return candidate
        if key or data.get('clear_key') or any(candidate[k] != self.values[k] for k in
                ('provider', 'base_url', 'model', 'protocol', 'json_mode', 'thinking', 'context_tokens', 'response_tokens',
                 'temperature', 'terminal', 'request_timeout')):
            candidate.pop('compatibility', None)
        if key:
            if os.name == "nt":
                self.directory.mkdir(parents=True, exist_ok=True)
                (self.directory / "credential.bin").write_bytes(base64.b64encode(protect(key.encode())))
            self.memory_key = key
        if data.get("clear_key"):
            self.memory_key = ""
            if os.name == 'nt':
                (self.directory / 'credential.bin').unlink(missing_ok=True)
        self.values = candidate
        atomic_json(self.path, candidate)
        return self.public()
