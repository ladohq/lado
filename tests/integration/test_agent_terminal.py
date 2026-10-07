"""An agent's terminal for the UI (lado.terminal) with real tmux and the fake agent: the
viewer session, input and sizes, history, and that `lado stop` and finishing a worker leave
no viewer and no agent behind. Through the UI server's WebSocket: test_agent_terminal_socket.py."""

import json
import os
import time
from pathlib import Path

import agent_helpers
import pytest

from lado import runtime, state, terminal, tmux

pytestmark = pytest.mark.integration

SESSION = "term"
WHEEL_UP = b"\x1b[<64;5;5M"  # the mouse wheel, as xterm.js sends it (SGR)


def wait_for(check, what: str, timeout: float = agent_helpers.TIMEOUT):
    return agent_helpers.wait_for(check, what, SESSION, timeout)


def start(repo: Path, name: str = SESSION) -> None:
    runtime.start_session(str(repo), name, None, "fake")
    agent_helpers.wait_for(
        lambda: state.get_agent(name, "supervisor").status == state.IDLE, "idle", name
    )


def inputs(agent: str) -> list:
    log = agent_helpers.fake_logs(SESSION, agent) / "inputs.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def output(term: terminal.Terminal, text: str, timeout: float = agent_helpers.TIMEOUT) -> bytes:
    """Read the terminal until `text` came; all that came."""
    seen = b""
    deadline = time.monotonic() + timeout
    while text.encode() not in seen:
        if time.monotonic() > deadline:
            pytest.fail(f"{text!r} did not come; came: {seen[-2000:]!r}")
        chunk = term.read()
        if chunk is None:
            pytest.fail(f"the terminal ended before {text!r} came; came: {seen[-2000:]!r}")
        seen += chunk
    return seen


def ends(term: terminal.Terminal, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while term.read() is not None:
        if time.monotonic() > deadline:
            pytest.fail("the terminal did not end")


def our_viewers() -> list[str]:
    home = str(state.home().resolve())
    listed = tmux.sessions_with(terminal.VIEWER, terminal.HOME)
    return [name for name, viewer, of_home in listed if viewer == "1" and of_home == home]


def pane(target: str, form: str) -> str:
    return tmux.run("display-message", "-p", "-t", target, form).strip()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def opened():
    """Open terminals with `opened(agent, mode)`; all closed after the test."""
    terms: list[terminal.Terminal] = []

    def open_(agent: str, mode: str, session: str = SESSION) -> terminal.Terminal:
        terms.append(terminal.open(session, agent, mode))
        return terms[-1]

    yield open_
    for term in terms:
        term.close()


def test_view_shows_the_agents_window_and_takes_no_input(repo, opened):
    start(repo)
    term = opened("supervisor", "view")
    # LADO still types into the agent: a read-only client would make tmux refuse it.
    tmux.send_text(SESSION, "supervisor", "lines 3")
    output(term, "line 3")
    with pytest.raises(terminal.ReadOnly):
        term.write(b"typed\r")
    assert "typed" not in inputs("supervisor")


def test_control_types_into_the_agent(repo, opened):
    start(repo)
    term = opened("supervisor", "control")
    term.write(b"lines 2\r")
    output(term, "line 2")
    assert inputs("supervisor")[-1] == "lines 2"


def test_a_viewer_has_only_the_agents_window_and_no_tmux_keys(repo, opened):
    start(repo)
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_for(lambda: state.get_agent(SESSION, "w1").status == state.IDLE, "w1 idle")
    keys_before = tmux.run("list-keys")
    term = opened("supervisor", "control")
    assert tmux.window_names(term.viewer) == ["supervisor"]  # no shell window, no w1
    # tmux's prefix keys (C-b n: next window; C-b w: the window tree) go to the agent.
    term.write(b"\x02n\x02w\r")
    term.write(b"lines 1\r")
    output(term, "line 1")
    assert inputs("supervisor")[-2:] == ["\x02n\x02w", "lines 1"]
    assert tmux.window_names(term.viewer) == ["supervisor"]
    assert pane(f"={term.viewer}:", "#{window_name} #{pane_in_mode}") == "supervisor 0"
    # The global key tables are as they were; the viewer's own table is new.
    tables = {line.split()[2] for line in tmux.run("list-keys").splitlines()}
    assert tmux.VIEWER_TABLE in tables
    assert [k for k in tmux.run("list-keys").splitlines() if tmux.VIEWER_TABLE not in k] == [
        k for k in keys_before.splitlines()
    ]


def test_the_humans_tmux_session_is_left_as_it_was(repo, opened):
    start(repo)
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_for(lambda: state.get_agent(SESSION, "w1").status == state.IDLE, "w1 idle")
    before = (
        tmux.run("show-options", "-t", f"={SESSION}:"),
        pane(f"={SESSION}:", "#{window_name}"),
    )
    opened("w1", "control")
    opened("w1", "view")
    after = (tmux.run("show-options", "-t", f"={SESSION}:"), pane(f"={SESSION}:", "#{window_name}"))
    assert after == before


def test_view_leaves_the_size_alone_and_control_sets_it(repo, opened):
    start(repo)
    window = f"={SESSION}:=supervisor"
    size = tmux.window_size(window)
    view = opened("supervisor", "view")
    assert view.size == size
    time.sleep(0.5)  # nothing to wait for: the size must stay as it is a while
    assert tmux.window_size(window) == size
    assert view.follow_window() is None
    control = opened("supervisor", "control")
    control.resize((70, 20))  # the client active last sets it
    wait_for(lambda: tmux.window_size(window) == (70, 20), "the window to be 70x20")
    wait_for(lambda: view.follow_window() == (70, 20), "the view to follow")
    assert view.size == (70, 20)


def test_the_wheel_in_control_scrolls_tmux_history_of_a_plain_cli(repo, opened):
    start(repo)
    term = opened("supervisor", "control")
    term.write(b"lines 100\r")
    output(term, "line 100")
    term.write(WHEEL_UP)
    # copy-mode of the pane: the human's tmux shows it too.
    wait_for(lambda: pane(f"={SESSION}:=supervisor", "#{pane_in_mode}") == "1", "copy-mode")


def test_the_wheel_in_control_goes_to_a_full_screen_cli_that_reads_the_mouse(repo, opened):
    start(repo)
    term = opened("supervisor", "control")
    term.write(b"fullscreen\r")
    output(term, "full screen")
    term.write(WHEEL_UP + b"\r")
    wait_for(lambda: any("\x1b[<64;" in str(i) for i in inputs("supervisor")), "the wheel")
    assert pane(f"={SESSION}:=supervisor", "#{pane_in_mode}") == "0"


def test_history_gives_the_windows_past_lines_and_says_when_it_is_full_screen(repo):
    start(repo)
    tmux.send_text(SESSION, "supervisor", "lines 300")
    wait_for(lambda: "line 300" in tmux.capture(SESSION, "supervisor"), "line 300")
    found = terminal.history(SESSION, "supervisor", 1000)
    assert not found.alternate
    assert "line 1\nline 2\n" in found.text and "line 300" in found.text
    assert "line 1\n" not in terminal.history(SESSION, "supervisor", 20).text
    tmux.send_text(SESSION, "supervisor", "fullscreen")
    wait_for(lambda: terminal.history(SESSION, "supervisor", 10).alternate, "the alternate screen")


def test_closing_a_terminal_leaves_no_viewer_and_no_client(repo, opened):
    start(repo)
    term = terminal.open(SESSION, "supervisor", "control")
    assert our_viewers() == [term.viewer]
    term.close()
    assert term.process.poll() is not None
    assert our_viewers() == []
    assert state.get_agent(SESSION, "supervisor").status == state.IDLE
    assert tmux.window_names(SESSION) == ["supervisor"]


def test_stop_ends_open_terminals_and_leaves_no_window_viewer_or_agent(repo, opened):
    start(repo)
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_for(lambda: state.get_agent(SESSION, "w1").status == state.IDLE, "w1 idle")
    pids = [int(pane(f"={SESSION}:={w}", "#{pane_pid}")) for w in ("supervisor", "w1")]
    terms = [opened("supervisor", "control"), opened("w1", "view")]
    runtime.stop_session(SESSION)
    for term in terms:
        ends(term)
        assert str(terminal.ended(SESSION, term.agent)) == f'session "{SESSION}" is stopped'
    assert our_viewers() == []
    assert not tmux.has_session(SESSION)
    wait_for(lambda: not any(alive(pid) for pid in pids), "the agents to end")


def test_a_terminal_opened_after_the_session_was_killed_is_none_and_leaves_nothing(repo):
    start(repo)
    tmux.kill_session(SESSION)  # lado stop's first step, before it marks the session
    with pytest.raises(terminal.NoTerminal, match='agent "supervisor" has no window'):
        terminal.open(SESSION, "supervisor", "view")
    assert our_viewers() == []


def test_a_start_after_the_tmux_session_is_gone_ends_the_viewers_keeping_its_agents(repo, opened):
    start(repo)
    pid = int(pane(f"={SESSION}:=supervisor", "#{pane_pid}"))
    term = opened("supervisor", "view")
    tmux.kill_session(SESSION)  # the human's tmux session only: the viewer keeps the window
    assert alive(pid)
    start(repo)  # resumed: the session's tmux is gone
    ends(term)
    assert our_viewers() == []
    wait_for(lambda: not alive(pid), "the old supervisor to end")


def test_finishing_a_worker_ends_its_terminal(repo, opened):
    start(repo)
    runtime.spawn_worker(SESSION, "sleep 0", name="w1")
    wait_for(lambda: state.get_agent(SESSION, "w1").status == state.IDLE, "w1 idle")
    term = opened("w1", "view")
    runtime.finish_worker(SESSION, "w1", discard=True)
    ends(term)
    assert str(terminal.ended(SESSION, "w1")) == f'no agent "w1" in session "{SESSION}"'
    assert our_viewers() == []


def test_cleanup_leaves_a_session_named_like_a_viewer_and_another_homes_viewers(
    repo, opened, tmp_path
):
    start(repo, "lado-view-x")
    ours = opened("supervisor", "view", session="lado-view-x")
    labels = {terminal.VIEWER: "1", terminal.HOME: str(tmp_path / "other"), terminal.SESSION: "s"}
    theirs = "lado-view-other"
    tmux.new_viewer(theirs, labels)
    assert terminal.close_viewers() == [ours.viewer]
    assert tmux.has_session("lado-view-x") and tmux.has_session(theirs)
    assert state.get_agent("lado-view-x", "supervisor").status == state.IDLE
