"""Command lifecycle and bounded output for the workspace terminal."""
import os
import subprocess
import time


def run_command(workspace, command):
    from .tools import Cancelled, clipped
    if not isinstance(command, str) or not command.strip() or len(command) > 20000:
        raise ValueError("Provide a nonempty command of at most 20,000 characters")
    argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command] if os.name == "nt" else ["/bin/sh", "-c", command]
    if os.name == "nt":
        argv[-1] = "$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); " + command
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    # Spool output to disk to avoid retaining unlimited subprocess output in RAM.
    output_path = workspace.root / ".terminal-output"
    with output_path.open("wb") as stream:
        process = subprocess.Popen(argv, cwd=workspace.root, stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, **kwargs)
        started = time.monotonic()
        timed_out = False
        output_limited = False
        try:
            while process.poll() is None:
                if workspace.cancel.is_set() or time.monotonic() - started > workspace.timeout or output_path.stat().st_size > 32000000:
                    timed_out = not workspace.cancel.is_set()
                    output_limited = output_path.stat().st_size > 32000000
                    if output_limited:
                        timed_out = False
                    workspace._terminate(process)
                    break
                time.sleep(0.1)
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                workspace._terminate(process)
    with output_path.open("rb") as stream:
        output = stream.read(48000).decode("utf-8", errors="replace")
    if workspace.cancel.is_set():
        raise Cancelled()
    return {"exit_code": process.returncode, "output": clipped(output), "timed_out": timed_out, "output_limited": output_limited}



def terminate(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)
