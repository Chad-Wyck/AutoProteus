"""Trusted Linux process supervisor; never copied into the editable seed."""
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time


def start_time(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def group_running(group):
    """Exited zombies cannot retain sockets; live group members still can."""
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue  # A process may finish while the group is being inspected.
        if fields[0] not in ('Z', 'X') and int(fields[2]) == group:
            return True
    return False


def command(binary, arguments, profile):
    return [sys.executable, '-I', '-B', '-u', str(Path(__file__).resolve()),
            str(os.getpid()), start_time(os.getpid()), profile, str(binary), *arguments]


class Job:
    def __init__(self):
        self.descriptor = None
        self.group = None

    def attach_and_resume(self, process):
        # The child supervisor sets limits before starting its actual program.
        self.descriptor = os.pidfd_open(process.pid)
        self.group = process.pid

    def close(self):
        if self.descriptor is not None:
            try:
                deadline = time.monotonic() + 5
                try:
                    signal.pidfd_send_signal(self.descriptor, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # Still wait for descendants if the supervisor exited first.
                # Wait for the supervisor to kill its group before callers reap it.
                # Killing the supervisor first could strand QEMU or model runners.
                poll = select.poll()
                poll.register(self.descriptor, select.POLLIN)
                if not poll.poll(5000):
                    raise TimeoutError('The managed Linux process did not stop')
                # SIGKILL delivery to a group is asynchronous. The supervisor's
                # pidfd can become readable before its children release sockets.
                while group_running(self.group):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('The managed Linux process group did not stop')
                    time.sleep(.01)
            finally:
                os.close(self.descriptor)
                self.descriptor = None


def supervise():
    parent, token, profile, binary, *arguments = sys.argv[1:]
    parent = int(parent)
    if profile not in ('vm', 'engine') or os.getpgrp() != os.getpid():
        raise ValueError('Managed Linux programs require their own process group')
    import ctypes
    import resource
    # Prevent privilege acquisition through executed programs.
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        raise OSError('Could not enable Linux no-new-privileges protection')
    if profile == 'vm':
        resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (7200, 7200))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))

    def stop(*_):
        os.killpg(os.getpgrp(), signal.SIGKILL)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    child = None
    try:
        if start_time(parent) != token:
            return 1
        child = subprocess.Popen([binary, *arguments], close_fds=True)
        while child.poll() is None:
            try:
                if start_time(parent) != token:
                    stop()
            except (OSError, IndexError):
                stop()
            time.sleep(.2)
        return child.returncode
    finally:
        # Include runner descendants even when the main program has exited.
        if child is not None:
            stop()


if __name__ == '__main__':
    sys.exit(supervise())
