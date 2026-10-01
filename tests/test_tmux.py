import shutil
import time
import uuid

import pytest

from lado import tmux

pytestmark = pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not installed")


def test_clean_env_drops_claude_session_vars(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "x")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/keep")
    env = tmux.clean_env()
    assert "CLAUDECODE" not in env and "CLAUDE_CODE_SESSION_ID" not in env
    assert env["CLAUDE_CONFIG_DIR"] == "/keep"


def test_send_text_pastes_multiline_text(tmp_path):
    session = f"test-{uuid.uuid4().hex[:6]}"
    out = tmp_path / "out.txt"
    tmux.new_session(session, "main", str(tmp_path), {"X": "1"}, ["sh", "-c", f"cat > {out}"])
    try:
        tmux.send_text(session, "main", "line one\nline two;")
        deadline = time.time() + 5
        while time.time() < deadline and "line two;" not in out.read_text():
            time.sleep(0.05)
        assert out.read_text().splitlines()[:2] == ["line one", "line two;"]
    finally:
        tmux.kill_session(session)
    assert not tmux.has_session(session)


def _windows(session):
    return tmux.run("list-windows", "-t", f"={session}", "-F", "#{window_name}").split()


def test_kill_window_closes_only_that_window(tmp_path):
    session = f"test-{uuid.uuid4().hex[:6]}"
    tmux.new_session(session, "w10", str(tmp_path), {}, ["sleep", "60"])
    try:
        tmux.new_window(session, "w1", str(tmp_path), {}, ["sleep", "60"])
        tmux.kill_window(session, "w1")
        assert _windows(session) == ["w10"]
        tmux.kill_window(session, "w1")  # already gone: fine
        tmux.kill_window(session, "w")  # no prefix match of w10
        assert _windows(session) == ["w10"]
    finally:
        tmux.kill_session(session)
    tmux.kill_window(session, "w10")  # the whole session is gone: fine
