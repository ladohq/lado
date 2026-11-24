"""Commit authors on three levels for real (openspec capability commit-authors): LADO's
author set by `lado git-server author`, a git server's and a project's, and an agent of the
fake agent that commits as the first of project → server → LADO's → git's own, author and
committer; `lado start --new` with LADO's author alone; the launch's warning for an author
variable. git's global and system configs stay as they were."""

import os
import subprocess
import sys
from pathlib import Path

import agent_helpers
import fake_provider
import pytest
from test_git_server_access import TOKEN, lado, result, script, world  # noqa: F401 - a fixture

from lado import projects, runtime, state

pytestmark = pytest.mark.integration

ANN = "Ann Lee <ann@example.com>|Ann Lee <ann@example.com>"
IVAN = "Ivan Petrov <ivan.petrov@corp.example>|Ivan Petrov <ivan.petrov@corp.example>"
SHOP = "Shop Bot <bot@shop.example>|Shop Bot <bot@shop.example>"
HUMANS = "LADO test <test@lado.invalid>|LADO test <test@lado.invalid>"  # the world's global
LOG = "git log -1 --format=%an' <'%ae'>|'%cn' <'%ce'>'"


def _ok(done: subprocess.CompletedProcess) -> str:
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def _idle(session: str, agent: str = "supervisor") -> None:
    agent_helpers.wait_for(
        lambda: (a := state.get_agent(session, agent)) and a.status == state.IDLE,
        f"{agent} idle",
        session,
    )


def _run(session: str, path: Path, out: Path, lines: list[str]) -> None:
    """Have the session's supervisor run `lines` as its shell tool, and wait for them."""
    runtime.send_message(session, "human", "supervisor", f"sh sh {script(path, out, lines)}")
    agent_helpers.wait_for(lambda: (out / "done").exists(), "the agent's script", session)


def _log(out: Path, name: str) -> str:
    code, stdout, stderr = result(out, name)
    assert code == 0, f"{name}: {stderr}"
    return stdout.strip()


def _commit(name: str) -> list[str]:
    return [f"git commit -q --allow-empty -m {name}", f"run {name} {LOG}"]


def test_ladOs_author_over_gits_own_and_under_a_servers(
    world,  # noqa: F811 - the fixture imported
    repo,
    tmp_path,
    monkeypatch,
):
    listed, _, _, before = world
    global_config = Path(os.environ["GIT_CONFIG_GLOBAL"])
    _ok(lado("git-server", "add", listed.url, "--token", token=TOKEN + "\n"))
    _ok(lado("git-server", "author", listed.url, "--name", "Ivan Petrov", "--email",
             "ivan.petrov@corp.example"))  # fmt: skip
    said = _ok(lado("git-server", "author", "--name", "Ann Lee", "--email", "ann@example.com"))
    assert said.splitlines()[0] == (
        "Agents commit as Ann Lee <ann@example.com> where no project or git server has an "
        "author of its own."
    )
    assert _ok(lado("git-server", "list")).splitlines()[0] == (
        "LADO's commit author: Ann Lee <ann@example.com>"
    )
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "me@home.example")
    started = runtime.start_session(str(repo), "authors", None, "fake")
    monkeypatch.delenv("GIT_AUTHOR_EMAIL")
    assert (
        "GIT_AUTHOR_EMAIL is set for supervisor: it wins over LADO's commit authors"
        in started.warnings
    )
    runtime.stop_session("authors")
    runtime.start_session(str(repo), "authors", None, "fake")
    _idle("authors")
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    try:
        _run(
            "authors",
            tmp_path / "agent.sh",
            out,
            [
                f'cd "{work}" && git init -q plain && cd plain',
                *_commit("plain"),
                # The repository's own user.name loses to LADO's author.
                "git config user.name Local && git config user.email local@repo.invalid",
                *_commit("local"),
                f'cd "{work}"',
                f"run clone git clone -q {listed.url}/team/app.git app",
                "cd app",
                *_commit("server"),
            ],
        )
        assert _log(out, "clone") == ""
        assert {name: _log(out, name) for name in ("plain", "local", "server")} == {
            "plain": ANN,
            "local": ANN,
            "server": IVAN,
        }
        # Cleared and restarted: git's own again.
        cleared = _ok(lado("git-server", "author", "--clear"))
        assert cleared.splitlines()[0] == "LADO has no commit author now."
        runtime.stop_session("authors")
        runtime.start_session(str(repo), "authors", None, "fake")
        _idle("authors")
        out2 = tmp_path / "out2"
        lines = [f'cd "{work}/plain"', "git config --unset user.name"]
        lines.append("git config --unset user.email")
        _run("authors", tmp_path / "agent2.sh", out2, [*lines, *_commit("after")])
        assert _log(out2, "after") == HUMANS
    finally:
        if state.get_session("authors"):
            runtime.stop_session("authors")
    assert {p: p.read_bytes() for p in before} == before
    assert "Ann Lee" not in global_config.read_text()


def test_a_projects_author_over_a_servers_in_a_project_session(
    world,  # noqa: F811 - the fixture imported
    tmp_path,
    monkeypatch,
):
    listed, _, _, before = world
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    _ok(lado("git-server", "add", listed.url, "--token", token=TOKEN + "\n"))
    _ok(lado("git-server", "author", listed.url, "--name", "Ivan Petrov", "--email",
             "ivan.petrov@corp.example"))  # fmt: skip
    _ok(lado("git-server", "author", "--name", "Ann Lee", "--email", "ann@example.com"))
    _ok(lado("project", "create", "shop"))
    said = _ok(lado("project", "author", "shop", "--name", "Shop Bot", "--email",
                    "bot@shop.example"))  # fmt: skip
    assert said.splitlines()[0] == "Agents of project shop commit as Shop Bot <bot@shop.example>."
    api = agent_helpers.init_repo(projects.folder("shop") / "api")
    subprocess.run(
        ["git", "-C", str(api), "remote", "add", "origin", f"{listed.url}/team/app.git"],
        check=True,
    )
    runtime.start_session(None, None, None, "fake", project="shop", repo_name="api")
    session = "shop-api"
    _idle(session)
    out = tmp_path / "out"
    try:
        _run(session, tmp_path / "agent.sh", out, [f'cd "{api}"', *_commit("project")])
        assert _log(out, "project") == SHOP
        # A worker of the session, in its own worktree, too.
        worker_out = tmp_path / "worker-out"
        task = script(tmp_path / "worker.sh", worker_out, _commit("worker"))
        runtime.spawn_worker(session, f"sh sh {task}", name="w1")
        agent_helpers.wait_for(lambda: (worker_out / "done").exists(), "the worker", session)
        assert _log(worker_out, "worker") == SHOP
    finally:
        if state.get_session(session):
            runtime.stop_session(session)
    assert {p: p.read_bytes() for p in before} == before


def test_a_fresh_start_with_ladOs_author_alone(tmp_path, monkeypatch):
    empty = tmp_path / "empty-gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    folder = tmp_path / "ws" / "coffee"
    argv = [sys.executable, str(fake_provider.LADO), "start", "--new", str(folder)]
    argv += ["--provider", "fake", "--no-attach"]
    refused = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    assert refused.returncode == 1
    assert "nobody signs the agents' commits" in refused.stderr
    assert "Settings → Git servers" in refused.stderr
    assert not folder.exists()
    _ok(lado("git-server", "author", "--name", "Ann Lee", "--email", "ann@example.com"))
    done = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    try:
        assert done.returncode == 0, done.stderr
        log = subprocess.run(
            ["git", "-C", str(folder), "log", "-1", "--format=%an <%ae>|%cn <%ce>"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert log == ANN
        assert empty.read_text() == ""
    finally:
        if state.get_session("coffee"):
            runtime.stop_session("coffee")
