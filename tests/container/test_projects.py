"""The workspace in LADO's image (openspec capability container): mounted at the host's
own path, a worker's worktree made in the container is a working tree on the host and its
files the host user's; the container's user takes the workspace owner's uid (not 0), keeps
it over a restart, takes another one with the same home volume, and keeps no way to root;
a workspace not mounted or not writable is named in `docker logs`; compose's
LADO_WORKSPACE holds a LADO project's folder where the host sees it."""

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request

import pytest
from container_helpers import agent_environ, claude_session, docker, free_port, health, new_name

pytestmark = pytest.mark.container

NOT_MOUNTED = (
    "lado: warning: LADO_REPOS is not a folder in the container: {}; "
    "mount the host's folder at this same path"
)
NOT_WRITABLE = "lado: warning: LADO may not write in LADO_REPOS {}"
NO_ROOT = (
    "lado: warning: the container may not become root (no-new-privileges or dropped "
    "capabilities): lado keeps uid 1000 instead of the owner's of {}, and the agents' "
    "LADO_REPOS is /projects"
)
READ_ONLY = (
    "lado: warning: the container's root file system is read-only: lado keeps uid 1000 "
    "instead of the owner's of {}, and the agents' LADO_REPOS is /projects"
)


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
    # The host's workspace, mounted at its own path, with a repository made on the host.
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


def test_projects_of_group_0_leave_lado_its_group(start, projects_volume):
    c = served(start, "-v", f"{projects_volume(2001, 0)}:/srv/projects",
               "-e", "LADO_REPOS=/srv/projects")  # fmt: skip
    assert c.exec("id", "-u").stdout.strip() == "2001"
    assert c.exec("id", "-g").stdout.strip() == "1000"


def test_a_skipped_entrypoint_leaves_its_rule_harmless(start):
    """With the entrypoint replaced (`--entrypoint`, compose's `entrypoint:`, Kubernetes'
    `command:`), the sudo rule stays: the caller's environment must not choose what the
    root phase runs. A `setpriv` first on the PATH the caller hands over is not run."""
    c = start(0, "--entrypoint", "/usr/bin/sleep", command=("infinity",))
    c.sh("mkdir -p /tmp/x && printf '#!/bin/sh\\necho uid=$(id -u)\\n' > /tmp/x/setpriv "
         "&& chmod +x /tmp/x/setpriv")  # fmt: skip
    done = c.sh(
        "LADO_ENTRYPOINT_PATH=/tmp/x:$PATH PATH=/tmp/x:$PATH "
        "sudo -E -n /usr/local/bin/lado-entrypoint id -u",
        check=False,
    )
    assert done.stdout.strip() == "1000", done.stdout + done.stderr


@pytest.mark.parametrize(
    "setting",
    [["--security-opt", "no-new-privileges"], ["--cap-drop", "ALL"]],
    ids=["no-new-privileges", "cap-drop-all"],
)
def test_a_container_that_may_not_become_root_starts_as_1000(start, projects_volume, setting):
    """A container whose settings forbid root (Kubernetes' allowPrivilegeEscalation: false,
    the restricted Pod Security) starts as before this change, uid 1000, and says why."""
    c = served(start, *setting, "-v", f"{projects_volume(2001, 2001)}:/srv/projects",
               "-e", "LADO_REPOS=/srv/projects")  # fmt: skip
    assert c.exec("id", "-u").stdout.strip() == "1000"
    assert NO_ROOT.format("/srv/projects") in c.logs().splitlines(), c.logs()


def test_a_read_only_container_starts_as_1000(start, projects_volume):
    """A read-only root file system (`--read-only`, Kubernetes' readOnlyRootFilesystem):
    nothing of the root step could be written, so the server starts as uid 1000."""
    c = served(start, "--read-only", "--tmpfs", "/tmp",
               "-v", f"{projects_volume(2001, 2001)}:/srv/projects",
               "-e", "LADO_REPOS=/srv/projects")  # fmt: skip
    assert c.exec("id", "-u").stdout.strip() == "1000"
    assert READ_ONLY.format("/srv/projects") in c.logs().splitlines(), c.logs()


def test_lado_repos_not_mounted_warns(start):
    c = served(start, "-e", "LADO_REPOS=/home/me/projects")
    assert NOT_MOUNTED.format("/home/me/projects") in c.logs().splitlines()


def folder_warning(port: int, token: str, path: str) -> str | None:
    """The UI's folder check of `path` (`GET /api/folders`): its warning."""
    query = urllib.parse.urlencode({"path": path})
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/folders?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as answer:
        return json.load(answer)["warning"]


def test_a_lado_project_of_the_compose_workspace_is_on_the_host(compose):
    """LADO_WORKSPACE is mounted at its own path as LADO_REPOS, so a LADO project's folder
    (<workspace>/projects/<id>) is the host's, and the UI does not call it outside."""
    compose.run("up", "-d")
    health(compose.port)
    workspace = compose.env["LADO_WORKSPACE"]
    made = compose.run("exec", "-T", "lado", "lado", "project", "create", "acme")
    acme = os.path.join(workspace, "projects", "acme")
    assert made.stdout.strip() == f"Made project acme: {acme}", made.stdout + made.stderr
    assert os.path.isdir(acme)

    link = compose.run("exec", "-T", "lado", "lado", "ui", "--no-open").stdout.strip()
    token = link.partition("?token=")[2]
    assert folder_warning(compose.port, token, acme) is None
    # The check is not blind: a folder only in the container is outside.
    outside = folder_warning(compose.port, token, "/home/lado/elsewhere")
    assert outside and outside.startswith(f"Outside the workspace ({workspace})"), outside
