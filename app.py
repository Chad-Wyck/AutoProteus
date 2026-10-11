"""Launch AutoProteus with Python 3.10+; there are no pip dependencies."""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from autoproteus.server import Application, make_server
from autoproteus.storage import atomic_json


def existing_instance(path, identity, no_browser):
    if path.exists():
        try:
            connection = json.loads(path.read_text())
            with urllib.request.urlopen(connection["url"] + "/health", timeout=1) as response:
                health = json.load(response)
            if health.get("identity") == identity:
                if not no_browser:
                    webbrowser.open(connection["url"])
                return True
        except (OSError, ValueError, KeyError):
            pass
    return False


def acquire_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / "app.lock").open("a+b")
    if stream.tell() == 0:
        stream.write(b"0"); stream.flush()
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        return None
    return stream


def main():
    parser = argparse.ArgumentParser(description="AutoProteus Seed")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=47831)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    identity = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    connection_file = root / ".data" / "server.json"
    if existing_instance(connection_file, identity, args.no_browser):
        return 0
    lock = acquire_lock(root / ".data")
    if lock is None:
        for _ in range(20):
            if existing_instance(connection_file, identity, args.no_browser):
                return 0
            time.sleep(0.5)
        raise RuntimeError("AutoProteus is already starting. Wait a moment and open it again.")
    # Opening another window must not reload or interrupt active session state.
    app = Application(root)
    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = make_server(app, port)
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("No local port is available. Close another AutoProteus window and try again.")
    url = f"http://127.0.0.1:{server.server_port}"
    atomic_json(connection_file, {"url": url, "identity": app.identity})
    print(f"AutoProteus is ready at {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        server.server_close()
        connection_file.unlink(missing_ok=True)
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
