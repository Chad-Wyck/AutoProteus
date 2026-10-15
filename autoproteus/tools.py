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
        """Read bounded UTF-8 text; character counts and CRLF stay unchanged."""
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
        if tool in ("read_file", "read_section"):
            path = self.path(args["path"])
            if tool == "read_file" and any(key in args for key in ("offset", "start", "length")):
                raise ValueError("read_file reads the whole file; use read_section with character start and length")
            start = args.get("start", 0) if tool == "read_section" else 0
            length = args.get("length", READ_DEFAULT) if tool == "read_section" else LIMIT
            if "offset" in args:
                raise ValueError("Use read_section with a character start, not a byte offset")
            if type(start) is not int or start < 0:
                raise ValueError("start must be a nonnegative character position; use next_start to continue")
            if type(length) is not int or not 1 <= length <= LIMIT:
                raise ValueError(f"length must be between 1 and {LIMIT} characters")
            try:
                # Preserve CRLF and skip by characters without allocating the prefix.
                with path.open("r", encoding="utf-8", newline="") as stream:
                    remaining = start
                    while remaining:
                        if self.cancel.is_set():
                            raise Cancelled()
                        skipped = stream.read(min(remaining, LIMIT))
                        if not skipped:
                            break
                        remaining -= len(skipped)
                    content = stream.read(length + 1)
            except UnicodeDecodeError:
                raise ValueError("Read a valid UTF-8 text file") from None
            eof = len(content) <= length
            if tool == "read_file" and not eof:
                raise ValueError(f"This file exceeds {LIMIT} characters; use read_section with start and length")
            content = content[:length]
            return {"path": args["path"], "content": content, "start": start,
                    "next_start": start + len(content), "eof": eof}
        if tool == "write_file":
            return self.write_text(args["path"], args["content"])
        if tool == "edit_file":
            path = self.path(args["path"])
            old, new = args["old_text"], args["new_text"]
            if not isinstance(old, str) or not old or not isinstance(new, str):
                raise ValueError("Supply a nonempty old_text and a text new_text")
            if max(len(old), len(new)) > TEXT_CHARACTER_LIMIT:
                raise ValueError("Edit text must be at most 100,000 characters")
            with path.open("rb") as stream:
                raw = stream.read(TEXT_CHARACTER_LIMIT * 4 + 1)
            if len(raw) > TEXT_CHARACTER_LIMIT * 4:
                raise ValueError("Edit files of at most 100,000 UTF-8 characters")
            content = raw.decode("utf-8")
            if len(content) > TEXT_CHARACTER_LIMIT:
                raise ValueError("Edit files of at most 100,000 UTF-8 characters")
            start = content.find(old)
            if start < 0 or content.find(old, start + 1) >= 0:
                count, locations, position = 0, [], start
                while position >= 0 and count < 50:
                    count += 1
                    if len(locations) < 3:
                        context_start = max(0, position - 80)
                        locations.append({'start': position, 'line': content.count('\n', 0, position) + 1,
                                          'context_start': context_start,
                                          'content': content[context_start:position + min(len(old), 160) + 80]})
                    position = content.find(old, position + 1)
                hint = ('Read one listed location with read_section and include enough surrounding text for one match.'
                        if count else 'Search for a short distinctive fragment, then read the current section and copy its exact text.')
                if not count and old.replace('\r\n', '\n') in content.replace('\r\n', '\n'):
                    hint = 'The line endings differ. Read the current section and preserve its exact newline characters.'
                raise EditConflict(f'old_text {"was not found" if not count else "is ambiguous"}: {count}{"+" if position >= 0 else ""} matches. No file was changed.',
                                   {'matches': count, 'matches_truncated': position >= 0, 'locations': locations, 'hint': hint})
            updated = content[:start] + new + content[start + len(old):]
            if len(updated) > TEXT_CHARACTER_LIMIT:
                raise ValueError("The edited file would exceed 100,000 characters")
            if self.cancel.is_set():
                raise Cancelled()
            path.write_bytes(updated.encode("utf-8"))
            return {"path": str(path.relative_to(self.root)), "bytes": len(updated.encode("utf-8")), "replacements": 1}
        if tool == "run_command":
            if not self.terminal:
                raise ValueError("Terminal access is disabled. Use file tools or ask the user to enable it in Settings.")
            return self.command(args["command"])
        raise ValueError("Unknown tool: " + str(tool))

    def command(self, command):
        return run_command(self, command)

    _terminate = staticmethod(terminate)
