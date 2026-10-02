import os
import shutil
import subprocess

import agent_helpers
import pytest
from agent_helpers import init_repo

from lado import state, tmux
from lado.providers import base


def _config(repo, key, *scope):
    result = subprocess.run(
        ["git", "-C", str(repo), "config", *scope, "--get", key], capture_output=True, text=True
    )
    return result.stdout.strip()


def test_copies_of_the_template_skip_lock_files_that_vanish(tmp_path, monkeypatch):
    # git's background maintenance holds .git/objects/maintenance.lock in the template for a
    # moment: the copy lists the file, and it is gone when the copy reads it.
    monkeypatch.setattr(agent_helpers, "_template", None)
    init_repo(tmp_path / "first")  # makes a fresh template
    template = agent_helpers._template
    (template / ".git" / "objects" / "maintenance.lock").write_text("")
    copyfile = shutil.copyfile

    def vanishing(src, dst, *args, **kwargs):
        if os.fspath(src).endswith(".lock"):
            (template / ".git" / "objects" / "maintenance.lock").unlink(missing_ok=True)
        return copyfile(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copyfile", vanishing)
    repo = init_repo(tmp_path / "second")
    assert not (repo / ".git" / "objects" / "maintenance.lock").exists()
    assert _config(repo, "user.name") == "LADO test"


def test_test_repos_never_run_git_maintenance(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_helpers, "_template", None)
    repo = init_repo(tmp_path / "repo")
    # In the repo's own config, so it holds for whatever process runs git there.
    assert _config(repo, "gc.auto", "--local") == "0"
    assert _config(repo, "maintenance.auto", "--local") == "false"
    # And for every other repo the test run makes (bare remotes, kit source clones).
    other = tmp_path / "other.git"
    subprocess.run(["git", "init", "-q", "--bare", str(other)], check=True)
    assert _config(other, "gc.auto") == "0"
    assert _config(other, "maintenance.auto") == "false"


@pytest.fixture
def failed_session(lado_home, monkeypatch):
    """Session "s" as a live test leaves it when it fails: w1 busy, its report queued, a hook
    error logged, w1's config written, two tmux windows with something on the screen."""
    state.add_session(state.Session("s", "/r", None))
    w1 = state.Agent("s", "w1", "worker", "/r/.lado/worktrees/s/w1", "lado/s/w1", "t", state.BUSY)
    state.add_agent(w1)
    state.add_event("s", "w1", state.STATUS, state.BUSY)
    state.queue_message("s", "w1", "supervisor", "done", "details")
    (lado_home / "hooks.log").write_text("hook error\n")
    (base.config_dir(w1) / "kilo.json").write_text("{}")
    screens = {"supervisor": "supervisor screen\n", "w1": "w1 screen\n"}

    def run(*args, input=None):
        if args[0] == "list-windows":
            return "".join(f"{name}\n" for name in screens)
        if args[0] == "capture-pane":
            return screens[args[-1].split(":")[1]]
        raise AssertionError(args)

    monkeypatch.setattr(tmux, "run", run)
    return "s"


def test_keep_evidence_copies_log_hooks_config_and_screens(failed_session, tmp_path):
    folder = agent_helpers.keep_evidence(failed_session, tmp_path / "evidence")
    log = (folder / "lado-log.txt").read_text()
    assert "w1: busy" in log
    assert "w1 → supervisor [pending] done\n    details" in log
    assert (folder / "hooks.log").read_text() == "hook error\n"
    assert (folder / "agents" / "w1" / "kilo.json").read_text() == "{}"
    assert (
        "w1 worker busy cwd /r/.lado/worktrees/s/w1 branch lado/s/w1"
        in (folder / "agents.txt").read_text()
    )
    assert (folder / "screens" / "supervisor.txt").read_text() == "supervisor screen\n"
    assert (folder / "screens" / "w1.txt").read_text() == "w1 screen\n"


def test_keep_evidence_of_a_stopped_session_keeps_what_is_left(
    failed_session, tmp_path, monkeypatch
):
    def no_server(*args, input=None):
        raise tmux.TmuxError("no server running")

    monkeypatch.setattr(tmux, "run", no_server)
    state.delete_agent("s", "w1")
    folder = agent_helpers.keep_evidence(failed_session, tmp_path / "evidence")
    assert "w1: busy" in (folder / "lado-log.txt").read_text()
    assert "no server running" in (folder / "screens" / "error.txt").read_text()
    assert (folder / "agents" / "w1" / "kilo.json").exists()


def test_a_timed_out_wait_says_what_it_waited_for_and_the_last_state(failed_session):
    with pytest.raises(pytest.fail.Exception) as failed:
        agent_helpers.wait_for(lambda: False, "w1's report", failed_session, timeout=0)
    first = str(failed.value).splitlines()[0]
    assert first.startswith("timed out after 0s waiting for w1's report; ")
    assert "agents: w1 busy" in first
    assert "messages: w1 → supervisor [pending] 'done'" in first
