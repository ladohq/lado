"""An agent's terminal through a real `lado server` process: its WebSocket with real tmux and
the fake agent, `lado stop` while one is open, and the viewers a server of the same LADO_HOME
left behind."""

import json
import os
import subprocess
import sys

import pytest
from test_agent_terminal import SESSION, inputs, our_viewers, start, wait_for
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from lado import state, terminal, tmux
from lado.server import auth
from lado.server import run as server_run

pytestmark = pytest.mark.integration


@pytest.fixture
def server(tmp_path):
    """A `lado server` on a free port: its server.json; stopped after the test."""
    with open(tmp_path / "server.out", "w") as out:
        process = subprocess.Popen(
            [sys.executable, "-m", "lado.cli", "server", "--port", "0"],
            stdout=out,
            stderr=subprocess.STDOUT,
            env=os.environ,
        )
    try:
        yield server_run.wait_ready()
    finally:
        server_run.stop()
        process.wait(timeout=10)


def socket(server: dict, agent: str = "supervisor", mode: str = "view") -> ClientConnection:
    """The agent's terminal as the UI's page opens it: its Origin and the login cookie."""
    url = server["url"].replace("http://", "ws://")
    return connect(
        f"{url}/api/sessions/{SESSION}/agents/{agent}/terminal?mode={mode}",
        origin=server["url"],
        additional_headers={"Cookie": f"{auth.cookie_name(server['port'])}={auth.token()}"},
        open_timeout=10,
    )


def frame(ws: ClientConnection) -> dict:
    """The next JSON frame; output on the way is skipped."""
    while isinstance(message := ws.recv(timeout=10), bytes):
        pass
    return json.loads(message)


def output(ws: ClientConnection, text: str) -> None:
    seen = b""
    while text.encode() not in seen:
        message = ws.recv(timeout=10)
        if isinstance(message, bytes):
            seen += message


def close_of(ws: ClientConnection) -> tuple[int, str]:
    with pytest.raises(ConnectionClosed) as gone:
        while True:
            ws.recv(timeout=10)
    return gone.value.rcvd.code, gone.value.rcvd.reason


def test_control_types_into_the_agent_and_shows_its_output(repo, server):
    start(repo)
    with socket(server, mode="control") as ws:
        assert frame(ws)["type"] == "size"
        ws.send(json.dumps({"type": "input", "data": "lines 2\r"}))
        output(ws, "line 2")
    assert inputs("supervisor")[-1] == "lines 2"
    wait_for(lambda: our_viewers() == [], "no viewer left")
    assert tmux.run("list-clients").strip() == ""  # no `tmux attach` left


def test_view_refuses_input_with_an_error_frame(repo, server):
    start(repo)
    with socket(server) as ws:
        frame(ws)
        ws.send(json.dumps({"type": "input", "data": "lines 2\r"}))
        assert frame(ws)["type"] == "error"
    assert "lines 2" not in inputs("supervisor")


def test_a_view_gets_the_new_size_when_the_window_changes(repo, server):
    start(repo)
    with socket(server) as view, socket(server, mode="control") as control:
        size = frame(view)
        frame(control)
        control.send(json.dumps({"type": "resize", "cols": 70, "rows": 20}))
        assert (size["cols"], size["rows"]) != (70, 20)
        assert frame(view) == {"type": "size", "cols": 70, "rows": 20}


def test_lado_stop_ends_an_open_terminal_for_good_and_leaves_no_viewer(repo, server):
    start(repo)
    with socket(server, mode="control") as ws:
        frame(ws)
        stopped = subprocess.run(
            [sys.executable, "-m", "lado.cli", "stop", SESSION], capture_output=True, text=True
        )
        assert stopped.returncode == 0, stopped.stderr
        assert close_of(ws) == (4404, f'session "{SESSION}" is stopped')
    assert our_viewers() == []
    assert not tmux.has_session(SESSION)
    assert state.list_agents(SESSION) == []


def test_a_server_removes_the_viewers_a_server_of_its_lado_home_left(repo, tmp_path):
    start(repo)
    left = terminal.open(SESSION, "supervisor", "view")
    left.process.kill()  # as if the server died: its viewer stays
    other = {terminal.VIEWER: "1", terminal.HOME: str(tmp_path / "other"), terminal.SESSION: "s"}
    tmux.new_viewer("lado-view-other", other)
    process = subprocess.Popen(
        [sys.executable, "-m", "lado.cli", "server", "--port", "0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ,
    )
    try:
        server_run.wait_ready()
        assert our_viewers() == []
        assert tmux.has_session("lado-view-other")
        assert tmux.window_names(SESSION) == ["supervisor"]
    finally:
        server_run.stop()
        process.wait(timeout=10)
        os.close(left.fd)
