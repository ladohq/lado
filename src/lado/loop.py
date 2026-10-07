"""The session loop: one hidden process per running session, `lado loop <session>`.

It sweeps the session's unconfirmed messages (lado.runtime.sweep) every few seconds, so a
message is typed again on time, and the queue of an idle agent typed in, even when no send
and no hook of its agent runs. It holds
an exclusive lock on LADO_HOME/loop/<session>.lock while it runs, so a second loop of the
session exits (after LOCK_WAIT) and `lado ls` sees a session without one; the lock goes
with the process, and `lado start` or `lado attach` start a loop whose lock is free. A
repeating error is written once with its traceback, then only counted. It ends by itself,
writing why to LADO_HOME/loop.log, when its session stops, its tmux session is gone, or the
database is no longer of its own schema.
"""

import contextlib
import fcntl
import math
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import IO

from lado import providers, state, tmux


def interval_from(value: str | None) -> float:
    """The seconds between two sweeps: `value`, LADO_LOOP_INTERVAL's, else 2. Only tests set
    it (the integration tests' conftest); a value that is no positive number is refused."""
    if value is None:
        return 2.0
    try:
        seconds = float(value)
    except ValueError:
        seconds = 0.0
    if not (0 < seconds < math.inf):
        raise ValueError(f"LADO_LOOP_INTERVAL must be a positive number of seconds, not {value!r}")
    return seconds


# Also how long an agent's window may be in the making (runtime.check_windows), and what
# wait_stopped waits for, in the processes started with LADO_LOOP_INTERVAL alike.
INTERVAL = interval_from(os.environ.get("LADO_LOOP_INTERVAL"))
LOCK_WAIT = 0.1  # seconds a starting loop tries to take the lock before it exits
REPEAT_NOTE = 60.0  # seconds between two lines about the same repeating error

# Why a loop ends after `lado stop`, which kills the tmux session, then marks it stopped.
STOPPED = "the session is stopped"
TMUX_GONE = "its tmux session is gone"


def lock_path(session: str) -> Path:
    return state.home() / "loop" / f"{session}.lock"


def why_stop(session: str) -> str | None:
    """Why the session's loop must end now, or None while it has work. Another schema of
    the database is a state.SchemaError (run ends on it)."""
    sess = state.get_session(session)
    if sess is None:
        return "the session is gone"
    if sess.stopped_at:
        return STOPPED
    if not tmux.has_session(session):
        return TMUX_GONE
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


def wait_stopped(session: str, timeout: float | None = None) -> bool:
    """Whether the session's loop has ended within `timeout` seconds (three intervals by
    default): after a stop it ends at its next pass. `lado update` waits for it, so no loop
    of the old LADO is left."""
    deadline = time.monotonic() + (3 * INTERVAL if timeout is None else timeout)
    while running(session):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def start(session: str) -> None:
    """Start the session's loop as a process of its own, outside tmux, that outlives the
    command starting it. If one runs already, the new one exits after LOCK_WAIT."""
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


def run(session: str, interval: float | None = None) -> int:
    """`lado loop <session>`: sweep the session every `interval` seconds (INTERVAL by
    default) until why_stop."""
    if interval is None:
        interval = INTERVAL
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
        log(session, f"loop started, pid {os.getpid()}, a pass every {interval:g} s")
        errors = RepeatedErrors(lambda text: log(session, text))
        missing: set[str] = set()  # the agents whose window the pass before did not find
        while True:
            try:
                reason = why_stop(session)
                if reason is None:
                    # First the agents that ended without a hook: what was meant for them
                    # is dropped and told, not typed into no window.
                    missing = runtime.check_windows(session, missing)
                    runtime.sweep(session)
                    errors.worked()
            except state.SchemaError as exc:
                # Every connection refuses another schema, so no pass migrates; this LADO
                # is not the one the database is for now: end.
                reason = str(exc)
            except Exception:
                reason = None
                errors.failed()
            if reason:
                errors.flush()
                log(session, f"loop ended: {reason}")
                return 0
            time.sleep(interval)


class RepeatedErrors:
    """What a loop writes about failing passes (with `write`): a new error with its
    traceback; the same error again only as a short line, at most every REPEAT_NOTE seconds,
    and as a count when passes work again or another error comes. The session loop's and
    the UI server's change feed (lado.server.feed)."""

    def __init__(self, write: Callable[[str], None]):
        self.write = write
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
            self.write(f"error in a pass, the loop goes on:\n{traceback.format_exc()}")
            return
        self.unlogged += 1
        if now - self.noted_at >= REPEAT_NOTE:
            self.write(f"the same error again, {self.unlogged} times since its last line")
            self.unlogged, self.noted_at = 0, now

    def worked(self) -> None:
        """A pass went through."""
        if self.last is not None:
            self.flush()
            self.last = None
            self.write("passes work again")

    def flush(self) -> None:
        """Log how often the error repeated since its latest line."""
        if self.unlogged:
            self.write(f"the same error repeated {self.unlogged} more times")
            self.unlogged = 0


def log(session: str, text: str) -> None:
    """A line in LADO_HOME/loop.log; also what undoing a failed start or spawn could not do
    (lado.runtime). Never raises."""
    with contextlib.suppress(OSError), open(state.home() / "loop.log", "a") as file:
        file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {session}: {text.rstrip()}\n")
