import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from agent_helpers import init_repo, no_maintenance_env, write_index

# Tests never use the user's LADO tmux server (socket "lado").
TEST_SOCKET = f"lado-test-{uuid.uuid4().hex[:8]}"

# An agent's shell has these set (its session, its LADO home, its tmux): the tests run there
# as is, and nothing of theirs reaches the agent's LADO, also not from a subprocess.
for _var in ("LADO_AGENT", "LADO_SESSION", "LADO_HOME", "LADO_TMUX_SOCKET", "TMUX"):
    os.environ.pop(_var, None)

# No git command of the test run (the tests', LADO's, the agents') starts background gc or
# maintenance, which would still be writing in a repo while a test copies or removes it.
os.environ.update(no_maintenance_env(os.environ))

# Agents get the test run's environment (the settings above, and in the integration tests
# their short LADO_LOOP_INTERVAL and LADO_RETRY_DELAYS from tests/integration/conftest.py),
# not the user's login shell; tests of the shell set their own.
os.environ["LADO_AGENT_ENV"] = "inherit"

# No test looks up LADO's latest version on PyPI; the tests of the check switch it on with a
# local index (LADO_UPDATE_INDEX).
os.environ["LADO_NO_UPDATE_CHECK"] = "1"


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
def published(tmp_path, monkeypatch):
    """The update check switched on, reading a local index: published(**releases) writes it
    (agent_helpers.pypi_index)."""
    path = tmp_path / "pypi-index.json"
    monkeypatch.delenv("LADO_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("LADO_UPDATE_INDEX", str(path))
    return lambda **releases: write_index(path, **releases)


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
def claude_config(tmp_path, monkeypatch):
    """Claude Code's global config for the agents (CLAUDE_CONFIG_DIR), never the user's: it
    trusts the folder of the `repo` fixture, as Claude Code would after the human said yes
    there. trust(*folders) replaces what it trusts."""
    folder = tmp_path / "claude-config"
    folder.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))

    class Config:
        path = folder / ".claude.json"

        def trust(self, *folders):
            projects = {str(f): {"hasTrustDialogAccepted": True} for f in folders}
            self.path.write_text(json.dumps({"projects": projects}))

    config = Config()
    config.trust(tmp_path / "My Repo")
    return config


@pytest.fixture
def fake_clis(tmp_path, monkeypatch, claude_config):
    """Stand-ins for the agent CLIs on PATH, which a launch looks its CLI up on; the folder."""
    folder = tmp_path / "fake-clis"
    folder.mkdir()
    for name in ("claude", "kilo", "opencode", "noskills"):
        (folder / name).write_text("#!/bin/sh\n")
        (folder / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return folder


@pytest.fixture
def fake_tmux(monkeypatch, loop_starts, fake_clis):
    """Record tmux calls instead of running them; no session loop is started either."""
    from lado import terminal, tmux

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

    def list_windows(session):
        windows = []
        for call in calls:
            if call[0] == "new_session" and call[1] == session:
                windows = [call[2]]
            elif call[0] == "new_window" and call[1] == session:
                windows.append(call[2])
            elif call[0] == "kill_window" and call[1] == session:
                windows = [w for w in windows if w != call[2]]
            elif call[0] == "kill_session" and call[1] == session:
                windows = []
        if not has_session(session):
            raise tmux.TmuxError(f"can't find session: {session}")
        return windows

    monkeypatch.setattr(tmux, "has_session", has_session)
    monkeypatch.setattr(tmux, "list_windows", list_windows)
    monkeypatch.setattr(tmux, "kill_session", lambda s: calls.append(("kill_session", s)))
    monkeypatch.setattr(tmux, "kill_window", lambda *a: calls.append(("kill_window", *a)))
    monkeypatch.setattr(tmux, "popup", lambda *a: calls.append(("popup", *a)))
    monkeypatch.setattr(terminal, "close_viewers", lambda s: calls.append(("close_viewers", s)))
    return calls
