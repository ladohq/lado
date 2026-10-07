"""An agent's liveness when its hooks do not come as usual: a turn that ends on an error, an
agent whose process ends by itself (with its session-end hook or without one), and LADO
ending agents itself (stop, finish) with no false alarm."""

import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lado import hooks, providers, runtime, state, tmux


def _hook(event, agent, payload=None):
    """Run a Claude Code hook of agent `agent` in session "s"; returns its decoded output."""
    if event == "SessionStart":
        state.add_event("s", agent, state.MCP_READY, state.get_agent("s", agent).instance)
    claude = providers.get("claude")
    neutral = claude.parse_event(event, json.dumps(payload or {}))
    output = hooks.handle(claude, neutral, "s", agent) if neutral else None
    return json.loads(output) if output else None


def _session_with_worker(repo):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task", name="w1")


def _from_lado(to):
    return [m.summary for m in state.list_messages("s") if m.sender == "lado" and m.recipient == to]


def test_a_turn_that_ends_on_an_error_types_in_the_queue_and_tells_the_supervisor(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("SessionStart", "w1")
    runtime.send_message("s", "supervisor", "w1", "one more thing")
    assert state.get_agent("s", "w1").status == state.BUSY
    out = _hook("StopFailure", "w1", {"error": "billing_error", "error_details": "no credit"})
    # Claude Code ignores StopFailure's output: the queue is typed in, not printed.
    assert out is None
    assert fake_tmux[-1] == ("send_text", "s", "w1", "[from supervisor] one more thing")
    events = [(e.kind, e.detail) for e in state.list_events("s") if e.agent == "w1"]
    assert (state.TURN_ERROR, "billing_error: no credit") in events
    assert ("status", state.IDLE) in events
    assert _from_lado("supervisor") == [
        "turn of w1 ended on an error: billing_error: no credit; it is idle"
    ]


def test_a_failed_turn_of_the_supervisor_is_told_to_the_human(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    _hook("SessionStart", "supervisor")
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go"})
    _hook("StopFailure", "supervisor", {"error": "rate_limit"})
    assert state.get_agent("s", "supervisor").status == state.IDLE
    assert _from_lado("human") == ["turn of supervisor ended on an error: rate_limit; it is idle"]
    assert _from_lado("supervisor") == []


def test_a_turn_end_without_an_error_tells_no_one(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("SessionStart", "w1")
    _hook("Stop", "w1")
    assert _from_lado("supervisor") == [] and _from_lado("human") == []
    assert state.TURN_ERROR not in [e.kind for e in state.list_events("s")]


@pytest.fixture
def resume_delays(monkeypatch):
    monkeypatch.setattr(runtime, "RESUME_DELAYS", (30.0, 120.0))


def _w1_busy(repo):
    _session_with_worker(repo)
    _hook("SessionStart", "w1")  # its task: busy


def _fail_again():
    """w1 works again (its resume, or the human), and its turn ends on an overload."""
    _hook("UserPromptSubmit", "w1", {"prompt": "go on"})
    _hook("StopFailure", "w1", {"error": "overloaded"})


def test_a_transient_error_plans_a_resume_and_tells_no_one(repo, fake_tmux, resume_delays):
    _w1_busy(repo)
    before = time.time()
    _hook("StopFailure", "w1", {"error": "overloaded", "error_details": "529"})
    w1 = state.get_agent("s", "w1")
    assert (w1.status, w1.resumes) == (state.IDLE, 1)
    assert before + 30 <= w1.resume_at <= time.time() + 30
    assert (state.TURN_ERROR, "overloaded: 529") in [
        (e.kind, e.detail) for e in state.list_events("s") if e.agent == "w1"
    ]
    assert _from_lado("supervisor") == [] and _from_lado("w1") == []


def test_each_resume_waits_its_own_delay_and_the_last_error_goes_to_the_lead(
    repo, fake_tmux, resume_delays
):
    _w1_busy(repo)
    _hook("StopFailure", "w1", {"error": "overloaded"})
    before = time.time()
    _fail_again()
    w1 = state.get_agent("s", "w1")
    assert w1.resumes == 2 and w1.resume_at >= before + 120
    assert _from_lado("supervisor") == []
    _fail_again()
    w1 = state.get_agent("s", "w1")
    assert (w1.resume_at, w1.resumes) == (None, 0)
    assert _from_lado("supervisor") == [
        "turn of w1 ended on an error after 2 resumes: overloaded; it is idle"
    ]


def test_a_transient_error_of_the_supervisor_goes_to_the_human_once_resumes_are_spent(
    repo, fake_tmux, monkeypatch
):
    monkeypatch.setattr(runtime, "RESUME_DELAYS", (30.0,))
    runtime.start_session(str(repo), "s", None, provider="claude")
    _hook("SessionStart", "supervisor")
    for _ in range(2):
        _hook("UserPromptSubmit", "supervisor", {"prompt": "go"})
        _hook("StopFailure", "supervisor", {"error": "server_error"})
    assert _from_lado("human") == [
        "turn of supervisor ended on an error after 1 resume: server_error; it is idle"
    ]


@pytest.mark.parametrize(
    "end",
    [("Stop", {}), ("StopFailure", {"error": "rate_limit"})],
    ids=["as usual", "permanent error"],
)
def test_a_turn_end_that_plans_no_resume_starts_the_resumes_again(
    repo, fake_tmux, resume_delays, end
):
    _w1_busy(repo)
    _hook("StopFailure", "w1", {"error": "overloaded"})
    _hook("UserPromptSubmit", "w1", {"prompt": "go on"})
    _hook(end[0], "w1", end[1])
    w1 = state.get_agent("s", "w1")
    assert (w1.resume_at, w1.resumes) == (None, 0)
    before = time.time()
    _fail_again()
    w1 = state.get_agent("s", "w1")
    assert w1.resumes == 1 and before + 30 <= w1.resume_at < before + 120


RESUME_LINE = (
    "[from lado] your turn ended on a temporary API error (overloaded: 529); "
    "continue where you left off (resume 1 of 2)"
)


def _w1_resume_planned(repo):
    """w1's turn ended on an overload; returns when its resume is due."""
    _w1_busy(repo)
    _hook("StopFailure", "w1", {"error": "overloaded", "error_details": "529"})
    return state.get_agent("s", "w1").resume_at


def test_a_due_resume_is_one_message_from_lado_through_the_queue(repo, fake_tmux, resume_delays):
    due = _w1_resume_planned(repo)
    runtime.sweep("s", now=due - 1)
    assert _from_lado("w1") == []
    runtime.sweep("s", now=due)
    assert [c for c in fake_tmux if c[0] == "send_text" and c[2] == "w1"] == [
        ("send_text", "s", "w1", RESUME_LINE)
    ]
    w1 = state.get_agent("s", "w1")
    assert (w1.status, w1.resume_at, w1.resumes) == (state.BUSY, None, 1)
    _hook("UserPromptSubmit", "w1", {"prompt": RESUME_LINE})
    state.set_status("s", "w1", state.IDLE)  # idle with no turn's end: nothing resets it
    runtime.sweep("s", now=due)
    [message] = [m for m in state.list_messages("s") if m.recipient == "w1"]
    assert (message.sender, message.state) == ("lado", state.DELIVERED)


@pytest.mark.parametrize("by", ["a message", "the human"])
def test_an_agent_busy_before_its_resume_is_due_gets_no_resume(repo, fake_tmux, resume_delays, by):
    due = _w1_resume_planned(repo)
    if by == "a message":
        runtime.send_message("s", "supervisor", "w1", "do this instead")
    else:
        _hook("UserPromptSubmit", "w1", {"prompt": "typed by the human"})
    assert state.get_agent("s", "w1").resume_at is None
    runtime.sweep("s", now=due + 1)
    assert _from_lado("w1") == []


def test_an_agent_that_clears_its_conversation_gets_no_resume(repo, fake_tmux, resume_delays):
    """Starting is no busy, and the new conversation makes it idle with no turn's end: the
    human acts on it, so the resume is dropped."""
    due = _w1_resume_planned(repo)
    _hook("SessionEnd", "w1", {"reason": "clear"})
    _hook("SessionStart", "w1", {"source": "clear"})
    assert state.get_agent("s", "w1").status == state.IDLE
    runtime.sweep("s", now=due + 1)
    assert _from_lado("w1") == []


def test_a_stopped_agent_gets_no_resume(repo, fake_tmux, resume_delays):
    due = _w1_resume_planned(repo)
    runtime.agent_ended("s", "w1", "its CLI exited")
    runtime.sweep("s", now=due + 1)
    assert _from_lado("w1") == []


@pytest.mark.parametrize(
    ("setting", "delays"),
    [(None, (30.0, 120.0, 480.0)), ("0.5,0.5", (0.5, 0.5))],
    ids=["default", "LADO_RESUME_DELAYS"],
)
def test_the_resume_delays_and_their_count_come_from_the_environment(setting, delays):
    env = {k: v for k, v in os.environ.items() if k != "LADO_RESUME_DELAYS"}
    if setting:
        env["LADO_RESUME_DELAYS"] = setting
    code = "from lado import runtime; print(repr(runtime.RESUME_DELAYS))"
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    ).stdout
    assert out.strip() == repr(delays)


def _queue_for_w1():
    """w1 gets a message typed in and unconfirmed (sent) and one queued (pending), and has
    a question open to the human."""
    state.set_status("s", "w1", state.IDLE)
    runtime.send_message("s", "supervisor", "w1", "typed")
    runtime.send_message("s", "supervisor", "w1", "queued")
    runtime.ask_human("s", "w1", "Which way?")
    sent, pending = [m for m in state.list_messages("s") if m.recipient == "w1"]
    assert (sent.state, pending.state) == (state.SENT, state.PENDING)
    return sent, pending


def test_an_agent_whose_cli_exits_is_stopped_with_its_queue_dropped_and_senders_told(
    repo, fake_tmux
):
    _session_with_worker(repo)
    sent, pending = _queue_for_w1()
    _hook("SessionEnd", "w1", {"reason": "other"})
    assert state.get_agent("s", "w1").status == state.STOPPED
    assert [state.get_message("s", m.id).state for m in (sent, pending)] == [state.DROPPED] * 2
    [question] = [m for m in state.list_messages("s") if m.kind == state.QUESTION]
    assert question.question_state == state.CLOSED
    ended = [e.detail for e in state.list_events("s") if e.kind == state.ENDED]
    assert ended == ["its CLI exited"]
    assert _from_lado("supervisor") == [
        f"message #{sent.id} to w1 not delivered: w1 stopped (its CLI exited): typed",
        f"message #{pending.id} to w1 not delivered: w1 stopped (its CLI exited): queued",
        'w1 stopped (its CLI exited): end it with finish_worker(name="w1")',
    ]


def test_an_ended_worker_with_unmerged_work_is_finished_with_discard(repo, fake_tmux):
    _session_with_worker(repo)
    worktree = Path(state.get_agent("s", "w1").cwd)
    (worktree / "half.txt").write_text("half done")
    runtime.agent_ended("s", "w1", "its CLI exited")
    hint = 'w1 stopped (its CLI exited): end it with finish_worker(name="w1", discard=true)'
    assert _from_lado("supervisor") == [hint]
    # Its window is gone already: finishing it closes none and forgets it.
    finished = runtime.finish_worker("s", "w1", discard=True)
    assert finished.how == "discarded" and state.get_agent("s", "w1") is None


def test_an_ended_worker_takes_no_new_message(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("SessionEnd", "w1")
    with pytest.raises(runtime.LadoError, match='no running agent "w1"'):
        runtime.send_message("s", "supervisor", "w1", "still there?")


def test_an_agent_that_ended_already_or_is_gone_ends_with_no_word(repo, fake_tmux):
    _session_with_worker(repo)
    assert runtime.agent_ended("s", "w1", "its CLI exited") is True
    told = len(state.list_messages("s"))
    events = len(state.list_events("s"))
    assert runtime.agent_ended("s", "w1", "its window closed") is False
    assert runtime.agent_ended("s", "nobody", "its window closed") is False
    assert (len(state.list_messages("s")), len(state.list_events("s"))) == (told, events)


def test_the_supervisor_ending_is_told_to_the_human_with_the_way_out(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.agent_ended("s", "supervisor", "its CLI exited")
    assert _from_lado("human") == [
        "supervisor stopped (its CLI exited): resume the session with `lado stop s`, "
        "then `lado start`"
    ]
    [told] = [m for m in state.list_messages("s") if m.recipient == "human"]
    assert told.body.splitlines()[:2] == ["lado stop s", f"lado start '{repo}' --name s"]


def test_finishing_a_worker_forgets_it_before_its_window_is_killed(repo, fake_tmux, monkeypatch):
    """The dying worker's session-end hook then finds no agent: no false alarm."""
    _session_with_worker(repo)
    seen = []
    monkeypatch.setattr(tmux, "kill_window", lambda s, w: seen.append(state.get_agent(s, w)))
    runtime.finish_worker("s", "w1")
    assert seen == [None]


def test_a_window_that_does_not_close_at_a_finish_is_told(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)

    def fails(session, window):
        raise tmux.TmuxError("server busy")

    monkeypatch.setattr(tmux, "kill_window", fails)
    with pytest.raises(runtime.LadoError) as error:
        runtime.finish_worker("s", "w1")
    assert str(error.value) == (
        'worker "w1" is finished (merged), but its window did not close: server busy; '
        f"close it with `tmux -L {tmux.socket()} kill-window -t s:w1`"
    )
    assert state.get_agent("s", "w1") is None


def test_stopping_a_session_marks_it_stopped_before_its_tmux_is_killed(
    repo, fake_tmux, monkeypatch
):
    _session_with_worker(repo)
    seen = []

    def kill_session(session):
        seen.append((state.get_session(session).stopped_at is not None, state.list_agents(session)))

    monkeypatch.setattr(tmux, "kill_session", kill_session)
    runtime.stop_session("s")
    assert seen == [(True, [])]


def test_a_tmux_session_that_survives_a_stop_is_told_with_the_way_out(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)

    def fails(session):
        raise tmux.TmuxError("server busy")

    monkeypatch.setattr(tmux, "kill_session", fails)
    with pytest.raises(runtime.LadoError) as error:
        runtime.stop_session("s")
    assert str(error.value) == (
        'session "s" is stopped, but its tmux session could not be killed: server busy; its '
        f"agents may still run: kill it with `tmux -L {tmux.socket()} kill-session -t s`; "
        "`lado start` resumes the session after that"
    )
    assert state.get_session("s").stopped_at


def later() -> datetime.datetime:
    """A minute from now: past a just spawned agent's first loop interval. Taken when the
    test runs, not at import: a long parallel run starts a test minutes after that."""
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)


GONE = "its window closed without a session-end hook"


@pytest.fixture
def windows(monkeypatch):
    """The windows tmux lists, as the test sets them."""
    shown = {"s": ["supervisor", "w1"]}
    monkeypatch.setattr(tmux, "list_windows", lambda session: list(shown[session]))
    return shown


def test_an_agent_whose_window_is_gone_two_passes_in_a_row_has_ended(repo, fake_tmux, windows):
    _session_with_worker(repo)
    windows["s"] = ["supervisor"]
    missing = runtime.check_windows("s", set(), later())
    assert missing == {"w1"} and state.get_agent("s", "w1").status == state.STARTING
    assert runtime.check_windows("s", missing, later()) == {"w1"}
    assert state.get_agent("s", "w1").status == state.STOPPED
    assert runtime.status_reason("s", "w1") == GONE
    assert _from_lado("supervisor")[-1].startswith(f"w1 stopped ({GONE})")


def test_a_window_back_in_the_next_pass_ends_nothing(repo, fake_tmux, windows):
    _session_with_worker(repo)
    windows["s"] = ["supervisor"]
    missing = runtime.check_windows("s", set(), later())
    windows["s"] = ["supervisor", "w1"]
    assert runtime.check_windows("s", missing, later()) == set()
    windows["s"] = ["supervisor"]
    assert runtime.check_windows("s", set(), later()) == {"w1"}
    assert state.get_agent("s", "w1").status == state.STARTING


def test_an_agent_spawned_within_a_loop_interval_is_left_alone(repo, fake_tmux, windows):
    """Its window may be in the making."""
    _session_with_worker(repo)
    windows["s"] = ["supervisor"]
    now = datetime.datetime.now(datetime.timezone.utc)
    assert runtime.check_windows("s", runtime.check_windows("s", set(), now), now) == set()
    assert state.get_agent("s", "w1").status == state.STARTING


def test_a_failing_window_list_changes_nothing(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)

    def fails(session):
        raise tmux.TmuxError("server busy")

    monkeypatch.setattr(tmux, "list_windows", fails)
    with pytest.raises(tmux.TmuxError):
        runtime.check_windows("s", {"w1"}, later())
    assert state.get_agent("s", "w1").status == state.STARTING
