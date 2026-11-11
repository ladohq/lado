"""Each agent's temporary folder for real (LAD-247): two workers of one session, each in its
tmux window started through lado.agent_env, write `$TMPDIR/pr.md` with their shell and get
two folders of their own; a stop and a resume keep a folder, finish_worker removes it (fake
agent, real tmux, hooks and MCP)."""

import json
import os
import stat
from pathlib import Path

import agent_helpers
import pytest

from lado import runtime, state

pytestmark = pytest.mark.integration

SESSION = "tmpdirs"
# What a turn of each worker does: names its TMPDIR, writes its draft there.
DRAFT = 'sh printf %s "$TMPDIR" > tmpdir.txt && echo "$LADO_AGENT" > "$TMPDIR/pr.md"'


def wait_for(check, what: str):
    return agent_helpers.wait_for(check, what, SESSION)


def seen(agent: str) -> dict:
    path = agent_helpers.fake_logs(SESSION, agent) / "seen.json"
    return json.loads(path.read_text()) if path.exists() else {}


def wait_status(agent: str, expected: str) -> None:
    wait_for(
        lambda: (a := state.get_agent(SESSION, agent)) and a.status == expected,
        f"{agent} to be {expected}",
    )


def drafted(agent: str):
    """The TMPDIR the worker's shell had, once its turn wrote it."""
    wait_for(lambda: seen(agent).get("sh", {}).get("code") == 0, f"{agent}'s draft")
    cwd = state.get_agent(SESSION, agent).cwd
    return (Path(cwd) / "tmpdir.txt").read_text()


def test_two_workers_write_the_same_name_each_in_its_own_folder(repo, agents_tmp):
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_status("supervisor", state.IDLE)
    runtime.spawn_worker(SESSION, DRAFT, name="dev-1")
    runtime.spawn_worker(SESSION, DRAFT, name="dev-2")
    root = agents_tmp / f"lado-{os.getuid()}" / SESSION
    folders = {name: drafted(name) for name in ("dev-1", "dev-2")}
    assert folders == {"dev-1": str(root / "dev-1"), "dev-2": str(root / "dev-2")}
    for name, folder in folders.items():
        path = Path(folder)
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        assert (path / "pr.md").read_text() == f"{name}\n"  # never the other's
    assert stat.S_IMODE(root.parent.stat().st_mode) == 0o700

    wait_status("dev-1", state.IDLE)
    runtime.finish_worker(SESSION, "dev-1", discard=True)
    assert not (root / "dev-1").exists()
    assert (root / "dev-2" / "pr.md").exists()

    # A stop and a resume keep the folders; the supervisor started again has its own.
    (root / "supervisor" / "notes.txt").write_text("kept")
    wait_status("dev-2", state.IDLE)
    runtime.stop_session(SESSION)
    runtime.start_session(str(repo), SESSION, None)
    wait_status("supervisor", state.IDLE)
    assert (root / "supervisor" / "notes.txt").read_text() == "kept"
    assert (root / "dev-2" / "pr.md").read_text() == "dev-2\n"
    runtime.stop_session(SESSION)
    runtime.forget_session(SESSION)
    assert not root.exists()
