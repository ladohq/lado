import dataclasses
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import agent_helpers
import pytest
import yaml

from lado import (
    agent_env,
    artifacts,
    gui_session,
    hooks,
    kits,
    loop,
    model_servers,
    model_settings,
    providers,
    runs,
    runtime,
    state,
    telemetry,
    terminal,
    tmux,
)
from lado.providers import base


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


def test_the_last_sessions_provider_not_installed_falls_back_to_the_only_one(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    suggestion = runtime.suggested_provider(str(repo), _installed("opencode"))
    assert suggestion == runtime.Suggestion("opencode", runtime.ONLY_INSTALLED)
    assert suggestion.line() == "opencode (the only one installed)"


def test_a_new_session_with_several_providers_and_no_history_is_refused(repo, fake_tmux):
    with pytest.raises(runtime.LadoError) as error:
        runtime.start_session(str(repo), "s", None)
    assert str(error.value) == (
        "which agent CLI should the session run? Installed on the agents' PATH: "
        "claude, codex, kilo, opencode; give one with --provider NAME"
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

    def layers(project=None):
        calls.append(1)
        shell = {
            "PATH": str(fake_clis),
            "FROM_SHELL": "1",
            "LADO_AGENT": "parent",
            "KILO_DISABLE_AUTOUPDATE": "0",
        }
        return agent_env.Layers(shell, {}, {}, {})

    monkeypatch.setattr(agent_env, "layers", layers)
    return calls


def _broken_env(project=None):
    raise agent_env.AgentEnvError("your shell failed with exit status 1: zsh -ilc ...")


def _shell(monkeypatch, env):
    """The agents' layers with `env` as the login shell's, and no file layer."""
    monkeypatch.setattr(
        agent_env, "layers", lambda project=None: agent_env.Layers(dict(env), {}, {}, {})
    )


def test_manual_starts_and_resumes_claude_code_as_default(repo, fake_tmux, lado_home):
    runtime.start_session(str(repo), "s", "manual", provider="claude")
    assert state.get_session("s").permission_mode == "default"
    _, cmd = agent_helpers.launched(fake_tmux[0])
    assert cmd[cmd.index("--permission-mode") + 1] == "default"
    runtime.stop_session("s")
    with state.connect() as db:  # as 0.47 stored `lado start --permission-mode manual`
        db.execute("UPDATE sessions SET permission_mode = 'manual' WHERE name = 's'")
    runtime.start_session(str(repo), "s", None)
    assert state.get_session("s").permission_mode == "default"
    _, cmd = agent_helpers.launched(fake_tmux[-1])
    assert cmd[cmd.index("--permission-mode") + 1] == "default"


def test_a_resume_whose_environment_fails_leaves_the_session_as_it_was(
    repo, fake_tmux, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    before = len(fake_tmux)
    with monkeypatch.context() as m:
        m.setattr(agent_env, "layers", _broken_env)
        with pytest.raises(runtime.LadoError, match="your shell failed"):
            runtime.start_session(str(repo), "s", "plan")
    assert len(fake_tmux) == before
    sess = state.get_session("s")
    assert sess.stopped_at and sess.permission_mode is None
    assert state.list_messages("s") == []  # no "session resumed" for a resume that never was


def test_a_spawn_whose_environment_fails_leaves_no_worker(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
    monkeypatch.setattr(agent_env, "layers", _broken_env)
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
    _shell(monkeypatch, {"PATH": str(empty)})


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


def test_resume_true_refuses_an_unknown_session(repo, fake_tmux):
    with pytest.raises(runtime.NoSuchSession, match='unknown session "s"'):
        runtime.start_session(str(repo), "s", None, resume=True, provider="claude")
    assert state.get_session("s") is None


def _refusal(path: Path) -> runtime.FolderProblem:
    with pytest.raises(runtime.FolderProblem) as refused:
        runtime.check_repo(str(path))
    return refused.value


def _fake_git(tmp_path: Path, monkeypatch, script: str) -> Path:
    """A `git` on an otherwise empty PATH that runs `script` (sh) with git's arguments."""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text(f"#!/bin/sh\n{script}\n")
    git.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    return bin_dir


XCRUN = "xcrun: error: invalid active developer path (/Library/Developer/CommandLineTools)"


def test_git_version_names_the_path_when_there_is_no_git(tmp_path, monkeypatch):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    with pytest.raises(runtime.FolderProblem) as refused:
        runtime.git_version()
    assert refused.value.kind == "no_git"
    assert str(refused.value) == f"git is not installed or not on PATH ({empty})"
    assert refused.value.hint is not None


def test_git_version_tells_a_git_that_does_not_run(tmp_path, monkeypatch):
    _fake_git(tmp_path, monkeypatch, f"echo '{XCRUN}' >&2\necho 'more' >&2\nexit 1")
    with pytest.raises(runtime.FolderProblem) as refused:
        runtime.git_version()
    assert refused.value.kind == "git_broken"
    assert str(refused.value) == f"git does not run: {XCRUN}"


def test_git_version_gives_the_version_text(tmp_path, monkeypatch):
    _fake_git(tmp_path, monkeypatch, "echo 'git version 2.30.2'")
    assert runtime.git_version() == "git version 2.30.2"


def test_git_without_git_is_ladoerror_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(runtime.LadoError, match=r"^git is not installed or not on PATH \("):
        runtime.git(str(tmp_path), "status")


def test_check_repo_refuses_a_file(tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("x")
    refused = _refusal(file)
    assert (refused.kind, str(refused), refused.hint) == (
        "not_folder",
        f"{file} is a file, not a folder",
        None,
    )


def test_check_repo_reads_git_in_english(tmp_path, monkeypatch):
    # A translating git would hide "not a git repository" (Apple's git translates nothing,
    # so a fake one answers in German unless LC_ALL=C).
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    script = (
        'if [ "$1" = --version ]; then echo "git version 2.47.1"; exit 0; fi\n'
        'if [ "$LC_ALL" = C ]; then echo "fatal: not a git repository (or any parent)" >&2\n'
        'else echo "fatal: kein Git-Repository" >&2; fi\nexit 128'
    )
    _fake_git(tmp_path, monkeypatch, script)
    assert _refusal(tmp_path).kind == "not_repo"


def test_check_repo_without_git(tmp_path, monkeypatch):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    refused = _refusal(tmp_path)
    assert (refused.kind, str(refused)) == (
        "no_git",
        f"git is not installed or not on PATH ({empty})",
    )


def test_check_repo_with_a_git_that_does_not_run(tmp_path, monkeypatch):
    _fake_git(tmp_path, monkeypatch, f"echo '{XCRUN}' >&2\nexit 1")
    refused = _refusal(tmp_path)
    assert (refused.kind, str(refused)) == ("git_broken", f"git does not run: {XCRUN}")


def test_check_repo_when_git_refuses_the_folder(tmp_path, monkeypatch):
    dubious = "fatal: detected dubious ownership in repository at '/x'"
    script = (
        'if [ "$1" = --version ]; then echo "git version 2.47.1"; exit 0; fi\n'
        f'echo "{dubious}" >&2\necho "To add an exception..." >&2\nexit 128'
    )
    _fake_git(tmp_path, monkeypatch, script)
    refused = _refusal(tmp_path)
    assert (refused.kind, str(refused), refused.hint) == (
        "git_refused",
        f"git cannot read {tmp_path}: {dubious}",
        None,
    )


@pytest.mark.parametrize(
    ("system", "command", "sentence"),
    [
        ("Darwin", "xcode-select --install", "brew install git"),
        ("Linux", "sudo apt install git", "your distribution's package manager"),
    ],
)
def test_the_install_hint_is_this_systems(tmp_path, monkeypatch, system, command, sentence):
    monkeypatch.setattr(runtime.platform, "system", lambda: system)
    monkeypatch.setenv("PATH", str(tmp_path))
    refused = _refusal(tmp_path)
    assert refused.hint is not None
    assert refused.hint.command == command
    assert sentence in refused.hint.text


@pytest.mark.parametrize(
    ("system", "command"),
    [("Darwin", "xcode-select --install"), ("Linux", "sudo apt install --reinstall git")],
)
def test_the_hint_for_a_git_that_does_not_run(tmp_path, monkeypatch, system, command):
    monkeypatch.setattr(runtime.platform, "system", lambda: system)
    _fake_git(tmp_path, monkeypatch, f"echo '{XCRUN}' >&2\nexit 1")
    refused = _refusal(tmp_path)
    assert refused.hint is not None
    assert refused.hint.command == command


@pytest.mark.parametrize("provider", ["kilo", "opencode"])
def test_an_opencode_family_worker_gets_its_first_line_on_its_command_line(
    repo, fake_tmux, provider
):
    """Its TUI loses what is typed in right after its start (notice_on_argv): the line of
    its task is handed over at its launch, as typed, and confirmed as typed text."""
    cli = providers.get(provider)
    runtime.start_session(str(repo), "s", None, provider=provider)
    runtime.spawn_worker("s", "fix the bug;", name="w1")
    [task] = state.list_messages("s")
    line = f"[from lado] your task (#{task.id}, 3 lines: call read_messages)"
    _, argv = agent_helpers.launched(fake_tmux[-1])
    assert argv[argv.index("--prompt") + 1] == line
    assert not [a for a in argv if "fix the bug" in a]  # never a body
    assert (task.state, task.attempts, task.channel) == (state.SENT, 1, state.TYPED)
    assert state.get_agent("s", "w1").status == state.STARTING
    # Its start makes it idle; the batch it has is not typed in again.
    hooks.handle(cli, providers.Event(providers.SESSION_START), "s", "w1")
    assert state.get_agent("s", "w1").status == state.IDLE
    assert not [c for c in fake_tmux if c[0] == "send_text"]
    hooks.handle(cli, providers.Event(providers.PROMPT_SUBMIT, line), "s", "w1")
    assert state.list_messages("s")[0].state == state.DELIVERED
    assert state.get_agent("s", "w1").status == state.BUSY


def test_handle_records_the_model_before_the_status(repo, fake_tmux):
    cli = providers.get("opencode")
    runtime.start_session(str(repo), "s", None, provider="opencode")
    runtime.spawn_worker("s", "fix the bug", name="w1")
    hooks.handle(cli, providers.Event(providers.SESSION_START, model="claude-opus-5-5"), "s", "w1")
    agent = state.get_agent("s", "w1")
    assert (agent.model, agent.model_source, agent.status) == ("claude-opus-5-5", "cli", state.IDLE)
    hooks.handle(cli, providers.Event(providers.PROMPT_SUBMIT, effort="high"), "s", "w1")
    agent = state.get_agent("s", "w1")
    assert (agent.model, agent.effort, agent.status) == ("claude-opus-5-5", "high", state.BUSY)
    # An event that says its model runs the default effort: no name any more.
    default = providers.Event(providers.TURN_END, effort="")
    hooks.handle(cli, default, "s", "w1")
    assert state.get_agent("s", "w1").effort is None


class _FirstInput(providers.Provider):
    """A CLI that starts its session only when its first input is submitted (Codex CLI)."""

    name = "firstinput"
    title = "First Input CLI"
    permission_modes = ()
    capabilities = providers.Capabilities(
        status_events=True,
        permission_event=False,
        deliver_on_turn_end=True,
        skills=True,
        notice_on_argv=True,
        session_start_on_first_input=True,
    )

    def launch_command(self, agent, session, spec, notice=None):
        self.environ = spec.environ
        return providers.Launch(["firstinput", *([notice] if notice else [])], warnings=["w!"])

    def parse_event(self, native, payload):
        return None


@pytest.fixture
def first_input(monkeypatch, fake_clis):
    (fake_clis / "firstinput").write_text("#!/bin/sh\n")
    (fake_clis / "firstinput").chmod(0o755)
    cli = _FirstInput()
    monkeypatch.setitem(providers._PROVIDERS, cli.name, cli)
    return cli


def test_an_agent_that_starts_at_its_first_input_gets_one_from_lado(repo, fake_tmux, first_input):
    """With nothing in its queue, it would never start its session: LADO queues one line of
    its own, stored and on the command line like any first line, never a body."""
    started = runtime.start_session(str(repo), "s", None, provider="firstinput")
    [hello] = state.list_messages("s")
    assert (hello.sender, hello.recipient, hello.summary, hello.body) == (
        "lado",
        "supervisor",
        runtime.FIRST_INPUT,
        "",
    )
    assert (hello.state, hello.attempts, hello.channel) == (state.SENT, 1, state.TYPED)
    _, argv = agent_helpers.launched(fake_tmux[0])
    assert argv == ["firstinput", f"[from lado] {runtime.FIRST_INPUT}"]
    # The provider's launch warnings reach whoever starts it.
    assert "w!" in started.warnings
    # The provider reads the agent's environment, the one its window gets.
    env, _ = agent_helpers.launched(fake_tmux[0])
    assert first_input.environ["PATH"] == env["PATH"]


@pytest.mark.parametrize(
    ("prompt", "refused"),
    [
        ("  \n ", "the first message is empty"),
        (
            "x" * (runtime.MAX_MESSAGE + 1),
            f"the first message is {runtime.MAX_MESSAGE + 1} characters, "
            f"the limit is {runtime.MAX_MESSAGE}",
        ),
    ],
)
def test_a_bad_first_message_is_refused_before_anything(repo, fake_tmux, prompt, refused):
    with pytest.raises(runtime.LadoError, match=f"^{re.escape(refused)}$"):
        runtime.start_session(str(repo), "s", None, provider="claude", prompt=prompt)
    assert state.get_session("s") is None
    assert fake_tmux == []


@pytest.mark.parametrize("provider", ["claude", "kilo", "opencode"])
def test_a_cli_that_starts_its_session_by_itself_gets_no_first_input(repo, fake_tmux, provider):
    runtime.start_session(str(repo), "s", None, provider=provider)
    assert [m.summary for m in state.list_messages("s")] == []


def test_a_resumed_opencode_family_supervisor_gets_lados_line_and_the_humans(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="kilo")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None, prompt="Continue")
    [_, m] = state.list_messages("s")
    _, argv = agent_helpers.launched(fake_tmux[-1])
    assert argv[argv.index("--prompt") + 1] == (
        "[from lado] session resumed: 0 open runs\n"
        f"[from human] {runtime.FIRST_MESSAGE} (#{m.id}, 1 line: call read_messages)"
        + runtime.HUMAN_REPLY_HINT
    )


def _prompt(cmd):
    return agent_helpers.claude_prompt(cmd)


HUMAN_REPLY_RULE = " ".join(runtime.HUMAN_REPLY_RULE.split())


def test_the_human_reply_rule_says_the_terminal_is_unseen_and_how_to_answer():
    assert "does not see your terminal" in HUMAN_REPLY_RULE
    assert "text you write outside a tool call reaches nobody" in HUMAN_REPLY_RULE
    assert 'Answer every message "[from human] ..." that needs an answer' in HUMAN_REPLY_RULE
    assert 'send_message(to="human")' in HUMAN_REPLY_RULE and "ask_human" in HUMAN_REPLY_RULE
    assert '(thanks, "not now") needs no reply' in HUMAN_REPLY_RULE
    assert 'without "[from human]", is answered in the window' in HUMAN_REPLY_RULE


def test_the_supervisor_is_told_the_human_reply_rule_right_after_its_name(repo, fake_tmux):
    """A weak model answered the human in its terminal: the rule was one ambiguous
    sentence in the middle of the instructions (LAD-274)."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    supervisor = " ".join(_prompt(fake_tmux[0][-1]).split())
    name = 'You are agent "supervisor" in LADO session "s".'
    assert f"{name} {HUMAN_REPLY_RULE}" in supervisor
    assert "answer text typed straight into your window in this window" not in supervisor


HINT = ' (reply with send_message(to="human") or ask_human)'


def test_the_humans_line_says_how_to_answer_it():
    hello = state.Message(id=3, sender=state.HUMAN, summary="hello")
    assert runtime.format_message(hello) == "[from human] hello" + HINT


def test_the_hint_comes_after_the_body_part_of_the_humans_line():
    hello = state.Message(id=3, sender=state.HUMAN, summary="hello", body="one\ntwo")
    assert runtime.format_message(hello) == (
        "[from human] hello (#3, 2 lines: call read_messages)" + HINT
    )


def test_an_answer_to_a_question_and_another_agents_line_get_no_hint():
    answer = state.Message(id=6, sender=state.HUMAN, summary="yes", reply_to=5)
    assert runtime.format_message(answer) == "[from human] yes"
    report = state.Message(id=7, sender="w1", summary="done")
    assert runtime.format_message(report) == "[from w1] done"


def test_every_worker_is_told_the_human_reply_rule(repo, fake_tmux):
    """The human may write to any agent, and every agent gets the hint on their line."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "task")
    assert HUMAN_REPLY_RULE in " ".join(_prompt(fake_tmux[-1][-1]).split())
    assert runtime.HUMAN_REPLY_RULE in runtime.WORKER_INPUT
    assert runtime.WORKER_INSTRUCTIONS.endswith(runtime.WORKER_INPUT)
    assert runtime.RUN_WORKER_INSTRUCTIONS.endswith(runtime.WORKER_INPUT)


def test_every_worker_commits_unless_its_task_says_otherwise(repo, fake_tmux, quiet_kit):
    """A worker in its own worktree and a run's worker hold the same rule on commits, whose
    exception is the task (LAD-173)."""
    rule = (
        "Commit your work on that branch, unless your task says otherwise: an explicit "
        "instruction of your task (not to commit, to leave the branch as it is) wins over "
        "this default."
    )
    runtime.start_session(str(repo), "s", None, kit_names=["quiet"], provider="claude")
    runtime.spawn_worker("s", "build", role="dev")
    worker = " ".join(agent_helpers.claude_prompt(fake_tmux[-1][-1]).split())
    run = state.Run("s", "ship/x", "ship", "{}", {}, "Add x", "build", str(repo), "main")
    runtime.spawn_worker("s", "build", role="dev", run=run, has_step=True)
    run_worker = " ".join(agent_helpers.claude_prompt(fake_tmux[-1][-1]).split())
    for prompt in (worker, run_worker):
        assert rule in prompt
        assert "Commit your work on that branch." not in prompt


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
    agent_helpers.forget_tasks("s")


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


def test_a_message_to_an_agent_in_background_is_queued_like_one_to_an_idle_agent(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.BACKGROUND)
    state.queue_message("s", "supervisor", "w1", "one")
    runtime.hand_over("s", "w1")
    state.set_status("s", "w1", state.BACKGROUND)  # its turn ended, the batch unconfirmed
    assert runtime.send_message("s", "supervisor", "w1", "two") == (
        "queued; w1 has not confirmed the message typed before"
    )
    state.set_status("s", "w1", state.BUSY)
    assert runtime.send_message("s", "supervisor", "w1", "three") == (
        "queued; w1 is busy and will get it when it is idle or background"
    )


def _to_w1():
    return [m.summary for m in state.list_messages("s") if m.recipient == "w1"]


def test_a_reminder_to_an_agent_whose_report_waits_is_refused_until_it_is_read(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.BUSY)
    report = runtime.send_message("s", "w1", "supervisor", "DONE", "the report")
    assert report.startswith("queued")
    [waiting] = state.list_messages("s")
    with pytest.raises(runtime.LadoError) as error:
        runtime.send_message("s", "supervisor", "w1", "send your report")
    assert str(error.value) == (
        f"w1's message #{waiting.id} waits for you, so nothing was sent: read it with "
        "read_messages, then send again if it still needs saying"
    )
    assert _to_w1() == []
    # Delivered by that error's result, but not read yet: still refused.
    state.take_pending("s", "supervisor", state.DELIVERED, channel=state.TOOL_RESULT)
    with pytest.raises(runtime.LadoError):
        runtime.send_message("s", "supervisor", "w1", "send your report")
    state.read_messages("s", "supervisor")
    runtime.send_message("s", "supervisor", "w1", "send your report")
    assert _to_w1() == ["send your report"]


def test_a_reminder_after_a_message_without_a_body_goes_once_its_line_arrived(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.BUSY)
    runtime.send_message("s", "w1", "supervisor", "DONE")
    [waiting] = state.list_messages("s")
    with pytest.raises(runtime.LadoError) as error:
        runtime.send_message("s", "supervisor", "w1", "thanks")
    assert str(error.value) == (
        f"w1's message #{waiting.id} waits for you, so nothing was sent: its line comes with "
        "this result; send again if it still needs saying"
    )
    state.take_pending("s", "supervisor", state.DELIVERED, channel=state.TOOL_RESULT)
    runtime.send_message("s", "supervisor", "w1", "thanks")
    assert _to_w1() == ["thanks"]


def test_a_message_to_the_human_is_never_refused_for_a_waiting_one(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.BUSY)
    runtime.send_message("s", "w1", "supervisor", "DONE", "the report")
    assert runtime.send_message("s", "supervisor", state.HUMAN, "x done").startswith("delivered")


def test_a_message_from_the_human_is_never_refused_for_one_waiting_for_them(repo, fake_tmux):
    """The human's messages stay delivered, never read: one to read never stops them."""
    _session_with_worker(repo)
    runtime.send_message("s", "supervisor", state.HUMAN, "which one?", "a or b")
    runtime.send_message("s", state.HUMAN, "supervisor", "a")
    assert [m.summary for m in state.list_messages("s") if m.sender == state.HUMAN] == ["a"]


def test_every_agent_is_told_where_mid_turn_messages_come_from(repo, fake_tmux):
    assert "arrives with the result of your next `lado` tool call" in runtime.MESSAGING
    runtime.start_session(str(repo), "s", None, provider="claude")
    supervisor = agent_helpers.claude_prompt(fake_tmux[0][-1])
    assert runtime.MESSAGING in supervisor
    assert "Do not wait for a worker inside your turn" in supervisor
    assert "call read_messages first" in supervisor
    runtime.spawn_worker("s", "task", name="w1")
    worker = agent_helpers.claude_prompt(fake_tmux[-1][-1])
    assert runtime.MESSAGING in worker
    assert "Do not wait for a worker" not in worker


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


def _mismatched_report(repo, fake_tmux):
    """w1's report typed into the idle supervisor, which then ran a prompt that does not
    contain it and ended its turn at once."""
    sent = _swallowed_report(repo, fake_tmux)
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    assert _hook("Stop", "supervisor") is None
    return sent


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


def _logged(line):
    return (state.home() / "loop.log").read_text().count(line)


# An agent whose CLI needs a login (Claude Code) and has none waits for it in its window
# (lado.login_wait), with lado.logins.wait_reason.
LOGIN_REASON = (
    "Claude Code is not logged in: log in in Settings → Agent CLIs, or set "
    "CLAUDE_CODE_OAUTH_TOKEN; the agent starts by itself once you do"
)


def _waits_for_login(cmd):
    return "login-wait" in cmd


def _stopped_claude_session(repo, fake_tmux):
    """A Claude session "s" started while logged in, then stopped; tmux's calls forgotten.
    A new one without the login is refused, so a resume is where an agent waits for it."""
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    fake_tmux.clear()


RESUME_REFUSED = (
    "Claude Code is not logged in, so the session was not resumed: log in in LADO's UI "
    "(Settings → Agent CLIs, `lado ui`), or set CLAUDE_CODE_OAUTH_TOKEN as "
    "LADO's secret or a project secret"
)


@pytest.mark.parametrize("resume", [None, True])  # lado start, and the UI's Resume
def test_a_stopped_claude_session_is_not_resumed_by_hand_without_a_login(
    repo, fake_tmux, cli_logins, resume
):
    _stopped_claude_session(repo, fake_tmux)
    cli_logins.logged_out()
    with pytest.raises(runtime.NotLoggedIn) as refused:
        runtime.start_session(str(repo), "s", None, resume=resume)
    assert str(refused.value) == RESUME_REFUSED
    assert state.get_session("s").stopped_at
    assert state.get_agent("s", "supervisor") is None
    assert fake_tmux == []


@pytest.mark.parametrize(
    "how", [{"reason": runtime.AT_START, "resume": True}, {"wait_for_login": True}]
)
def test_lados_own_resume_waits_for_the_login(repo, fake_tmux, cli_logins, how):
    """At the container's start (resume_at_start), and after `lado update` (its `lado start
    --wait-for-login`)."""
    _stopped_claude_session(repo, fake_tmux)
    cli_logins.logged_out()
    started = runtime.start_session(str(repo), "s", None, **how)
    assert started.resumed
    assert started.warnings == [LOGIN_REASON]
    assert runtime.status_reasons("s") == {"supervisor": LOGIN_REASON}
    [call] = [c for c in fake_tmux if c[0] == "new_session"]
    assert _waits_for_login(call[-1])


def test_a_resume_with_another_provider_goes_on(repo, fake_tmux, cli_logins):
    _stopped_claude_session(repo, fake_tmux)
    cli_logins.logged_out()
    started = runtime.start_session(str(repo), "s", None, provider="kilo")
    assert started.resumed and state.get_session("s").provider == "kilo"
    assert state.get_agent("s", "supervisor").status == state.STARTING


def test_a_claude_worker_whose_login_goes_after_the_check_waits_and_says_so(
    repo, fake_tmux, cli_logins, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="kilo")
    checked = runtime.check_login

    def check_then_log_out(*args):
        checked(*args)
        cli_logins.logged_out()  # between the check and the launch

    monkeypatch.setattr(runtime, "check_login", check_then_log_out)
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", provider="claude", warnings=warnings)
    assert warnings == [LOGIN_REASON]
    assert runtime.status_reasons("s") == {"w1": LOGIN_REASON}
    assert _logged(f"s: w1: {LOGIN_REASON}") == 1
    [call] = [c for c in fake_tmux if c[0] == "new_window"]
    assert _waits_for_login(call[-1])


def test_lado_records_claude_codes_trust_in_the_log_only(repo, fake_tmux, claude_config):
    claude_config.trust()  # Claude Code trusts no folder
    note = claude_config.note(repo)
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    assert started.warnings == []
    assert _logged(f"s: supervisor: {note}") == 1
    assert state.get_agent("s", "supervisor").status == state.STARTING
    assert runtime.status_reasons("s") == {}
    projects = json.loads(claude_config.path.read_text())["projects"]
    assert projects == {str(repo): {"hasTrustDialogAccepted": True}}
    # Trusted now: the worker's spawn writes nothing and says nothing.
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", warnings=warnings)
    assert warnings == []
    assert _logged(note) == 1


def test_lado_records_claude_codes_trust_at_a_resume(repo, fake_tmux, claude_config):
    runtime.start_session(str(repo), "s", None, provider="claude")  # trusted
    runtime.stop_session("s")
    claude_config.trust()
    started = runtime.start_session(str(repo), "s", None)
    assert started.warnings == []
    assert _logged(f"s: supervisor: {claude_config.note(repo)}") == 1
    assert state.get_agent("s", "supervisor").status == state.STARTING


def test_lado_records_claude_codes_trust_for_a_worker(repo, fake_tmux, claude_config):
    runtime.start_session(str(repo), "s", None, provider="kilo")
    claude_config.trust()
    warnings = []
    worker = runtime.spawn_worker("s", "task", name="w1", provider="claude", warnings=warnings)
    note = claude_config.note(repo)  # the main repo's root, not the worktree's
    assert warnings == []
    assert _logged(f"s: w1: {note}") == 1
    assert state.get_agent("s", "w1").status == state.STARTING
    assert list(json.loads(claude_config.path.read_text())["projects"]) == [str(repo)]
    assert worker.cwd != str(repo)


@pytest.fixture
def keychain(monkeypatch):
    """Claude Code on a Mac with no login but the keychain's; keychain.text(template) is the
    warning LADO gives for it."""
    from lado.providers import claude

    monkeypatch.setattr(claude.sys, "platform", "darwin")
    for name in claude.LOGINS:
        monkeypatch.delenv(name, raising=False)
    hint = providers.get("claude").keychain_login({})

    class Keychain:
        @staticmethod
        def text(template):
            return gui_session.fill(template, [("Claude Code", hint)])

    return Keychain()


@pytest.mark.parametrize(
    ("place", "server", "warned"),
    [
        ("gui", gui_session.Place.REMOTE, gui_session.OUTSIDE_GUI),
        ("remote", gui_session.Place.NO_GUI, gui_session.OUTSIDE_GUI),
        ("no-gui", None, gui_session.NO_GUI),
        ("gui", gui_session.Place.GUI, None),
        ("remote", gui_session.Place.GUI, None),
        ("gui", None, None),
        ("gui", gui_session.Place.UNKNOWN, None),
    ],
)
def test_an_agent_that_cannot_read_the_keychain_is_started_with_a_warning(
    repo, fake_tmux, keychain, monkeypatch, place, server, warned
):
    monkeypatch.setenv("LADO_MACOS_PLACE", place)
    monkeypatch.setattr(gui_session, "server_place", lambda socket: server)
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    expected = [keychain.text(warned)] if warned else []
    assert started.warnings == expected
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", warnings=warnings)
    assert warnings == expected
    logged = (state.home() / "loop.log").read_text() if expected else ""
    for agent in ("supervisor", "w1"):
        assert all(f"s: {agent}: {line}" in logged for line in expected)
    assert [a.name for a in state.list_agents("s")] == ["supervisor", "w1"]


@pytest.fixture
def outside(tmp_path, monkeypatch):
    """The outside folder (LADO_ENV_DIR), empty."""
    folder = tmp_path / "secrets"
    folder.mkdir()
    monkeypatch.setenv("LADO_ENV_DIR", str(folder))
    return folder


def test_a_start_with_the_null_device_warns_nothing(repo, fake_tmux, monkeypatch):
    # compose's default without secrets: /dev/null at /run/secrets.
    monkeypatch.setenv("LADO_ENV_DIR", os.devnull)
    started = runtime.start_session(str(repo), "s", None, provider="kilo")
    assert started.warnings == []
    runtime.stop_session("s")
    assert runtime.start_session(str(repo), "s", None).warnings == []


@pytest.fixture
def projects(tmp_path, monkeypatch):
    """A container (LADO_CONTAINER) whose workspace (LADO_REPOS) is a new one."""
    folder = tmp_path / "projects"
    folder.mkdir()
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setenv("LADO_REPOS", str(folder))
    return folder


def test_a_start_and_a_resume_outside_the_repositories_folder_warn(repo, fake_tmux, projects):
    """A warning, never a refusal: the session runs."""
    line = runtime.OUTSIDE_WORKSPACE.format(folder=projects)
    started = runtime.start_session(str(repo), "s", None, provider="kilo")
    assert line in started.warnings
    assert state.get_session("s") is not None
    runtime.stop_session("s")
    assert line in runtime.start_session(str(repo), "s", None).warnings


def test_a_name_the_provider_sets_keeps_its_value_and_is_named(repo, fake_tmux, outside):
    (outside / "KILO_DISABLE_AUTOUPDATE").write_text("0")
    (outside / "PATH").write_text("/x")
    started = runtime.start_session(str(repo), "s", None, provider="kilo")
    provider_set = (
        f"variable file KILO_DISABLE_AUTOUPDATE in {outside} not used: "
        "LADO sets KILO_DISABLE_AUTOUPDATE for kilo"
    )
    assert provider_set in started.warnings
    env, _ = agent_helpers.launched(fake_tmux[0])
    assert env["KILO_DISABLE_AUTOUPDATE"] == "1"
    # A spawn names only what depends on its provider: the folder is the session's.
    warnings = []
    runtime.spawn_worker("s", "task", name="w1", warnings=warnings)
    assert warnings == [provider_set]
    warnings = []
    runtime.spawn_worker("s", "task", name="w2", provider="claude", warnings=warnings)
    assert warnings == []


@pytest.mark.parametrize(
    ("status", "wait"),
    [
        (state.BUSY, True),
        (state.IDLE, True),
        (state.BACKGROUND, True),
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


WAITS = (75.0, 600.0)  # a hook_output batch's (not printed, printed), as LADO's own


def test_the_hook_output_waits_are_lados_unless_the_environment_gives_others():
    assert (runtime.HOOK_OUTPUT_WAIT, runtime.HOOK_OUTPUT_BACKSTOP) == WAITS
    assert runtime.HOOK_OUTPUT_WAIT == base.TURN_END_HOOK_TIMEOUT + 15
    assert runtime.seconds_from(None, 75.0) == 75.0
    assert runtime.seconds_from("", 75.0) == 75.0
    assert runtime.seconds_from("2.5", 75.0) == 2.5


@pytest.mark.parametrize(("provider", "waits"), [("claude", WAITS), ("kilo", None), ("x", None)])
def test_the_sweep_gives_the_plan_the_hook_output_waits_of_a_cli_that_takes_it_printed(
    provider, waits, lado_home, monkeypatch
):
    state.add_session(state.Session("s", "/r", None, provider="claude"))
    state.add_agent(
        state.Agent("s", "w1", "worker", "/r", None, None, state.BUSY, provider=provider)
    )
    planned = []
    monkeypatch.setattr(runtime, "_plan", lambda *args: planned.append(args[4:]) or state.Plan())
    runtime.sweep("s", "w1", now=100.0, delays=DELAYS)
    assert planned == [(waits,)]


def _retry_until_failed(sent, start=0):
    """Sweep at the end of each delay, from the `start`-th one on, until the message fails."""
    at = sent
    for delay in DELAYS[start:] + DELAYS[-1:]:
        at += delay
        runtime.sweep("s", now=at, delays=DELAYS)
    return at


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


def _handed_over_in_the_stop_hook(repo, printed=True):
    """w1's report in the busy supervisor's Stop hook output, marked printed as hooks.main
    marks it unless not `printed`. Returns when it was handed over."""
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "report")
    assert _hook("Stop", "supervisor") == {"decision": "block", "reason": "[from w1] report"}
    sent = state.list_messages("s")[0].sent_at
    if printed:
        state.output_printed("s", "supervisor", since=sent)
    return sent


def test_a_batch_printed_once_and_handed_over_again_unprinted_waits_only_the_hook_limit(
    repo, fake_tmux
):
    """Printed, back in the queue, then in the output of a Stop hook that dies before its
    print: the old mark must not make it wait for the backstop."""
    first = _handed_over_in_the_stop_hook(repo)
    state.sweep(
        "s", "supervisor", first + 1, lambda agent, sent: state.Plan(requeue=[m.id for m in sent])
    )
    assert state.list_messages("s")[0].state == state.PENDING
    assert _hook("Stop", "supervisor") == {"decision": "block", "reason": "[from w1] report"}
    [report] = state.list_messages("s")
    assert (report.state, report.channel, report.printed_at) == (
        state.SENT,
        state.HOOK_OUTPUT,
        None,
    )
    runtime.sweep("s", now=report.sent_at + runtime.HOOK_OUTPUT_WAIT - 1, delays=DELAYS)
    assert _typed(fake_tmux) == []
    runtime.sweep("s", now=report.sent_at + runtime.HOOK_OUTPUT_WAIT, delays=DELAYS)
    assert _typed(fake_tmux) == ["[from w1] report"]


def _report_and_ping_in_the_stop_hook(repo):
    """w1's report (with a body) and ping (without) in the busy supervisor's Stop hook
    output. Returns when they were handed over."""
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "report", "the details")
    runtime.send_message("s", "w1", "supervisor", "ping")
    assert _hook("Stop", "supervisor")["decision"] == "block"
    return state.list_messages("s")[0].sent_at


@pytest.mark.parametrize("taken", [True, False])
def test_a_message_read_before_its_confirmation_is_never_typed_again(repo, fake_tmux, taken):
    sent = _report_and_ping_in_the_stop_hook(repo)
    state.read_messages("s", "supervisor")
    # The turn ends: went on from the output, or not (the ping goes by TYPED then).
    _hook("Stop", "supervisor", CONTINUED if taken else {})
    at = _retry_until_failed(sent)
    runtime.sweep("s", now=at + 1000, delays=DELAYS)
    report, ping = state.list_messages("s")[:2]
    assert report.state == state.READ
    typed = [t for t in _typed(fake_tmux) if "report" in t]
    assert typed == []
    if not taken:
        # The ping fails alone; the report's sender hears of the ping only.
        assert ping.state == state.FAILED
        notices = [m.summary for m in state.list_messages("s") if m.sender == state.LADO]
        assert notices == [f"message #{ping.id} to supervisor not delivered: ping"]


def test_message_errors(repo, fake_tmux):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match="running agents: supervisor, w1"):
        runtime.send_message("s", "w1", "nobody", "hi")
    with pytest.raises(runtime.LadoError, match=r"write the details to an artifact \(write_"):
        runtime.send_message("s", "w1", "supervisor", "done", "x" * 9000)


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
    assert state.get_agent("s", "w1").status == state.IDLE  # ready: its queue is empty
    assert "w1: LADO's MCP server listed no tools" in (lado_home / "hooks.log").read_text()


def test_a_session_start_with_a_note_tells_the_lead_and_hands_the_queue_over(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.send_message("s", "supervisor", "w1", "go on")
    start = providers.Event(providers.SESSION_START, note="no report from its TUI")
    hooks.handle(providers.get("kilo"), start, "s", "w1")
    told = [m.summary for m in state.list_messages("s") if m.sender == state.LADO]
    assert "w1: no report from its TUI" in told
    assert [c for c in fake_tmux if c[0] == "send_text"]


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_no_session_start_of_claude_code_or_codex_has_a_note_or_says_ready(provider):
    event = providers.get(provider).parse_event("SessionStart", '{"source": "startup"}')
    assert event.kind == providers.SESSION_START
    assert (event.note, event.ready) == ("", False)


def test_a_cli_that_says_it_takes_input_ends_a_wait_of_failed_messages(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.WAITING)  # as a failed message leaves it, with no key
    hooks.handle(
        providers.get("kilo"), providers.Event(providers.SESSION_START, ready=True), "s", "w1"
    )
    assert state.get_agent("s", "w1").status == state.IDLE


def test_a_cli_that_says_it_takes_input_leaves_a_dialog_with_a_key(repo, fake_tmux):
    _session_with_worker(repo)
    state.wait("s", "w1", "per_1")
    hooks.handle(
        providers.get("kilo"), providers.Event(providers.SESSION_START, ready=True), "s", "w1"
    )
    assert state.get_agent("s", "w1").status == state.WAITING


READY = providers.Event(providers.SESSION_START, ready=True)
SILENT = providers.Event(providers.SESSION_START, note="no report from its TUI")


@pytest.mark.parametrize("provider", ["kilo", "opencode"])
def test_lines_on_the_command_line_taken_before_the_report_change_nothing(
    repo, fake_tmux, provider
):
    """chat.message before tui.ready: the agent is in its turn, and the report leaves it there."""
    cli = providers.get(provider)
    runtime.start_session(str(repo), "s", None, provider=provider)
    runtime.spawn_worker("s", "fix the bug;", name="w1")
    [task] = state.list_messages("s")
    line = f"[from lado] your task (#{task.id}, 3 lines: call read_messages)"
    hooks.handle(cli, providers.Event(providers.PROMPT_SUBMIT, line), "s", "w1")
    hooks.handle(cli, READY, "s", "w1")
    assert state.get_agent("s", "w1").status == state.BUSY
    assert state.get_message("s", task.id).state == state.DELIVERED
    assert not [c for c in fake_tmux if c[0] == "send_text"]


def _typed_into_a_silent_tui(repo) -> state.Message:
    """A worker made ready by a silent TUI, its message typed in and not confirmed."""
    _session_with_worker(repo)
    hooks.handle(providers.get("kilo"), SILENT, "s", "w1")
    runtime.send_message("s", "supervisor", "w1", "go on")
    [typed] = [m for m in state.list_messages("s") if m.recipient == "w1"]
    assert (typed.state, state.get_agent("s", "w1").status) == (state.SENT, state.BUSY)
    return typed


def test_a_report_after_a_paste_starts_its_wait_again_and_the_paste_goes_in_again(repo, fake_tmux):
    typed = _typed_into_a_silent_tui(repo)
    hooks.handle(providers.get("kilo"), READY, "s", "w1")
    assert state.get_agent("s", "w1").status == state.IDLE
    again = state.get_message("s", typed.id)
    assert (again.state, again.attempts) == (state.SENT, 1)  # the paste may yet be confirmed
    pastes = len([c for c in fake_tmux if c[0] == "send_text"])
    runtime.sweep("s", now=again.sent_at + runtime.RETRY_DELAYS[0] - 1)
    assert len([c for c in fake_tmux if c[0] == "send_text"]) == pastes
    runtime.sweep("s", now=again.sent_at + runtime.RETRY_DELAYS[0])
    assert len([c for c in fake_tmux if c[0] == "send_text"]) == pastes + 1
    assert state.get_agent("s", "w1").status == state.BUSY


def test_a_report_after_the_last_paste_saves_it_from_failing(repo, fake_tmux):
    typed = _typed_into_a_silent_tui(repo)
    with state.connect() as db:
        db.execute(
            "UPDATE messages SET attempts = ? WHERE id = ?",
            (len(runtime.RETRY_DELAYS) + 1, typed.id),
        )
    hooks.handle(providers.get("kilo"), READY, "s", "w1")
    runtime.sweep("s", now=state.get_message("s", typed.id).sent_at + runtime.RETRY_DELAYS[-1])
    assert state.get_message("s", typed.id).state != state.FAILED


def test_a_paste_confirmed_after_the_report_is_not_typed_again(repo, fake_tmux):
    """A CLI that held the paste after all: its prompt comes within the wait."""
    typed = _typed_into_a_silent_tui(repo)
    cli = providers.get("kilo")
    hooks.handle(cli, READY, "s", "w1")
    line = runtime.format_message(state.get_message("s", typed.id))
    hooks.handle(cli, providers.Event(providers.PROMPT_SUBMIT, line), "s", "w1")
    pastes = len([c for c in fake_tmux if c[0] == "send_text"])
    runtime.sweep("s", now=time.time() + runtime.RETRY_DELAYS[-1] * 2)
    assert state.get_message("s", typed.id).state == state.DELIVERED
    assert len([c for c in fake_tmux if c[0] == "send_text"]) == pastes


def test_a_late_silent_report_is_no_sign_of_the_agent(repo, fake_tmux):
    """It comes after tui.ready too: it must not pass for a hook after a paste (runtime._plan)."""
    _session_with_worker(repo)
    cli = providers.get("kilo")
    hooks.handle(cli, READY, "s", "w1")
    seen = state.get_agent("s", "w1").seen_at
    hooks.handle(cli, SILENT, "s", "w1")
    assert state.get_agent("s", "w1").seen_at == seen


def test_another_session_start_leaves_a_wait_of_failed_messages(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.WAITING)
    hooks.handle(providers.get("kilo"), providers.Event(providers.SESSION_START), "s", "w1")
    assert state.get_agent("s", "w1").status == state.WAITING


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


def _stop_hook_with_report(repo, monkeypatch):
    """w1's report queued for the busy supervisor; returns a Stop hook of its, run by
    hooks.main."""
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")
    runtime.send_message("s", "w1", "supervisor", "report")
    instance = state.get_agent("s", "supervisor").instance
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    return lambda: hooks.main("Stop", "s", "supervisor", instance)


def test_the_stop_hook_marks_its_output_printed_after_printing_it(
    repo, fake_tmux, monkeypatch, capsys
):
    stop = _stop_hook_with_report(repo, monkeypatch)
    mark = state.output_printed
    printed_before = []

    def marked(*args, **kwargs):
        printed_before.append(capsys.readouterr().out)
        mark(*args, **kwargs)

    monkeypatch.setattr(state, "output_printed", marked)
    assert stop() == 0
    assert [json.loads(out)["reason"] for out in printed_before] == ["[from w1] report"]
    [report] = state.list_messages("s")
    assert (report.state, report.channel) == (state.SENT, state.HOOK_OUTPUT)
    assert report.printed_at is not None and report.printed_at >= report.sent_at


def test_no_print_mark_for_a_cli_that_may_not_take_the_printed_output(
    repo, fake_tmux, monkeypatch, capsys
):
    stop = _stop_hook_with_report(repo, monkeypatch)
    claude = providers.get("claude")
    untaken = dataclasses.replace(claude.capabilities, output_taken_when_printed=False)
    monkeypatch.setattr(claude, "capabilities", untaken)
    assert stop() == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "[from w1] report"
    [report] = state.list_messages("s")
    assert (report.channel, report.printed_at) == (state.HOOK_OUTPUT, None)


def test_a_print_mark_that_fails_leaves_the_printed_output_to_its_turn(
    repo, fake_tmux, lado_home, monkeypatch, capsys
):
    """The output went out: the CLI has it, so it is not made TYPED, which would type it
    in again after the first delay; it waits as output not marked printed (runtime._plan)."""
    stop = _stop_hook_with_report(repo, monkeypatch)
    monkeypatch.setattr(state, "output_printed", lambda *args, **kwargs: 1 / 0)
    assert stop() == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "[from w1] report"
    assert "ZeroDivisionError" in (lado_home / "hooks.log").read_text()
    [report] = state.list_messages("s")
    assert (report.state, report.channel, report.printed_at) == (
        state.SENT,
        state.HOOK_OUTPUT,
        None,
    )


def test_a_hook_writes_nothing_into_a_deleted_home(repo, fake_tmux, monkeypatch, lado_home):
    runtime.start_session(str(repo), "s", None, provider="claude")
    instance = state.get_agent("s", "supervisor").instance
    runtime.stop_session("s")
    shutil.rmtree(lado_home)  # deleted right after `lado stop`, before the dying agent's hook
    monkeypatch.setattr("sys.stdin.read", lambda: "{}")
    assert hooks.main("SessionEnd", "s", "supervisor", instance) == 0
    assert not lado_home.exists()


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


def test_a_kill_that_fails_does_not_keep_the_containers_stop_from_the_rest(
    repo, fake_tmux, lado_home, monkeypatch, capsys
):
    for name in ("a", "b"):
        runtime.start_session(str(repo), name, None, provider="claude")
    record = tmux.kill_session

    def kill(session):
        if session == "a":
            raise tmux.TmuxError("server exited unexpectedly")
        record(session)

    monkeypatch.setattr(tmux, "kill_session", kill)
    assert runtime.stop_for_container() == ["a", "b"]
    assert ("kill_session", "b") in fake_tmux
    assert ("close_viewers", "b") in fake_tmux
    assert capsys.readouterr().err == (
        'lado: could not kill the tmux session of "a": server exited unexpectedly\n'
    )
    assert state.get_session("a").stopped_at and state.get_session("a").resume_at_start


def test_viewers_that_cannot_be_closed_do_not_keep_the_containers_stop_from_the_rest(
    repo, fake_tmux, lado_home, monkeypatch, capsys
):
    for name in ("a", "b"):
        runtime.start_session(str(repo), name, None, provider="claude")

    def close(session):
        if session == "a":
            raise tmux.TmuxError("server exited unexpectedly")
        fake_tmux.append(("close_viewers", session))

    monkeypatch.setattr(terminal, "close_viewers", close)
    assert runtime.stop_for_container() == ["a", "b"]
    assert ("kill_session", "b") in fake_tmux and ("close_viewers", "b") in fake_tmux
    assert _config_folders(lado_home) == []
    assert capsys.readouterr().err == (
        'lado: could not close the UI\'s terminals of "a": server exited unexpectedly\n'
    )


def test_the_containers_stop_without_lado_db_makes_nothing(lado_home):
    assert runtime.stop_for_container() == []
    assert not lado_home.exists()


def test_the_containers_first_start_makes_no_lado_db(lado_home):
    """A new container's server makes lado.db elsewhere; a second maker at the same moment
    could leave it half made (schema version 0 with tables)."""
    lado_home.mkdir()
    lines = []
    runtime.resume_at_start(lines.append)
    assert lines == [] and not (lado_home / "lado.db").exists()


def _started(name: str) -> runtime.Started:
    """What a resume with nothing to say returns."""
    return runtime.Started(state.get_session(name), resumed=True)


def _resumed(monkeypatch) -> list[tuple]:
    """start_session replaced: the calls it got, as (repo, name, permission mode, kwargs)."""
    calls = []
    monkeypatch.setattr(
        runtime, "start_session", lambda *a, **k: calls.append((*a, k)) or _started(a[1])
    )
    return calls


def test_the_containers_start_resumes_the_marked_and_the_gone(repo, fake_tmux, monkeypatch):
    for name in ("marked", "gone", "running", "mine"):
        runtime.start_session(str(repo), name, None, provider="claude")
    runtime.stop_session("mine")  # the human's: stays stopped
    state.stop_for_container()  # marked, gone and running, as the stop would
    state.resume_session(state.get_session("gone"), "")  # not stopped, its tmux gone
    state.resume_session(state.get_session("running"), "")  # its tmux is there
    fake_tmux.append(("kill_session", "gone"))
    calls = _resumed(monkeypatch)
    lines = []
    runtime.resume_at_start(lines.append)
    reason = {"resume": True, "reason": "at the container's start"}
    assert calls == [(str(repo), "marked", None, reason), (str(repo), "gone", None, reason)]
    assert lines == [
        'lado: resumed session "marked" at the container\'s start',
        'lado: resumed session "gone" at the container\'s start',
    ]


def test_a_resumes_problems_and_warnings_are_reported(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "a", None, provider="claude")
    state.stop_for_container()

    def start(path, name, mode, **kwargs):
        return runtime.Started(
            state.get_session(name),
            resumed=True,
            problems=["run x: role reviewer is not in the session's kits"],
            warnings=["kit k: its supervisor does not lead"],
        )

    monkeypatch.setattr(runtime, "start_session", start)
    lines = []
    runtime.resume_at_start(lines.append)
    assert lines == [
        'lado: resumed session "a" at the container\'s start',
        'lado: session "a": run x: role reviewer is not in the session\'s kits',
        'lado: session "a": kit k: its supervisor does not lead',
    ]


def test_a_resume_that_fails_gives_up_and_goes_on(repo, fake_tmux, monkeypatch):
    for name in ("a", "b"):
        runtime.start_session(str(repo), name, None, provider="claude")
    state.stop_for_container()
    resumed = []

    def start(path, name, mode, **kwargs):
        if name == "a":
            raise runtime.LadoError(f"{path} is not there\nmore")
        resumed.append(name)
        return _started(name)

    monkeypatch.setattr(runtime, "start_session", start)
    lines = []
    runtime.resume_at_start(lines.append)
    assert resumed == ["b"]
    assert lines == [
        f'lado: could not resume session "a" at the container\'s start: {repo} is not there; '
        "it stays stopped",
        'lado: resumed session "b" at the container\'s start',
    ]
    assert state.get_session("a").stopped_at and not state.get_session("a").resume_at_start
    lines.clear()
    resumed.clear()
    runtime.resume_at_start(lines.append)  # the next start: b is still marked (start_session
    assert resumed == ["b"]  # was replaced), a is not tried again
    assert lines == ['lado: resumed session "b" at the container\'s start']


def test_a_resume_that_fails_unexpectedly_is_recorded(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "a", None, provider="claude")
    state.stop_for_container()
    recorded = []
    monkeypatch.setattr(telemetry, "record", lambda where, exc, **k: recorded.append(where))

    def start(*a, **k):
        raise KeyError("x")

    monkeypatch.setattr(runtime, "start_session", start)
    lines = []
    runtime.resume_at_start(lines.append)
    assert lines == [
        "lado: could not resume session \"a\" at the container's start: KeyError: 'x'; "
        "it stays stopped"
    ]
    assert recorded == ["server:resume"]


def test_a_failed_resume_of_a_session_that_runs_does_not_stop_it(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "a", None, provider="claude")
    state.stop_for_container()
    fake_tmux.append(("kill_session", "a"))
    real = runtime.start_session

    def start(path, name, mode, **kwargs):
        real(path, name, None)  # the human's resume wins the race
        return real(path, name, mode, **kwargs)  # already running

    monkeypatch.setattr(runtime, "start_session", start)
    lines = []
    runtime.resume_at_start(lines.append)
    sess = state.get_session("a")
    assert not sess.stopped_at and not sess.resume_at_start
    assert lines == ['lado: session "a" runs already at the container\'s start']


def test_the_containers_start_resumes_nothing_more_once_it_stops(repo, fake_tmux, monkeypatch):
    for name in ("a", "b"):
        runtime.start_session(str(repo), name, None, provider="claude")
    state.stop_for_container()
    stopping = threading.Event()
    calls = []

    def start(path, name, mode, **kwargs):
        calls.append(name)
        stopping.set()
        return _started(name)

    monkeypatch.setattr(runtime, "start_session", start)
    runtime.resume_at_start(lambda line: None, stopping)
    assert calls == ["a"]
    assert state.get_session("b").resume_at_start  # left for the next start


def test_a_resume_with_a_reason_says_it_in_its_event(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    state.stop_for_container()
    runtime.start_session(str(repo), "s", None, resume=True, reason="at the container's start")
    [resume] = [e for e in state.list_events("s") if e.kind == state.SESSION_RESUME]
    assert resume.detail == "at the container's start; same settings"
    assert not state.get_session("s").resume_at_start


def test_start_resumes_a_stopped_session(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.spawn_worker("s", "task")  # "worker"
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None)
    assert (started.resumed, started.changes, started.problems) == (True, [], [])
    assert started.session.stopped_at is None
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert [(m.sender, m.recipient, m.summary, m.state) for m in state.list_messages("s")][-1] == (
        "lado",
        "supervisor",
        "session resumed: 0 open runs",
        state.PENDING,
    )
    kinds = [e.kind for e in state.list_events("s")]
    assert kinds[-2:] == [state.SESSION_RESUME, state.SPAWNED]
    # The branch of "worker" is still there: the next worker gets another name.
    assert runtime.spawn_worker("s", "task").name == "worker-2"


def _fail(*args, **kwargs):
    raise tmux.TmuxError("command too long")


@pytest.mark.parametrize("failing", ["tmux", "provider"])
def test_a_failed_spawn_leaves_no_ghost_worker(repo, fake_tmux, monkeypatch, failing):
    runtime.start_session(str(repo), "s", None, provider="claude")
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


def _locked(*args, **kwargs):
    raise sqlite3.OperationalError("database is locked")


def _undo_notes(error):
    return getattr(error, "__notes__", [])


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
    """An installed kit on top of the default kit: a reviewer role, two skills, an MCP
    server."""
    kit = repo.parent / "kits" / "team"
    _write(kit / "kit.yaml", "name: team\nversion: 1.0.0\n")
    _write(
        kit / "agents" / "reviewer.md",
        "---\nname: reviewer\ndescription: reviews branches\nskills: [checklist]\n"
        "mcp:\n  db:\n    command: ['${KIT_DIR}/db.sh']\n    env: {TOKEN: '${DB_TOKEN}'}\n"
        "---\nYou review. Notes are in ${KIT_DIR}/notes.\n",
    )
    for skill in ("checklist", "style"):
        _write(kit / "skills" / skill / "SKILL.md", f"---\nname: {skill}\ndescription: d\n---\n")
    agent_helpers.install_kit(kit)
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
    prompt = agent_helpers.claude_prompt(cmd)
    assert prompt.startswith("You are the supervisor.")  # the role from the default kit
    assert 'agent "supervisor" in LADO session "s"' in prompt
    assert "`role` picks the kind of worker; required: this session has several. Roles:" in prompt
    assert "  - reviewer (kit team): reviews branches" in prompt
    assert "  - worker (kit default): " in prompt
    # The supervisor lists no skills, so it gets all of them except the one switched off.
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]


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


class _NoSkills(providers.Provider):
    name = "noskills"
    title = "No Skills CLI"
    capabilities = providers.Capabilities(
        status_events=True, permission_event=False, deliver_on_turn_end=True, skills=False
    )

    def launch_command(self, agent, session, spec):
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


def test_git_exclude_keeps_the_projects_lado_files_visible(repo, fake_tmux):
    _write(repo / ".lado" / "sdlc.md", "# settings\n")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("# mine\n/.lado/\n")  # what LADO 0.3 wrote
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.spawn_worker("s", "t")
    assert exclude.read_text() == "# mine\n/.lado/worktrees/\n"
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "-uall"], capture_output=True, text=True
    )
    assert ".lado/sdlc.md" in status.stdout
    assert "worktrees" not in status.stdout
    runtime.spawn_worker("s", "t")
    assert exclude.read_text() == "# mine\n/.lado/worktrees/\n"


def test_include_worktrees_drops_only_lados_line(repo):
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text("# mine\n/.lado/worktrees/\n*.log\n")
    runtime.include_worktrees(str(repo))
    assert exclude.read_text() == "# mine\n*.log\n"
    runtime.include_worktrees(str(repo))  # nothing to drop: no change
    assert exclude.read_text() == "# mine\n*.log\n"


def test_include_worktrees_without_the_file_is_no_error(repo):
    exclude = repo / ".git" / "info" / "exclude"
    exclude.unlink(missing_ok=True)
    runtime.include_worktrees(str(repo))
    assert not exclude.exists()


def _commit(worktree, name="work.txt"):
    Path(worktree, name).write_text("done\n")
    runtime.git(worktree, "add", name)
    runtime.git(worktree, "commit", "-q", "-m", f"add {name}")


def test_keeps_work_of_a_gone_branch_counts_the_worktrees_commits(repo):
    worktree = str(repo / ".lado" / "worktrees" / "s" / "w")
    runtime.git(str(repo), "worktree", "add", "-q", "-b", "lado/s/w", worktree)
    _commit(worktree, "one.txt")
    _commit(worktree, "two.txt")
    runtime.git(worktree, "checkout", "-q", "--detach")
    runtime.git(str(repo), "branch", "-D", "lado/s/w")
    work = runtime.work_of(str(repo), worktree, "lado/s/w")
    assert work.gone == ["branch"]
    assert runtime.keeps_work(work) == "2 commits not in main"


def test_work_state_refuses_an_agent_without_a_branch(repo, fake_tmux):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match="works in the repo, not on a branch of its own"):
        runtime.work_state("s", "supervisor")
    with pytest.raises(runtime.LadoError, match='no agent "w9"'):
        runtime.work_state("s", "w9")


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


def _detach_and_delete_branch(repo, worker):
    runtime.git(worker.cwd, "checkout", "-q", "--detach")
    runtime.git(str(repo), "branch", "-D", worker.branch)


def test_a_worker_whose_branch_is_gone_keeps_unmerged_commits_without_discard(repo, fake_tmux):
    # The worktree's detached HEAD still holds commits the repo's branch does not have.
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    _commit(worker.cwd)
    _detach_and_delete_branch(repo, worker)
    assert runtime.work_state("s", "w1").ahead == 1
    refused = (
        f"branch lado/s/w1 is gone, but its worktree {worker.cwd} holds 1 commit not in main "
        f"(the current branch of {repo}); merge it first, or finish with discard to throw "
        "its work away"
    )
    assert runtime.finish_preview("s", "w1").refused == refused
    with pytest.raises(runtime.LadoError, match=re.escape(refused)):
        runtime.finish_worker("s", "w1")
    assert state.get_agent("s", "w1") is not None and Path(worker.cwd).exists()
    assert runtime.finish_worker("s", "w1", discard=True).how == "discarded"
    assert not Path(worker.cwd).exists()


@pytest.mark.parametrize("discard", [False, True])
def test_a_worker_whose_branch_and_worktree_are_gone_finishes(repo, fake_tmux, discard):
    _session_with_worker(repo)
    worker = state.get_agent("s", "w1")
    runtime.git(str(repo), "worktree", "remove", worker.cwd)
    runtime.git(str(repo), "branch", "-D", worker.branch)
    assert runtime.work_state("s", "w1").gone == ["worktree", "branch"]
    assert runtime.finish_preview("s", "w1").refused is None
    finished = runtime.finish_worker("s", "w1", discard=discard)
    assert finished.gone == ["worktree", "branch"]
    assert finished.text().endswith(
        f"removed window; already gone: worktree {worker.cwd}, branch lado/s/w1"
    )
    assert state.get_agent("s", "w1") is None
    assert ("kill_window", "s", "w1") in fake_tmux


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


@pytest.mark.parametrize(
    ("queue", "send"),
    [
        ("queue_message", lambda question: runtime.send_message("s", "supervisor", "w1", "late")),
        ("queue_with_copy", lambda question: runtime.write_as_human("s", "late", to="w1")),
        ("reply_to_questions", lambda question: runtime.answer_question("s", question.id, "yes")),
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
    taken = state.take_pending("s", "w1", state.SENT, state.BUSY)
    assert [m.summary for m in taken] == ["your task"]  # its own only
    # Read as soon as it is handed over: the new w1's task, nothing to the old one.
    assert [m.id for m in state.read_messages("s", "w1")] == [taken[0].id]


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


def test_a_migration_due_names_the_sessions_that_keep_it_from_running(repo, fake_tmux):
    assert runtime.migration_due() is None  # no lado.db
    runtime.start_session(str(repo), "old", None, provider="claude")
    runtime.start_session(str(repo), "other", None, provider="claude")
    assert runtime.migration_due() is None  # this LADO's schema
    tmux.kill_session("other")  # marked running in lado.db, gone from tmux
    agent_helpers.previous_schema()
    assert runtime.migration_due() == (state.SCHEMA_VERSION - 1, ["old"])
    runtime.stop_session("old")
    assert runtime.migration_due() is None  # migrated by the stop


def _database() -> bytes:
    """lado.db with its WAL folded in: equal bytes mean nothing was written in between."""
    return agent_helpers.database()


def _spy_migrate(monkeypatch, calls):
    """Record state.migrate in the tmux calls, to see it in order with the kills."""
    migrate = state.migrate
    monkeypatch.setattr(state, "migrate", lambda: calls.append(("migrate",)) or migrate())


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
        ("end_login_windows",),  # they go with LADO's sessions (lado.logins)
    ]
    assert state.pending_migration() is None
    assert all(state.get_session(n).stopped_at for n in ("a", "b", "gone"))
    # A session found gone gets its session_gone; the ones it killed do not.
    assert state.SESSION_GONE in [e.kind for e in state.list_events("gone")]
    assert state.SESSION_GONE not in [e.kind for e in state.list_events("a")]


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


def test_stop_returns_once_the_loop_has_ended(repo, fake_tmux, monkeypatch, lado_home):
    runtime.start_session(str(repo), "s", None, provider="claude")
    events = []
    kill = tmux.kill_session
    monkeypatch.setattr(tmux, "kill_session", lambda s: (events.append("kill"), kill(s)))

    def wait_stopped(session, timeout=None):
        events.append(("wait", session, bool(state.get_session(session).stopped_at)))
        return False

    monkeypatch.setattr(loop, "wait_stopped", wait_stopped)
    with pytest.raises(runtime.LadoError) as failed:
        runtime.stop_session("s")
    assert events == ["kill", ("wait", "s", True)]  # marked, killed, then waited for
    assert str(failed.value) == (
        'session "s" is stopped, but its loop did not end (LADO_HOME/loop/s.lock is held); '
        f"see {lado_home / 'loop.log'}"
    )
    assert state.get_session("s").stopped_at


def test_a_stop_without_its_wait_leaves_the_loop_to_the_caller(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="claude")
    monkeypatch.setattr(loop, "wait_stopped", lambda session, timeout=None: pytest.fail("waited"))
    runtime.stop_session("s", wait=False)
    runtime.start_session(str(repo), "t", None, provider="claude")
    runtime.stop_all(lambda name, stopped: None, wait=False)
    assert state.get_session("s").stopped_at and state.get_session("t").stopped_at


def test_stop_all_waits_for_the_loops_after_stopping_them_all(repo, fake_tmux, monkeypatch):
    for name in ("a", "b", "c"):
        runtime.start_session(str(repo), name, None, provider="claude")
    events = []

    def wait_stopped(session, timeout=None):
        events.append(f"wait {session}")
        return session != "b"

    monkeypatch.setattr(loop, "wait_stopped", wait_stopped)
    with pytest.raises(runtime.LadoError) as failed:
        runtime.stop_all(lambda name, stopped: events.append(f"stopped {name}"))
    assert events == [*(f"stopped {n}" for n in "abc"), *(f"wait {n}" for n in "abc")]
    assert str(failed.value) == (
        'session "b" is stopped, but its loop did not end (LADO_HOME/loop/b.lock is held); '
        f'see {state.home() / "loop.log"}; stopped: "a", "b", "c"'
    )
    assert all(state.get_session(n).stopped_at for n in "abc")


def test_a_wait_that_fails_does_not_cut_stop_all_short(repo, fake_tmux, monkeypatch):
    for name in ("a", "b"):
        runtime.start_session(str(repo), name, None, provider="claude")
    ended = []
    monkeypatch.setattr(runtime.logins, "end_windows", lambda: ended.append(True))

    def wait_stopped(session, timeout=None):
        if session == "a":
            raise PermissionError("loop/a.lock")
        return True

    monkeypatch.setattr(loop, "wait_stopped", wait_stopped)
    with pytest.raises(runtime.LadoError) as failed:
        _stop_all()
    assert str(failed.value) == (
        'could not wait for the loop of session "a": PermissionError: loop/a.lock; '
        'stopped: "a", "b"'
    )
    assert ended == [True]


def _stop_all() -> list[str]:
    """The sessions stop_all stopped, in the order it reported them."""
    reported = []
    runtime.stop_all(lambda name, stopped: reported.append(name))
    return reported


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


@pytest.mark.parametrize(
    ("text", "summary", "body"),
    [
        ("look at\tthis\x1b[0m now", "look at this [0m now", "look at\tthis\x1b[0m now"),
        (
            "fix it\N{LINE SEPARATOR}now \N{RIGHT-TO-LEFT OVERRIDE}please",
            "fix it now please",
            "fix it\N{LINE SEPARATOR}now \N{RIGHT-TO-LEFT OVERRIDE}please",
        ),
        ("\N{ZERO WIDTH SPACE}ok\nmore", "ok", "\N{ZERO WIDTH SPACE}ok\nmore"),
        ("Семья 👨\N{ZERO WIDTH JOINER}👩", "Семья 👨\N{ZERO WIDTH JOINER}👩", ""),
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
    assert fake_tmux[-1] == (
        "send_text",
        "s",
        "w1",
        "[from human] use the other port" + runtime.HUMAN_REPLY_HINT,
    )


def test_the_copy_of_a_long_text_stays_one_short_line(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.write_as_human("s", "x" * 250, to="w1")
    mine, copy = state.list_messages("s")
    assert len(copy.summary) == state.SUMMARY_LIMIT
    assert copy.summary.startswith("human wrote to w1: xxx")
    assert copy.summary.endswith(f"… (#{mine.id})")


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


@pytest.mark.parametrize(
    ("question", "choices", "free", "reason"),
    [
        ("", None, True, "question is empty"),
        (
            "a\nb",
            None,
            True,
            "question must be one line of visible text: U+000A is not allowed; "
            "put the details in details",
        ),
        ("a\u2029b?", None, True, "U+2029 PARAGRAPH SEPARATOR is not allowed"),
        ("ok?", ["yes\u202e"], True, "a choice must be one line of visible text: U+202E"),
        ("ok?", ["\ufeffno"], True, "U+FEFF ZERO WIDTH NO-BREAK SPACE is not allowed"),
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


def _messages():
    """The session's messages but LADO's requests for the lead's recommendation, which a
    worker's question queues too (test_recommendation.py)."""
    return [m for m in state.list_messages("s") if not m.summary.startswith("recommend on ")]


def _asked(repo, choices=("yes", "later"), free=True):
    """w1, idle, asked the human a question; returns it."""
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    runtime.ask_human("s", "w1", "Merge now?", None, list(choices) if choices else None, free)
    return _messages()[-1]


def test_a_too_long_comment_is_refused_and_the_question_stays_open(repo, fake_tmux):
    question = _asked(repo)
    long = "x" * (runtime.MAX_MESSAGE + 1)
    with pytest.raises(runtime.LadoError, match=f"the limit is {runtime.MAX_MESSAGE}"):
        runtime.dismiss_question("s", question.id, long)
    assert [m.question_state for m in _messages()] == [state.OPEN_QUESTION]


def _two_asked(repo, status=state.IDLE):
    """w1 asked two questions, "Short or long?" (choices short, long) and "Which branch?"
    (a free answer), and has `status`; returns their ids."""
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    runtime.ask_human("s", "w1", "Short or long?", None, ["short", "long"], False)
    runtime.ask_human("s", "w1", "Which branch?")
    state.set_status("s", "w1", status)
    return [m.id for m in state.list_messages("s") if m.kind == state.QUESTION]


def _pastes(fake_tmux, agent="w1"):
    return [call[3] for call in fake_tmux if call[:3] == ("send_text", "s", agent)]


def test_a_reply_with_eleven_files_is_refused(repo, fake_tmux):
    first, second = _two_asked(repo)
    names = [artifacts.upload("s", f"{n}.txt", str(n).encode()).full_name for n in range(11)]
    before = state.list_messages("s")
    with pytest.raises(runtime.LadoError, match="^11 files, the limit is 10$"):
        runtime.answer_questions(
            "s",
            [
                runtime.HumanReply(first, "short"),
                runtime.HumanReply(second, text="x", attached=tuple(names)),
            ],
        )
    assert state.list_messages("s") == before
    assert _question_states() == [state.OPEN_QUESTION, state.OPEN_QUESTION]


def test_a_question_closed_between_the_check_and_the_write_changes_nothing(
    repo, fake_tmux, monkeypatch
):
    first, second = _two_asked(repo)
    store = state.reply_to_questions

    def answered_first(*args, **kwargs):
        # the other tab answers #second after this call checked it open
        with state.connect() as db:
            db.execute("UPDATE messages SET question_state = 'answered' WHERE id = ?", (second,))
        return store(*args, **kwargs)

    monkeypatch.setattr(state, "reply_to_questions", answered_first)
    before = state.list_messages("s")
    with pytest.raises(runtime.LadoError, match=f"^question #{second} is answered$"):
        runtime.answer_questions(
            "s", [runtime.HumanReply(first, "short"), runtime.HumanReply(second, text="x")]
        )
    assert _question_states() == [state.OPEN_QUESTION, state.ANSWERED]
    assert [m.id for m in state.list_messages("s")] == [m.id for m in before]
    assert _pastes(fake_tmux) == []


@pytest.mark.parametrize(
    ("replies", "reason"),
    [
        (lambda q: [], "no answers"),
        (
            lambda q: [runtime.HumanReply(q[0], "short"), runtime.HumanReply(q[0], "long")],
            "question #{0} is answered twice",
        ),
        (
            lambda q: [runtime.HumanReply(q[0], "short"), runtime.HumanReply(q[2], "yes")],
            "answers go to one agent at a time: #{0} is w1's, #{2} is supervisor's",
        ),
        (
            lambda q: [runtime.HumanReply(q[0], "short", skip=True)],
            "question #{0}: skip takes no choice",
        ),
        (
            lambda q: [runtime.HumanReply(q[1], text="x"), runtime.HumanReply(q[0], "maybe")],
            'question #{0} has no choice "maybe"; its choices: short, long',
        ),
        (
            lambda q: [runtime.HumanReply(q[0], text="medium")],
            "question #{0} takes one of its choices, not an own answer",
        ),
        (
            lambda q: [runtime.HumanReply(q[1], text=" ")],
            "choose one of the choices or write an answer",
        ),
        (lambda q: [runtime.HumanReply(999, "x")], "no question #999 in session s"),
    ],
    ids=[
        "empty",
        "twice",
        "two agents",
        "skip with a choice",
        "no such choice",
        "own words",
        "blank",
        "no question",
    ],
)
def test_a_batch_the_core_refuses_changes_nothing(repo, fake_tmux, replies, reason):
    asked = _two_asked(repo)
    runtime.ask_human("s", "supervisor", "Ship?", None, ["yes", "no"])
    asked.append(state.list_messages("s")[-1].id)
    before = state.list_messages("s")
    with pytest.raises(runtime.LadoError, match="^" + re.escape(reason.format(*asked)) + "$"):
        runtime.answer_questions("s", replies(asked))
    assert state.list_messages("s") == before


def _question_states():
    return [m.question_state for m in state.list_messages("s") if m.kind == state.QUESTION]


def test_the_containers_stop_marks_the_open_questions_stopped(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.ask_human("s", "supervisor", "which port?")
    assert runtime.stop_for_container() == ["s"]
    assert _question_states() == [state.QUESTION_STOPPED]


def test_a_reply_to_a_stopped_question_says_so_and_queues_nothing(repo, fake_tmux):
    question = _asked(repo)
    runtime.stop_session("s")
    before = state.list_messages("s")
    refused = f"question #{question.id} is stopped"
    with pytest.raises(runtime.LadoError, match=refused):  # the session stopped
        runtime.answer_question("s", question.id, text="yes")
    assert state.list_messages("s") == before
    runtime.start_session(str(repo), "s", None)
    before = state.list_messages("s")
    with pytest.raises(runtime.LadoError, match=refused):  # and resumed
        runtime.answer_question("s", question.id, text="yes")
    assert state.list_messages("s") == before


def _notices():
    return [m for m in state.list_messages("s") if "closed unanswered" in m.summary]


def test_the_resumed_supervisor_gets_the_questions_the_stop_closed(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.ask_human("s", "supervisor", "Which port?", "The preview needs one.", ["8123", "8200"])
    runtime.ask_human("s", "w1", "Merge now?", None, ["yes"], False)
    runtime.ask_human("s", "w1", "Why red?")
    first, second, third = [m.id for m in state.list_messages("s") if m.kind == state.QUESTION]
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    to_lead = [m for m in state.list_messages("s") if m.state == state.PENDING]
    assert [(m.sender, m.summary) for m in to_lead] == [
        ("lado", "session resumed: 0 open runs"),
        ("lado", "3 questions to the human closed unanswered by the stop"),
    ]
    assert to_lead[1].recipient == "supervisor"
    assert to_lead[1].body == (
        f"#{first} from supervisor: Which port?\n"
        "The preview needs one.\n"
        "Choices: 8123, 8200 (or an answer in the human's own words)\n"
        f"#{second} from w1: Merge now?\n"
        "Choices: yes\n"
        f"#{third} from w1: Why red?\n"
        "No choices: the human answers in their own words.\n"
        "No one answered these. Ask again with ask_human what is still needed; a run's new "
        "worker may ask its own again in its step."
    )


def test_one_stopped_question_is_named_in_the_singular(repo, fake_tmux):
    _asked(repo)
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    [notice] = _notices()
    assert notice.summary == "1 question to the human closed unanswered by the stop"


def test_with_nothing_open_a_resume_says_nothing_of_questions(repo, fake_tmux):
    question = _asked(repo)
    runtime.answer_question("s", question.id, text="yes")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    assert _notices() == []


def test_a_question_is_told_once_after_its_notice_was_read(repo, fake_tmux):
    _asked(repo)
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    [notice] = _notices()
    with state.connect() as db:
        db.execute("UPDATE messages SET state = ? WHERE id = ?", (state.READ, notice.id))
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    assert [m.id for m in _notices()] == [notice.id]


def test_a_stop_before_the_notice_was_read_tells_the_question_again(repo, fake_tmux):
    question = _asked(repo)
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    dropped, told = _notices()
    assert (dropped.state, told.state) == (state.DROPPED, state.PENDING)
    assert state.get_message("s", question.id).answered_by == told.id


def test_a_failed_resume_leaves_the_question_to_the_next_one(repo, fake_tmux, monkeypatch):
    _asked(repo)
    runtime.stop_session("s")
    with monkeypatch.context() as m:
        m.setattr(tmux, "new_session", _fail)
        with pytest.raises(tmux.TmuxError):
            runtime.start_session(str(repo), "s", None)
    runtime.start_session(str(repo), "s", None)
    assert [m.state for m in _notices()] == [state.DROPPED, state.PENDING]


def _human_writes(text="merge w1?", agent="supervisor"):
    """The human's message typed into the idle agent and confirmed by its prompt."""
    state.set_status("s", agent, state.IDLE)
    runtime.write_as_human("s", text, to=agent)
    message = state.list_messages("s")[-1]
    _hook("UserPromptSubmit", agent, {"prompt": runtime.format_message(message)})
    return message


def _reply_state(message):
    return state.get_message("s", message.id).reply_state


def _reminders(agent="supervisor"):
    return [
        m
        for m in state.list_messages("s")
        if m.sender == state.LADO and m.recipient == agent and m.summary.startswith("your answer")
    ]


def test_a_turn_that_wrote_nothing_to_the_human_gets_one_reminder(repo, fake_tmux):
    """A weak model answered the human in its terminal, and never learnt it (LAD-274)."""
    _session_with_worker(repo)
    mine = _human_writes()
    output = _hook("Stop", "supervisor")
    assert _reply_state(mine) == state.REMINDED
    [reminder] = _reminders()
    assert reminder.summary == (
        f"your answer to the human's message #{mine.id} went only to your terminal, which"
        ' the human does not see. If it needs an answer, use send_message(to="human") or'
        " ask_human; else do nothing."
    )
    assert len(reminder.summary) <= state.SUMMARY_LIMIT and not reminder.body
    assert output["reason"] == runtime.format_message(reminder)  # handed over at once


def test_an_answer_after_the_reminder_is_a_reply(repo, fake_tmux):
    _session_with_worker(repo)
    mine = _human_writes()
    _hook("Stop", "supervisor")  # the reminder in its output
    runtime.send_message("s", "supervisor", "human", "merged")
    _hook("Stop", "supervisor", CONTINUED)
    assert _reply_state(mine) == state.REPLIED
    assert len(_reminders()) == 1


def test_silence_after_the_reminder_is_flagged_and_reminded_no_more(repo, fake_tmux):
    _session_with_worker(repo)
    mine = _human_writes()
    _hook("Stop", "supervisor")
    assert _hook("Stop", "supervisor", CONTINUED) is None  # nothing more to hand over
    assert _reply_state(mine) == state.MISSING
    assert len(_reminders()) == 1


def test_a_turn_that_ends_before_the_reminder_is_handed_over_decides_nothing(repo, fake_tmux):
    """The reminder waits in the queue (its agent failed, or got it typed in later): a turn
    that ends meanwhile has not seen it."""
    _session_with_worker(repo)
    mine = _human_writes()
    _hook("Stop", "supervisor")  # the reminder is handed over in this output, not confirmed
    [reminder] = _reminders()
    for waiting in (state.SENT, state.PENDING):
        with state.connect() as db:
            db.execute("UPDATE messages SET state = ? WHERE id = ?", (waiting, reminder.id))
        assert state.check_replies("s", "supervisor") == []  # a turn's end meanwhile
        assert _reply_state(mine) == state.REMINDED


def test_no_reminder_on_a_turn_that_ended_on_an_error(repo, fake_tmux):
    _session_with_worker(repo)
    _human_writes()
    _turn_fails()
    assert _reminders() == []


def _turn_fails():
    event = providers.Event(providers.TURN_END, error="APIError: the server broke")
    hooks.handle(providers.get("claude"), event, "s", "supervisor")


def test_a_message_handed_over_at_the_turn_end_is_checked_at_the_next_one(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "supervisor")  # busy
    runtime.write_as_human("s", "merge w1?")
    mine = state.list_messages("s")[-1]
    assert _hook("Stop", "supervisor")["reason"] == "[from human] merge w1?" + HINT
    assert _reply_state(mine) is None
    runtime.send_message("s", "supervisor", "human", "merged")
    _hook("Stop", "supervisor", CONTINUED)
    assert _reply_state(mine) == state.REPLIED


def _got(sender="supervisor", agent="w1", summary="one last note", body="Reply with ACK"):
    """A message to the idle agent, typed in and confirmed by its prompt: delivered."""
    state.set_status("s", agent, state.IDLE)
    runtime.send_message("s", sender, agent, summary, body)
    message = state.list_messages("s")[-1]
    _hook("UserPromptSubmit", agent, {"prompt": runtime.format_message(message)})
    return message


def _unread_reminders(agent="w1"):
    return [
        m
        for m in state.list_messages("s")
        if m.sender == state.LADO and m.recipient == agent and m.summary.startswith("you have not")
    ]


def test_a_turn_that_left_a_text_unread_gets_one_reminder(repo, fake_tmux):
    """A weak model answered without reading the text, and never learnt it (LAD-234)."""
    _session_with_worker(repo)
    note = _got()
    output = _hook("Stop", "w1")
    [reminder] = _unread_reminders()
    assert reminder.summary == (
        f"you have not read message #{note.id} from supervisor: call read_messages to get"
        " its text; if it asks nothing of you, do nothing."
    )
    assert not reminder.body and reminder.attachments == 0
    assert output["reason"] == runtime.format_message(reminder)  # handed over at once


def test_texts_left_unread_get_one_reminder_naming_each(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.spawn_worker("s", "task", name="w2")
    agent_helpers.forget_tasks("s")
    _hook("UserPromptSubmit", "supervisor")  # busy: both wait for its turn's end
    runtime.send_message("s", "w1", "supervisor", "report", "the details")
    runtime.send_message("s", "w2", "supervisor", "report", "the details")
    w1, w2 = state.list_messages("s")[-2:]
    _hook("Stop", "supervisor")  # hands them over in its output
    _hook("Stop", "supervisor", CONTINUED)
    [reminder] = _unread_reminders("supervisor")
    assert reminder.summary == (
        f"you have not read messages #{w1.id} from w1, #{w2.id} from w2: call read_messages"
        " to get their text; if it asks nothing of you, do nothing."
    )


def test_a_long_list_of_unread_texts_fits_one_line(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "w1")  # busy
    for n in range(9):
        runtime.send_message("s", "supervisor", "w1", f"note {n}", "the text")
    _hook("Stop", "w1")
    _hook("Stop", "w1", CONTINUED)
    [reminder] = _unread_reminders()
    assert len(reminder.summary) <= state.SUMMARY_LIMIT
    assert re.search(r"from supervisor, … \(\d more\): call read_messages", reminder.summary)


def test_an_attached_artifact_left_unread_is_reminded(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "w1")  # busy: the report waits for its turn's end
    state.queue_message("s", "w2", "w1", "the report", attachments=[("a1", "r1")])
    report = state.list_messages("s")[-1]
    _hook("Stop", "w1")  # hands it over in its output
    _hook("Stop", "w1", CONTINUED)
    [reminder] = _unread_reminders()
    assert f"#{report.id} from w2" in reminder.summary


@pytest.mark.parametrize("body", ["", "Reply with ACK"])
def test_a_text_read_or_nothing_to_read_gets_no_reminder(repo, fake_tmux, body):
    _session_with_worker(repo)
    _got(body=body)
    state.read_messages("s", "w1")
    assert _hook("Stop", "w1") is None
    assert _unread_reminders() == []


def test_a_text_is_reminded_once_also_when_the_reminder_is_ignored(repo, fake_tmux):
    _session_with_worker(repo)
    _got()
    _hook("Stop", "w1")  # the reminder in its output
    assert _hook("Stop", "w1", CONTINUED) is None  # still unread: nothing more
    _got(body="")  # a later turn, nothing more to read
    _hook("Stop", "w1")
    assert len(_unread_reminders()) == 1


def test_a_turn_that_ended_on_an_error_reminds_of_no_unread_text(repo, fake_tmux):
    _session_with_worker(repo)
    _got()
    event = providers.Event(providers.TURN_END, error="APIError: 429 Too Many Requests")
    hooks.handle(providers.get("claude"), event, "s", "w1")
    assert _unread_reminders() == []
    _hook("Stop", "w1")  # the next clean turn's end checks it
    assert len(_unread_reminders()) == 1


def test_a_text_handed_over_at_the_turn_end_is_checked_at_the_next_one(repo, fake_tmux):
    _session_with_worker(repo)
    _hook("UserPromptSubmit", "w1")  # busy
    runtime.send_message("s", "supervisor", "w1", "one last note", "Reply with ACK")
    note = state.list_messages("s")[-1]
    output = _hook("Stop", "w1")
    assert output["reason"] == runtime.format_message(note)
    assert _unread_reminders() == []  # sent in this output, not seen yet
    _hook("Stop", "w1", CONTINUED)  # the turn that got it ended without reading it
    [reminder] = _unread_reminders()
    assert f"#{note.id} from supervisor" in reminder.summary


def test_a_message_is_decided_once(repo, fake_tmux):
    _session_with_worker(repo)
    mine = _human_writes()
    _hook("Stop", "supervisor")
    _hook("Stop", "supervisor", CONTINUED)  # the reminder's turn
    runtime.send_message("s", "supervisor", "human", "merged, late")
    _hook("UserPromptSubmit", "supervisor")
    _hook("Stop", "supervisor")
    assert _reply_state(mine) == state.MISSING and len(_reminders()) == 1


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
    kit = repo.parent / "kits" / "boss"
    _write(kit / "kit.yaml", "name: boss\nversion: 1.0.0\nsupervisor: chief\n")
    agent_helpers.install_kit(kit)
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
    prompt = agent_helpers.claude_prompt(cmd)
    assert (
        "Kits whose own supervisor does not lead: boss. Read the skill lead-<kit> before you "
        "take a task for that kit's roles or flows.\n"
    ) in prompt


def test_a_lead_skill_says_when_its_supervisor_lists_no_skills(repo, fake_tmux, lado_home):
    kit = repo.parent / "kits" / "boss"
    _write(kit / "kit.yaml", "name: boss\nversion: 1.0.0\nsupervisor: chief\n")
    agent_helpers.install_kit(kit)
    _write(kit / "agents" / "chief.md", "---\nname: chief\ndescription: c\n---\nLead.\n")
    runtime.start_session(str(repo), "s", None, kit_names=["default", "boss"], provider="claude")
    skill_md = _lead_dir(lado_home) / "lead-skills" / "lead-boss" / "SKILL.md"
    assert skill_md.read_text().endswith("Lead.\n\nThis kit's supervisor lists no skills.\n")
    _write(kit / "agents" / "chief.md", "---\nname: chief\ndescription: c\nskills: []\n---\nL.\n")
    runtime.stop_session("s")
    runtime.start_session(str(repo), "s", None)
    assert skill_md.read_text().endswith("---\nL.\n")


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


@pytest.fixture
def quiet_kit(repo):
    """Kit quiet: a read-only reviewer and a developer."""
    kit = repo.parent / "kits" / "quiet"
    _write(kit / "kit.yaml", "name: quiet\nversion: 1.0.0\n")
    agent_helpers.install_kit(kit)
    _write(
        kit / "agents" / "reviewer.md",
        "---\nname: reviewer\ndescription: reviews\nread_only: true\n---\nYou review.\n",
    )
    _write(kit / "agents" / "dev.md", "---\nname: dev\ndescription: develops\n---\nDevelop.\n")
    return kit


def test_in_a_container_every_agent_is_told_of_mise_and_who_sets_a_default(
    repo, fake_tmux, quiet_kit, monkeypatch
):
    """The common paragraph for every agent, a read-only one too; the sentence on a default
    version for the whole container by whether the agent is the session's supervisor."""
    monkeypatch.setenv("LADO_CONTAINER", "1")
    runtime.start_session(str(repo), "s", None, kit_names=["quiet"], provider="claude")
    supervisor = agent_helpers.claude_prompt(fake_tmux[0][-1])
    runtime.spawn_worker("s", "build", role="dev")
    worker = agent_helpers.claude_prompt(fake_tmux[-1][-1])
    runtime.spawn_worker("s", "review", role="reviewer")
    reviewer = agent_helpers.claude_prompt(fake_tmux[-1][-1])
    run = state.Run("s", "ship/x", "ship", "{}", {}, "Add x", "build", str(repo), "main")
    runtime.spawn_worker("s", "build", role="dev", run=run, has_step=True)
    run_worker = agent_helpers.claude_prompt(fake_tmux[-1][-1])
    for prompt in (supervisor, worker, reviewer, run_worker):
        assert runtime.CONTAINER_INSTRUCTIONS in prompt
        assert prompt.index(runtime.CONTAINER_INSTRUCTIONS) < prompt.index(runtime.MESSAGING)
    assert runtime.CONTAINER_SUPERVISOR in supervisor
    assert runtime.CONTAINER_WORKER not in supervisor
    for prompt in (worker, reviewer, run_worker):
        assert runtime.CONTAINER_WORKER in prompt
        assert runtime.CONTAINER_SUPERVISOR not in prompt
    assert "Only you set a tool's default version" in runtime.CONTAINER_SUPERVISOR
    assert "ask the supervisor" in runtime.CONTAINER_WORKER


@pytest.mark.parametrize("container", [False, True])
def test_every_agent_is_told_to_keep_its_temporary_files_in_its_folder(
    repo, fake_tmux, quiet_kit, monkeypatch, container
):
    """After the lines on messages, for a supervisor, a worker, a read-only worker and a
    run's worker, in and out of LADO's container (LAD-247)."""
    if container:
        monkeypatch.setenv("LADO_CONTAINER", "1")
    runtime.start_session(str(repo), "s", None, kit_names=["quiet"], provider="claude")
    runtime.spawn_worker("s", "build", role="dev")
    runtime.spawn_worker("s", "review", role="reviewer")
    run = state.Run("s", "ship/x", "ship", "{}", {}, "Add x", "build", str(repo), "main")
    runtime.spawn_worker("s", "build", role="dev", run=run, has_step=True)
    windows = [c for c in fake_tmux if c[0] in ("new_session", "new_window")]
    assert len(windows) == 4
    for window in windows:
        prompt = agent_helpers.claude_prompt(window[-1])
        assert prompt.endswith(runtime.MESSAGING + runtime.TEMP_FILES)
    assert "`$TMPDIR`" in runtime.TEMP_FILES
    assert "Never write to a fixed path in `/tmp`" in runtime.TEMP_FILES


def test_a_read_only_worker_on_a_cli_that_cannot_take_edits_is_refused_before_its_worktree(
    repo, fake_tmux, quiet_kit, monkeypatch
):
    monkeypatch.setitem(providers._PROVIDERS, "noskills", _NoSkills())
    runtime.start_session(str(repo), "s", None, kit_names=["quiet"], provider="claude")
    with pytest.raises(runtime.LadoError) as e:
        runtime.spawn_worker("s", "review", role="reviewer", provider="noskills")
    assert str(e.value) == (
        "role reviewer is read-only, but No Skills CLI cannot take its edit tools away; use a "
        "provider that can: claude, codex, kilo, opencode (spawn_worker(provider=...))"
    )
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*") == ""
    assert not (repo / ".lado" / "worktrees" / "s" / "reviewer").exists()


def _codex_config(agent: state.Agent) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    return tomllib.loads((base.config_dir(agent) / "config.toml").read_text())


@pytest.mark.parametrize("mode", ["default", "bypassPermissions"])
def test_a_read_only_codex_lead_and_worker_start(repo, fake_tmux, quiet_kit, mode):
    runtime.start_session(str(repo), "w", mode, kit_names=["quiet"], provider="codex")
    warnings = []
    runtime.spawn_worker("w", "review", role="reviewer", warnings=warnings)
    _write(quiet_kit / "kit.yaml", "name: quiet\nversion: 1.0.0\nsupervisor: reviewer\n")
    started = runtime.start_session(str(repo), "s", mode, kit_names=["quiet"], provider="codex")
    for session, name in (("w", "reviewer"), ("s", "supervisor")):
        agent = state.get_agent(session, name)
        assert agent.read_only is True
        config = _codex_config(agent)
        assert config["features"]["worktrees"] is False
        assert (
            runtime.READ_ONLY_INSTRUCTIONS.format(role="reviewer")
            in (config["developer_instructions"])
        )
    assert [w for w in started.warnings if "apply_patch" in w]
    assert [w for w in warnings if "apply_patch" in w]


def test_a_read_only_lead_on_a_cli_that_cannot_take_edits_refuses_the_start(
    repo, fake_tmux, quiet_kit, monkeypatch
):
    monkeypatch.setitem(providers._PROVIDERS, "noskills", _NoSkills())
    _write(quiet_kit / "kit.yaml", "name: quiet\nversion: 1.0.0\nsupervisor: reviewer\n")
    with pytest.raises(runtime.LadoError) as e:
        runtime.start_session(str(repo), "s", None, kit_names=["quiet"], provider="noskills")
    assert str(e.value) == (
        "role reviewer is read-only, but No Skills CLI cannot take its edit tools away; use a "
        "provider that can: claude, codex, kilo, opencode (lado start --provider NAME)"
    )
    assert state.get_session("s") is None and fake_tmux == []


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
    }
    for name, (kit_names, _) in sessions.items():
        (tmp_path / name).mkdir()
        state.add_session(
            state.Session(name, str(tmp_path / name), None, kits=kit_names, provider="claude")
        )
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


@pytest.mark.parametrize(("value", "delays"), [(None, (15.0, 30.0, 60.0)), ("0.5,1", (0.5, 1.0))])
def test_the_retry_delays_are_lado_retry_delays_else_lado_s_own(value, delays):
    assert runtime.retry_delays_from(value) == delays


def _expecting_kits(repo):
    """Kit sdlc whose role analyst uses skill tracker, which it expects; kit tracker, without
    agents, has it."""
    base = repo.parent / "kits"
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
    agent_helpers.install_kit(base / "sdlc")
    agent_helpers.install_kit(base / "tracker")


@pytest.fixture
def agents_bin(monkeypatch, fake_clis, tmp_path):
    """A folder on the agents' PATH (with the agent CLIs), not on this process's."""
    folder = tmp_path / "agents-bin"
    folder.mkdir()
    path = f"{folder}{os.pathsep}{fake_clis}"
    _shell(monkeypatch, {"PATH": path})
    return folder


def _command(folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("#!/bin/sh\n")
    (folder / name).chmod(0o755)


def _commanding_kits(repo):
    """Kit sdlc (role analyst) expects commands openspec and uv; kit host (role dev) gh."""
    base = repo.parent / "kits"
    for kit, role, commands in (("sdlc", "analyst", "[openspec, uv]"), ("host", "dev", "[gh]")):
        (base / kit / "agents").mkdir(parents=True)
        (base / kit / "kit.yaml").write_text(
            f"name: {kit}\nversion: 1.0.0\nexpects:\n  commands: {commands}\n"
        )
        (base / kit / "agents" / f"{role}.md").write_text(
            f"---\nname: {role}\ndescription: r\n---\nR.\n"
        )
        agent_helpers.install_kit(base / kit)


def _missing_text(path: str) -> str:
    return (
        'kit "sdlc" expects commands "openspec", "uv", which are not on the agents\' PATH: '
        'install them (each launch looks again), or start the session without kit "sdlc"\n'
        'kit "host" expects command "gh", which is not on the agents\' PATH: install it (each '
        'launch looks again), or start the session without kit "host"\n'
        f"the agents' PATH: {path}; for a command installed elsewhere: {agent_env.PATH_ADVICE}"
    )


def test_a_resume_whose_kits_expect_missing_commands_stays_stopped(repo, fake_tmux, agents_bin):
    _commanding_kits(repo)
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    before = state.get_session("s")
    for kit_names in (["sdlc", "host"], None):
        if kit_names is None:
            # Stored with commands the agents' PATH had then and has no longer.
            for name in ("openspec", "uv", "gh"):
                _command(agents_bin, name)
            runtime.start_session(str(repo), "s", None, kit_names=["sdlc", "host"])
            runtime.stop_session("s")
            before = state.get_session("s")
            for name in ("openspec", "uv", "gh"):
                (agents_bin / name).unlink()
        resumes = [e.kind for e in state.list_events("s")].count(state.SESSION_RESUME)
        with pytest.raises(runtime.LadoError) as exc:
            runtime.start_session(str(repo), "s", None, kit_names=kit_names)
        assert str(exc.value) == _missing_text(agent_env.resolve()["PATH"])
        after = state.get_session("s")
        assert after == before and after.stopped_at is not None
        assert [e.kind for e in state.list_events("s")].count(state.SESSION_RESUME) == resumes


def test_a_spawn_whose_kits_expect_a_missing_command_is_refused(repo, fake_tmux, agents_bin):
    _commanding_kits(repo)
    for name in ("openspec", "uv", "gh"):
        _command(agents_bin, name)
    runtime.start_session(str(repo), "s", None, kit_names=["sdlc", "host"], provider="claude")
    windows = len(fake_tmux)
    (agents_bin / "gh").unlink()  # of kit host; the worker's role is sdlc's
    with pytest.raises(runtime.LadoError) as exc:
        runtime.spawn_worker("s", "t", role="analyst")
    assert str(exc.value) == (
        'kit "host" expects command "gh", which is not on the agents\' PATH: install it (each '
        'launch looks again), or start the session without kit "host"\n'
        f"the agents' PATH: {agent_env.resolve()['PATH']}; for a command installed elsewhere: "
        f"{agent_env.PATH_ADVICE}"
    )
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert len(fake_tmux) == windows
    assert runtime.git(str(repo), "branch", "--list", "lado/s/*").strip() == ""
    assert not (repo / ".lado" / "worktrees" / "s").exists()


def test_a_bad_title_refuses_before_anything_starts(repo, fake_tmux):
    with pytest.raises(runtime.LadoError, match="^a title is one line of visible text"):
        runtime.start_session(str(repo), "shop", None, "claude", title="a\nb")
    assert fake_tmux == []
    assert state.get_session("shop") is None


def test_a_resume_with_a_title_is_refused(repo, fake_tmux):
    runtime.start_session(str(repo), "shop", None, "claude")
    state.stop_session("shop")
    with pytest.raises(runtime.LadoError, match="^a title is set with lado title on a resume$"):
        runtime.start_session(str(repo), "shop", None, "claude", title="Shop")
    assert state.get_session("shop").stopped_at is not None


def _set_power(session: str, cli: str, model: str) -> None:
    """Give a running session a power table, as a start with --model stores it."""
    with state.connect() as db:
        db.execute(
            "UPDATE sessions SET power = ? WHERE name = ?",
            (state.PowerTable.single(cli, model).to_json(), session),
        )


def test_a_worker_of_another_cli_gets_the_note(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="kilo")
    _set_power("s", "codex", "gpt-5.6-sol")
    warnings = []
    runtime.spawn_worker("s", "a task", name="w1", provider="claude", warnings=warnings)
    _, argv = agent_helpers.launched(fake_tmux[-1])
    assert "--model" not in argv
    line = (
        "w1 runs on Claude Code's default model: the session's model gpt-5.6-sol is for Codex CLI"
    )
    assert line in warnings
    assert f"s: w1: {line}" in (state.home() / "loop.log").read_text()
    agent = state.get_agent("s", "w1")
    note = "the session's model gpt-5.6-sol is for Codex CLI"
    assert (agent.model, agent.model_source, agent.model_detail) == (None, "cli", note)


def _models(monkeypatch, name, *models):
    """`name`'s CLI lists `models` (none: it gives no list)."""
    listed = (
        providers.base.ModelList(models=models, command=f"{name} models")
        if models
        else providers.base.ModelList(why=f"{name} gives no list")
    )
    monkeypatch.setattr(type(providers.get(name)), "model_list", lambda self, env: listed)


def test_the_model_is_taken_without_its_spaces(repo, fake_tmux, monkeypatch):
    _models(monkeypatch, "kilo", "kilo/a")
    started = runtime.start_session(str(repo), "s", None, provider="kilo", model=" kilo/a ")
    assert not [w for w in started.warnings if "kilo/a" in w]
    assert state.get_session("s").power == state.PowerTable.single("kilo", "kilo/a")
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None, model="  ")
    assert started.changes == ["model: kilo kilo/a -> Kilo CLI's settings"]
    assert state.get_session("s").power == state.PowerTable.single("kilo", "")


_KEPT_REFUSED = (
    "kilo/a is not in Kilo CLI's list of models; kilo models prints the list; the session "
    "ran on it before: resume it with --model '' for Kilo CLI's settings or --model <model> "
    "for another"
)


def _kept_model_gone(repo, fake_tmux, monkeypatch) -> int:
    """Session s of Kilo, stopped with the model kilo/a, which Kilo's list no longer has;
    the number of tmux calls until then."""
    _models(monkeypatch, "kilo", "kilo/a")
    runtime.start_session(str(repo), "s", None, provider="kilo", model="kilo/a")
    runtime.stop_session("s")
    _models(monkeypatch, "kilo", "kilo/b")
    return len(fake_tmux)


def test_a_resume_refuses_a_kept_model_the_list_lacks(repo, fake_tmux, monkeypatch):
    calls = _kept_model_gone(repo, fake_tmux, monkeypatch)
    with pytest.raises(runtime.LadoError) as error:
        runtime.start_session(str(repo), "s", None)
    assert str(error.value) == _KEPT_REFUSED
    sess = state.get_session("s")
    assert sess.stopped_at and sess.power == state.PowerTable.single("kilo", "kilo/a")
    assert len(fake_tmux) == calls  # no agent started


def test_a_resume_to_the_default_of_a_kept_model_the_list_lacks(repo, fake_tmux, monkeypatch):
    _kept_model_gone(repo, fake_tmux, monkeypatch)
    started = runtime.start_session(str(repo), "s", None, model="")
    assert started.changes == ["model: kilo kilo/a -> Kilo CLI's settings"]
    runtime.stop_session("s")
    with pytest.raises(runtime.LadoError) as error:  # a model given: no way out to name
        runtime.start_session(str(repo), "s", None, model="kilo/a")
    assert str(error.value) == (
        "kilo/a is not in Kilo CLI's list of models; kilo models prints the list"
    )


def test_lados_own_resume_of_a_kept_model_the_list_lacks(repo, fake_tmux, monkeypatch):
    _kept_model_gone(repo, fake_tmux, monkeypatch)
    state.resume_session(state.get_session("s"), "")
    state.stop_for_container()
    lines = []
    runtime.resume_at_start(lines.append)
    assert lines == [
        f'lado: could not resume session "s" at the container\'s start: {_KEPT_REFUSED}; '
        "it stays stopped"
    ]
    sess = state.get_session("s")
    assert sess.stopped_at and sess.power == state.PowerTable.single("kilo", "kilo/a")


CHAT = providers.base.CHAT_COMPLETIONS
NOT_GIVEN_WAY_OUT = '; list_models shows the others, model="" is the CLI\'s own settings'


def _on_server(name="Локальная Qwen", cli="opencode", model="qwen3-8b", server="LM Studio дома"):
    """A saved model on a server of that name, saved first when new."""
    saved = state.model_server(server) or state.add_model_server(
        server.encode().hex()[:12], server, "http://localhost:1234", "LM Studio", [CHAT]
    )
    return state.add_model(name, cli, model, saved.id)


def _default(saved):
    state.set_cli_default(state.ModelRef(saved.cli, saved.id, None))


def _answers(monkeypatch, *models):
    """Every saved server answers with `models`; the servers asked, by name."""
    asked = []

    def probe(server):
        asked.append(server.name)
        return model_servers.Probe(server.address, False, "LM Studio", frozenset([CHAT]), models)

    monkeypatch.setattr(model_settings, "probe_saved", probe)
    return asked


def _silent(monkeypatch):
    """No saved server answers."""

    def probe(server):
        raise model_servers.ProbeError(
            f"{server.address} does not answer (connection refused)", silent="connection refused"
        )

    monkeypatch.setattr(model_settings, "probe_saved", probe)


def _config(call):
    env, _ = agent_helpers.launched(call)
    return json.loads(env["OPENCODE_CONFIG_CONTENT"])


def test_a_default_changed_before_a_resume_is_said(repo, fake_tmux, monkeypatch):
    first = _on_server()
    _default(first)
    _answers(monkeypatch, "qwen3-8b", "qwen3-coder-30b")
    runtime.start_session(str(repo), "s", None, provider="opencode")
    runtime.stop_session("s")
    second = _on_server("Рабочая Qwen", model="qwen3-coder-30b")
    _default(second)
    started = runtime.start_session(str(repo), "s", None)
    assert started.changes == ["model: Локальная Qwen -> Рабочая Qwen"]
    assert "changed model: Локальная Qwen -> Рабочая Qwen" in started.warnings
    log = (state.home() / "loop.log").read_text()
    assert "s: supervisor: changed model: Локальная Qwen -> Рабочая Qwen" in log
    assert _config(fake_tmux[-1])["model"] == f"lado-{second.server}/qwen3-coder-30b"


def test_a_default_set_or_cleared_before_a_resume_is_said(repo, fake_tmux, monkeypatch):
    _answers(monkeypatch, "qwen3-8b")
    runtime.start_session(str(repo), "s", None, provider="opencode")
    runtime.stop_session("s")
    _default(_on_server())
    started = runtime.start_session(str(repo), "s", None)
    assert started.changes == ["model: CLI default -> Локальная Qwen"]
    runtime.stop_session("s")
    state.clear_cli_default("opencode")
    started = runtime.start_session(str(repo), "s", None)
    assert started.changes == ["model: Локальная Qwen -> CLI default"]


def test_all_ticked_models_are_in_the_config_whatever_the_session_chose(
    repo, fake_tmux, monkeypatch
):
    one = _on_server()
    other = _on_server("Шлюз Qwen", model="gw-qwen", server="Шлюз")
    _models(monkeypatch, "opencode", "opencode/big-pickle")
    _answers(monkeypatch, "qwen3-8b")
    both = {f"lado-{one.server}", f"lado-{other.server}"}
    for number, model in enumerate(("opencode/big-pickle", "Локальная Qwen", None)):
        runtime.start_session(str(repo), f"s{number}", None, provider="opencode", model=model)
        assert set(_config(fake_tmux[-1])["provider"]) == both


def test_a_failed_start_leaves_no_state(repo, fake_tmux, lado_home, monkeypatch):
    def fails(*_args, **_kwargs):
        (lado_home / "agent-state" / "s" / "supervisor").mkdir(parents=True, exist_ok=True)
        raise tmux.TmuxError("no tmux")

    monkeypatch.setattr(tmux, "new_session", fails)
    with pytest.raises(tmux.TmuxError):
        runtime.start_session(str(repo), "s", None, provider="opencode")
    assert not (lado_home / "agent-state" / "s").exists()


def test_a_kept_model_no_longer_saved_is_refused(repo, fake_tmux, monkeypatch):
    saved = _on_server("Рабочая Qwen")
    _models(monkeypatch, "opencode", "opencode/big-pickle")
    _answers(monkeypatch, "qwen3-8b")
    runtime.start_session(str(repo), "s", None, provider="opencode", model="Рабочая Qwen")
    runtime.stop_session("s")
    state.remove_model(saved.name)
    with pytest.raises(runtime.LadoError) as error:
        runtime.start_session(str(repo), "s", None)
    assert str(error.value) == (
        "the session ran on the model Рабочая Qwen, which is no longer saved; resume it with "
        "--model '' for OpenCode's settings or --model <model> for another"
    )
    assert state.get_session("s").stopped_at


def _break_power(session):
    with state.connect() as db:
        db.execute("UPDATE sessions SET power = 'not json' WHERE name = ?", (session,))


def test_a_table_that_cannot_be_read_refuses_its_resume_only(repo, fake_tmux, monkeypatch):
    _models(monkeypatch, "kilo", "kilo/a")
    runtime.start_session(str(repo), "s", None, provider="kilo", model="kilo/a")
    runtime.stop_session("s")
    _break_power("s")
    with pytest.raises(runtime.LadoError) as error:
        runtime.start_session(str(repo), "s", None)
    assert str(error.value) == (
        "the session's model cannot be read; resume it with --model '' for Kilo CLI's settings or "
        "--model <model> for another"
    )
    started = runtime.start_session(str(repo), "s", None, model="kilo/a")
    assert started.changes == ["model: an unreadable model -> kilo kilo/a"]
    assert state.get_session("s").power == state.PowerTable.single("kilo", "kilo/a")


def test_another_provider_drops_the_model(repo, fake_tmux, monkeypatch):
    _models(monkeypatch, "kilo", "kilo/a")
    runtime.start_session(str(repo), "s", None, provider="kilo", model="kilo/a")
    runtime.stop_session("s")
    started = runtime.start_session(str(repo), "s", None, provider="claude")
    assert started.changes == ["provider: kilo -> claude", "model: kilo kilo/a -> CLI default"]
    assert state.get_session("s").power is None
    _, argv = agent_helpers.launched(fake_tmux[-1])
    assert "--model" not in argv


# A worker on a model by name.


def _nothing_of(repo, fake_tmux, worker):
    assert state.get_agent("s", worker) is None
    assert not [m for m in state.list_messages("s") if m.recipient == worker]
    assert not (repo / ".lado" / "worktrees" / "s" / worker).exists()
    assert runtime.git(str(repo), "branch", "--list", f"lado/s/{worker}") == ""
    assert not [c for c in fake_tmux if c[0] == "new_window"]


def test_a_silent_server_refuses_a_model_given(repo, fake_tmux, monkeypatch):
    runtime.start_session(str(repo), "s", None, provider="opencode")
    _on_server()
    _silent(monkeypatch)
    with pytest.raises(runtime.ModelRefused) as error:
        runtime.spawn_worker("s", "a task", name="w1", model="Локальная Qwen")
    assert str(error.value).startswith(
        "http://localhost:1234 does not answer (connection refused); LADO cannot check qwen3-8b"
    )
    assert NOT_GIVEN_WAY_OUT not in str(error.value)
    _nothing_of(repo, fake_tmux, "w1")


def test_list_models_refuses_a_cli_not_installed(repo, fake_tmux, monkeypatch, tmp_path):
    runtime.start_session(str(repo), "s", None, provider="claude")
    _path_without_clis(monkeypatch, tmp_path)
    with pytest.raises(runtime.ModelRefused, match="Codex CLI is not installed"):
        runtime.list_models("s", "codex")


def test_a_table_that_cannot_be_read_refuses_a_worker_with_its_way_out(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="opencode")
    _break_power("s")
    with pytest.raises(runtime.ModelRefused) as error:
        runtime.spawn_worker("s", "a task", name="w1")
    assert NOT_GIVEN_WAY_OUT in str(error.value)
    _nothing_of(repo, fake_tmux, "w1")
    runtime.spawn_worker("s", "a task", name="w1", model="")  # the way out works
    assert state.get_agent("s", "w1").model is None


# A Claude agent on a model server needs no Claude login (Provider.needs_login).


def _claude_on_server(monkeypatch, name="Шлюз Qwen", model="qwen3-8b", server="Шлюз"):
    """A model of Claude Code on a saved server that proves its API, made its default."""
    found = state.model_server(server) or state.add_model_server(
        server.encode().hex()[:12],
        server,
        "http://localhost:4000",
        "OpenAI-compatible",
        [providers.base.ANTHROPIC_MESSAGES],
    )
    saved = state.add_model(name, "claude", model, found.id)
    monkeypatch.setattr(
        model_settings,
        "probe_saved",
        lambda server: model_servers.Probe(
            server.address,
            False,
            "OpenAI-compatible",
            frozenset([providers.base.ANTHROPIC_MESSAGES]),
            (model,),
        ),
    )
    return saved


def test_a_claude_worker_on_a_server_starts_without_a_login(
    repo, fake_tmux, cli_logins, monkeypatch
):
    runtime.start_session(str(repo), "s", None, provider="kilo")
    _claude_on_server(monkeypatch)
    cli_logins.logged_out()
    runtime.spawn_worker("s", "a task", name="w1", provider="claude", model="Шлюз Qwen")
    assert state.get_agent("s", "w1").model == "qwen3-8b"
    assert runtime.status_reasons("s") == {}


def _check_new(path, name=None, mode=None, provider="claude", kits=None, title=None, model=None):
    """runtime.check_new_session for the folder `path`, which may not exist."""
    return runtime.check_new_session(str(path), name, mode, provider, kits, None, title, model)


def test_a_clone_for_a_session_on_a_server_is_not_refused_for_the_login(
    cli_logins, fake_clis, monkeypatch, tmp_path
):
    _claude_on_server(monkeypatch)
    cli_logins.logged_out()
    _check_new(tmp_path / "app", model="Шлюз Qwen")
    with pytest.raises(runtime.NotLoggedIn):
        _check_new(tmp_path / "app", model="opus")
    with pytest.raises(runtime.NotLoggedIn):
        _check_new(tmp_path / "app")


def test_a_clone_on_the_default_model_of_a_server_is_not_refused_for_the_login(
    cli_logins, fake_clis, monkeypatch, tmp_path
):
    _default(_claude_on_server(monkeypatch))
    cli_logins.logged_out()
    _check_new(tmp_path / "app")


# A new session checked whole before its folder is made (openspec change scratch-checks-first).


def test_a_new_session_is_checked_whole_before_its_folder_exists(repo, fake_tmux, tmp_path):
    _expecting_kits(repo)
    folder = tmp_path / "work" / "shop"
    checked = _check_new(folder, "Shop", kits=["sdlc", "tracker"], title="Кофейня")
    assert (checked.sess.name, checked.sess.repo, checked.sess.title) == (
        "shop",
        os.path.realpath(folder),
        "Кофейня",
    )
    assert (checked.sess.provider, checked.sess.kits, checked.chosen) == (
        "claude",
        ["sdlc", "tracker"],
        None,
    )
    assert not (tmp_path / "work").exists()
    assert state.list_sessions() == [] and fake_tmux == []


def test_a_new_sessions_provider_is_chosen_before_its_folder_exists(
    fake_tmux, monkeypatch, fake_clis, tmp_path
):
    only = tmp_path / "only-kilo"
    only.mkdir()
    (only / "kilo").symlink_to(fake_clis / "kilo")
    _shell(monkeypatch, {"PATH": str(only)})
    checked = _check_new(tmp_path / "shop", provider=None)
    assert (checked.sess.provider, checked.chosen) == (
        "kilo",
        runtime.Suggestion("kilo", runtime.ONLY_INSTALLED),
    )
    _shell(monkeypatch, {"PATH": str(fake_clis)})
    with pytest.raises(runtime.LadoError, match="which agent CLI should the session run"):
        _check_new(tmp_path / "shop", provider=None)
    assert not (tmp_path / "shop").exists()


@pytest.mark.parametrize(
    ("given", "refused"),
    [
        ({"kits": []}, "a session needs at least one kit"),
        ({"kits": ["sdlc"]}, 'kit "sdlc" expects skill "tracker", which no kit'),
        ({"name": "taken"}, 'session "taken" was started in'),
        ({"title": "a\nb"}, "a title is one line"),
        ({"provider": "nope"}, 'unknown provider "nope"'),
        ({"provider": "kilo", "mode": "dontAsk"}, 'permission mode "dontAsk"'),
    ],
)
def test_a_new_session_is_refused_before_its_folder_exists(
    repo, fake_tmux, tmp_path, given, refused
):
    _expecting_kits(repo)
    runtime.start_session(str(repo), "taken", None, provider="claude")
    folder = tmp_path / "shop"
    with pytest.raises((runtime.LadoError, kits.KitError), match=re.escape(refused)):
        _check_new(folder, **given)
    assert not folder.exists()
    assert [s.name for s in state.list_sessions()] == ["taken"]


def test_a_new_session_of_a_taken_name_in_that_folder_is_refused_as_existing(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    with pytest.raises(runtime.SessionExists):
        _check_new(repo, "s")


def test_a_new_session_whose_kits_expect_a_command_not_there_is_refused_first(
    repo, fake_tmux, agents_bin, tmp_path
):
    _commanding_kits(repo)
    with pytest.raises(runtime.LadoError, match='kit "sdlc" expects commands "openspec"'):
        _check_new(tmp_path / "shop", kits=["sdlc"])
    assert not (tmp_path / "shop").exists()


def test_a_new_session_without_the_login_or_with_a_model_refused_is_refused_first(
    repo, fake_tmux, tmp_path, cli_logins, monkeypatch
):
    cli_logins.logged_out()
    with pytest.raises(runtime.NotLoggedIn):
        _check_new(tmp_path / "shop")
    cli_logins.logged_in()
    _on_server()
    _models(monkeypatch, "opencode", "opencode/big-pickle")
    _silent(monkeypatch)
    with pytest.raises(runtime.ModelRefused):
        _check_new(tmp_path / "shop", provider="opencode", model="Локальная Qwen")
    assert not (tmp_path / "shop").exists() and fake_tmux == []


# A turn no hook ends (Provider.failed_turn).


class FailingProvider:
    """The provider of an agent, whose turn `event` ended; the keys it was given."""

    def __init__(self, event):
        self.event = event
        self.asked = []
        self.keys = None

    def failed_turn(self, agent, keys):
        self.asked.append(agent.name)
        self.keys = keys
        return self.event

    def __getattr__(self, name):
        return getattr(providers.get("opencode"), name)


def _failing(monkeypatch, event):
    failing = FailingProvider(event)
    real = providers.get
    monkeypatch.setattr(
        runtime.providers, "get", lambda name: failing if name == "codex" else real(name)
    )
    return failing


def _busy_codex(repo):
    runtime.start_session(str(repo), "s", None, provider="opencode")
    runtime.spawn_worker("s", "a task", name="w1")
    with state.connect() as db:
        db.execute("UPDATE agents SET provider = 'codex' WHERE name = 'w1'")
    state.set_status("s", "w1", state.BUSY)


REFUSED_TURN = providers.Event(
    base.TURN_END, error="the model provider refused the key (401)", output_ignored=True
)


def test_check_turns_ends_a_failed_turn_as_a_hook_does(repo, fake_tmux, monkeypatch):
    _busy_codex(repo)
    _failing(monkeypatch, REFUSED_TURN)
    runtime.check_turns("s")
    assert state.get_agent("s", "w1").status == state.IDLE
    assert [m.summary for m in state.list_messages("s") if m.recipient == runtime.SUPERVISOR] == [
        "turn of w1 ended on an error: the model provider refused the key (401); it is idle"
    ]


def test_check_turns_asks_only_about_busy_agents(repo, fake_tmux, monkeypatch):
    _busy_codex(repo)
    state.set_status("s", "w1", state.IDLE)
    failing = _failing(monkeypatch, REFUSED_TURN)
    runtime.check_turns("s")
    assert failing.asked == []


def test_the_keys_of_a_failed_turn_are_the_kept_key_of_the_agent_s_server(
    repo, fake_tmux, monkeypatch
):
    _busy_codex(repo)
    failing = _failing(monkeypatch, None)
    server = state.add_model_server("gw", "Шлюз", "http://gw", "OpenAI-compatible", [CHAT])
    model_settings._write_key(server.id, "sk-kept")
    failing.launched_on = lambda agent: server.id
    runtime.check_turns("s")
    assert list(failing.keys()) == ["sk-kept"]


@pytest.mark.parametrize("launched_on", [None, "removed"], ids=["no server", "a server removed"])
def test_no_server_has_no_keys(repo, fake_tmux, monkeypatch, launched_on):
    _busy_codex(repo)
    failing = _failing(monkeypatch, None)
    failing.launched_on = lambda agent: launched_on
    runtime.check_turns("s")
    assert list(failing.keys()) == []


def _dropped_message(summary):
    [message] = [m for m in state.list_messages("s") if m.summary == summary]
    return message.state == state.DROPPED


@pytest.mark.parametrize("to", ["supervisor", "w1"])
def test_a_stop_during_the_typing_refuses_the_humans_message(repo, fake_tmux, monkeypatch, to):
    _session_with_worker(repo)
    state.set_status("s", to, state.IDLE)
    agent_helpers.stop_while_typing(monkeypatch, "s")
    with pytest.raises(runtime.LadoError) as refused:
        runtime.write_as_human("s", "merge it", to)
    assert str(refused.value) == agent_helpers.cut_off(to)
    assert _dropped_message("merge it")


def test_a_stop_during_the_typing_refuses_the_humans_answer(repo, fake_tmux, monkeypatch):
    question = _asked(repo)
    agent_helpers.stop_while_typing(monkeypatch, "s")
    with pytest.raises(runtime.LadoError) as refused:
        runtime.answer_question("s", question.id, "yes", "")
    assert str(refused.value) == agent_helpers.cut_off("w1")


def test_a_stop_while_a_message_is_typed_again_refuses_the_next_one(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    runtime.send_message("s", "supervisor", "w1", "first")  # typed, not confirmed: busy
    monkeypatch.setattr(runtime, "RETRY_DELAYS", (0, 0, 0))
    agent_helpers.stop_while_typing(monkeypatch, "s")
    with pytest.raises(runtime.LadoError) as refused:
        runtime.write_as_human("s", "second", "w1")
    assert str(refused.value) == agent_helpers.cut_off("w1")


def test_a_stop_before_the_hand_over_refuses_without_a_list_of_agents(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    sweep_sent = runtime._sweep_sent

    def stopped_first(*args):
        runtime.stop_session("s")
        sweep_sent(*args)

    monkeypatch.setattr(runtime, "_sweep_sent", stopped_first)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.write_as_human("s", "merge it")
    assert str(refused.value) == agent_helpers.cut_off("supervisor")
    assert _dropped_message("merge it")


def test_a_stop_before_the_message_is_stored_refuses_in_the_same_words(repo, fake_tmux):
    _session_with_worker(repo)
    state.stop_session("s")
    with pytest.raises(runtime.LadoError) as refused:
        runtime.post("s", state.LADO, "w1", "your step")
    assert str(refused.value) == agent_helpers.cut_off("w1")


def test_a_tmux_session_gone_without_a_stop_refuses_in_the_same_words(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    fake_tmux.append(("kill_session", "s"))  # killed by hand: has_session says no

    def typed(*_):
        raise tmux.TmuxError("no server running on /tmp/tmux-1/lado")

    monkeypatch.setattr(tmux, "send_text", typed)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.write_as_human("s", "merge it")
    assert str(refused.value) == agent_helpers.cut_off("supervisor")
    assert state.get_session("s").stopped_at is None  # the loop's to find, as ever


@pytest.mark.parametrize(
    "failure",
    [tmux.TmuxError("server exited unexpectedly"), tmux.TmuxMissing("tmux not found")],
    ids=["tmux failed", "no tmux"],
)
def test_a_tmux_failure_of_a_running_session_stays_an_error(repo, fake_tmux, monkeypatch, failure):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)

    def typed(*_):
        raise failure

    monkeypatch.setattr(tmux, "send_text", typed)
    with pytest.raises(type(failure)) as raised:
        runtime.write_as_human("s", "merge it")
    assert raised.value is failure


def test_a_message_in_an_unknown_session_promises_no_resume(lado_home):
    with pytest.raises(runtime.LadoError) as refused:
        runtime.send_message("nowhere", "supervisor", "nobody", "hello")
    assert str(refused.value) == 'no running agent "nobody"; running agents: ; or "human"'


def test_a_session_forgotten_during_the_typing_promises_no_resume(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)

    def typed(*_):
        runtime.stop_session("s")
        runtime.forget_session("s", force=True)
        raise tmux.TmuxError("can't find session: s")

    monkeypatch.setattr(tmux, "send_text", typed)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.write_as_human("s", "merge it")
    assert str(refused.value) == 'unknown session "s"'


def test_a_stopped_agent_of_a_running_session_keeps_the_list_of_running_agents(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.finish_worker("s", "w1", discard=True)
    with pytest.raises(runtime.LadoError) as refused:
        runtime.write_as_human("s", "merge it", "w1")
    assert str(refused.value) == 'no running agent "w1"; running agents: supervisor'


def test_the_tmux_server_gone_ends_a_line_to_the_lead_quietly(repo, fake_tmux, monkeypatch):
    """A hook at an agent's end: the line stays for the session's end to drop, no traceback."""
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    fake_tmux.append(("kill_session", "s"))

    def typed(*_):
        raise tmux.TmuxError("error connecting to /tmp/tmux-1/lado (No such file or directory)")

    monkeypatch.setattr(tmux, "send_text", typed)
    runtime._tell_lead("s", "w1", "w1 ended")
    [line] = [m for m in state.list_messages("s") if m.summary == "w1 ended"]
    assert line.state == state.SENT
