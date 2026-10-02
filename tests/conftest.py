import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from agent_helpers import init_repo, no_maintenance_env

# Tests never use the user's LADO tmux server (socket "lado").
TEST_SOCKET = f"lado-test-{uuid.uuid4().hex[:8]}"

# An agent's shell has these set (its session, its LADO home, its tmux): the tests run there
# as is, and nothing of theirs reaches the agent's LADO, also not from a subprocess.
for _var in ("LADO_AGENT", "LADO_SESSION", "LADO_HOME", "LADO_TMUX_SOCKET", "TMUX"):
    os.environ.pop(_var, None)

# No git command of the test run (the tests', LADO's, the agents') starts background gc or
# maintenance, which would still be writing in a repo while a test copies or removes it.
os.environ.update(no_maintenance_env(os.environ))


def _kill_tmux_server(socket: str) -> None:
    if shutil.which("tmux"):
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True, check=False)
    # tmux leaves the socket file behind.
    tmpdir = Path(os.environ.get("TMUX_TMPDIR") or "/tmp", f"tmux-{os.getuid()}")
    (tmpdir / socket).unlink(missing_ok=True)


@pytest.fixture(scope="session")
def kill_tmux_server():
    return _kill_tmux_server


@pytest.fixture(scope="session", autouse=True)
def _kill_test_tmux_server():
    yield
    _kill_tmux_server(TEST_SOCKET)


@pytest.fixture(autouse=True)
def lado_home(tmp_path, monkeypatch):
    home = tmp_path / "lado-home"
    monkeypatch.setenv("LADO_HOME", str(home))
    monkeypatch.setenv("LADO_TMUX_SOCKET", TEST_SOCKET)
    return home


@pytest.fixture
def repo(tmp_path):
    return init_repo(tmp_path / "My Repo")


@pytest.fixture
def loop_starts(monkeypatch):
    """Record the sessions whose loop is started, instead of starting a process."""
    from lado import loop

    started = []
    monkeypatch.setattr(loop, "start", started.append)
    return started


@pytest.fixture
def fake_tmux(monkeypatch, loop_starts):
    """Record tmux calls instead of running them; no session loop is started either."""
    from lado import tmux

    calls = []
    monkeypatch.setattr(tmux, "new_session", lambda *a: calls.append(("new_session", *a)))
    monkeypatch.setattr(tmux, "new_window", lambda *a: calls.append(("new_window", *a)))
    monkeypatch.setattr(tmux, "send_text", lambda *a: calls.append(("send_text", *a)))

    def has_session(session):
        alive = False
        for call in calls:
            if call[0] in ("new_session", "kill_session") and call[1] == session:
                alive = call[0] == "new_session"
        return alive

    monkeypatch.setattr(tmux, "has_session", has_session)
    monkeypatch.setattr(tmux, "kill_session", lambda s: calls.append(("kill_session", s)))
    monkeypatch.setattr(tmux, "kill_window", lambda *a: calls.append(("kill_window", *a)))
    monkeypatch.setattr(tmux, "popup", lambda *a: calls.append(("popup", *a)))
    return calls
