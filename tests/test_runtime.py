import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import agent_helpers
import pytest

from lado import agent_env, hooks, kits, loop, providers, runs, runtime, state, tmux


def test_slug():
    assert runtime.slug("My Repo.v2") == "my-repo-v2"
    assert runtime.slug("...") == "lado"


def test_start_session_launches_supervisor(repo, fake_tmux, lado_home):
    started = runtime.start_session(str(repo), None, "acceptEdits")
    assert (started.session.name, started.resumed) == ("my-repo", False)
    [(kind, session, window, cwd, *_)] = fake_tmux
    assert (kind, session, window, cwd) == ("new_session", "my-repo", "supervisor", str(repo))
    env, cmd = agent_helpers.launched(fake_tmux[0])
    assert (
        env.items()
        >= {
            "LADO_HOME": str(lado_home),
            "LADO_SESSION": "my-repo",
            "LADO_AGENT": "supervisor",
            "LADO_TMUX_SOCKET": tmux.socket(),
        }.items()
    )
    assert cmd[0] == "claude"
    assert cmd[cmd.index("--permission-mode") + 1] == "acceptEdits"
    mcp = json.loads(open(cmd[cmd.index("--mcp-config") + 1]).read())
    assert mcp["mcpServers"]["lado"]["env"]["LADO_SESSION"] == "my-repo"
    settings = json.loads(open(cmd[cmd.index("--settings") + 1]).read())
    assert (
        "hook Stop --session my-repo --agent supervisor"
        in (settings["hooks"]["Stop"][0]["hooks"][0]["command"])
    )
    assert state.get_agent("my-repo", "supervisor").status == state.STARTING


@pytest.fixture
def resolved(monkeypatch, fake_clis):
    """Make the resolved environment a known one; count how often it is resolved."""
    calls = []

    def resolve():
        calls.append(1)
        return {
            "PATH": str(fake_clis),
            "FROM_SHELL": "1",
            "LADO_AGENT": "parent",
            "KILO_DISABLE_AUTOUPDATE": "0",
        }

    monkeypatch.setattr(agent_env, "resolve", resolve)
    return calls


def test_agents_get_the_resolved_environment_then_lados_then_the_providers(
    repo, fake_tmux, resolved
):
    runtime.start_session(str(repo), "s", None, "kilo")
    runtime.spawn_worker("s", "a task")
    for call, name in zip(fake_tmux, ("supervisor", "worker"), strict=True):
        env, _ = agent_helpers.launched(call)
        assert env["FROM_SHELL"] == "1"
        assert env["LADO_AGENT"] == name
        assert env["KILO_DISABLE_AUTOUPDATE"] == "1"
    assert len(resolved) == 2  # anew for each launch


def _broken_env():
    raise agent_env.AgentEnvError("your shell failed with exit status 1: zsh -ilc ...")


def test_a_start_whose_environment_fails_launches_nothing(repo, fake_tmux, monkeypatch):
    monkeypatch.setattr(agent_env, "resolve", _broken_env)
    with pytest.raises(runtime.LadoError, match="your shell failed with exit status 1"):
        runtime.start_session(str(repo), "s", None)
    assert fake_tmux == []
    assert state.get_session("s") is None
    assert not (state.home() / "agents" / "s").exists()


def test_a_resume_whose_environment_fails_leaves_the_session_as_it_was(
    repo, fake_tmux, monkeypatch
):
    runtime.start_session(str(repo), "s", None)
    runtime.stop_session("s")
    before = len(fake_tmux)
    with monkeypatch.context() as m:
        m.setattr(agent_env, "resolve", _broken_env)
        with pytest.raises(runtime.LadoError, match="your shell failed"):
            runtime.start_session(str(repo), "s", "plan")
    assert len(fake_tmux) == before
    sess = state.get_session("s")
    assert sess.stopped_at and sess.permission_mode is None
    assert state.list_messages("s") == []  # no "session resumed" for a resume that never was


def test_a_spawn_whose_environment_fails_leaves_no_worker(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None)
    monkeypatch.setattr(agent_env, "resolve", _broken_env)
    with pytest.raises(runtime.LadoError, match="your shell failed"):
        runtime.spawn_worker("s", "a task")
    assert [c[0] for c in fake_tmux] == ["new_session"]
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert [e.agent for e in state.list_events("s")] == ["supervisor"]
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*") == ""


def _path_without_clis(monkeypatch, tmp_path):
    """The resolved environment's PATH has no agent CLI on it."""
    empty = tmp_path / "empty-bin"
    empty.mkdir(exist_ok=True)
    monkeypatch.setattr(agent_env, "resolve", lambda: {"PATH": str(empty)})


def test_a_start_whose_cli_is_not_on_the_agents_path_launches_nothing(
    repo, fake_tmux, monkeypatch, tmp_path
):
    _path_without_clis(monkeypatch, tmp_path)
    with pytest.raises(runtime.LadoError, match=r"`claude` is not on the agents' PATH") as error:
        runtime.start_session(str(repo), "s", None)
    assert "LADO_AGENT_ENV=inherit" in str(error.value)
    assert fake_tmux == []
    assert state.get_session("s") is None
    assert not (state.home() / "agents" / "s" / "supervisor").exists()


def test_a_spawn_whose_cli_is_not_on_the_agents_path_leaves_no_worker(
    repo, fake_tmux, monkeypatch, tmp_path
):
    runtime.start_session(str(repo), "s", None)
    _path_without_clis(monkeypatch, tmp_path)
    with pytest.raises(runtime.LadoError, match=r"`kilo` is not on the agents' PATH"):
        runtime.spawn_worker("s", "a task", provider="kilo")
    assert "new_window" not in [c[0] for c in fake_tmux]
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*") == ""
    assert not (state.home() / "agents" / "s" / "worker").exists()


def test_start_refuses_running_session(repo, fake_tmux):
    runtime.start_session(str(repo), None, None)
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(str(repo), None, None)


def test_start_on_a_running_session_restarts_a_dead_loop(repo, fake_tmux, loop_starts):
    from lado import loop

    runtime.start_session(str(repo), "s", None)
    assert loop_starts == ["s"]
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(str(repo), "s", None)
    assert loop_starts == ["s", "s"]  # its lock was free: the loop had died
    held = loop.take_lock("s")  # its loop runs
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(str(repo), "s", None)
    assert loop_starts == ["s", "s"]
    held.close()


def test_start_requires_git_repo(tmp_path, fake_tmux):
    with pytest.raises(runtime.LadoError, match="not inside a git repository"):
        runtime.start_session(str(tmp_path), None, None)


def _session_in(status, repo, fake_tmux):
    """A session "s" of `repo` that is running, stopped or whose tmux server is gone."""
    runtime.start_session(str(repo), "s", None)
    if status == runtime.SessionStatus.STOPPED:
        runtime.stop_session("s")
    elif status == runtime.SessionStatus.TMUX_GONE:
        fake_tmux.append(("kill_session", "s"))


def test_a_new_session_starts_with_resume_false(repo, fake_tmux):
    started = runtime.start_session(str(repo), "s", None, resume=False)
    assert not started.resumed
    assert state.get_session("s").repo == str(repo)


@pytest.mark.parametrize(
    "status",
    [runtime.SessionStatus.RUNNING, runtime.SessionStatus.STOPPED, runtime.SessionStatus.TMUX_GONE],
)
def test_resume_false_refuses_a_session_of_that_name(repo, fake_tmux, status):
    _session_in(status, repo, fake_tmux)
    events = len(state.list_events("s"))
    # A running session's loop is not started here: its status says so.
    shown = runtime.SessionStatus.LOOP_DOWN if status == runtime.SessionStatus.RUNNING else status
    with pytest.raises(runtime.SessionExists) as error:
        runtime.start_session(str(repo), "s", "plan", resume=False)
    assert (error.value.status, error.value.repo) == (shown, str(repo))
    assert f'session "s" exists already ({shown.value}, in {repo})' in str(error.value)
    assert len(state.list_events("s")) == events  # nothing was changed
    assert state.get_session("s").permission_mode is None


def test_resume_true_refuses_an_unknown_session(repo, fake_tmux):
    with pytest.raises(runtime.NoSuchSession, match='unknown session "s"'):
        runtime.start_session(str(repo), "s", None, resume=True)
    assert state.get_session("s") is None


@pytest.mark.parametrize("status", [runtime.SessionStatus.STOPPED, runtime.SessionStatus.TMUX_GONE])
def test_resume_true_resumes_a_session_not_running(repo, fake_tmux, status):
    _session_in(status, repo, fake_tmux)
    started = runtime.start_session(str(repo), "s", "plan", resume=True)
    assert started.resumed
    assert started.changes == ["permission mode: none -> plan"]


def test_resume_true_refuses_a_running_session(repo, fake_tmux):
    _session_in(runtime.SessionStatus.RUNNING, repo, fake_tmux)
    with pytest.raises(runtime.LadoError, match='session "s" is already running') as error:
        runtime.start_session(str(repo), "s", None, resume=True)
    assert not isinstance(error.value, runtime.SessionExists)


def test_check_repo_gives_the_root_of_a_repository_with_commits(repo):
    (repo / "sub").mkdir()
    assert runtime.check_repo(str(repo / "sub")) == str(repo)


def test_check_repo_refuses_a_folder_that_is_not_there(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(runtime.LadoError, match=f"^{missing} does not exist$"):
        runtime.check_repo(str(missing))


def test_check_repo_refuses_a_folder_outside_git(tmp_path):
    with pytest.raises(runtime.LadoError, match=f"^{tmp_path} is not inside a git repository$"):
        runtime.check_repo(str(tmp_path))


def _repo_without_commits(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_check_repo_refuses_a_repository_without_commits(tmp_path):
    empty = _repo_without_commits(tmp_path / "empty")
    expected = f"^{empty} has no commits yet: make a first commit, then start$"
    with pytest.raises(runtime.LadoError, match=expected):
        runtime.check_repo(str(empty))


def test_start_refuses_a_repository_without_commits(tmp_path, fake_tmux):
    empty = _repo_without_commits(tmp_path / "empty")
    with pytest.raises(runtime.LadoError, match="has no commits yet"):
        runtime.start_session(str(empty), None, None)
    assert state.list_sessions() == []


def test_spawn_worker_creates_worktree_and_passes_task(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    worker = runtime.spawn_worker("s", "fix the bug;")
    assert (worker.name, worker.branch) == ("worker", "lado/s/worker")
    assert (repo / ".lado/worktrees/s/worker/.git").exists()
    kind, _, window, cwd, cmd = fake_tmux[-1]
    assert (kind, window, cwd) == ("new_window", "worker", worker.cwd)
    assert cmd[-2] == "--"
    assert cmd[-1].startswith("fix the bug;") and "send_message" in cmd[-1]
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout == ""  # .lado/ is excluded
    assert runtime.spawn_worker("s", "another").name == "worker-2"
    assert runtime.spawn_worker("s", "named", name="w1").name == "w1"  # a given name wins
    assert runtime.spawn_worker("s", "third").name == "worker-3"


@pytest.mark.parametrize(
    ("role", "taken", "expected"),
    [
        ("developer", set(), "developer"),
        ("developer", {"developer", "developer-2"}, "developer-3"),
        ("Code Reviewer", set(), "code-reviewer"),  # made valid like a given name
        ("lado", set(), "lado-2"),
        ("human", set(), "human-2"),
        ("supervisor", set(), "supervisor-2"),
    ],
)
def test_default_worker_name_is_the_first_free_one_of_its_role(role, taken, expected):
    assert runtime._next_name(role, taken) == expected


def test_worker_is_told_a_text_report_is_lost(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    cmd = fake_tmux[-1][-1]
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert "The supervisor cannot see your screen" in prompt


def _prompt(cmd):
    return cmd[cmd.index("--append-system-prompt") + 1]


def test_agents_are_told_how_to_send_and_read_messages(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")
    for _, _, window, _, cmd in fake_tmux:
        prompt = _prompt(cmd)
        assert "one-line summary" in prompt, window
        assert "body" in prompt and "call read_messages" in prompt, window
        assert "last action of your turn" in prompt, window
        assert "being idle tells" in prompt, window
    supervisor = _prompt(fake_tmux[0][-1])
    assert "Do not relay worker or reviewer reports to the human" in supervisor
    assert "lado log" in supervisor


def test_the_supervisor_is_told_to_answer_the_human_where_they_asked(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    supervisor = " ".join(_prompt(fake_tmux[0][-1]).split())
    assert "The human talks to you in this window" not in supervisor
    assert 'answer a message "[from human] ..." with send_message(to="human")' in supervisor
    assert "ask with ask_human" in supervisor
    assert "answer text typed straight into your window in this window" in supervisor


def _mcp_ready(agent, instance=None):
    """What the agent's LADO MCP server records when Claude Code has listed its tools."""
    instance = instance or state.get_agent("s", agent).instance
    state.add_event("s", agent, state.MCP_READY, instance)


def _hook(event, agent, payload=None, mcp_ready=True):
    """Run a Claude Code hook of agent `agent` in session "s"; returns its decoded output.
    Before SessionStart its LADO MCP server is ready unless `mcp_ready` is false."""
    if event == "SessionStart" and mcp_ready:
        _mcp_ready(agent)
    claude = providers.get("claude")
    neutral = claude.parse_event(event, json.dumps(payload or {}))
    output = hooks.handle(claude, neutral, "s", agent) if neutral else None
    return json.loads(output) if output else None


def _session_with_worker(repo):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task", name="w1")


def test_message_to_idle_agent_is_pasted(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    assert runtime.send_message("s", "supervisor", "w1", "hi") == "sent"
    assert fake_tmux[-1] == ("send_text", "s", "w1", "[from supervisor] hi")
    assert state.get_agent("s", "w1").status == state.BUSY
    _hook("UserPromptSubmit", "w1", {"prompt": "[from supervisor] hi"})
    _hook("Stop", "w1")
    assert fake_tmux[-1][0] == "send_text"  # confirmed, so not delivered again


def test_an_agent_being_typed_into_never_looks_idle(repo, fake_tmux, monkeypatch):
    """Taken from the queue and the agent busy in one step: no one sees the agent idle
    with a message on its way in."""
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    status_once_taken = []
    take_pending = state.take_pending

    def spy(*args, **kwargs):
        taken = take_pending(*args, **kwargs)
        status_once_taken.append(state.get_agent("s", "w1").status)
        return taken

    monkeypatch.setattr(state, "take_pending", spy)
    assert runtime.send_message("s", "supervisor", "w1", "hi") == "sent"
    assert status_once_taken == [state.BUSY]


DELAYS = (15, 30, 60)


def _typed(fake_tmux, window="supervisor"):
    """What was typed into the window, one text per paste."""
    return [c[3] for c in fake_tmux if c[0] == "send_text" and c[2] == window]


def _swallowed_report(repo, fake_tmux):
    """w1's report typed into the idle supervisor, and swallowed by a dialog: no hook runs.
    Returns when it was typed."""
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", "report")
    return state.list_messages("s")[-1].sent_at


def test_a_swallowed_message_is_typed_again_after_each_delay(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    runtime.sweep("s", now=sent + 14, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]
    for at in (15, 15 + 30, 15 + 30 + 60):
        runtime.sweep("s", now=sent + at - 1, delays=DELAYS)
        runtime.sweep("s", now=sent + at, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"] * 4
    [message] = state.list_messages("s")
    assert (message.state, message.attempts) == (state.SENT, 4)
    assert state.get_agent("s", "supervisor").status == state.BUSY


def test_a_message_is_not_typed_again_after_a_hook_of_its_agent(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    _hook("UserPromptSubmit", "supervisor", {"prompt": "the human typed this"})
    runtime.sweep("s", now=sent + 1000, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]
    assert state.list_messages("s")[0].state == state.SENT


@pytest.mark.parametrize("status", [state.WAITING, state.STARTING, state.STOPPED])
def test_nothing_is_typed_again_into_an_agent_not_busy(repo, fake_tmux, status):
    sent = _swallowed_report(repo, fake_tmux)
    state.set_status("s", "supervisor", status)
    runtime.sweep("s", now=sent + 15, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]


def test_sweeps_at_once_type_a_message_again_only_once(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    errors = []

    def sweep():
        try:
            runtime.sweep("s", now=sent + 15)
        except Exception as exc:
            errors.append(exc)

    sweeps = [threading.Thread(target=sweep) for _ in range(8)]
    for t in sweeps:
        t.start()
    for t in sweeps:
        t.join()
    assert errors == []
    assert _typed(fake_tmux) == ["[from w1] report"] * 2
    assert state.list_messages("s")[0].attempts == 2


def _mismatched_report(repo, fake_tmux):
    """w1's report typed into the idle supervisor, which then ran a prompt that does not
    contain it and ended its turn at once."""
    sent = _swallowed_report(repo, fake_tmux)
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    assert _hook("Stop", "supervisor") is None
    return sent


def test_a_hook_soon_after_typing_does_not_type_again(repo, fake_tmux):
    _mismatched_report(repo, fake_tmux)
    assert _typed(fake_tmux) == ["[from w1] report"]
    assert state.list_messages("s")[0].state == state.SENT


def test_a_message_not_confirmed_by_the_next_prompt_is_typed_again(repo, fake_tmux):
    sent = _mismatched_report(repo, fake_tmux)
    runtime.sweep("s", now=sent + 14, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]
    runtime.sweep("s", now=sent + 15, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"] * 2
    [message] = state.list_messages("s")
    assert (message.state, message.attempts) == (state.SENT, 2)
    assert state.get_agent("s", "supervisor").status == state.BUSY


def test_a_message_never_confirmed_is_typed_once_per_attempt_and_fails(repo, fake_tmux):
    _mismatched_report(repo, fake_tmux)
    for delay in DELAYS + DELAYS[-1:]:
        message = state.list_messages("s")[0]
        runtime.sweep("s", now=message.sent_at + delay, delays=DELAYS)
        _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
        assert _hook("Stop", "supervisor") is None
    assert _typed(fake_tmux) == ["[from w1] report"] * (1 + len(DELAYS))
    assert state.list_messages("s")[0].state == state.FAILED
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go on"})
    _hook("Stop", "supervisor")
    assert len(_typed(fake_tmux)) == 1 + len(DELAYS)


def test_a_turn_end_after_the_delay_types_the_message_again(repo, fake_tmux, monkeypatch):
    _swallowed_report(repo, fake_tmux)
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    monkeypatch.setattr(runtime, "RETRY_DELAYS", (0, 0, 0))
    assert _hook("Stop", "supervisor") is None
    assert _typed(fake_tmux) == ["[from w1] report"] * 2
    assert state.list_messages("s")[0].attempts == 2


def test_the_first_hook_after_a_swallowed_failure_delivers_it_again(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    _retry_until_failed(sent)
    # The human answered the dialog and typed a line.
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go on"})
    [report, _] = state.list_messages("s")
    assert (report.state, report.attempts) == (state.PENDING, 0)
    assert _hook("Stop", "supervisor") == {"decision": "block", "reason": "[from w1] report"}
    assert state.list_messages("s")[0].state == state.DELIVERED


def test_a_new_message_waits_while_one_typed_is_unconfirmed(repo, fake_tmux):
    _mismatched_report(repo, fake_tmux)  # the supervisor is idle
    assert runtime.send_message("s", "w1", "supervisor", "ping").startswith("queued")
    assert _typed(fake_tmux) == ["[from w1] report"]


def test_a_new_message_brings_a_swallowed_one_again_after_the_delay(repo, fake_tmux, monkeypatch):
    _swallowed_report(repo, fake_tmux)
    assert runtime.send_message("s", "w1", "supervisor", "ping").startswith("queued")
    monkeypatch.setattr(runtime, "RETRY_DELAYS", (0, 0, 0))
    runtime.send_message("s", "w1", "supervisor", "pong")
    assert _typed(fake_tmux)[1:] == ["[from w1] report\n[from w1] ping\n[from w1] pong"]
    assert [m.attempts for m in state.list_messages("s")] == [2, 1, 1]


def _sweeps_that_typed_into_a_waiting_agent(fake_tmux, sent):
    """Sweep every 15 s for 400 s; returns the times of the sweeps that left the supervisor
    waiting and typed into it."""
    wrong = []
    for at in range(15, 400, 15):
        typed = len(_typed(fake_tmux))
        runtime.sweep("s", now=sent + at, delays=DELAYS)
        waiting = state.get_agent("s", "supervisor").status == state.WAITING
        if waiting and len(_typed(fake_tmux)) > typed:
            wrong.append(at)
    return wrong


def test_a_failure_types_nothing_more_with_a_swallowed_message(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    runtime.send_message("s", "w1", "supervisor", "ping")  # queued behind the report
    assert _sweeps_that_typed_into_a_waiting_agent(fake_tmux, sent) == []
    assert state.list_messages("s")[0].state == state.FAILED


def test_a_failure_types_nothing_more_with_an_unconfirmed_message(repo, fake_tmux):
    sent = _mismatched_report(repo, fake_tmux)
    runtime.send_message("s", "w1", "supervisor", "ping")  # queued behind the report
    runtime.sweep("s", now=sent + 15, delays=DELAYS)  # both typed: report 2nd, ping 1st time
    with state.connect() as db:  # the report is on its last attempt, the ping is not
        db.execute("UPDATE messages SET attempts = 4 WHERE summary = 'report'")
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    _hook("Stop", "supervisor")
    typed = len(_typed(fake_tmux))
    runtime.sweep("s", now=state.list_messages("s")[0].sent_at + 60, delays=DELAYS)
    assert state.get_agent("s", "supervisor").status == state.WAITING
    assert len(_typed(fake_tmux)) == typed
    assert [m.state for m in state.list_messages("s")[:2]] == [state.FAILED, state.PENDING]


def test_a_message_typed_with_a_failed_one_fails_with_it(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    runtime.send_message("s", "w1", "supervisor", "ping")  # typed with the report from now on
    at = _retry_until_failed(sent)
    report, ping = state.list_messages("s")[:2]
    assert (report.state, ping.state) == (state.FAILED, state.FAILED)
    runtime.sweep("s", now=at + 1000, delays=DELAYS)  # the session loop sweeps on
    assert runtime.waiting_reasons("s") == {
        "supervisor": "did not take 2 messages: answer the dialog in its window "
        "or type any line there"
    }
    notices = [m.summary for m in state.list_messages("s") if m.sender == state.LADO]
    assert notices == [
        f"message #{report.id} to supervisor not delivered: report",
        f"message #{ping.id} to supervisor not delivered: ping",
    ]
    # The human answers the dialog: both go to the supervisor again.
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go on"})
    assert _hook("Stop", "supervisor") == {
        "decision": "block",
        "reason": "[from w1] report\n[from w1] ping",
    }


def test_nothing_is_typed_into_an_agent_waiting_after_a_failure(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    _retry_until_failed(sent)
    assert state.get_agent("s", "supervisor").status == state.WAITING
    typed = len(_typed(fake_tmux))
    assert runtime.send_message("s", "w1", "supervisor", "ping").startswith("queued")
    assert len(_typed(fake_tmux)) == typed


def test_an_agent_waiting_after_swallowed_messages_says_what_to_do(repo, fake_tmux):
    _retry_until_failed(_swallowed_report(repo, fake_tmux))
    assert runtime.waiting_reasons("s") == {
        "supervisor": "did not take 1 message: answer the dialog in its window "
        "or type any line there"
    }
    assert runtime.waiting_reason("s", "supervisor") == runtime.waiting_reasons("s")["supervisor"]
    assert runtime.waiting_reason("s", "w1") is None  # not waiting
    assert runtime.waiting_reason("s", "nobody") is None


def test_an_agent_waiting_after_unconfirmed_messages_says_so(repo, fake_tmux):
    _mismatched_report(repo, fake_tmux)
    no_delays = (0, 0, 0)  # in real time: the hooks below come after the failure
    for _ in no_delays:
        runtime.sweep("s", delays=no_delays)
        _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
        _hook("Stop", "supervisor")
    runtime.sweep("s", delays=no_delays)
    assert state.list_messages("s")[0].state == state.FAILED
    assert runtime.waiting_reasons("s") == {
        "supervisor": "did not confirm 1 message (the text typed did not match)"
    }
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go on"})
    assert runtime.waiting_reasons("s") == {}  # busy again
    # Later it waits for a permission: the old failure is not why.
    _hook("Notification", "supervisor", {"notification_type": "permission_prompt"})
    assert state.get_agent("s", "supervisor").status == state.WAITING
    assert runtime.waiting_reasons("s") == {}
    assert runtime.waiting_reason("s", "supervisor") is None


def test_stop_drops_failed_messages(repo, fake_tmux):
    _retry_until_failed(_swallowed_report(repo, fake_tmux))
    assert runtime.stop_session("s").dropped == 2  # the report and the notice to w1
    assert [m.state for m in state.list_messages("s")] == [state.DROPPED] * 2


def test_finish_drops_the_failed_messages_of_the_worker(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    runtime.send_message("s", "supervisor", "w1", "task")
    _retry_until_failed(state.list_messages("s")[0].sent_at)
    assert runtime.finish_worker("s", "w1", discard=True).dropped == 1
    assert state.list_messages("s")[0].state == state.DROPPED


def _retry_until_failed(sent, start=0):
    """Sweep at the end of each delay, from the `start`-th one on, until the message fails."""
    at = sent
    for delay in DELAYS[start:] + DELAYS[-1:]:
        at += delay
        runtime.sweep("s", now=at, delays=DELAYS)
    return at


def test_a_message_never_taken_fails_after_the_last_delay(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    at = _retry_until_failed(sent)
    assert len(_typed(fake_tmux)) == 1 + len(DELAYS)
    report = state.list_messages("s")[0]
    assert report.state == state.FAILED
    assert state.get_agent("s", "supervisor").status == state.WAITING
    runtime.sweep("s", now=at + 1000, delays=DELAYS)
    assert len(_typed(fake_tmux)) == 1 + len(DELAYS)
    # Its sender hears of it, in one line from LADO.
    notice = state.list_messages("s")[-1]
    assert (notice.sender, notice.recipient, notice.body) == ("lado", "w1", "")
    assert notice.summary == f"message #{report.id} to supervisor not delivered: report"


def test_a_failed_message_from_lado_is_reported_to_the_supervisor(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    runtime.post("s", "lado", "w1", "flow x: step y", "the step")
    step = state.list_messages("s")[-1]
    _retry_until_failed(step.sent_at)
    notice = state.list_messages("s")[-1]
    assert (notice.sender, notice.recipient) == ("lado", "supervisor")
    assert notice.summary == f"message #{step.id} to w1 not delivered: flow x: step y"


def test_a_failed_notice_is_not_reported(repo, fake_tmux):
    sent = _swallowed_report(repo, fake_tmux)
    state.set_status("s", "w1", state.IDLE)
    _retry_until_failed(sent)
    # w1 swallows the notice too.
    _retry_until_failed(state.list_messages("s")[-1].sent_at)
    assert [(m.sender, m.recipient, m.state) for m in state.list_messages("s")] == [
        ("w1", "supervisor", state.FAILED),
        ("lado", "w1", state.FAILED),
    ]


def test_message_to_busy_agent_arrives_via_stop_hook(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    assert runtime.send_message("s", "w1", "supervisor", "done").startswith("queued")
    assert runtime.send_message("s", "w1", "supervisor", "branch lado/s/w1").startswith("queued")
    out = _hook("Stop", "supervisor")
    assert out == {
        "decision": "block",
        "reason": "[from w1] done\n[from w1] branch lado/s/w1",
    }
    assert state.get_agent("s", "supervisor").status == state.BUSY
    assert _hook("Stop", "supervisor") is None
    assert state.get_agent("s", "supervisor").status == state.IDLE


def test_only_the_summary_is_typed_and_the_body_waits(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    body = "Status: DONE\nFiles: a.py\nChecks: make check green"
    assert runtime.send_message("s", "w1", "supervisor", "DONE: tests pass", body) == "sent"
    [message] = state.list_messages("s")
    line = f"[from w1] DONE: tests pass (#{message.id}, 3 lines: call read_messages)"
    assert fake_tmux[-1] == ("send_text", "s", "supervisor", line)
    assert (message.summary, message.body) == ("DONE: tests pass", body)
    _hook("UserPromptSubmit", "supervisor", {"prompt": line})
    assert state.list_messages("s")[0].state == state.DELIVERED


def test_summary_is_stripped_so_a_trimmed_prompt_confirms_it(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", " done \t")
    assert fake_tmux[-1][3] == "[from w1] done"
    _hook("UserPromptSubmit", "supervisor", {"prompt": "[from w1] done"})
    assert state.list_messages("s")[0].state == state.DELIVERED


def test_stop_hook_carries_one_short_line_per_message(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "DONE: added x", "line one\nline two")
    runtime.send_message("s", "w1", "supervisor", "one more thing", "a single line")
    first, second = state.list_messages("s")
    out = _hook("Stop", "supervisor")
    assert out["reason"] == (
        f"[from w1] DONE: added x (#{first.id}, 2 lines: call read_messages)\n"
        f"[from w1] one more thing (#{second.id}, 1 line: call read_messages)"
    )


def test_message_errors(repo, fake_tmux):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match="running agents: supervisor, w1"):
        runtime.send_message("s", "w1", "nobody", "hi")
    with pytest.raises(runtime.LadoError, match="write the details to a file"):
        runtime.send_message("s", "w1", "supervisor", "done", "x" * 9000)


@pytest.mark.parametrize(
    ("summary", "reason"),
    [
        ("", "summary is empty"),
        ("  ", "summary is empty"),
        ("done\nall tests pass", "summary must be one line; put the details in body"),
        ("done\tall", "summary must be one line without control characters"),
        ("done\x1b[31m", "summary must be one line without control characters"),
        ("done all", "summary must be one line"),
        ("x" * 201, "summary is 201 characters, the limit is 200; put the details in body"),
    ],
)
def test_summary_must_be_one_short_line(repo, fake_tmux, summary, reason):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match=re.escape(reason)):
        runtime.send_message("s", "w1", "supervisor", summary, "body")
    assert state.list_messages("s") == []


def test_status_hooks(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("SessionStart", "supervisor")
    _hook("SessionStart", "w1")
    assert state.get_agent("s", "supervisor").status == state.IDLE  # no task yet
    assert state.get_agent("s", "w1").status == state.BUSY  # started with a task
    _hook("Notification", "w1", {"notification_type": "permission_prompt"})
    assert state.get_agent("s", "w1").status == state.WAITING
    _hook("Notification", "w1", {"notification_type": "idle_prompt"})
    assert state.get_agent("s", "w1").status == state.WAITING
    _hook("SessionEnd", "w1")
    assert state.get_agent("s", "w1").status == state.STOPPED


def test_session_start_waits_until_the_lado_mcp_server_listed_its_tools(repo, fake_tmux):
    """Claude Code starts the first turn after its SessionStart hooks, but not after its MCP
    servers: tools listed later are deferred behind tool search."""
    _session_with_worker(repo)
    _mcp_ready("w1", instance="an-earlier-launch")
    started = time.monotonic()
    threading.Timer(0.2, _mcp_ready, ["w1"]).start()
    _hook("SessionStart", "w1", mcp_ready=False)
    assert 0.2 <= time.monotonic() - started < hooks.MCP_READY_TIMEOUT
    assert state.get_agent("s", "w1").status == state.BUSY


def test_session_start_goes_on_without_the_lado_mcp_server_after_a_while(
    repo, fake_tmux, lado_home, monkeypatch
):
    _session_with_worker(repo)
    monkeypatch.setattr(hooks, "MCP_READY_TIMEOUT", 0.1)
    started = time.monotonic()
    _hook("SessionStart", "w1", mcp_ready=False)
    assert time.monotonic() - started >= 0.1
    assert state.get_agent("s", "w1").status == state.BUSY
    assert "w1: LADO's MCP server listed no tools" in (lado_home / "hooks.log").read_text()


def test_session_start_waits_only_where_the_provider_needs_it(repo, fake_tmux):
    _session_with_worker(repo)
    kilo_cli = providers.get("kilo")
    assert not kilo_cli.capabilities.hold_first_turn  # its session start is the plugin's init
    started = time.monotonic()
    hooks.handle(kilo_cli, providers.Event(providers.SESSION_START), "s", "w1")
    # Far below the wait, but not tight: the tests run in parallel on a busy machine.
    assert time.monotonic() - started < hooks.MCP_READY_TIMEOUT / 4
    assert state.get_agent("s", "w1").status == state.BUSY


@pytest.mark.parametrize("command", ["clear", "resume"])
def test_conversation_switch_keeps_agent_running(repo, fake_tmux, command):
    _session_with_worker(repo)
    _hook("SessionStart", "supervisor", {"source": "startup"})
    _hook("SessionEnd", "supervisor", {"reason": command})
    # Not ready (the next conversation is loading): messages wait instead of being typed.
    assert state.get_agent("s", "supervisor").status == state.STARTING
    assert runtime.send_message("s", "w1", "supervisor", "report").startswith("queued")
    assert fake_tmux[-1][0] != "send_text"
    _hook("SessionStart", "supervisor", {"source": command})
    assert fake_tmux[-1] == ("send_text", "s", "supervisor", "[from w1] report")
    assert state.get_agent("s", "supervisor").status == state.BUSY
    _hook("UserPromptSubmit", "supervisor", {"prompt": "[from w1] report"})
    _hook("Stop", "supervisor")
    assert state.get_agent("s", "supervisor").status == state.IDLE
    assert [m.state for m in state.list_messages("s")] == [state.DELIVERED]


def test_conversation_switch_ends_idle_with_nothing_queued(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("SessionStart", "w1", {"source": "startup"})  # busy with its task
    _hook("Stop", "w1")
    _hook("SessionEnd", "w1", {"reason": "resume"})
    _hook("SessionStart", "w1", {"source": "resume"})
    assert state.get_agent("s", "w1").status == state.IDLE  # not busy with its task again


def test_the_resume_picker_leaves_the_agent_idle_until_a_conversation_is_chosen(repo, fake_tmux):
    """What Claude Code 2.1.287 sends, captured with a probe (2026-10-02): typing /resume
    and opening its picker fire no hook, nor does cancelling it with Esc. Choosing a
    conversation fires SessionEnd(resume) and, a second later, SessionStart(resume)."""
    _session_with_worker(repo)
    _hook("SessionStart", "w1", {"source": "startup", "model": "claude-haiku-4-5-20251001"})
    _hook("UserPromptSubmit", "w1", {"prompt": "Reply with the single word hi"})
    _hook("Stop", "w1")
    # /resume, picker open, Esc: no hook. The CLI is ready again, and so is the agent.
    assert state.get_agent("s", "w1").status == state.IDLE
    assert runtime.send_message("s", "supervisor", "w1", "next") == "sent"
    _hook("UserPromptSubmit", "w1", {"prompt": "[from supervisor] next"})
    _hook("Stop", "w1")
    # /resume again, a conversation chosen:
    _hook("SessionEnd", "w1", {"reason": "resume", "prompt_id": "e0d81dbc"})
    assert state.get_agent("s", "w1").status == state.STARTING
    payload = {"source": "resume", "prompt_id": "e0d81dbc", "seconds_since_last_response": 965}
    _hook("SessionStart", "w1", payload)
    assert state.get_agent("s", "w1").status == state.IDLE


def test_real_exit_stops_agent(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("SessionStart", "w1", {"source": "startup"})
    _hook("SessionEnd", "w1", {"reason": "prompt_input_exit"})
    assert state.get_agent("s", "w1").status == state.STOPPED
    with pytest.raises(runtime.LadoError, match='no running agent "w1"'):
        runtime.send_message("s", "supervisor", "w1", "hi")


def test_hook_errors_are_logged_not_raised(repo, fake_tmux, lado_home, monkeypatch):
    runtime.start_session(str(repo), "s", None)
    instance = state.get_agent("s", "supervisor").instance
    monkeypatch.setattr("sys.stdin.read", lambda: "not json")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    assert "JSONDecodeError" in (lado_home / "hooks.log").read_text()


def test_hooks_from_an_earlier_launch_are_ignored(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None)
    old = state.get_agent("s", "supervisor").instance
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    hooks.main("SessionEnd", "s", "supervisor", old)  # the killed process exits late
    assert state.get_agent("s", "supervisor").status == state.STARTING


def test_stop_session_keeps_worktrees_and_history(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.send_message("s", "supervisor", "w1", "hi")  # w1 is starting: queued
    stopped = runtime.stop_session("s")
    assert [w.name for w in stopped.workers] == ["w1"]
    assert stopped.dropped == 1
    assert state.get_session("s").stopped_at
    assert state.list_agents("s") == []
    assert [m.state for m in state.list_messages("s")] == [state.DROPPED]
    assert ("kill_session", "s") in fake_tmux
    assert Path(repo, ".lado/worktrees/s/w1/.git").exists()
    with pytest.raises(runtime.LadoError, match='session "s" is stopped already'):
        runtime.stop_session("s")
    with pytest.raises(runtime.LadoError, match='unknown session "nope"'):
        runtime.stop_session("nope")


def _launched_with(cmd):
    """The first message a fake-tmux claude command line was started with."""
    return cmd[-1] if cmd[-2] == "--" else None


def test_start_resumes_a_stopped_session(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.spawn_worker("s", "task")  # "worker"
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None)
    assert (started.resumed, started.changes, started.problems) == (True, [], [])
    assert started.session.stopped_at is None
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert _launched_with(fake_tmux[-1][-1]) == "[from lado] session resumed: 0 open runs"
    assert [(m.sender, m.recipient, m.state) for m in state.list_messages("s")][-1] == (
        "lado",
        "supervisor",
        state.DELIVERED,
    )
    kinds = [e.kind for e in state.list_events("s")]
    assert kinds[-2:] == [state.SESSION_RESUME, state.SPAWNED]
    # The branch of "worker" is still there: the next worker gets another name.
    assert runtime.spawn_worker("s", "task").name == "worker-2"


def test_start_resumes_a_session_whose_tmux_server_is_gone(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.send_message("s", "supervisor", "w1", "hi")
    fake_tmux.append(("kill_session", "s"))  # the tmux server died, no lado stop
    started = runtime.start_session(str(repo), "s", None)
    assert started.resumed
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert state.list_messages("s")[0].state == state.DROPPED
    assert state.SESSION_STOP in [e.kind for e in state.list_events("s")]


def _fail(*args, **kwargs):
    raise tmux.TmuxError("command too long")


@pytest.mark.parametrize("failing", ["tmux", "provider"])
def test_a_failed_spawn_leaves_no_ghost_worker(repo, fake_tmux, monkeypatch, failing):
    runtime.start_session(str(repo), "s", None)
    monkeypatch.setattr(runtime, "FIRST_INPUT_LIMIT", 10)  # the task comes as a message
    with monkeypatch.context() as m:
        if failing == "tmux":
            m.setattr(tmux, "new_window", _fail)
        else:
            m.setattr(providers.get("claude"), "launch_command", _fail)
        with pytest.raises(tmux.TmuxError, match="command too long"):
            runtime.spawn_worker("s", "a task that is long")
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert [m.state for m in state.list_messages("s")] == [state.DROPPED]
    assert not (state.home() / "agents" / "s" / "worker").exists()
    assert runtime.session_worktrees(str(repo), "s") == {}
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*") == ""
    last = state.list_events("s")[-1]
    assert (last.agent, last.kind) == ("worker", state.FINISHED)
    assert last.detail.startswith("not started: command too long")
    assert runtime.spawn_worker("s", "a task that is long").name == "worker"


def test_a_failed_start_leaves_no_session(repo, fake_tmux, monkeypatch):
    monkeypatch.setattr(tmux, "new_session", _fail)
    with pytest.raises(tmux.TmuxError, match="command too long"):
        runtime.start_session(str(repo), "s", None)
    assert state.get_session("s") is None
    assert not (state.home() / "agents" / "s" / "supervisor").exists()


def test_a_failed_resume_leaves_the_session_stopped(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None)
    runtime.stop_session("s")
    with monkeypatch.context() as m:
        m.setattr(tmux, "new_session", _fail)
        with pytest.raises(tmux.TmuxError, match="command too long"):
            runtime.start_session(str(repo), "s", None)
    assert state.get_session("s").stopped_at
    assert state.list_agents("s") == []
    # LADO's first messages never reached a supervisor.
    [resumed] = state.list_messages("s")
    assert (resumed.summary, resumed.state) == ("session resumed: 0 open runs", state.DROPPED)
    assert not (state.home() / "agents" / "s" / "supervisor").exists()
    assert runtime.start_session(str(repo), "s", None).resumed
    assert state.get_agent("s", "supervisor") is not None


@pytest.mark.parametrize("failing", ["tmux", "runs"])
def test_a_failed_resume_keeps_the_settings_it_had(repo, fake_tmux, monkeypatch, team_kit, failing):
    runtime.start_session(str(repo), "s", None)
    runtime.stop_session("s")
    with monkeypatch.context() as m:
        if failing == "tmux":
            m.setattr(tmux, "new_session", _fail)
        else:
            m.setattr(runs, "resume", _fail)
        with pytest.raises(tmux.TmuxError, match="command too long"):
            runtime.start_session(str(repo), "s", "plan", "kilo", ["team"], ["skill:style"])
    sess = state.get_session("s")
    assert (sess.provider, sess.kits, sess.without, sess.permission_mode) == (
        "claude",
        ["default"],
        [],
        None,
    )
    assert sess.stopped_at
    # The log says the settings went back, not only what the resume changed.
    stop = state.list_events("s")[-1]
    assert stop.kind == state.SESSION_STOP
    assert "settings put back: provider: kilo -> claude" in stop.detail
    started = runtime.start_session(str(repo), "s", None, "kilo")
    assert started.changes == ["provider: claude -> kilo"]
    assert state.get_session("s").provider == "kilo"


@pytest.mark.parametrize("resumed", [False, True])
def test_a_start_that_loses_the_race_leaves_the_running_session_alone(
    repo, fake_tmux, monkeypatch, resumed
):
    """Two `lado start` of one name at once: both see the same stored session, the other
    one starts first."""
    if resumed:
        runtime.start_session(str(repo), "s", None)
        runtime.stop_session("s")
    seen = state.get_session("s")
    runtime.start_session(str(repo), "s", None)  # the other `lado start`
    with monkeypatch.context() as m:
        m.setattr(state, "get_session", lambda name: seen)
        with pytest.raises(runtime.LadoError, match='session "s" is already running'):
            runtime.start_session(str(repo), "s", None, "kilo")
    sess = state.get_session("s")
    assert (sess.provider, sess.stopped_at) == ("claude", None)
    assert state.get_agent("s", "supervisor") is not None
    assert (state.home() / "agents" / "s" / "supervisor").exists()


def test_resume_refuses_another_repo(repo, tmp_path, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    runtime.stop_session("s")
    other = agent_helpers.init_repo(tmp_path / "other")
    with pytest.raises(runtime.LadoError, match=f'session "s" was started in {repo}') as error:
        runtime.start_session(str(other), "s", None)
    assert "lado forget s" in str(error.value) and "--name" in str(error.value)
    assert state.get_session("s").stopped_at


def test_resume_replaces_the_settings_given_and_keeps_the_others(repo, fake_tmux, team_kit):
    runtime.start_session(str(repo), "s", "plan", kit_names=["team"])
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None, "kilo", without=["skill:style"])
    assert started.changes == ["provider: claude -> kilo", "without: none -> skill:style"]
    sess = state.get_session("s")
    assert (sess.provider, sess.kits, sess.without, sess.permission_mode) == (
        "kilo",
        ["team"],
        ["skill:style"],
        "plan",
    )
    assert (
        state.list_events("s")[-2].detail
        == "provider: claude -> kilo; without: none -> skill:style"
    )
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None, kit_names=["default", "team"])
    assert started.changes == ["kits: team -> default, team"]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def team_kit(repo):
    """A project kit on top of the default kit: a reviewer role, two skills, an MCP server."""
    kit = repo / ".lado" / "kits" / "team"
    _write(kit / "kit.yaml", "name: team\ninclude: [default]\n")
    _write(
        kit / "agents" / "reviewer.md",
        "---\nname: reviewer\ndescription: reviews branches\nskills: [checklist]\n"
        "mcp:\n  db:\n    command: ['${KIT_DIR}/db.sh']\n    env: {TOKEN: '${DB_TOKEN}'}\n"
        "---\nYou review. Notes are in ${KIT_DIR}/notes.\n",
    )
    for skill in ("checklist", "style"):
        _write(kit / "skills" / skill / "SKILL.md", f"---\nname: {skill}\ndescription: d\n---\n")
    return kit


def test_start_with_kits_stores_them_and_appends_lado_instructions(repo, fake_tmux, team_kit):
    sess = runtime.start_session(
        str(repo), "s", None, kit_names=["team"], without=["skill:style"]
    ).session
    assert (sess.kits, sess.without) == (["team"], ["skill:style"])
    stored = state.get_session("s")
    assert (stored.kits, stored.without) == (["team"], ["skill:style"])
    assert state.get_agent("s", "supervisor").role == "supervisor"
    cmd = fake_tmux[0][-1]
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert prompt.startswith("You are the supervisor.")  # the role from the default kit
    assert 'agent "supervisor" in LADO session "s"' in prompt
    assert '`role` picks the kind of worker (default: "worker")' in prompt
    assert "  - reviewer: reviews branches" in prompt
    # The supervisor lists no skills, so it gets all of them except the one switched off.
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]


def test_spawn_worker_with_role_and_without(repo, fake_tmux, team_kit, monkeypatch):
    runtime.start_session(str(repo), "s", None, kit_names=["team"])
    monkeypatch.setenv("DB_TOKEN", "t0k")
    worker = runtime.spawn_worker("s", "review it", role="reviewer")
    assert worker.role == "reviewer"
    cmd = fake_tmux[-1][-1]
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert prompt.startswith(f"You review. Notes are in {team_kit.resolve()}/notes.")
    assert 'You are worker "reviewer" in LADO session "s"' in prompt
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]
    mcp = json.loads(open(cmd[cmd.index("--mcp-config") + 1]).read())["mcpServers"]
    assert mcp["db"]["command"] == f"{team_kit.resolve()}/db.sh"
    assert mcp["db"]["env"] == {"TOKEN": "t0k"}
    # The default role gets all skills; this one without the MCP server it does not have.
    runtime.spawn_worker("s", "t", without=["skill:style"])
    cmd = fake_tmux[-1][-1]
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]
    runtime.spawn_worker("s", "t", role="reviewer", without=["mcp:db"])
    mcp = json.loads(open(fake_tmux[-1][-1][fake_tmux[-1][-1].index("--mcp-config") + 1]).read())
    assert list(mcp["mcpServers"]) == ["lado"]


def test_kit_mcp_variables_come_from_the_agents_environment(repo, fake_tmux, team_kit, monkeypatch):
    runtime.start_session(str(repo), "s", None, kit_names=["team"])
    monkeypatch.delenv("DB_TOKEN", raising=False)  # set only by the user's shell
    path = os.environ["PATH"]
    monkeypatch.setattr(agent_env, "resolve", lambda: {"PATH": path, "DB_TOKEN": "from-shell"})
    runtime.spawn_worker("s", "review it", role="reviewer")
    cmd = fake_tmux[-1][-1]
    mcp = json.loads(open(cmd[cmd.index("--mcp-config") + 1]).read())["mcpServers"]
    assert mcp["db"]["env"] == {"TOKEN": "from-shell"}


def test_spawn_worker_errors_leave_nothing_behind(repo, fake_tmux, team_kit, monkeypatch):
    runtime.start_session(str(repo), "s", None, kit_names=["team"])
    monkeypatch.delenv("DB_TOKEN", raising=False)
    with pytest.raises(kits.KitError, match="environment variable DB_TOKEN is not set"):
        runtime.spawn_worker("s", "t", role="reviewer")
    with pytest.raises(kits.KitError, match='no worker role "boss"'):
        runtime.spawn_worker("s", "t", role="boss")
    with pytest.raises(kits.KitError, match="no such skill"):
        runtime.spawn_worker("s", "t", without=["skill:nope"])
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert not (repo / ".lado" / "worktrees").exists()


def test_start_errors_leave_no_session(repo, fake_tmux):
    with pytest.raises(kits.KitError, match='kit "nope" not found'):
        runtime.start_session(str(repo), "s", None, kit_names=["nope"])
    with pytest.raises(kits.KitError, match="no agent with `supervisor: true`"):
        runtime.start_session(str(repo), "s", None, without=["agent:supervisor"])
    assert state.get_session("s") is None and fake_tmux == []


class _NoSkills(providers.Provider):
    name = "noskills"
    title = "No Skills CLI"
    capabilities = providers.Capabilities(
        status_events=True, permission_event=False, deliver_on_turn_end=True, skills=False
    )

    def launch_command(self, agent, session, spec, first_message=None):
        return providers.Launch(["noskills"])

    def parse_event(self, native, payload):
        return None


def test_provider_without_skills_fails_loudly(repo, fake_tmux, team_kit, monkeypatch):
    monkeypatch.setitem(providers._PROVIDERS, "noskills", _NoSkills())
    with pytest.raises(runtime.LadoError, match="No Skills CLI cannot load skills.*checklist"):
        runtime.start_session(str(repo), "s", None, "noskills", kit_names=["team"])
    runtime.start_session(
        str(repo), "s", None, "noskills", ["team"], ["skill:style", "skill:checklist"]
    )
    assert agent_helpers.launched(fake_tmux[0])[1] == ["noskills"]


def test_git_exclude_keeps_project_kits_visible(repo, fake_tmux, team_kit):
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("# mine\n/.lado/\n")  # what LADO 0.3 wrote
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "t")
    assert exclude.read_text() == "# mine\n/.lado/worktrees/\n"
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "-uall"], capture_output=True, text=True
    )
    assert ".lado/kits/team/kit.yaml" in status.stdout
    assert "worktrees" not in status.stdout
    runtime.spawn_worker("s", "t")
    assert exclude.read_text() == "# mine\n/.lado/worktrees/\n"


def test_start_and_spawn_record_spawned_events(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    runtime.spawn_worker("s", "task", provider="claude")
    assert [(e.agent, e.kind, e.detail) for e in state.list_events("s")] == [
        ("supervisor", "spawned", "role supervisor, provider kilo"),
        ("worker", "spawned", "role worker, provider claude"),
    ]


def _commit(worktree, name="work.txt"):
    Path(worktree, name).write_text("done\n")
    runtime.git(worktree, "add", name)
    runtime.git(worktree, "commit", "-q", "-m", f"add {name}")


def _branches(repo):
    return runtime.git(str(repo), "branch", "--format=%(refname:short)").split()


def test_finish_worker_removes_a_merged_worker(repo, fake_tmux):
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    _commit(worker.cwd)
    runtime.git(str(repo), "merge", "-q", "--ff-only", worker.branch)
    finished = runtime.finish_worker("s", "w1").worker
    assert (finished.name, finished.branch, finished.cwd) == ("w1", "lado/s/w1", worker.cwd)
    assert ("kill_window", "s", "w1") in fake_tmux
    assert not Path(worker.cwd).exists()
    assert _branches(repo) == ["main"]
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    last = state.list_events("s")[-1]
    assert (last.agent, last.kind, last.detail) == ("w1", "finished", "merged")
    assert runtime.spawn_worker("s", "again", name="w1").branch == "lado/s/w1"


def test_a_finished_workers_name_is_the_default_again(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    worker = runtime.spawn_worker("s", "task")
    assert runtime.spawn_worker("s", "at the same time").name == "worker-2"
    runtime.finish_worker("s", worker.name)  # nothing to merge
    assert runtime.spawn_worker("s", "again").name == "worker"


def test_finish_worker_refuses_unknown_session_agent_and_supervisor(repo, fake_tmux):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match='unknown session "nope"'):
        runtime.finish_worker("nope", "w1")
    with pytest.raises(runtime.LadoError, match='no worker "w9"; workers: w1'):
        runtime.finish_worker("s", "w9")
    for discard in (False, True):
        with pytest.raises(runtime.LadoError, match="supervisor.*lado stop s"):
            runtime.finish_worker("s", "supervisor", discard=discard)
    assert len(state.list_agents("s")) == 2


def test_finish_worker_refuses_unmerged_or_dirty_work(repo, fake_tmux):
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    _commit(worker.cwd)
    with pytest.raises(runtime.LadoError, match="lado/s/w1 is not merged into main.*discard"):
        runtime.finish_worker("s", "w1")
    runtime.git(str(repo), "merge", "-q", "--ff-only", worker.branch)
    Path(worker.cwd, "untracked.txt").write_text("x")
    with pytest.raises(runtime.LadoError, match="(?s)uncommitted changes.*untracked.txt.*discard"):
        runtime.finish_worker("s", "w1")
    Path(worker.cwd, "untracked.txt").unlink()
    Path(worker.cwd, "work.txt").write_text("changed")
    with pytest.raises(runtime.LadoError, match="(?s)uncommitted changes.*work.txt"):
        runtime.finish_worker("s", "w1")
    assert not any(c[0] == "kill_window" for c in fake_tmux)
    assert Path(worker.cwd).exists() and "lado/s/w1" in _branches(repo)
    assert state.get_agent("s", "w1") is not None


def test_finish_worker_discard_throws_the_work_away(repo, fake_tmux):
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    _commit(worker.cwd)
    Path(worker.cwd, "untracked.txt").write_text("x")
    Path(worker.cwd, "work.txt").write_text("changed")
    runtime.finish_worker("s", "w1", discard=True)
    assert not Path(worker.cwd).exists()
    assert _branches(repo) == ["main"]
    assert state.get_agent("s", "w1") is None
    last = state.list_events("s")[-1]
    assert (last.agent, last.kind, last.detail) == ("w1", "finished", "discarded")


@pytest.mark.parametrize("discard", [False, True])
def test_finish_worker_keeps_the_window_when_git_fails(repo, fake_tmux, discard):
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    runtime.git(str(repo), "worktree", "lock", worker.cwd)  # `remove` refuses a locked one
    with pytest.raises(runtime.LadoError, match="locked"):
        runtime.finish_worker("s", "w1", discard=discard)
    assert not any(c[0] == "kill_window" for c in fake_tmux)
    assert state.get_agent("s", "w1") is not None
    runtime.git(str(repo), "worktree", "unlock", worker.cwd)
    runtime.finish_worker("s", "w1", discard=discard)
    assert ("kill_window", "s", "w1") in fake_tmux


def test_finish_worker_drops_its_undelivered_messages(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "w1")  # busy, so messages wait for its turn to end
    runtime.send_message("s", "supervisor", "w1", "old task")
    state.set_status("s", "w1", state.IDLE)
    runtime.send_message("s", "supervisor", "w1", "typed, never confirmed")
    finished = runtime.finish_worker("s", "w1", discard=True)
    assert finished.dropped == 2
    last = state.list_events("s")[-1]
    assert (last.kind, last.detail) == ("finished", "discarded; 2 messages dropped")
    runtime.spawn_worker("s", "new task", name="w1")
    monkeypatch.setattr(runtime, "RETRY_DELAYS", (0, 0, 0))
    assert _hook("Stop", "w1") is None  # nothing meant for the old w1
    assert fake_tmux[-1][0] != "send_text"
    assert [m.state for m in state.list_messages("s")] == [state.DROPPED, state.DROPPED]


def test_finish_worker_drops_the_bodies_it_never_read(repo, fake_tmux):
    _session_with_worker(repo)
    for summary, body in [("details inside", "the body"), ("no body", "")]:
        state.set_status("s", "w1", state.IDLE)
        runtime.send_message("s", "supervisor", "w1", summary, body)
        _hook("UserPromptSubmit", "w1", {"prompt": fake_tmux[-1][3]})
    assert [m.state for m in state.list_messages("s")] == [state.DELIVERED] * 2
    finished = runtime.finish_worker("s", "w1", discard=True)
    assert finished.dropped == 1
    runtime.spawn_worker("s", "new task", name="w1")
    assert state.read_messages("s", "w1") == []  # nothing meant for the old w1
    assert [m.state for m in state.list_messages("s")] == [state.DROPPED, state.DELIVERED]


def test_hooks_of_a_finished_worker_are_ignored(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    old = state.get_agent("s", "w1").instance
    runtime.finish_worker("s", "w1", discard=True)
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    assert hooks.main("Stop", "s", "w1", old) == 0
    assert state.get_agent("s", "w1") is None  # not recreated
    runtime.spawn_worker("s", "again", name="w1")
    assert hooks.main("SessionEnd", "s", "w1", old) == 0  # the killed process exits late
    assert state.get_agent("s", "w1").status == state.STARTING


def test_no_migration_under_a_running_session(repo, fake_tmux):
    runtime.start_session(str(repo), "old", None)
    runtime.start_session(str(repo), "other", None)
    runtime.start_session(str(repo), "gone", None)
    runtime.stop_session("gone")
    tmux.kill_session("other")  # its tmux server died without `lado stop`
    agent_helpers.previous_schema()
    with pytest.raises(runtime.LadoError) as refused:
        runtime.check_migration()
    message = str(refused.value)
    assert f"schema version {state.SCHEMA_VERSION - 1}" in message
    assert 'running sessions: "old"' in message
    assert "other" not in message and "gone" not in message
    assert "`lado stop old`" in message
    assert state.pending_migration() is not None  # nothing migrated


def test_migration_goes_ahead_with_no_session_running(repo, fake_tmux):
    runtime.start_session(str(repo), "old", None)
    runtime.stop_session("old")
    agent_helpers.previous_schema()
    runtime.check_migration()
    runtime.check_migration()  # nothing pending: nothing to check
    assert state.get_session("old").stopped_at
    assert state.pending_migration() is None


def test_session_status_tells_the_four_states(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    sess = state.get_session("s")
    assert runtime.session_status(sess) == runtime.SessionStatus.LOOP_DOWN
    held = loop.take_lock("s")  # its loop runs
    assert runtime.session_status(sess) == runtime.SessionStatus.RUNNING
    tmux.kill_session("s")
    assert runtime.session_status(sess) == runtime.SessionStatus.TMUX_GONE
    held.close()
    runtime.stop_session("s")
    assert runtime.session_status(state.get_session("s")) == runtime.SessionStatus.STOPPED


def test_a_message_to_the_human_is_delivered_at_once_into_no_window(repo, fake_tmux):
    _session_with_worker(repo)
    typed_before = len(fake_tmux)
    assert runtime.send_message("s", "supervisor", "human", "need a decision", "A or B?") == (
        "delivered: the human reads it in LADO's UI"
    )
    assert len(fake_tmux) == typed_before
    [message] = state.list_messages("s")
    assert (message.sender, message.recipient, message.state) == (
        "supervisor",
        "human",
        state.DELIVERED,
    )


def test_an_unknown_recipient_names_the_human_too(repo, fake_tmux):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match='running agents: supervisor, w1; or "human"'):
        runtime.send_message("s", "w1", "nobody", "hi")


@pytest.mark.parametrize("name", ["human", "lado", "Human"])
def test_a_worker_cannot_take_a_name_of_lado_or_the_human(repo, fake_tmux, name):
    runtime.start_session(str(repo), "s", None)
    with pytest.raises(runtime.LadoError, match=f'"{name.lower()}" is reserved'):
        runtime.spawn_worker("s", "task", name=name)
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert not (repo / ".lado/worktrees/s" / name.lower()).exists()


def test_messages_to_the_human_are_never_dropped(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.send_message("s", "w1", "human", "a question", "with a body")
    runtime.send_message("s", "supervisor", "human", "a milestone")
    runtime.sweep("s", now=time.time() + 1000, delays=DELAYS)
    assert runtime.finish_worker("s", "w1", discard=True).dropped == 0
    assert runtime.stop_session("s").dropped == 0
    assert [m.state for m in state.list_messages("s")] == [state.DELIVERED] * 2
    assert state.list_events("s")[-1].detail == "0 messages dropped"


def test_the_humans_text_reaches_the_supervisor_as_a_message(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    assert runtime.write_as_human("s", "  merge w1, please\t\n") == "sent"
    assert fake_tmux[-1] == ("send_text", "s", "supervisor", "[from human] merge w1, please")
    [message] = state.list_messages("s")
    assert (message.sender, message.recipient, message.body) == ("human", "supervisor", "")


@pytest.mark.parametrize(
    ("text", "summary", "body"),
    [
        ("look at\tthis\x1b[0m now", "look at this [0m now", ""),
        ("first line\nsecond line", "first line", "first line\nsecond line"),
        ("x" * 250, "x" * 199 + "…", "x" * 250),
    ],
)
def test_the_humans_text_is_split_into_a_summary_and_a_body(repo, fake_tmux, text, summary, body):
    _session_with_worker(repo)
    runtime.write_as_human("s", text, to="w1")
    [message] = state.list_messages("s")
    assert (message.recipient, message.summary, message.body) == ("w1", summary, body)


@pytest.mark.parametrize(
    ("text", "to", "reason"),
    [
        (" \n ", "supervisor", "the message is empty"),
        ("x" * 8001, "supervisor", "the message is 8001 characters, the limit is 8000"),
        ("hi", "nobody", 'no running agent "nobody"'),
        ("hi", "human", 'no running agent "human"'),
    ],
)
def test_the_humans_text_is_refused_with_a_reason(repo, fake_tmux, text, to, reason):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match=re.escape(reason)):
        runtime.write_as_human("s", text, to=to)
    assert state.list_messages("s") == []


def test_the_human_cannot_write_into_a_stopped_session(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.stop_session("s")
    with pytest.raises(runtime.LadoError, match='session "s" is stopped'):
        runtime.write_as_human("s", "hi")


def test_the_human_hears_of_their_message_that_failed(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    runtime.write_as_human("s", "are you there?")
    _retry_until_failed(state.list_messages("s")[0].sent_at)
    mine, notice = state.list_messages("s")
    assert mine.state == state.FAILED
    assert (notice.sender, notice.recipient, notice.state) == ("lado", "human", state.DELIVERED)
    assert notice.summary == f"message #{mine.id} to supervisor not delivered: are you there?"


def test_an_agent_asks_the_human_a_question(repo, fake_tmux):
    _session_with_worker(repo)
    typed_before = len(fake_tmux)
    result = runtime.ask_human("s", "w1", "Merge now?", "Tests pass.", ["yes", "later"], False)
    [question] = state.list_messages("s")
    assert result == (
        f"question #{question.id} asked; the human's answer or dismissal comes as a message "
        "from human"
    )
    assert len(fake_tmux) == typed_before
    assert (question.kind, question.sender, question.recipient, question.state) == (
        state.QUESTION,
        "w1",
        "human",
        state.DELIVERED,
    )
    assert (question.summary, question.body) == ("Merge now?", "Tests pass.")
    assert (question.choices, question.free_answer, question.question_state) == (
        ["yes", "later"],
        False,
        state.OPEN_QUESTION,
    )


def test_a_question_without_choices_takes_a_free_answer(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.ask_human("s", "w1", "Which port?")
    [question] = state.list_messages("s")
    assert (question.choices, question.free_answer) == (None, True)


@pytest.mark.parametrize(
    ("question", "choices", "free", "reason"),
    [
        ("", None, True, "question is empty"),
        ("a\nb", None, True, "question must be one line; put the details in details"),
        ("x" * 201, None, True, "question is 201 characters, the limit is 200"),
        ("ok?", [], False, "no choices and no free answer: the human could not answer"),
        ("ok?", list("abcdefg"), True, "7 choices, the limit is 6"),
        ("ok?", ["yes", "yes"], True, 'choice "yes" is given twice'),
        ("ok?", ["yes", " "], True, "a choice is empty"),
        ("ok?", ["a\nb"], True, "a choice must be one line"),
        ("ok?", ["x" * 161], True, "a choice is 161 characters, the limit is 160"),
    ],
)
def test_a_question_is_refused_with_a_reason(repo, fake_tmux, question, choices, free, reason):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match=re.escape(reason)):
        runtime.ask_human("s", "w1", question, None, choices, free)
    assert state.list_messages("s") == []


def _asked(repo, choices=("yes", "later"), free=True):
    """w1, idle, asked the human a question; returns it."""
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    runtime.ask_human("s", "w1", "Merge now?", None, list(choices) if choices else None, free)
    return state.list_messages("s")[-1]


@pytest.mark.parametrize(
    ("choice", "text", "summary", "body"),
    [
        ("yes", None, "Answer to #{id}: yes", ""),
        (
            "later",
            "after the release\nplease",
            "Answer to #{id}: later",
            "after the release\nplease",
        ),
        (None, " after the release ", "Answer to #{id}: after the release", ""),
        (None, "after\nthe release", "Answer to #{id}: after", "after\nthe release"),
    ],
)
def test_the_humans_answer_comes_to_the_agent_as_a_message(
    repo, fake_tmux, choice, text, summary, body
):
    question = _asked(repo)
    runtime.answer_question("s", question.id, choice, text)
    asked, answer = state.list_messages("s")
    summary = summary.format(id=question.id)
    assert (answer.sender, answer.recipient, answer.summary, answer.body) == (
        "human",
        "w1",
        summary,
        body,
    )
    assert (answer.reply_to, answer.choice) == (question.id, choice)
    assert (asked.question_state, asked.answered_by) == (state.ANSWERED, answer.id)
    assert fake_tmux[-1][:3] == ("send_text", "s", "w1")
    assert fake_tmux[-1][3].startswith(f"[from human] {summary}")


def test_a_long_own_answer_is_cut_in_the_summary_and_whole_in_the_body(repo, fake_tmux):
    question = _asked(repo)
    runtime.answer_question("s", question.id, None, "x" * 300)
    answer = state.list_messages("s")[-1]
    assert len(answer.summary) == state.SUMMARY_LIMIT and answer.summary.endswith("…")
    assert answer.body == "x" * 300


def test_the_human_dismisses_a_question_and_the_agent_hears_of_it(repo, fake_tmux):
    question = _asked(repo)
    runtime.dismiss_question("s", question.id)
    asked, dismissal = state.list_messages("s")
    assert (dismissal.sender, dismissal.recipient, dismissal.summary) == (
        "human",
        "w1",
        f"Dismissed #{question.id}",
    )
    assert (dismissal.reply_to, dismissal.choice) == (question.id, None)
    assert (asked.question_state, asked.answered_by) == (state.DISMISSED, dismissal.id)
    assert fake_tmux[-1] == ("send_text", "s", "w1", f"[from human] Dismissed #{question.id}")


@pytest.mark.parametrize(
    ("choices", "free", "choice", "text", "reason"),
    [
        (
            ("yes", "later"),
            True,
            "no",
            None,
            'question #{id} has no choice "no"; its choices: yes, later',
        ),
        (
            ("yes",),
            False,
            None,
            "maybe",
            "question #{id} takes one of its choices, not an own answer",
        ),
        (("yes",), True, None, None, "choose one of the choices or write an answer"),
        (("yes",), True, None, "  ", "choose one of the choices or write an answer"),
    ],
)
def test_a_wrong_answer_is_refused(repo, fake_tmux, choices, free, choice, text, reason):
    question = _asked(repo, choices, free)
    with pytest.raises(runtime.LadoError, match=re.escape(reason.format(id=question.id))):
        runtime.answer_question("s", question.id, choice, text)
    assert state.list_messages("s")[-1].question_state == state.OPEN_QUESTION


def test_only_an_open_question_takes_an_answer(repo, fake_tmux):
    question = _asked(repo)
    runtime.answer_question("s", question.id, "yes")
    for act in (
        lambda: runtime.answer_question("s", question.id, "later"),
        lambda: runtime.dismiss_question("s", question.id),
    ):
        with pytest.raises(runtime.LadoError, match=f"question #{question.id} is answered"):
            act()
    assert len(state.list_messages("s")) == 2


def test_an_answer_to_no_question_is_refused(repo, fake_tmux):
    question = _asked(repo)
    answer_id = question.id + 1
    runtime.send_message("s", "w1", "human", "not a question")
    for missing in (answer_id, 999):
        with pytest.raises(runtime.LadoError, match=f"no question #{missing} in session s"):
            runtime.answer_question("s", missing, "yes")


def _question_states():
    return [m.question_state for m in state.list_messages("s") if m.kind == state.QUESTION]


def test_a_finished_workers_open_questions_are_closed(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.ask_human("s", "w1", "first?")
    runtime.ask_human("s", "w1", "second?")
    runtime.ask_human("s", "supervisor", "the supervisor's?")
    runtime.answer_question("s", state.list_messages("s")[0].id, text="done")
    runtime.finish_worker("s", "w1", discard=True)
    assert _question_states() == [state.ANSWERED, state.CLOSED, state.OPEN_QUESTION]


def test_stopping_the_session_closes_its_open_questions(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.ask_human("s", "w1", "first?")
    runtime.ask_human("s", "supervisor", "second?")
    runtime.stop_session("s")
    assert _question_states() == [state.CLOSED, state.CLOSED]


def _human_writes(text="merge w1?", agent="supervisor"):
    """The human's message typed into the idle agent and confirmed by its prompt."""
    state.set_status("s", agent, state.IDLE)
    runtime.write_as_human("s", text, to=agent)
    message = state.list_messages("s")[-1]
    _hook("UserPromptSubmit", agent, {"prompt": runtime.format_message(message)})
    return message


def _reply_state(message):
    return state.get_message("s", message.id).reply_state


def test_a_turn_that_wrote_nothing_to_the_human_is_flagged(repo, fake_tmux):
    _session_with_worker(repo)
    mine = _human_writes()
    _hook("Stop", "supervisor")
    assert _reply_state(mine) == state.MISSING


@pytest.mark.parametrize(
    "reply",
    [
        lambda: runtime.send_message("s", "supervisor", "human", "merged"),
        lambda: runtime.ask_human("s", "supervisor", "merge w2 too?"),
    ],
)
def test_a_turn_that_wrote_to_the_human_is_not_flagged(repo, fake_tmux, reply):
    _session_with_worker(repo)
    mine = _human_writes()
    reply()
    _hook("Stop", "supervisor")
    assert _reply_state(mine) == state.REPLIED


def test_a_body_read_in_a_turn_without_a_reply_is_flagged(repo, fake_tmux):
    _session_with_worker(repo)
    mine = _human_writes("merge w1?\nthen tag it")
    assert [m.id for m in state.read_messages("s", "supervisor")] == [mine.id]
    _hook("Stop", "supervisor")
    assert _reply_state(mine) == state.MISSING


def test_an_answer_to_a_question_needs_no_reply(repo, fake_tmux):
    question = _asked(repo)
    runtime.answer_question("s", question.id, "yes")
    answer = state.list_messages("s")[-1]
    _hook("UserPromptSubmit", "w1", {"prompt": runtime.format_message(answer)})
    _hook("Stop", "w1")
    assert _reply_state(answer) is None


def test_a_message_handed_over_at_the_turn_end_is_checked_at_the_next_one(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")  # busy
    runtime.write_as_human("s", "merge w1?")
    mine = state.list_messages("s")[-1]
    assert _hook("Stop", "supervisor")["reason"] == "[from human] merge w1?"
    assert _reply_state(mine) is None
    runtime.send_message("s", "supervisor", "human", "merged")
    _hook("Stop", "supervisor")
    assert _reply_state(mine) == state.REPLIED


def test_what_the_agent_wrote_before_it_got_the_message_is_no_reply_to_it(repo, fake_tmux):
    """Written in the turn before: the human's message, queued while the agent was busy,
    has a lower id than the agent's report, but the agent had not got it yet."""
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")  # busy
    runtime.write_as_human("s", "merge w1?")
    mine = state.list_messages("s")[-1]
    runtime.send_message("s", "supervisor", "human", "a report written meanwhile")
    _hook("Stop", "supervisor")  # hands the human's message over
    _hook("Stop", "supervisor")  # that turn wrote nothing to the human
    assert _reply_state(mine) == state.MISSING


def test_a_message_is_checked_once(repo, fake_tmux):
    _session_with_worker(repo)
    mine = _human_writes()
    _hook("Stop", "supervisor")
    runtime.send_message("s", "supervisor", "human", "merged, late")
    _hook("UserPromptSubmit", "supervisor")
    _hook("Stop", "supervisor")
    assert _reply_state(mine) == state.MISSING


def test_only_an_agent_is_told_it_may_write_to_the_human(repo, fake_tmux):
    question = _asked(repo)
    runtime.finish_worker("s", "w1", discard=True)
    state.add_agent(state.Agent("s", "w1", "worker", "/w", "b", "t", state.STOPPED))
    for act in (
        lambda: runtime.write_as_human("s", "hi", to="nobody"),
        lambda: runtime.post("s", "lado", "nobody", "a step"),
    ):
        with pytest.raises(runtime.LadoError) as refused:
            act()
        assert str(refused.value) == 'no running agent "nobody"; running agents: supervisor'
    with state.connect() as db:  # the question of a w1 that is not running
        db.execute("UPDATE messages SET question_state = 'open' WHERE id = ?", (question.id,))
    with pytest.raises(runtime.LadoError) as refused:
        runtime.answer_question("s", question.id, "yes")
    assert str(refused.value) == 'no running agent "w1"; running agents: supervisor'
