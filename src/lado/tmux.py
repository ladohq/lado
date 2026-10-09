"""Thin wrapper over the tmux CLI.

LADO runs its own tmux server (socket `lado`, or LADO_TMUX_SOCKET), so it never touches the
user's tmux sessions.
"""

import functools
import os
import re
import shlex
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping

DEFAULT_SOCKET = "lado"
TIMEOUT = 10
POPUP_WIDTH, POPUP_HEIGHT = "80%", "60%"
POPUP_BORDER, POPUP_BORDER_STYLE = "rounded", "fg=colour214"  # a soft orange
SERVER_ENDED = "server exited unexpectedly"  # tmux's error for a server that was exiting
SERVER_ENDED_WAIT = 0.2  # seconds before such a command runs again
POPUP_VERSION = (3, 2)  # display-popup
POPUP_BORDER_VERSION = (3, 3)  # its -b and -S; older tmux refuses the popup with them

# Set by Claude Code in its child processes. A `claude` started with them believes it is
# nested inside another Claude Code session, so the LADO tmux server must not inherit them.
_INHERITED_AGENT_VARS = ("CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT", "AI_AGENT")
_INHERITED_AGENT_PREFIXES = (
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_CODE_MESSAGING_",
    "CLAUDE_CODE_SESSION_",
    "CLAUDE_CODE_CHILD_SESSION",
)


class TmuxError(RuntimeError):
    pass


class TmuxMissing(TmuxError):
    """tmux could not be run at all. It says nothing about a session or window, so the
    calls that read a failing command as "gone" raise it instead."""


def clean_env() -> dict[str, str]:
    return without_agent_vars(os.environ)


def without_agent_vars(env: Mapping[str, str]) -> dict[str, str]:
    """`env` without the variables of the agent LADO may run in."""
    return {
        k: v
        for k, v in env.items()
        if k not in _INHERITED_AGENT_VARS and not k.startswith(_INHERITED_AGENT_PREFIXES)
    }


def socket() -> str:
    return os.environ.get("LADO_TMUX_SOCKET") or DEFAULT_SOCKET


def _arg(value: str) -> str:
    # tmux reads an argument ending in ";" as a command separator.
    return value[:-1] + "\\;" if value.endswith(";") else value


def run(*args: str, input: str | None = None) -> str:
    return _run([_arg(a) for a in args], input)


def run_chain(*commands: list[str], before_attempt: Callable[[], object] | None = None) -> str:
    """Several commands in one tmux call, run in order; tmux skips the rest after one fails
    (and the call fails). `before_attempt` runs before each attempt (_run)."""
    args: list[str] = []
    for command in commands:
        args += [*([";"] if args else []), *(_arg(a) for a in command)]
    return _run(args, before_attempt=before_attempt)


def _run(
    args: list[str],
    input: str | None = None,
    before_attempt: Callable[[], object] | None = None,
) -> str:
    if before_attempt:
        before_attempt()
    try:
        return _run_once(args, input)
    except TmuxError as error:
        # The server was ending as the command came (its last session was just killed, as
        # `lado start` does to a gone session's UI viewers): it ran nothing. Once more, on
        # a new server.
        if str(error) != SERVER_ENDED:
            raise
        time.sleep(SERVER_ENDED_WAIT)
        if before_attempt:
            before_attempt()
        return _run_once(args, input)


def server_running(sock: str | None = None) -> bool:
    """Whether a tmux server runs on the socket (LADO's by default); never starts one."""
    try:
        _run_once(["list-sessions"], None, sock)
    except TmuxMissing:
        raise
    except TmuxError as error:
        if "no server running" in str(error) or "error connecting" in str(error):
            return False
        raise
    return True


def _run_once(args: list[str], input: str | None, sock: str | None = None) -> str:
    cmd = ["tmux", "-L", sock or socket(), *args]
    env = clean_env()
    try:
        result = subprocess.run(
            cmd,
            input=input,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TmuxError(f"tmux timed out: {' '.join(args)}") from exc
    except FileNotFoundError as exc:
        # Looked up on the PATH of `env`, as subprocess does.
        raise TmuxMissing(f"tmux is not installed or not on PATH ({env.get('PATH', '')})") from exc
    except OSError as exc:
        raise TmuxMissing(f"cannot run tmux (PATH: {env.get('PATH', '')}): {exc}") from exc
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip() or f"tmux failed: {' '.join(args)}")
    return result.stdout


def _env_args(env: dict[str, str]) -> list[str]:
    return [arg for k, v in env.items() for arg in ("-e", f"{k}={v}")]


# A window's name is its agent's, the only way LADO finds the agent's window. A name given
# with -n is not renamed automatically; no program renames it either, also when the user's
# tmux.conf allows that (the option is global on LADO's own server).
NO_RENAME = ["set-option", "-g", "allow-rename", "off"]
# tmux's default, set again first: a server started without sessions (by launchd, see
# lado.gui_session) then ends with its last session as any other, and at once when the
# new-session fails.
EXIT_EMPTY = ["set-option", "-g", "exit-empty", "on"]


# A window gets the tmux server's environment; an agent's window replaces it (lado.agent_env).
def new_session(
    session: str,
    window: str,
    cwd: str,
    cmd: list[str],
    before_attempt: Callable[[], str | None] | None = None,
) -> list[str]:
    """`before_attempt` runs before each attempt to make the session, which may start the
    tmux server; returns what it said (each line once)."""
    said: list[str] = []

    def attempt() -> None:
        line = before_attempt() if before_attempt else None
        if line and line not in said:
            said.append(line)

    made = ["new-session", "-d", "-s", session, "-n", window, "-c", cwd, *cmd]
    run_chain(EXIT_EMPTY, made, NO_RENAME, before_attempt=attempt)
    return said


def new_window(session: str, window: str, cwd: str, cmd: list[str]) -> None:
    run_chain(["new-window", "-d", "-t", f"{session}:", "-n", window, "-c", cwd, *cmd], NO_RENAME)


def has_session(session: str) -> bool:
    try:
        run("has-session", "-t", f"={session}")
    except TmuxMissing:
        raise
    except TmuxError:
        return False
    return True


def kill_session(session: str) -> None:
    run("kill-session", "-t", f"={session}")


def kill_window(session: str, window: str) -> None:
    """Close the window and the program in it, in every session it is linked into (a UI
    viewer's too). A window that is already gone is fine."""
    if window in window_names(session):
        run("kill-window", "-t", f"={session}:={window}")


def window_names(session: str) -> list[str]:
    """The names of the session's windows; none when the session is gone."""
    try:
        return run("list-windows", "-t", f"={session}", "-F", "#{window_name}").split()
    except TmuxMissing:
        raise
    except TmuxError:
        return []


def list_windows(session: str) -> list[str]:
    """The names of the session's windows; a TmuxError when tmux cannot list them (also for
    a gone session), never an empty list for a failure: the session loop takes an agent
    whose window is not listed for ended (lado.runtime.check_windows)."""
    return run("list-windows", "-t", f"={session}", "-F", "#{window_name}").splitlines()


def send_text(session: str, window: str, text: str) -> None:
    """Type `text` into the program running in the window and press Enter.

    The text goes in as one bracketed paste, so newlines inside it do not submit early. A
    text ending in a backslash gets a space after it: Claude Code reads a backslash before
    Enter as a line break, not a submit.
    """
    if text.endswith("\\"):
        text += " "
    target = f"{session}:{window}"
    if run("display-message", "-p", "-t", target, "#{pane_in_mode}").strip() == "1":
        run("send-keys", "-t", target, "-X", "cancel")  # copy-mode swallows input
    buffer = f"lado-{uuid.uuid4().hex[:8]}"
    run("load-buffer", "-b", buffer, "-", input=text)
    run("paste-buffer", "-p", "-d", "-b", buffer, "-t", target)
    time.sleep(0.05)  # let the paste land before Enter, or Enter can end up inside it
    run("send-keys", "-t", target, "Enter")


def popup(session: str, title: str, argv: list[str], env: dict[str, str]) -> int:
    """Open a popup running `argv` on each client attached to the session; it closes when
    `argv` exits. Returns on how many clients. Does not wait for the popups: tmux would
    block until they close. A client that shows a popup already keeps it and its command:
    tmux does not stack popups, it only applies the new options (such as the title) to the
    open one."""
    try:
        clients = run("list-clients", "-t", f"={session}", "-F", "#{client_name}").split()
    except TmuxMissing:
        raise
    except TmuxError:
        return 0  # the session is gone
    for client in clients:
        subprocess.Popen(
            popup_command(client, title, argv, env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=clean_env(),
            start_new_session=True,
        )
    return len(clients)


def popup_command(client: str, title: str, argv: list[str], env: dict[str, str]) -> list[str]:
    """The tmux command for a popup on `client`: easy to notice but calm, a rounded border
    in a soft colour around the terminal's own background and text (tmux 3.3+; older ones
    get tmux's plain border)."""
    title = " " + title.replace("#", "##") + " "  # -T is a format
    cmd = ["tmux", "-L", socket(), "display-popup", "-c", client, "-E", "-T", title]
    found = version()
    if found and found >= POPUP_BORDER_VERSION:
        cmd += ["-b", POPUP_BORDER, "-S", POPUP_BORDER_STYLE]
    cmd += ["-w", POPUP_WIDTH, "-h", POPUP_HEIGHT]
    return [*cmd, *_env_args(env), shlex.join(argv)]


@functools.cache
def version() -> tuple[int, int] | None:
    """The installed tmux's version, from `tmux -V`; None if it cannot be read."""
    try:
        result = subprocess.run(
            ["tmux", "-V"], capture_output=True, text=True, timeout=TIMEOUT, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_version(result.stdout)


def parse_version(output: str) -> tuple[int, int] | None:
    """(major, minor) from `tmux -V` output such as "tmux 3.2a" or "tmux next-3.4"."""
    found = re.search(r"(\d+)\.(\d+)", output)
    return (int(found[1]), int(found[2])) if found else None


def capture(session: str, window: str) -> str:
    return run("capture-pane", "-p", "-t", f"{session}:{window}")


def attach_argv(session: str) -> list[str]:
    return ["tmux", "-L", socket(), "attach-session", "-t", f"={session}"]


# A viewer's own key table (lado.terminal): only the wheel is bound. It goes to the program
# when that reads the mouse or the pane is in a mode, else into tmux's copy-mode, which it
# leaves at the bottom. tmux's other tables stay as they are.
VIEWER_TABLE = "lado-viewer"
VIEWER_BINDINGS = [
    [
        "bind-key",
        "-T",
        VIEWER_TABLE,
        "WheelUpPane",
        "if-shell",
        "-F",
        "#{||:#{pane_in_mode},#{mouse_any_flag}}",
        "send-keys -M",
        "copy-mode -e",
    ],
    ["bind-key", "-T", VIEWER_TABLE, "WheelDownPane", "send-keys", "-M"],
]


def new_viewer(viewer: str, labels: dict[str, str]) -> str:
    """A detached session for a viewer, with its labels (user options) set in the same tmux
    call: it never exists without them. Returns the id of the window it was made with."""
    made = ["new-session", "-d", "-s", viewer, "-P", "-F", "#{window_id}", "cat"]
    labelled = (["set-option", "-t", f"={viewer}:", k, v] for k, v in labels.items())
    return run_chain(made, *labelled).strip()


def link_viewer(viewer: str, own: str, session: str, window: str, options: dict[str, str]) -> None:
    """Give the viewer the window `session:window` as its only one: link it, close the
    window `own` it was made with, bind its key table, set its options."""
    run_chain(
        ["link-window", "-s", f"={session}:={window}", "-t", f"={viewer}:"],
        ["kill-window", "-t", own],
        *VIEWER_BINDINGS,
        *(["set-option", "-t", f"={viewer}:", k, v] for k, v in options.items()),
    )


def attach_viewer_argv(viewer: str, ignore_size: bool) -> list[str]:
    """`tmux attach` to a viewer. With `ignore_size` its size counts only while no other
    client is attached. Never read-only: tmux takes an attached client for the client of a
    command from outside, and a read-only one makes LADO's send-keys fail."""
    flags = ["-f", "ignore-size"] if ignore_size else []
    return ["tmux", "-L", socket(), "attach-session", *flags, "-t", f"={viewer}"]


def sessions_with(*options: str) -> list[list[str]]:
    """Each session's name and the values of the user options given ('' where unset); none
    when no tmux server runs."""
    form = "\t".join(["#{session_name}", *(f"#{{{option}}}" for option in options)])
    try:
        listed = run("list-sessions", "-F", form)
    except TmuxError as error:
        if "no server running" in str(error) or "error connecting" in str(error):
            return []
        raise
    return [line.split("\t") for line in listed.splitlines()]


def window_size(target: str) -> tuple[int, int]:
    """The width and height of the window `target`."""
    size = run("display-message", "-p", "-t", target, "#{window_width} #{window_height}")
    cols, rows = size.split()
    return int(cols), int(rows)


def history(session: str, window: str, lines: int) -> tuple[str, bool]:
    """The last `lines` lines of the window's history and its screen, wrapped lines joined,
    and whether the program shows the alternate screen (a full-screen program: its history
    is not in tmux's)."""
    target = f"={session}:={window}"
    alternate = run("display-message", "-p", "-t", target, "#{alternate_on}").strip() == "1"
    text = run("capture-pane", "-p", "-J", "-S", f"-{lines}", "-t", target)
    return text, alternate
