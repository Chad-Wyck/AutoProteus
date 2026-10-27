"""Cross-process VM ownership; foreground work takes priority over prewarming."""
import os
import time

from .artifacts import safe_path
from .errors import Cancelled, IsolationError


def _open(path):
    stream=path.open('a+b')
    if not path.stat().st_size:
        stream.write(b'0');stream.flush()
    return stream


def _try_lock(stream):
    try:
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return True
    except OSError:
        return False


class VMLease:
    """The demand gate stays held while a foreground caller waits for the VM.

    Idle cache owners observe that gate and release their VM. Active work never
    yields. Background acquisition is nonblocking and cannot jump the gate.
    OS locks automatically clear when a requester exits; no stale signal files.
    """
    def __init__(self,directory):
        self.path=safe_path(directory,'active-vm.lock')
        self.demand=safe_path(directory,'active-vm-demand.lock')
        self.stream=None

    def request_pending(self):
        with _open(self.demand) as stream:
            return not _try_lock(stream)

    def acquire(self,cancel,deadline,on_wait=None,*,background=False):
        gate=_open(self.demand);stream=None
        try:
            while True:
                if cancel.is_set():raise Cancelled()
                if time.monotonic()>deadline:raise IsolationError('Timed out waiting for the isolated environment')
                if _try_lock(gate):break
                if background:raise IsolationError('Foreground work has priority over VM prewarming')
                if on_wait:on_wait();on_wait=None
                cancel.wait(.1)
            stream=_open(self.path)
            while True:
                if cancel.is_set():raise Cancelled()
                if time.monotonic()>deadline:raise IsolationError('Timed out waiting for the isolated environment')
                if _try_lock(stream):
                    self.stream=stream;stream=None
                    return
                if background:raise IsolationError('The VM slot is in use')
                if on_wait:on_wait();on_wait=None
                cancel.wait(.1)
        finally:
            gate.close()
            if stream:stream.close()

    def close(self):
        if self.stream:
            self.stream.close();self.stream=None
