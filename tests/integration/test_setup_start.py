"""A plain folder set up and started through real processes: the UI server makes a folder
of files a repository, leaving its secret out, and starts the fake agent there, whose
worker gets a worktree with the saved files and not the secret (openspec change
new-session-window, capability folder-setup)."""

import os
import subprocess
from pathlib import Path

import pytest
from agent_helpers import wait_for
from test_scratch_start import idle
from test_server_launch_process import call, server  # noqa: F401 (a fixture)

from lado import runtime, state

pytestmark = pytest.mark.integration


def test_the_server_sets_up_a_folder_and_starts(git_config, server, tmp_path):  # noqa: F811
    """git_config before server: the server's process takes the test's git config."""
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "a.txt").write_text("hello\n")
    (folder / ".env").write_text("KEY=1\n")
    given = {"where": {"kind": "setup", "path": str(folder), "include": []}, "provider": "fake"}
    status, started = call(server, "POST", "/api/sessions", given)
    try:
        assert status == 200, started
        assert started["session"]["repo"] == os.path.realpath(folder)
        wait_for(idle("notes"), "the supervisor idle in the set-up folder", "notes")
        assert (folder / ".gitignore").read_text() == "/.env\n"
        log = subprocess.run(
            ["git", "-C", str(folder), "log", "--format=%s"], capture_output=True, text=True
        )
        assert log.stdout == "First commit\n"
        worker = runtime.spawn_worker("notes", "sleep 0", name="w1")
        assert (Path(worker.cwd) / "a.txt").read_text() == "hello\n"
        assert not (Path(worker.cwd) / ".env").exists()
        wait_for(idle("notes", "w1"), "the worker idle in its worktree", "notes")
    finally:
        if state.get_session("notes"):
            runtime.stop_session("notes")
