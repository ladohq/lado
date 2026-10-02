"""The session loop: one hidden process per running session, `lado loop <session>`.

It sweeps the session's unconfirmed messages (lado.runtime.sweep) every few seconds, so a
message is typed again on time even when no send and no hook of its agent runs. It holds
an exclusive lock on LADO_HOME/loop/<session>.lock while it runs, so a second loop of the
session exits at once and `lado ls` sees a session without one; the lock goes with the
process. It ends by itself, writing why to LADO_HOME/loop.log, when its session stops, its
tmux session is gone, or the database is no longer of its own schema.
"""

import contextlib
import fcntl
import os
import subprocess
import time
import traceback
from pathlib import Path
from typing import IO

from lado import providers, state, tmux

INTERVAL = 2.0  # seconds between two sweeps


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


def forget(session: str) -> None:
    """Remove the lock file of a session that is gone."""
    lock_path(session).unlink(missing_ok=True)


def run(session: str, interval: float = INTERVAL) -> int:
    """`lado loop <session>`: sweep the session every `interval` seconds until why_stop."""
    # Imported here: lado.runtime starts the loop.
    from lado import runtime

    lock = take_lock(session)
    if lock is None:
        return 0  # the session has its loop
    with lock:
        _log(session, f"loop started, pid {os.getpid()}")
        while True:
            try:
                reason = why_stop(session)
                if reason is None:
                    runtime.sweep(session)
            except Exception:
                reason = None
                _log(session, f"error in a pass, the loop goes on:\n{traceback.format_exc()}")
            if reason:
                _log(session, f"loop ended: {reason}")
                return 0
            time.sleep(interval)


def _log(session: str, text: str) -> None:
    with contextlib.suppress(OSError), open(state.home() / "loop.log", "a") as log:
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {session}: {text.rstrip()}\n")
