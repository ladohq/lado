"""A container test run's hold on its prefix, and what it does about other runs' leftovers.

The run's objects live in Docker, so a run that ends at once (SIGKILL, a second Ctrl-C in
the teardown) leaves them behind. While it lives a run holds an flock of `<prefix>lock` in
RUNS, a folder of the user's outside every checkout and `$TMPDIR` (LADO gives each agent
its own), so every worktree's run sees every other's; the kernel frees it when the process
ends in any way.

- `RunLock(prefix)`: the run's own lock, taken before its first object; `free()` at its end.
- `reap(docker, own)`: at a run's start, removes the containers, volumes, networks and image
  tags of each prefix whose lock is free, containers first (Docker removes no volume or
  network in use), then its lock file; a held lock's are not touched. One `UserWarning`
  names the objects of a prefix with no lock file (a run before the lock, or of another
  machine on the same Docker), never removed, and each removal that failed, with one
  command that removes them all.
- `left(docker, own)`: what Docker still holds of the run's own prefix, by kind.
- `trap_signals()`: SIGTERM and SIGHUP raise KeyboardInterrupt, so pytest ends the run as
  on Ctrl-C and the finalizers remove each test's objects; `restore_signals` undoes it.

Standard library only; `docker` is container_helpers.docker, or a recorder in the unit
tests (tests/test_container_runs.py).
"""

from __future__ import annotations

import fcntl
import os
import re
import signal
import warnings
from pathlib import Path

RUNS = Path(os.environ.get("LADO_CONTAINER_RUNS") or f"/tmp/lado-container-runs-{os.getuid()}")
# A run's prefix (container_helpers.PREFIX) anywhere in a name: compose's `lado-<folder>`
# projects of install.sh carry it after `lado-`, their networks before `_default`.
PREFIX_IN_NAME = re.compile(r"lado-test-[0-9a-f]{6}-")
# Each kind: the command that lists its `lado-test-*` names, the one that removes one name,
# in the order of removal.
KINDS = {
    "containers": (
        ["ps", "-a", "--format", "{{.Names}}", "--filter", "name=lado-test-"],
        ["rm", "-f"],
    ),
    "volumes": (
        ["volume", "ls", "--format", "{{.Name}}", "--filter", "name=lado-test-"],
        ["volume", "rm", "-f"],
    ),
    "networks": (
        ["network", "ls", "--format", "{{.Name}}", "--filter", "name=lado-test-"],
        ["network", "rm"],
    ),
    "tags": (
        [
            "image",
            "ls",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            "--filter",
            "reference=lado-test-*",
        ],
        ["image", "rm"],  # the tag only: the image under test keeps its own
    ),
}
SIGNALS = (signal.SIGTERM, signal.SIGHUP)


def lock_path(prefix: str) -> Path:
    return RUNS / f"{prefix}lock"


class RunLock:
    """The exclusive flock of `prefix`'s lock file, held until `free()` or the process's end."""

    def __init__(self, prefix: str):
        self.path = lock_path(prefix)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            # A reaper may have taken the new file for a dead run's and deleted it between
            # the open and the lock: then the lock holds a file no other run can see.
            if _same_file(fd, self.path):
                self.fd = fd
                return
            os.close(fd)

    def free(self) -> None:
        self.path.unlink(missing_ok=True)
        os.close(self.fd)


def _same_file(fd: int, path: Path) -> bool:
    try:
        return os.stat(path).st_ino == os.fstat(fd).st_ino
    except FileNotFoundError:
        return False


def objects(docker) -> dict[str, dict[str, list[str]]]:
    """Docker's `lado-test-*` objects: prefix -> kind -> names, kinds with none left out."""
    found: dict[str, dict[str, list[str]]] = {}
    for kind, (ls, _) in KINDS.items():
        for name in docker(*ls).stdout.split():
            prefix = PREFIX_IN_NAME.search(name)
            if prefix:
                found.setdefault(prefix.group(), {}).setdefault(kind, []).append(name)
    return found


def left(docker, own: str) -> dict[str, list[str]]:
    return objects(docker).get(own, {})


def _claim(prefix: str) -> int | None | bool:
    """A dead run's lock, taken: its fd; False when a live run holds it; None with no file."""
    try:
        fd = os.open(lock_path(prefix), os.O_RDWR)
    except FileNotFoundError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    return fd


def reap(docker, own: str) -> None:
    found = objects(docker)
    locks = (
        {p.name[: -len("lock")] for p in RUNS.glob("lado-test-*lock")} if RUNS.is_dir() else set()
    )
    unknown: dict[str, list[str]] = {}
    failed: list[tuple[str, str, str]] = []  # kind, name, docker's words
    for prefix in sorted((set(found) | locks) - {own}):
        kinds = found.get(prefix, {})
        fd = _claim(prefix)
        if fd is False:
            continue
        if fd is None:
            for kind, names in kinds.items():
                unknown.setdefault(kind, []).extend(names)
            continue
        before = len(failed)
        for kind, (_, rm) in KINDS.items():
            for name in kinds.get(kind, []):
                done = docker(*rm, name, check=False)
                if done.returncode != 0:
                    failed.append((kind, name, (done.stderr or done.stdout).strip()))
        if len(failed) == before:  # else its lock file stays and a later run tries again
            lock_path(prefix).unlink(missing_ok=True)
        os.close(fd)
    if unknown or failed:
        warnings.warn(_report(unknown, failed), UserWarning, stacklevel=2)


def _report(unknown: dict[str, list[str]], failed: list[tuple[str, str, str]]) -> str:
    lines = []
    if unknown:
        lines.append(
            f"lado-test-* objects in Docker of no known container test run (no lock file in"
            f" {RUNS}), not removed:"
        )
        lines += [f"  {kind[:-1]} {name}" for kind, names in unknown.items() for name in names]
    if failed:
        lines.append("could not remove what a dead container test run left:")
        lines += [f"  {kind[:-1]} {name}: {words}" for kind, name, words in failed]
    every = {kind: list(names) for kind, names in unknown.items()}
    for kind, name, _ in failed:
        every.setdefault(kind, []).append(name)
    command = "; ".join(
        " ".join(["docker", *KINDS[kind][1], *every[kind]]) for kind in KINDS if kind in every
    )
    lines.append(f"remove them with: {command}")
    return "\n".join(lines)


def _interrupt(signum, frame):
    raise KeyboardInterrupt(f"signal {signal.Signals(signum).name}")


def trap_signals() -> dict:
    return {one: signal.signal(one, _interrupt) for one in SIGNALS}


def restore_signals(saved: dict) -> None:
    for one, handler in saved.items():
        signal.signal(one, handler)
