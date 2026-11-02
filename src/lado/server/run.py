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
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import IO

import lado
from lado import logins, providers, state, telemetry, terminal
from lado.runtime import LadoError

DEFAULT_PORT = 8000
LAST_PORT = 8020  # the last port tried when the ones before it are busy
LOCK_WAIT = 0.1  # seconds a starting server tries to take the lock: `running()` holds it briefly
READY_TIMEOUT = 15.0  # seconds `lado ui` waits for a server it started
STOP_TIMEOUT = 10.0  # seconds `lado server stop` waits for the server to end
# Seconds a stopping server waits for open requests; its event streams end at once (app.Server).
SHUTDOWN_GRACE = 1
CONTAINER_NOTE = (
    "the LADO server runs in a container and listens on {host}:{port} inside it; who "
    "reaches it depends on how the container publishes the port "
    "(127.0.0.1:{port}:{port}: this computer only). Published to other machines, the "
    "token travels unencrypted (plain HTTP)."
)
# A host name or an IPv4 address: letters, digits, `.` and `-`, at most 253 characters,
# neither first nor last a `.` or `-`.
PUBLIC_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
PROBE = ("192.0.2.1", 9)  # TEST-NET-1: a UDP connect picks the route and sends nothing


def lock_path():
    return state.home() / "server.lock"


def info_path():
    return state.home() / "server.json"


def log_path():
    return state.home() / "server.log"


def bound_log() -> None:
    """Keep server.log within its bound while a server writes it: its output was opened
    with O_APPEND, so after a copy and truncation its next line lands at the new end."""
    telemetry.trim(log_path())


def resume_sessions(application) -> threading.Thread | None:
    """In a container: resume its sessions in the background while the server serves
    (runtime.resume_at_start), each line on stderr (docker logs), until the server stops
    (`application.state.stopping`). The thread; None outside a container."""
    from lado import runtime, update

    if not update.in_container():
        return None

    def say(line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    def resume() -> None:
        try:
            runtime.resume_at_start(say, application.state.stopping)
        except Exception as error:  # one resume's failure is its own line; this is the rest
            telemetry.record("server:resume", error)
            say(f"lado: could not resume the sessions: {type(error).__name__}: {error}")

    thread = threading.Thread(target=resume, daemon=True)
    thread.start()
    return thread


def housekeeping(stop: threading.Event) -> None:
    """A running server's chores, at its start and every telemetry.KICK_EVERY until `stop`:
    server.log's bound, and the statistics sender when something is due."""
    while True:
        bound_log()
        telemetry.kick()
        if stop.wait(telemetry.KICK_EVERY):
            return


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


def network_address() -> str | None:
    """This machine's IPv4 address in its network: the source address of its route to the
    outside, found anew at each call; None without one (no network)."""
    with contextlib.suppress(OSError, ValueError):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(PROBE)
            found = probe.getsockname()[0]
        ip = ipaddress.ip_address(found)
        if not (ip.is_loopback or ip.is_unspecified):
            return found
    return None


def public_host(env: Mapping[str, str]) -> tuple[str | None, str | None]:
    """LADO_PUBLIC_HOST when it is a host name or address, else None; with the warning for
    a value that is not one (empty is unset, with no warning)."""
    value = env.get("LADO_PUBLIC_HOST", "")
    if not value:
        return None, None
    if PUBLIC_HOST.fullmatch(value):
        return value, None
    return None, (
        f"LADO_PUBLIC_HOST is not a host name or address: {value}; "
        "the link for other devices does not use it"
    )


def _open_warning(where: str) -> str:
    return (
        f"the LADO server listens on {where}, open to other machines: whoever "
        "reaches it with the token can run commands as you, and the token travels "
        "unencrypted (plain HTTP). Use it only on a network you trust."
    )


@dataclass(frozen=True)
class Listening:
    """Where a server listening on an address is reached: `url` from this machine (what
    server.json keeps), `remote` from other devices (the base of the link for another
    device), or None with its `reason` (`loopback`, `no-address`, `unknown`).

    One rule (share-access): outside a container the address decides, with the `warning`
    of a server open to other machines; in a container (`container`, the caller's
    `update.in_container()`) only the port's publication does, which the container knows
    from `LADO_LISTEN` (`listen`) and nothing else: unknown, it prints the `note`.
    `LADO_PUBLIC_HOST` names the host for `remote`; a value that is not a host is one of
    the `problems`, for the start's warning lines."""

    url: str
    remote: str | None
    warning: str | None
    note: str | None = None
    reason: str | None = None
    problems: tuple[str, ...] = ()
    listen: str | None = None

    @classmethod
    def of(
        cls, host: str, port: int, container: bool = False, env: Mapping[str, str] | None = None
    ) -> "Listening":
        """For the address the socket took (`getsockname`), not the name it was given, and
        the server's environment (`os.environ` by default)."""
        env = os.environ if env is None else env
        named, problem = public_host(env)
        problems = (problem,) if problem else ()
        ip = ipaddress.ip_address(host)
        if ip.is_loopback:
            return cls(f"http://{host}:{port}", None, None, reason="loopback", problems=problems)
        local = f"http://127.0.0.1:{port}" if ip.is_unspecified else f"http://{host}:{port}"
        if container:
            return cls._in_container(
                local, host, port, env.get("LADO_LISTEN") or None, named, problems
            )
        if named is not None:
            address = named
        elif ip.is_unspecified:
            address = network_address() or socket.gethostname()
        else:
            address = host
        return cls(
            local, f"http://{address}:{port}", _open_warning(f"{host}:{port}"), problems=problems
        )

    @classmethod
    def _in_container(
        cls,
        local: str,
        host: str,
        port: int,
        listen: str | None,
        named: str | None,
        problems: tuple[str, ...],
    ) -> "Listening":
        remote = f"http://{named}:{port}" if named else None
        try:
            published = ipaddress.IPv4Address(listen or "")
        except ValueError:  # unset, a name or IPv6: compose refuses a name at `up`
            note = CONTAINER_NOTE.format(host=host, port=port)
            reason = None if remote else "unknown"
            return cls(local, remote, None, note, reason, problems, listen)
        if published.is_loopback:
            return cls(local, None, None, None, "loopback", problems, listen)
        if remote is None and not published.is_unspecified:
            remote = f"http://{listen}:{port}"
        reason = None if remote else "no-address"
        return cls(local, remote, _open_warning(f"{listen}:{port}"), None, reason, problems, listen)


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

    from lado import update
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
        listening = Listening.of(listens, bound, update.in_container())
        for problem in listening.problems:
            print(f"lado: warning: {problem}", file=sys.stderr, flush=True)
        if listening.warning:
            print(f"lado: warning: {listening.warning}", file=sys.stderr, flush=True)
        if listening.note:
            print(f"lado: note: {listening.note}", file=sys.stderr, flush=True)
        if app.bundle_missing(app.STATIC):
            print(
                f"lado: warning: the web UI's bundle is missing: {app.BUILD_HINT}", file=sys.stderr
            )
        # No access log: it would write the login link, token included, to server.log.
        application = app.create_app(token, bound, host=listens)
        config = uvicorn.Config(
            application,
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
        # And its login windows (lado.logins): only the UI gets to them.
        left = logins.end_windows()
        if left:
            print(f"Closed {len(left)} login windows left over: {', '.join(left)}", flush=True)
        print(f"Open the UI with: lado ui (token in {auth.token_path()})", flush=True)
        # uvicorn shuts down on SIGTERM or SIGINT, then raises the signal again: end with 0
        # through the `finally` below instead of being killed by it.
        signal.signal(signal.SIGTERM, _exit)
        stop = threading.Event()
        threading.Thread(target=housekeeping, args=(stop,), daemon=True).start()
        # The socket listens already: /api/health answers while the sessions come back.
        resume_sessions(application)
        try:
            server.run(sockets=[sock])
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            info_path().unlink(missing_ok=True)
            with contextlib.suppress(Exception):  # tmux gone or failing: nothing to end
                logins.end_windows()
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
    telemetry.rotate(log_path())  # bounded: the server bounds it while it runs (bound_log)
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


def _answer(ask: str | urllib.request.Request, timeout: float) -> dict | None:
    """The JSON object a server answers; None for no answer, an error or another value."""
    with contextlib.suppress(OSError, ValueError):
        with urllib.request.urlopen(ask, timeout=timeout) as answer:
            said = json.load(answer)
            return said if isinstance(said, dict) else None
    return None


def health(url: str, timeout: float = 1) -> dict | None:
    """What the server at `url` answers on /api/health; None when it does not."""
    return _answer(f"{url}/api/health", timeout)


def access(url: str, token: str, timeout: float = 2) -> dict | None:
    """What the server at `url` answers on /api/access with the token: the link for another
    device by the server's environment; None when it does not answer it (an older server,
    an error)."""
    headers = {"Authorization": f"Bearer {token}"}
    return _answer(urllib.request.Request(f"{url}/api/access", headers=headers), timeout)


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


def _gone(pid: int) -> bool:
    """Whether the process `pid` has ended: reaped when it is this process's child, else
    no longer there (a pid we may not signal is no longer our server's)."""
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == pid
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return True
    return False


def stop() -> dict | None:
    """Stop the running server and wait until its process has ended (it frees its lock a
    moment before); its server.json, or None when none runs."""
    info = running()
    if info is None:
        return None
    os.kill(info["pid"], signal.SIGTERM)
    deadline = time.monotonic() + STOP_TIMEOUT
    while _held() or not _gone(info["pid"]):
        if time.monotonic() > deadline:
            raise LadoError(f"the LADO server (pid {info['pid']}) did not end in {STOP_TIMEOUT:g}s")
        time.sleep(0.05)
    return info
