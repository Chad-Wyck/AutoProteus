"""Workspace file tools and optional native terminal execution."""
from __future__ import annotations

import threading
from pathlib import Path

from .search import search_files
from .terminal import run_command, terminate

LIMIT = 12000
READ_DEFAULT = 1000
TEXT_CHARACTER_LIMIT = 100000
WRITE_LIMIT = TEXT_CHARACTER_LIMIT  # Compatibility name; the unit is characters.


class Cancelled(Exception):
    pass


class EditConflict(ValueError):
    def __init__(self, message, details):
        super().__init__(message)
        self.details = details


def clipped(text, limit=LIMIT):
    return text if len(text) <= limit else text[:limit] + "\n[Output shortened; read a smaller section if needed.]"


class Workspace:
    def read_text(self, path, missing_ok=False):
        """Processing helper: read up to 100000 characters, preserving CRLF.

        Use this inside text tools. The model-facing read_file/read_section
        tools have a separate 12000-character display limit.
        """
        if self.cancel.is_set():
            raise Cancelled()
        path = self.path(str(path) if isinstance(path, Path) else path)
        try:
            with path.open("r", encoding="utf-8", newline="") as stream:
                text = stream.read(TEXT_CHARACTER_LIMIT + 1)
        except FileNotFoundError:
            if missing_ok:
                return ""
            raise
        if len(text) > TEXT_CHARACTER_LIMIT:
            raise ValueError("Read text of at most 100,000 characters")
        if self.cancel.is_set():
            raise Cancelled()
        return text

    def write_text(self, path, content):
        """Replace UTF-8 text after character-limit validation; create parents."""
        path = self.path(str(path) if isinstance(path, Path) else path)
        if not isinstance(content, str) or len(content) > TEXT_CHARACTER_LIMIT:
            raise ValueError("Write a text string of at most 100,000 characters")
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.cancel.is_set():
            raise Cancelled()
        data = content.encode("utf-8")
        path.write_bytes(data)
        return {"path": str(path.relative_to(self.root)), "bytes": len(data), "written": True}

    def __init__(self, root: Path, terminal=False, cancel=None, timeout=60):
        self.root = root.resolve()
        self.terminal = terminal
        self.cancel = cancel or threading.Event()
        self.timeout = timeout

    def path(self, value="."):
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError("Use a relative workspace path")
        candidate = (self.root / value).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("This path is outside the session workspace")
        return candidate

    def execute(self, tool, args):
        if self.cancel.is_set():
            raise Cancelled()
        if not isinstance(args, dict):
            raise ValueError("Action arguments must be an object")
        if tool == "list_files":
            path = self.path(args.get("path", "."))
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            return {"files": [{"name": p.name, "directory": p.is_dir(), "bytes": p.stat().st_size if p.is_file() else None}
                              for p in entries[:200]], "truncated": len(entries) > 200}
        if tool == "delete_file":
            value = args['path']
            if not isinstance(value, str) or (self.root / value).is_symlink():
                raise ValueError('Delete an ordinary workspace file')
            path = self.path(value)
            if not path.is_file():
                raise ValueError('Delete an existing ordinary file, not a directory')
            if self.cancel.is_set():
                raise Cancelled()
            path.unlink()
            return {'path': value, 'deleted': True}
        if tool == 'search_files':
            return search_files(self, args)
        if tool == 'web_request':
            from .web import web_request
            return web_request(self, args)
        if tool in ("read_file", "read_section"):
            from .file_ops import read_file
            return read_file(self, tool, args)
        if tool == "write_file":
            return self.write_text(args["path"], args["content"])
        if tool == "edit_file":
            from .file_ops import edit_file
            return edit_file(self, args)
        if tool == "run_command":
            if not self.terminal:
                raise ValueError("Terminal access is disabled. Use file tools or ask the user to enable it in Settings.")
            return self.command(args["command"])
        raise ValueError("Unknown tool: " + str(tool))

    def command(self, command):
        return run_command(self, command)

    _terminate = staticmethod(terminate)
