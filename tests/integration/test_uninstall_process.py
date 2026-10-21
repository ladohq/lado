"""`lado uninstall` as a process, on a running session of the fake agent with a merged and
an unmerged worker, the UI server and a terminal viewer. The test's LADO_HOME is not the
default ~/.lado, so the program is kept: the test never removes LADO."""

import os
import subprocess
import uuid
from pathlib import Path

import agent_helpers
import fake_provider
import pytest

from lado import runtime, state, terminal, tmux
from lado.server import run as server_run

pytestmark = pytest.mark.integration


@pytest.fixture
def session():
    return f"uni-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def no_server_left():
    yield
    if server_run.lock_path().exists() and server_run.running():
        server_run.stop()


@pytest.fixture(autouse=True)
def no_program(tmp_path, monkeypatch):
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    monkeypatch.setenv("LADO_UPDATE_PREFIX", str(prefix))
    return prefix


def lado(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        fake_provider.lado_command(*args),
        capture_output=True,
        text=True,
        env=os.environ,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=120,
    )


def loops(session: str) -> list[str]:
    found = subprocess.run(["pgrep", "-f", f" loop {session}$"], capture_output=True, text=True)
    return found.stdout.split()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def idle(session: str, agent: str) -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(session, agent)) and a.status == state.IDLE,
        f"{agent} idle",
        session,
    )


def commit(worktree: str, name: str) -> None:
    Path(worktree, name).write_text("done\n")
    runtime.git(worktree, "add", name)
    runtime.git(worktree, "commit", "-q", "-m", f"add {name}")


def running_session(repo, session: str):
    """The session with the fake agent, a merged worker `dev` and an unmerged one `rev`."""
    runtime.start_session(str(repo), session, None, "fake")
    idle(session, "supervisor")
    agent_helpers.wait_for(lambda: len(loops(session)) == 1, "one loop", session)
    dev = runtime.spawn_worker(session, "sleep 0", name="dev")
    rev = runtime.spawn_worker(session, "sleep 0", name="rev")
    idle(session, "dev")
    idle(session, "rev")
    commit(dev.cwd, "dev.txt")
    runtime.git(str(repo), "merge", "-q", "--ff-only", dev.branch)
    commit(rev.cwd, "rev.txt")
    return dev, rev


def agent_pids(session: str) -> list[int]:
    listed = tmux.run("list-panes", "-s", "-t", f"={session}", "-F", "#{pane_pid}")
    return [int(pid) for pid in listed.split()]


def test_uninstall_leaves_nothing(repo, session, lado_home, no_program):
    dev, rev = running_session(repo, session)
    pids = agent_pids(session)
    started = lado("ui", "--no-open", "--port", "0")
    assert started.returncode == 0, started.stderr
    server = server_run.running()
    viewer = terminal.open(session, "supervisor", "view")
    try:
        done = lado("uninstall", "--yes")
    finally:
        viewer.close()
    assert done.returncode == 0, done.stdout + done.stderr
    out = done.stdout
    assert "Stopped the UI server" in out and f'Stopped session "{session}"' in out
    assert not alive(server["pid"])
    assert loops(session) == []
    assert not any(alive(pid) for pid in pids)
    assert not tmux.server_running()
    assert not Path(dev.cwd).exists()
    assert Path(rev.cwd).exists()
    branches = runtime.git(str(repo), "branch", "--format=%(refname:short)").split()
    assert sorted(branches) == ["lado/" + session + "/rev", "main"]
    assert f"git -C '{repo}' branch -D lado/{session}/rev" in out
    assert not lado_home.exists()
    assert f"Kept the program: LADO runs from {no_program}" in out


def test_agents_that_end_with_their_hook_do_not_make_lado_home_again(
    repo, session, lado_home, monkeypatch
):
    """Like Claude Code, the fake agent runs its session-end hook, `lado hook`, when tmux
    kills it, and the hook opens lado.db: the uninstall waits for it before LADO_HOME goes."""
    monkeypatch.setenv("FAKE_AGENT_HANGUP_HOOK", "1")
    monkeypatch.setenv("FAKE_AGENT_HANGUP_DELAY", "1")  # the hook well after tmux's kill
    running_session(repo, session)
    pids = agent_pids(session)
    done = lado("uninstall", "--yes")
    left = [pid for pid in pids if alive(pid)]
    assert done.returncode == 0, done.stdout + done.stderr
    # Once the agents are gone their hooks have run, whenever the uninstall deleted LADO_HOME.
    agent_helpers.wait_for(lambda: not any(alive(pid) for pid in pids), "the agents' end", session)
    assert not lado_home.exists()
    assert left == []


def test_uninstall_keep_data_resumes(repo, session, lado_home):
    dev, rev = running_session(repo, session)
    done = lado("uninstall", "--keep-data", "--yes")
    assert done.returncode == 0, done.stdout + done.stderr
    assert loops(session) == [] and not tmux.server_running()
    assert lado_home.exists() and Path(dev.cwd).exists() and Path(rev.cwd).exists()
    resumed = lado("start", str(repo), "--name", session, "--no-attach")
    assert resumed.returncode == 0, resumed.stderr
    assert resumed.stdout.startswith(f'Resumed session "{session}"')
    assert any(e.kind == state.SESSION_RESUME for e in state.list_events(session))
    assert Path(rev.cwd).exists()
    runtime.stop_session(session)
