"""Run a command while holding the machine's test-run lock: one heavy test run at a time.

    python scripts/check_lock.py <command> [args...]
    python scripts/check_lock.py --path      # print the lock file

The Makefile runs `make check`, `make test`, `make test-integration` and `make test-ui`
through it, so two runs from different worktrees or sessions do not overload the machine.
The lock is an flock on one file in /tmp, shared by every worktree and every LADO_HOME
(LADO_CHECK_LOCK_FILE overrides it, for the tests). A second run waits and says once for
whose run. The lock is held by this process, never by the command's: it goes when this
process ends, also on a failure, Ctrl-C or a kill, and a process the command leaves behind
does not keep it.

The command gets LADO_CHECK_LOCK_HELD, and a run inside it does not lock again (check
calls its parts). LADO_CHECK_LOCK=0 runs the command without the lock (CI, or a parallel
run on purpose).

Standard library only: macOS has no flock(1).
"""

import fcntl
import os
import signal
import subprocess
import sys
from pathlib import Path

HELD = "LADO_CHECK_LOCK_HELD"
SWITCH = "LADO_CHECK_LOCK"
FILE = "LADO_CHECK_LOCK_FILE"


def lock_path() -> Path:
    return Path(os.environ.get(FILE) or f"/tmp/lado-check-{os.getuid()}.lock")


def main(argv: list[str]) -> int:
    if argv == ["--path"]:
        print(lock_path())
        return 0
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    if os.environ.get(SWITCH) == "0" or os.environ.get(HELD):
        os.execvp(argv[0], argv)

    # Not inherited by the command (Python's default), so only this process holds the lock.
    fd = os.open(lock_path(), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        holder = os.pread(fd, 4096, 0).decode(errors="replace").strip() or "another run"
        print(f"check lock: waiting for {holder}", file=sys.stderr, flush=True)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except KeyboardInterrupt:
            return 130
    os.ftruncate(fd, 0)
    os.pwrite(fd, f"the run in {os.getcwd()} (pid {os.getpid()})\n".encode(), 0)

    command = subprocess.Popen(argv, env={**os.environ, HELD: str(os.getpid())})

    # Ctrl-C reaches the command from the terminal itself: wait for it to stop. A signal
    # sent to this process alone is passed on. Handlers, not SIG_IGN: the command must
    # not inherit an ignored SIGINT.
    signal.signal(signal.SIGINT, lambda *_: None)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda signum, _: command.send_signal(signum))
    status = command.wait()
    return 128 - status if status < 0 else status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
