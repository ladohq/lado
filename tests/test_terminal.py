"""An agent's terminal for the UI (lado.terminal): the viewer session's tmux commands, which
viewers a cleanup takes, and the order of `lado stop`. With real tmux and processes:
tests/integration/test_terminal.py."""

import pytest

from lado import runtime, state, terminal, tmux


@pytest.fixture
def commands(monkeypatch):
    """Record each tmux call (one list of commands per call) instead of running it."""
    calls: list[list[list[str]]] = []

    def chain(*commands: list[str]) -> str:
        calls.append([list(c) for c in commands])
        return "@9\n" if commands[0][0] == "new-session" else ""

    monkeypatch.setattr(tmux, "run_chain", chain)
    monkeypatch.setattr(tmux, "run", lambda *args: chain(list(args)))
    monkeypatch.setattr(tmux, "window_size", lambda target: (100, 30))
    return calls


@pytest.fixture
def no_attach(monkeypatch):
    """Do not start `tmux attach`: the terminal's process and pty are not needed here."""
    monkeypatch.setattr(terminal, "_attach", lambda viewer, mode, size: (None, -1))


@pytest.fixture
def agent_session(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    return "s"


@pytest.mark.parametrize("mode", ["view", "control"])
def test_a_viewer_is_labelled_as_it_is_made_then_gets_only_the_agents_window(
    agent_session, commands, no_attach, mode
):
    terminal.open("s", "supervisor", mode)
    made, linked = commands
    viewer = made[0][made[0].index("-s") + 1]
    assert viewer.startswith("lado-view-")
    # The labels go with new-session in one tmux call: never a viewer without them.
    assert made[0][0] == "new-session"
    labels = {c[3]: c[4] for c in made[1:]}
    assert all(c[:3] == ["set-option", "-t", f"={viewer}:"] for c in made[1:])
    assert labels == {
        "@lado-viewer": "1",
        "@lado-home": str(state.home().resolve()),
        "@lado-session": "s",
    }
    # Then the agent's window, then its own shell window goes, then its settings.
    assert linked[0] == ["link-window", "-s", "=s:=supervisor", "-t", f"={viewer}:"]
    assert linked[1] == ["kill-window", "-t", "@9"]
    options = {c[3]: c[4] for c in linked if c[0] == "set-option"}
    assert options == {
        "prefix": "None",
        "prefix2": "None",
        "status": "off",
        "key-table": "lado-viewer",
        "mouse": "on" if mode == "control" else "off",
    }
    # Only the viewer's own key table gets bindings, and only for the wheel.
    bound = [c for c in linked if c[0] == "bind-key"]
    assert {c[2] for c in bound} == {"lado-viewer"}
    assert {c[3] for c in bound} == {"WheelUpPane", "WheelDownPane"}
    assert len(linked) == 2 + len(bound) + len(options)


def test_a_viewer_that_cannot_link_the_window_is_removed(agent_session, fake_tmux, monkeypatch):
    def chain(*commands):
        if commands[0][0] == "link-window":
            raise tmux.TmuxError("can't find window: supervisor")
        return "@9\n"

    monkeypatch.setattr(tmux, "run_chain", chain)
    with pytest.raises(terminal.NoTerminal, match='agent "supervisor" has no window'):
        terminal.open("s", "supervisor", "view")
    (kind, viewer) = fake_tmux[-1]
    assert kind == "kill_session" and viewer.startswith("lado-view-")


def test_no_terminal_for_an_unknown_agent_or_a_stopped_session(agent_session, commands):
    with pytest.raises(terminal.NoTerminal, match='no agent "w9"'):
        terminal.open("s", "w9", "view")
    with pytest.raises(terminal.NoTerminal, match='unknown session "x"'):
        terminal.open("x", "supervisor", "view")
    runtime.stop_session("s")
    commands.clear()
    with pytest.raises(terminal.NoTerminal, match='session "s" is stopped'):
        terminal.open("s", "supervisor", "control")
    assert commands == []  # nothing made in tmux


def test_cleanup_takes_only_viewers_labelled_with_this_lado_home(monkeypatch, commands):
    # Unit level: tmux's answer is made up. The real tmux: tests/integration/test_terminal.py.
    home = str(state.home().resolve())
    listed = [
        ["lado-view-1", "1", home, "s"],
        ["lado-view-2", "1", home, "t"],
        ["lado-view-x", "", "", ""],  # a LADO session with a viewer's name
        ["lado-view-3", "1", "/other/home", "s"],  # another LADO_HOME's viewer
        ["s", "", "", ""],
    ]
    monkeypatch.setattr(tmux, "sessions_with", lambda *options: listed)
    assert terminal.close_viewers() == ["lado-view-1", "lado-view-2"]
    assert terminal.close_viewers("s") == ["lado-view-1"]
    killed = [call[0] for call in commands]
    assert killed == [
        ["kill-session", "-t", f"={name}"] for name in ("lado-view-1", "lado-view-2")
    ] + [["kill-session", "-t", "=lado-view-1"]]


def test_stop_kills_the_session_first_then_its_viewers(agent_session, fake_tmux):
    runtime.stop_session("s")
    assert [c[0] for c in fake_tmux[-2:]] == ["kill_session", "close_viewers"]
    assert fake_tmux[-1] == ("close_viewers", "s")


def test_a_start_after_the_tmux_session_is_gone_kills_its_viewers(agent_session, fake_tmux):
    fake_tmux.clear()  # the tmux server died: no session "s"
    runtime.start_session(str(state.get_session("s").repo), "s", None)
    assert [c[0] for c in fake_tmux] == ["close_viewers", "new_session"]
