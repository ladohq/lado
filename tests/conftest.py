import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from agent_helpers import init_repo

# Tests never use the user's LADO tmux server (socket "lado").
TEST_SOCKET = f"lado-test-{uuid.uuid4().hex[:8]}"


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
    for var in ("LADO_SESSION", "LADO_AGENT"):  # set when the tests run inside a LADO agent
        monkeypatch.delenv(var, raising=False)
    return home


@pytest.fixture
def repo(tmp_path):
    return init_repo(tmp_path / "My Repo")


@pytest.fixture
def fake_tmux(monkeypatch):
    """Record tmux calls instead of running them."""
    from lado import tmux

    calls = []
    monkeypatch.setattr(tmux, "new_session", lambda *a: calls.append(("new_session", *a)))
    monkeypatch.setattr(tmux, "new_window", lambda *a: calls.append(("new_window", *a)))
    monkeypatch.setattr(tmux, "send_text", lambda *a: calls.append(("send_text", *a)))
    monkeypatch.setattr(tmux, "has_session", lambda s: any(c[0] == "new_session" for c in calls))
    monkeypatch.setattr(tmux, "kill_session", lambda s: calls.append(("kill_session", s)))
    return calls
