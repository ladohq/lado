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
    tmux.new_session(session, "main", str(tmp_path), ["sh", "-c", f"cat > {out}"])
    try:
        tmux.send_text(session, "main", "line one\nline two;")
        deadline = time.time() + 5
        while time.time() < deadline and "line two;" not in out.read_text():
            time.sleep(0.05)
        assert out.read_text().splitlines()[:2] == ["line one", "line two;"]
    finally:
        tmux.kill_session(session)
    assert not tmux.has_session(session)


def _screen(session, window, text, timeout=5):
    """The window's screen once `text` shows on it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        screen = tmux.capture(session, window)
        if text in screen:
            return screen
        time.sleep(0.05)
    raise AssertionError(f"{text!r} not on the screen:\n{screen}")


@pytest.mark.parametrize(
    ("output", "version"),
    [("tmux 3.7c", (3, 7)), ("tmux 3.2a", (3, 2)), ("tmux next-3.4", (3, 4)), ("tmux", None)],
)
def test_parse_version(output, version):
    assert tmux.parse_version(output) == version


def test_a_popup_on_tmux_before_3_3_has_no_border_options(monkeypatch):
    # tmux 3.2 (Ubuntu 22.04) has display-popup, but refuses -b and -S.
    monkeypatch.setattr(tmux, "version", lambda: (3, 2))
    cmd = tmux.popup_command("/dev/ttys001", "LADO: waiting", ["lado", "answer"], {})
    assert "-b" not in cmd and "-S" not in cmd
    assert cmd[cmd.index("-T") + 1] == " LADO: waiting "
    assert cmd[-1] == "lado answer"


def test_a_popup_has_a_calm_coloured_rounded_border_and_a_title(monkeypatch):
    monkeypatch.setenv("LADO_TMUX_SOCKET", "lado-test-x")
    monkeypatch.setattr(tmux, "version", lambda: (3, 7))
    cmd = tmux.popup_command("/dev/ttys001", "LADO: waiting #1", ["lado", "answer"], {"A": "b"})
    assert cmd[:6] == ["tmux", "-L", "lado-test-x", "display-popup", "-c", "/dev/ttys001"]

    def option(flag):
        return cmd[cmd.index(flag) + 1]

    assert "-E" in cmd  # closes when the command exits
    assert option("-T") == " LADO: waiting ##1 "  # a format: "#" is doubled
    assert option("-b") == "rounded"
    assert option("-S") == "fg=colour214"  # a soft orange border
    assert "-s" not in cmd  # the terminal's own background and text colours
    assert option("-e") == "A=b"
    assert cmd[-1] == "lado answer"


def test_popup_opens_on_the_clients_attached_to_the_session(tmp_path):
    session = f"test-{uuid.uuid4().hex[:6]}"
    viewer = f"viewer-{uuid.uuid4().hex[:6]}"
    tmux.new_session(session, "main", str(tmp_path), ["sleep", "60"])
    try:
        assert tmux.popup(session, "nobody", ["true"], {}) == 0  # no client attached
        # A client: a tmux attached to the session, running in a window of its own.
        attach = ["env", "-u", "TMUX", *tmux.attach_argv(session)]
        tmux.new_session(viewer, "v", str(tmp_path), attach)
        deadline = time.time() + 5
        while time.time() < deadline and not tmux.run("list-clients", "-t", f"={session}"):
            time.sleep(0.05)
        out = tmp_path / "answer.txt"
        script = f'echo "asks $LADO_X"; read a; echo "$a" > "{out}"'
        assert tmux.popup(session, "lado #1", ["sh", "-c", script], {"LADO_X": "y"}) == 1
        screen = _screen(viewer, "v", "asks y")
        assert "lado #1" in screen
        # A second popup while one is open does not run: the open one stays.
        assert tmux.popup(session, "lado #1", ["sh", "-c", "echo other; sleep 5"], {}) == 1
        time.sleep(0.3)
        screen = tmux.capture(viewer, "v")
        assert "asks y" in screen and "other" not in screen
        tmux.run("send-keys", "-t", f"{viewer}:v", "approve", "Enter")
        deadline = time.time() + 5
        while time.time() < deadline and not out.exists():
            time.sleep(0.05)
        assert out.read_text() == "approve\n"
        # The agent's window got nothing.
        assert "approve" not in tmux.capture(session, "main")
    finally:
        if tmux.has_session(viewer):
            tmux.kill_session(viewer)
        tmux.kill_session(session)
    assert tmux.popup(session, "gone", ["true"], {}) == 0


def test_a_command_that_meets_an_ending_server_runs_once_more(monkeypatch):
    answers = [tmux.TmuxError("server exited unexpectedly"), "ok"]
    calls = []

    def once(args, input):
        calls.append(args)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(tmux, "_run_once", once)
    monkeypatch.setattr(tmux, "SERVER_ENDED_WAIT", 0)
    assert tmux.run("new-session", "-d") == "ok"
    assert calls == [["new-session", "-d"]] * 2
    monkeypatch.setattr(
        tmux,
        "_run_once",
        lambda args, input: (_ for _ in ()).throw(tmux.TmuxError("can't find session: x")),
    )
    with pytest.raises(tmux.TmuxError, match="can't find session"):
        tmux.run("has-session")


def test_a_missing_tmux_is_a_tmux_error_that_names_the_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(tmux.TmuxMissing) as error:
        tmux.run("list-sessions")
    assert str(error.value) == f"tmux is not installed or not on PATH ({tmp_path})"
    assert isinstance(error.value, tmux.TmuxError)


def test_a_tmux_that_cannot_run_is_a_tmux_error_that_names_the_path(monkeypatch, tmp_path):
    (tmp_path / "tmux").write_text("not a program")  # not executable: PermissionError
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(tmux.TmuxMissing) as error:
        tmux.run("list-sessions")
    message = str(error.value)
    assert message.startswith("cannot run tmux (PATH: ")
    assert str(tmp_path) in message and "Permission denied" in message


def test_a_missing_tmux_is_not_taken_for_a_gone_session(monkeypatch, tmp_path):
    # A missing tmux says nothing about the session: it must not read as gone (a migration
    # under a running session, a session shown as gone, a ghost worker left starting).
    monkeypatch.setenv("PATH", str(tmp_path))
    for call in (
        lambda: tmux.has_session("s"),
        lambda: tmux.window_names("s"),
        lambda: tmux.kill_window("s", "w"),
        lambda: tmux.popup("s", "t", ["true"], {}),
        lambda: tmux.sessions_with("@x"),
    ):
        with pytest.raises(tmux.TmuxMissing):
            call()


def _windows(session):
    return tmux.run("list-windows", "-t", f"={session}", "-F", "#{window_name}").split()


def test_kill_window_closes_only_that_window(tmp_path):
    session = f"test-{uuid.uuid4().hex[:6]}"
    tmux.new_session(session, "w10", str(tmp_path), ["sleep", "60"])
    try:
        tmux.new_window(session, "w1", str(tmp_path), ["sleep", "60"])
        tmux.kill_window(session, "w1")
        assert _windows(session) == ["w10"]
        tmux.kill_window(session, "w1")  # already gone: fine
        tmux.kill_window(session, "w")  # no prefix match of w10
        assert _windows(session) == ["w10"]
    finally:
        tmux.kill_session(session)
    tmux.kill_window(session, "w10")  # the whole session is gone: fine
