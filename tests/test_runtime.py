import json
import re
import subprocess
from pathlib import Path

import agent_helpers
import pytest

from lado import hooks, kits, providers, runtime, state, tmux


def test_slug():
    assert runtime.slug("My Repo.v2") == "my-repo-v2"
    assert runtime.slug("...") == "lado"


def test_start_session_launches_supervisor(repo, fake_tmux, lado_home):
    started = runtime.start_session(str(repo), None, "acceptEdits")
    assert (started.session.name, started.resumed) == ("my-repo", False)
    [(kind, session, window, cwd, env, cmd)] = fake_tmux
    assert (kind, session, window, cwd) == ("new_session", "my-repo", "supervisor", str(repo))
    assert env == {
        "LADO_HOME": str(lado_home),
        "LADO_SESSION": "my-repo",
        "LADO_AGENT": "supervisor",
        "LADO_TMUX_SOCKET": tmux.socket(),
    }
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


def test_start_refuses_running_session(repo, fake_tmux):
    runtime.start_session(str(repo), None, None)
    with pytest.raises(runtime.LadoError, match="already running"):
        runtime.start_session(str(repo), None, None)


def test_start_requires_git_repo(tmp_path, fake_tmux):
    with pytest.raises(runtime.LadoError, match="not inside a git repository"):
        runtime.start_session(str(tmp_path), None, None)


def test_spawn_worker_creates_worktree_and_passes_task(repo, fake_tmux):
    runtime.start_session(str(repo), "s", None)
    worker = runtime.spawn_worker("s", "fix the bug;")
    assert (worker.name, worker.branch) == ("w1", "lado/s/w1")
    assert (repo / ".lado/worktrees/s/w1/.git").exists()
    kind, _, window, cwd, _, cmd = fake_tmux[-1]
    assert (kind, window, cwd) == ("new_window", "w1", worker.cwd)
    assert cmd[-2] == "--"
    assert cmd[-1].startswith("fix the bug;") and "send_message" in cmd[-1]
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout == ""  # .lado/ is excluded
    assert runtime.spawn_worker("s", "another").name == "w2"


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
    for _, _, window, _, _, cmd in fake_tmux:
        prompt = _prompt(cmd)
        assert "one-line summary" in prompt, window
        assert "body" in prompt and "call read_messages" in prompt, window
        assert "last action of your turn" in prompt, window
        assert "being idle tells" in prompt, window
    supervisor = _prompt(fake_tmux[0][-1])
    assert "Do not relay worker or reviewer reports to the human" in supervisor
    assert "lado log" in supervisor


def _hook(event, agent, payload=None):
    """Run a Claude Code hook of agent `agent` in session "s"; returns its decoded output."""
    claude = providers.get("claude")
    neutral = claude.parse_event(event, json.dumps(payload or {}))
    output = hooks.handle(claude, neutral, "s", agent) if neutral else None
    return json.loads(output) if output else None


def _session_with_worker(repo):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")


def test_message_to_idle_agent_is_pasted(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    assert runtime.send_message("s", "supervisor", "w1", "hi") == "sent"
    assert fake_tmux[-1] == ("send_text", "s", "w1", "[from supervisor] hi")
    assert state.get_agent("s", "w1").status == state.BUSY
    _hook("UserPromptSubmit", "w1", {"prompt": "[from supervisor] hi"})
    _hook("Stop", "w1")
    assert fake_tmux[-1][0] == "send_text"  # confirmed, so not delivered again


def test_typed_message_that_never_arrived_is_delivered_again(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", "report")
    # A dialog swallowed the text: no UserPromptSubmit, the agent looks busy forever.
    monkeypatch.setattr(runtime, "CONFIRM_TIMEOUT", -1)
    assert runtime.send_message("s", "w1", "supervisor", "ping") == "sent"
    assert fake_tmux[-1][3] == "[from w1] report\n[from w1] ping"


def test_stop_hook_redelivers_unconfirmed_message(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", "report")
    monkeypatch.setattr(hooks, "CONFIRM_TIMEOUT", -1)
    _hook("UserPromptSubmit", "supervisor", {"prompt": "something else"})
    out = _hook("Stop", "supervisor")
    assert out == {"decision": "block", "reason": "[from w1] report"}


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


@pytest.mark.parametrize("command", ["clear", "resume"])
def test_conversation_switch_keeps_agent_running(repo, fake_tmux, command):
    _session_with_worker(repo)
    _hook("SessionStart", "supervisor", {"source": "startup"})
    _hook("SessionEnd", "supervisor", {"reason": command})
    # Not ready (e.g. the /resume picker is open): messages wait instead of being typed.
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
    # w1's branch is still there: the next worker gets another name.
    assert runtime.spawn_worker("s", "task").name == "w2"


def test_start_resumes_a_session_whose_tmux_server_is_gone(repo, fake_tmux):
    _session_with_worker(repo)
    runtime.send_message("s", "supervisor", "w1", "hi")
    fake_tmux.append(("kill_session", "s"))  # the tmux server died, no lado stop
    started = runtime.start_session(str(repo), "s", None)
    assert started.resumed
    assert [a.name for a in state.list_agents("s")] == ["supervisor"]
    assert state.list_messages("s")[0].state == state.DROPPED
    assert state.SESSION_STOP in [e.kind for e in state.list_events("s")]


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
    cmd = fake_tmux[0][5]
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
    cmd = fake_tmux[-1][5]
    prompt = cmd[cmd.index("--append-system-prompt") + 1]
    assert prompt.startswith(f"You review. Notes are in {team_kit.resolve()}/notes.")
    assert 'You are worker "w1" in LADO session "s"' in prompt
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]
    mcp = json.loads(open(cmd[cmd.index("--mcp-config") + 1]).read())["mcpServers"]
    assert mcp["db"]["command"] == f"{team_kit.resolve()}/db.sh"
    assert mcp["db"]["env"] == {"TOKEN": "t0k"}
    # The default role gets all skills; this one without the MCP server it does not have.
    runtime.spawn_worker("s", "t", without=["skill:style"])
    cmd = fake_tmux[-1][5]
    added = Path(cmd[cmd.index("--add-dir") + 1], ".claude", "skills")
    assert sorted(p.name for p in added.iterdir()) == ["checklist"]
    runtime.spawn_worker("s", "t", role="reviewer", without=["mcp:db"])
    mcp = json.loads(open(fake_tmux[-1][5][fake_tmux[-1][5].index("--mcp-config") + 1]).read())
    assert list(mcp["mcpServers"]) == ["lado"]


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
    assert fake_tmux[0][5] == ["noskills"]


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
        ("w1", "spawned", "role worker, provider claude"),
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
    monkeypatch.setattr(hooks, "CONFIRM_TIMEOUT", -1)
    assert _hook("Stop", "w1") is None  # nothing meant for the old w1
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
