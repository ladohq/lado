"""The processes a test or a test run leaves alive: found by a mark in their environment,
waited for, killed and named.

Every process a test starts carries the test's `LADO_HOME` in its environment (the tmux
server, the agents, their hooks and `lado mcp`, the session loop, `lado server`, a real CLI
and its children), and every process a pytest process starts carries that pytest process's
pid as `LADO_TEST_PID` (tests/conftest.py). Parent-child trees miss orphans and the session
loop (a session of its own), process groups miss the daemonised tmux server; the
environment is the one mark all of them keep.

- `sweep(home)`: after a test's tmux server is killed, the `isolated` fixtures wait up to
  `WAIT` for the test's processes to end, kill the rest and `fail_if` they were any.
- `reap_dead_runs()`: at a run's start, kills what a run killed from outside left (its
  `LADO_TEST_PID` names a pid no longer alive) and removes the dead `lado-test-*` sockets.
- `own_left()`: at a pytest process's end, what still carries its own `LADO_TEST_PID`.

A process's environment is read from `/proc` on Linux and from `ps -E` on macOS (the
environment it started with, which is what its parent gave it); standard library only.
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

# How long a test's or a run's processes have to end by themselves, and a session loop to
# see that its tmux session is gone, before they count as left: about forty loop intervals
# of the integration tests, longer than any pass takes on a loaded CI runner.
WAIT = 10.0

POLL = 0.1


@dataclass(frozen=True)
class Process:
    pid: int
    command: str
    # Linux: the NAME=value entries joined by NULs. macOS: `ps -E`'s line, the command
    # then the environment, joined by spaces.
    environ: str
    sep: str

    def has(self, name: str, value: str) -> bool:
        sep = re.escape(self.sep)
        entry = re.escape(f"{name}={value}")
        return re.search(f"(?:^|{sep}){entry}(?:{sep}|$)", self.environ) is not None

    def get(self, name: str) -> str | None:
        sep = re.escape(self.sep)
        found = re.findall(f"(?:^|{sep}){re.escape(name)}=([^{sep}]*)", self.environ)
        return found[-1] if found else None  # macOS: the environment comes after the command


def from_proc(root: Path) -> list[Process]:
    """The user's processes in a `/proc` folder; one that ended meanwhile, is not readable,
    or has no environment (a zombie) is skipped."""
    found = []
    for folder in root.iterdir():
        if not folder.name.isdigit():
            continue
        try:
            if folder.stat().st_uid != os.getuid():
                continue
            environ = (folder / "environ").read_bytes()
            cmdline = (folder / "cmdline").read_bytes()
        except OSError:
            continue
        if not environ:
            continue
        found.append(
            Process(
                int(folder.name),
                cmdline.rstrip(b"\0").replace(b"\0", b" ").decode(errors="replace"),
                environ.rstrip(b"\0").decode(errors="replace"),
                "\0",
            )
        )
    return sorted(found, key=lambda p: p.pid)


def from_ps(with_environ: str, commands: str) -> list[Process]:
    """The processes of `ps -E -o pid=,command=` (each line's environment after its
    command), named by their command in `ps -o pid=,command=`."""
    names = dict(_ps_lines(commands))
    return [Process(pid, names.get(pid, line), line, " ") for pid, line in _ps_lines(with_environ)]


def _ps_lines(text: str) -> list[tuple[int, str]]:
    lines = []
    for line in text.splitlines():
        pid, _, rest = line.strip().partition(" ")
        if pid.isdigit():
            lines.append((int(pid), rest.strip()))
    return lines


def processes() -> list[Process]:
    """The user's processes with their command and environment."""
    if sys.platform.startswith("linux"):
        return from_proc(Path("/proc"))
    if sys.platform == "darwin":
        user = ["-U", str(os.getuid())]
        ps = ["ps", "-ww", *user, "-o", "pid=,command="]
        return from_ps(_run([ps[0], "-E", *ps[1:]]), _run(ps))
    raise RuntimeError(f"tests/leftovers.py cannot read processes' environment on {sys.platform}")


def _run(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


def marked(name: str, value: str) -> list[Process]:
    """The processes whose environment has `name=value`, the caller left out."""
    me = os.getpid()
    return [p for p in processes() if p.pid != me and p.has(name, value)]


def sweep(home: Path | str, wait: float = WAIT) -> list[Process]:
    """Wait up to `wait` seconds for the processes with `LADO_HOME=home` to end; kill the
    rest and return them. Returns as soon as none is left."""
    return _end("LADO_HOME", str(home), wait)


def own_left(wait: float = WAIT) -> list[Process]:
    """The processes with this pytest process's own `LADO_TEST_PID` still alive after
    `wait` seconds, killed."""
    return _end("LADO_TEST_PID", str(os.getpid()), wait)


def _end(name: str, value: str, wait: float) -> list[Process]:
    deadline = time.monotonic() + wait
    while (left := marked(name, value)) and time.monotonic() < deadline:
        time.sleep(POLL)
    _kill(left)
    return left


def fail_if(left: list[Process], after: str) -> None:
    """Fail the test when `left` names any process."""
    if left:
        pytest.fail(f"processes left after {after}, killed:\n{describe(left)}", pytrace=False)


def describe(left: list[Process]) -> str:
    return "\n".join(f"  {p.pid} {p.command}" for p in left)


def reap_dead_runs() -> list[Process]:
    """Kill the processes whose `LADO_TEST_PID` names a pid no longer alive (a run killed
    from outside, a crashed xdist worker) and remove the `lado-test-*` tmux sockets no server
    answers on; the killed processes. A living run's processes are never touched; a pid
    reused by another process makes a dead run look alive, and its leftovers wait for a
    later run."""
    dead = [p for p in processes() if p.pid != os.getpid() and _dead_owner(p.get("LADO_TEST_PID"))]
    _kill(dead)
    if shutil.which("tmux"):
        folder = Path(os.environ.get("TMUX_TMPDIR") or "/tmp", f"tmux-{os.getuid()}")
        for socket in sorted(folder.glob("lado-test-*")) if folder.is_dir() else []:
            answer = subprocess.run(
                ["tmux", "-L", socket.name, "list-sessions"], capture_output=True, text=True
            )
            if answer.returncode and (
                "no server" in answer.stderr or "error connecting" in answer.stderr
            ):
                socket.unlink(missing_ok=True)
    return dead


def _dead_owner(mark: str | None) -> bool:
    return bool(mark) and mark.isdigit() and not _alive(int(mark))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def _kill(left: list[Process]) -> None:
    """SIGKILL each and wait (up to a few seconds) until it is gone; a child of the caller
    is reaped, so it is not left a zombie."""
    for process in left:
        try:
            os.kill(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    pids = {p.pid for p in left}
    while pids and time.monotonic() < deadline:
        for pid in list(pids):
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
        pids &= {p.pid for p in processes()}
        if pids:
            time.sleep(POLL)
