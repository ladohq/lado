"""The projects folder in LADO's image (openspec capability container): mounted at the
host's own path, a worker's worktree made in the container is a working tree on the host
and its files the host user's; the container's user takes the projects owner's uid (not 0),
keeps it over a restart, takes another one with the same home volume, and keeps no way to
root; a projects folder not mounted or not writable is named in `docker logs`."""

import os
import subprocess
import time

import pytest
from container_helpers import agent_environ, claude_session, docker, free_port, health, new_name

pytestmark = pytest.mark.container

NOT_MOUNTED = (
    "lado: warning: LADO_REPOS is not a folder in the container: {}; "
    "mount the host's folder at this same path"
)
NOT_WRITABLE = "lado: warning: LADO may not write in LADO_REPOS {}"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def served(start, *args: str, home: str | None = None):
    """The image on a free port, its server answering."""
    port = free_port()
    started = start(port, "-e", f"LADO_PORT={port}", "-p", f"127.0.0.1:{port}:{port}", *args,
                    home=home)  # fmt: skip
    health(port)
    return started


def test_a_workers_worktree_works_on_the_host(start, tmp_path):
    # The host's projects folder, mounted at its own path, with a repository made on the host.
    projects = tmp_path / "projects"
    app = projects / "app"
    app.mkdir(parents=True)
    assert git("init", "-q", "-b", "main", str(app)).returncode == 0
    first = git("-C", str(app), "-c", "user.name=t", "-c", "user.email=t@example.com",
                "commit", "-q", "--allow-empty", "-m", "first")  # fmt: skip
    assert first.returncode == 0, first.stderr
    c = served(start, "-v", f"{projects}:{projects}", "-e", f"LADO_REPOS={projects}")

    claude_session(c, str(app))
    c.python(
        "from lado import runtime; runtime.spawn_worker('smoke', 'wait for messages', name='w1')"
    )
    worktree = app / ".lado" / "worktrees" / "smoke" / "w1"
    c.sh(
        f"cd '{worktree}' && echo hi > hello.txt && git add hello.txt && "
        "git -c user.name=t -c user.email=t@example.com commit -qm hello"
    )

    # On the host: a working tree, not a prunable one, and the container's files the host
    # user's (uid 1001 on GitHub's Linux runner; Docker Desktop maps to the host's user).
    status = git("-C", str(worktree), "status", "--short")
    assert status.returncode == 0, status.stderr
    listing = git("-C", str(app), "worktree", "list", "--porcelain").stdout
    assert f"worktree {worktree}\n" in listing, listing
    assert "prunable" not in listing, listing
    head = git("-C", str(worktree), "rev-parse", "HEAD").stdout.strip()
    assert git("-C", str(app), "log", "-1", "--format=%s", head).stdout.strip() == "hello"
    assert os.stat(worktree / "hello.txt").st_uid == os.getuid()
    common = git("-C", str(worktree), "rev-parse", "--git-common-dir").stdout.strip()
    obj = (worktree / common).resolve() / "objects" / head[:2] / head[2:]
    assert os.stat(obj).st_uid == os.getuid()

    # The worker's own environment, from its login shell: the container's LADO_REPOS.
    deadline = time.monotonic() + 120
    while c.agent_status("smoke", "w1") in ("starting", "gone") and time.monotonic() < deadline:
        time.sleep(0.5)
    assert f"LADO_REPOS={projects}" in agent_environ(c, "smoke", "w1")

    stopped = c.exec("lado", "stop", "--all", check=False)
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr


def test_the_user_takes_the_projects_owner(start, projects_volume):
    volume = projects_volume(2001, 2001)
    c = served(start, "-v", f"{volume}:/srv/projects", "-e", "LADO_REPOS=/srv/projects")
    assert c.exec("id", "-u").stdout.strip() == "2001"
    assert c.exec("id", "-g").stdout.strip() == "2001"
    assert c.sh("find /home/lado ! -uid 2001 -print -quit").stdout == ""
    # The one way to root is gone once the container has started.
    assert c.exec("sudo", "-n", "true", check=False).returncode != 0
    assert c.exec("test", "-e", "/etc/sudoers.d/lado-entrypoint", check=False).returncode != 0
    # docker exec runs as lado with that uid, and finds the server's LADO_HOME.
    link = c.exec("lado", "ui", "--no-open").stdout.strip()
    assert link.startswith(f"http://127.0.0.1:{c.port}/?token="), link
    assert NOT_WRITABLE.format("/srv/projects") not in c.logs()
    # A restart keeps the uid; the stop's signal reaches the server (no 10 s kill).
    began = time.monotonic()
    docker("restart", "-t", "10", c.name)
    assert time.monotonic() - began < 8
    health(c.port)
    assert c.exec("id", "-u").stdout.strip() == "2001"


def test_recreated_with_another_owner_keeps_the_home(start, projects_volume):
    home = f"{new_name()}-home"
    first = served(start, "-v", f"{projects_volume(2001, 2001)}:/srv/projects",
                   "-e", "LADO_REPOS=/srv/projects", home=home)  # fmt: skip
    assert first.exec("id", "-u").stdout.strip() == "2001"
    docker("rm", "-f", first.name)

    second = served(start, "-v", f"{projects_volume(2002, 2002)}:/srv/projects",
                    "-e", "LADO_REPOS=/srv/projects", home=home)  # fmt: skip
    assert second.exec("id", "-u").stdout.strip() == "2002"
    assert second.sh("find /home/lado ! -uid 2002 -print -quit").stdout == ""
    doctor = second.exec("lado", "doctor", check=False).stdout
    assert not [line for line in doctor.splitlines() if line.startswith("[FAIL]")], doctor
    listed = second.exec("lado", "ls", check=False)
    assert listed.returncode == 0, listed.stdout + listed.stderr


def test_an_owner_of_0_keeps_1000_and_warns(start, projects_volume):
    c = served(start, "-v", f"{projects_volume(0, 0)}:/srv/projects",
               "-e", "LADO_REPOS=/srv/projects")  # fmt: skip
    assert c.exec("id", "-u").stdout.strip() == "1000"
    assert NOT_WRITABLE.format("/srv/projects") in c.logs().splitlines()


def test_lado_repos_not_mounted_warns(start):
    c = served(start, "-e", "LADO_REPOS=/home/me/projects")
    assert NOT_MOUNTED.format("/home/me/projects") in c.logs().splitlines()
