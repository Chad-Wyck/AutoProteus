"""Workspace file tools and optional native terminal execution."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

LIMIT = 12000


class Cancelled(Exception):
    pass


def clipped(text, limit=LIMIT):
    return text if len(text) <= limit else text[:limit] + "\n[Output shortened; read a smaller section if needed.]"


class Workspace:
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
        if tool == "read_file":
            path = self.path(args["path"])
            offset = max(0, int(args.get("offset", 0)))
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                # Bound reads even for unexpectedly large files.
                stream.seek(min(offset, 10000000))
                content = stream.read(LIMIT + 1)
            return {"path": args["path"], "content": clipped(content), "offset": offset}
        if tool in ("write_file", "update_todo"):
            target = "todo.txt" if tool == "update_todo" else args["path"]
            path = self.path(target)
            content = args["content"]
            if not isinstance(content, str) or len(content) > 100000:
                raise ValueError("Write a text string of at most 100,000 characters")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"path": str(path.relative_to(self.root)), "bytes": len(content.encode("utf-8")), "written": True}
        if tool == "run_command":
            if not self.terminal:
                raise ValueError("Terminal access is disabled. Use file tools or ask the user to enable it in Settings.")
            return self.command(args["command"])
        raise ValueError("Unknown tool: " + str(tool))

    def command(self, command):
        if not isinstance(command, str) or not command.strip() or len(command) > 20000:
            raise ValueError("Provide a nonempty command of at most 20,000 characters")
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command] if os.name == "nt" else ["/bin/sh", "-c", command]
        if os.name == "nt":
            argv[-1] = "$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); " + command
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        # Spool output to disk to avoid retaining unlimited subprocess output in RAM.
        output_path = self.root / ".terminal-output"
        with output_path.open("wb") as stream:
            process = subprocess.Popen(argv, cwd=self.root, stdin=subprocess.DEVNULL, stdout=stream,
                                       stderr=subprocess.STDOUT, **kwargs)
            started = time.monotonic()
            timed_out = False
            output_limited = False
            try:
                while process.poll() is None:
                    if self.cancel.is_set() or time.monotonic() - started > self.timeout or output_path.stat().st_size > 32000000:
                        timed_out = not self.cancel.is_set()
                        output_limited = output_path.stat().st_size > 32000000
                        if output_limited:
                            timed_out = False
                        self._terminate(process)
                        break
                    time.sleep(0.1)
                process.wait(timeout=10)
            finally:
                if process.poll() is None:
                    self._terminate(process)
        with output_path.open("rb") as stream:
            output = stream.read(48000).decode("utf-8", errors="replace")
        if self.cancel.is_set():
            raise Cancelled()
        return {"exit_code": process.returncode, "output": clipped(output), "timed_out": timed_out, "output_limited": output_limited}

    @staticmethod
    def _terminate(process):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        else:
            import signal
            os.killpg(process.pid, signal.SIGKILL)
