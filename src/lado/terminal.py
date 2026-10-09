"""An agent's terminal for the UI: the stream of its tmux window.

A viewer is a tmux session of its own whose only window is the agent's, linked into it
(`link-window`), and one `tmux attach` client to it on a pty: whoever reads the stream
cannot reach another agent's window, and tmux's keys are off in it (no prefix, no status
line, a key table of its own with only the wheel bound). A viewer is labelled with tmux user
options as it is made (VIEWER, HOME, SESSION): `lado stop` and the UI server's start find
their viewers by these labels only, never by name.

In VIEW nothing is written to the client (`Terminal.write` refuses), and its pty always has
the window's size (`Terminal.follow_window`), so it never changes it; tmux's ignore-size
flag also keeps it out while another client is attached. The client is not tmux's read-only
kind: with one attached, tmux refuses LADO's own send-keys ("client is read-only"). In
CONTROL the input goes to the agent, and tmux gives the window the size of the client that
was active last (`window-size latest`), also for the human's `lado attach`.

An agent without a terminal (unknown, its session stopped, its window gone; later an agent
that runs over ACP) raises NoTerminal. The stream is blocking: the UI server reads it in a
thread.
"""

import contextlib
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import termios
import uuid

from lado import state, tmux

VIEW, CONTROL = "view", "control"
MODES = (VIEW, CONTROL)
VIEWER, HOME, SESSION = "@lado-viewer", "@lado-home", "@lado-session"
VERSION = (3, 2)  # attach-session -f ignore-size (never read-only: see above)
READ_SIZE = 65536


class NoTerminal(Exception):
    """The agent has no terminal to show; the text says why."""


class ReadOnly(Exception):
    """Input to a terminal opened to view."""


def _check(session: str, agent: str) -> None:
    sess = state.get_session(session)
    if sess is None:
        raise NoTerminal(f'unknown session "{session}"')
    if sess.stopped_at:
        raise NoTerminal(f'session "{session}" is stopped')
    if state.get_agent(session, agent) is None:
        raise NoTerminal(f'no agent "{agent}" in session "{session}"')


def _home() -> str:
    return str(state.home().resolve())


def _options(mode: str) -> dict[str, str]:
    return {
        "prefix": "None",
        "prefix2": "None",
        "status": "off",
        "key-table": tmux.VIEWER_TABLE,
        "mouse": "on" if mode == CONTROL else "off",  # the wheel's bindings need it
    }


def open(session: str, agent: str, mode: str) -> "Terminal":
    """The agent's terminal: a viewer session with its window, and a client attached to it."""
    if mode not in MODES:
        raise ValueError(f"mode is {' or '.join(MODES)}, not {mode}")
    _check(session, agent)
    found = tmux.version()
    if found and found < VERSION:
        raise NoTerminal("an agent's terminal needs tmux 3.2 or later (see `lado doctor`)")
    viewer = f"lado-view-{uuid.uuid4().hex[:8]}"
    labels = {VIEWER: "1", HOME: _home(), SESSION: session}
    own = tmux.new_viewer(viewer, labels)
    try:
        # After the main session is killed (lado stop), there is no window to link.
        tmux.link_viewer(viewer, own, session, agent, _options(mode))
        size = tmux.window_size(f"={viewer}:")
        process, fd = _attach(viewer, mode, size)
    except BaseException as error:
        _kill(viewer)
        if isinstance(error, tmux.TmuxError):
            raise NoTerminal(f'agent "{agent}" has no window: {error}') from error
        raise
    return Terminal(session, agent, viewer, mode, process, fd, size)


def _attach(viewer: str, mode: str, size: tuple[int, int]) -> tuple[subprocess.Popen, int]:
    """`tmux attach` to the viewer on a new pty of `size`: the process and the pty's end."""
    master, slave = pty.openpty()
    try:
        _set_size(slave, size)
        # Not inside the tmux of whoever started the server: tmux would refuse to nest.
        env = {k: v for k, v in tmux.clean_env().items() if k != "TMUX"}
        env["TERM"] = "xterm-256color"
        process = subprocess.Popen(
            tmux.attach_viewer_argv(viewer, ignore_size=mode == VIEW),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            start_new_session=True,
        )
    except BaseException:
        os.close(master)
        raise
    finally:
        os.close(slave)
    return process, master


def _set_size(fd: int, size: tuple[int, int]) -> None:
    cols, rows = size
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _kill(viewer: str) -> None:
    with contextlib.suppress(tmux.TmuxError):  # gone already: with its client or window
        tmux.kill_session(viewer)


class Terminal:
    """One open terminal: read its output, write input (CONTROL), follow sizes, close."""

    def __init__(
        self,
        session: str,
        agent: str,
        viewer: str,
        mode: str,
        process: subprocess.Popen,
        fd: int,
        size: tuple[int, int],
    ):
        self.session, self.agent, self.viewer, self.mode = session, agent, viewer, mode
        self.process, self.fd, self.size = process, fd, size
        self.closed = False

    def read(self, timeout: float = 0.25) -> bytes | None:
        """The output that came, b"" when none came within `timeout` seconds, None at the
        end (the client ended: the viewer or the agent's window is gone)."""
        if self.closed:
            return None
        try:
            ready, _, _ = select.select([self.fd], [], [], timeout)
            if not ready:
                return b""
            return os.read(self.fd, READ_SIZE) or None
        except (OSError, ValueError):  # EIO once the client is gone; closed meanwhile
            return None

    def write(self, data: bytes) -> None:
        if self.mode != CONTROL:
            raise ReadOnly("this terminal is open to view: take control to type")
        while data:
            data = data[os.write(self.fd, data) :]

    def resize(self, size: tuple[int, int]) -> None:
        _set_size(self.fd, size)
        self.size = size
        self.process.send_signal(signal.SIGWINCH)

    def follow_window(self) -> tuple[int, int] | None:
        """VIEW: keep the client as large as the window (whose size the human or a CONTROL
        client sets), or it shows only a part of it. The new size when it changed."""
        try:
            size = tmux.window_size(f"={self.viewer}:")
        except tmux.TmuxError:
            return None  # the viewer is gone: read() ends
        if size == self.size:
            return None
        self.resize(size)
        return size

    def close(self) -> None:
        """End the client and remove the viewer; the agent and its window stay."""
        if self.closed:
            return
        self.closed = True
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        os.close(self.fd)
        _kill(self.viewer)


def ended(session: str, agent: str) -> NoTerminal | None:
    """Why the agent's terminal ended for good (a new one would fail as well), or None when
    a new one may open."""
    try:
        _check(session, agent)
    except NoTerminal as gone:
        return gone
    if not tmux.has_session(session):
        return NoTerminal(f'the tmux session of "{session}" is gone')
    if agent not in tmux.window_names(session):
        return NoTerminal(f'agent "{agent}" has no window')
    return None


def close_viewers(session: str | None = None) -> list[str]:
    """Remove this LADO_HOME's viewers (of one LADO session, when given), found by their
    labels only: a session named like a viewer, or another LADO_HOME's viewer, stays. Their
    clients end, and the UI's streams with them. The names of the viewers removed."""
    home = _home()
    closed = []
    for name, viewer, of_home, of_session in tmux.sessions_with(VIEWER, HOME, SESSION):
        if viewer == "1" and of_home == home and session in (None, of_session):
            _kill(name)
            closed.append(name)
    return closed
