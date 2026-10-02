"""The session loop: one hidden process per running session, `lado loop <session>`.

It sweeps the session's unconfirmed messages (lado.runtime.sweep) every few seconds, so a
message is typed again on time even when no send and no hook of its agent runs. It holds
an exclusive lock on LADO_HOME/loop/<session>.lock while it runs, so a second loop of the
session exits (after LOCK_WAIT) and `lado ls` sees a session without one; the lock goes
with the process, and `lado start` or `lado attach` start a loop whose lock is free. A
repeating error is written once with its traceback, then only counted. It ends by itself,
writing why to LADO_HOME/loop.log, when its session stops, its tmux session is gone, or the
database is no longer of its own schema.
"""

import contextlib
import fcntl
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import IO

from lado import providers, state, tmux

INTERVAL = 2.0  # seconds between two sweeps
LOCK_WAIT = 0.1  # seconds a starting loop tries to take the lock before it exits
REPEAT_NOTE = 60.0  # seconds between two lines about the same repeating error


def lock_path(session: str) -> Path:
    return state.home() / "loop" / f"{session}.lock"


def why_stop(session: str) -> str | None:
    """Why the session's loop must end now, or None while it has work."""
    version = state.schema_version()
    if version != state.SCHEMA_VERSION:
        # Checked first: opening the database with another schema would migrate it.
        return f"the database has schema version {version}, this loop knows {state.SCHEMA_VERSION}"
    sess = state.get_session(session)
    if sess is None:
        return "the session is gone"
    if sess.stopped_at:
        return "the session is stopped"
    if not tmux.has_session(session):
        return "its tmux session is gone"
    return None


def take_lock(session: str) -> IO | None:
    """The session's loop lock, held until the returned file is closed or the process ends;
    None when another process holds it."""
    path = lock_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = open(path, "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return None
    return lock


def running(session: str) -> bool:
    """Whether a loop of the session runs: its lock is held."""
    if not lock_path(session).exists():
        return False
    lock = take_lock(session)
    if lock is None:
        return True
    lock.close()
    return False


def start(session: str) -> None:
    """Start the session's loop as a process of its own, outside tmux, that outlives the
    command starting it. If one runs already, the new one exits at once."""
    subprocess.Popen(
        providers.lado_command("loop", session),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # not ended with the terminal or tmux client that started it
    )


def ensure(session: str) -> None:
    """Start the loop of a running session whose loop is gone (killed, crashed)."""
    if not running(session):
        start(session)


def forget(session: str) -> None:
    """Remove the lock file of a session that is gone."""
    lock_path(session).unlink(missing_ok=True)


def run(session: str, interval: float = INTERVAL) -> int:
    """`lado loop <session>`: sweep the session every `interval` seconds until why_stop."""
    # Imported here: lado.runtime starts the loop.
    from lado import runtime

    # `running()` holds the lock for a moment, so a loop starting then waits a little.
    deadline = time.monotonic() + LOCK_WAIT
    lock = take_lock(session)
    while lock is None and time.monotonic() < deadline:
        time.sleep(LOCK_WAIT / 10)
        lock = take_lock(session)
    if lock is None:
        return 0  # the session has its loop
    with lock:
        _log(session, f"loop started, pid {os.getpid()}")
        errors = _Errors(session)
        while True:
            try:
                reason = why_stop(session)
                if reason is None:
                    runtime.sweep(session)
            except Exception:
                reason = None
                errors.failed()
            else:
                errors.worked()
            if reason:
                errors.flush()
                _log(session, f"loop ended: {reason}")
                return 0
            time.sleep(interval)


class _Errors:
    """What the loop writes about failing passes: a new error with its traceback; the same
    error again only as a short line, at most every REPEAT_NOTE seconds, and as a count when
    passes work again or another error comes."""

    def __init__(self, session: str):
        self.session = session
        self.last: str | None = None  # the error of the latest failing pass, while it repeats
        self.unlogged = 0  # repeats of it since its latest line
        self.noted_at = 0.0

    def failed(self) -> None:
        """Log the error being handled."""
        error = "".join(traceback.format_exception_only(*sys.exc_info()[:2])).strip()
        now = time.monotonic()
        if error != self.last:
            self.flush()
            self.last, self.noted_at = error, now
            _log(self.session, f"error in a pass, the loop goes on:\n{traceback.format_exc()}")
            return
        self.unlogged += 1
        if now - self.noted_at >= REPEAT_NOTE:
            _log(self.session, f"the same error again, {self.unlogged} times since its last line")
            self.unlogged, self.noted_at = 0, now

    def worked(self) -> None:
        """A pass went through."""
        if self.last is not None:
            self.flush()
            self.last = None
            _log(self.session, "passes work again")

    def flush(self) -> None:
        """Log how often the error repeated since its latest line."""
        if self.unlogged:
            _log(self.session, f"the same error repeated {self.unlogged} more times")
            self.unlogged = 0


def _log(session: str, text: str) -> None:
    with contextlib.suppress(OSError), open(state.home() / "loop.log", "a") as log:
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {session}: {text.rstrip()}\n")
