"""Explicit Linux process execution. These lifecycle controls are not isolation."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from .execution import ExecutionPolicy
from .isolation import WorkerTransport


class NativeWorker(WorkerTransport):
    def __init__(self, root, execution):
        # Revalidate before starting any process; never infer consent from settings.
        ExecutionPolicy(execution.mode, execution.acknowledge_host_access)
        if execution.mode != 'native':
            raise ValueError('Native worker requires explicit native execution')
        super().__init__()
        self.temporary = None
        root = Path(root).resolve()
        directory = root / '.data/native-runs'
        directory.mkdir(parents=True, exist_ok=True)
        try:
            self.temporary = tempfile.TemporaryDirectory(prefix='run-', dir=directory)
            self.workspace = Path(self.temporary.name)
            # This avoids deliberately passing keys. Same-account access remains possible.
            environment = {key: value for key, value in os.environ.items()
                           if key in ('PATH', 'LANG', 'LC_ALL', 'TZ')}
            self.process = subprocess.Popen(
                [sys.executable, '-I', '-u', str(root / 'guest/worker.py'),
                 '--native-root', str(self.workspace), '--acknowledge-host-access',
                 '--controller-pid', str(os.getpid())],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=self.workspace, env=environment, start_new_session=True, close_fds=True)
            self.start_readers()
        except Exception:
            self.close()
            raise

    def kill(self):
        # Ordinary commands create their own process groups. Find live descendants
        # before terminating the worker, so Stop also reaches those groups.
        # Reparented/deliberately detached processes still require external controls.
        if self.process.poll() is None:
            try:
                os.kill(self.process.pid, signal.SIGSTOP)
            except ProcessLookupError:
                pass
            descendants = {self.process.pid}
            processes = {}
            for path in Path('/proc').glob('[0-9]*/stat'):
                try:
                    fields = path.read_text().rsplit(')', 1)[1].split()
                    processes[int(path.parent.name)] = (int(fields[1]), fields[19])
                except (OSError, ValueError, IndexError):
                    continue
            while True:
                children = {pid for pid, (parent, _) in processes.items() if parent in descendants}
                if children <= descendants:
                    break
                descendants.update(children)
            for pid in descendants - {self.process.pid}:
                try:
                    # Check start time to avoid signaling a reused process ID.
                    current = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
                    if current[19] == processes[pid][1]:
                        os.kill(pid, signal.SIGKILL)
                except (OSError, IndexError):
                    pass
        # Kill the ordinary process group even if its leader already exited.
        # Code may escape this group; external isolation must handle that case.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if self.process.poll() is None:
            self.process.kill()

    def cleanup(self):
        if self.temporary:
            self.temporary.cleanup()
            self.temporary = None
