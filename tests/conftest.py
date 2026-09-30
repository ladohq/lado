import subprocess

import pytest


@pytest.fixture(autouse=True)
def lado_home(tmp_path, monkeypatch):
    home = tmp_path / "lado-home"
    monkeypatch.setenv("LADO_HOME", str(home))
    return home


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "My Repo"
    path.mkdir()
    git = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return path


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
