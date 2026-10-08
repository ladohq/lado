import dataclasses
import datetime
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import agent_helpers
import pytest
import yaml

from lado import agent_env, hooks, kits, loop, mcp_exec, providers, runs, runtime, state, tmux


def test_slug():
    assert runtime.slug("My Repo.v2") == "my-repo-v2"
    assert runtime.slug("...") == "lado"


def test_start_session_launches_supervisor(repo, fake_tmux, lado_home):
    started = runtime.start_session(str(repo), None, "acceptEdits", provider="claude")
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


def _installed(*names):
    return lambda provider: provider.name in names


def test_the_suggested_provider_is_the_folders_last_sessions_when_installed(repo, fake_tmux):
    runtime.start_session(str(repo), "old", None, "opencode")
    runtime.start_session(str(repo), "new", None, "kilo")
    suggestion = runtime.suggested_provider(str(repo), _installed("claude", "kilo", "opencode"))
    assert suggestion == runtime.Suggestion("kilo", runtime.LAST_SESSION)
    assert suggestion.line() == "kilo (the folder's last session)"


def test_the_last_sessions_provider_not_installed_falls_back_to_the_only_one(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    suggestion = runtime.suggested_provider(str(repo), _installed("opencode"))
    assert suggestion == runtime.Suggestion("opencode", runtime.ONLY_INSTALLED)
    assert suggestion.line() == "opencode (the only one installed)"


def test_another_folders_session_does_not_count(repo, tmp_path, fake_tmux):
    other = agent_helpers.init_repo(tmp_path / "other")
    runtime.start_session(str(other), "o", None, "kilo")
    assert runtime.suggested_provider(str(repo), _installed("claude", "kilo")) is None


@pytest.mark.parametrize(
    ("installed", "expected"),
    [
        (("kilo",), runtime.Suggestion("kilo", runtime.ONLY_INSTALLED)),
        (("claude", "opencode"), None),
        ((), None),
    ],
)
def test_without_a_last_session_only_a_single_installed_provider_is_suggested(
    repo, installed, expected
):
    assert runtime.suggested_provider(str(repo), _installed(*installed)) == expected
    assert runtime.suggested_provider(None, _installed(*installed)) == expected


def test_a_new_session_without_a_provider_takes_the_one_on_the_agents_path(
    repo, fake_tmux, monkeypatch, fake_clis, tmp_path
):
    only = tmp_path / "only-kilo"
    only.mkdir()
    (only / "kilo").symlink_to(fake_clis / "kilo")
    monkeypatch.setattr(agent_env, "resolve", lambda: {"PATH": str(only)})
    started = runtime.start_session(str(repo), "s", None)
    assert started.session.provider == "kilo"
    assert started.chosen == runtime.Suggestion("kilo", runtime.ONLY_INSTALLED)
    runtime.stop_session("s")
    resumed = runtime.start_session(str(repo), "s", None)  # a resume keeps its own
    assert (resumed.session.provider, resumed.chosen) == ("kilo", None)


def test_a_new_session_takes_the_folders_last_provider(repo, fake_tmux):
    runtime.start_session(str(repo), "a", None, "opencode")
    started = runtime.start_session(str(repo), "b", None)
    assert started.session.provider == "opencode"
    assert started.chosen == runtime.Suggestion("opencode", runtime.LAST_SESSION)


def test_a_new_session_with_several_providers_and_no_history_is_refused(repo, fake_tmux):
    with pytest.raises(runtime.LadoError) as error:
        runtime.start_session(str(repo), "s", None)
    assert str(error.value) == (
        "which agent CLI should the session run? Installed on the agents' PATH: "
        "claude, kilo, opencode; give one with --provider NAME"
    )
    assert fake_tmux == []
    assert state.get_session("s") is None


def test_a_new_session_with_no_provider_installed_is_refused_with_install_hints(
    repo, fake_tmux, monkeypatch, tmp_path
):
    _path_without_clis(monkeypatch, tmp_path)
    with pytest.raises(runtime.LadoError) as error:
        runtime.start_session(str(repo), "s", None)
    message = str(error.value)
    assert message.startswith("no agent CLI is on the agents' PATH; ")
    for name in providers.names():
        assert providers.get(name).install_hint in message
    assert state.get_session("s") is None


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


@pytest.mark.parametrize(
    ("given", "refused"),
    [
        ({"provider": "nope"}, 'unknown provider "nope"'),
        ({"provider": "kilo", "permission_mode": "dontAsk"}, 'permission mode "dontAsk"'),
    ],
)
@pytest.mark.parametrize("resumed", [False, True])
def test_a_wrong_provider_or_mode_is_refused_before_the_login_shell(
    repo, fake_tmux, monkeypatch, given, refused, resumed
):
    if resumed:
        runtime.start_session(str(repo), "s", None, "claude")
        runtime.stop_session("s")
    monkeypatch.setattr(agent_env, "resolve", _broken_env)
    with pytest.raises(runtime.LadoError, match=re.escape(refused)):
        runtime.start_session(str(repo), "s", given.get("permission_mode"), given["provider"])


def test_a_start_whose_environment_fails_launches_nothing(repo, fake_tmux, monkeypatch):
    monkeypatch.setattr(agent_env, "resolve", _broken_env)
    with pytest.raises(runtime.LadoError, match="your shell failed with exit status 1"):
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert fake_tmux == []
    assert state.get_session("s") is None
    assert not (state.home() / "agents" / "s").exists()


def test_a_resume_whose_environment_fails_leaves_the_session_as_it_was(
    repo, fake_tmux, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="claude")
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
    runtime.start_session(str(repo), "s", None, provider="claude")
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
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert "LADO_AGENT_ENV=inherit" in str(error.value)
    assert fake_tmux == []
    assert state.get_session("s") is None
    assert not (state.home() / "agents" / "s" / "supervisor").exists()


def test_a_spawn_whose_cli_is_not_on_the_agents_path_leaves_no_worker(
    repo, fake_tmux, monkeypatch, tmp_path
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    _path_without_clis(monkeypatch, tmp_path)
    with pytest.raises(runtime.LadoError, match=r"`kilo` is not on the agents' PATH"):
        runtime.spawn_worker("s", "a task", provider="kilo")
    assert "new_window" not in [c[0] for c in fake_tmux]
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*") == ""
    assert not (state.home() / "agents" / "s" / "worker").exists()


def test_start_refuses_running_session(repo, fake_tmux):
    runtime.start_session(str(repo), None, None, provider="claude")
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(str(repo), None, None, provider="claude")


def test_start_on_a_running_session_restarts_a_dead_loop(repo, fake_tmux, loop_starts):
    from lado import loop

    runtime.start_session(str(repo), "s", None, provider="claude")
    assert loop_starts == ["s"]
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert loop_starts == ["s", "s"]  # its lock was free: the loop had died
    held = loop.take_lock("s")  # its loop runs
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert loop_starts == ["s", "s"]
    held.close()


def test_start_requires_git_repo(tmp_path, fake_tmux):
    with pytest.raises(runtime.LadoError, match="not inside a git repository"):
        runtime.start_session(str(tmp_path), None, None, provider="claude")


def _session_in(status, repo, fake_tmux):
    """A session "s" of `repo` that is running, stopped or whose tmux server is gone."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    if status == runtime.SessionStatus.STOPPED:
        runtime.stop_session("s")
    elif status == runtime.SessionStatus.TMUX_GONE:
        fake_tmux.append(("kill_session", "s"))


def test_a_new_session_starts_with_resume_false(repo, fake_tmux):
    started = runtime.start_session(str(repo), "s", None, resume=False, provider="claude")
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
        runtime.start_session(str(repo), "s", "plan", resume=False, provider="claude")
    assert (error.value.status, error.value.repo) == (shown, str(repo))
    assert f'session "s" exists already ({shown.value}, in {repo})' in str(error.value)
    assert len(state.list_events("s")) == events  # nothing was changed
    assert state.get_session("s").permission_mode is None


def test_resume_true_refuses_an_unknown_session(repo, fake_tmux):
    with pytest.raises(runtime.NoSuchSession, match='unknown session "s"'):
        runtime.start_session(str(repo), "s", None, resume=True, provider="claude")
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
        runtime.start_session(str(repo), "s", None, resume=True, provider="claude")
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
        runtime.start_session(str(empty), None, None, provider="claude")
    assert state.list_sessions() == []


def test_spawn_worker_creates_worktree_and_passes_task(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
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
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task")
    cmd = fake_tmux[-1][-1]
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert "The supervisor cannot see your screen" in prompt


def _prompt(cmd):
    return cmd[cmd.index("--append-system-prompt") + 1]


def test_agents_are_told_how_to_send_and_read_messages(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
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


def test_agents_are_told_to_keep_results_as_artifacts_and_attach_them(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task")
    for _, _, window, _, cmd in fake_tmux:
        prompt = " ".join(_prompt(cmd).split())
        for tool in ("write_artifact", "read_artifact", "list_artifacts"):
            assert tool in prompt, window
        assert "`artifacts`" in prompt and "flow_advance" in prompt, window
        assert "is an artifact, not a path to a file" in prompt, window
    supervisor = " ".join(_prompt(fake_tmux[0][-1]).split())
    assert "A bare artifact name is in the session's scope" in supervisor
    assert 'named by their full name, "<run>/<name>"' in supervisor
    assert "in a step of your own in a run, write and attach the run's artifacts" in supervisor


def test_the_supervisor_is_told_to_answer_the_human_where_they_asked(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    supervisor = " ".join(_prompt(fake_tmux[0][-1]).split())
    assert "The human talks to you in this window" not in supervisor
    assert 'answer a message "[from human] ..." with send_message(to="human")' in supervisor
    assert "ask with ask_human" in supervisor
    assert "answer text typed straight into your window in this window" in supervisor


def test_the_supervisor_is_told_the_copy_of_the_humans_message_is_for_its_information(
    repo, fake_tmux
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    supervisor = " ".join(_prompt(fake_tmux[0][-1]).split())
    assert '"[from lado] human wrote to <agent>: ..." that is for your information' in supervisor
    assert "do not pass it on and do not answer it" in supervisor
    assert "if it changes the plan, take it into account" in supervisor


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
    runtime.start_session(str(repo), "s", None, provider="claude")
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


def test_a_message_the_loop_types_in_while_it_is_sent_is_reported_sent(
    repo, fake_tmux, monkeypatch
):
    """The session loop's sweep may hand the message over between the sender's queue and
    its look at the agent: the agent is busy then, with this message."""
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    queue_message = state.queue_message

    def queue_then_loop_pass(*args, **kwargs):
        queued = queue_message(*args, **kwargs)
        runtime.sweep("s")
        return queued

    monkeypatch.setattr(state, "queue_message", queue_then_loop_pass)
    assert runtime.send_message("s", "supervisor", "w1", "hi") == "sent"
    assert _typed(fake_tmux, "w1") == ["[from supervisor] hi"]


@pytest.mark.parametrize("dropped", [True, False])
def test_a_message_to_a_worker_finished_while_it_is_sent_is_refused(
    repo, fake_tmux, monkeypatch, dropped
):
    """finish_worker forgets the worker, then drops its undelivered messages: either may
    come between the sender's queue and its delivery. Nobody got the message."""
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    queue_message = state.queue_message

    def queue_then_finish(*args, **kwargs):
        queued = queue_message(*args, **kwargs)
        state.delete_agent("s", "w1")
        if dropped:
            state.drop_undelivered("s", "w1")
        return queued

    monkeypatch.setattr(state, "queue_message", queue_then_finish)
    with pytest.raises(runtime.LadoError, match='no running agent "w1"; running agents: '):
        runtime.send_message("s", "supervisor", "w1", "hi")
    assert _typed(fake_tmux, "w1") == []


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


def test_hand_over_by_hook_output_returns_the_lines_and_types_nothing(repo, fake_tmux):
    _session_with_worker(repo)
    state.queue_message("s", "supervisor", "w1", "one")
    state.queue_message("s", "supervisor", "w1", "two")
    state.set_status("s", "w1", state.IDLE)
    text = runtime.hand_over("s", "w1", state.HOOK_OUTPUT)
    assert text == "[from supervisor] one\n[from supervisor] two"
    assert _typed(fake_tmux, "w1") == []
    messages = state.list_messages("s")
    assert [(m.state, m.channel, m.attempts) for m in messages] == [
        (state.SENT, state.HOOK_OUTPUT, 1)
    ] * 2
    assert state.get_agent("s", "w1").status == state.BUSY


def test_hand_over_by_typing_types_the_lines(repo, fake_tmux):
    _session_with_worker(repo)
    state.queue_message("s", "supervisor", "w1", "one")
    state.set_status("s", "w1", state.IDLE)
    assert runtime.hand_over("s", "w1", state.TYPED) == "[from supervisor] one"
    assert _typed(fake_tmux, "w1") == ["[from supervisor] one"]
    assert state.list_messages("s")[0].channel == state.TYPED


@pytest.mark.parametrize("channel", [state.TYPED, state.HOOK_OUTPUT])
def test_hand_over_takes_nothing_while_a_batch_is_unconfirmed_or_the_agent_not_idle(
    repo, fake_tmux, channel
):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.BUSY)
    state.queue_message("s", "supervisor", "w1", "one")
    assert runtime.hand_over("s", "w1", channel) == ""
    state.set_status("s", "w1", state.IDLE)
    assert runtime.hand_over("s", "w1", channel)
    state.set_status("s", "w1", state.IDLE)
    state.queue_message("s", "supervisor", "w1", "two")
    assert runtime.hand_over("s", "w1", channel) == ""
    assert [m.state for m in state.list_messages("s")] == [state.SENT, state.PENDING]


DELAYS = (15, 30, 60)
CONTINUED = {"stop_hook_active": True}  # Claude Code's Stop of a turn its Stop hook went on


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


def _missed_report(repo):
    """w1's report queued for the idle supervisor and handed over by no one: as if every
    hook had missed it."""
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    state.queue_message("s", "w1", "supervisor", "report", "")


def test_a_sweep_types_in_what_no_hook_handed_over(repo, fake_tmux):
    _missed_report(repo)
    runtime.sweep("s")
    assert _typed(fake_tmux) == ["[from w1] report"]
    assert [m.state for m in state.list_messages("s")] == [state.SENT]
    assert state.get_agent("s", "supervisor").status == state.BUSY
    runtime.sweep("s")
    assert _typed(fake_tmux) == ["[from w1] report"]


@pytest.mark.parametrize("status", [state.BUSY, state.WAITING, state.STARTING, state.STOPPED])
def test_a_sweep_types_nothing_into_an_agent_not_idle(repo, fake_tmux, status):
    _missed_report(repo)
    state.set_status("s", "supervisor", status)
    runtime.sweep("s")
    assert _typed(fake_tmux) == []
    assert [m.state for m in state.list_messages("s")] == [state.PENDING]


def test_a_sweep_types_nothing_new_while_a_typed_message_is_unconfirmed(repo, fake_tmux):
    sent = _mismatched_report(repo, fake_tmux)  # the supervisor is idle
    state.queue_message("s", "w1", "supervisor", "ping", "")
    runtime.sweep("s", now=sent + 1, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]
    assert [m.state for m in state.list_messages("s")] == [state.SENT, state.PENDING]


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
    assert state.list_messages("s")[0].state == state.SENT
    _hook("Stop", "supervisor", CONTINUED)
    assert state.list_messages("s")[0].state == state.DELIVERED


def test_a_new_message_waits_while_one_typed_is_unconfirmed(repo, fake_tmux):
    _mismatched_report(repo, fake_tmux)  # the supervisor is idle
    assert runtime.send_message("s", "w1", "supervisor", "ping").startswith("queued")
    assert _typed(fake_tmux) == ["[from w1] report"]


@pytest.mark.parametrize(
    ("event", "payload"),
    [("SessionStart", {"source": "clear"}), ("Stop", {}), ("Stop", CONTINUED)],
    ids=["conversation start", "turn end", "turn end that went on"],
)
def test_a_hook_hands_over_nothing_while_a_message_typed_is_unconfirmed(
    repo, fake_tmux, event, payload
):
    _swallowed_report(repo, fake_tmux)  # the supervisor is busy, as LADO typed into it
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    runtime.send_message("s", "w1", "supervisor", "ping")
    assert _hook(event, "supervisor", payload) is None
    assert _typed(fake_tmux) == ["[from w1] report"]
    assert [m.state for m in state.list_messages("s")] == [state.SENT, state.PENDING]


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
    assert runtime.status_reasons("s") == {
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
    assert runtime.status_reasons("s") == {
        "supervisor": "did not take 1 message: answer the dialog in its window "
        "or type any line there"
    }
    assert runtime.status_reason("s", "supervisor") == runtime.status_reasons("s")["supervisor"]
    assert runtime.status_reason("s", "w1") is None  # not waiting
    assert runtime.status_reason("s", "nobody") is None


def test_an_agent_waiting_after_unconfirmed_messages_says_so(repo, fake_tmux):
    _mismatched_report(repo, fake_tmux)
    no_delays = (0, 0, 0)  # in real time: the hooks below come after the failure
    for _ in no_delays:
        runtime.sweep("s", delays=no_delays)
        _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
        _hook("Stop", "supervisor")
    runtime.sweep("s", delays=no_delays)
    assert state.list_messages("s")[0].state == state.FAILED
    assert runtime.status_reasons("s") == {
        "supervisor": "did not confirm 1 message (the text typed did not match)"
    }
    _hook("UserPromptSubmit", "supervisor", {"prompt": "go on"})
    assert runtime.status_reasons("s") == {}  # busy again
    # Later it waits for a permission: the old failure is not why.
    _hook("PermissionRequest", "supervisor", {"tool_name": "Bash", "tool_input": {}})
    assert state.get_agent("s", "supervisor").status == state.WAITING
    assert runtime.status_reasons("s") == {}
    assert runtime.status_reason("s", "supervisor") is None


def test_an_agent_waiting_after_swallowed_messages_works_again_after_any_tool(repo, fake_tmux):
    """A wait for no request in particular: the agent's first tool call says the human
    answered the dialog. Its messages wait for its turn's end, as for any busy agent."""
    _retry_until_failed(_swallowed_report(repo, fake_tmux))
    typed = len(_typed(fake_tmux))
    assert _hook("PostToolUse", "supervisor", {"tool_name": "Read", "tool_input": {}}) is None
    assert state.get_agent("s", "supervisor").status == state.BUSY
    assert len(_typed(fake_tmux)) == typed  # nothing typed into a busy agent
    report = state.list_messages("s")[0]
    assert (report.state, report.attempts) == (state.PENDING, 0)  # back in the queue
    assert _hook("Stop", "supervisor") == {"decision": "block", "reason": "[from w1] report"}


def test_a_waiting_agent_works_again_once_the_human_answered_its_dialog(repo, fake_tmux):
    _session_with_worker(repo)
    bash = {"tool_name": "Bash", "tool_input": {"command": "make"}}
    _hook("PermissionRequest", "w1", bash)
    assert state.get_agent("s", "w1").status == state.WAITING
    # Its subagent reads a file meanwhile: the dialog is still open.
    _hook("PostToolUse", "w1", {"tool_name": "Read", "tool_input": {}, "agent_id": "a1"})
    assert state.get_agent("s", "w1").status == state.WAITING
    assert [w.agent.name for w in state.waiting_items("s")] == ["w1"]
    _hook("PostToolUse", "w1", {**bash, "tool_response": {"stdout": ""}})
    assert state.get_agent("s", "w1").status == state.BUSY
    assert state.waiting_items("s") == []
    _hook("Stop", "w1")
    _hook("PostToolUse", "w1", bash)  # an async hook that comes after the turn's end
    assert state.get_agent("s", "w1").status == state.IDLE


def _trust_reason(repo):
    return (
        f'Claude Code asks whether to trust {repo}: in its terminal choose "Yes, I trust '
        'this folder" (Enter alone answers "No, exit" and closes the agent)'
    )


def _seen_at_launch(monkeypatch, call, agent):
    """Record the agent's status and status_reason when tmux's `call` starts its window."""
    seen, launch = [], getattr(tmux, call)

    def record(*args):
        seen.append((state.get_agent("s", agent).status, runtime.status_reason("s", agent)))
        return launch(*args)

    monkeypatch.setattr(tmux, call, record)
    return seen


def test_an_agent_held_before_its_first_hook_waits_for_the_human_from_its_start(
    repo, fake_tmux, claude_config, monkeypatch
):
    claude_config.trust()  # Claude Code trusts no folder: it asks before any hook
    seen = _seen_at_launch(monkeypatch, "new_session", "supervisor")
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    reason = _trust_reason(repo)
    assert seen == [(state.WAITING, reason)]  # waiting before its window starts
    assert reason in started.warnings
    assert runtime.status_reasons("s") == {"supervisor": reason}
    [waits] = state.waiting_items("s")
    assert waits.agent.name == "supervisor"
    runtime.write_as_human("s", "hi")
    assert state.list_messages("s")[-1].state == state.PENDING
    assert fake_tmux[-1][0] == "new_session"  # nothing typed into it
    # The human trusts the folder: Claude Code starts, its session-start hook runs.
    _hook("SessionStart", "supervisor", {"source": "startup"})
    assert state.get_agent("s", "supervisor").status == state.BUSY  # typed in: the message
    assert runtime.status_reasons("s") == {}
    assert state.waiting_items("s") == []


def test_the_reason_an_agent_was_held_goes_with_its_next_status(repo, fake_tmux, claude_config):
    claude_config.trust()
    runtime.start_session(str(repo), "s", None, provider="claude")
    _hook("SessionStart", "supervisor", {"source": "startup"})
    # Later it waits for a permission: the folder's trust is not why.
    _hook("PermissionRequest", "supervisor", {"tool_name": "Bash", "tool_input": {}})
    assert state.get_agent("s", "supervisor").status == state.WAITING
    assert runtime.status_reason("s", "supervisor") is None


def test_a_session_start_ends_no_other_wait(repo, fake_tmux):
    """Claude Code's SessionStart after a compaction is a session start too."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    _hook("SessionStart", "supervisor", {"source": "startup"})
    _hook("PermissionRequest", "supervisor", {"tool_name": "Bash", "tool_input": {}})
    _hook("SessionStart", "supervisor", {"source": "compact"})
    assert state.get_agent("s", "supervisor").status == state.WAITING


def test_a_conversation_start_of_a_held_agent_is_as_before(repo, fake_tmux, claude_config):
    claude_config.trust()
    runtime.start_session(str(repo), "s", None, provider="claude")
    _hook("SessionStart", "supervisor", {"source": "clear"})
    assert state.get_agent("s", "supervisor").status == state.IDLE


def test_a_held_agent_of_an_earlier_launch_is_no_reason_for_the_next(
    repo, fake_tmux, claude_config
):
    claude_config.trust()
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    claude_config.trust(repo)
    started = runtime.start_session(str(repo), "s", None)
    assert started.warnings == []
    assert state.get_agent("s", "supervisor").status == state.STARTING
    state.wait("s", "supervisor")  # e.g. after messages failed
    assert runtime.status_reason("s", "supervisor") is None


def test_a_failed_start_of_a_held_agent_leaves_nothing_waiting(
    repo, fake_tmux, claude_config, monkeypatch
):
    claude_config.trust()
    monkeypatch.setattr(tmux, "new_session", _fail)
    with pytest.raises(tmux.TmuxError):
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert state.waiting_items() == []


def test_a_worker_held_before_its_first_hook_says_so_to_its_spawner(
    repo, fake_tmux, claude_config, monkeypatch
):
    claude_config.trust()
    runtime.start_session(str(repo), "s", None, provider="kilo")
    seen = _seen_at_launch(monkeypatch, "new_window", "w1")
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", provider="claude", warnings=warnings)
    reason = _trust_reason(repo)
    assert seen == [(state.WAITING, reason)]
    assert warnings == [reason]
    assert f"s: w1: {reason}" in (state.home() / "loop.log").read_text()
    assert runtime.status_reasons("s") == {"w1": reason}


def test_a_claude_config_that_cannot_be_read_is_a_warning(repo, fake_tmux, claude_config):
    claude_config.path.write_text("{not json")
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    assert started.warnings == [
        f"cannot tell whether Claude Code trusts {repo}: {claude_config.path}: Expecting "
        "property name enclosed in double quotes: line 1 column 2 (char 1)"
    ]
    assert state.get_agent("s", "supervisor").status == state.STARTING
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", warnings=warnings)
    assert warnings == started.warnings
    assert f"s: w1: {warnings[0]}" in (state.home() / "loop.log").read_text()


def test_providers_that_never_hold_an_agent_start_it_as_before(repo, fake_tmux, claude_config):
    claude_config.trust()
    started = runtime.start_session(str(repo), "s", None, provider="kilo")
    assert started.warnings == []
    assert state.get_agent("s", "supervisor").status == state.STARTING


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


@pytest.mark.parametrize(
    ("status", "wait"),
    [
        (state.BUSY, True),
        (state.IDLE, True),
        (state.WAITING, False),
        (state.STARTING, False),
    ],
)
def test_a_failure_plans_a_busy_or_idle_agent_waiting(status, wait):
    agent = state.Agent("s", "w1", "worker", "/r", None, None, status, provider="claude")
    last = state.Message(7, "supervisor", "hi", "", "w1", state.SENT, attempts=len(DELAYS) + 1)
    plan = runtime._plan(agent, [last], 100.0, DELAYS)
    assert (plan.fail, plan.retype, plan.wait) == ([7], False, wait)
    young = dataclasses.replace(last, attempts=1, sent_at=100.0)
    assert runtime._plan(agent, [young], 100.0, DELAYS) == state.Plan()


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


def test_messages_in_the_stop_hooks_output_are_delivered_when_the_turn_goes_on(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "one")
    assert _hook("Stop", "supervisor") == {"decision": "block", "reason": "[from w1] one"}
    [one] = state.list_messages("s")
    assert (one.state, one.channel) == (state.SENT, state.HOOK_OUTPUT)
    # A second block at once: the first one is confirmed before the queue is taken.
    runtime.send_message("s", "w1", "supervisor", "two")
    assert _hook("Stop", "supervisor", CONTINUED) == {
        "decision": "block",
        "reason": "[from w1] two",
    }
    assert [m.state for m in state.list_messages("s")] == [state.DELIVERED, state.SENT]
    assert _hook("Stop", "supervisor", CONTINUED) is None
    assert [m.state for m in state.list_messages("s")] == [state.DELIVERED] * 2
    assert state.get_agent("s", "supervisor").status == state.IDLE
    assert _typed(fake_tmux) == []


def test_a_turn_that_went_on_confirms_no_message_typed_in(repo, fake_tmux):
    """Another Stop hook of the user's may have made the turn go on: what LADO typed is
    confirmed only by its line."""
    _swallowed_report(repo, fake_tmux)
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    _hook("Stop", "supervisor", CONTINUED)
    [report] = state.list_messages("s")
    assert (report.state, report.channel) == (state.SENT, state.TYPED)


def _handed_over_in_the_stop_hook(repo):
    """w1's report in the busy supervisor's Stop hook output. Returns when it was handed
    over."""
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "report")
    assert _hook("Stop", "supervisor") == {"decision": "block", "reason": "[from w1] report"}
    return state.list_messages("s")[0].sent_at


def test_a_long_turn_from_the_hook_output_gets_it_typed_in_once_and_never_fails(repo, fake_tmux):
    sent = _handed_over_in_the_stop_hook(repo)
    for at in range(DELAYS[0] - 1, DELAYS[0] + DELAYS[1]):  # each second, no hook
        runtime.sweep("s", now=sent + at, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]
    [report] = state.list_messages("s")
    assert (report.state, report.channel) == (state.SENT, state.TYPED)
    # The turn ends; the CLI takes what was typed in meanwhile as its next prompt.
    _hook("Stop", "supervisor", CONTINUED)
    assert state.list_messages("s")[0].state == state.SENT
    _hook("UserPromptSubmit", "supervisor", {"prompt": "[from w1] report"})
    assert state.list_messages("s")[0].state == state.DELIVERED


def test_typed_in_after_the_hook_output_it_is_retried_and_fails_as_any_typed(repo, fake_tmux):
    sent = _handed_over_in_the_stop_hook(repo)
    _retry_until_failed(sent)
    assert _typed(fake_tmux) == ["[from w1] report"] * len(DELAYS)
    assert state.list_messages("s")[0].state == state.FAILED
    assert state.get_agent("s", "supervisor").status == state.WAITING
    notice = state.list_messages("s")[-1]
    assert (notice.sender, notice.recipient) == ("lado", "w1")
    assert notice.summary == "message #1 to supervisor not delivered: report"


def test_a_turn_that_ends_without_taking_the_hook_output_gets_it_from_the_queue(repo, fake_tmux):
    sent = _handed_over_in_the_stop_hook(repo)
    _hook("Stop", "supervisor")  # not stop_hook_active: the CLI did not take the output
    runtime.sweep("s", now=sent + DELAYS[0] - 1, delays=DELAYS)
    assert state.list_messages("s")[0].state == state.SENT
    runtime.sweep("s", now=sent + DELAYS[0], delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]
    [report] = state.list_messages("s")
    assert (report.state, report.channel, report.attempts) == (state.SENT, state.TYPED, 2)


def test_output_a_turn_ended_without_is_not_confirmed_by_a_later_turn_that_goes_on(repo, fake_tmux):
    """E.g. Claude Code's 8th block in a row is overridden: the turn ends without the text.
    A later turn that another Stop hook made go on must not confirm it."""
    _handed_over_in_the_stop_hook(repo)
    _hook("Stop", "supervisor")  # not stop_hook_active: the CLI did not take the output
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    _hook("Stop", "supervisor", CONTINUED)
    [report] = state.list_messages("s")
    assert (report.state, report.channel) == (state.SENT, state.TYPED)


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
    with pytest.raises(runtime.LadoError, match=r"write the details to an artifact \(write_"):
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
    _hook("PermissionRequest", "w1", {"tool_name": "Bash", "tool_input": {}})
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


def test_session_start_looks_for_the_lado_mcp_server_every_twentieth_of_a_second(
    repo, fake_tmux, monkeypatch
):
    """Each look sooner starts the agent's first turn sooner."""
    _session_with_worker(repo)
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            _mcp_ready("w1")

    monkeypatch.setattr(hooks.time, "sleep", sleep)
    _hook("SessionStart", "w1", mcp_ready=False)
    assert hooks.MCP_READY_POLL == 0.02
    assert sleeps == [hooks.MCP_READY_POLL] * 2
    assert hooks.MCP_READY_TIMEOUT == 20.0


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


def test_session_start_types_in_what_was_queued_while_the_agent_started(repo, fake_tmux):
    _session_with_worker(repo)
    # Not at its turn's end: as soon as it is idle.
    assert runtime.send_message("s", "w1", "supervisor", "report") == (
        "queued; supervisor is starting and will get it when it is idle"
    )
    _hook("SessionStart", "supervisor", {"source": "startup"})
    assert _typed(fake_tmux) == ["[from w1] report"]
    assert [m.state for m in state.list_messages("s")] == [state.SENT]
    assert state.get_agent("s", "supervisor").status == state.BUSY


def test_session_start_of_an_agent_busy_with_its_task_types_in_nothing(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.send_message("s", "supervisor", "w1", "hi")
    _hook("SessionStart", "w1", {"source": "startup"})
    assert _typed(fake_tmux, "w1") == []  # it gets the queue when its first turn ends
    assert _hook("Stop", "w1") == {"decision": "block", "reason": "[from supervisor] hi"}


@pytest.mark.parametrize("hook_runs", ["before the queue", "after the queue", "after the read"])
def test_a_message_sent_while_the_agent_becomes_idle_is_handed_over_once(
    repo, fake_tmux, monkeypatch, hook_runs
):
    """The sender queues, then reads the status; the hook sets idle, then takes the queue.
    Wherever the hook runs in between, exactly one of them types the message in."""
    _session_with_worker(repo)
    queue_message, get_agent = state.queue_message, state.get_agent
    status_read_next = []

    def session_start():
        _hook("SessionStart", "supervisor", {"source": "startup"})

    def queue(*args, **kwargs):
        if hook_runs == "before the queue":
            session_start()
        queued = queue_message(*args, **kwargs)
        if hook_runs == "after the queue":
            session_start()
        status_read_next.append(True)
        return queued

    def read_status(*args, **kwargs):
        agent = get_agent(*args, **kwargs)
        if status_read_next and status_read_next.pop() and hook_runs == "after the read":
            session_start()  # the sender has seen the supervisor starting
        return agent

    monkeypatch.setattr(state, "queue_message", queue)
    monkeypatch.setattr(state, "get_agent", read_status)
    runtime.send_message("s", "w1", "supervisor", "report")
    monkeypatch.setattr(state, "queue_message", queue_message)
    monkeypatch.setattr(state, "get_agent", get_agent)
    runtime.sweep("s")  # the session loop finds nothing more to do
    assert _typed(fake_tmux) == ["[from w1] report"]
    assert [m.state for m in state.list_messages("s")] == [state.SENT]


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
    runtime.start_session(str(repo), "s", None, provider="claude")
    instance = state.get_agent("s", "supervisor").instance
    monkeypatch.setattr("sys.stdin.read", lambda: "not json")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    assert "JSONDecodeError" in (lado_home / "hooks.log").read_text()


def test_a_stop_hook_that_fails_after_the_hand_over_loses_no_message(
    repo, fake_tmux, lado_home, monkeypatch
):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "report")
    instance = state.get_agent("s", "supervisor").instance
    claude = type(providers.get("claude"))
    monkeypatch.setattr(claude, "continue_output", lambda self, text: 1 / 0)
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    assert "ZeroDivisionError" in (lado_home / "hooks.log").read_text()
    # Never printed: it waits to be typed in, and no turn that goes on confirms it.
    [report] = state.list_messages("s")
    assert (report.state, report.channel) == (state.SENT, state.TYPED)
    # No output, so no hook follows: the sweep types it in after the first delay.
    runtime.sweep("s", now=report.sent_at + DELAYS[0], delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]


def test_a_turn_another_stop_hook_went_on_with_confirms_no_output_never_printed(
    repo, fake_tmux, monkeypatch
):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "report")
    instance = state.get_agent("s", "supervisor").instance
    with monkeypatch.context() as patched:
        claude = type(providers.get("claude"))
        patched.setattr(claude, "continue_output", lambda self, text: 1 / 0)
        patched.setattr("sys.stdin.read", lambda: "{}")
        hooks.main("Stop", "s", "supervisor", instance)
    # The user's own Stop hook made the turn go on.
    _hook("Stop", "supervisor", CONTINUED)
    assert state.list_messages("s")[0].state == state.SENT


def test_a_hook_on_an_older_schema_says_why_and_changes_nothing(
    repo, fake_tmux, lado_home, monkeypatch
):
    """LADO upgraded in place under a running session: its hooks run the new code."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    instance = state.get_agent("s", "supervisor").instance
    agent_helpers.previous_schema()
    before = agent_helpers.database()
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    assert hooks.main("Stop", "s", "supervisor", instance) == 0
    log = (lado_home / "hooks.log").read_text()
    assert "Stop s/supervisor: " in log
    assert "LADO was upgraded under a running session" in log and "`lado stop --all`" in log
    assert "Traceback" not in log
    assert agent_helpers.database() == before


def test_hooks_from_an_earlier_launch_are_ignored(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
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


def _config_folders(lado_home):
    """The agents' config folders there are, as "<session>/<agent>"."""
    root = lado_home / "agents"
    return sorted(str(p.relative_to(root)) for p in root.glob("*/*")) if root.exists() else []


def test_an_agents_config_folder_lives_only_while_it_runs(repo, fake_tmux, lado_home):
    _session_with_worker(repo)
    runtime.start_session(str(repo), "other", None, provider="claude")
    assert _config_folders(lado_home) == ["other/supervisor", "s/supervisor", "s/w1"]
    worker = state.get_agent("s", "w1")
    _commit(worker.cwd)
    runtime.git(str(repo), "merge", "-q", "--ff-only", worker.branch)
    runtime.finish_worker("s", "w1")
    assert _config_folders(lado_home) == ["other/supervisor", "s/supervisor"]
    runtime.spawn_worker("s", "task", name="w2")
    runtime.agent_ended("s", "w2", "its CLI exited")
    assert _config_folders(lado_home) == ["other/supervisor", "s/supervisor"]
    runtime.stop_session("s")
    assert _config_folders(lado_home) == ["other/supervisor"]
    # Left by an older LADO, or a launch that failed: the next start removes it.
    (lado_home / "agents" / "s" / "old-worker").mkdir(parents=True)
    (lado_home / "agents" / "s" / "supervisor").mkdir()
    (lado_home / "agents" / "s" / "supervisor" / "env.json").write_text("{}")
    runtime.start_session(str(repo), "s", None)
    assert _config_folders(lado_home) == ["other/supervisor", "s/supervisor"]
    assert [p.name for p in (lado_home / "agents/s/supervisor").glob("env.json")] == ["env.json"]
    runtime.stop_session("s")
    (lado_home / "agents" / "s" / "old-worker").mkdir(parents=True)
    runtime.forget_session("s")
    assert not (lado_home / "agents" / "s").exists()
    assert _config_folders(lado_home) == ["other/supervisor"]


def test_stop_all_removes_the_config_folders_of_each_session(repo, fake_tmux, lado_home):
    _session_with_worker(repo)
    runtime.start_session(str(repo), "other", None, provider="claude")
    runtime.stop_all(lambda name, stopped: None)
    assert _config_folders(lado_home) == []


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
    runtime.start_session(str(repo), "s", None, provider="claude")
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
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert state.get_session("s") is None
    assert not (state.home() / "agents" / "s" / "supervisor").exists()


def test_a_failed_resume_leaves_the_session_stopped(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
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
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    with monkeypatch.context() as m:
        if failing == "tmux":
            m.setattr(tmux, "new_session", _fail)
        else:
            m.setattr(runs, "resume", _fail)
        with pytest.raises(tmux.TmuxError, match="command too long"):
            runtime.start_session(
                str(repo), "s", "plan", "kilo", ["default", "team"], ["skill:style"]
            )
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


def _no_tmux(*args, **kwargs):
    raise tmux.TmuxMissing("tmux is not installed or not on PATH (/nowhere)")


def _locked(*args, **kwargs):
    raise sqlite3.OperationalError("database is locked")


def _undo_notes(error):
    return getattr(error, "__notes__", [])


def test_a_spawn_without_tmux_leaves_no_ghost_worker(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
    with monkeypatch.context() as m:
        m.setattr(tmux, "new_window", _no_tmux)
        m.setattr(tmux, "kill_window", _no_tmux)  # its undo's tmux call fails the same way
        with pytest.raises(tmux.TmuxMissing, match="tmux is not installed") as error:
            runtime.spawn_worker("s", "task")
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert not (state.home() / "agents" / "s" / "worker").exists()
    assert runtime.session_worktrees(str(repo), "s") == {}
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*") == ""
    last = state.list_events("s")[-1]
    assert (last.agent, last.kind) == ("worker", state.FINISHED)
    note = (
        "undo of the spawn of worker: close its window failed: TmuxMissing: "
        "tmux is not installed or not on PATH (/nowhere)"
    )
    assert _undo_notes(error.value) == [note]
    assert note in (state.home() / "loop.log").read_text()


def test_a_failed_spawn_undo_keeps_the_cause_and_runs_every_step(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
    with monkeypatch.context() as m:
        m.setattr(tmux, "new_window", _fail)
        m.setattr(state, "delete_agent", _locked)
        with pytest.raises(tmux.TmuxError, match="command too long") as error:
            runtime.spawn_worker("s", "task")
    assert _undo_notes(error.value) == [
        "undo of the spawn of worker: forget the worker failed: OperationalError: "
        "database is locked"
    ]
    assert "forget the worker failed" in (state.home() / "loop.log").read_text()
    # The steps after the failing one ran all the same.
    assert not (state.home() / "agents" / "s" / "worker").exists()
    assert runtime.session_worktrees(str(repo), "s") == {}
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*") == ""


def test_a_failed_start_undo_keeps_the_cause_and_runs_every_step(repo, fake_tmux, monkeypatch):
    monkeypatch.setattr(tmux, "new_session", _fail)
    monkeypatch.setattr(providers.base, "remove_config_dir", _locked)
    with pytest.raises(tmux.TmuxError, match="command too long") as error:
        runtime.start_session(str(repo), "s", None, provider="claude")
    assert _undo_notes(error.value) == [
        "undo of the start of s: remove the supervisor's config failed: OperationalError: "
        "database is locked"
    ]
    assert state.get_session("s") is None  # the next step ran


@pytest.mark.parametrize("resumed", [False, True])
def test_a_start_whose_undo_fails_raises_the_cause(repo, fake_tmux, monkeypatch, resumed):
    if resumed:
        runtime.start_session(str(repo), "s", None, provider="claude")
        runtime.stop_session("s")
    monkeypatch.setattr(tmux, "new_session", _fail)
    monkeypatch.setattr(state, "fail_resume" if resumed else "delete_session", _locked)
    with pytest.raises(tmux.TmuxError, match="command too long") as error:
        runtime.start_session(str(repo), "s", None, provider="claude")
    step = "stop the session again" if resumed else "forget the session"
    assert _undo_notes(error.value) == [
        f"undo of the start of s: {step} failed: OperationalError: database is locked"
    ]
    assert f"s: undo of the start of s: {step} failed" in (state.home() / "loop.log").read_text()
    assert not (state.home() / "agents" / "s" / "supervisor").exists()


@pytest.mark.parametrize("resumed", [False, True])
def test_a_start_that_loses_the_race_leaves_the_running_session_alone(
    repo, fake_tmux, monkeypatch, resumed
):
    """Two `lado start` of one name at once: both see the same stored session, the other
    one starts first."""
    if resumed:
        runtime.start_session(str(repo), "s", None, provider="claude")
        runtime.stop_session("s")
    seen = state.get_session("s")
    runtime.start_session(str(repo), "s", None, provider="claude")  # the other `lado start`
    with monkeypatch.context() as m:
        m.setattr(state, "get_session", lambda name: seen)
        with pytest.raises(runtime.LadoError, match='session "s" is already running'):
            runtime.start_session(str(repo), "s", None, "kilo")
    sess = state.get_session("s")
    assert (sess.provider, sess.stopped_at) == ("claude", None)
    assert state.get_agent("s", "supervisor") is not None
    assert (state.home() / "agents" / "s" / "supervisor").exists()


def test_resume_refuses_another_repo(repo, tmp_path, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    other = agent_helpers.init_repo(tmp_path / "other")
    with pytest.raises(runtime.LadoError, match=f'session "s" was started in {repo}') as error:
        runtime.start_session(str(other), "s", None, provider="claude")
    assert "lado forget s" in str(error.value) and "--name" in str(error.value)
    assert state.get_session("s").stopped_at


def test_resume_replaces_the_settings_given_and_keeps_the_others(repo, fake_tmux, team_kit):
    runtime.start_session(str(repo), "s", "plan", kit_names=["default", "team"], provider="claude")
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None, "kilo", without=["skill:style"])
    assert started.changes == ["provider: claude -> kilo", "without: none -> skill:style"]
    sess = state.get_session("s")
    assert (sess.provider, sess.kits, sess.without, sess.permission_mode) == (
        "kilo",
        ["default", "team"],
        ["skill:style"],
        "plan",
    )
    assert (
        state.list_events("s")[-2].detail
        == "provider: claude -> kilo; without: none -> skill:style"
    )
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None, kit_names=["default"], without=[])
    assert started.changes == ["kits: default, team -> default", "without: skill:style -> none"]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def team_kit(repo):
    """A project kit on top of the default kit: a reviewer role, two skills, an MCP server."""
    kit = repo / ".lado" / "kits" / "team"
    _write(kit / "kit.yaml", "name: team\nversion: 1.0.0\n")
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
    started = runtime.start_session(
        str(repo),
        "s",
        None,
        kit_names=["default", "team"],
        without=["skill:style"],
        provider="claude",
    )
    sess = started.session
    assert (started.lead, started.warnings) == ("lead: supervisor of kit default", [])
    assert (sess.kits, sess.without) == (["default", "team"], ["skill:style"])
    stored = state.get_session("s")
    assert (stored.kits, stored.without) == (["default", "team"], ["skill:style"])
    assert state.get_agent("s", "supervisor").role == "supervisor"
    cmd = fake_tmux[0][-1]
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert prompt.startswith("You are the supervisor.")  # the role from the default kit
    assert 'agent "supervisor" in LADO session "s"' in prompt
    assert "`role` picks the kind of worker; required: this session has several. Roles:" in prompt
    assert "  - reviewer (kit team): reviews branches" in prompt
    assert "  - worker (kit default): " in prompt
    # The supervisor lists no skills, so it gets all of them except the one switched off.
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]


def test_spawn_worker_with_role_and_without(repo, fake_tmux, team_kit, monkeypatch):
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
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
    templates = {"TOKEN": "${DB_TOKEN}"}
    wrapped = mcp_exec.wrap("db", [f"{team_kit.resolve()}/db.sh"], templates)
    assert [mcp["db"]["command"], *mcp["db"]["args"]] == wrapped
    assert mcp["db"]["env"] == {}
    # The worker role gets all skills; this one without the MCP server it does not have.
    runtime.spawn_worker("s", "t", role="worker", without=["skill:style"])
    cmd = fake_tmux[-1][-1]
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]
    runtime.spawn_worker("s", "t", role="reviewer", without=["mcp:db"])
    mcp = json.loads(open(fake_tmux[-1][-1][fake_tmux[-1][-1].index("--mcp-config") + 1]).read())
    assert list(mcp["mcpServers"]) == ["lado"]


def test_kit_mcp_variables_come_from_the_agents_environment(repo, fake_tmux, team_kit, monkeypatch):
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    monkeypatch.delenv("DB_TOKEN", raising=False)  # set only by the user's shell
    path = os.environ["PATH"]
    monkeypatch.setattr(agent_env, "resolve", lambda: {"PATH": path, "DB_TOKEN": "from-shell"})
    runtime.spawn_worker("s", "review it", role="reviewer")
    env, _ = agent_helpers.launched(fake_tmux[-1])
    assert env["DB_TOKEN"] == "from-shell"  # the wrapper's CLI gets it from there


@pytest.mark.parametrize("provider", ["claude", "kilo", "opencode"])
def test_kit_mcp_secrets_are_in_no_file_lado_leaves(
    repo, fake_tmux, team_kit, monkeypatch, lado_home, provider
):
    monkeypatch.setenv("DB_TOKEN", "s3cr3t")
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider=provider)
    runtime.spawn_worker("s", "review it", role="reviewer", name="r")
    env, _ = agent_helpers.launched(fake_tmux[-1])
    for name, value in env.items():
        if name.endswith("_CONFIG_CONTENT"):
            assert "s3cr3t" not in value
    found = []
    for path in (lado_home / "agents").rglob("*"):
        if path.is_file() and path.name != "env.json" and "s3cr3t" in path.read_text():
            found.append(path)
    assert found == []
    config = providers.base.config_path(state.get_agent("s", "r"))
    text = "\n".join(p.read_text() for p in config.glob("*.json") if p.name != "env.json")
    assert "lado.mcp_exec" in text
    assert "${" not in text and "{env:" not in text
    env_files = list((lado_home / "agents").rglob("env.json"))
    assert [f.stat().st_mode & 0o777 for f in env_files] == [0o600, 0o600]


def test_spawn_worker_errors_leave_nothing_behind(repo, fake_tmux, team_kit, monkeypatch):
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    monkeypatch.delenv("DB_TOKEN", raising=False)
    with pytest.raises(kits.KitError, match="environment variable DB_TOKEN is not set"):
        runtime.spawn_worker("s", "t", role="reviewer")
    with pytest.raises(kits.KitError, match='no worker role "boss"'):
        runtime.spawn_worker("s", "t", role="boss")
    with pytest.raises(kits.KitError, match="no such skill"):
        runtime.spawn_worker("s", "t", role="worker", without=["skill:nope"])
    with pytest.raises(
        kits.KitError, match="role is required: this session has several worker roles: worker, "
    ):
        runtime.spawn_worker("s", "t")
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert not (repo / ".lado" / "worktrees").exists()


def test_spawn_worker_takes_the_only_role(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    cmd = fake_tmux[0][-1]
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert '`role` picks the kind of worker; it may be left out: "worker" is the only one.' in (
        prompt
    )
    assert runtime.spawn_worker("s", "t").role == "worker"


def test_a_worker_gets_its_role_from_an_installed_kit(tmp_path, repo, fake_tmux):
    """An installed kit is a row in lado.db; a running session reads it at each spawn."""
    work = agent_helpers.init_repo(tmp_path / "team-kit")
    agent = "---\nname: dev\ndescription: d\n---\n{text}\n"
    files = {"kit.yaml": "name: team\nversion: 1.0.0\n", "agents/dev.md": agent.format(text="v1")}
    url = agent_helpers.publish(work, files, tag="v1.0.0")
    kits.install(kits.plan_add(url))
    assert not (state.home() / "kits").exists()

    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    runtime.spawn_worker("s", "t", role="dev")
    assert _prompt(fake_tmux[-1][-1]).startswith("v1")

    files = {"kit.yaml": "name: team\nversion: 1.1.0\n", "agents/dev.md": agent.format(text="v2")}
    agent_helpers.publish(work, files, tag="v1.1.0")
    kits.install(kits.plan_update("team"))
    assert runtime.spawn_worker("s", "t", role="dev").name == "dev-2"
    assert _prompt(fake_tmux[-1][-1]).startswith("v2")


def test_a_kit_supervisor_leads_the_session(repo, fake_tmux, team_kit):
    _write(team_kit / "kit.yaml", "name: team\nversion: 1.0.0\nsupervisor: boss\n")
    _write(team_kit / "agents" / "boss.md", "---\nname: boss\ndescription: d\n---\nYou lead.\n")
    started = runtime.start_session(str(repo), "s", None, kit_names=["team"], provider="claude")
    assert started.lead == "lead: boss of kit team"
    assert state.get_agent("s", "supervisor").role == "boss"
    cmd = fake_tmux[0][-1]
    assert cmd[cmd.index("--append-system-prompt") + 1].startswith("You lead.")
    started = runtime.start_session(
        str(repo), "t", None, kit_names=["default", "team"], provider="claude"
    )
    assert started.lead == (
        "lead: LADO's built-in supervisor (kits default and team each have a supervisor)"
    )
    assert [w.split(" (")[0].split(":")[0] for w in started.warnings] == [
        "kit default's supervisor leads as LADO's built-in supervisor",
        "kit team's supervisor does not lead",
        "kit team's supervisor lists no skills",
    ]


def test_start_errors_leave_no_session(repo, fake_tmux):
    with pytest.raises(kits.KitError, match='kit "nope" not found'):
        runtime.start_session(str(repo), "s", None, kit_names=["nope"], provider="claude")
    with pytest.raises(kits.KitError, match="kit default has no agent nope"):
        runtime.start_session(
            str(repo), "s", None, without=["agent:nope@default"], provider="claude"
        )
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
        runtime.start_session(str(repo), "s", None, "noskills", kit_names=["default", "team"])
    runtime.start_session(
        str(repo), "s", None, "noskills", ["default", "team"], ["skill:style", "skill:checklist"]
    )
    assert agent_helpers.launched(fake_tmux[0])[1] == ["noskills"]


def test_git_exclude_keeps_project_kits_visible(repo, fake_tmux, team_kit):
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("# mine\n/.lado/\n")  # what LADO 0.3 wrote
    runtime.start_session(str(repo), "s", None, provider="claude")
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


def test_work_state_tells_how_a_workers_branch_stands_against_the_repo(repo, fake_tmux):
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    work = runtime.work_state("s", "w1")
    assert (work.branch, work.base, work.ahead, work.behind, work.uncommitted) == (
        "lado/s/w1",
        "main",
        0,
        0,
        0,
    )
    _commit(worker.cwd, "one.txt")
    _commit(worker.cwd, "two.txt")
    _commit(str(repo), "on-main.txt")
    Path(worker.cwd, "untracked.txt").write_text("x")
    Path(worker.cwd, "one.txt").write_text("changed")
    work = runtime.work_state("s", "w1")
    assert (work.ahead, work.behind, work.uncommitted) == (2, 1, 2)
    head = runtime.git(worker.cwd, "rev-parse", "HEAD")
    assert (work.last_commit.sha, work.last_commit.subject) == (head, "add two.txt")
    assert work.last_commit.at.tzinfo is not None


def test_work_state_reads_the_time_of_a_commit_made_in_utc(repo, fake_tmux, monkeypatch):
    # git 2.45+ writes such a time with "Z", which Python 3.10's fromisoformat refuses.
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-04T11:00:00 +0000")
    _commit(worker.cwd)
    at = runtime.work_state("s", "w1").last_commit.at
    assert at == datetime.datetime(2026, 10, 4, 11, 0, tzinfo=datetime.timezone.utc)
    assert runtime.finish_preview("s", "w1").refused.startswith("branch lado/s/w1")


def test_work_state_refuses_an_agent_without_a_branch(repo, fake_tmux):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match="works in the repo, not on a branch of its own"):
        runtime.work_state("s", "supervisor")
    with pytest.raises(runtime.LadoError, match='no agent "w9"'):
        runtime.work_state("s", "w9")


def test_finish_preview_says_what_finishing_a_worker_would_do_and_changes_nothing(repo, fake_tmux):
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    preview = runtime.finish_preview("s", "w1")
    assert (preview.removes_worktree, preview.refused, preview.work.ahead) == (True, None, 0)
    _commit(worker.cwd)
    preview = runtime.finish_preview("s", "w1")
    assert preview.refused == (
        f"branch lado/s/w1 is not merged into main (the current branch of {repo}); "
        "merge it first, or finish with discard to throw its work away"
    )
    assert preview.work.ahead == 1
    assert state.get_agent("s", "w1") is not None and Path(worker.cwd).exists()
    for name, error in [("supervisor", "lado stop s"), ("w9", 'no worker "w9"')]:
        with pytest.raises(runtime.LadoError, match=re.escape(error)):
            runtime.finish_preview("s", name)


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
    runtime.start_session(str(repo), "s", None, provider="claude")
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


@pytest.mark.parametrize(
    ("queue", "send"),
    [
        ("queue_message", lambda question: runtime.send_message("s", "supervisor", "w1", "late")),
        ("queue_with_copy", lambda question: runtime.write_as_human("s", "late", to="w1")),
        ("reply_to_question", lambda question: runtime.answer_question("s", question.id, "yes")),
    ],
    ids=["send_message", "write_as_human", "answer_question"],
)
def test_a_message_queued_while_the_worker_is_finished_reaches_nobody(
    repo, fake_tmux, monkeypatch, queue, send
):
    question = _asked(repo)
    store = getattr(state, queue)

    def finished_first(*args, **kwargs):
        # finish_worker runs after the sender found w1 running, before the message is stored
        runtime.finish_worker("s", "w1", discard=True)
        return store(*args, **kwargs)

    monkeypatch.setattr(state, queue, finished_first)
    with pytest.raises(
        runtime.LadoError, match='^no running agent "w1"; running agents: supervisor'
    ):
        send(question)
    monkeypatch.setattr(state, queue, store)
    runtime.spawn_worker("s", "new task", name="w1")
    assert state.take_pending("s", "w1", state.SENT, state.BUSY) == []
    assert state.read_messages("s", "w1") == []


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
    runtime.start_session(str(repo), "old", None, provider="claude")
    runtime.start_session(str(repo), "other", None, provider="claude")
    runtime.start_session(str(repo), "gone", None, provider="claude")
    runtime.stop_session("gone")
    tmux.kill_session("other")  # its tmux server died without `lado stop`
    agent_helpers.previous_schema()
    with pytest.raises(runtime.LadoError) as refused:
        runtime.migrate_if_safe()
    message = str(refused.value)
    assert f"schema version {state.SCHEMA_VERSION - 1}" in message
    assert 'running sessions: "old"' in message
    assert "other" not in message and "gone" not in message
    assert "`lado stop --all`" in message
    assert state.pending_migration() is not None  # nothing migrated


def test_migration_goes_ahead_with_no_session_running(repo, fake_tmux):
    runtime.start_session(str(repo), "old", None, provider="claude")
    runtime.stop_session("old")
    agent_helpers.previous_schema()
    assert state.pending_migration() is not None
    runtime.migrate_if_safe()
    assert state.pending_migration() is None
    runtime.migrate_if_safe()  # nothing pending: nothing to do
    assert state.get_session("old").stopped_at


def _database() -> bytes:
    """lado.db with its WAL folded in: equal bytes mean nothing was written in between."""
    return agent_helpers.database()


def _spy_migrate(monkeypatch, calls):
    """Record state.migrate in the tmux calls, to see it in order with the kills."""
    migrate = state.migrate
    monkeypatch.setattr(state, "migrate", lambda: calls.append(("migrate",)) or migrate())


def test_stopping_one_of_two_running_sessions_on_an_older_schema_is_refused(repo, fake_tmux):
    runtime.start_session(str(repo), "a", None, provider="claude")
    runtime.start_session(str(repo), "b", None, provider="claude")
    agent_helpers.previous_schema()
    before, calls = _database(), len(fake_tmux)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.stop_session("a")
    assert "`lado stop --all`" in str(refused.value)
    assert '"b"' in str(refused.value)
    assert fake_tmux[calls:] == []  # no session killed
    assert _database() == before


def test_stopping_the_only_running_session_on_an_older_schema_kills_migrates_and_marks(
    repo, fake_tmux, monkeypatch
):
    runtime.start_session(str(repo), "a", None, provider="claude")
    runtime.start_session(str(repo), "gone", None, provider="claude")
    tmux.kill_session("gone")  # its tmux server died: not running
    agent_helpers.previous_schema()
    _spy_migrate(monkeypatch, fake_tmux)
    calls = len(fake_tmux)
    runtime.stop_session("a")
    assert fake_tmux[calls:] == [("kill_session", "a"), ("migrate",), ("close_viewers", "a")]
    assert state.pending_migration() is None
    assert state.get_session("a").stopped_at
    assert state.SESSION_GONE not in [e.kind for e in state.list_events("a")]
    assert not state.get_session("gone").stopped_at  # only the one asked for


def test_stopping_an_unknown_session_on_an_older_schema(repo, fake_tmux):
    runtime.start_session(str(repo), "a", None, provider="claude")
    agent_helpers.previous_schema()
    before = _database()
    with pytest.raises(runtime.LadoError) as refused:
        runtime.stop_session("typo")
    assert 'unknown or stopped session "typo"' in str(refused.value)
    assert "`lado stop --all`" in str(refused.value)
    assert _database() == before
    runtime.stop_session("a")
    # With no session running it migrates, then refuses as a stop always does.
    agent_helpers.previous_schema()
    with pytest.raises(runtime.LadoError, match='unknown session "typo"'):
        runtime.stop_session("typo")
    assert state.pending_migration() is None


def test_stop_all_on_an_older_schema_kills_all_then_migrates_then_marks(
    repo, fake_tmux, monkeypatch
):
    for name in ("a", "b", "gone", "stopped"):
        runtime.start_session(str(repo), name, None, provider="claude")
    tmux.kill_session("gone")
    runtime.stop_session("stopped")
    agent_helpers.previous_schema()
    _spy_migrate(monkeypatch, fake_tmux)
    calls = len(fake_tmux)
    assert _stop_all() == ["a", "b", "gone"]
    assert fake_tmux[calls:] == [
        ("kill_session", "a"),
        ("kill_session", "b"),
        ("migrate",),
        ("close_viewers", "a"),
        ("close_viewers", "b"),
        ("close_viewers", "gone"),
    ]
    assert state.pending_migration() is None
    assert all(state.get_session(n).stopped_at for n in ("a", "b", "gone"))
    # A session found gone gets its session_gone; the ones it killed do not.
    assert state.SESSION_GONE in [e.kind for e in state.list_events("gone")]
    assert state.SESSION_GONE not in [e.kind for e in state.list_events("a")]


def test_stop_all_stops_every_session_not_stopped(repo, fake_tmux):
    for name in ("a", "b"):
        runtime.start_session(str(repo), name, None, provider="claude")
    tmux.kill_session("b")
    assert _stop_all() == ["a", "b"]
    assert all(state.get_session(n).stopped_at for n in ("a", "b"))
    assert _stop_all() == []


def test_stop_all_does_not_migrate_while_a_loop_runs_on(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "a", None, provider="claude")
    agent_helpers.previous_schema()
    monkeypatch.setattr(loop, "wait_stopped", lambda session: False)
    with pytest.raises(runtime.LadoError) as refused:
        _stop_all()
    assert 'loop of session "a"' in str(refused.value)
    assert "`lado stop --all`" in str(refused.value)
    assert state.pending_migration() == (state.SCHEMA_VERSION - 1, ["a"])
    monkeypatch.setattr(loop, "wait_stopped", lambda session: True)
    assert _stop_all() == ["a"]  # again, once it ended


@pytest.mark.parametrize("older", [False, True])
def test_stop_all_goes_on_past_a_session_it_cannot_stop_and_names_it(
    repo, fake_tmux, monkeypatch, older
):
    for name in ("a", "b", "c"):
        runtime.start_session(str(repo), name, None, provider="claude")
    if older:
        agent_helpers.previous_schema()
    mark = state.stop_session

    def locked(session, gone=False):
        if session == "b":
            raise sqlite3.OperationalError("database is locked")
        return mark(session, gone)

    monkeypatch.setattr(state, "stop_session", locked)
    reported = []
    with pytest.raises(runtime.LadoError) as failed:
        runtime.stop_all(lambda name, stopped: reported.append(name))
    assert reported == ["a", "c"]  # each one as soon as it is stopped
    assert str(failed.value) == (
        'could not stop session "b": OperationalError: database is locked; stopped: "a", "c"'
    )
    assert [bool(state.get_session(n).stopped_at) for n in "abc"] == [True, False, True]


def _stop_all() -> list[str]:
    """The sessions stop_all stopped, in the order it reported them."""
    reported = []
    runtime.stop_all(lambda name, stopped: reported.append(name))
    return reported


def test_session_status_tells_the_four_states(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
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
    runtime.start_session(str(repo), "s", None, provider="claude")
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
    message = state.list_messages("s")[0]
    assert (message.recipient, message.summary, message.body) == ("w1", summary, body)


def test_the_supervisor_gets_a_one_line_copy_of_the_humans_text_to_a_worker(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    assert runtime.write_as_human("s", "use the other port\nit is 8080", to="w1").startswith(
        "queued; w1 is starting"
    )
    mine, copy = state.list_messages("s")
    assert (mine.sender, mine.recipient) == ("human", "w1")
    assert (copy.sender, copy.recipient, copy.body) == ("lado", "supervisor", "")
    assert copy.summary == f"human wrote to w1: use the other port (#{mine.id})"
    assert fake_tmux[-1] == ("send_text", "s", "supervisor", f"[from lado] {copy.summary}")


def test_a_stopped_supervisor_gets_no_copy_and_the_worker_its_message(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    state.set_status("s", "supervisor", state.STOPPED)
    assert runtime.write_as_human("s", "use the other port", to="w1") == "sent"
    [mine] = state.list_messages("s")
    assert (mine.recipient, mine.state) == ("w1", state.SENT)
    assert fake_tmux[-1] == ("send_text", "s", "w1", "[from human] use the other port")


def test_the_copy_of_a_long_text_stays_one_short_line(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.write_as_human("s", "x" * 250, to="w1")
    mine, copy = state.list_messages("s")
    assert len(copy.summary) == state.SUMMARY_LIMIT
    assert copy.summary.startswith("human wrote to w1: xxx")
    assert copy.summary.endswith(f"… (#{mine.id})")


def test_no_copy_of_the_humans_text_to_the_supervisor_or_of_answers(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.write_as_human("s", "hello")
    first = runtime.ask_human("s", "w1", "Merge now?", choices=["yes", "no"])
    second = runtime.ask_human("s", "w1", "Which port?")
    asked = [m.id for m in state.list_messages("s") if m.kind == state.QUESTION]
    assert first and second
    runtime.answer_question("s", asked[0], choice="yes")
    runtime.dismiss_question("s", asked[1])
    assert [m.sender for m in state.list_messages("s") if m.recipient == "supervisor"] == ["human"]


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
    _hook("Stop", "supervisor", CONTINUED)
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
    _hook("Stop", "supervisor", CONTINUED)  # that turn wrote nothing to the human
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
    state.add_agent(
        state.Agent("s", "w1", "worker", "/w", "b", "t", state.STOPPED, provider="claude")
    )
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


@pytest.fixture
def boss_kit(repo):
    """Kit boss with a supervisor that names its skill notes (with a script, and a link to a
    file outside the kit) and has an MCP server; with the default kit, it does not lead."""
    kit = repo / ".lado" / "kits" / "boss"
    _write(kit / "kit.yaml", "name: boss\nversion: 1.0.0\nsupervisor: chief\n")
    _write(
        kit / "agents" / "chief.md",
        "---\nname: chief\ndescription: 'Chief: leads \"boss\" work'\nskills: [notes]\n"
        "mcp: {db: {command: [db]}}\n---\nYou lead boss work.\n",
    )
    _write(kit / "agents" / "dev.md", "---\nname: dev\ndescription: develops\n---\nDevelop.\n")
    notes = kit / "skills" / "notes"
    _write(notes / "SKILL.md", "---\nname: notes\ndescription: d\n---\nTake notes.\n")
    _write(notes / "scripts" / "run.sh", "echo hi\n")
    _write(repo.parent / "outside.txt", "outside\n")
    (notes / "outside.txt").symlink_to(repo.parent / "outside.txt")
    return kit


def _lead_dir(lado_home, session="s"):
    return lado_home / "agents" / session / "supervisor"


def test_the_built_in_lead_gets_a_lead_skill_per_kit_supervisor(
    repo, fake_tmux, boss_kit, lado_home
):
    runtime.start_session(str(repo), "s", None, kit_names=["default", "boss"], provider="claude")
    config = _lead_dir(lado_home)
    skill_md = config / "lead-skills" / "lead-boss" / "SKILL.md"
    front, body = skill_md.read_text().split("---\n")[1:]
    assert yaml.safe_load(front) == {
        "name": "lead-boss",
        "description": "How kit boss wants its work led: read it before you take a task for "
        'its roles or flows. Chief: leads "boss" work',
    }
    files = config / "lead-files"
    assert body == (
        "You lead boss work.\n\n"
        "## Skills this text names\n"
        "When the text above names one of these skills, read it from here (they are kit "
        "boss's versions, not your own skills):\n"
        f"- notes: {files / 'boss' / 'notes' / 'SKILL.md'}\n\n"
        "MCP servers of this kit's supervisor are not available to you: db.\n"
    )
    copy = files / "boss" / "notes"
    assert (copy / "SKILL.md").read_text().endswith("Take notes.\n")
    assert (copy / "scripts" / "run.sh").is_file()
    # A link in the skill is copied as its file: the lead may read the copy only.
    assert not (copy / "outside.txt").is_symlink()
    assert (copy / "outside.txt").read_text() == "outside\n"
    # Only the lead skill itself is a SKILL.md where skills are looked up.
    assert list((config / "lead-skills").rglob("SKILL.md")) == [skill_md]
    _, cmd = agent_helpers.launched(fake_tmux[0])
    added = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--add-dir"]
    assert added == [str(config / "skills"), str(files)]
    link = config / "skills" / ".claude" / "skills" / "lead-boss"
    assert link.resolve() == skill_md.parent
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert (
        "Kits whose own supervisor does not lead: boss. Read the skill lead-<kit> before you "
        "take a task for that kit's roles or flows.\n"
    ) in prompt


def test_lead_skills_are_written_anew_at_each_start(repo, fake_tmux, boss_kit, lado_home):
    runtime.start_session(str(repo), "s", None, kit_names=["default", "boss"], provider="claude")
    files = _lead_dir(lado_home) / "lead-files"
    _write(files / "boss" / "notes" / "stale.md", "old\n")
    _write(_lead_dir(lado_home) / "lead-skills" / "lead-gone" / "SKILL.md", "old\n")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    assert not (files / "boss" / "notes" / "stale.md").exists()
    assert not (_lead_dir(lado_home) / "lead-skills" / "lead-gone").exists()
    assert (files / "boss" / "notes" / "SKILL.md").is_file()
    # A kit supervisor that leads gets no lead skills.
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None, kit_names=["boss"])
    assert not files.exists() and not (_lead_dir(lado_home) / "lead-skills").exists()


def test_a_lead_skill_says_when_its_supervisor_lists_no_skills(repo, fake_tmux, lado_home):
    kit = repo / ".lado" / "kits" / "boss"
    _write(kit / "kit.yaml", "name: boss\nversion: 1.0.0\nsupervisor: chief\n")
    _write(kit / "agents" / "chief.md", "---\nname: chief\ndescription: c\n---\nLead.\n")
    runtime.start_session(str(repo), "s", None, kit_names=["default", "boss"], provider="claude")
    skill_md = _lead_dir(lado_home) / "lead-skills" / "lead-boss" / "SKILL.md"
    assert skill_md.read_text().endswith("Lead.\n\nThis kit's supervisor lists no skills.\n")
    _write(kit / "agents" / "chief.md", "---\nname: chief\ndescription: c\nskills: []\n---\nL.\n")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    assert skill_md.read_text().endswith("---\nL.\n")


def test_a_lost_start_does_not_touch_the_running_leads_files(
    repo, fake_tmux, boss_kit, lado_home, monkeypatch
):
    config = _lead_dir(lado_home)
    _write(config / "lead-files" / "boss" / "notes" / "SKILL.md", "the running lead's\n")
    monkeypatch.setattr(state, "add_session", lambda sess: False)  # another start took it
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(
            str(repo), "s", None, kit_names=["default", "boss"], provider="claude"
        )
    assert (config / "lead-files" / "boss" / "notes" / "SKILL.md").read_text() == (
        "the running lead's\n"
    )
    assert not (config / "lead-skills").exists()


@pytest.mark.parametrize("target", ["missing.txt", "loop"])
def test_a_skill_that_cannot_be_copied_names_the_skill_and_its_kit(
    repo, fake_tmux, boss_kit, lado_home, target
):
    (boss_kit / "skills" / "notes" / "loop").symlink_to(boss_kit / "skills" / "notes" / target)
    with pytest.raises(runtime.LadoError, match="cannot copy skill notes of kit boss"):
        runtime.start_session(
            str(repo), "s", None, kit_names=["default", "boss"], provider="claude"
        )
    assert state.get_session("s") is None and not _lead_dir(lado_home).exists()


def test_a_provider_without_skills_names_the_way_out_of_lead_skills(
    repo, fake_tmux, boss_kit, monkeypatch
):
    monkeypatch.setitem(providers._PROVIDERS, "noskills", _NoSkills())
    kit_names = ["default", "boss"]
    with pytest.raises(runtime.LadoError) as e:
        runtime.start_session(str(repo), "s", None, "noskills", kit_names, ["skill:notes"])
    assert str(e.value) == (
        'No Skills CLI cannot load skills, but agent "supervisor" (supervisor) gets the lead '
        "skill lead-boss; switch its kit's supervisor off with --without agent:chief@boss"
    )
    runtime.start_session(
        str(repo), "s", None, "noskills", kit_names, ["skill:notes", "agent:chief@boss"]
    )


def test_kit_users_are_the_sessions_that_name_the_kit_split_by_status(
    tmp_path, lado_home, monkeypatch
):
    status = runtime.SessionStatus
    sessions = {
        "a": (["tool"], status.RUNNING),
        "b": (["default", "tool"], status.LOOP_DOWN),
        "c": (["tool"], status.STOPPED),
        "d": (["tool"], status.TMUX_GONE),
        "e": (["default"], status.RUNNING),
        "f": (["tool"], status.RUNNING),  # its project has a kit "tool" of its own
    }
    for name, (kit_names, _) in sessions.items():
        (tmp_path / name).mkdir()
        state.add_session(
            state.Session(name, str(tmp_path / name), None, kits=kit_names, provider="claude")
        )
    (tmp_path / "f" / ".lado" / "kits" / "tool").mkdir(parents=True)
    monkeypatch.setattr(runtime, "session_status", lambda sess: sessions[sess.name][1])
    users = runtime.kit_users("tool")
    assert users == runtime.KitUsers(running=["a", "b"], stopped=["c", "d"])
    assert users.running_line("tool") == (
        'running sessions a and b use kit "tool": their new agents and flow runs fail to '
        "start until it is added again; the agents running now keep working"
    )
    assert users.stopped_line("tool") == (
        'stopped sessions c and d use kit "tool" too: a resume needs it'
    )
    one = runtime.KitUsers(running=["a"], stopped=["c"])
    assert one.running_line("tool").startswith('running session a uses kit "tool": its new ')
    assert one.stopped_line("tool") == 'stopped session c uses kit "tool" too: a resume needs it'
    none = runtime.kit_users("nope")
    assert none == runtime.KitUsers([], [])
    assert none.running_line("nope") is None and none.stopped_line("nope") is None


# The time a session ran (runtime.session_time) and the end of one whose tmux died.


def _utc(at: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(at).replace(tzinfo=datetime.timezone.utc)


def _set_created(session, at):
    with state.connect() as db:
        db.execute("UPDATE sessions SET created_at = ? WHERE name = ?", (at, session))


def _set_events(session, kind, *times):
    """Give the session's events of `kind`, oldest first, these times."""
    with state.connect() as db:
        ids = [
            r[0]
            for r in db.execute(
                "SELECT id FROM events WHERE session = ? AND kind = ? ORDER BY id", (session, kind)
            )
        ]
        db.executemany(
            "UPDATE events SET created_at = ? WHERE id = ?", zip(times, ids, strict=True)
        )


def _set_all_events(session, at):
    with state.connect() as db:
        db.execute("UPDATE events SET created_at = ? WHERE session = ?", (at, session))


def _set_seen(session, at):
    with state.connect() as db:
        db.execute(
            "UPDATE agents SET seen_at = ? WHERE session = ?", (_utc(at).timestamp(), session)
        )


def _gone(session):
    return [e.created_at for e in state.list_events(session) if e.kind == state.SESSION_GONE]


def test_a_new_session_runs_since_it_was_created(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    _set_created("s", "2026-10-05 10:00:00")
    sess = state.get_session("s")
    assert sess.created_at == "2026-10-05 10:00:00"
    assert runtime.session_time(sess) == runtime.SessionTime(0, _utc("2026-10-05 10:00:00"))


def test_a_session_ran_between_its_starts_and_stops(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    _set_created("s", "2026-10-05 10:00:00")
    _set_all_events("s", "2026-10-05 10:00:00.000")
    _set_events("s", state.SESSION_STOP, "2026-10-05 10:10:00.000", "2026-10-05 11:05:00.500")
    _set_events("s", state.SESSION_RESUME, "2026-10-05 11:00:00.000", "2026-10-05 12:00:00.000")
    running = runtime.session_time(state.get_session("s"))
    assert running == runtime.SessionTime(900, _utc("2026-10-05 12:00:00"))
    runtime.stop_session("s")
    _set_events(
        "s",
        state.SESSION_STOP,
        *["2026-10-05 10:10:00.000", "2026-10-05 11:05:00.500"],
        "2026-10-05 12:01:00.000",
    )
    assert runtime.session_time(state.get_session("s")) == runtime.SessionTime(960, None)
    assert _gone("s") == []


def _died(repo, fake_tmux, seen):
    """Session "s", created at 10:00, whose agents' latest hook ran at `seen` (none for
    None), and whose tmux server died then."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    _set_created("s", "2026-10-05 10:00:00")
    _set_all_events("s", "2026-10-05 10:05:00.000")
    if seen:
        _set_seen("s", seen)
    fake_tmux.append(("kill_session", "s"))


def test_a_resume_after_tmux_died_counts_no_time_after_the_last_sign_of_life(repo, fake_tmux):
    _died(repo, fake_tmux, "2026-10-05 10:20:00")
    gone = runtime.session_time(state.get_session("s"))
    assert gone == runtime.SessionTime(1200, None)
    runtime.start_session(str(repo), "s", None)
    assert _gone("s") == ["2026-10-05 10:20:00.000"]
    _set_events("s", state.SESSION_STOP, "2026-10-05 13:00:00.000")
    _set_events("s", state.SESSION_RESUME, "2026-10-05 13:00:00.000")
    resumed = runtime.session_time(state.get_session("s"))
    assert resumed == runtime.SessionTime(gone.ran_seconds, _utc("2026-10-05 13:00:00"))


def test_a_stop_after_tmux_died_counts_no_time_after_the_last_sign_of_life(repo, fake_tmux):
    _died(repo, fake_tmux, "2026-10-05 10:20:00")
    gone = runtime.session_time(state.get_session("s"))
    runtime.stop_session("s")
    assert _gone("s") == ["2026-10-05 10:20:00.000"]
    assert runtime.session_time(state.get_session("s")) == gone == runtime.SessionTime(1200, None)


def test_without_hooks_the_last_sign_of_life_is_the_sessions_latest_event(repo, fake_tmux):
    _died(repo, fake_tmux, None)
    assert runtime.session_time(state.get_session("s")) == runtime.SessionTime(300, None)
    runtime.stop_session("s")
    assert _gone("s") == ["2026-10-05 10:05:00.000"]
    assert runtime.session_time(state.get_session("s")) == runtime.SessionTime(300, None)


def test_a_stop_of_a_session_whose_tmux_runs_records_no_end_of_life(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    assert _gone("s") == []


@pytest.mark.parametrize("seen", [None, "2026-10-05 10:50:00"])
def test_a_last_sign_of_life_before_the_resume_makes_a_span_of_nothing(repo, fake_tmux, seen):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    _set_created("s", "2026-10-05 10:00:00")
    _set_all_events("s", "2026-10-05 10:05:00.000")
    _set_events("s", state.SESSION_STOP, "2026-10-05 10:10:00.000")
    _set_events("s", state.SESSION_RESUME, "2026-10-05 11:00:00.000")
    if seen:  # a hook of the agents of before the stop, say
        _set_seen("s", seen)
    fake_tmux.append(("kill_session", "s"))
    assert runtime.session_time(state.get_session("s")) == runtime.SessionTime(600, None)
    runtime.stop_session("s")
    assert runtime.session_time(state.get_session("s")) == runtime.SessionTime(600, None)


@pytest.mark.parametrize(
    ("url", "public"),
    [
        ("https://user:token@github.com/ladohq/lado.git", "https://github.com/ladohq/lado.git"),
        ("https://ghp_secret@github.com/ladohq/lado", "https://github.com/ladohq/lado"),
        ("ssh://git@github.com/ladohq/lado.git", "ssh://git@github.com/ladohq/lado.git"),
        ("ssh://u:p@host:2222/lado.git", "ssh://u@host:2222/lado.git"),
        ("git@github.com:ladohq/lado.git", "git@github.com:ladohq/lado.git"),
        ("/srv/git/lado.git", "/srv/git/lado.git"),
    ],
)
def test_public_remote_drops_what_may_be_a_secret(url, public):
    assert runtime.public_remote(url) == public


def test_branch_and_remote_of_a_repository_with_origin(repo):
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:ladohq/lado.git"],
        check=True,
    )
    assert (runtime.branch(str(repo)), runtime.remote(str(repo))) == (
        "main",
        "git@github.com:ladohq/lado.git",
    )


def test_no_remote_without_origin_and_no_branch_on_a_detached_head(repo):
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--detach"], check=True)
    assert (runtime.branch(str(repo)), runtime.remote(str(repo))) == (None, None)


@pytest.mark.parametrize(("value", "delays"), [(None, (15.0, 30.0, 60.0)), ("0.5,1", (0.5, 1.0))])
def test_the_retry_delays_are_lado_retry_delays_else_lado_s_own(value, delays):
    assert runtime.retry_delays_from(value) == delays


def _expecting_kits(repo):
    """Kit sdlc whose role analyst uses skill tracker, which it expects; kit tracker, without
    agents, has it."""
    base = repo / ".lado" / "kits"
    (base / "sdlc" / "agents").mkdir(parents=True)
    (base / "sdlc" / "kit.yaml").write_text(
        "name: sdlc\nversion: 1.0.0\nexpects:\n  skills: [tracker]\n"
    )
    (base / "sdlc" / "agents" / "analyst.md").write_text(
        "---\nname: analyst\ndescription: a\nskills: [tracker]\n---\nA.\n"
    )
    (base / "tracker" / "skills" / "tracker").mkdir(parents=True)
    (base / "tracker" / "kit.yaml").write_text("name: tracker\nversion: 1.0.0\n")
    (base / "tracker" / "skills" / "tracker" / "SKILL.md").write_text(
        "---\nname: tracker\ndescription: t\n---\n"
    )


def test_a_session_without_the_kit_an_expected_skill_needs_does_not_start(repo, fake_tmux):
    _expecting_kits(repo)
    with pytest.raises(kits.KitError) as exc:
        runtime.start_session(str(repo), "s", None, kit_names=["sdlc"], provider="claude")
    assert str(exc.value) == (
        'kit "sdlc" expects skill "tracker", which no kit of the session provides: add a kit '
        "that provides it with --kit <kit>"
    )
    assert state.get_session("s") is None and fake_tmux == []


def test_a_spawn_may_not_switch_off_a_skill_its_kit_expects(repo, fake_tmux):
    _expecting_kits(repo)
    runtime.start_session(str(repo), "s", None, kit_names=["sdlc", "tracker"], provider="claude")
    windows = len(fake_tmux)
    with pytest.raises(kits.KitError, match='agent "analyst" cannot run without it'):
        runtime.spawn_worker("s", "t", role="analyst", without=["skill:tracker"])
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert len(fake_tmux) == windows
