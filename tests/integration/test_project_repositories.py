"""A project's repositories as the human meets them: `lado project repo add` by a clone of a
local bare repository and from scratch, a session started in each, a clone that fails or
is ended leaving nothing, and `lado project repo remove` with a running and a stopped
session and a worker's branch not pushed (openspec change project-repositories). The CLI
as its own process, real tmux, git and the session loop; the fake agent stands in for an
LLM."""

import os
import signal
import subprocess
import sys
import time

import fake_provider
import pytest
from agent_helpers import fake_git, fake_git_calls, gone, init_repo, wait_for

from lado import projects, runtime, state

pytestmark = pytest.mark.integration


@pytest.fixture
def shop(tmp_path, monkeypatch, git_config):
    """LADO_REPOS=<tmp>/ws (for the CLI's processes and the agents, which inherit it) and the
    project shop, empty; its folder."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    return projects.folder("shop")


@pytest.fixture
def remote(tmp_path) -> str:
    """A bare repository <tmp>/git/frontend.git with one commit on main; its file:// URL."""
    work = init_repo(tmp_path / "frontend-work")
    bare = tmp_path / "git" / "frontend.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True)
    return bare.as_uri()


def lado(*args: str, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(fake_provider.LADO), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, **env},
    )


def idle(session: str) -> bool:
    agent = state.get_agent(session, "supervisor")
    return agent is not None and agent.status == state.IDLE


def stop_all() -> None:
    for sess in state.list_sessions():
        if not sess.stopped_at:
            runtime.stop_session(sess.name)


def _entries(folder) -> list[str]:
    return sorted(p.name for p in folder.iterdir())


def test_repositories_added_by_a_clone_and_from_scratch_take_sessions(shop, remote):
    cloned = lado("project", "repo", "add", "shop", remote)
    assert cloned.returncode == 0, cloned.stderr
    assert cloned.stdout.splitlines() == [
        f"Added repository frontend to project shop: {shop / 'frontend'}",
        "Start a session in it: lado start --project shop --repo frontend",
    ]
    made = lado("project", "repo", "add", "shop", "--new", "backend")
    assert made.returncode == 0, made.stderr
    assert made.stdout.splitlines()[0] == (
        f"Made {shop / 'backend'} a git repository with an empty first commit"
    )
    shown = lado("project", "show", "shop").stdout.splitlines()
    assert "    backend   main  (no remote)" in shown
    assert f"    frontend  main  {remote}" in shown
    try:
        for name in ("frontend", "backend"):
            started = lado(
                "start", "--project", "shop", "--repo", name, "--provider", "fake", "--no-attach"
            )
            assert started.returncode == 0, started.stderr
            wait_for(lambda name=name: idle(f"shop-{name}"), "the supervisor idle", f"shop-{name}")
            assert state.get_session(f"shop-{name}").repo == str(shop / name)
    finally:
        stop_all()


def test_a_failed_clone_leaves_nothing(shop, tmp_path):
    url = (tmp_path / "nothing.git").as_uri()
    failed = lado("project", "repo", "add", "shop", url)
    assert failed.returncode == 1
    assert failed.stderr.splitlines()[-1].startswith(f"lado: cannot clone {url}: ")
    assert _entries(shop) == []
    assert lado("project", "show", "shop").stdout.splitlines()[-1] == "  repositories: none"


def test_a_clone_ended_by_sigterm_leaves_nothing(shop, tmp_path):
    env = {**os.environ, **fake_git(tmp_path / "fake", "slow")}
    process = subprocess.Popen(
        [
            sys.executable,
            str(fake_provider.LADO),
            *("project", "repo", "add", "shop", "https://git.example.com/shop/web"),
        ],
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        deadline = time.monotonic() + 30
        while not fake_git_calls(tmp_path / "fake"):
            assert time.monotonic() < deadline, "git never started"
            time.sleep(0.05)
        assert [name for name in _entries(shop) if name.startswith(".web.clone-")]
        process.send_signal(signal.SIGTERM)
        _, err = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
    assert process.returncode == 128 + signal.SIGTERM, err
    assert err.splitlines()[-1] == "lado: clone cancelled (SIGTERM)"
    assert _entries(shop) == []
    [call] = fake_git_calls(tmp_path / "fake")
    assert gone(call["pid"]) and gone(call["child"])


def test_remove_refuses_while_running_shows_the_workers_branch_and_needs_yes(
    shop, remote, tmp_path
):
    assert lado("project", "repo", "add", "shop", remote).returncode == 0
    assert lado("project", "repo", "add", "shop", "--new", "backend").returncode == 0
    beside = tmp_path / "ws" / "notes.txt"
    beside.write_text("mine")
    frontend = shop / "frontend"
    try:
        runtime.start_session(None, None, None, "fake", project="shop", repo_name="frontend")
        wait_for(lambda: idle("shop-frontend"), "the supervisor idle", "shop-frontend")
        running = lado("project", "repo", "remove", "shop", "frontend", "--yes")
        assert (running.returncode, running.stderr) == (
            1,
            "lado: repository frontend of project shop has sessions not stopped: shop-frontend; "
            "stop them first with lado stop <name>\n",
        )
        worker = runtime.spawn_worker("shop-frontend", "sleep 0", name="dev-1")
        subprocess.run(
            ["git", "-C", worker.cwd, "commit", "-q", "--allow-empty", "-m", "work"], check=True
        )
        assert lado("stop", "shop-frontend").returncode == 0
    finally:
        stop_all()
    asked = lado("project", "repo", "remove", "shop", "frontend")
    assert asked.returncode == 1
    assert asked.stdout.splitlines() == [
        "Sessions to forget: shop-frontend",
        f"Unpushed work in {frontend}:",
        f"  frontend: branch {worker.branch} not pushed",
    ]
    assert asked.stderr == (
        f"lado: removing repository frontend of project shop deletes its folder {frontend} with "
        "everything in it and forgets its 1 session; run again with --yes\n"
    )
    assert frontend.is_dir() and state.get_session("shop-frontend")
    removed = lado("project", "repo", "remove", "shop", "frontend", "--yes")
    assert removed.returncode == 0, removed.stderr
    assert removed.stdout.splitlines()[-1] == "Removed repository frontend from project shop"
    assert not os.path.lexists(frontend)
    assert "shop-frontend" not in lado("ls").stdout
    assert state.get_session("shop-frontend") is None
    assert [r.name for r in projects.repositories("shop")] == ["backend"]
    assert state.get_project("shop") and beside.read_text() == "mine"
    bare = tmp_path / "git" / "frontend.git"
    assert subprocess.run(["git", "-C", str(bare), "rev-parse", "-q", "main"], check=True)


@pytest.mark.parametrize(
    "argv", [["add", "shop", "--new", "site"], ["remove", "shop", "frontend", "--yes"]]
)
def test_an_agent_cannot_add_or_remove(shop, argv):
    init_repo(shop / "frontend")
    refused = lado("project", "repo", *argv, LADO_SESSION="s", LADO_AGENT="w1")
    assert (refused.returncode, refused.stderr) == (
        1,
        f'lado: lado project repo {argv[0]} is for the human; agent "w1" cannot use it\n',
    )
    assert _entries(shop) == ["frontend"]
