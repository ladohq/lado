"""On a Mac, from outside the graphical session: LADO's tmux server is started by launchd in
the graphical domain, so its agents run there (lado.gui_session). Real launchctl and tmux,
the fake agent."""

import os
import subprocess
import sys

import agent_helpers
import pytest

from lado import gui_session, runtime, state, tmux

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "darwin", reason="macOS only: launchd"),
]


@pytest.fixture(autouse=True)
def graphical_domain():
    domain = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}"], capture_output=True, check=False
    )
    if domain.returncode != 0:
        pytest.skip(
            f"nobody is logged in to the graphical session (launchctl: {domain.returncode})"
        )


def _jobs() -> str:
    return subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout


def test_a_start_from_outside_the_gui_starts_tmux_in_it_through_launchd(repo, monkeypatch):
    monkeypatch.setenv("LADO_MACOS_PLACE", "remote")
    started = []
    start = gui_session.start_server
    monkeypatch.setattr(gui_session, "start_server", lambda *a: started.append(a[0]) or start(*a))
    socket = tmux.socket()
    assert not tmux.server_running(socket)
    said = runtime.start_session(str(repo), "s", None, "fake")
    assert said.warnings == []
    assert started == [socket]  # launchd started it
    assert gui_session.server_place(socket) == gui_session.Place.GUI
    agent_helpers.wait_for(
        lambda: state.get_agent("s", "supervisor").status == state.IDLE, "supervisor idle", "s"
    )
    label = f"{gui_session.LABEL_PREFIX}.{socket}.{os.getpid()}"
    assert label not in _jobs()
    assert list((state.home() / "launchd").glob("*")) == []
    runtime.stop_session("s")
    agent_helpers.wait_for(lambda: not tmux.server_running(socket), "the server's end", "s")


def test_the_place_of_no_server_starts_none():
    socket = tmux.socket()
    assert gui_session.server_place(socket) is None
    assert not tmux.server_running(socket)
