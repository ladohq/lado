"""A git server's commit author for real (openspec capability git-servers): `lado git-server
author` on a server saved by `lado git-server add`, then an agent of the fake agent commits
to the server's repository, cloned by its https and its `git@` address, as that author
(author and committer, in the pushed commit too), and to any other repository as the human's
own git settings say; once the author is cleared and the agent restarted, as before. A
worker's commit in its own worktree of a repository LADO cloned carries the author too, also
with the remote's host in another letter case. The global and system git configs stay as
they were."""

import subprocess
from pathlib import Path

import agent_helpers
import fake_git_api
import pytest
from test_git_server_access import (
    SESSION,
    TOKEN,
    lado,
    result,
    run_in_agent,
    script,
    wait_idle,
    world,  # noqa: F401 - a fixture
)

from lado import runtime, state

pytestmark = pytest.mark.integration

NAME, EMAIL = "Ivan Petrov", "ivan.petrov@corp.example"
SERVERS = f"{NAME} <{EMAIL}>|{NAME} <{EMAIL}>"
HUMANS = "LADO test <test@lado.invalid>|LADO test <test@lado.invalid>"  # the world's global
LOG = "git log -1 --format=%an' <'%ae'>|'%cn' <'%ce'>'"


def _author_file(lado_home: Path, server_id: str) -> Path:
    return lado_home / "agents" / SESSION / "supervisor" / "git-authors" / f"{server_id}.gitconfig"


def _log(out: Path, name: str) -> str:
    code, stdout, stderr = result(out, name)
    assert code == 0, f"{name}: {stderr}"
    return stdout.strip()


def test_an_agent_commits_to_a_listed_servers_repositories_as_its_author(
    world,  # noqa: F811 - the fixture imported
    repo,
    tmp_path,
    lado_home,
):
    listed, other, _, before = world
    added = lado("git-server", "add", listed.url, "--token", token=TOKEN + "\n")
    assert added.returncode == 0, added.stderr
    assert added.stdout.splitlines()[0] == f"GitLab, signed in as {fake_git_api.LOGIN}"
    authored = lado("git-server", "author", listed.url, "--name", NAME, "--email", EMAIL)
    assert authored.returncode == 0, authored.stderr
    assert authored.stdout.splitlines()[0] == f"Agents commit to {listed.url} as {NAME} <{EMAIL}>."
    listing = lado("git-server", "list")
    assert listing.stdout.splitlines()[1].endswith(f" {NAME} <{EMAIL}>")
    [server] = state.git_servers()

    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_idle("supervisor")
    assert _author_file(lado_home, server.id).read_text() == (
        f'[user]\n\tname = "{NAME}"\n\temail = "{EMAIL}"\n'
    )
    work, out = tmp_path / "agent-work", tmp_path / "agent-out"
    work.mkdir()
    url = f"{listed.url}/team/app.git"
    run_in_agent(
        "supervisor",
        script(
            tmp_path / "agent.sh",
            out,
            [
                f'cd "{work}"',
                f"run clone git clone -q {url} app",
                "cd app",
                "git commit -q --allow-empty -m by-https",
                "run push git push -q origin HEAD:main",
                f"run https {LOG}",
                f'cd "{work}"',
                "run scpclone git clone -q git@127.0.0.1:team/app.git scp",
                "cd scp",
                "run scpremote git config remote.origin.url",
                "git commit -q --allow-empty -m by-scp",
                f"run scp {LOG}",
                # The repository's own user.name loses to the server's author.
                "git config user.name Local && git config user.email local@repo.invalid",
                "git commit -q --allow-empty -m local",
                f"run local {LOG}",
                f'cd "{work}" && git init -q other && cd other',
                f"git remote add origin {other.url}/team/app.git",
                "git commit -q --allow-empty -m other",
                f"run other {LOG}",
                f'cd "{work}" && git init -q none && cd none',
                "git commit -q --allow-empty -m none",
                f"run none {LOG}",
            ],
        ),
        out,
    )
    for name in ("clone", "push", "scpclone"):
        code, _, stderr = result(out, name)
        assert code == 0, f"{name}: {stderr}"
    assert _log(out, "scpremote") == "git@127.0.0.1:team/app.git"  # as cloned, not rewritten
    assert {name: _log(out, name) for name in ("https", "scp", "local", "other", "none")} == {
        "https": SERVERS,
        "scp": SERVERS,
        "local": SERVERS,
        "other": HUMANS,
        "none": HUMANS,
    }
    pushed = _git_log(listed.root / "team/app.git")
    assert pushed == SERVERS

    # Cleared, and the agent restarted: the human's own author again; the file is gone.
    cleared = lado("git-server", "author", listed.url, "--clear")
    assert cleared.returncode == 0, cleared.stderr
    runtime.stop_session(SESSION)
    assert not _author_file(lado_home, server.id).exists()
    runtime.start_session(str(repo), SESSION, None, "fake")
    wait_idle("supervisor")
    out2 = tmp_path / "agent-out-2"
    run_in_agent(
        "supervisor",
        script(
            tmp_path / "agent2.sh",
            out2,
            [f'cd "{work}/app"', "git commit -q --allow-empty -m after", f"run after {LOG}"],
        ),
        out2,
    )
    assert _log(out2, "after") == HUMANS
    assert not _author_file(lado_home, server.id).parent.exists()
    runtime.stop_session(SESSION)

    # Nothing written to git's global and system configs.
    assert {p: p.read_bytes() for p in before} == before


def test_a_workers_commit_in_its_worktree_of_lados_clone_carries_the_author(
    world,  # noqa: F811 - the fixture imported
    tmp_path,
    lado_home,
):
    listed, _, _, before = world
    # By the name its certificate also holds, so a remote may write it in another case.
    address = listed.url.replace("127.0.0.1", "localhost")
    port = address.rsplit(":", 1)[1]
    assert lado("git-server", "add", address, "--token", token=TOKEN + "\n").returncode == 0
    authored = lado("git-server", "author", address, "--name", NAME, "--email", EMAIL)
    assert authored.returncode == 0, authored.stderr

    # LADO clones the session's repository; a worker commits in its own worktree of it.
    clone_into = tmp_path / "work" / "app"
    started = lado(
        "start", f"{address}/team/app.git", str(clone_into), "--provider", "fake", "--no-attach"
    )
    assert started.returncode == 0, started.stderr
    session = "app"
    try:
        out = tmp_path / "worker-out"
        task = script(
            tmp_path / "worker.sh",
            out,
            [
                "run toplevel git rev-parse --show-toplevel",
                "git commit -q --allow-empty -m by-the-worker",
                f"run worktree {LOG}",
                # The same remote with its host in another case: still the server's.
                f"git remote set-url origin https://LocalHost:{port}/team/app.git",
                "git commit -q --allow-empty -m by-another-case",
                f"run other_case {LOG}",
            ],
        )
        worker = runtime.spawn_worker(session, f"sh sh {task}", name="w1")
        agent_helpers.wait_for(lambda: (out / "done").exists(), "the worker's script", session)
        worktree = Path(state.get_agent(session, "w1").cwd)
        assert worktree != clone_into and (worktree / ".git").is_file()  # a worktree of it
        assert Path(_log(out, "toplevel")).resolve() == worktree.resolve()
        assert worker.name == "w1"
        assert {name: _log(out, name) for name in ("worktree", "other_case")} == {
            "worktree": SERVERS,
            "other_case": SERVERS,
        }
    finally:
        if state.get_session(session):
            runtime.stop_session(session)
    assert {p: p.read_bytes() for p in before} == before


def _git_log(repository: Path) -> str:
    found = subprocess.run(
        ["git", "-C", str(repository), "log", "-1", "--format=%an <%ae>|%cn <%ce>", "main"],
        capture_output=True,
        text=True,
        check=True,
    )
    return found.stdout.strip()
