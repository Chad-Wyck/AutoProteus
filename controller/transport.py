"""Bounded message transport shared by isolated and explicit native workers."""
import json
import queue
import threading
import time

from .errors import Cancelled, IsolationError

PREFIX = b'AP1 '
MAX_FRAME = 4 * 1024 * 1024
MAX_WIRE = 100 * 1024 * 1024


class WorkerTransport:
    """Bounded pipe protocol shared by VM and opt-in native workers."""
    def __init__(self):
        self.job, self.process = None, None
        self.frames = queue.Queue(maxsize=8)
        self.stderr = bytearray()
        self.output_bytes = 0
        self.closed = threading.Event()
        self.close_lock = threading.Lock()

    def start_readers(self):
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._errors, daemon=True).start()

    def _errors(self):
        while chunk := self.process.stderr.read1(4096):
            if len(self.stderr) < 64000:
                self.stderr.extend(chunk[:64000 - len(self.stderr)])

    def _read(self):
        try:
            while not self.closed.is_set():
                raw = self.process.stdout.readline(MAX_FRAME + 1)
                if not raw:
                    raise IsolationError('The VM closed: ' + self.stderr.decode(errors='replace')[-2000:])
                self.output_bytes += len(raw)
                if len(raw) > MAX_FRAME or self.output_bytes > MAX_WIRE:
                    raise IsolationError('Guest output quota exceeded')
                if raw.startswith(PREFIX):
                    value = json.loads(raw[len(PREFIX):])
                    while not self.closed.is_set():
                        try:
                            self.frames.put(value, timeout=0.1)
                            break
                        except queue.Full:
                            pass
        except Exception as error:
            try:
                self.frames.put(error, timeout=0.1)
            except queue.Full:
                self.close()

    def send(self, value):
        raw = PREFIX + json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode() + b'\n'
        if len(raw) > MAX_FRAME:
            raise IsolationError('Host transfer is too large')
        view = memoryview(raw)
        while view and not self.closed.is_set():
            count = self.process.stdin.write(view)
            if not count:
                raise IsolationError('VM transport closed')
            view = view[count:]
        self.process.stdin.flush()

    def next(self, cancel, deadline):
        while True:
            if cancel.is_set():
                raise Cancelled()
            if time.monotonic() > deadline:
                raise IsolationError('The isolated run reached its time limit')
            try:
                value = self.frames.get(timeout=0.1)
                if isinstance(value, Exception):
                    raise value
                if not isinstance(value, dict):
                    raise IsolationError('Invalid guest message')
                return value
            except queue.Empty:
                if self.process.poll() is not None:
                    raise IsolationError('The VM could not start: ' + self.stderr.decode(errors='replace')[-2000:])

    def close(self):
        with self.close_lock:
            if self.closed.is_set():
                return
            self.closed.set()
            if self.job:
                self.job.close()
            if self.process:
                self.kill()
                self.process.wait(timeout=5)
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if stream is not None:
                        stream.close()
            self.cleanup()

    def kill(self):
        if self.process.poll() is None:
            self.process.kill()

    def cleanup(self):
        pass
