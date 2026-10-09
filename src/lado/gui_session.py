"""Where a process runs on macOS: in the user's graphical session or outside it (ssh, cron).

macOS opens the login keychain only to processes of the user's graphical audit session, and
a process inherits its audit session from its parent, never from its environment. An
agent's parent is LADO's tmux server, which is born in the audit session of whoever runs
the first `new-session` on an empty socket. So when that is a process outside the
graphical session (`lado start` over ssh, `lado update` resuming sessions from ssh), the
server is started by launchd in the graphical domain instead (`ensure_server`), and its
agents can read their login from the keychain. Design: docs/design/macos-gui-session.md.

Only the standard library. The texts are neutral: the caller fills in the provider and its
hint (`fill`).
"""

import enum
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from lado import state, tmux


class Place(enum.Enum):
    OTHER = "other"  # not macOS
    GUI = "gui"  # in the graphical session
    REMOTE = "remote"  # outside it, while someone is logged in to it
    NO_GUI = "no-gui"  # outside it, and nobody is logged in to it
    UNKNOWN = "unknown"  # the flags or the domain could not be read


HAS_GRAPHIC_ACCESS = 0x0010  # AU_SESSION_FLAG_HAS_GRAPHIC_ACCESS, <bsm/audit_session.h>
AUDIT_INFO_SIZE = 48  # struct auditinfo_addr, <bsm/audit.h>
FLAGS_OFFSET = 40  # its last field, ai_flags (u64)
PLACE_VAR = "LADO_MACOS_PLACE"  # tests only: gui, remote or no-gui on a Mac
LABEL_PREFIX = "dev.lado.tmux"
START_TIMEOUT = 5.0  # seconds launchd's tmux server has to come up
START_POLL = 0.05
LAUNCHCTL_TIMEOUT = 10

OUTSIDE_GUI = (
    "LADO's tmux server runs outside the graphical session, so {provider} cannot read its "
    "login from the Keychain: run `lado stop --all`, then start the sessions again (over "
    "ssh too){hint}"
)
NO_GUI = (
    "nobody is logged in to the graphical session, so {provider} cannot read its login from "
    "the Keychain: log in on the Mac (Screen Sharing works){hint}"
)
PLAN_REMOTE = "tmux server will be started in the graphical session (launchd)"
LAUNCHD_FAILED = (
    "could not start LADO's tmux server in the graphical session: {why}; it starts here instead"
)
NOBODY = "an agent CLI that keeps its login there"  # `fill` with no provider


# Prints the process's auditinfo_addr in hex. Run by LADO's tmux server (run-shell), so it
# reads the server's audit session; with -I, as it imports nothing of LADO.
PROBE = (
    "import ctypes\n"
    f"info = ctypes.create_string_buffer({AUDIT_INFO_SIZE})\n"
    f"if ctypes.CDLL(None).getaudit_addr(info, {AUDIT_INFO_SIZE}):\n"
    "    raise SystemExit('getaudit_addr failed')\n"
    "print(info.raw.hex())\n"
)


def flags_from(raw: bytes) -> int:
    """ai_flags of an auditinfo_addr's bytes."""
    return int.from_bytes(raw[FLAGS_OFFSET:AUDIT_INFO_SIZE], sys.byteorder)


def _audit_raw() -> bytes:
    """This process's auditinfo_addr; OSError when it cannot be read."""
    import ctypes  # only on a Mac: hooks import this module

    info = ctypes.create_string_buffer(AUDIT_INFO_SIZE)
    try:
        failed = ctypes.CDLL(None, use_errno=True).getaudit_addr(info, AUDIT_INFO_SIZE)
    except AttributeError as error:
        raise OSError(f"no getaudit_addr: {error}") from error
    if failed:
        raise OSError(ctypes.get_errno(), "getaudit_addr failed")
    return info.raw


def _launchctl(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=LAUNCHCTL_TIMEOUT, check=False, **kwargs
    )


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _outside(flags: int) -> Place:
    """The place of a process with these flags: GUI, or by whether the graphical domain
    exists."""
    if flags & HAS_GRAPHIC_ACCESS:
        return Place.GUI
    try:
        found = _launchctl(["launchctl", "print", _domain()])
    except (OSError, subprocess.TimeoutExpired):
        return Place.UNKNOWN
    return Place.REMOTE if found.returncode == 0 else Place.NO_GUI


def place() -> Place:
    """Where this process runs: by its audit session's flags and the graphical domain,
    never by its environment (launchd's jobs have no SSH_CONNECTION, tmux's may inherit
    one)."""
    if sys.platform != "darwin":
        return Place.OTHER
    if os.environ.get(PLACE_VAR) in (Place.GUI.value, Place.REMOTE.value, Place.NO_GUI.value):
        return Place(os.environ[PLACE_VAR])
    try:
        flags = flags_from(_audit_raw())
    except OSError:
        return Place.UNKNOWN
    return _outside(flags)


def probe_argv() -> list[str]:
    return [sys.executable, "-I", "-c", PROBE]


def server_place(socket: str) -> Place | None:
    """Where LADO's tmux server on `socket` runs: None when none runs (asked first, so this
    never starts one), OTHER but on a Mac."""
    if sys.platform != "darwin":
        return Place.OTHER
    try:
        if not tmux.server_running(socket):
            return None
        printed = tmux._run_once(["run-shell", shlex.join(probe_argv())], None, socket)
        flags = flags_from(bytes.fromhex(printed.strip()))
    except (tmux.TmuxError, ValueError):
        return Place.UNKNOWN
    return _outside(flags)


def start_server(socket: str, tmux_path: str, env: dict[str, str]) -> str | None:
    """Start a tmux server on `socket` as a launchd job of the graphical domain, so it and
    its windows run in the graphical session; the job goes once the server is up, the
    server stays (it set exit-empty off: `tmux.new_session` sets it on again). None when a
    server runs after it (also one another start brought), else why not."""
    import plistlib

    label = f"{LABEL_PREFIX}.{socket}.{os.getpid()}"
    job = {
        "Label": label,
        "ProgramArguments": [
            tmux_path,
            *("-L", socket, "start-server", ";", "set-option", "-g", "exit-empty", "off"),
        ],
        "RunAtLoad": True,
        "AbandonProcessGroup": True,
    }
    # launchd's jobs start with the C locale; and a TMUX_TMPDIR of its own would put the
    # socket elsewhere.
    kept = {k: env[k] for k in ("LANG", "LC_ALL", "LC_CTYPE", "TMUX_TMPDIR") if env.get(k)}
    if kept:
        job["EnvironmentVariables"] = kept
    folder = state.home() / "launchd"
    folder.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f"{label}.", suffix=".plist", dir=folder)
    why = None
    try:
        with os.fdopen(fd, "wb") as plist:
            plistlib.dump(job, plist)
        done = _launchctl(["launchctl", "bootstrap", _domain(), name])
        if done.returncode != 0:
            why = done.stderr.strip() or f"launchctl bootstrap exited with {done.returncode}"
        else:
            deadline = time.monotonic() + START_TIMEOUT
            while not tmux.server_running(socket) and time.monotonic() < deadline:
                time.sleep(START_POLL)
            why = f"no tmux server after {START_TIMEOUT:g} s"
        _launchctl(["launchctl", "bootout", f"{_domain()}/{label}"])
    except (OSError, subprocess.TimeoutExpired, tmux.TmuxError) as error:
        why = str(error)
    finally:
        Path(name).unlink(missing_ok=True)
    return None if tmux.server_running(socket) else why


def ensure_server(socket: str) -> str | None:
    """Before a `new-session` that may start LADO's tmux server: from outside the graphical
    session, with someone logged in to it and no server on `socket`, start one there.
    None, or LAUNCHD_FAILED with why."""
    if place() != Place.REMOTE:
        return None
    try:
        if tmux.server_running(socket):
            return None
    except tmux.TmuxMissing:
        return None  # the new-session says so
    except tmux.TmuxError as error:
        return LAUNCHD_FAILED.format(why=error)
    env = tmux.clean_env()
    path = shutil.which("tmux", path=env.get("PATH"))
    if path is None:
        return None  # the new-session says tmux is missing
    why = start_server(socket, str(Path(path).absolute()), env)
    return LAUNCHD_FAILED.format(why=why) if why else None


def fill(text: str, users: list[tuple[str, str]]) -> str:
    """OUTSIDE_GUI or NO_GUI for the agent CLIs `users` (title, hint) that need the keychain."""
    provider = " and ".join(title for title, _ in users) or NOBODY
    return text.format(provider=provider, hint="".join(hint for _, hint in users))
