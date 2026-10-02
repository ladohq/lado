"""The one UI server of a LADO_HOME as a process: `lado server` in the foreground, started in
the background by `lado ui`, stopped by `lado server stop`.

The server holds an exclusive lock on LADO_HOME/server.lock while it runs and writes
LADO_HOME/server.json (url, port, pid, version) for the commands that look for it. The file
counts only while the lock is held: with the lock free it was left by a server that died,
and it is removed (its pid may belong to another process by now). A server started in the
background writes its output and request errors to LADO_HOME/server.log.
"""

import contextlib
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from typing import IO

from lado import __version__, providers, state
from lado.runtime import LadoError

HOSTS = ("127.0.0.1", "localhost")  # a remote host waits for a real login
DEFAULT_PORT = 8000
LAST_PORT = 8020  # the last port tried when the ones before it are busy
LOCK_WAIT = 0.1  # seconds a starting server tries to take the lock: `running()` holds it briefly
READY_TIMEOUT = 15.0  # seconds `lado ui` waits for a server it started
STOP_TIMEOUT = 10.0  # seconds `lado server stop` waits for the server to end


def lock_path():
    return state.home() / "server.lock"


def info_path():
    return state.home() / "server.json"


def log_path():
    return state.home() / "server.log"


def take_lock(wait: float = 0) -> IO | None:
    """The server lock, held until the returned file is closed or the process ends; None
    when another process holds it for longer than `wait` seconds."""
    deadline = time.monotonic() + wait
    lock = open(lock_path(), "a")
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock
        except OSError:
            if time.monotonic() >= deadline:
                lock.close()
                return None
            time.sleep(wait / 10)


def _held() -> bool:
    lock = take_lock()
    if lock is None:
        return True
    lock.close()
    return False


def running() -> dict | None:
    """The running server's server.json; None when no server runs (a file left by a dead
    one is removed) or it has not written the file yet."""
    if not _held():
        info_path().unlink(missing_ok=True)
        return None
    try:
        return json.loads(info_path().read_text())
    except (OSError, ValueError):
        return None


def check_host(host: str) -> None:
    if host not in HOSTS:
        raise LadoError(
            f"lado server listens only on 127.0.0.1 or localhost for now, not {host}: "
            "a remote host needs a login LADO does not have yet"
        )


def bind(
    host: str, port: int | None, first: int = DEFAULT_PORT, last: int = LAST_PORT
) -> socket.socket:
    """A listening socket: on `port` exactly (0: any free one), or with None on the first
    free port from `first` to `last`."""
    for candidate in [port] if port is not None else range(first, last + 1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, candidate))
        except OSError:
            sock.close()
            continue
        sock.listen(128)
        return sock
    if port is not None:
        raise LadoError(f"port {port} is busy; leave out --port to take a free one")
    raise LadoError(f"no free port from {first} to {last}; name one with --port")


def serve(host: str, port: int | None, new_token: bool) -> int:
    """`lado server`: serve until stopped (Ctrl-C, SIGTERM from `lado server stop`)."""
    import uvicorn

    from lado.server import app, auth

    check_host(host)
    lock = take_lock(LOCK_WAIT)
    if lock is None:
        info = running()
        where = f" at {info['url']}" if info else ""
        raise LadoError(f"a LADO server already runs{where}; stop it with `lado server stop`")
    with lock:
        token = auth.token(new=new_token)
        sock = bind(host, port)
        bound = sock.getsockname()[1]
        url = f"http://127.0.0.1:{bound}"
        if app.bundle_missing(app.STATIC):
            print(
                f"lado: warning: the web UI's bundle is missing: {app.BUILD_HINT}", file=sys.stderr
            )
        server = uvicorn.Server(uvicorn.Config(app.create_app(token, bound), log_level="info"))
        info = {"url": url, "port": bound, "pid": os.getpid(), "version": __version__}
        written = info_path().with_suffix(".tmp")
        written.write_text(json.dumps(info))
        written.replace(info_path())
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{stamp} LADO server {__version__} at {url}, pid {os.getpid()}", flush=True)
        print(f"Open the UI with: lado ui (token in {auth.token_path()})", flush=True)
        # uvicorn shuts down on SIGTERM or SIGINT, then raises the signal again: end with 0
        # through the `finally` below instead of being killed by it.
        signal.signal(signal.SIGTERM, _exit)
        try:
            server.run(sockets=[sock])
        except KeyboardInterrupt:
            pass
        finally:
            info_path().unlink(missing_ok=True)
    return 0


def _exit(signum, frame) -> None:
    raise SystemExit(0)


def start_background(port: int | None) -> None:
    """Start `lado server` as a process of its own that outlives the command starting it,
    its output going to server.log."""
    args = ["server"] + ([] if port is None else ["--port", str(port)])
    with open(log_path(), "a") as log:
        subprocess.Popen(
            providers.lado_command(*args),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            start_new_session=True,  # not ended with the terminal that started it
        )


def _healthy(url: str) -> bool:
    with contextlib.suppress(OSError, ValueError):
        with urllib.request.urlopen(f"{url}/api/health", timeout=1) as answer:
            return json.load(answer).get("ok") is True
    return False


def wait_ready(timeout: float | None = None) -> dict:
    """The server's server.json once it answers; LadoError naming server.log after
    `timeout` seconds."""
    timeout = READY_TIMEOUT if timeout is None else timeout
    deadline = time.monotonic() + timeout
    while True:
        info = running()
        if info and _healthy(info["url"]):
            return info
        if time.monotonic() > deadline:
            raise LadoError(f"the LADO server did not come up in {timeout:g}s; see {log_path()}")
        time.sleep(0.1)


def stop() -> dict | None:
    """Stop the running server; its server.json, or None when none runs."""
    info = running()
    if info is None:
        return None
    os.kill(info["pid"], signal.SIGTERM)
    deadline = time.monotonic() + STOP_TIMEOUT
    while _held():
        if time.monotonic() > deadline:
            raise LadoError(f"the LADO server (pid {info['pid']}) did not end in {STOP_TIMEOUT:g}s")
        time.sleep(0.05)
    return info
