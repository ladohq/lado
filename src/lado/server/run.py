"""The one UI server of a LADO_HOME as a process: `lado server` in the foreground, started in
the background by `lado ui`, stopped by `lado server stop`.

The server holds an exclusive lock on LADO_HOME/server.lock while it runs and writes
LADO_HOME/server.json (url, host, port, pid, version) for the commands that look for it: `url`
reaches it from this machine, `host` is the address it listens on. The file
counts only while the lock is held: with the lock free it was left by a server that died,
and it is removed (its pid may belong to another process by now). A server started in the
background writes its output and request errors to LADO_HOME/server.log.
"""

import contextlib
import errno
import fcntl
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import IO

import lado
from lado import providers, state, terminal
from lado.runtime import LadoError

DEFAULT_PORT = 8000
LAST_PORT = 8020  # the last port tried when the ones before it are busy
LOCK_WAIT = 0.1  # seconds a starting server tries to take the lock: `running()` holds it briefly
READY_TIMEOUT = 15.0  # seconds `lado ui` waits for a server it started
STOP_TIMEOUT = 10.0  # seconds `lado server stop` waits for the server to end
# Seconds a stopping server waits for open requests; its event streams end at once (app.Server).
SHUTDOWN_GRACE = 1


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
    lock = take_lock()
    if lock is not None:
        with lock:  # removed while held: a server starting now cannot have written it yet
            info_path().unlink(missing_ok=True)
        return None
    try:
        info = json.loads(info_path().read_text())
    except (OSError, ValueError):
        return None
    return {"host": "127.0.0.1", **info}  # a LADO before `--host` wrote none


@dataclass(frozen=True)
class Listening:
    """Where a server listening on an address is reached: `url` from this machine (what
    server.json keeps), `remote` from others with the `warning` that says so, or None
    for a loopback address."""

    url: str
    remote: str | None
    warning: str | None

    @classmethod
    def of(cls, host: str, port: int) -> "Listening":
        """For the address the socket took (`getsockname`), not the name it was given."""
        ip = ipaddress.ip_address(host)
        if ip.is_loopback:
            return cls(f"http://{host}:{port}", None, None)
        warning = (
            f"the LADO server listens on {host}:{port}, open to other machines: whoever "
            "reaches it with the token can run commands as you, and the token travels "
            "unencrypted (plain HTTP). Use it only on a network you trust."
        )
        if ip.is_unspecified:
            return cls(f"http://127.0.0.1:{port}", f"http://{socket.gethostname()}:{port}", warning)
        return cls(f"http://{host}:{port}", f"http://{host}:{port}", warning)


def _ipv4(host: str) -> None:
    if ":" in host:
        raise LadoError(f"cannot listen on {host}: IPv6 is not supported yet")


def address(host: str) -> str:
    """The IPv4 address the server listens on for `host` (an address or a name), as
    server.json keeps it: `localhost` is 127.0.0.1."""
    _ipv4(host)
    try:
        return socket.gethostbyname(host)
    except OSError as error:
        raise LadoError(f"cannot listen on {host}: {error.strerror or error}") from error


def _bound(host: str, port: int) -> socket.socket | None:
    """A socket bound to the address; None when the port is busy there. LadoError when
    the server cannot listen there at all (no such address on this machine, no such name,
    a port it may not take)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError as error:
        sock.close()
        if isinstance(error, socket.gaierror) or error.errno != errno.EADDRINUSE:
            raise LadoError(f"cannot listen on {host}:{port}: {error.strerror or error}") from error
        return None
    return sock


def _busy_locally(port: int) -> bool:
    """Whether another process listens on 127.0.0.1:`port`."""
    try:
        probe = _bound("127.0.0.1", port)
    except LadoError:
        return False  # not busy: the bind on 0.0.0.0 says why it cannot listen
    if probe is None:
        return True
    probe.close()
    return False


def bind(
    host: str, port: int | None, first: int = DEFAULT_PORT, last: int = LAST_PORT
) -> socket.socket:
    """A listening socket: on `port` exactly (0: any free one), or with None on the first
    free port from `first` to `last`. Only a busy port moves on to the next one."""
    _ipv4(host)
    for candidate in [port] if port is not None else range(first, last + 1):
        # Every address is reached locally on 127.0.0.1, and macOS lets 0.0.0.0 take a port
        # another process holds there: that one would answer the local link.
        if candidate and host == "0.0.0.0" and _busy_locally(candidate):
            continue
        sock = _bound(host, candidate)
        if sock is None:
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

    lock = take_lock(LOCK_WAIT)
    if lock is None:
        info = running()
        where = f" at {info['url']}" if info else ""
        raise LadoError(f"a LADO server already runs{where}; stop it with `lado server stop`")
    with lock:
        token = auth.token(new=new_token)
        sock = bind(host, port)
        listens, bound = sock.getsockname()
        listening = Listening.of(listens, bound)
        if listening.warning:
            print(f"lado: warning: {listening.warning}", file=sys.stderr, flush=True)
        if app.bundle_missing(app.STATIC):
            print(
                f"lado: warning: the web UI's bundle is missing: {app.BUILD_HINT}", file=sys.stderr
            )
        # No access log: it would write the login link, token included, to server.log.
        config = uvicorn.Config(
            app.create_app(token, bound, host=listens),
            log_level="info",
            access_log=False,
            timeout_graceful_shutdown=SHUTDOWN_GRACE,
        )
        server = app.Server(config)
        url = listening.url
        info = {
            "url": url,
            "host": listens,
            "port": bound,
            "pid": os.getpid(),
            "version": lado.__version__,
        }
        written = info_path().with_suffix(".tmp")
        written.write_text(json.dumps(info))
        written.replace(info_path())
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{stamp} LADO server {lado.__version__} at {url}, listening on {listens}:{bound}, "
            f"pid {os.getpid()}",
            flush=True,
        )
        # Terminals a server of this LADO_HOME left open when it died: nobody reads them.
        left = terminal.close_viewers()
        if left:
            print(f"Closed {len(left)} terminal viewers left over: {', '.join(left)}", flush=True)
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


@dataclass
class Started:
    """A server `lado ui` started: its process and where its lines in server.log begin."""

    process: subprocess.Popen
    log_from: int


def start_background(host: str | None, port: int | None) -> Started:
    """Start `lado server` as a process of its own that outlives the command starting it,
    its output going to server.log (the owner's only, like the token)."""
    args = ["server"] + ([] if host is None else ["--host", host])
    args += [] if port is None else ["--port", str(port)]
    fd = os.open(log_path(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.fchmod(fd, 0o600)  # also a log an older LADO made
    with os.fdopen(fd, "a") as log:
        log_from = log.tell()
        process = subprocess.Popen(
            providers.lado_command(*args),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            start_new_session=True,  # not ended with the terminal that started it
        )
    return Started(process, log_from)


def health(url: str, timeout: float = 1) -> dict | None:
    """What the server at `url` answers on /api/health; None when it does not."""
    with contextlib.suppress(OSError, ValueError):
        with urllib.request.urlopen(f"{url}/api/health", timeout=timeout) as answer:
            said = json.load(answer)
            return said if isinstance(said, dict) else None
    return None


def _healthy(url: str) -> bool:
    said = health(url)
    return bool(said and said.get("ok") is True)


def wait_ready(started: Started | None = None, timeout: float | None = None) -> dict:
    """The server's server.json once it answers; LadoError naming server.log after
    `timeout` seconds, or at once when the server `started` ends before."""
    timeout = READY_TIMEOUT if timeout is None else timeout
    deadline = time.monotonic() + timeout
    while True:
        info = running()
        if info and _healthy(info["url"]):
            return info
        code = started.process.poll() if started else None
        if code is not None:
            with open(log_path()) as log:
                log.seek(started.log_from)
                lines = log.read().strip().splitlines()
            said = f": {lines[-1]}" if lines else ""
            raise LadoError(
                f"the LADO server ended as it started, exit code {code}{said}; see {log_path()}"
            )
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
