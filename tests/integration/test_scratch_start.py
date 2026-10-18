"""A session from scratch through real processes: `lado start --new` makes a new folder a
repository and starts the fake agent there, whose worker gets a worktree of it; and the UI
server does the same for the window, with the session's title (openspec change
start-from-scratch)."""

import os
import subprocess
import sys
from pathlib import Path

import fake_provider
import pytest
from agent_helpers import wait_for
from test_server_launch_process import call, server  # noqa: F401 (a fixture)

from lado import runtime, state

pytestmark = pytest.mark.integration


def idle(session: str, name: str = "supervisor"):
    def check():
        agent = state.get_agent(session, name)
        return agent is not None and agent.status == state.IDLE

    return check


def test_a_new_folder_from_the_terminal(tmp_path, git_config):
    folder = tmp_path / "lado" / "shop"
    done = subprocess.run(
        [sys.executable, str(fake_provider.LADO), "start", "--new", str(folder)]
        + ["--provider", "fake", "--no-attach"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        assert done.returncode == 0, done.stderr
        assert done.stdout.startswith(f"Made {folder} a git repository with an empty first commit")
        sess = state.get_session("shop")
        assert sess is not None and sess.repo == os.path.realpath(folder)
        wait_for(idle("shop"), "the supervisor idle in the new repository", "shop")
        worker = runtime.spawn_worker("shop", "sleep 0", name="w1")
        assert Path(worker.cwd).is_dir() and worker.branch
        listed = subprocess.run(
            ["git", "-C", str(folder), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert f"worktree {worker.cwd}\n" in listed
        wait_for(idle("shop", "w1"), "the worker idle in its worktree", "shop")
    finally:
        if state.get_session("shop"):
            runtime.stop_session("shop")


def test_the_server_starts_from_scratch_with_a_title(git_config, server, tmp_path):  # noqa: F811
    """git_config before server: the server's process takes the test's git config."""
    folder = tmp_path / "lado" / "sait-kofeini"
    given = {
        "where": {"kind": "scratch", "path": str(folder)},
        "name": "sait-kofeini",
        "title": "Сайт кофейни",
        "provider": "fake",
    }
    status, started = call(server, "POST", "/api/sessions", given)
    try:
        assert status == 200, started
        status, sessions = call(server, "GET", "/api/sessions")
        assert [(s["name"], s["title"], s["repo"]) for s in sessions] == [
            ("sait-kofeini", "Сайт кофейни", os.path.realpath(folder))
        ]
        wait_for(idle("sait-kofeini"), "the supervisor idle", "sait-kofeini")
        log = subprocess.run(
            ["git", "-C", str(folder), "log", "--format=%s"], capture_output=True, text=True
        )
        assert log.stdout == "Start from scratch\n"
    finally:
        if state.get_session("sait-kofeini"):
            runtime.stop_session("sait-kofeini")
