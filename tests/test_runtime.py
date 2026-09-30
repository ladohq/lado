import json
import subprocess

import pytest

from lado import hooks, runtime, state


def test_slug():
    assert runtime.slug("My Repo.v2") == "my-repo-v2"
    assert runtime.slug("...") == "lado"


def test_start_session_launches_supervisor(repo, fake_tmux, lado_home):
    sess = runtime.start_session(str(repo), None, "acceptEdits")
    assert sess.name == "my-repo"
    [(kind, session, window, cwd, env, cmd)] = fake_tmux
    assert (kind, session, window, cwd) == ("new_session", "my-repo", "supervisor", str(repo))
    assert env["LADO_AGENT"] == "supervisor"
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


def _session_with_worker(repo):
    runtime.start_session(str(repo), "s", None)
    runtime.spawn_worker("s", "task")


def test_message_to_idle_agent_is_pasted(repo, fake_tmux):
    _session_with_worker(repo)
    state.set_status("s", "w1", state.IDLE)
    assert runtime.send_message("s", "supervisor", "w1", "hi") == "sent"
    assert fake_tmux[-1] == ("send_text", "s", "w1", "[from supervisor] hi")
    assert state.get_agent("s", "w1").status == state.BUSY
    hooks.handle("UserPromptSubmit", "s", "w1", {"prompt": "[from supervisor] hi"})
    hooks.handle("Stop", "s", "w1", {})
    assert fake_tmux[-1][0] == "send_text"  # confirmed, so not delivered again


def test_typed_message_that_never_arrived_is_delivered_again(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", "report")
    # A dialog swallowed the text: no UserPromptSubmit, the agent looks busy forever.
    monkeypatch.setattr(runtime, "CONFIRM_TIMEOUT", -1)
    assert runtime.send_message("s", "w1", "supervisor", "ping") == "sent"
    assert fake_tmux[-1][3] == "[from w1] report\n\n[from w1] ping"


def test_stop_hook_redelivers_unconfirmed_message(repo, fake_tmux, monkeypatch):
    _session_with_worker(repo)
    state.set_status("s", "supervisor", state.IDLE)
    runtime.send_message("s", "w1", "supervisor", "report")
    monkeypatch.setattr(hooks, "CONFIRM_TIMEOUT", -1)
    hooks.handle("UserPromptSubmit", "s", "supervisor", {"prompt": "something else"})
    out = hooks.handle("Stop", "s", "supervisor", {})
    assert out == {"decision": "block", "reason": "[from w1] report"}


def test_message_to_busy_agent_arrives_via_stop_hook(repo, fake_tmux):
    _session_with_worker(repo)
    hooks.handle("UserPromptSubmit", "s", "supervisor", {})
    assert runtime.send_message("s", "w1", "supervisor", "done").startswith("queued")
    assert runtime.send_message("s", "w1", "supervisor", "branch lado/s/w1").startswith("queued")
    out = hooks.handle("Stop", "s", "supervisor", {})
    assert out == {
        "decision": "block",
        "reason": "[from w1] done\n\n[from w1] branch lado/s/w1",
    }
    assert state.get_agent("s", "supervisor").status == state.BUSY
    assert hooks.handle("Stop", "s", "supervisor", {}) is None
    assert state.get_agent("s", "supervisor").status == state.IDLE


def test_message_errors(repo, fake_tmux):
    _session_with_worker(repo)
    with pytest.raises(runtime.LadoError, match="running agents: supervisor, w1"):
        runtime.send_message("s", "w1", "nobody", "hi")
    with pytest.raises(runtime.LadoError, match="write the details to a file"):
        runtime.send_message("s", "w1", "supervisor", "x" * 9000)


def test_status_hooks(repo, fake_tmux):
    _session_with_worker(repo)
    hooks.handle("SessionStart", "s", "supervisor", {})
    hooks.handle("SessionStart", "s", "w1", {})
    assert state.get_agent("s", "supervisor").status == state.IDLE  # no task yet
    assert state.get_agent("s", "w1").status == state.BUSY  # started with a task
    hooks.handle("Notification", "s", "w1", {"notification_type": "permission_prompt"})
    assert state.get_agent("s", "w1").status == state.WAITING
    hooks.handle("Notification", "s", "w1", {"notification_type": "idle_prompt"})
    assert state.get_agent("s", "w1").status == state.WAITING
    hooks.handle("SessionEnd", "s", "w1", {})
    assert state.get_agent("s", "w1").status == state.STOPPED


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


def test_incompatible_database_is_reported(lado_home):
    import sqlite3

    lado_home.mkdir()
    sqlite3.connect(lado_home / "lado.db").execute("CREATE TABLE sessions (name TEXT)")
    with pytest.raises(RuntimeError, match="incompatible schema"):
        state.list_sessions()


def test_stop_session_keeps_worktrees(repo, fake_tmux):
    _session_with_worker(repo)
    workers = runtime.stop_session("s")
    assert [w.name for w in workers] == ["w1"]
    assert state.get_session("s") is None
    assert ("kill_session", "s") in fake_tmux
